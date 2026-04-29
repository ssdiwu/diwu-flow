"""L2 tests for dloop dual-mode architecture."""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
STOP_DECISION_SCRIPT = PROJECT_ROOT / "hooks" / "scripts" / "stop_decision.py"
TASK_GUARD_SCRIPT = PROJECT_ROOT / "hooks" / "scripts" / "task_entry_guard.py"
DLOOP_STATE_NAME = ".diwu/dloop-state.json"


def _run_stop_decision(tmp_path, **kwargs):
    """Run stop_decision.py with given tmp_path and optional stdin data."""
    cmd = [sys.executable, str(STOP_DECISION_SCRIPT), "--task-json", str(tmp_path / ".diwu" / "dtask.json")]
    stdin_data = json.dumps(kwargs) if kwargs else ""
    result = subprocess.run(
        cmd,
        input=stdin_data,
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    return result


def _make_dtask(tasks, tmp_path):
    """Write dtask.json to tmp_path/.diwu/."""
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.json").write_text(json.dumps({"tasks": tasks}), encoding="utf-8")


def _make_dloop_state(tmp_path, **overrides):
    """Write dloop-state.json to tmp_path."""
    state = {
        "active": True,
        "session_id": "test-session-123",
        "started_at": "2026-04-30T12:00:00Z",
        "completed_task_ids": [],
        "current_iteration": 0,
        "max_tasks": 10,
        "stopped_at": None,
        "stop_reason": None,
    }
    state.update(overrides)
    # Ensure .diwu/ directory exists
    (tmp_path / ".diwu").mkdir(exist_ok=True)
    (tmp_path / DLOOP_STATE_NAME).write_text(json.dumps(state), encoding="utf-8")


def test_dloop_state_file_creation(tmp_path):
    """Verify dloop-state.json can be created and has correct structure."""
    _make_dloop_state(tmp_path, session_id="test-abc")
    state = json.loads((tmp_path / DLOOP_STATE_NAME).read_text(encoding="utf-8"))
    assert state["active"] is True
    assert state["session_id"] == "test-abc"
    assert state["completed_task_ids"] == []
    assert state["current_iteration"] == 0
    assert state["max_tasks"] == 10


def test_cancel_dloop_removes_state(tmp_path):
    """Verify removing dloop-state.json cancels the loop."""
    _make_dloop_state(tmp_path)
    assert (tmp_path / DLOOP_STATE_NAME).exists()
    (tmp_path / DLOOP_STATE_NAME).unlink()
    assert not (tmp_path / DLOOP_STATE_NAME).exists()


def test_stop_decision_loop_mode_blocks_with_inSpec(tmp_path):
    """Loop mode + InSpec task -> block with iteration info."""
    tasks = [{"id": 1, "title": "Test task", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(tmp_path, session_id="test-session-match")

    result = _run_stop_decision(
        tmp_path,
        session_id="test-session-match",
        cwd=str(tmp_path),
    )

    assert result.returncode == 0  # continue
    output = json.loads(result.stdout) if result.stdout.strip() else {}
    assert output.get("decision") == "block"
    assert "iteration" in output.get("reason", "")


def test_stop_decision_default_mode_allows_stop(tmp_path):
    """Default mode (no dloop-state) + InSpec task -> allow stop (no auto-continue!)."""
    tasks = [{"id": 1, "title": "Test task", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)

    result = _run_stop_decision(
        tmp_path,
        session_id="some-session",
        cwd=str(tmp_path),
    )

    assert result.returncode == 1  # stop


def test_stop_decision_inprogress_always_blocks(tmp_path):
    """InProgress task -> block regardless of dloop mode."""
    tasks = [{"id": 1, "title": "Active task", "status": "InProgress"}]
    _make_dtask(tasks, tmp_path)

    # Default mode: no dloop-state
    result = _run_stop_decision(tmp_path, cwd=str(tmp_path))
    assert result.returncode == 0
    output = json.loads(result.stdout) if result.stdout.strip() else {}
    assert output.get("decision") == "block"

    # Loop mode: with dloop-state
    _make_dloop_state(tmp_path, session_id="session-b")
    result = _run_stop_decision(
        tmp_path,
        session_id="session-b",
        cwd=str(tmp_path),
    )
    assert result.returncode == 0
    output = json.loads(result.stdout) if result.stdout.strip() else {}
    assert output.get("decision") == "block"


def test_stop_decision_session_isolation(tmp_path):
    """dloop-state.json session_id mismatch -> default mode behavior."""
    tasks = [
        {"id": 1, "title": "Task A", "status": "InSpec"},
        {"id": 2, "title": "Task B", "status": "Done"},
    ]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(tmp_path, session_id="original-session")

    result = _run_stop_decision(
        tmp_path,
        session_id="different-session",
        cwd=str(tmp_path),
    )

    # Falls through to default mode -> allow stop
    assert result.returncode == 1


def test_stop_decision_max_tasks_stops_with_report(tmp_path):
    """completed_task_ids >= max_tasks -> loop stops with phase report + cleanup."""
    tasks = [
        {"id": 1, "title": "Done task", "status": "Done"},
        {"id": 2, "title": "Next task", "status": "InSpec"},
    ]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(
        tmp_path,
        session_id="session-max",
        completed_task_ids=[1, 2, 3],
        current_iteration=3,
        max_tasks=3,
    )

    result = _run_stop_decision(
        tmp_path,
        session_id="session-max",
        cwd=str(tmp_path),
    )

    # Should stop (exit code 1)
    assert result.returncode == 1
    # State file MUST be cleaned up
    assert not (tmp_path / DLOOP_STATE_NAME).exists()
    # Phase report should be in stderr
    assert "DLOOP 阶段报告" in result.stderr
    assert "达到任务上限" in result.stderr


def test_task_guard_allows_loop_state_write(tmp_path):
    """task_entry_guard should allow writes to .diwu/dloop-state.json."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "cwd": str(tmp_path),
        "tool_input": {"file_path": str(tmp_path / DLOOP_STATE_NAME)},
    }
    result = subprocess.run(
        [sys.executable, str(TASK_GUARD_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0
    assert result.stderr == ""


def test_stop_decision_no_tasks_stops_with_report(tmp_path):
    """No InSpec/InProgress tasks in loop mode -> loop stops with report + cleanup."""
    tasks = [
        {"id": 1, "title": "Done task", "status": "Done"},
        {"id": 2, "title": "Also done", "status": "Done"},
    ]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(
        tmp_path,
        session_id="session-empty",
        completed_task_ids=[1, 2],
        current_iteration=2,
    )

    result = _run_stop_decision(
        tmp_path,
        session_id="session-empty",
        cwd=str(tmp_path),
    )

    assert result.returncode == 1
    assert not (tmp_path / DLOOP_STATE_NAME).exists()
    assert "DLOOP 阶段报告" in result.stderr
    assert "无可执行任务" in result.stderr


def test_stop_decision_loop_mode_only_inreview_stops(tmp_path):
    """Loop mode + only InReview tasks remaining (no InSpec/InProgress) -> allow stop."""
    tasks = [
        {"id": 1, "title": "Done task", "status": "Done"},
        {"id": 2, "title": "Review task", "status": "InReview"},
    ]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(
        tmp_path,
        session_id="session-inreview",
        completed_task_ids=[1],
        current_iteration=1,
    )

    result = _run_stop_decision(
        tmp_path,
        session_id="session-inreview",
        cwd=str(tmp_path),
    )

    assert result.returncode == 1  # allow stop
    assert not (tmp_path / DLOOP_STATE_NAME).exists()
    assert "DLOOP 阶段报告" in result.stderr
    assert "无可执行任务" in result.stderr


def test_loop_completion_reports_completed_tasks(tmp_path):
    """Phase report includes completed task details from dtask.json."""
    tasks = [
        {"id": 1, "title": "Fix bug A", "status": "Done"},
        {"id": 2, "title": "Refactor B", "status": "Done"},
        {"id": 3, "title": "Pending C", "status": "InSpec"},
    ]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(
        tmp_path,
        session_id="session-report",
        completed_task_ids=[1, 2],
        current_iteration=2,
        max_tasks=2,  # Trigger max_tasks stop
    )

    result = _run_stop_decision(
        tmp_path,
        session_id="session-report",
        cwd=str(tmp_path),
    )

    assert result.returncode == 1
    # Report should mention completed tasks by name
    assert "Fix bug A" in result.stderr
    assert "Refactor B" in result.stderr
    # Report should mention remaining tasks
    assert "Pending C" in result.stderr
