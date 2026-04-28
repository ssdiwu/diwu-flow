"""Context monitor hook — tracks tool usage context for drift detection and auto-checkpoint.

Monitors tool call density per session. When write-tool count exceeds
critical+delay threshold, writes an auto-checkpoint to recording/.
"""
import json
import os
import sys
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


def _load_cache():
    """Load or initialize the usage cache."""
    if os.path.exists(CACHE):
        try:
            with open(CACHE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"rd_count": 0, "wr_count": 0, "checkpoint_written": False}


def _save_cache(cache):
    """Persist usage cache."""
    os.makedirs(os.path.dirname(CACHE) or ".", exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def _classify_tool():
    """Classify the current tool from CLAUDE_HOOK_TOOL_NAME env var."""
    tool_name = os.environ.get("CLAUDE_HOOK_TOOL_NAME", "")
    if tool_name in RD_TOOLS:
        return "rd"
    if tool_name in WR_TOOLS:
        return "wr"
    return None


def checkpoint(task_info=None):
    """Write an auto-checkpoint session file for the current InProgress task.

    If task_info is not provided, reads .diwu/dtask.json to find
    the current InProgress task (backward compatible with L2 tests).
    """
    rec_dir = ".diwu/recording"
    os.makedirs(rec_dir, exist_ok=True)

    # Auto-read task if not provided
    if task_info is None:
        task_path = ".diwu/dtask.json"
        if os.path.exists(task_path):
            try:
                with open(task_path, encoding="utf-8") as f:
                    data = json.load(f)
                tasks = [t for t in data.get("tasks", []) if t.get("status") == "InProgress"]
                if tasks:
                    task_info = tasks[0]
            except (json.JSONDecodeError, OSError):
                pass

    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    filename = f"session-{ts}.md"
    filepath = os.path.join(rec_dir, filename)

    task_line = ""
    if task_info:
        task_line = f"**Task#{task_info['id']}: {task_info.get('title', '')} → {task_info.get('status', '')}**\n"

    content = (
        f"## Session {ts}\n"
        f"### [Auto Checkpoint]\n"
        f"{task_line}"
        f"自动检查点：上下文监控触发（写工具调用达 CRITICAL+DELAY 阈值）\n"
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def main():
    """Main entry point — called by PreToolUse hook on every Bash tool use."""
    cfg = _cfg()
    cache = _load_cache()

    tool_type = _classify_tool()
    if tool_type is None:
        # Non-tracked tool, no-op but still exit clean
        sys.exit(0)

    cache[f"{tool_type}_count"] = cache.get(f"{tool_type}_count", 0) + 1
    wr_count = cache.get("wr_count", 0)
    critical = cfg["critical"]
    delay = cfg["delay"]

    # Check if we've crossed critical + delay threshold
    if wr_count >= critical + delay and not cache.get("checkpoint_written"):
        cp_path = checkpoint()  # auto-reads InProgress task from dtask.json
        cache["checkpoint_written"] = True

        # Output structured info for Claude to pick up
        result = {
            "level": "checkpoint",
            "message": f"上下文监控：写工具调用 ({wr_count}) 达到阈值 ({critical}+{delay})，已写入自动检查点 {cp_path}",
            "wr_count": wr_count,
            "threshold": critical + delay,
        }
        print(json.dumps(result, ensure_ascii=False))

    elif wr_count >= cfg["warning"] and not cache.get("warning_emitted"):
        cache["warning_emitted"] = True
        result = {
            "level": "warning",
            "message": f"上下文监控：写工具调用 ({wr_count}) 接近警告阈值 ({cfg['warning']})",
            "wr_count": wr_count,
            "threshold": cfg["warning"],
        }
        print(json.dumps(result, ensure_ascii=False))

    _save_cache(cache)
    sys.exit(0)


if __name__ == "__main__":
    main()
