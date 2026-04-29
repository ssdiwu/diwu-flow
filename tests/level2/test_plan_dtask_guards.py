"""L2 tests for Plan->Dtask hook guards."""

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
PLAN_EXIT_SCRIPT = PROJECT_ROOT / "hooks" / "scripts" / "plan_exit_hint.py"
TASK_GUARD_SCRIPT = PROJECT_ROOT / "hooks" / "scripts" / "task_entry_guard.py"


def _run_script(script_path, payload, cwd):
    result = subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )
    return result


def test_plan_exit_hint_emits_additional_context(tmp_path):
    payload = {"hook_event_name": "PreToolUse", "tool_name": "ExitPlanMode", "cwd": str(tmp_path)}
    result = _run_script(PLAN_EXIT_SCRIPT, payload, tmp_path)

    assert result.returncode == 0
    output = json.loads(result.stdout)
    hook_output = output["hookSpecificOutput"]
    assert hook_output["hookEventName"] == "PreToolUse"
    assert "additionalContext" in hook_output
    assert "permissionDecision" not in hook_output
    assert "/dtask" in hook_output["additionalContext"]


def test_task_entry_guard_blocks_without_dtask(tmp_path):
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "cwd": str(tmp_path),
        "tool_input": {"file_path": str(tmp_path / "src" / "feature.py")},
    }
    result = _run_script(TASK_GUARD_SCRIPT, payload, tmp_path)

    assert result.returncode == 2
    assert "diwu-task-guard" in result.stderr


def test_task_entry_guard_allows_when_active_task_exists(tmp_path):
    diwu = tmp_path / ".diwu"
    diwu.mkdir()
    (diwu / "dtask.json").write_text(
        json.dumps({
            "tasks": [
                {"id": 1, "title": "x", "status": "InSpec"},
            ]
        }),
        encoding="utf-8",
    )
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "cwd": str(tmp_path),
        "tool_input": {"file_path": str(tmp_path / "src" / "feature.py")},
    }
    result = _run_script(TASK_GUARD_SCRIPT, payload, tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


def test_task_entry_guard_allows_workflow_file_write(tmp_path):
    diwu = tmp_path / ".diwu"
    recording = diwu / "recording"
    recording.mkdir(parents=True)
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "cwd": str(tmp_path),
        "tool_input": {"file_path": str(recording / "session-1.md")},
    }
    result = _run_script(TASK_GUARD_SCRIPT, payload, tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""
