#!/usr/bin/env python3
"""Shared runtime state helper for dtask-state.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from common import save_json

RUNTIME_STATE_PATH = ".diwu/dtask-state.json"
LEGACY_DLOOP_STATE_PATH = ".diwu/dloop-state.json"
RUNTIME_STATE_VERSION = 1
ACTIVE_TASK_STATUSES = ("InProgress",)


@dataclass
class RuntimeStateSyncResult:
    ok: bool
    state: dict
    reason: str = ""
    changed: bool = False
    migrated_legacy_loop: bool = False
    cleaned_task_ids: list[int] = field(default_factory=list)

    @property
    def is_invalid(self) -> bool:
        return not self.ok


@dataclass
class SessionTaskResolution:
    status: str
    task: dict | None = None
    reason: str = ""
    owner_session_id: str = ""

    @property
    def is_match(self) -> bool:
        return self.status == "match"


def runtime_state_path(cwd: Path | str) -> Path:
    base = Path(cwd) if isinstance(cwd, str) else cwd
    return base / RUNTIME_STATE_PATH


def legacy_dloop_state_path(cwd: Path | str) -> Path:
    base = Path(cwd) if isinstance(cwd, str) else cwd
    return base / LEGACY_DLOOP_STATE_PATH


def default_runtime_state() -> dict:
    return {
        "version": RUNTIME_STATE_VERSION,
        "task_sessions": {},
        "dloop": None,
        "pending_recording": None,
    }


def _read_json(path: Path) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"读取失败: {exc}"
    if not raw.strip():
        return None, "空文件"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"JSON 损坏: {exc}"
    if not isinstance(data, dict):
        return None, "根结构必须是对象"
    return data, None


def _is_non_negative_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _normalize_task_id(task_id) -> int | None:
    if isinstance(task_id, bool):
        return None
    if isinstance(task_id, int):
        return task_id if task_id >= 0 else None
    if isinstance(task_id, str) and task_id.isdigit():
        return int(task_id)
    return None


def _normalize_owner(owner: dict) -> tuple[dict | None, str | None]:
    if not isinstance(owner, dict):
        return None, "task_sessions.* 必须是对象"
    if "status" in owner:
        return None, "task_sessions 不允许保存 status 字段"
    session_id = owner.get("session_id") or owner.get("sessionId")
    started_at = owner.get("started_at")
    if not isinstance(session_id, str) or not session_id:
        return None, "task_sessions.*.session_id 必须是非空字符串"
    if not isinstance(started_at, str) or not started_at:
        return None, "task_sessions.*.started_at 必须是非空字符串"
    return {
        "session_id": session_id,
        "started_at": started_at,
    }, None


def _normalize_loop(loop: dict | None) -> tuple[dict | None, str | None]:
    if loop is None:
        return None, None
    if not isinstance(loop, dict):
        return None, "dloop 必须是对象或 null"

    if not isinstance(loop.get("active"), bool):
        return None, "dloop.active 必须是 bool"

    active = loop.get("active", False)
    started_at = loop.get("started_at", "")

    if active:
        if not isinstance(started_at, str) or not started_at:
            return None, "dloop.started_at 必须是非空字符串"
    else:
        if started_at and not isinstance(started_at, str):
            return None, "dloop.started_at 必须是字符串"

    completed = loop.get("completed_task_ids", [])
    if not isinstance(completed, list) or not all(_is_non_negative_int(task_id) for task_id in completed):
        return None, "dloop.completed_task_ids 必须是非负整数列表"

    current_iteration = loop.get("current_iteration", 0)
    if not _is_non_negative_int(current_iteration):
        return None, "dloop.current_iteration 必须是非负整数"

    max_tasks = loop.get("max_tasks", 0)
    if not _is_non_negative_int(max_tasks):
        return None, "dloop.max_tasks 必须是非负整数"

    stopped_at = loop.get("stopped_at")
    if stopped_at is not None and not isinstance(stopped_at, str):
        return None, "dloop.stopped_at 必须是字符串或 null"

    stop_reason = loop.get("stop_reason")
    if stop_reason is not None and not isinstance(stop_reason, str):
        return None, "dloop.stop_reason 必须是字符串或 null"

    mode = loop.get("mode", "cron")
    if not isinstance(mode, str) or mode not in ("cron",):
        return None, f"dloop.mode 必须是 'cron'，实际: {mode!r}"

    cron_job_id = loop.get("cron_job_id")
    if cron_job_id is not None and not isinstance(cron_job_id, str):
        return None, "dloop.cron_job_id 必须是字符串或 null"

    initial_done = loop.get("initial_done_ids", [])
    if not isinstance(initial_done, list) or not all(_is_non_negative_int(tid) for tid in initial_done):
        initial_done = []

    return {
        "active": active,
        "started_at": started_at,
        "completed_task_ids": completed,
        "initial_done_ids": initial_done,
        "current_iteration": current_iteration,
        "max_tasks": max_tasks,
        "stopped_at": stopped_at,
        "stop_reason": stop_reason,
        "mode": mode,
        "cron_job_id": cron_job_id,
    }, None


def _normalize_pending_recording(value) -> tuple[dict | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, dict):
        return None, "pending_recording 必须是对象或 null"
    task_id = value.get("task_id")
    target_status = value.get("target_status")
    released_at = value.get("released_at")
    session_id = value.get("session_id")
    if not _is_non_negative_int(task_id):
        return None, "pending_recording.task_id 必须是非负整数"
    if not isinstance(target_status, str) or not target_status:
        return None, "pending_recording.target_status 必须是非空字符串"
    if not isinstance(released_at, str) or not released_at:
        return None, "pending_recording.released_at 必须是字符串"
    if not isinstance(session_id, str) or not session_id:
        return None, "pending_recording.session_id 必须是非空字符串"
    return {
        "task_id": task_id,
        "target_status": target_status,
        "released_at": released_at,
        "session_id": session_id,
    }, None


def normalize_runtime_state(data: dict | None) -> tuple[dict | None, bool, str | None]:
    source = data or default_runtime_state()
    if not isinstance(source, dict):
        return None, False, "dtask-state 根结构必须是对象"

    version = source.get("version", RUNTIME_STATE_VERSION)
    if not isinstance(version, int) or isinstance(version, bool) or version <= 0:
        return None, False, "version 必须是正整数"

    raw_sessions = source.get("task_sessions", {})
    if raw_sessions is None:
        raw_sessions = {}
    if not isinstance(raw_sessions, dict):
        return None, False, "task_sessions 必须是对象"

    task_sessions: dict[str, dict] = {}
    session_to_task: dict[str, str] = {}
    changed = data is None

    for raw_task_id, raw_owner in raw_sessions.items():
        task_id = _normalize_task_id(raw_task_id)
        if task_id is None:
            return None, False, f"非法 task_sessions key: {raw_task_id!r}"
        owner, err = _normalize_owner(raw_owner)
        if err:
            return None, False, err
        task_key = str(task_id)
        existing_task = session_to_task.get(owner["session_id"])
        if existing_task is not None and existing_task != task_key:
            return None, False, (
                f"同一 session 不可同时持有多个任务: {owner['session_id']} -> "
                f"Task#{existing_task}, Task#{task_key}"
            )
        session_to_task[owner["session_id"]] = task_key
        task_sessions[task_key] = owner
        if raw_task_id != task_key or raw_owner != owner:
            changed = True

    dloop, err = _normalize_loop(source.get("dloop"))
    if err:
        return None, False, err

    pending_recording, pr_err = _normalize_pending_recording(source.get("pending_recording"))
    if pr_err:
        return None, False, pr_err

    normalized = {
        "version": version,
        "task_sessions": task_sessions,
        "dloop": dloop,
        "pending_recording": pending_recording,
    }
    if normalized != source:
        changed = True
    return normalized, changed, None


def _task_list(dtask_data: dict | None) -> list[dict]:
    if not isinstance(dtask_data, dict):
        return []
    tasks = dtask_data.get("tasks", [])
    if not isinstance(tasks, list):
        return []
    return [task for task in tasks if isinstance(task, dict)]


def _active_task_ids(dtask_data: dict | None) -> set[int]:
    active_ids = set()
    for task in _task_list(dtask_data):
        task_id = _normalize_task_id(task.get("id"))
        if task_id is None:
            continue
        if task.get("status") in ACTIVE_TASK_STATUSES:
            active_ids.add(task_id)
    return active_ids


def load_runtime_state(cwd: Path | str) -> RuntimeStateSyncResult:
    path = runtime_state_path(cwd)
    raw, err = _read_json(path)
    if err:
        return RuntimeStateSyncResult(False, default_runtime_state(), reason=f"dtask-state.json {err}")
    normalized, changed, norm_err = normalize_runtime_state(raw)
    if norm_err:
        return RuntimeStateSyncResult(False, default_runtime_state(), reason=norm_err)
    return RuntimeStateSyncResult(True, normalized or default_runtime_state(), changed=changed)


def save_runtime_state(cwd: Path | str, state: dict, *, remove_legacy: bool = False) -> None:
    path = runtime_state_path(cwd)
    save_json(state, path)
    if remove_legacy:
        delete_legacy_dloop_state(cwd)


def delete_legacy_dloop_state(cwd: Path | str) -> None:
    legacy_path = legacy_dloop_state_path(cwd)
    if legacy_path.exists():
        try:
            legacy_path.unlink()
        except OSError:
            pass


def sync_runtime_state(
    cwd: Path | str,
    dtask_data: dict | None = None,
    *,
    persist: bool = True,
    ensure_exists: bool = False,
) -> RuntimeStateSyncResult:
    cwd_path = Path(cwd) if isinstance(cwd, str) else cwd
    result = load_runtime_state(cwd_path)
    if result.is_invalid:
        return result

    state = result.state
    changed = result.changed
    migrated_legacy_loop = False
    cleaned_task_ids: list[int] = []

    legacy_path = legacy_dloop_state_path(cwd_path)
    if state.get("dloop") is None and legacy_path.exists():
        raw_legacy, legacy_err = _read_json(legacy_path)
        if legacy_err:
            return RuntimeStateSyncResult(False, state, reason=f"legacy dloop-state.json {legacy_err}")
        legacy_loop, loop_err = _normalize_loop(raw_legacy)
        if loop_err:
            return RuntimeStateSyncResult(False, state, reason=f"legacy dloop-state.json {loop_err}")
        state["dloop"] = legacy_loop
        changed = True
        migrated_legacy_loop = True

    if dtask_data is not None:
        active_ids = _active_task_ids(dtask_data)
        for task_key in list(state.get("task_sessions", {}).keys()):
            if int(task_key) not in active_ids:
                del state["task_sessions"][task_key]
                cleaned_task_ids.append(int(task_key))
                changed = True

        session_to_task: dict[str, str] = {}
        for task_key, owner in state.get("task_sessions", {}).items():
            session_id = owner["session_id"]
            existing_task = session_to_task.get(session_id)
            if existing_task is not None and existing_task != task_key:
                return RuntimeStateSyncResult(
                    False,
                    state,
                    reason=(
                        f"同一 session 不可同时持有多个任务: {session_id} -> "
                        f"Task#{existing_task}, Task#{task_key}"
                    ),
                )
            session_to_task[session_id] = task_key

    # self-heal: 清除指向不存在任务或状态不匹配的 stale pending_recording 标记
    pr = state.get("pending_recording")
    if pr and isinstance(pr, dict) and dtask_data is not None:
        pr_task_id = pr.get("task_id")
        pr_target = pr.get("target_status", "")
        task_map = {t.get("id"): t for t in _task_list(dtask_data) if isinstance(t.get("id"), int)}
        target_task = task_map.get(pr_task_id)
        if target_task is None:
            state["pending_recording"] = None
            changed = True
        elif target_task.get("status") != pr_target:
            state["pending_recording"] = None
            changed = True

    if persist and (changed or ensure_exists or migrated_legacy_loop):
        save_runtime_state(cwd_path, state, remove_legacy=True)
    elif persist and legacy_path.exists() and runtime_state_path(cwd_path).exists():
        delete_legacy_dloop_state(cwd_path)

    return RuntimeStateSyncResult(
        True,
        state,
        changed=changed,
        migrated_legacy_loop=migrated_legacy_loop,
        cleaned_task_ids=cleaned_task_ids,
    )


def get_task_owner(runtime_state: dict, task_id: int) -> dict | None:
    return (runtime_state.get("task_sessions") or {}).get(str(task_id))


def session_owned_task_ids(runtime_state: dict, session_id: str) -> list[int]:
    owned = []
    for task_key, owner in (runtime_state.get("task_sessions") or {}).items():
        if owner.get("session_id") == session_id:
            owned.append(int(task_key))
    return owned


def set_task_owner(runtime_state: dict, task_id: int, session_id: str, started_at: str) -> tuple[bool, str | None]:
    owners = runtime_state.setdefault("task_sessions", {})
    owned = session_owned_task_ids(runtime_state, session_id)
    if owned and owned != [task_id]:
        return False, f"session {session_id} 已持有 Task#{owned[0]}"
    owners[str(task_id)] = {
        "session_id": session_id,
        "started_at": started_at,
    }
    return True, None


def clear_task_owner(runtime_state: dict, task_id: int) -> bool:
    owners = runtime_state.setdefault("task_sessions", {})
    return owners.pop(str(task_id), None) is not None


def loop_state(runtime_state: dict) -> dict | None:
    dloop = runtime_state.get("dloop")
    return dloop if isinstance(dloop, dict) else None


def set_loop_state(runtime_state: dict, dloop_state: dict | None) -> None:
    runtime_state["dloop"] = dloop_state


def clear_loop_state(runtime_state: dict) -> bool:
    if runtime_state.get("dloop") is None:
        return False
    runtime_state["dloop"] = None
    return True


def is_cron_mode(loop_state: dict | None) -> bool:
    """Return True when dloop is in cron mode."""
    if not isinstance(loop_state, dict):
        return False
    return loop_state.get("mode") == "cron"


def resolve_session_inprogress_task(
    tasks: list[dict],
    runtime_state: dict,
    session_id: str,
) -> SessionTaskResolution:
    inprogress = [task for task in tasks if task.get("status") in ACTIVE_TASK_STATUSES]
    if not inprogress:
        return SessionTaskResolution("none")

    matching: list[dict] = []
    missing_owner: list[dict] = []
    foreign_owner: list[tuple[dict, str]] = []

    for task in inprogress:
        task_id = _normalize_task_id(task.get("id"))
        if task_id is None:
            continue
        owner = get_task_owner(runtime_state, task_id)
        if owner is None:
            missing_owner.append(task)
            continue
        owner_session_id = owner.get("session_id", "")
        if session_id and owner_session_id == session_id:
            matching.append(task)
        else:
            foreign_owner.append((task, owner_session_id))

    if len(matching) > 1:
        return SessionTaskResolution(
            "invalid_runtime_state",
            reason=f"session {session_id} 同时命中多个 InProgress 任务",
        )
    if matching:
        return SessionTaskResolution("match", task=matching[0])

    if missing_owner:
        task = missing_owner[0]
        return SessionTaskResolution(
            "missing_owner",
            task=task,
            reason=f"Task#{task.get('id')} 为 InProgress，但 dtask-state.json 中缺少 owner 记录",
        )

    if not session_id:
        return SessionTaskResolution(
            "invalid_runtime_state",
            reason="当前存在 InProgress 任务，但事件缺少 session_id/sessionId，无法判定 owner",
        )

    if foreign_owner:
        task, owner_session_id = foreign_owner[0]
        return SessionTaskResolution(
            "owner_mismatch",
            task=task,
            owner_session_id=owner_session_id,
            reason=(
                f"Task#{task.get('id')} 当前 owner 为 session {owner_session_id}，"
                f"当前 session {session_id} 需先显式 adopt"
            ),
        )

    return SessionTaskResolution("none")


def set_pending_recording(runtime_state: dict, task_id: int, target_status: str,
                          released_at: str, session_id: str) -> None:
    runtime_state["pending_recording"] = {
        "task_id": task_id,
        "target_status": target_status,
        "released_at": released_at,
        "session_id": session_id,
    }


def clear_pending_recording(runtime_state: dict) -> bool:
    if runtime_state.get("pending_recording") is None:
        return False
    runtime_state["pending_recording"] = None
    return True
