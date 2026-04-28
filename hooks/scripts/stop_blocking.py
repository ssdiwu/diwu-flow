"""Stop hook dispatcher: delegates to sub-modules.

Minimal implementation that handles InProgress detection and
delegates to stop_decision for full decision logic.
"""
import json
import os
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

# Import sub-modules (may be stubs or full implementations)
try:
    import stop_snapshot
except ImportError:
    stop_snapshot = None  # type: ignore[assignment]

try:
    import stop_integrity
except ImportError:
    stop_integrity = None  # type: ignore[assignment]

try:
    import stop_archive_agg
except ImportError:
    stop_archive_agg = None  # type: ignore[assignment]

try:
    import stop_decision
except ImportError:
    stop_decision = None  # type: ignore[assignment]

TASK_JSON_PATH = ".diwu/dtask.json"
SETTINGS_PATH = ".diwu/dsettings.json"


def _load(path, default=None):
    """Load JSON file, returning default on missing/error."""
    full = os.path.join(os.getcwd(), path)
    if os.path.exists(full):
        try:
            with open(full, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return default if default is not None else {}


def main():
    data = _load(TASK_JSON_PATH, {"tasks": []})
    tasks = data.get("tasks", [])
    settings = _load(SETTINGS_PATH, {})

    ip = [t for t in tasks if t.get("status") == "InProgress"]

    if ip:
        t = ip[0]
        result = {
            "decision": "block",
            "reason": f"继续完成当前任务：Task#{t['id']}: {t.get('title', '')}",
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)

    # No InProgress task — use stop_decision if available
    if stop_decision is not None:
        should_continue, output = stop_decision.decide(
            tasks, settings, data,
            os.path.join(os.getcwd(), TASK_JSON_PATH),
            [],
        )
        if output:
            print(json.dumps(output, ensure_ascii=False))
        sys.exit(0 if should_continue else 1)

    # Fallback: no decision module available
    print(json.dumps({}, ensure_ascii=False))
    sys.exit(1)


if __name__ == "__main__":
    main()
