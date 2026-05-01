#!/usr/bin/env python3
"""TaskCompleted: lightweight reminder after a task is marked Done.

Fires when task.json transitions to Done.
Checks recording_reminder.enabled (default true) in dsettings.json.
Non-blocking: always exit(0), outputs reminder via additionalSystemPrompt.

Does NOT write files — recording is handled by Stop hook.

Loop tracking: maintains completed_task_ids in dtask-state.json.dloop
when an active dloop session matches the current event session_id.
Execution order: clear_task_owner (raw load, pre-sync) -> loop track -> reminder gating.

Key design: clear_task_owner MUST run before sync_runtime_state because
sync's cleanup logic removes non-InProgress entries from task_sessions,
which would swallow the Done task's owner before we can clear it.
Loop tracking only fires after successful owner clearance to avoid counting
unconfirmed completions. Reminder sys.exit(0) comes after all bookkeeping.
"""

import json, os, sys

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HOOKS_DIR))
SHARED_SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SHARED_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SHARED_SCRIPTS_DIR)

from dtask_state import (  # noqa: E402
    clear_task_owner,
    save_runtime_state,
    sync_runtime_state,
    load_runtime_state,
)

SETTINGS_FILE = '.diwu/dsettings.json'
TASK_JSON_PATH = '.diwu/dtask.json'
RUNTIME_STATE_PATH = '.diwu/dtask-state.json'

_CWD: str = "."


def _load(p):
    """Load JSON file, return {} on error."""
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _get_event_data():
    """Parse stdin JSON for TaskCompleted event."""
    try:
        raw = sys.stdin.read()
        if not raw:
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}


def _task_summary(task):
    """Build brief task summary string from task dict."""
    tid = task.get('id', '?')
    title = task.get('title', '未知任务')
    return f"Task#{tid}: {title}"


def _track_loop_completion(task_id: int, session_id: str):
    """Loop 追踪：仅在精确条件满足时追加 completed_task_ids。

    必须在 clear_task_owner 成功后的路径中调用（由 main() 调用时机保证）。
    即使 recording_reminder 关闭，loop 计数仍需维护（reminder 门控在追踪之后）。
    只认 event.task 原始精确信号，不使用 fallback heuristic 结果。

    此函数内部使用 sync_runtime_state（含 cleanup），此时 owner 已被清除，
    cleanup 不再影响当前 task 的 loop 计数逻辑。
    """
    task_data = _load(TASK_JSON_PATH)
    sync_result = sync_runtime_state(_CWD, task_data, persist=True, ensure_exists=True)
    if not sync_result.ok:
        return
    runtime_loop = sync_result.state.get("dloop") if sync_result.state else None
    if (not runtime_loop or not runtime_loop.get("active")
            or runtime_loop.get("session_id") != session_id):
        return
    current_completed = runtime_loop.get("completed_task_ids", [])
    if task_id in current_completed:
        return  # 防重复：同一 task_id 再次 Done 不追加
    runtime_loop["completed_task_ids"] = current_completed + [task_id]
    save_runtime_state(_CWD, sync_result.state, remove_legacy=True)


def main():
    global _CWD
    event = _get_event_data()
    _CWD = event.get("cwd", ".")
    session_id = event.get("sessionId", event.get("session_id", ""))

    # === 阶段 1: Fallback heuristic + clear_task_owner + loop 追踪（必须在 reminder 之前完成）===
    settings = _load(SETTINGS_FILE)  # 提前加载，后面还要用

    task_info = ''
    completed_task = event.get("task")

    if not completed_task:
        # Fallback: scan task.json for Done tasks (heuristic)
        task_data = _load(TASK_JSON_PATH)
        tasks = task_data.get("tasks", [])
        # Last Done task found (most recent completion)
        for t in reversed(tasks):
            if t.get("status") == "Done":
                completed_task = t
                break

    if completed_task:
        task_info = _task_summary(completed_task)
        task_id = completed_task.get("id")

        if isinstance(task_id, int) and not isinstance(task_id, bool):
            # 关键：先用 raw load 做 clear_task_owner，
            # 不能用 sync_runtime_state（它的 cleanup 会删除 Done 任务的 owner 条目）
            load_result = load_runtime_state(_CWD)
            if load_result.ok and load_result.state is not None:
                if clear_task_owner(load_result.state, task_id):
                    save_runtime_state(_CWD, load_result.state, remove_legacy=True)

                    # === Loop 追踪（仅在 owner 清理成功后）===
                    _event_task = event.get("task")
                    if (_event_task
                            and isinstance(_event_task.get("id"), int)
                            and not isinstance(_event_task["id"], bool)
                            and _event_task.get("status") == "Done"
                            and _event_task.get("id") == task_id):
                        _track_loop_completion(task_id, session_id)

    # === 阶段 2: Reminder 门控（安全地在 loop 追踪和 owner 清理之后）===
    if settings.get("recording_reminder", {}).get("enabled") == False:
        sys.exit(0)

    # === 阶段 3: Reminder 输出 ===
    reminder_parts = []
    if task_info:
        reminder_parts.append(f"[TASK-DONE] {task_info} 已完成。")
    else:
        reminder_parts.append("[TASK-DONE] 任务已完成。")

    reminder_parts.append(
        "请确认：1) 本次 session 记录已写入 .diwu/recording/（→ drec skill）  "
        "2) 如有设计决策已追加到 .diwu/decisions.md  "
        "3) 验收证据等级是否达标（→ dvfy 验证体系）"
    )

    message = " ".join(reminder_parts)

    print(json.dumps({
        'continue': True,
        'additionalSystemPrompt': message
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
