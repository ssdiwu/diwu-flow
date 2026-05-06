#!/usr/bin/env python3
"""Shared dloop state classification helper."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from dtask_state import (
    clear_loop_state,
    loop_state,
    save_runtime_state,
    sync_runtime_state,
    _is_non_negative_int,
    _task_list,
)

ACTIVE_STATUSES = ("InProgress", "InProcess")


class LoopStateClass(Enum):
    ACTIVE_OR_RECOVERABLE = "active_or_recoverable"
    TERMINAL_STALE = "terminal_stale"
    INVALID_STATE = "invalid_state"


class LoopStateResult:
    def __init__(self, cls: LoopStateClass, reason: str = "", data: dict | None = None):
        self.cls = cls
        self.reason = reason
        self.data = data

    @property
    def is_active(self) -> bool:
        return self.cls == LoopStateClass.ACTIVE_OR_RECOVERABLE

    @property
    def is_stale(self) -> bool:
        return self.cls == LoopStateClass.TERMINAL_STALE

    @property
    def is_invalid(self) -> bool:
        return self.cls == LoopStateClass.INVALID_STATE


def get_done_ids(tasks: list) -> set[int]:
    done = set()
    for task in tasks:
        task_id = task.get("id")
        if task.get("status") == "Done" and isinstance(task_id, int) and not isinstance(task_id, bool):
            done.add(task_id)
    return done


def is_unblocked(task: dict, tasks: list, done_ids: set[int] | None = None) -> bool:
    blocked_by = task.get("blocked_by", [])
    if blocked_by is None:
        blocked_by = []
    if not isinstance(blocked_by, list):
        return False
    if done_ids is None:
        done_ids = get_done_ids(tasks)
    return all(isinstance(blocker_id, int) and not isinstance(blocker_id, bool) and blocker_id in done_ids for blocker_id in blocked_by)


def get_executable_tasks(tasks: list) -> list:
    done_ids = get_done_ids(tasks)
    executable = []
    for task in tasks:
        status = task.get("status", "")
        if status in ACTIVE_STATUSES:
            executable.append(task)
        elif status == "InSpec" and is_unblocked(task, tasks, done_ids):
            executable.append(task)
    return executable


def get_active_tasks(tasks: list) -> list:
    return [task for task in tasks if task.get("status") in ("InSpec", *ACTIVE_STATUSES)]


def get_terminal_stop_reason(
    tasks: list,
    settings: dict | None = None,
    data: dict | None = None,
    loop_state_data: dict | None = None,
    *,
    check_task_state: bool = True,
) -> str | None:
    settings = settings or {}
    data = data or {}
    loop_state_data = loop_state_data or {}

    ip = []
    rev = []
    nx = []
    if check_task_state:
        ip = [task for task in tasks if task.get("status") in ACTIVE_STATUSES]
        rev = [task for task in tasks if task.get("status") == "InReview"]
        nx = [task for task in tasks if task.get("status") == "InSpec" and is_unblocked(task, tasks)]
        if not nx and not ip:
            return "无可执行任务"

    completed_ids = loop_state_data.get("completed_task_ids", [])
    if not isinstance(completed_ids, list):
        completed_ids = []
    max_tasks = loop_state_data.get("max_tasks", 0)
    if not _is_non_negative_int(max_tasks):
        max_tasks = 0
    if max_tasks > 0 and len(completed_ids) >= max_tasks:
        return f"达到任务上限 (max_tasks={max_tasks})"

    if check_task_state:
        review_limit = settings.get("review_limit", 5)
        if not _is_non_negative_int(review_limit):
            review_limit = 5
        review_used = data.get("review_used", 0)
        if not _is_non_negative_int(review_used):
            review_used = 0
        if rev and review_used >= review_limit:
            return f"PENDING REVIEW ({len(rev)} 个 InReview ≥ review_limit={review_limit})"

    return None


def classify(cwd: Path | str | None = None, dtask_data: dict | None = None, settings: dict | None = None) -> LoopStateResult:
    base = Path(".") if cwd is None else Path(cwd)
    sync_result = sync_runtime_state(base, dtask_data, persist=True)
    if sync_result.is_invalid:
        return LoopStateResult(LoopStateClass.INVALID_STATE, sync_result.reason)

    loop = loop_state(sync_result.state)
    if loop is None:
        return LoopStateResult(LoopStateClass.ACTIVE_OR_RECOVERABLE, "no_state_file")
    if not loop.get("active"):
        return LoopStateResult(LoopStateClass.ACTIVE_OR_RECOVERABLE, "inactive（非活跃）", data=loop)

    tasks = _task_list(dtask_data or {})
    stop_reason = get_terminal_stop_reason(
        tasks,
        settings=settings,
        data=dtask_data or {},
        loop_state_data=loop,
        check_task_state=dtask_data is not None,
    )
    if stop_reason:
        return LoopStateResult(LoopStateClass.TERMINAL_STALE, stop_reason, data=loop)

    return LoopStateResult(LoopStateClass.ACTIVE_OR_RECOVERABLE, "循环活跃或可恢复", data=loop)


def cleanup_state(cwd: Path | str) -> bool:
    sync_result = sync_runtime_state(cwd, persist=True, ensure_exists=False)
    if sync_result.is_invalid:
        return False
    changed = clear_loop_state(sync_result.state)
    if changed:
        save_runtime_state(cwd, sync_result.state, remove_legacy=True)
        return True
    return False
