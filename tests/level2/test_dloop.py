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


def _run_stop_decision(tmp_path, **kwargs):
    """Run stop_decision.py with given tmp_path and optional stdin data."""
    cmd = [sys.executable, str(STOP_DECISION_SCRIPT), "--task-json", str(tmp_path / ".diwu" / "dtask.json")]
    stdin_data = json.dumps(kwargs) if kwargs else ""
    env = os.environ.copy()
    env["DIWU_SILENT"] = "1"
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
    """Write dsettings.json to tmp_path/.diwu/."""
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    settings = {"review_limit": 5}
    settings.update(overrides)
    (diwu / "dsettings.json").write_text(json.dumps(settings), encoding="utf-8")


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
    _make_runtime_state(
        tmp_path,
        task_sessions={"1": {"session_id": "session-a", "started_at": "2026-04-30T12:00:00Z"}},
    )

    result = _run_stop_decision(tmp_path, session_id="session-a", cwd=str(tmp_path))
    assert result.returncode == 0
    output = json.loads(result.stdout) if result.stdout.strip() else {}
    assert output.get("decision") == "block"

    _make_dloop_state(tmp_path, session_id="session-a")
    result = _run_stop_decision(
        tmp_path,
        session_id="session-a",
        cwd=str(tmp_path),
    )
    assert result.returncode == 0
    output = json.loads(result.stdout) if result.stdout.strip() else {}
    assert output.get("decision") == "block"


def test_stop_decision_session_isolation(tmp_path):
    """dtask-state.json.dloop session_id mismatch -> default mode behavior."""
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


def test_stop_decision_session_isolation_accepts_sessionId(tmp_path):
    """sessionId 事件字段也必须触发 session isolation。"""
    tasks = [
        {"id": 1, "title": "Task A", "status": "InSpec"},
        {"id": 2, "title": "Task B", "status": "Done"},
    ]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(tmp_path, session_id="original-session")

    result = _run_stop_decision(
        tmp_path,
        sessionId="different-session",
        cwd=str(tmp_path),
    )

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
    runtime_state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    assert runtime_state["dloop"] is None
    # Phase report should be in stderr
    assert "DLOOP 阶段报告" in result.stderr
    assert "达到任务上限" in result.stderr


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
    runtime_state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    assert runtime_state["dloop"] is None
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
    runtime_state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    assert runtime_state["dloop"] is None
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


def test_stop_decision_pending_review_stops_with_report(tmp_path):
    """PENDING REVIEW should stop the loop and cleanup stale state."""
    tasks = [
        {"id": 1, "title": "Review task", "status": "InReview"},
        {"id": 2, "title": "Pending C", "status": "InSpec"},
    ]
    _make_dtask(tasks, tmp_path, review_used=5)
    _make_dsettings(tmp_path, review_limit=5)
    _make_dloop_state(
        tmp_path,
        session_id="session-review-limit",
        completed_task_ids=[1],
        current_iteration=1,
        max_tasks=0,
    )

    result = _run_stop_decision(
        tmp_path,
        session_id="session-review-limit",
        cwd=str(tmp_path),
    )

    assert result.returncode == 1
    runtime_state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    assert runtime_state["dloop"] is None
    assert "PENDING REVIEW" in result.stderr


def test_stop_decision_first_bind_replaces_dummy_id(tmp_path):
    """T1: 首次带真实 SID 的 Stop event 应将 dummy loop_sid 替换并持久化。"""
    tasks = [{"id": 1, "title": "T1", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(tmp_path, session_id="dloop-20260430-120000")  # dummy

    # 第一次：真实 SID → 应绑定并 block
    result = _run_stop_decision(tmp_path, session_id="real-session-abc", cwd=str(tmp_path))
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output.get("decision") == "block"

    # 验证 state 已被持久化
    state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    assert state["dloop"]["session_id"] == "real-session-abc"

    # 第二次：同一 SID → 继续 block
    result2 = _run_stop_decision(tmp_path, session_id="real-session-abc", cwd=str(tmp_path))
    assert result2.returncode == 0

    # 第三步：不同 SID → 退出 loop mode (allow stop)
    result3 = _run_stop_decision(tmp_path, session_id="other-session", cwd=str(tmp_path))
    assert result3.returncode == 1  # allow stop


def test_stop_decision_missing_session_id_exits_loop_mode(tmp_path):
    """T2a: Stop event 无 session_id + InSpec 任务 → 必须 allow stop。"""
    tasks = [{"id": 1, "title": "T1", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(tmp_path, session_id="dloop-test")  # dummy 或已绑定

    # 不传 session_id
    result = _run_stop_decision(tmp_path, cwd=str(tmp_path))  # 无 session_id 字段
    assert result.returncode == 1  # 必须退出 loop mode
    # stderr 应含 allow_stop 提示
    assert "allow_stop" in result.stdout


def test_stop_decision_missing_session_with_inprogress_allows_stop(tmp_path):
    """T2b: Stop event 无 session_id + InProgress 任务 → 显式 allow stop。"""
    tasks = [{"id": 1, "title": "Active", "status": "InProgress"}]
    _make_dtask(tasks, tmp_path)
    _make_runtime_state(
        tmp_path,
        task_sessions={"1": {"session_id": "session-a", "started_at": "2026-04-30T12:00:00Z"}},
    )
    _make_dloop_state(tmp_path, session_id="dloop-test")

    # 不传 session_id
    result = _run_stop_decision(tmp_path, cwd=str(tmp_path))
    # 必须 allow stop（不能落入 default mode 的 resolve_session_inprogress_task）
    assert result.returncode == 1
    assert "allow_stop" in result.stdout


def test_stop_decision_loop_mode_reason_delegates_drun(tmp_path):
    """Loop mode + InSpec + 未命中停止条件 → reason 含 /drun 委托而非具体任务名。"""
    tasks = [{"id": 1, "title": "Next task", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(tmp_path, session_id="match-sid", max_tasks=5)

    result = _run_stop_decision(tmp_path, session_id="match-sid", cwd=str(tmp_path))
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output.get("decision") == "block"
    assert "请继续执行 /drun" in output.get("reason", "")
    # 不应包含具体任务名
    assert "Next task" not in output.get("reason", "")


def test_stop_decision_first_bind_replaces_dummy_id(tmp_path):
    """T1: 首次带真实 SID 的 Stop event 应将 dummy loop_sid 替换并持久化。"""
    tasks = [{"id": 1, "title": "T1", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(tmp_path, session_id="dloop-20260430-120000")  # dummy

    # 第一次：真实 SID → 应绑定并 block
    result = _run_stop_decision(tmp_path, session_id="real-session-abc", cwd=str(tmp_path))
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output.get("decision") == "block"

    # 验证 state 已被持久化
    state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    assert state["dloop"]["session_id"] == "real-session-abc"

    # 第二次：同一 SID → 继续 block
    result2 = _run_stop_decision(tmp_path, session_id="real-session-abc", cwd=str(tmp_path))
    assert result2.returncode == 0

    # 第三步：不同 SID → 退出 loop mode (allow stop)
    result3 = _run_stop_decision(tmp_path, session_id="other-session", cwd=str(tmp_path))
    assert result3.returncode == 1  # allow stop


def test_stop_decision_missing_session_id_exits_loop_mode(tmp_path):
    """T2a: Stop event 无 session_id + InSpec 任务 → 必须 allow stop。"""
    tasks = [{"id": 1, "title": "T1", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(tmp_path, session_id="dloop-test")  # dummy 或已绑定

    # 不传 session_id
    result = _run_stop_decision(tmp_path, cwd=str(tmp_path))  # 无 session_id 字段
    assert result.returncode == 1  # 必须退出 loop mode
    # stderr 应含 allow_stop 提示
    assert "allow_stop" in result.stdout


def test_stop_decision_missing_session_with_inprogress_allows_stop(tmp_path):
    """T2b: Stop event 无 session_id + InProgress 任务 → 显式 allow stop。"""
    tasks = [{"id": 1, "title": "Active", "status": "InProgress"}]
    _make_dtask(tasks, tmp_path)
    _make_runtime_state(
        tmp_path,
        task_sessions={"1": {"session_id": "session-a", "started_at": "2026-04-30T12:00:00Z"}},
    )
    _make_dloop_state(tmp_path, session_id="dloop-test")

    # 不传 session_id
    result = _run_stop_decision(tmp_path, cwd=str(tmp_path))
    # 必须 allow stop（不能落入 default mode 的 resolve_session_inprogress_task）
    assert result.returncode == 1
    assert "allow_stop" in result.stdout


def test_stop_decision_loop_mode_reason_delegates_drun(tmp_path):
    """Loop mode + InSpec + 未命中停止条件 → reason 含 /drun 委托而非具体任务名。"""
    tasks = [{"id": 1, "title": "Next task", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(tmp_path, session_id="match-sid", max_tasks=5)

    result = _run_stop_decision(tmp_path, session_id="match-sid", cwd=str(tmp_path))
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output.get("decision") == "block"
    assert "请继续执行 /drun" in output.get("reason", "")
    # 不应包含具体任务名
    assert "Next task" not in output.get("reason", "")
