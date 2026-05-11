"""Context monitor hook — tracks tool usage context and reminds /drec.

Monitors write-tool call density per session. When count exceeds
critical threshold, outputs additionalContext prompting /drec.
"""
import glob as _glob
import json
import os
import sys
import tempfile
import time
import tomllib

from _shared import setup_sys_path, load_stdin_event  # noqa: E402

setup_sys_path()


# Configuration paths (relative to project root)
SETTINGS = ".diwu/dsettings.toml"

# Cross-platform cache dir: tempdir + session ID namespace
_CACHE_PREFIX = os.path.join(tempfile.gettempdir(), "diwu_ctxmon_")

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


def _settings_path(cwd="."):
    return os.path.join(cwd, SETTINGS)


def _cfg(cwd="."):
    """Load context monitor settings from dsettings.toml with defaults."""
    defaults = DEFAULTS.copy()
    settings_path = _settings_path(cwd)
    if not os.path.exists(settings_path):
        return defaults
    try:
        with open(settings_path, "rb") as f:
            data = tomllib.load(f)
        return {
            "warning": data.get(_TOML_KEYS["warning"], defaults["warning"]),
            "critical": data.get(_TOML_KEYS["critical"], defaults["critical"]),
            "delay": data.get(_TOML_KEYS["delay"], defaults["delay"]),
        }
    except (tomllib.TOMLDecodeError, OSError):
        return defaults


def _cleanup_stale_cache():
    """Remove expired temp cache files on startup."""
    try:
        for fp in _glob.glob(_CACHE_PREFIX + "*"):
            try:
                age = time.time() - os.path.getmtime(fp)
                if age > 3600:
                    os.unlink(fp)
            except OSError:
                pass
    except OSError:
        pass


_cleanup_stale_cache()


def _cache_path(session_id="", cwd="."):
    """Return session-scoped cache path in tempdir (cross-platform, zero git pollution)."""
    sid = session_id or "unknown"
    return _CACHE_PREFIX + sid + ".json"


def _load_cache(session_id="", cwd="."):
    """Load or initialize the session-scoped usage cache."""
    cp = _cache_path(session_id, cwd)
    if os.path.exists(cp):
        try:
            with open(cp, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"rd_count": 0, "wr_count": 0}


def _save_cache(cache, session_id="", cwd="."):
    """Persist session-scoped usage cache to tempdir."""
    cp = _cache_path(session_id, cwd)
    try:
        with open(cp, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except OSError:
        pass


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


def main():
    """Main entry point — called by PreToolUse hook on every Bash tool use."""
    event = _load_event()
    cwd = event.get("cwd") or os.getcwd()
    cfg = _cfg(cwd)
    session_id = event.get("session_id") or event.get("sessionId") or ""

    cache = _load_cache(session_id, cwd)

    tool_type = _classify_tool(event)
    if tool_type is None:
        sys.exit(0)

    cache[f"{tool_type}_count"] = cache.get(f"{tool_type}_count", 0) + 1
    wr_count = cache.get("wr_count", 0)
    critical = cfg["critical"]

    prompts = []

    if wr_count >= critical and not cache.get("critical_emitted"):
        cache["critical_emitted"] = True
        prompts.append(
            f"上下文监控：写工具调用 ({wr_count}) 已达到阈值 ({critical})，"
            f"建议立即执行 /drec 记录本轮 session 进度"
        )

    elif wr_count >= cfg["warning"] and not cache.get("warning_emitted"):
        cache["warning_emitted"] = True
        prompts.append(
            f"上下文监控：写工具调用 ({wr_count}) 接近警告阈值 ({cfg['warning']})，"
            f"建议准备执行 /drec"
        )

    _save_cache(cache, session_id, cwd)

    if prompts:
        print(json.dumps({
            "additionalContext": "\n".join(prompts),
        }, ensure_ascii=False))

    sys.exit(0)


if __name__ == "__main__":
    main()
