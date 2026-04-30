#!/usr/bin/env python3
"""diwu-flow dloop_state: 共享状态判定 helper。"""

import json
from enum import Enum
from pathlib import Path

DLOOP_STATE_PATH = ".diwu/dloop-state.json"
ACTIVE_STATUSES = ("InProgress", "InProcess")


class LoopStateClass(Enum):
    """dloop 状态分类。"""
    ACTIVE_OR_RECOVERABLE = "active_or_recoverable"
    TERMINAL_STALE = "terminal_stale"
    INVALID_STATE = "invalid_state"


class LoopStateResult:
    """判定结果。"""

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


def _is_non_negative_int(value) -> bool:
    """Return True only for real non-negative ints, excluding bool."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _task_list(data) -> list:
    """Extract task dicts from dtask-like payloads."""
    if not isinstance(data, dict):
        return []
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        return []
    return [t for t in tasks if isinstance(t, dict)]


def get_done_ids(tasks: list) -> set[int]:
    """Collect Done task ids from task list."""
    done = set()
    for task in tasks:
        task_id = task.get("id")
        if task.get("status") == "Done" and isinstance(task_id, int) and not isinstance(task_id, bool):
            done.add(task_id)
    return done


def is_unblocked(task: dict, tasks: list, done_ids: set[int] | None = None) -> bool:
    """Return whether an InSpec task is unblocked under current task statuses."""
    blocked_by = task.get("blocked_by", [])
    if blocked_by is None:
        blocked_by = []
    if not isinstance(blocked_by, list):
        return False
    if done_ids is None:
        done_ids = get_done_ids(tasks)
    return all(isinstance(blocker_id, int) and not isinstance(blocker_id, bool) and blocker_id in done_ids for blocker_id in blocked_by)


def get_executable_tasks(tasks: list) -> list:
    """Return tasks executable right now: InProgress + unblocked InSpec."""
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
    """Return all active tasks for automatic snapshot: InSpec + InProgress."""
    return [task for task in tasks if task.get("status") in ("InSpec", *ACTIVE_STATUSES)]


def get_terminal_stop_reason(
    tasks: list,
    settings: dict | None = None,
    data: dict | None = None,
    loop_state: dict | None = None,
    *,
    check_task_state: bool = True,
) -> str | None:
    """Mirror stop_decision loop stop semantics and return terminal reason if any."""
    settings = settings or {}
    data = data or {}
    loop_state = loop_state or {}

    ip = []
    rev = []
    nx = []
    if check_task_state:
        ip = [task for task in tasks if task.get("status") in ACTIVE_STATUSES]
        rev = [task for task in tasks if task.get("status") == "InReview"]
        nx = [task for task in tasks if task.get("status") == "InSpec" and is_unblocked(task, tasks)]

        if not nx and not ip:
            return "无可执行任务"

    completed_ids = loop_state.get("completed_task_ids", [])
    if not isinstance(completed_ids, list):
        completed_ids = []
    max_tasks = loop_state.get("max_tasks", 0)
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
    """对 dloop-state.json 做三分类判定。

    Args:
        cwd: 项目目录（用于定位 state 文件）
        dtask_data: dtask.json 内容（可选，用于检查可执行任务）
        settings: dsettings.json 内容（可选，用于 review limit）

    Returns:
        LoopStateResult 含 cls/reason/data
    """
    if cwd is None:
        cwd = Path(".")
    elif isinstance(cwd, str):
        cwd = Path(cwd)

    state_path = cwd / DLOOP_STATE_PATH

    # 文件不存在 → 无状态（不是 invalid，只是没有）
    if not state_path.exists():
        return LoopStateResult(LoopStateClass.ACTIVE_OR_RECOVERABLE, "no_state_file")

    # 尝试读取
    try:
        raw = state_path.read_text(encoding="utf-8")
        if not raw.strip():
            return LoopStateResult(LoopStateClass.INVALID_STATE, "空文件")
        state = json.loads(raw)
    except (json.JSONDecodeError, OSError) as e:
        return LoopStateResult(LoopStateClass.INVALID_STATE, f"JSON 损坏: {e}")

    if not isinstance(state, dict):
        return LoopStateResult(LoopStateClass.INVALID_STATE, "非 dict 结构")

    # 必须有 active 字段，且类型正确
    if "active" not in state:
        return LoopStateResult(LoopStateClass.INVALID_STATE, "缺少 active 字段")
    if not isinstance(state.get("active"), bool):
        return LoopStateResult(LoopStateClass.INVALID_STATE, "active 必须是 bool")

    # 非 active → 不是 stale（正常停止状态）
    if not state.get("active"):
        return LoopStateResult(LoopStateClass.ACTIVE_OR_RECOVERABLE, "inactive（非活跃）")

    # active=True → 基本字段必须完整且类型正确
    required_fields = ["session_id", "started_at"]
    for field in required_fields:
        if field not in state:
            return LoopStateResult(LoopStateClass.INVALID_STATE, f"缺少必需字段: {field}")
    if not isinstance(state.get("session_id"), str) or not state.get("session_id"):
        return LoopStateResult(LoopStateClass.INVALID_STATE, "session_id 必须是非空字符串")
    if not isinstance(state.get("started_at"), str) or not state.get("started_at"):
        return LoopStateResult(LoopStateClass.INVALID_STATE, "started_at 必须是非空字符串")

    completed = state.get("completed_task_ids", [])
    if not isinstance(completed, list) or not all(_is_non_negative_int(task_id) for task_id in completed):
        return LoopStateResult(LoopStateClass.INVALID_STATE, "completed_task_ids 必须是非负整数列表")
    max_tasks = state.get("max_tasks", 0)
    if not _is_non_negative_int(max_tasks):
        return LoopStateResult(LoopStateClass.INVALID_STATE, "max_tasks 必须是非负整数")
    iteration = state.get("current_iteration", 0)
    if not _is_non_negative_int(iteration):
        return LoopStateResult(LoopStateClass.INVALID_STATE, "current_iteration 必须是非负整数")

    tasks = _task_list(dtask_data or {})
    stop_reason = get_terminal_stop_reason(
        tasks,
        settings=settings,
        data=dtask_data or {},
        loop_state=state,
        check_task_state=dtask_data is not None,
    )
    if stop_reason:
        return LoopStateResult(LoopStateClass.TERMINAL_STALE, stop_reason, data=state)

    return LoopStateResult(
        LoopStateClass.ACTIVE_OR_RECOVERABLE,
        "循环活跃或可恢复",
        data=state,
    )


def cleanup_state(cwd: Path | str) -> bool:
    """删除 dloop-state.json。返回是否成功删除。"""
    path = (Path(cwd) if isinstance(cwd, str) else cwd) / DLOOP_STATE_PATH
    if path.exists():
        try:
            path.unlink()
            return True
        except OSError:
            return False
    return False
