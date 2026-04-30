import json
import os
import subprocess
import sys

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HOOKS_DIR))
SHARED_SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SHARED_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SHARED_SCRIPTS_DIR)

from dtask_state import resolve_session_inprogress_task, sync_runtime_state  # noqa: E402

TASK_JSON_PATH = ".diwu/dtask.json"
RECORDING_DIR = ".diwu/recording"


def _load_event():
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def _load_task_data(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


event = _load_event()
cwd = event.get("cwd", ".")
session_id = event.get("session_id") or event.get("sessionId") or ""

task_file = os.path.join(cwd, TASK_JSON_PATH)
task_data = _load_task_data(task_file)
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
except Exception:
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
open(session_file, "w").write(entry)
