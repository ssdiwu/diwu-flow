#!/usr/bin/env python3
"""TaskCompleted: lightweight reminder after a task is marked Done.

Fires when task.json transitions to Done.
Checks recording_reminder.enabled (default true) in dsettings.json.
Non-blocking: always exit(0), outputs reminder via additionalSystemPrompt.

Does NOT write files — recording is handled by Stop hook.
"""

import json, os, sys

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


def main():
    settings = _load(SETTINGS_FILE)
    if settings.get('recording_reminder', {}).get('enabled') == False:
        sys.exit(0)

    event = _get_event_data()
    session_id = event.get('sessionId', event.get('session_id', ''))

    # Try to identify the completed task from event or task.json
    task_info = ''
    completed_task = event.get('task')

    if not completed_task:
        # Fallback: scan task.json for Done tasks (heuristic)
        task_data = _load(TASK_JSON_PATH)
        tasks = task_data.get('tasks', [])
        # Last Done task found (most recent completion)
        for t in reversed(tasks):
            if t.get('status') == 'Done':
                completed_task = t
                break

    if completed_task:
        task_info = _task_summary(completed_task)

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


if __name__ == '__main__':
    main()
