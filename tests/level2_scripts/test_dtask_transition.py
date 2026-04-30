import json
from pathlib import Path

from conftest import run_script  # noqa: E402


def _write_dtask(root: Path, tasks):
    diwu = root / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.json").write_text(
        json.dumps({"tasks": tasks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_dtask(root: Path) -> dict:
    return json.loads((root / ".diwu" / "dtask.json").read_text(encoding="utf-8"))


def _read_runtime(root: Path) -> dict:
    return json.loads((root / ".diwu" / "dtask-state.json").read_text(encoding="utf-8"))


def test_mark_inspec_updates_status_only(tmp_project_dir):
    _write_dtask(tmp_project_dir, [
        {"id": 1, "title": "a", "status": "InDraft"},
        {"id": 2, "title": "b", "status": "InDraft"},
    ])
    rc, out, _ = run_script("dtask_transition.py", "mark-inspec", "--task-ids", "1,2", "--cwd", str(tmp_project_dir))
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    data = _read_dtask(tmp_project_dir)
    assert [task["status"] for task in data["tasks"]] == ["InSpec", "InSpec"]
    assert _read_runtime(tmp_project_dir)["task_sessions"] == {}


def test_claim_writes_owner_and_inprogress(tmp_project_dir):
    _write_dtask(tmp_project_dir, [
        {"id": 1, "title": "a", "status": "InSpec"},
    ])
    rc, out, _ = run_script(
        "dtask_transition.py",
        "claim",
        "--task-id", "1",
        "--session-id", "sid-1",
        "--cwd", str(tmp_project_dir),
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["status"] == "claimed"
    assert _read_dtask(tmp_project_dir)["tasks"][0]["status"] == "InProgress"
    assert _read_runtime(tmp_project_dir)["task_sessions"]["1"]["session_id"] == "sid-1"


def test_release_requires_owner_match(tmp_project_dir):
    _write_dtask(tmp_project_dir, [
        {"id": 1, "title": "a", "status": "InProgress"},
    ])
    runtime = {
        "version": 1,
        "task_sessions": {
            "1": {"session_id": "sid-old", "started_at": "2026-04-30T12:00:00Z"}
        },
        "dloop": None,
    }
    (tmp_project_dir / ".diwu" / "dtask-state.json").write_text(json.dumps(runtime, ensure_ascii=False, indent=2))
    rc, out, _ = run_script(
        "dtask_transition.py",
        "release",
        "--task-id", "1",
        "--to", "done",
        "--session-id", "sid-new",
        "--cwd", str(tmp_project_dir),
    )
    assert rc == 1
    payload = json.loads(out)
    assert payload["status"] == "owner_mismatch"
    assert _read_dtask(tmp_project_dir)["tasks"][0]["status"] == "InProgress"


def test_adopt_then_release_succeeds(tmp_project_dir):
    _write_dtask(tmp_project_dir, [
        {"id": 1, "title": "a", "status": "InProgress"},
    ])
    runtime = {
        "version": 1,
        "task_sessions": {
            "1": {"session_id": "sid-old", "started_at": "2026-04-30T12:00:00Z"}
        },
        "dloop": None,
    }
    (tmp_project_dir / ".diwu" / "dtask-state.json").write_text(json.dumps(runtime, ensure_ascii=False, indent=2))

    rc_adopt, out_adopt, _ = run_script(
        "dtask_transition.py",
        "adopt",
        "--task-id", "1",
        "--session-id", "sid-new",
        "--cwd", str(tmp_project_dir),
    )
    assert rc_adopt == 0
    assert json.loads(out_adopt)["status"] == "adopted"

    rc_release, out_release, _ = run_script(
        "dtask_transition.py",
        "release",
        "--task-id", "1",
        "--to", "done",
        "--session-id", "sid-new",
        "--cwd", str(tmp_project_dir),
    )
    assert rc_release == 0
    assert json.loads(out_release)["status"] == "released"
    assert _read_dtask(tmp_project_dir)["tasks"][0]["status"] == "Done"
    assert _read_runtime(tmp_project_dir)["task_sessions"] == {}


def test_claim_rejects_second_inprogress_for_same_session(tmp_project_dir):
    _write_dtask(tmp_project_dir, [
        {"id": 1, "title": "a", "status": "InProgress"},
        {"id": 2, "title": "b", "status": "InSpec"},
    ])
    runtime = {
        "version": 1,
        "task_sessions": {
            "1": {"session_id": "sid-1", "started_at": "2026-04-30T12:00:00Z"}
        },
        "dloop": None,
    }
    (tmp_project_dir / ".diwu" / "dtask-state.json").write_text(json.dumps(runtime, ensure_ascii=False, indent=2))
    rc, out, _ = run_script(
        "dtask_transition.py",
        "claim",
        "--task-id", "2",
        "--session-id", "sid-1",
        "--cwd", str(tmp_project_dir),
    )
    assert rc == 1
    payload = json.loads(out)
    assert payload["status"] == "invalid_runtime_state"
    assert _read_dtask(tmp_project_dir)["tasks"][1]["status"] == "InSpec"


def test_release_rejects_direct_inspec_to_done(tmp_project_dir):
    _write_dtask(tmp_project_dir, [
        {"id": 1, "title": "a", "status": "InSpec"},
    ])
    rc, out, _ = run_script(
        "dtask_transition.py",
        "release",
        "--task-id", "1",
        "--to", "done",
        "--session-id", "sid-1",
        "--cwd", str(tmp_project_dir),
    )
    assert rc == 1
    payload = json.loads(out)
    assert payload["status"] == "invalid_transition"
