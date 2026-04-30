#!/usr/bin/env python3
"""Unified dtask status transition entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import load_json_or_empty, save_json
from dtask_state import (
    clear_task_owner,
    get_task_owner,
    save_runtime_state,
    session_owned_task_ids,
    set_task_owner,
    sync_runtime_state,
)

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

    save_json(task_payload, _task_path(cwd))
    sync_result = sync_runtime_state(cwd, task_payload, persist=True, ensure_exists=True)
    if sync_result.is_invalid:
        return _result(False, "invalid_runtime_state", message=sync_result.reason)

    return _result(True, "marked_inspec", task_ids=changed)


def cmd_claim(cwd: Path, task_id: int, session_id: str) -> dict:
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
    return _result(True, "claimed", task_id=task_id, session_id=session_id)


def cmd_release(cwd: Path, task_id: int, session_id: str, target: str) -> dict:
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
    clear_task_owner(runtime_state, task_id)
    _save_release(cwd, task_payload, runtime_state)
    return _result(True, "released", task_id=task_id, to=VALID_RELEASE_TARGETS[target])


def cmd_adopt(cwd: Path, task_id: int, session_id: str) -> dict:
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
    p_claim.add_argument("--session-id", required=True)
    add_cwd_arg(p_claim)

    p_release = sub.add_parser("release", help="InProgress -> InReview/Done/InSpec/Cancelled")
    p_release.add_argument("--task-id", required=True, type=int)
    p_release.add_argument("--to", required=True, choices=sorted(VALID_RELEASE_TARGETS.keys()))
    p_release.add_argument("--session-id", required=True)
    add_cwd_arg(p_release)

    p_adopt = sub.add_parser("adopt", help="显式接管其他 session 的 InProgress owner")
    p_adopt.add_argument("--task-id", required=True, type=int)
    p_adopt.add_argument("--session-id", required=True)
    add_cwd_arg(p_adopt)

    p_sync = sub.add_parser("sync-runtime", help="清理 stale owner 并迁移 legacy dloop")
    add_cwd_arg(p_sync)

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
    else:
        payload = cmd_sync_runtime(cwd)

    _print_and_exit(payload, 0 if payload.get("ok") else 1)


if __name__ == "__main__":
    main()
