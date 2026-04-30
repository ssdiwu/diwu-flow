#!/usr/bin/env python3
"""PreToolUse(ExitPlanMode): inject Plan->Dtask reminder without changing approval semantics."""

import json
import os
import sys


MESSAGE = (
    "[diwu-plan-guard] Plan→Dtask 门控提醒：\n\n"
    "⚠️ 如果本次 plan 包含 >=3 步实施工作，必须先用 /dtask 将步骤派生为 .diwu/dtask.json "
    "条目（每条含 GWT acceptance），再进入 /drun 或代码实施。\n"
    "<3 步且结果可预期的小改动可直接执行。\n\n"
    "完整规则见 rules/mindset.md §Plan→Dtask 门控"
)


def _load_event():
    """Parse stdin JSON safely. Missing or invalid input degrades to empty dict."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}


def main():
    event = _load_event()
    if event.get("tool_name") not in ("", "ExitPlanMode"):
        sys.exit(0)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": MESSAGE,
        }
    }
    print(json.dumps(output, ensure_ascii=False))

    # 仅当本次 plan >=20 行时才创建 marker
    _PLAN_LINE_THRESHOLD = 20
    _PLAN_DIR = os.path.normpath(os.path.expanduser("~/.claude/plans"))

    plan_path = None
    tool_input = event.get("tool_input") or {}
    candidate = tool_input.get("file_path", "")
    if candidate and candidate.endswith(".md") and _PLAN_DIR in os.path.normpath(os.path.abspath(candidate)):
        plan_path = candidate

    # 无 plan_path 信息 → 安全侧，不创建 marker（避免误用 stale plan）
    should_create_marker = False
    if plan_path:
        try:
            with open(plan_path, encoding="utf-8") as f:
                line_count = sum(1 for _ in f)
            if line_count >= _PLAN_LINE_THRESHOLD:
                should_create_marker = True
        except (OSError, UnicodeDecodeError):
            pass

    if should_create_marker:
        cwd = event.get("cwd") or os.getcwd()
        marker_path = os.path.join(cwd, ".claude", ".plan-active")
        try:
            os.makedirs(os.path.dirname(marker_path), exist_ok=True)
            # 写入 plan 文件绝对路径（非空文件）
            with open(marker_path, "w") as mf:
                mf.write(plan_path + "\n")
        except OSError:
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
