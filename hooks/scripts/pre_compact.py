import os
import sys
import time

from _shared import setup_sys_path, load_stdin_event  # noqa: E402

setup_sys_path()

RECORDING_DIR = ".diwu/recording"

event = load_stdin_event()
cwd = event.get("cwd", ".")
session_id = event.get("session_id") or event.get("sessionId") or ""

# Session ID validation: reject writes from non-current session
expected_sid = os.environ.get("DIWU_SESSION_ID", "")
if expected_sid and session_id and session_id != expected_sid:
    sys.exit(0)

recording_dir = os.path.join(cwd, RECORDING_DIR)
if not os.path.isdir(os.path.dirname(recording_dir)):
    sys.exit(0)

# Use Python time instead of subprocess to avoid fork/exec overhead
now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
filename = now.replace(" ", "-").replace(":", "")
entry = f"## [auto-compact] 进度快照 {now}\n\n"

os.makedirs(recording_dir, exist_ok=True)
session_file = os.path.join(recording_dir, f"session-{filename}.md")
# Atomic write: write to tmp file then rename
tmp_file = session_file + ".tmp"
with open(tmp_file, "w", encoding="utf-8") as f:
    f.write(entry)
os.rename(tmp_file, session_file)
