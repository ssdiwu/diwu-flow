#!/usr/bin/env python3
"""PreToolUse(ExitPlanMode): inject Plan->Dtask reminder without changing approval semantics."""

import io
import json
import os
import sys

try:
    from _shared import load_stdin_event  # noqa: E402
except (ImportError, ModuleNotFoundError):
    import threading

    def _read_stdin_with_timeout(timeout_sec=3.0):
        result = [""]
        def _reader():
            try:
                result[0] = sys.stdin.read()
            except (OSError, ValueError):
                pass
        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        t.join(timeout=timeout_sec)
        return "" if t.is_alive() else result[0]

    def load_stdin_event(*, check_tty=False):
        try:
            if check_tty and sys.stdin.isatty():
                return {}
            raw = _read_stdin_with_timeout()
            if not raw.strip():
                return {}
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {}


MESSAGE = (
    "[diwu-plan-guard] Plan→Dtask 门控提醒：\n\n"
    "⚠️ 如果本次 plan 包含 >=3 步实施工作，必须先用 /dtask 将步骤派生为 .diwu/dtask.toml "
    "条目（每条含 GWT acceptance），再进入 /drun 或代码实施。\n"
    "<3 步且结果可预期的小改动可直接执行。\n\n"
    "完整规则见 rules/mindset.md §Plan→Dtask 门控"
)

_PLAN_LINE_THRESHOLD = 20
_MARKER_PATH = os.path.join(".claude", ".plan-active")


def _load_event():
    """Parse stdin JSON safely. Missing or invalid input degrades to empty dict."""
    return load_stdin_event()


def _count_lines(text):
    if not isinstance(text, str) or not text:
        return 0
    return sum(1 for _ in io.StringIO(text))


def _build_marker_payload(event):
    tool_input = event.get("tool_input") or {}
    plan_text = tool_input.get("plan")
    if not isinstance(plan_text, str) or not plan_text.strip():
        return None

    line_count = _count_lines(plan_text)
    if line_count < _PLAN_LINE_THRESHOLD:
        return None

    return {
        "version": 2,
        "source": "tool_input.plan",
        "session_id": event.get("session_id", ""),
        "line_count": line_count,
    }


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

    marker_payload = _build_marker_payload(event)
    if marker_payload:
        cwd = event.get("cwd") or os.getcwd()
        marker_path = os.path.join(cwd, _MARKER_PATH)
        try:
            os.makedirs(os.path.dirname(marker_path), exist_ok=True)
            with open(marker_path, "w", encoding="utf-8") as mf:
                json.dump(marker_payload, mf, ensure_ascii=False, indent=2)
                mf.write("\n")
        except OSError:
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
