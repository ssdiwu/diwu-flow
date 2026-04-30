import json
import os
import sys

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HOOKS_DIR))
SHARED_SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SHARED_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SHARED_SCRIPTS_DIR)

from dtask_state import sync_runtime_state  # noqa: E402


def _load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


event = {}
try:
    event = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    event = {}

sid = event.get("session_id") or event.get("sessionId") or ""
if sid:
    open("/tmp/.claude_main_session", "w").write(sid)

result = {}
cwd = event.get("cwd", "")
if cwd:
    task_data = _load_json(os.path.join(cwd, ".diwu", "dtask.json"))
    sync_result = sync_runtime_state(cwd, task_data, persist=True, ensure_exists=True)
    if sync_result.is_invalid:
        result["additionalSystemPrompt"] = (
            "dtask-state.json 无效，当前 session 不会自动恢复 InProgress。"
            f"请先修复 runtime state：{sync_result.reason}"
        )

    env_path = os.path.join(cwd, ".claude", "env")
    if os.path.isfile(env_path):
        env = {}
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
        if env:
            result["env"] = env

if result:
    print(json.dumps(result))
