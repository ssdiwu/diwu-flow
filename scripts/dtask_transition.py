#!/usr/bin/env python3
"""Unified dtask status transition entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import load_json_or_empty, save_json
from dtask_state import (
    clear_pending_recording,
    clear_task_owner,
    get_task_owner,
    load_runtime_state,
    save_runtime_state,
    session_owned_task_ids,
    set_pending_recording,
    set_task_owner,
    sync_runtime_state,
)

_PLAN_GUARD_MARKER = ".claude/.plan-active"

VALID_RELEASE_TARGETS = {
    "inreview": "InReview",
    "done": "Done",
    "inspec": "InSpec",
    "cancelled": "Cancelled",
}


def _result(ok: bool, status: str, **extra):
    payload = {"ok": ok, "status": status}
    payload.update(extra)
    return payload


def _print_and_exit(payload: dict, rc: int) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(rc)


def _task_path(cwd: Path) -> Path:
    return cwd / ".diwu" / "dtask.json"


def _load_tasks(cwd: Path) -> tuple[dict, list[dict]]:
    data = load_json_or_empty(_task_path(cwd))
    if not isinstance(data, dict):
        _print_and_exit(_result(False, "invalid_task_file", message="dtask.json 根结构必须是对象"), 1)
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        _print_and_exit(_result(False, "invalid_task_file", message="dtask.json.tasks 必须是数组"), 1)
    return data, tasks


def _task_index(tasks: list[dict]) -> dict[int, dict]:
    index = {}
    for task in tasks:
        task_id = task.get("id")
        if isinstance(task_id, int) and not isinstance(task_id, bool):
            index[task_id] = task
    return index


def _parse_task_ids(raw: str) -> list[int]:
    task_ids = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if not piece.isdigit():
            _print_and_exit(_result(False, "invalid_args", message=f"非法 task id: {piece}"), 1)
        task_ids.append(int(piece))
    if not task_ids:
        _print_and_exit(_result(False, "invalid_args", message="至少提供一个 task id"), 1)
    return task_ids


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cleanup_plan_marker(cwd: Path) -> None:
    """清理 plan-guard marker 文件（存在才删）。"""
    marker = cwd / _PLAN_GUARD_MARKER
    if marker.exists():
        try:
            marker.unlink()
        except OSError:
            pass


def _save_claim(cwd: Path, task_payload: dict, runtime_state: dict) -> None:
    save_runtime_state(cwd, runtime_state, remove_legacy=True)
    save_json(task_payload, _task_path(cwd))


def _save_release(cwd: Path, task_payload: dict, runtime_state: dict) -> None:
    save_json(task_payload, _task_path(cwd))
    save_runtime_state(cwd, runtime_state, remove_legacy=True)


def cmd_mark_inspec(cwd: Path, task_ids: list[int]) -> dict:
    task_payload, tasks = _load_tasks(cwd)
    index = _task_index(tasks)
    missing = [task_id for task_id in task_ids if task_id not in index]
    if missing:
        return _result(False, "task_not_found", message=f"未找到任务: {missing}")

    changed = []
    for task_id in task_ids:
        task = index[task_id]
        if task.get("status") != "InDraft":
            return _result(
                False,
                "invalid_transition",
                message=f"Task#{task_id} 当前为 {task.get('status')}，不能 mark-inspec",
            )
        task["status"] = "InSpec"
        changed.append(task_id)

    # 先校验 runtime state，通过后才落盘（避免"失败但已生效"）
    sync_result = sync_runtime_state(cwd, task_payload, persist=True, ensure_exists=True)
    if sync_result.is_invalid:
        return _result(False, "invalid_runtime_state", message=sync_result.reason)

    save_json(task_payload, _task_path(cwd))
    _cleanup_plan_marker(cwd)
    return _result(True, "marked_inspec", task_ids=changed)


def _resolve_session_id(session_id: str) -> str:
    """解析 session_id：auto 时按优先级链获取真实 SID。

    优先级：(1) CLAUDE_SESSION_ID 环境变量（进程级可靠）
           (2) /tmp/.claude_main_session 文件内容（session_start hook 写入）
           (3) fallback 到 drun-<timestamp> + stderr 警告
    """
    if session_id and session_id != "auto":
        return session_id

    # 优先级 1：环境变量（进程级，不受跨会话污染）
    env_sid = os.environ.get("CLAUDE_SESSION_ID", "")
    if env_sid:
        return env_sid

    # 优先级 2：session_start hook 写入的文件
    session_file = Path("/tmp/.claude_main_session")
    if session_file.exists():
        try:
            content = session_file.read_text(encoding="utf-8").strip()
            if content and len(content) > 4:
                return content
        except OSError:
            pass

    # 优先级 3：fallback
    fallback = f"drun-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    print(f"[SESSION_ID] 使用 fallback session ID: {fallback}（非 CC 真实 session ID）", file=sys.stderr)
    return fallback


def cmd_claim(cwd: Path, task_id: int, session_id: str) -> dict:
    session_id = _resolve_session_id(session_id)
    task_payload, tasks = _load_tasks(cwd)
    index = _task_index(tasks)
    task = index.get(task_id)
    if task is None:
        return _result(False, "task_not_found", message=f"未找到 Task#{task_id}")
    if task.get("status") != "InSpec":
        return _result(False, "invalid_transition", message=f"Task#{task_id} 当前为 {task.get('status')}，不能 claim")

    sync_result = sync_runtime_state(cwd, task_payload, persist=True, ensure_exists=True)
    if sync_result.is_invalid:
        return _result(False, "invalid_runtime_state", message=sync_result.reason)

    runtime_state = sync_result.state
    owned = session_owned_task_ids(runtime_state, session_id)
    if owned and owned != [task_id]:
        return _result(False, "invalid_runtime_state", message=f"session {session_id} 已持有 Task#{owned[0]}")

    ok, reason = set_task_owner(runtime_state, task_id, session_id, _now())
    if not ok:
        return _result(False, "invalid_runtime_state", message=reason)

    task["status"] = "InProgress"
    _save_claim(cwd, task_payload, runtime_state)
    _cleanup_plan_marker(cwd)
    return _result(True, "claimed", task_id=task_id, session_id=session_id)


def cmd_release(cwd: Path, task_id: int, session_id: str, target: str) -> dict:
    session_id = _resolve_session_id(session_id)
    task_payload, tasks = _load_tasks(cwd)
    index = _task_index(tasks)
    task = index.get(task_id)
    if task is None:
        return _result(False, "task_not_found", message=f"未找到 Task#{task_id}")
    if task.get("status") != "InProgress":
        return _result(False, "invalid_transition", message=f"Task#{task_id} 当前为 {task.get('status')}，不能 release")

    sync_result = sync_runtime_state(cwd, task_payload, persist=True, ensure_exists=True)
    if sync_result.is_invalid:
        return _result(False, "invalid_runtime_state", message=sync_result.reason)

    runtime_state = sync_result.state
    owner = get_task_owner(runtime_state, task_id)
    if owner is None:
        return _result(False, "invalid_runtime_state", message=f"Task#{task_id} 缺少 owner 记录")
    if owner.get("session_id") != session_id:
        return _result(
            False,
            "owner_mismatch",
            message=f"Task#{task_id} 当前 owner 为 {owner.get('session_id')}，不是 {session_id}",
        )

    task["status"] = VALID_RELEASE_TARGETS[target]
    set_pending_recording(runtime_state, task_id, VALID_RELEASE_TARGETS[target], _now(), session_id)
    clear_task_owner(runtime_state, task_id)
    _save_release(cwd, task_payload, runtime_state)
    return _result(True, "released", task_id=task_id, to=VALID_RELEASE_TARGETS[target])


def cmd_adopt(cwd: Path, task_id: int, session_id: str) -> dict:
    session_id = _resolve_session_id(session_id)
    task_payload, tasks = _load_tasks(cwd)
    index = _task_index(tasks)
    task = index.get(task_id)
    if task is None:
        return _result(False, "task_not_found", message=f"未找到 Task#{task_id}")
    if task.get("status") != "InProgress":
        return _result(False, "invalid_transition", message=f"Task#{task_id} 当前为 {task.get('status')}，不能 adopt")

    sync_result = sync_runtime_state(cwd, task_payload, persist=True, ensure_exists=True)
    if sync_result.is_invalid:
        return _result(False, "invalid_runtime_state", message=sync_result.reason)

    runtime_state = sync_result.state
    owned = session_owned_task_ids(runtime_state, session_id)
    if owned and owned != [task_id]:
        return _result(False, "invalid_runtime_state", message=f"session {session_id} 已持有 Task#{owned[0]}")

    ok, reason = set_task_owner(runtime_state, task_id, session_id, _now())
    if not ok:
        return _result(False, "invalid_runtime_state", message=reason)

    save_runtime_state(cwd, runtime_state, remove_legacy=True)
    return _result(True, "adopted", task_id=task_id, session_id=session_id)


def cmd_show_pending(cwd: Path) -> dict:
    task_payload, _ = _load_tasks(cwd)
    sync_result = sync_runtime_state(cwd, task_payload, persist=True, ensure_exists=True)
    if sync_result.is_invalid:
        return _result(False, "invalid_runtime_state", message=sync_result.reason)
    pr = sync_result.state.get("pending_recording")
    if not pr:
        return _result(True, "no_pending_recording")
    return _result(True, "has_pending_recording", pending_recording=pr)


def cmd_clear_pending(cwd: Path) -> dict:
    result = load_runtime_state(cwd)
    if result.is_invalid:
        return _result(False, "invalid_runtime_state", message=result.reason)
    cleared = clear_pending_recording(result.state)
    if cleared:
        save_runtime_state(cwd, result.state)
    return _result(True, "cleared" if cleared else "was_already_clear")


def cmd_sync_runtime(cwd: Path) -> dict:
    task_payload, _tasks = _load_tasks(cwd)
    sync_result = sync_runtime_state(cwd, task_payload, persist=True, ensure_exists=True)
    if sync_result.is_invalid:
        return _result(False, "invalid_runtime_state", message=sync_result.reason)
    return _result(
        True,
        "runtime_synced",
        changed=sync_result.changed,
        migrated_legacy_loop=sync_result.migrated_legacy_loop,
        cleaned_task_ids=sync_result.cleaned_task_ids,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="dtask status/runtime transition entrypoint")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_cwd_arg(subparser):
        subparser.add_argument("--cwd", default=".", help="项目根目录")

    p_mark = sub.add_parser("mark-inspec", help="批量 InDraft -> InSpec")
    p_mark.add_argument("--task-ids", required=True, help="逗号分隔 task ids")
    add_cwd_arg(p_mark)

    p_claim = sub.add_parser("claim", help="InSpec -> InProgress 并写 owner")
    p_claim.add_argument("--task-id", required=True, type=int)
    p_claim.add_argument("--session-id", default="auto", help="session ID（默认 auto 从文件/环境变量自动解析）")
    add_cwd_arg(p_claim)

    p_release = sub.add_parser("release", help="InProgress -> InReview/Done/InSpec/Cancelled")
    p_release.add_argument("--task-id", required=True, type=int)
    p_release.add_argument("--to", required=True, choices=sorted(VALID_RELEASE_TARGETS.keys()))
    p_release.add_argument("--session-id", default="auto", help="session ID（默认 auto 从文件/环境变量自动解析）")
    add_cwd_arg(p_release)

    p_adopt = sub.add_parser("adopt", help="显式接管其他 session 的 InProgress owner")
    p_adopt.add_argument("--task-id", required=True, type=int)
    p_adopt.add_argument("--session-id", default="auto", help="session ID（默认 auto 从文件/环境变量自动解析）")
    add_cwd_arg(p_adopt)

    p_sync = sub.add_parser("sync-runtime", help="清理 stale owner 并迁移 legacy dloop")
    add_cwd_arg(p_sync)

    p_show_pr = sub.add_parser("show-pending", help="显示 pending_recording 标记（供 drec SKILL 调用）")
    add_cwd_arg(p_show_pr)

    p_clear_pr = sub.add_parser("clear-pending", help="清除 pending_recording 标记（drec closeout 成功后调用）")
    add_cwd_arg(p_clear_pr)

    args = parser.parse_args()
    cwd = Path(args.cwd).resolve()

    if args.command == "mark-inspec":
        payload = cmd_mark_inspec(cwd, _parse_task_ids(args.task_ids))
    elif args.command == "claim":
        payload = cmd_claim(cwd, args.task_id, args.session_id)
    elif args.command == "release":
        payload = cmd_release(cwd, args.task_id, args.session_id, args.to)
    elif args.command == "adopt":
        payload = cmd_adopt(cwd, args.task_id, args.session_id)
    elif args.command == "sync-runtime":
        payload = cmd_sync_runtime(cwd)
    elif args.command == "show-pending":
        payload = cmd_show_pending(cwd)
    elif args.command == "clear-pending":
        payload = cmd_clear_pending(cwd)

    _print_and_exit(payload, 0 if payload.get("ok") else 1)


if __name__ == "__main__":
    main()
