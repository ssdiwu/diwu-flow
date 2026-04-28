"""Stop hook: task & recording archive detection.

Checks whether Done/Cancelled tasks or old session recordings
have exceeded their archive thresholds.
"""
import json
import os
import time

SETTINGS_PATH = ".diwu/dsettings.json"
TASK_JSON_PATH = ".diwu/dtask.json"
RECORDING_DIR = ".diwu/recording"

DEFAULTS = {
    "task_archive_threshold": 20,
    "recording_archive_threshold": 50,
    "recording_retention_days": 30,
}


def _load_settings():
    """Load settings from dsettings.json, falling back to defaults."""
    full = os.path.join(os.getcwd(), SETTINGS_PATH)
    if not os.path.exists(full):
        return dict(DEFAULTS)
    try:
        with open(full, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)
    result = dict(DEFAULTS)
    result.update({k: v for k, v in data.items() if k in DEFAULTS})
    return result


def _load_tasks():
    """Load tasks from dtask.json, returning empty list on failure."""
    full = os.path.join(os.getcwd(), TASK_JSON_PATH)
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
    threshold = settings.get("task_archive_threshold", DEFAULTS["task_archive_threshold"])
    terminal = [t for t in tasks if t.get("status") in ("Done", "Cancelled")]
    count = len(terminal)

    if count >= threshold:
        msg = (
            f"[ARCHIVE_CHECK] Task archive: "
            f"已完成/已取消任务数 ({count}) 达到归档阈值 ({threshold})，"
            f"建议执行 /darc 归档"
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
        "recording_archive_threshold", DEFAULTS["recording_archive_threshold"]
    )
    dt = settings.get(
        "recording_retention_days", DEFAULTS["recording_retention_days"]
    )

    rec_dir = os.path.join(os.getcwd(), RECORDING_DIR)
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
            + "; ".join(parts) + "，建议执行 /darc"
        )
        return True, total, old, ct, dt, msg

    return False, total, old, ct, dt, ""


def check(settings=None, tasks=None):
    """Main entry point — returns list of (level, message) tuples."""
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
    stdin_data = {}
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
            if raw.strip():
                stdin_data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            pass

    results = check()
    if results:
        messages = [msg for _, msg in results]
        # Use hookSpecificOutput — CC-recognized field for plugin-specific advisory output
        output = {
            "hookSpecificOutput": {
                "source": "stop_archive",
                "level": "info",
                "messages": messages,
                "suggestion": "建议执行 /darc 归档",
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)
