#!/usr/bin/env python3
"""PreToolUse(Edit|Write): guard business-file writes until executable dtask exists."""

import json
import os
import sys


ACTIVE_STATUSES = {"InSpec", "InProgress", "InReview"}
WORKFLOW_DECISIONS = ".diwu/decisions.md"
WORKFLOW_DTASK = ".diwu/dtask.json"
WORKFLOW_RECORDING = ".diwu/recording"
BLOCK_MESSAGE = (
    "[diwu-task-guard] ⛔ 检测到文件写入操作，但未发现可执行的 dtask 任务。\n"
    "请先运行 /dtask 将计划派生为任务条目（含 GWT acceptance），或确认 .diwu/dtask.json "
    "中存在 InSpec/InProgress/InReview 状态的任务。"
)


def _load_event():
    """Read hook event JSON from stdin safely."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}


def _norm(path):
    return os.path.normcase(os.path.abspath(path))


def _workflow_targets(cwd):
    base = _norm(cwd)
    return {
        "dtask": _norm(os.path.join(base, WORKFLOW_DTASK)),
        "decisions": _norm(os.path.join(base, WORKFLOW_DECISIONS)),
        "recording": _norm(os.path.join(base, WORKFLOW_RECORDING)),
    }


def _is_workflow_file(target_path, cwd):
    """Allow writes to workflow files that bootstrap or record task state."""
    if not target_path:
        return False
    target = _norm(target_path)
    paths = _workflow_targets(cwd)
    if target in {paths["dtask"], paths["decisions"]}:
        return True
    recording_prefix = paths["recording"] + os.sep
    return target.startswith(recording_prefix)


def _has_active_task(task_json_path):
    """Return True when task.json exists and contains executable tasks."""
    if not os.path.exists(task_json_path):
        return False
    try:
        with open(task_json_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False

    for task in data.get("tasks", []):
        if task.get("status") in ACTIVE_STATUSES:
            return True
    return False


def main():
    event = _load_event()
    tool_name = event.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    cwd = event.get("cwd") or os.getcwd()
    tool_input = event.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")
    task_json_path = os.path.join(cwd, WORKFLOW_DTASK)

    if _is_workflow_file(file_path, cwd):
        sys.exit(0)

    if _has_active_task(task_json_path):
        sys.exit(0)

    print(BLOCK_MESSAGE, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
