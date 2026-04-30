import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from dtask_state import runtime_state_path, sync_runtime_state  # noqa: E402


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_sync_creates_standard_runtime_state(tmp_project_dir):
    dtask = {"tasks": []}
    result = sync_runtime_state(tmp_project_dir, dtask, persist=True, ensure_exists=True)
    assert result.ok is True
    state = json.loads(runtime_state_path(tmp_project_dir).read_text(encoding="utf-8"))
    assert state["version"] == 1
    assert state["task_sessions"] == {}
    assert state["dloop"] is None


def test_sync_cleans_stale_owner(tmp_project_dir):
    _write_json(
        runtime_state_path(tmp_project_dir),
        {
            "version": 1,
            "task_sessions": {
                "1": {"session_id": "sid-1", "started_at": "2026-04-30T12:00:00Z"}
            },
            "dloop": None,
        },
    )
    dtask = {"tasks": [{"id": 1, "title": "done", "status": "Done"}]}
    result = sync_runtime_state(tmp_project_dir, dtask, persist=True, ensure_exists=True)
    assert result.ok is True
    assert result.cleaned_task_ids == [1]
    state = json.loads(runtime_state_path(tmp_project_dir).read_text(encoding="utf-8"))
    assert state["task_sessions"] == {}


def test_sync_rejects_multiple_tasks_for_same_session(tmp_project_dir):
    _write_json(
        runtime_state_path(tmp_project_dir),
        {
            "version": 1,
            "task_sessions": {
                "1": {"session_id": "same-session", "started_at": "2026-04-30T12:00:00Z"},
                "2": {"session_id": "same-session", "started_at": "2026-04-30T12:05:00Z"},
            },
            "dloop": None,
        },
    )
    dtask = {
        "tasks": [
            {"id": 1, "title": "a", "status": "InProgress"},
            {"id": 2, "title": "b", "status": "InProgress"},
        ]
    }
    result = sync_runtime_state(tmp_project_dir, dtask, persist=False)
    assert result.ok is False
    assert "同一 session" in result.reason


def test_sync_rejects_status_field_in_task_sessions(tmp_project_dir):
    _write_json(
        runtime_state_path(tmp_project_dir),
        {
            "version": 1,
            "task_sessions": {
                "1": {
                    "session_id": "sid-1",
                    "started_at": "2026-04-30T12:00:00Z",
                    "status": "InProgress",
                }
            },
            "dloop": None,
        },
    )
    result = sync_runtime_state(tmp_project_dir, {"tasks": []}, persist=False)
    assert result.ok is False
    assert "status" in result.reason


def test_sync_migrates_legacy_dloop_state(tmp_project_dir):
    legacy = tmp_project_dir / ".diwu" / "dloop-state.json"
    _write_json(
        legacy,
        {
            "active": True,
            "session_id": "loop-session",
            "started_at": "2026-04-30T12:00:00Z",
            "completed_task_ids": [1],
            "current_iteration": 1,
            "max_tasks": 3,
            "stopped_at": None,
            "stop_reason": None,
        },
    )
    result = sync_runtime_state(tmp_project_dir, {"tasks": []}, persist=True, ensure_exists=True)
    assert result.ok is True
    assert result.migrated_legacy_loop is True
    state = json.loads(runtime_state_path(tmp_project_dir).read_text(encoding="utf-8"))
    assert state["dloop"]["session_id"] == "loop-session"
    assert not legacy.exists()
