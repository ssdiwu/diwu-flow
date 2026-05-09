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

from session_scope import scoped_session_file  # noqa: E402


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

    assert result.returncode == 0
    assert result.stdout.strip() == ""


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

    # Falls through to default mode -> allow stop, and stale loop state is cleared.
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    runtime_state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    assert runtime_state["dloop"] is None


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

    assert result.returncode == 0
    assert result.stdout.strip() == ""
    runtime_state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    assert runtime_state["dloop"] is None


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

    # Should stop and emit phase report without blocking the stop hook process
    assert result.returncode == 0
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

    assert result.returncode == 0
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

    assert result.returncode == 0
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

    assert result.returncode == 0
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

    assert result.returncode == 0
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
    assert result3.returncode == 0
    assert result3.stdout.strip() == ""


def test_stop_decision_missing_session_id_exits_loop_mode(tmp_path):
    """T2a: Stop event 无 session_id + InSpec 任务 → 必须 allow stop。"""
    tasks = [{"id": 1, "title": "T1", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(tmp_path, session_id="dloop-test")  # dummy 或已绑定

    # 不传 session_id
    result = _run_stop_decision(tmp_path, cwd=str(tmp_path))  # 无 session_id 字段
    assert result.returncode == 1
    # stderr 应含 STOP_HINT 提示（不再输出非法 decision JSON 到 stdout）
    assert "STOP_HINT" in result.stderr
    assert result.stdout.strip() == ""


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
    assert "STOP_HINT" in result.stderr
    assert result.stdout.strip() == ""


def test_stop_decision_missing_event_session_uses_env_for_dloop(tmp_path):
    """Stop event 无 session_id 但 env 有 SID → 用 env 驱动 dloop。"""
    tasks = [{"id": 1, "title": "T1", "status": "InSpec", "blocked_by": []}]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(tmp_path, session_id="dloop-20260504-120000")

    result = _run_stop_decision(
        tmp_path,
        env_overrides={"CLAUDE_SESSION_ID": "env-loop-session"},
        cwd=str(tmp_path),
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["decision"] == "block"
    state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    assert state["dloop"]["session_id"] == "env-loop-session"


def test_stop_decision_missing_event_session_uses_scoped_file_for_dloop(tmp_path):
    """Stop event/env 无 session_id 但 scoped 文件有 SID → 用 scoped 文件驱动 dloop。"""
    tasks = [{"id": 1, "title": "T1", "status": "InSpec", "blocked_by": []}]
    _make_dtask(tasks, tmp_path)
    _make_dloop_state(tmp_path, session_id="dloop-20260504-120001")
    session_file = scoped_session_file(tmp_path)
    try:
        session_file.write_text("file-loop-session\n", encoding="utf-8")
        result = _run_stop_decision(tmp_path, cwd=str(tmp_path))
    finally:
        session_file.unlink(missing_ok=True)

    assert result.returncode == 0
    assert json.loads(result.stdout)["decision"] == "block"
    state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    assert state["dloop"]["session_id"] == "file-loop-session"


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
    """cron 模式缺少 --interval → 返回 error。"""
    import subprocess
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "dloop.py"), "start",
         "--cwd", str(tmp_path), "--mode", "cron"],
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
        tmp_path, max_tasks=0, session_id="cron-test-sid",
        mode="cron", interval="3m",
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
        tmp_path, mode="cron", interval="5m", cron_job_id="existing-job-456",
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


def test_dloop_session_mode_backward_compatible(tmp_path):
    """默认 --mode=session 行为不变（向后兼容）。"""
    tasks = [{"id": 1, "title": "T", "status": "InSpec"}]
    _make_dtask(tasks, tmp_path)

    from dloop import cmd_start
    result = cmd_start(tmp_path, session_id="compat-test")
    assert result["ok"] is True
    assert result["data"]["mode"] == "session"

    state = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    # 默认 mode 不写入（_normalize_loop 默认为 "session"）
    assert state["dloop"].get("mode", "session") == "session"
