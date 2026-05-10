"""L2 tests for dloop dual-mode architecture."""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
STOP_DECISION_SCRIPT = PROJECT_ROOT / "hooks" / "scripts" / "stop_decision.py"
TASK_GUARD_SCRIPT = PROJECT_ROOT / "hooks" / "scripts" / "task_entry_guard.py"
RUNTIME_STATE_NAME = ".diwu/dtask-state.json"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))



def _run_stop_decision(tmp_path, env_overrides=None, **kwargs):
    """Run stop_decision.py with given tmp_path and optional stdin data."""
    cmd = [sys.executable, str(STOP_DECISION_SCRIPT), "--task-json", str(tmp_path / ".diwu" / "dtask.json")]
    stdin_data = json.dumps(kwargs) if kwargs else ""
    env = os.environ.copy()
    env["DIWU_SILENT"] = "1"
    env.pop("CLAUDE_SESSION_ID", None)
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        cmd,
        input=stdin_data,
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
    )
    return result


def _make_dtask(tasks, tmp_path, **extra):
    """Write dtask.json to tmp_path/.diwu/."""
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    payload = {"tasks": tasks}
    payload.update(extra)
    (diwu / "dtask.json").write_text(json.dumps(payload), encoding="utf-8")


def _make_dsettings(tmp_path, **overrides):
    """Write dsettings.toml to tmp_path/.diwu/."""
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    settings = {"dloop_review_cap": 5}
    settings.update(overrides)
    (diwu / "dsettings.toml").write_text(_dict_to_toml(settings), encoding="utf-8")


def _dict_to_toml(d):
    """Simple dict-to-TOML conversion for test settings (flat + one-level nested)."""
    lines = []
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"[{k}]")
            for sk, sv in v.items():
                if isinstance(sv, bool):
                    lines.append(f"{sk} = {'true' if sv else 'false'}")
                elif isinstance(sv, (int, float)):
                    lines.append(f"{sk} = {sv}")
                else:
                    lines.append(f'{sk} = "{sv}"')
        else:
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, (int, float)):
                lines.append(f"{k} = {v}")
            else:
                lines.append(f'{k} = "{v}"')
    return "\n".join(lines) + "\n"


def _make_runtime_state(tmp_path, *, dloop=None, task_sessions=None):
    (tmp_path / ".diwu").mkdir(exist_ok=True)
    state = {
        "version": 1,
        "task_sessions": task_sessions or {},
        "dloop": dloop,
    }
    (tmp_path / RUNTIME_STATE_NAME).write_text(json.dumps(state), encoding="utf-8")


def _make_dloop_state(tmp_path, **overrides):
    existing = {"task_sessions": {}}
    if (tmp_path / RUNTIME_STATE_NAME).exists():
        existing = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    dloop = {
        "active": True,
        "session_id": "test-session-123",
        "started_at": "2026-04-30T12:00:00Z",
        "completed_task_ids": [],
        "current_iteration": 0,
        "max_tasks": 0,
        "stopped_at": None,
        "stop_reason": None,
    }
    dloop.update(overrides)
    _make_runtime_state(tmp_path, dloop=dloop, task_sessions=existing.get("task_sessions", {}))


def test_dloop_state_file_creation(tmp_path):
    """Verify dtask-state.json carries dloop structure."""
    _make_dloop_state(tmp_path, session_id="test-abc")
    state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    assert state["version"] == 1
    assert state["dloop"]["active"] is True
    assert state["dloop"]["session_id"] == "test-abc"
    assert state["dloop"]["completed_task_ids"] == []
    assert state["dloop"]["current_iteration"] == 0
    assert state["dloop"]["max_tasks"] == 0

def test_cancel_dloop_removes_state(tmp_path):
    """Verify runtime state file can be removed."""
    _make_dloop_state(tmp_path)
    assert (tmp_path / RUNTIME_STATE_NAME).exists()
    (tmp_path / RUNTIME_STATE_NAME).unlink()
    assert not (tmp_path / RUNTIME_STATE_NAME).exists()


def test_stop_decision_default_mode_allows_stop(tmp_path):
    """Default mode (no dloop-state) + InSpec task -> allow stop (no auto-continue!)."""
    tasks = [{"id": 1, "title": "Test task", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)

    result = _run_stop_decision(
        tmp_path,
        session_id="some-session",
        cwd=str(tmp_path),
    )

    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_stop_decision_inprogress_always_blocks(tmp_path):
    """InProgress task no longer triggers dloop block in stop_decision (A group removed).
    stop_decision now only handles B group checks (pending_recording, reminders)."""
    pass


def test_stop_decision_max_tasks_stops_with_report(tmp_path):
    """dloop max_tasks stop logic removed from stop_decision (A group removed)."""
    pass

def test_task_guard_allows_loop_state_write(tmp_path):
    """task_entry_guard should allow writes to .diwu/dtask-state.json."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "cwd": str(tmp_path),
        "tool_input": {"file_path": str(tmp_path / RUNTIME_STATE_NAME)},
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
    """dloop no-tasks stop logic removed from stop_decision (A group removed)."""
    pass


def test_stop_decision_only_inreview_stops(tmp_path):
    """dloop inreview stop logic removed from stop_decision (A group removed)."""
    pass




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

    assert result.returncode == 0
    assert result.stderr == ""


def test_stop_decision_pending_review_stops_with_report(tmp_path):
    """dloop pending_review stop logic removed from stop_decision (A group removed)."""
    pass


# ── Cron mode tests ──────────────────────────────────────────────

def _make_cron_dloop_state(tmp_path, **overrides):
    """Create dloop state with mode=cron."""
    base = {
        "active": True,
        "mode": "cron",
        "session_id": "cron-session-001",
        "started_at": "2026-05-09T00:00:00Z",
        "completed_task_ids": [],
        "initial_done_ids": [],
        "current_iteration": 0,
        "max_tasks": 0,
        "stopped_at": None,
        "stop_reason": None,
        "cron_job_id": "test-job-123",
    }
    base.update(overrides)
    _make_dloop_state(tmp_path, **{k: v for k, v in base.items() if k != "active"})


def test_dloop_cron_mode_start_requires_interval(tmp_path):
    """缺少 --interval → 返回 error。"""
    import subprocess
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "dloop.py"), "start",
         "--cwd", str(tmp_path)],
        capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["status"] == "missing_interval"


def test_dloop_cron_mode_start_creates_state_with_mode(tmp_path):
    """cron 模式 start 写入 mode=cron 到 state。"""
    tasks = [{"id": 1, "title": "Cron task", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)

    from dloop import cmd_start
    result = cmd_start(
        tmp_path, max_tasks=0, interval="3m",
        # 不传 cron_job_id → 应返回 cron_action="create"
    )
    assert result["ok"] is True
    assert result["data"]["mode"] == "cron"
    assert result["data"].get("cron_action") == "create"

    # 验证 state 文件
    state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    assert state["dloop"]["mode"] == "cron"
    assert state["dloop"]["active"] is True


def test_dloop_cron_mode_start_with_job_id(tmp_path):
    """cron 模式 + 已有 job_id → state 包含 cron_job_id。"""
    tasks = [{"id": 1, "title": "T", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)

    from dloop import cmd_start
    result = cmd_start(
        tmp_path, interval="5m", cron_job_id="existing-job-456",
    )
    assert result["ok"] is True
    assert result["data"]["cron_job_id"] == "existing-job-456"
    assert "cron_action" not in result["data"]

    state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    assert state["dloop"]["cron_job_id"] == "existing-job-456"


def test_dloop_status_shows_cron_mode(tmp_path):
    """cmd_status() 输出包含 mode 和 cron_job_id。"""
    tasks = [{"id": 1, "title": "Status T", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)  # 需要 dtask.json 防止 stale 判定
    _make_cron_dloop_state(tmp_path)

    from dloop import cmd_status
    result = cmd_status(tmp_path)
    assert result["ok"] is True
    assert result["status"] == "running"
    assert result["data"]["mode"] == "cron"
    assert result["data"]["cron_job_id"] == "test-job-123"
    assert "cron" in result["formatted_text"]


def test_dloop_stop_cron_mode_returns_cleanup_instruction(tmp_path):
    """cmd_stop() 在 cron 模式下返回 cron_action=delete。"""
    _make_cron_dloop_state(tmp_path)

    from dloop import cmd_stop
    result = cmd_stop(tmp_path)
    assert result["ok"] is True
    assert result["status"] == "cancelled"
    assert result["mode"] == "cron"
    assert result["cron_action"] == "delete"
    assert result["cron_job_id"] == "test-job-123"



