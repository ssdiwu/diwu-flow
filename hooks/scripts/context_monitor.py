"""Context monitor hook — tracks tool usage context for drift detection.

This is a minimal implementation migrated to diwu-flow.
Original functionality was more extensive; this version covers the core
threshold-based monitoring with dict-mapped actions.
"""
import json
import os
from datetime import datetime

# Configuration paths (relative to project root)
SETTINGS = ".diwu/dsettings.json"
CACHE = ".diwu/.context_monitor_cache.json"

# Default threshold values
DEFAULTS = {
    "warning": 30,
    "critical": 50,
    "delay": 10,
}

# Tool classification sets
RD_TOOLS = {"Read", "Grep", "Glob", "LSP", "WebSearch", "WebFetch"}
WR_TOOLS = {"Edit", "Write", "Bash"}


def _cfg():
    """Load context monitor settings from dsettings.json with defaults."""
    defaults = DEFAULTS.copy()
    if not os.path.exists(SETTINGS):
        return defaults
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            data = json.load(f)
        return {
            "warning": data.get("context_monitor_warning", defaults["warning"]),
            "critical": data.get("context_monitor_critical", defaults["critical"]),
            "delay": data.get("context_monitor_delay", defaults["delay"]),
        }
    except (json.JSONDecodeError, OSError):
        return defaults


def checkpoint():
    """Write an auto-checkpoint session file for the current InProgress task."""
    rec_dir = ".diwu/recording"
    os.makedirs(rec_dir, exist_ok=True)

    # Read current InProgress task
    task_path = ".diwu/dtask.json"
    tasks = []
    if os.path.exists(task_path):
        with open(task_path, encoding="utf-8") as f:
            data = json.load(f)
        tasks = [t for t in data.get("tasks", []) if t.get("status") == "InProgress"]

    if not tasks:
        return

    t = tasks[0]
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    filename = f"session-{ts}.md"
    filepath = os.path.join(rec_dir, filename)

    content = (
        f"## Session {ts}\n"
        f"### [Auto Checkpoint]\n"
        f"**Task#{t['id']}: {t.get('title', '')} → {t.get('status')}\n"
        f"自动检查点：上下文监控触发\n"
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
