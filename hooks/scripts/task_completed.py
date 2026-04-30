#!/usr/bin/env python3
"""TaskCompleted: lightweight reminder after a task is marked Done.

Fires when task.json transitions to Done.
Checks recording_reminder.enabled (default true) in dsettings.json.
Non-blocking: always exit(0), outputs reminder via additionalSystemPrompt.

Does NOT write files — recording is handled by Stop hook.

Loop tracking: independently maintains completed_task_ids in dtask-state.json.dloop
when an active dloop session matches the current event session_id.
This runs BEFORE the recording_reminder gating so loop bookkeeping
is never disabled by reminder settings.
"""

import json, os, sys

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HOOKS_DIR))
SHARED_SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SHARED_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SHARED_SCRIPTS_DIR)

from dtask_state import clear_task_owner, save_runtime_state, sync_runtime_state  # noqa: E402

SETTINGS_FILE = '.diwu/dsettings.json'
TASK_JSON_PATH = '.diwu/dtask.json'


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

    独立于 reminder gating —— 即使 recording_reminder 关闭，loop 计数仍需维护。
    只认 event.task 原始精确信号（event_task），不使用 fallback heuristic 结果。
    必须在 clear_task_owner 成功后的路径中调用（通过 main() 调用时机保证）。
    """
    task_data = _load(TASK_JSON_PATH)
    sync_result = sync_runtime_state(".", task_data, persist=True, ensure_exists=True)
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
    save_runtime_state(".", sync_result.state, remove_legacy=True)


def main():
    event = _get_event_data()
    session_id = event.get("sessionId", event.get("session_id", ""))

    # === Loop 追踪（独立于 reminder gating，必须在 reminder 早退之前）===
    # 只认 event.task 原始精确信号，不使用 fallback heuristic 的结果
    _event_task = event.get("task")
    if (_event_task and isinstance(_event_task.get("id"), int)
            and not isinstance(_event_task["id"], bool)):
        _track_loop_completion(_event_task["id"], session_id)

    # === Reminder 提醒（原有逻辑）===
    settings = _load(SETTINGS_FILE)
    if settings.get("recording_reminder", {}).get("enabled") == False:
        sys.exit(0)

    # Try to identify the completed task from event or task.json
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

        task_data = _load(TASK_JSON_PATH)
        sync_result = sync_runtime_state(".", task_data, persist=True, ensure_exists=True)
        if sync_result.ok:
            task_id = completed_task.get("id")
            if isinstance(task_id, int) and not isinstance(task_id, bool):
                if clear_task_owner(sync_result.state, task_id):
                    save_runtime_state(".", sync_result.state, remove_legacy=True)

    # Compose reminder message
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
