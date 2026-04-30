#!/usr/bin/env python3
"""PreToolUse(Edit|Write): guard business-file writes until executable dtask exists.

v2: Upgrade to hard block when unlanded >=3-step plan detected.
Soft warning (exit 0) → hard block (exit 1) for plan-without-dtask scenario.
"""

import json
import os
import sys


ACTIVE_STATUSES = {"InSpec", "InProgress", "InReview"}
WORKFLOW_DECISIONS = ".diwu/decisions.md"
WORKFLOW_DTASK = ".diwu/dtask.json"
WORKFLOW_DTASK_STATE = ".diwu/dtask-state.json"
WORKFLOW_RECORDING = ".diwu/recording"
WORKFLOW_DLOOP_STATE = ".diwu/dloop-state.json"
# Plan mode writes plan files to ~/.claude/plans/ — always allow
_PLAN_DIR = os.path.normpath(os.path.expanduser("~/.claude/plans"))
_PLAN_LINE_THRESHOLD = 20  # 行数超过此阈值视为“>=3 步方案”
_PLAN_GUARD_MARKER = os.path.join(".claude", ".plan-active")
_BLOCK_HARD_MESSAGE = (
    "[diwu-plan-guard] 🛑 HARD BLOCK：检测到未落地的 >=3 步实施方案。\n\n"
    "存在 ~/.claude/plans/ 下的 plan 文件（行数 >= {threshold}），但 .diwu/dtask.json \n"
    "中无对应的落地任务（无 InSpec/InProgress/InReview 状态任务）。\n\n"
    "请先执行 /dtask 将方案派生为任务条目（含 GWT acceptance），再进行代码实施。\n"
    "完整规则见 rules/mindset.md §Plan→Dtask 门控\n"
)
BLOCK_SOFT_MESSAGE = (
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
        "dtask_state": _norm(os.path.join(base, WORKFLOW_DTASK_STATE)),
        "decisions": _norm(os.path.join(base, WORKFLOW_DECISIONS)),
        "recording": _norm(os.path.join(base, WORKFLOW_RECORDING)),
        "dloop_state": _norm(os.path.join(base, WORKFLOW_DLOOP_STATE)),
    }


def _is_workflow_file(target_path, cwd):
    """Allow writes to workflow files that bootstrap or record task state."""
    if not target_path:
        return False
    target = _norm(target_path)
    paths = _workflow_targets(cwd)
    if target in {paths["dtask"], paths["dtask_state"], paths["decisions"], paths["dloop_state"]}:
        return True
    recording_prefix = paths["recording"] + os.sep
    return target.startswith(recording_prefix)


def _is_plan_file(target_path):
    """Allow Plan mode plan files regardless of dtask state."""
    if not target_path:
        return False
    target = _norm(target_path)
    return target.startswith(_PLAN_DIR + os.sep)


def _is_doc_file(target_path):
    """Allow .md documentation files regardless of dtask state."""
    if not target_path:
        return False
    return target_path.endswith('.md')


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


def _has_unlanded_plan(cwd):
    """Return (True, line_count) when ~/.claude/plans/ has plan file above threshold
    but dtask.json has no active tasks — meaning plan was never /dtask'd.

    This is the hard block condition: >=3 step plan exists but nothing landed.
    """
    marker_path = os.path.join(cwd, _PLAN_GUARD_MARKER)
    if not os.path.exists(marker_path):
        return False, 0

    if not os.path.isdir(_PLAN_DIR):
        return False, 0

    max_lines = 0
    for fname in os.listdir(_PLAN_DIR):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(_PLAN_DIR, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                lines = sum(1 for _ in f)  # non-empty lines
            if lines > max_lines:
                max_lines = lines
        except (OSError, UnicodeDecodeError):
            continue

    if max_lines < _PLAN_LINE_THRESHOLD:
        return False, 0

    # Plan file is substantial — check if dtask has active tasks to allow it
    task_json_path = os.path.join(cwd, WORKFLOW_DTASK)
    if _has_active_task(task_json_path):
        return False, 0  # Active tasks exist → plan considered landed

    return True, max_lines


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

    if _is_plan_file(file_path):
        sys.exit(0)

    if _is_doc_file(file_path):
        sys.exit(0)

    if _has_active_task(task_json_path):
        sys.exit(0)

    # === Hard block: unlanded >=3-step plan exists ===
    unlanded, plan_lines = _has_unlanded_plan(cwd)
    if unlanded:
        print(_BLOCK_HARD_MESSAGE.format(threshold=_PLAN_LINE_THRESHOLD), file=sys.stderr)
        sys.exit(1)  # Hard block: prevent write

    print(BLOCK_SOFT_MESSAGE, file=sys.stderr)
    sys.exit(0)  # Soft warning: advise but don't block


if __name__ == "__main__":
    main()
