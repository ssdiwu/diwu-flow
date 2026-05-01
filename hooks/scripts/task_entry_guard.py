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


def _should_block_dloop(state_path, session_id=""):
    """Return True when dloop is active AND the caller is NOT the loop's owner session.

    Active loop + matching session_id → loop's own task execution, allow.
    Active loop + mismatched/missing session_id → external write, block.
    """
    if not os.path.exists(state_path):
        return False
    try:
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
        dloop = state.get("dloop")
        if not isinstance(dloop, dict) or dloop.get("active") is not True:
            return False
        # Loop is active — allow only if this IS the loop's own session
        loop_sid = dloop.get("session_id", "")
        if session_id and loop_sid and session_id == loop_sid:
            return False  # Loop owner: allow normal task execution
        return True  # Non-owner or unknown: block
    except (json.JSONDecodeError, OSError):
        return False


def _has_unlanded_plan(cwd):
    """Return (True, line_count) when ~/.claude/plans/ has plan file above threshold
    but dtask.json has no active tasks — meaning plan was never /dtask'd.

    This is the hard block condition: >=3 step plan exists but nothing landed.
    """
    marker_path = os.path.join(cwd, _PLAN_GUARD_MARKER)
    if not os.path.exists(marker_path):
        return False, 0

    # 读取 marker 中记录的 plan 路径
    recorded_plan = None
    try:
        with open(marker_path, "r") as f:
            recorded_plan = f.read().strip()
    except OSError:
        return False, 0

    if not recorded_plan or not os.path.isfile(recorded_plan):
        # marker 过期或无效 -> 清理并跳过
        try:
            os.remove(marker_path)
        except OSError:
            pass
        return False, 0

    # 只检查 marker 记录的 plan 文件是否满足阈值
    if not os.path.isfile(recorded_plan):
        # marker 记录的 plan 不存在 -> 过期
        try:
            os.remove(marker_path)
        except OSError:
            pass
        return False, 0

    try:
        with open(recorded_plan, encoding="utf-8") as f:
            plan_lines = sum(1 for _ in f)
    except (OSError, UnicodeDecodeError):
        try:
            os.remove(marker_path)
        except OSError:
            pass
        return False, 0

    if plan_lines < _PLAN_LINE_THRESHOLD:
        return False, 0

    task_json_path = os.path.join(cwd, WORKFLOW_DTASK)
    if _has_active_task(task_json_path):
        return False, 0  # Active tasks exist -> plan considered landed

    return True, plan_lines


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

    # === Fail-fast: block non-owner writes when dloop is still active ===
    # Must check BEFORE _has_active_task — real dloop always has active tasks,
    # so _has_active_task would exit(0) early and skip this guard.
    event_session_id = event.get("session_id") or event.get("sessionId", "")
    if _should_block_dloop(os.path.join(cwd, WORKFLOW_DTASK_STATE), session_id=event_session_id):
        print(
            "[diwu-dloop-guard] 🛑 BLOCK：检测到活跃的 dloop 运行时（dtask-state.json.dloop.active=true）。\n\n"
            "当前 session 非 dloop owner，Edit/Write 可能污染运行态快照。\n"
            "请先执行 /dend 取消循环，或使用 dloop owner session 继续执行。",
            file=sys.stderr,
        )
        sys.exit(1)  # Hard block: prevent non-owner write during active loop

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
