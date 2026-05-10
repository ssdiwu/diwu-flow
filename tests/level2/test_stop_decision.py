"""L2 tests for stop_decision.py — continuous_mode decision tree."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'hooks', 'scripts'))
from stop_decision import decide, decide_cron_mode, format_task, hook_session_id
import tempfile as _tmpmod

_TEST_CWD = None
RUNTIME_STATE_NAME = ".diwu/dtask-state.json"


def _make_dtask_for_test(tasks, tmp_path):
    """Write dtask.json for test (local to this file)."""
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.json").write_text(
        json.dumps({"tasks": tasks}), encoding="utf-8"
    )


def _make_dsettings_for_test(tmp_path, **overrides):
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    settings = {"review_limit": 5}
    settings.update(overrides)
    (diwu / "dsettings.json").write_text(
        json.dumps(settings), encoding="utf-8"
    )


def _make_runtime_state_for_test(tmp_path, *, dloop=None, task_sessions=None):
    (tmp_path / ".diwu").mkdir(exist_ok=True)
    state = {
        "version": 1,
        "task_sessions": task_sessions or {},
        "dloop": dloop,
    }
    (tmp_path / RUNTIME_STATE_NAME).write_text(json.dumps(state), encoding="utf-8")


def _run_stop_decision_for_test(tmp_path, env_overrides=None, **kwargs):
    """Run stop_decision.py with given tmp_path and optional stdin data."""
    _stop_script = Path(__file__).parent.parent.parent / "hooks" / "scripts" / "stop_decision.py"
    cmd = [sys.executable, str(_stop_script), "--task-json",
          str(tmp_path / ".diwu" / "dtask.json")]
    stdin_data = json.dumps(kwargs) if kwargs else ""
    env = os.environ.copy()
    env["DIWU_SILENT"] = "1"
    env.pop("CLAUDE_SESSION_ID", None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        cmd, input=stdin_data, capture_output=True, text=True,
        cwd=str(tmp_path), env=env,
    )


def _get_test_cwd():
    global _TEST_CWD
    if _TEST_CWD is None:
        _TEST_CWD = _tmpmod.mkdtemp()
    return _TEST_CWD


class TestFormatTask(unittest.TestCase):
    """Test format_task helper."""

    def test_format_contains_task_info(self):
        t = {'id': 5, 'title': 'Do X', 'description': 'desc',
             'acceptance': ['G W T'], 'steps': ['s1']}
        result = format_task('prefix:', t)
        self.assertIn('Task#5', result)
        self.assertIn('Do X', result)
        self.assertIn('desc', result)

    def test_format_contains_acceptance_and_steps(self):
        t = {'id': 1, 'title': 'T', 'description': '',
             'acceptance': ['Given A When B Then C'],
             'steps': ['step one']}
        result = format_task('go:', t)
        self.assertIn('Given A When B Then C', result)
        self.assertIn('step one', result)


class TestHookSessionId(unittest.TestCase):
    """Stop hook session id normalization."""

    def test_prefers_session_id(self):
        event = {"session_id": "snake", "sessionId": "camel"}
        self.assertEqual(hook_session_id(event), "snake")

    def test_accepts_sessionId(self):
        event = {"sessionId": "camel-only"}
        self.assertEqual(hook_session_id(event), "camel-only")


class TestDecideInProgress(unittest.TestCase):
    """Test decide() when InProgress task exists."""

    def test_inprogress_returns_continue(self):
        tasks = [{'id': 1, 'title': 'Active', 'status': 'InProgress',
                  'description': '', 'acceptance': [], 'steps': []}]
        settings = {'continuous_mode': True}
        runtime_state = {
            'version': 1,
            'task_sessions': {
                '1': {'session_id': 'session-a', 'started_at': '2026-04-30T12:00:00Z'}
            },
            'dloop': None,
        }
        should_continue, output = decide(
            tasks, settings, {}, '.diwu/dtask.json', _get_test_cwd(), [], None,
            runtime_state=runtime_state, session_id='session-a'
        )
        self.assertTrue(should_continue)
        self.assertEqual(output.get('decision'), 'block')
        self.assertIn('Active', output.get('reason', ''))

    def test_inprogress_without_owner_returns_invalid(self):
        tasks = [{'id': 1, 'title': 'Active', 'status': 'InProgress',
                  'description': '', 'acceptance': [], 'steps': []}]
        should_continue, output = decide(
            tasks, {'continuous_mode': True}, {}, '.diwu/dtask.json', _get_test_cwd(), [], None,
            runtime_state={'version': 1, 'task_sessions': {}, 'dloop': None}, session_id='session-a'
        )
        self.assertFalse(should_continue)
        # missing_owner 不再返回非法 decision 值（旧行为返回 {"decision": "missing_owner"}），
        # 而是返回空 dict + stderr 输出 STOP_HINT 引导 AI 执行 claim/adopt
        self.assertNotIn('decision', output)


class TestDecideInReview(unittest.TestCase):
    """Test decide() when only InReview tasks exist."""

    def test_inreview_within_limit_advances(self):
        """Default mode: InReview + InSpec but no InProgress -> allow stop."""
        tasks = [{'id': 1, 'status': 'InReview', 'title': 'R',
                  'description': '', 'acceptance': [], 'steps': []},
                 {'id': 2, 'status': 'InSpec', 'title': 'Next',
                  'description': '', 'acceptance': [], 'steps': [], 'blocked_by': []}]
        settings = {'continuous_mode': True, 'review_limit': 5}
        data = {'review_used': 0}
        # New behavior: no dloop-state -> default mode -> allow stop
        should_continue, output = decide(tasks, settings, data, '.diwu/t.json', _get_test_cwd(), [], None)
        self.assertFalse(should_continue)

    def test_inreview_at_limit_stops(self):
        tasks = [{'id': 1, 'status': 'InReview', 'title': 'R',
                  'description': '', 'acceptance': [], 'steps': []}]
        settings = {'continuous_mode': True, 'review_limit': 5}
        data = {'review_used': 5}  # at limit
        # Patch notify to avoid /dev/tty OSError in test env
        import stop_decision
        _orig_notify = stop_decision.notify
        stop_decision.notify = lambda msg: None
        try:
            should_continue, output = decide(tasks, settings, data, '.diwu/t.json', _get_test_cwd(), [], None)
        finally:
            stop_decision.notify = _orig_notify
        self.assertFalse(should_continue)


class TestDecideInSpec(unittest.TestCase):
    """Test decide() when InSpec tasks available."""

    def test_inspec_auto_advances(self):
        """Default mode: InSpec but no InProgress -> allow stop (no auto-continue)."""
        tasks = [{'id': 3, 'status': 'InSpec', 'title': 'Ready',
                  'description': '', 'acceptance': [], 'steps': [], 'blocked_by': []}]
        settings = {'continuous_mode': True}
        # New behavior: no dloop-state -> default mode -> allows stop
        should_continue, output = decide(tasks, settings, {}, '.diwu/t.json', _get_test_cwd(), [], None)
        self.assertFalse(should_continue)
        self.assertEqual(output, {})


class TestDecideEmpty(unittest.TestCase):
    """Test decide() when no active tasks."""

    def test_no_tasks_returns_stop(self):
        settings = {'continuous_mode': True}
        should_continue, output = decide([], settings, {}, '.diwu/t.json', _get_test_cwd(), [], None)
        self.assertFalse(should_continue)
        self.assertEqual(output, {})


class TestDecideContinuousModeOff(unittest.TestCase):
    """Test decide() with continuous_mode=False."""

    def test_inspec_continuous_off_returns_summary(self):
        """Default mode: InSpec + no InProgress -> allow stop (no auto-continue)."""
        tasks = [{'id': 1, 'status': 'InSpec', 'title': 'T',
                  'description': '', 'acceptance': [], 'steps': [], 'blocked_by': []},
                 {'id': 99, 'status': 'Done', 'title': 'Done1',
                  'description': '', 'acceptance': [], 'steps': []}]
        settings = {'continuous_mode': False}
        # New behavior: default mode allows stop when no InProgress task
        should_continue, output = decide(tasks, settings, {}, '.diwu/t.json', _get_test_cwd(), [], None)
        self.assertFalse(should_continue)
        self.assertEqual(output, {})  # No block decision = allow stop


# ---------------------------------------------------------------------------
# pending_recording 强制门控测试
# ---------------------------------------------------------------------------

from stop_decision import (
    _check_diu_dirty,
    _check_pending_recording_gate,
    _resolve_stop_session_id,
    decide_default_mode,
)
from session_scope import scoped_session_file


class _PendingRecordingTestBase(unittest.TestCase):
    """共享 setUp：创建临时目录 + git repo + .diwu/ 基础结构。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cwd = self.tmpdir
        # 初始化 git repo（_check_diu_dirty 依赖 git status）
        subprocess.run(["git", "init"], cwd=self.cwd, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=self.cwd, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"],
            cwd=self.cwd, capture_output=True,
        )
        # 初始 commit（让 git status 有 baseline）
        init_file = os.path.join(self.cwd, ".gitkeep")
        with open(init_file, "w") as f:
            f.write("init")
        subprocess.run(
            ["git", "add", "."], cwd=self.cwd, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=self.cwd, capture_output=True,
        )
        # 创建 .diwu/ 目录
        _diwu_path = os.path.join(self.cwd, ".diwu")
        os.makedirs(_diwu_path, exist_ok=True)
        # 写入空 dtask-state.json
        state_path = os.path.join(_diwu_path, "dtask-state.json")
        with open(state_path, "w") as f:
            json.dump({"version": 1}, f)
        # 写入空 dtask.json（基线文件，commit 后修改才变 dirty）
        task_path = os.path.join(_diwu_path, "dtask.json")
        with open(task_path, "w") as f:
            json.dump({"tasks": []}, f)
        # 第二次 commit：将 .diwu/ 基线文件纳入 git 追踪
        # （否则后续测试中这些文件永远是 untracked → _check_diu_dirty 误报 dirty）
        subprocess.run(
            ["git", "add", "."], cwd=self.cwd, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "baseline .diwu"],
            cwd=self.cwd, capture_output=True,
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_state(self, **overrides):
        """写入 dtask-state.json，默认保留 version=1。"""
        state = {"version": 1}
        state.update(overrides)
        path = os.path.join(self.cwd, ".diwu", "dtask-state.json")
        with open(path, "w") as f:
            json.dump(state, f, ensure_ascii=False)

    def _touch_file(self, relpath):
        """创建/修改文件并记录到 git index（不 commit）→ 变为 dirty。"""
        full = os.path.join(self.cwd, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write("modified")


class TestPendingRecordingGate(_PendingRecordingTestBase):
    """_check_pending_recording_gate 单元测试。"""

    def test_no_marker_returns_empty(self):
        """无 pending_recording → ("", "")。"""
        level, hint = _check_pending_recording_gate(self.cwd, "sess-001")
        self.assertEqual(level, "")
        self.assertEqual(hint, "")

    def test_null_marker_returns_empty(self):
        """pending_recording=null → ("", ")。"""
        self._write_state(pending_recording=None)
        level, hint = _check_pending_recording_gate(self.cwd, "sess-001")
        self.assertEqual(level, "")
        self.assertEqual(hint, "")

    def test_own_session_with_diu_dirty_blocks(self):
        """本次 session + .diwu/ dirty + ≤30min → block，hint 含 /drec。"""
        from datetime import datetime, timezone as _tz
        now_iso = datetime.now(_tz.utc).isoformat()
        self._write_state(pending_recording={
            "task_id": 7,
            "target_status": "Done",
            "session_id": "sess-own",
            "released_at": now_iso,
        })
        # 制造 .diwu/ dirty
        self._touch_file(".diwu/dtask.json")

        level, hint = _check_pending_recording_gate(self.cwd, "sess-own")
        self.assertEqual(level, "block")
        self.assertIn("/drec", hint)

    def test_own_session_diu_clean_no_block(self):
        """本次 session + .diwu/ 干净 → ("", ") 不阻塞。"""
        from datetime import datetime, timezone as _tz
        now_iso = datetime.now(_tz.utc).isoformat()
        self._write_state(pending_recording={
            "task_id": 7,
            "target_status": "Done",
            "session_id": "sess-own",
            "released_at": now_iso,
        })
        # _write_state 修改了 dtask-state.json，需 commit 回归干净
        subprocess.run(
            ["git", "add", ".diwu/dtask-state.json"],
            cwd=self.cwd, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "state updated"],
            cwd=self.cwd, capture_output=True,
        )

        level, hint = _check_pending_recording_gate(self.cwd, "sess-own")
        self.assertEqual(level, "")
        self.assertEqual(hint, "")

    def test_stale_marker_downgrades_to_warn(self):
        """>30min 标记 → warn，hint 含"过期"。"""
        from datetime import datetime, timezone as _tz, timedelta
        stale_time = (datetime.now(_tz.utc) - timedelta(minutes=35)).isoformat()
        self._write_state(pending_recording={
            "task_id": 3,
            "target_status": "InReview",
            "session_id": "sess-old",
            "released_at": stale_time,
        })
        self._touch_file(".diwu/dtask.json")

        level, hint = _check_pending_recording_gate(self.cwd, "sess-old")
        self.assertEqual(level, "warn")
        self.assertIn("过期", hint)

    def test_other_session_silent(self):
        """非 owner session → 完全静默（/drec 需要任务上下文，非 owner 不可能拥有）。"""
        from datetime import datetime, timezone as _tz
        now_iso = datetime.now(_tz.utc).isoformat()
        self._write_state(pending_recording={
            "task_id": 5,
            "target_status": "Done",
            "session_id": "sess-other",
            "released_at": now_iso,
        })
        self._touch_file(".diwu/dtask.json")

        level, hint = _check_pending_recording_gate(self.cwd, "sess-mine")
        self.assertEqual(level, "")
        self.assertEqual(hint, "")

    def test_corrupted_state_file_safe(self):
        """损坏的 JSON → ("", "") 安全降级。"""
        state_path = os.path.join(self.cwd, ".diwu", "dtask-state.json")
        with open(state_path, "w") as f:
            f.write("{broken json!!!")

        level, hint = _check_pending_recording_gate(self.cwd, "sess-001")
        self.assertEqual(level, "")
        self.assertEqual(hint, "")


class TestDiuDirty(_PendingRecordingTestBase):
    """_check_diu_dirty 独立测试。"""

    def test_diu_dirty_detects_dtask_json_change(self):
        """修改 .diwu/dtask.json 后返回 (True, [...])。"""
        self._touch_file(".diwu/dtask.json")
        has_dirty, files = _check_diu_dirty(self.cwd)
        self.assertTrue(has_dirty)
        self.assertTrue(any("dtask.json" in f for f in files))

    def test_diu_dirty_detects_recording_file_change(self):
        """修改 recording/ 下文件后返回 (True, [...])。"""
        self._touch_file(".diwu/recording/session-test.md")
        has_dirty, files = _check_diu_dirty(self.cwd)
        self.assertTrue(has_dirty)
        self.assertTrue(any("recording" in f for f in files))

    def test_diu_dirty_ignores_code_changes(self):
        """只修改代码文件（非 .diwu/）→ (False, [])。"""
        self._touch_file("src/main.py")
        has_dirty, files = _check_diu_dirty(self.cwd)
        self.assertFalse(has_dirty)
        self.assertEqual(files, [])


class TestResolveStopSessionId(unittest.TestCase):
    """_resolve_stop_session_id 独立测试。"""

    def test_resolves_from_event_id(self):
        """有 event_session_id 时直接返回。"""
        result = _resolve_stop_session_id("event-sid-123", "/tmp/fake")
        self.assertEqual(result, "event-sid-123")

    def test_falls_back_to_env_var(self):
        """空 event 但有 CLAUDE_SESSION_ID env 时返回 env 值。"""
        old_val = os.environ.get("CLAUDE_SESSION_ID")
        try:
            os.environ["CLAUDE_SESSION_ID"] = "env-session-abc"
            result = _resolve_stop_session_id("", "/tmp/fake")
            self.assertEqual(result, "env-session-abc")
        finally:
            if old_val is None:
                os.environ.pop("CLAUDE_SESSION_ID", None)
            else:
                os.environ["CLAUDE_SESSION_ID"] = old_val

    def test_falls_back_to_session_file(self):
        """空 event/env 但 scoped session 文件存在时返回文件内容。"""
        cwd = tempfile.mkdtemp()
        session_file = scoped_session_file(cwd)
        old_val = os.environ.get("CLAUDE_SESSION_ID")
        try:
            os.environ.pop("CLAUDE_SESSION_ID", None)
            session_file.write_text("file-session-xyz\n", encoding="utf-8")
            result = _resolve_stop_session_id("", cwd)
            self.assertEqual(result, "file-session-xyz")
        finally:
            if old_val is not None:
                os.environ["CLAUDE_SESSION_ID"] = old_val
            session_file.unlink(missing_ok=True)
            import shutil
            shutil.rmtree(cwd, ignore_errors=True)


class TestPendingRecordingIntegration(_PendingRecordingTestBase):
    """pending_recording 集成测试：完整 decide_default_mode / decide_loop_mode 调用链路。"""

    def test_default_mode_own_session_block_integration(self):
        """完整链路：带标记 state + .diwu/ dirty + 同 session_id → block。"""
        from datetime import datetime, timezone as _tz
        now_iso = datetime.now(_tz.utc).isoformat()
        self._write_state(
            version=1,
            task_sessions={},
            dloop=None,
            pending_recording={
                "task_id": 42,
                "target_status": "Done",
                "session_id": "integ-sess",
                "released_at": now_iso,
            },
        )
        self._touch_file(".diwu/dtask.json")

        should_continue, output = decide_default_mode(
            tasks=[],
            settings={"continuous_mode": True},
            data={},
            task_json_path=os.path.join(self.cwd, ".diwu", "dtask.json"),
            additional_prompts=[],
            runtime_state={"version": 1, "task_sessions": {}, "dloop": None},
            session_id="integ-sess",
            cwd=self.cwd,
        )
        self.assertTrue(should_continue)
        self.assertEqual(output.get("decision"), "block")
        self.assertIn("PENDING_REC", output.get("reason", ""))

    def test_default_mode_missing_session_fallback(self):
        """event 缺 session_id 但 env 有值 → 解析后仍能匹配标记的 session_id → block。"""
        from datetime import datetime, timezone as _tz
        now_iso = datetime.now(_tz.utc).isoformat()
        marker_sid = "env-fallback-sess"
        self._write_state(
            version=1,
            task_sessions={},
            dloop=None,
            pending_recording={
                "task_id": 10,
                "target_status": "Done",
                "session_id": marker_sid,
                "released_at": now_iso,
            },
        )
        self._touch_file(".diwu/dtask.json")

        old_env = os.environ.get("CLAUDE_SESSION_ID")
        try:
            os.environ["CLAUDE_SESSION_ID"] = marker_sid
            should_continue, output = decide_default_mode(
                tasks=[],
                settings={"continuous_mode": True},
                data={},
                task_json_path=os.path.join(self.cwd, ".diwu", "dtask.json"),
                additional_prompts=[],
                runtime_state={"version": 1, "task_sessions": {}, "dloop": None},
                session_id="",  # 空 → fallback 到 env
                cwd=self.cwd,
            )
        finally:
            if old_env is None:
                os.environ.pop("CLAUDE_SESSION_ID", None)
            else:
                os.environ["CLAUDE_SESSION_ID"] = old_env

        self.assertTrue(should_continue)
        self.assertEqual(output.get("decision"), "block")
        self.assertIn("PENDING_REC", output.get("reason", ""))



# ── Cron mode tests ────────────────────────────────────────────

class TestCronModeStopDecision(_PendingRecordingTestBase):
    """decide_cron_mode() 专项测试。"""

    def _cron_loop_state(self, **overrides):
        base = {
            "active": True,
            "mode": "cron",
            "session_id": "cron-sid-001",
            "started_at": "2026-05-09T00:00:00Z",
            "completed_task_ids": [],
            "current_iteration": 0,
            "max_tasks": 0,
            "cron_job_id": "test-cron-job-id",
        }
        base.update(overrides)
        return base

    def test_cron_mode_no_stop_allows_session_end(self):
        """cron 模式 + 未命中停止条件 → 返回 (False, {}) 允许 session 结束。"""
        loop_state = self._cron_loop_state(completed_task_ids=[1])
        should_continue, output = decide_cron_mode(
            tasks=[
                {"id": 1, "status": "Done", "title": "Done T", "description": "",
                 "acceptance": [], "steps": []},
                {"id": 2, "status": "InSpec", "title": "Next T", "description": "",
                 "acceptance": [], "steps": [], "blocked_by": []},
            ],
            settings={},
            data={},
            task_json_path=os.path.join(self.cwd, ".diwu", "dtask.json"),
            loop_state=loop_state,
            cwd=self.cwd,
            additional_prompts=[],
            runtime_state={"version": 1, "task_sessions": {}, "dloop": loop_state},
        )
        self.assertFalse(should_continue)
        self.assertEqual(output, {})

    def test_cron_mode_max_tasks_triggers_stop(self):
        """cron 模式 + completed >= max_tasks → 停止并清理 dloop state。"""
        loop_state = self._cron_loop_state(
            completed_task_ids=[1, 2, 3], current_iteration=3, max_tasks=3
        )
        runtime = {"version": 1, "task_sessions": {}, "dloop": loop_state}

        should_continue, output = decide_cron_mode(
            tasks=[
                {"id": i, "status": "Done" if i <= 3 else "InSpec",
                 "title": f"T{i}", "description": "", "acceptance": [], "steps": []}
                for i in range(1, 5)
            ],
            settings={},
            data={},
            task_json_path=os.path.join(self.cwd, ".diwu", "dtask.json"),
            loop_state=loop_state,
            cwd=self.cwd,
            additional_prompts=[],
            runtime_state=runtime,
        )
        self.assertFalse(should_continue)
        self.assertEqual(output, {})
        # 验证 dloop 已清理
        state_file = os.path.join(self.cwd, ".diwu", "dtask-state.json")
        if os.path.exists(state_file):
            saved = json.loads(open(state_file).read())
            self.assertIsNone(saved.get("dloop"))

    def test_cron_mode_no_executable_tasks_stops(self):
        """cron 模式 + 无可执行任务 → 停止。"""
        loop_state = self._cron_loop_state(completed_task_ids=[1], current_iteration=1)

        should_continue, output = decide_cron_mode(
            tasks=[{"id": 1, "status": "Done", "title": "T", "description": "",
                   "acceptance": [], "steps": []}],
            settings={}, data={},
            task_json_path=os.path.join(self.cwd, ".diwu", "dtask.json"),
            loop_state=loop_state, cwd=self.cwd, additional_prompts=[],
            runtime_state={"version": 1, "task_sessions": {}, "dloop": loop_state},
        )
        self.assertFalse(should_continue)

    def test_cron_mode_skips_session_id_binding(self):
        """cron 模式不检查 session_id 匹配（无 session 绑定逻辑）。

        集成测试：通过 main() 入口传入 cron mode 的 loop_state，
        验证即使 session_id 不匹配也不影响 cron 判断流程。"""
        tasks = [{"id": 1, "title": "CT", "status": "InSpec", "blocked_by": [],
                  "acceptance": [], "steps": [], "description": ""}]
        _make_dtask_for_test(tasks, Path(self.cwd))
        _make_dsettings_for_test(Path(self.cwd))
        _make_runtime_state_for_test(
            Path(self.cwd),
            dloop=self._cron_loop_state(session_id="original-cron-sid"),
        )

        # 用不同的 session_id 调用 — cron 模式不检查 session_id
        result = _run_stop_decision_for_test(
            Path(self.cwd),
            session_id="different-cron-sid",
            cwd=self.cwd,
        )
        assert result.returncode == 0
        # cron 模式正常执行，进入 decide_cron_mode 判断

    def test_cron_mode_pending_rec_silent_for_new_session(self):
        """cron 模式：新 iteration（新 SID）遇到旧 PENDING_REC → 静默。

        这是审查修正 #2 的验证：现有 PENDING_REC 门控逻辑在 cron 模式下自然正确，
        因为每次 iteration 是全新 session（新 SID），非 owner 直接返回 ("", "")。"""
        from datetime import datetime, timezone as _tz
        now_iso = datetime.now(_tz.utc).isoformat()
        # 上一个 cron iteration 留下的 PENDING_REC 标记
        self._write_state(
            version=1, task_sessions={}, dloop=None,
            pending_recording={
                "task_id": 7, "target_status": "Done",
                "session_id": "previous-cron-sid",  # 属于上一个 iteration
                "released_at": now_iso,
            },
        )
        self._touch_file(".diwu/dtask.json")

        loop_state = self._cron_loop_state()
        should_continue, output = decide_cron_mode(
            tasks=[{"id": 8, "status": "InSpec", "title": "New T", "description": "",
                  "acceptance": [], "steps": [], "blocked_by": []}],
            settings={}, data={},
            task_json_path=os.path.join(self.cwd, ".diwu", "dtask.json"),
            loop_state=loop_state, cwd=self.cwd, additional_prompts=[],
            runtime_state={"version": 1, "task_sessions": {}, "dloop": loop_state},
        )
        # decide_cron_mode 不检查 PENDING_REC（只做停止条件判断）
        # 但即使检查，当前 session_id ≠ previous-cron-sid → 静默
        self.assertFalse(should_continue)

    def test_cron_mode_terminal_outputs_delete_instruction(self):
        """cron 模式终止时：stdout 为空（框架协议层），stderr 含 /dstop 文本提示。

        内部指令（cron_action）不应泄漏到 hook stdout——那是 dloop.py stop() 的职责。"""
        tasks = [{"id": 1, "title": "CT", "status": "Done", "blocked_by": [],
                  "acceptance": [], "steps": [], "description": ""}]
        _make_dtask_for_test(tasks, Path(self.cwd))
        _make_dsettings_for_test(Path(self.cwd))
        # max_tasks=1, completed=[1] → 命中终止条件
        _make_runtime_state_for_test(
            Path(self.cwd),
            dloop=self._cron_loop_state(
                session_id="cron-sid",
                completed_task_ids=[1],
                current_iteration=1,
                max_tasks=1,
            ),
        )

        result = _run_stop_decision_for_test(Path(self.cwd), cwd=self.cwd)
        assert result.returncode == 0
        # stdout 不含内部指令字段（cron_action 是 dloop.py 的职责）
        if result.stdout.strip():
            output = json.loads(result.stdout)
            assert "cron_action" not in output, "内部指令不应泄漏到 hook stdout"
        # stderr 为空（已移除 stderr 输出）
        assert result.stderr == ""


def test_stop_decision_cron_mode_dispatch(tmp_path):
    """集成测试：decide() 正确分发到 decide_cron_mode()。"""
    tasks = [
        {"id": 1, "status": "Done", "title": "D", "description": "",
         "acceptance": [], "steps": []},
        {"id": 2, "status": "InSpec", "title": "N", "description": "",
         "acceptance": [], "steps": [], "blocked_by": []},
    ]
    _make_dtask_for_test(tasks, tmp_path)
    _make_cron_dloop_state(tmp_path)  # 使用上面定义的 helper

    result = _run_stop_decision_for_test(tmp_path, session_id="any-sid", cwd=str(tmp_path))
    # cron 模式：未命中停止条件 → 返回空 stdout（allow stop / no block decision）
    assert result.returncode == 0
    # 不应返回 block decision（session 模式才会 block 续跑）
    if result.stdout.strip():
        output = json.loads(result.stdout)
        # 如果有输出，不应是续跑指令
        assert "请继续执行 /drun" not in output.get("reason", "")


def _make_cron_dloop_state(tmp_path, **overrides):
    """Create cron-mode dloop state for integration tests."""
    base = {
        "active": True,
        "mode": "cron",
        "session_id": "cron-int-sid",
        "started_at": "2026-05-09T00:00:00Z",
        "completed_task_ids": [],
        "initial_done_ids": [],
        "current_iteration": 0,
        "max_tasks": 0,
        "stopped_at": None,
        "stop_reason": None,
        "cron_job_id": "int-job-999",
    }
    base.update(overrides)
    existing = {"task_sessions": {}}
    if (tmp_path / RUNTIME_STATE_NAME).exists():
        existing = json.loads((tmp_path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    _make_runtime_state_for_test(tmp_path, dloop=base, task_sessions=existing.get("task_sessions", {}))


if __name__ == '__main__':
    unittest.main()
