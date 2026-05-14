"""Shared utilities for diwu-flow hook scripts.

Provides:
  - ensure_shared_dir(): add this file's directory to sys.path (handles exec() context)
  - setup_sys_path(): inject scripts/ into sys.path for cross-module imports
  - load_json_fallback(path): load JSON file, return {} on any error
  - load_stdin_event(*, check_tty=False): read hook event from stdin
"""
import json
import os
import sys
import threading


def ensure_shared_dir():
    """Add this file's own directory to sys.path so sibling imports work."""
    shared_dir = os.path.dirname(os.path.abspath(__file__))
    if shared_dir not in sys.path:
        sys.path.insert(0, shared_dir)


def setup_sys_path():
    """Add project scripts/ to sys.path so hooks can import from dtask_state etc."""
    hooks_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(hooks_dir))
    shared = os.path.join(repo_root, "scripts")
    if shared not in sys.path:
        sys.path.insert(0, shared)


def load_json_fallback(path):
    """Load a JSON file; return {} if missing or corrupt."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _read_stdin_with_timeout(timeout_sec: float = 3.0) -> str:
    """Read stdin with timeout to avoid hanging on Windows where pipe EOF may never arrive."""
    result = [""]

    def _reader():
        try:
            result[0] = sys.stdin.read()
        except (OSError, ValueError):
            pass

    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    t.join(timeout=timeout_sec)

    if t.is_alive():
        return ""
    return result[0]


def load_stdin_event(*, check_tty=False):
    """Read hook event JSON from stdin. Returns {} on any error or empty input.

    Args:
        check_tty: If True, skip reading when stdin is a terminal (for PreToolUse).
    """
    try:
        if check_tty and sys.stdin.isatty():
            return {}
        raw = _read_stdin_with_timeout()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}


def load_toml_fallback(path):
    """Load a TOML file; return {} if missing or corrupt."""
    import tomllib
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}
