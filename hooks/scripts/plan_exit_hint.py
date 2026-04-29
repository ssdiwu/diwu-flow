#!/usr/bin/env python3
"""PreToolUse(ExitPlanMode): inject Plan->Dtask reminder without changing approval semantics."""

import json
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
    sys.exit(0)


if __name__ == "__main__":
    main()
