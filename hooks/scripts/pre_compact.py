import json
import os
import subprocess
import sys

from _shared import setup_sys_path, load_json_fallback, load_stdin_event  # noqa: E402

setup_sys_path()

from dtask_state import resolve_session_inprogress_task, sync_runtime_state  # noqa: E402

TASK_JSON_PATH = ".diwu/dtask.json"
RECORDING_DIR = ".diwu/recording"

event = load_stdin_event()
cwd = event.get("cwd", ".")
session_id = event.get("session_id") or event.get("sessionId") or ""

# Session ID validation: reject writes from non-current session
expected_sid = os.environ.get("DIWU_SESSION_ID", "")
if expected_sid and session_id and session_id != expected_sid:
    sys.exit(0)

task_file = os.path.join(cwd, TASK_JSON_PATH)
task_data = load_json_fallback(task_file)
sync_result = sync_runtime_state(cwd, task_data, persist=True)
if sync_result.is_invalid:
    sys.exit(0)

resolution = resolve_session_inprogress_task(task_data.get("tasks", []), sync_result.state, session_id)
if not resolution.is_match:
    sys.exit(0)

recording_dir = os.path.join(cwd, RECORDING_DIR)
if not os.path.isdir(os.path.dirname(recording_dir)):
    sys.exit(0)

try:
    diff = subprocess.check_output(
        ["git", "diff", "--stat"], cwd=cwd, stderr=subprocess.DEVNULL
    ).decode().strip()
    cached = subprocess.check_output(
        ["git", "diff", "--cached", "--stat"], cwd=cwd, stderr=subprocess.DEVNULL
    ).decode().strip()
    stat = "\n".join(filter(None, [diff, cached]))
except (subprocess.CalledProcessError, OSError, FileNotFoundError):
    stat = ""

now = subprocess.check_output(["date", "+%Y-%m-%d %H:%M:%S"]).decode().strip()
filename = now.replace(" ", "-").replace(":", "")
task = resolution.task
entry = (
    "## [auto-compact] Task#" + str(task["id"]) + " 进度快照 " + now + "\n\n"
    + "任务：" + task.get("title", "") + "\n"
)
if stat:
    entry += "\n```\n" + stat + "\n```\n"

os.makedirs(recording_dir, exist_ok=True)
session_file = os.path.join(recording_dir, f"session-{filename}.md")
# Atomic write: write to tmp file then rename
tmp_file = session_file + ".tmp"
with open(tmp_file, "w", encoding="utf-8") as f:
    f.write(entry)
os.rename(tmp_file, session_file)
