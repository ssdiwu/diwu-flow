"""Context monitor hook — tracks tool usage context for drift detection and auto-checkpoint.

Monitors tool call density per session. When write-tool count exceeds
critical+delay threshold, writes an auto-checkpoint to recording/.
"""
import json
import os
import sys
import tomllib
from datetime import datetime

from _shared import setup_sys_path, load_stdin_event  # noqa: E402

setup_sys_path()


# Configuration paths (relative to project root)
SETTINGS = ".diwu/dsettings.toml"
CACHE_TEMPLATE = ".diwu/.context_monitor_cache_{sid}.json"

# Default threshold values
DEFAULTS = {
    "warning": 30,
    "critical": 50,
    "delay": 10,
}

# TOML key mapping (Issue #31 alignment)
_TOML_KEYS = {
    "warning": "ctxmon_warn_at",
    "critical": "ctxmon_checkpoint_at",
    "delay": "ctxmon_checkpoint_delay",
}

# Tool classification sets
RD_TOOLS = {"Read", "Grep", "Glob", "LSP", "WebSearch", "WebFetch"}
WR_TOOLS = {"Edit", "Write", "Bash"}


def _cfg():
    """Load context monitor settings from dsettings.toml with defaults."""
    defaults = DEFAULTS.copy()
    if not os.path.exists(SETTINGS):
        return defaults
    try:
        with open(SETTINGS, "rb") as f:
            data = tomllib.load(f)
        return {
            "warning": data.get(_TOML_KEYS["warning"], defaults["warning"]),
            "critical": data.get(_TOML_KEYS["critical"], defaults["critical"]),
            "delay": data.get(_TOML_KEYS["delay"], defaults["delay"]),
        }
    except (tomllib.TOMLDecodeError, OSError):
        return defaults


def _cache_path(session_id=""):
    """Return session-scoped cache file path."""
    sid = session_id or "unknown"
    return CACHE_TEMPLATE.format(sid=sid)


def _load_cache(session_id=""):
    """Load or initialize the session-scoped usage cache."""
    cp = _cache_path(session_id)
    if os.path.exists(cp):
        try:
            with open(cp, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"rd_count": 0, "wr_count": 0, "checkpoint_written": False}


def _save_cache(cache, session_id=""):
    """Persist session-scoped usage cache."""
    cp = _cache_path(session_id)
    os.makedirs(os.path.dirname(cp) or ".", exist_ok=True)
    with open(cp, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def _load_event():
    """Read PreToolUse payload once; fall back to env-only testing."""
    return load_stdin_event(check_tty=True)


def _classify_tool(event):
    tool_name = event.get("tool_name") or os.environ.get("CLAUDE_HOOK_TOOL_NAME", "")
    if tool_name in RD_TOOLS:
        return "rd"
    if tool_name in WR_TOOLS:
        return "wr"
    return None


def checkpoint(cwd="."):
    """Write an auto-checkpoint session file (no task association)."""
    rec_dir = os.path.join(cwd, ".diwu", "recording")
    os.makedirs(rec_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    filename = f"checkpoint-{ts}.md"
    filepath = os.path.join(rec_dir, filename)

    content = (
        f"## Checkpoint {ts}\n"
        f"### [Auto Checkpoint]\n"
        f"自动检查点：上下文监控触发（写工具调用达 CRITICAL+DELAY 阈值）\n"
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def main():
    """Main entry point — called by PreToolUse hook on every Bash tool use."""
    cfg = _cfg()
    event = _load_event()
    session_id = event.get("session_id") or event.get("sessionId") or ""

    cache = _load_cache(session_id)

    tool_type = _classify_tool(event)
    if tool_type is None:
        sys.exit(0)

    cache[f"{tool_type}_count"] = cache.get(f"{tool_type}_count", 0) + 1
    wr_count = cache.get("wr_count", 0)
    critical = cfg["critical"]
    delay = cfg["delay"]

    if wr_count >= critical + delay and not cache.get("checkpoint_written"):
        cwd = event.get("cwd") or os.getcwd()
        cp_path = checkpoint(cwd=cwd)
        cache["checkpoint_written"] = True

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

    _save_cache(cache, session_id)
    sys.exit(0)


if __name__ == "__main__":
    main()
