"""Stop hook: task & recording archive detection.

Checks whether Done/Cancelled tasks or old session recordings
have exceeded their archive thresholds.
"""
import json
import os
import sys
import time
import tomllib
from pathlib import Path

try:
    from _shared import load_stdin_event  # noqa: E402
except (ImportError, ModuleNotFoundError):
    def load_stdin_event(*, check_tty=False):
        try:
            if check_tty and sys.stdin.isatty():
                return {}
            raw = sys.stdin.read()
            if not raw.strip():
                return {}
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {}

SETTINGS_PATH = ".diwu/dsettings.toml"
TASK_JSON_PATH = ".diwu/dtask.json"
RECORDING_DIR = ".diwu/recording"

DEFAULTS = {
    "task_archive_limit": 20,
    "recording_file_limit": 30,
    "recording_retention_days": 30,
}

_CWD: str = "."


def _resolve(path: str) -> str:
    return os.path.join(_CWD, path)


def _load_settings():
    """Load settings from dsettings.toml, falling back to defaults."""
    full = _resolve(SETTINGS_PATH)
    if not os.path.exists(full):
        return dict(DEFAULTS)
    try:
        with open(full, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return dict(DEFAULTS)
    result = dict(DEFAULTS)
    result.update({k: v for k, v in data.items() if k in DEFAULTS})
    return result


def _load_tasks():
    """Load tasks from dtask.json, returning empty list on failure."""
    full = _resolve(TASK_JSON_PATH)
    if not os.path.exists(full):
        return []
    try:
        with open(full, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tasks", [])
    except (json.JSONDecodeError, OSError):
        return []


def check_task_archive(settings, tasks):
    """Check if terminal tasks exceed the archive threshold.

    Returns:
        (needs_archive: bool, count: int, threshold: int, message: str)
    """
    threshold = settings.get("task_archive_limit", DEFAULTS["task_archive_limit"])
    terminal = [t for t in tasks if t.get("status") in ("Done", "Cancelled")]
    count = len(terminal)

    if count >= threshold:
        msg = (
            f"[ARCHIVE_CHECK] Task archive: "
            f"已完成/已取消任务数 ({count}) 达到归档阈值 ({threshold})，"
            f"建议执行 /drec 归档"
        )
        return True, count, threshold, msg

    return False, count, threshold, ""


def check_recording_archive(settings):
    """Check if recording files exceed count or age thresholds.

    Returns:
        (needs_archive: bool, total: int, old_count: int,
         count_threshold: int, days_threshold: int, message: str)
    """
    ct = settings.get(
        "recording_file_limit", DEFAULTS["recording_file_limit"]
    )
    dt = settings.get(
        "recording_retention_days", DEFAULTS["recording_retention_days"]
    )

    rec_dir = _resolve(RECORDING_DIR)
    if not os.path.isdir(rec_dir):
        return False, 0, 0, ct, dt, ""

    now = time.time()
    cutoff = now - (dt * 86400)

    md_files = []
    for name in os.listdir(rec_dir):
        if name.endswith(".md"):
            md_files.append(os.path.join(rec_dir, name))

    total = len(md_files)
    old = sum(1 for f in md_files if os.path.getmtime(f) < cutoff)

    if total >= ct or old > 0:
        parts = []
        if total >= ct:
            parts.append(f"文件数 ({total}) >= 阈值 ({ct})")
        if old > 0:
            parts.append(f"{old} 个文件超过 {dt} 天")
        msg = (
            f"[ARCHIVE_CHECK] Recording archive: "
            + "; ".join(parts) + "，建议执行 /drec"
        )
        return True, total, old, ct, dt, msg

    return False, total, old, ct, dt, ""


def check(settings=None, tasks=None, cwd=None):
    """Main entry point — returns list of (level, message) tuples."""
    global _CWD
    if cwd:
        _CWD = cwd
    if settings is None:
        settings = _load_settings()
    if tasks is None:
        tasks = _load_tasks()

    results = []

    # Task archive check
    needs, count, thresh, msg = check_task_archive(settings, tasks)
    if needs:
        results.append(("info", msg))

    # Recording archive check
    needs2, total, old, ct, dt, msg2 = check_recording_archive(settings)
    if needs2:
        results.append(("info", msg2))

    return results


if __name__ == "__main__":
    import sys

    # Read stdin (CC Stop hook may send JSON input)
    stdin_data = load_stdin_event(check_tty=True)

    event_cwd = stdin_data.get("cwd", ".") if stdin_data else "."
    results = check(cwd=event_cwd)
    if results:
        messages = [msg for _, msg in results]
        # Use hookSpecificOutput — CC-recognized field for plugin-specific advisory output
        output = {
            "hookSpecificOutput": {
                "source": "stop_archive",
                "level": "info",
                "messages": messages,
                "suggestion": "建议执行 /drec 归档",
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)
