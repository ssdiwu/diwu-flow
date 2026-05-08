import json
import sys
import unittest
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from conftest import run_script  # noqa: E402
from session_scope import scoped_session_file  # noqa: E402


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


def test_claim_rejects_stale_owner_from_other_session(tmp_project_dir):
    """claim 应拒绝 task_sessions 中属于其他 session 的任务（即使 status=InSpec）。

    防止跨会话抢任务：前序 dloop 会话遗留的 task_sessions owner
    不应被当前会话的 claim 静默覆盖。
    """
    _write_dtask(tmp_project_dir, [
        {"id": 7, "title": "stale-owned", "status": "InSpec"},
        {"id": 8, "title": "clean", "status": "InSpec"},
    ])
    runtime = {
        "version": 1,
        "task_sessions": {
            "7": {"session_id": "other-session-abc", "started_at": "2026-05-08T04:00:00Z"}
        },
        "dloop": None,
    }
    (tmp_project_dir / ".diwu" / "dtask-state.json").write_text(json.dumps(runtime, ensure_ascii=False, indent=2))

    # Task#7 有其他 session 的 stale owner → claim 应拒绝
    rc, out, _ = run_script(
        "dtask_transition.py",
        "claim",
        "--task-id", "7",
        "--session-id", "current-session",
        "--cwd", str(tmp_project_dir),
    )
    assert rc == 1
    payload = json.loads(out)
    assert payload["status"] == "owner_mismatch"
    assert "other-session" in payload.get("message", "") or "持有" in payload.get("message", "")
    # Task 状态不变
    assert _read_dtask(tmp_project_dir)["tasks"][0]["status"] == "InSpec"

    # Task#8 无 owner → claim 应正常通过
    rc2, out2, _ = run_script(
        "dtask_transition.py",
        "claim",
        "--task-id", "8",
        "--session-id", "current-session",
        "--cwd", str(tmp_project_dir),
    )
    assert rc2 == 0
    payload2 = json.loads(out2)
    assert payload2["status"] == "claimed"
    assert _read_dtask(tmp_project_dir)["tasks"][1]["status"] == "InProgress"


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


class TestAutoSessionIdResolution(unittest.TestCase):
    """Task#49: --session-id auto 解析优先级链路测试。"""

    def _run(self, extra_args: list[str] | None = None, env=None):
        cmd = ["dtask_transition.py", "claim", "--task-id", "1", "--cwd", str(self.tmp_dir)]
        if extra_args:
            cmd.extend(extra_args)
        return run_script(*cmd, env=env)

    def setUp(self):
        self.tmp_dir = Path(__file__).resolve().parent / f"tmp_auto_sid_{id(self)}"
        self.tmp_dir.mkdir(exist_ok=True, parents=True)
        # 清理可能残留的 session 文件
        sf = scoped_session_file(self.tmp_dir)
        if sf.exists():
            sf.unlink()

    def tearDown(self):
        import shutil
        sf = scoped_session_file(self.tmp_dir)
        if sf.exists():
            sf.unlink()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_auto_uses_file_when_exists(self):
        """文件存在且非空时使用文件内容作为 SID。"""
        _write_dtask(self.tmp_dir, [{"id": 1, "title": "T", "status": "InSpec"}])
        scoped_session_file(self.tmp_dir).write_text("real-session-abc-123\n", encoding="utf-8")
        rc, out, _ = self._run()
        assert rc == 0
        payload = json.loads(out)
        assert payload["status"] == "claimed"
        # 验证 dtask-state.json 中写入了真实 SID
        state = json.load(open(self.tmp_dir / ".diwu" / "dtask-state.json"))
        sid = state["task_sessions"]["1"]["session_id"]
        assert sid == "real-session-abc-123"

    def test_auto_falls_back_to_env_var_when_no_file(self):
        """文件不存在时尝试环境变量。"""
        _write_dtask(self.tmp_dir, [{"id": 1, "title": "T", "status": "InSpec"}])
        rc, out, _ = self._run(["--session-id", "auto"], env={"CLAUDE_SESSION_ID": "env-sid-xyz"})
        assert rc == 0
        payload = json.loads(out)
        state = json.load(open(self.tmp_dir / ".diwu" / "dtask-state.json"))
        assert state["task_sessions"]["1"]["session_id"] == "env-sid-xyz"

    def test_auto_falls_back_to_date_when_neither_file_nor_env(self):
        """文件和环境变量都不存在时 fallback 到 drun<date> 格式。"""
        _write_dtask(self.tmp_dir, [{"id": 1, "title": "T", "status": "InSpec"}])
        rc, out, err = self._run(["--session-id", "auto"], env={})
        assert rc == 0
        payload = json.loads(out)
        state = json.load(open(self.tmp_dir / ".diwu" / "dtask-state.json"))
        sid = state["task_sessions"]["1"]["session_id"]
        assert sid.startswith("drun-")  # fallback 格式
        assert "[SESSION_ID]" in err  # 应有警告输出

    def test_explicit_session_id_overrides_auto(self):
        """显式传入 --session-id 时忽略 auto 解析，直接使用传入值。"""
        _write_dtask(self.tmp_dir, [{"id": 1, "title": "T", "status": "InSpec"}])
        scoped_session_file(self.tmp_dir).write_text("file-sid-should-ignore\n", encoding="utf-8")
        rc, out, _ = self._run(["--session-id", "explicit-sid-999"])
        assert rc == 0
        state = json.load(open(self.tmp_dir / ".diwu" / "dtask-state.json"))
        assert state["task_sessions"]["1"]["session_id"] == "explicit-sid-999"

    def test_env_overrides_file_when_both_exist(self):
        """env 和文件同时存在时，CLAUDE_SESSION_ID 优先于文件内容（防跨会话污染）。"""
        _write_dtask(self.tmp_dir, [{"id": 1, "title": "T", "status": "InSpec"}])
        scoped_session_file(self.tmp_dir).write_text("other-session-from-file\n", encoding="utf-8")
        rc, out, _ = self._run(["--session-id", "auto"], env={"CLAUDE_SESSION_ID": "current-session-env"})
        assert rc == 0
        state = json.load(open(self.tmp_dir / ".diwu" / "dtask-state.json"))
        assert state["task_sessions"]["1"]["session_id"] == "current-session-env"

    def test_adopt_also_supports_auto(self):
        """adopt 命令同样支持 auto 解析。"""
        _write_dtask(self.tmp_dir, [{"id": 1, "title": "T", "status": "InProgress"}])
        scoped_session_file(self.tmp_dir).write_text("adopt-sid-file\n", encoding="utf-8")
        # 先 claim 用一个假 SID
        self._run(["--session-id", "old-sid"])
        # adopt 用 auto → 应读取文件
        rc, out, _ = self._run_script("adopt", ["--session-id", "auto"])
        assert rc == 0
        state = json.load(open(self.tmp_dir / ".diwu" / "dtask-state.json"))
        assert state["task_sessions"]["1"]["session_id"] == "adopt-sid-file"

    def _run_script(self, command, extra_args=None, env=None):
        cmd = ["dtask_transition.py", command, "--task-id", "1", "--cwd", str(self.tmp_dir)]
        if extra_args:
            cmd.extend(extra_args)
        return run_script(*cmd, env=env)


# ---------------------------------------------------------------------------
# pending_recording 机制测试
# ---------------------------------------------------------------------------


def test_release_writes_pending_recording(tmp_project_dir):
    """release done 后 dtask-state.json 含 pending_recording 标记。"""
    _write_dtask(tmp_project_dir, [{"id": 1, "title": "a", "status": "InSpec"}])
    rc, out, _ = run_script(
        "dtask_transition.py",
        "claim", "--task-id", "1", "--session-id", "sid-1",
        "--cwd", str(tmp_project_dir),
    )
    assert rc == 0
    rc, out, _ = run_script(
        "dtask_transition.py",
        "release", "--task-id", "1", "--to", "done",
        "--session-id", "sid-1",
        "--cwd", str(tmp_project_dir),
    )
    assert rc == 0
    state = _read_runtime(tmp_project_dir)
    pr = state.get("pending_recording")
    assert pr is not None
    assert pr["task_id"] == 1
    assert pr["target_status"] == "Done"
    assert pr["session_id"] == "sid-1"
    assert "released_at" in pr


def test_release_overwrites_existing_pending_recording(tmp_project_dir):
    """多次 release 幂等覆盖，标记只指向最后一次 release 的任务。"""
    _write_dtask(tmp_project_dir, [
        {"id": 1, "title": "a", "status": "InSpec"},
        {"id": 2, "title": "b", "status": "InSpec"},
    ])
    # release task1
    for tid in (1, 2):
        rc, _, _ = run_script(
            "dtask_transition.py",
            "claim", "--task-id", str(tid), "--session-id", f"sid-{tid}",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        rc, _, _ = run_script(
            "dtask_transition.py",
            "release", "--task-id", str(tid), "--to", "done",
            "--session-id", f"sid-{tid}",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
    state = _read_runtime(tmp_project_dir)
    pr = state.get("pending_recording")
    assert pr is not None
    assert pr["task_id"] == 2  # 只指向 task2


def test_release_failure_does_not_write_mark(tmp_project_dir):
    """owner mismatch 时 release 失败，不写入 pending_recording 标记。"""
    _write_dtask(tmp_project_dir, [{"id": 1, "title": "a", "status": "InProgress"}])
    runtime = {
        "version": 1,
        "task_sessions": {
            "1": {"session_id": "sid-old", "started_at": "2026-04-30T12:00:00Z"}
        },
        "dloop": None,
    }
    (tmp_project_dir / ".diwu" / "dtask-state.json").write_text(
        json.dumps(runtime, ensure_ascii=False, indent=2)
    )
    rc, out, _ = run_script(
        "dtask_transition.py",
        "release", "--task-id", "1", "--to", "done",
        "--session-id", "sid-new",  # 不匹配 owner
        "--cwd", str(tmp_project_dir),
    )
    assert rc == 1
    state = _read_runtime(tmp_project_dir)
    assert state.get("pending_recording") is None


@pytest.mark.parametrize("target_cli,target_status", [
    ("inreview", "InReview"),
    ("cancelled", "Cancelled"),
    ("inspec", "InSpec"),
])
def test_non_done_release_also_writes_mark(tmp_project_dir, target_cli, target_status):
    """InReview/Cancelled/InSpec 目标的 release 也写入 pending_recording 标记。"""
    _write_dtask(tmp_project_dir, [{"id": 1, "title": "a", "status": "InSpec"}])
    rc, _, _ = run_script(
        "dtask_transition.py",
        "claim", "--task-id", "1", "--session-id", "sid-1",
        "--cwd", str(tmp_project_dir),
    )
    assert rc == 0
    rc, out, _ = run_script(
        "dtask_transition.py",
        "release", "--task-id", "1", "--to", target_cli,
        "--session-id", "sid-1",
        "--cwd", str(tmp_project_dir),
    )
    assert rc == 0
    state = _read_runtime(tmp_project_dir)
    pr = state.get("pending_recording")
    assert pr is not None
    assert pr["task_id"] == 1
    assert pr["target_status"] == target_status


def test_show_pending_cli_returns_marker(tmp_project_dir):
    """show-pending 子命令：有标记时返回 has_pending_recording 且字段完整。"""
    _write_dtask(tmp_project_dir, [{"id": 1, "title": "a", "status": "InSpec"}])
    run_script(
        "dtask_transition.py",
        "claim", "--task-id", "1", "--session-id", "sid-x",
        "--cwd", str(tmp_project_dir),
    )
    run_script(
        "dtask_transition.py",
        "release", "--task-id", "1", "--to", "done",
        "--session-id", "sid-x",
        "--cwd", str(tmp_project_dir),
    )
    rc, out, _ = run_script(
        "dtask_transition.py",
        "show-pending", "--cwd", str(tmp_project_dir),
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["status"] == "has_pending_recording"
    pr = payload["pending_recording"]
    assert pr["task_id"] == 1
    assert pr["target_status"] == "Done"
    assert pr["session_id"] == "sid-x"


def test_show_pending_cli_no_marker(tmp_project_dir):
    """无标记时 show-pending 返回 no_pending_recording。"""
    _write_dtask(tmp_project_dir, [{"id": 1, "title": "a", "status": "InSpec"}])
    rc, out, _ = run_script(
        "dtask_transition.py",
        "show-pending", "--cwd", str(tmp_project_dir),
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["status"] == "no_pending_recording"


def test_clear_pending_cli(tmp_project_dir):
    """clear-pending 子命令：清除标记后再 show-pending 确认已清空。"""
    _write_dtask(tmp_project_dir, [{"id": 1, "title": "a", "status": "InSpec"}])
    run_script(
        "dtask_transition.py",
        "claim", "--task-id", "1", "--session-id", "sid-c",
        "--cwd", str(tmp_project_dir),
    )
    run_script(
        "dtask_transition.py",
        "release", "--task-id", "1", "--to", "done",
        "--session-id", "sid-c",
        "--cwd", str(tmp_project_dir),
    )
    # clear-pending
    rc, out, _ = run_script(
        "dtask_transition.py",
        "clear-pending", "--cwd", str(tmp_project_dir),
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["status"] == "cleared"

    # 再次 show-pending 确认已清空
    rc, out, _ = run_script(
        "dtask_transition.py",
        "show-pending", "--cwd", str(tmp_project_dir),
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["status"] == "no_pending_recording"


def test_show_pending_triggers_self_heal(tmp_project_dir):
    """show-pending 走 sync 触发 self-heal：stale 标记（指向不存在 task）被自动清除。"""
    _write_dtask(tmp_project_dir, [{"id": 1, "title": "a", "status": "InSpec"}])
    # 手写含 stale pending_recording 的 state
    stale_state = {
        "version": 1,
        "task_sessions": {},
        "dloop": None,
        "pending_recording": {
            "task_id": 999,
            "target_status": "Done",
            "released_at": "2026-05-01T00:00:00Z",
            "session_id": "sid-stale",
        },
    }
    (tmp_project_dir / ".diwu" / "dtask-state.json").write_text(
        json.dumps(stale_state, ensure_ascii=False, indent=2)
    )
    rc, out, _ = run_script(
        "dtask_transition.py",
        "show-pending", "--cwd", str(tmp_project_dir),
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["status"] == "no_pending_recording"
    # 确认磁盘上的 state 也已被 self-heal 清除
    state = _read_runtime(tmp_project_dir)
    assert state.get("pending_recording") is None
