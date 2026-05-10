"""L2 tests for stop_decision.py — B group checks (pending_recording gate, reminders)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'hooks', 'scripts'))
from stop_decision import hook_session_id



RUNTIME_STATE_NAME = ".diwu/dtask-state.toml"


class _PendingRecordingTestBase(unittest.TestCase):
    """共享 setUp：创建临时目录 + git repo + .diwu/ 基础结构。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cwd = self.tmpdir
        subprocess.run(["git", "init"], cwd=self.cwd, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=self.cwd, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"],
            cwd=self.cwd, capture_output=True,
        )
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
        _diwu_path = os.path.join(self.cwd, ".diwu")
        os.makedirs(_diwu_path, exist_ok=True)
        import tomli_w
        state_path = os.path.join(_diwu_path, "dtask-state.toml")
        with open(state_path, "wb") as f:
            tomli_w.dump({"version": 1}, f)
        task_path = os.path.join(_diwu_path, "dtask.toml")
        with open(task_path, "w") as f:
            json.dump({"tasks": []}, f)
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
        state = {"version": 1}
        state.update(overrides)
        path = os.path.join(self.cwd, ".diwu", "dtask-state.toml")
        import tomli_w

        def _strip_none(obj):
            if isinstance(obj, dict):
                return {k: _strip_none(v) for k, v in obj.items() if v is not None}
            if isinstance(obj, list):
                return [_strip_none(item) for item in obj]
            return obj

        with open(path, "wb") as f:
            tomli_w.dump(_strip_none(state), f)

    def _touch_file(self, relpath):
        full = os.path.join(self.cwd, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write("modified")


class TestHookSessionId(unittest.TestCase):
    """Stop hook session id normalization."""

    def test_prefers_session_id(self):
        event = {"session_id": "snake", "sessionId": "camel"}
        self.assertEqual(hook_session_id(event), "snake")

    def test_accepts_sessionId(self):
        event = {"sessionId": "camel-only"}
        self.assertEqual(hook_session_id(event), "camel-only")


from stop_decision import (
    _check_diu_dirty,
    _check_pending_recording_gate,
    _resolve_stop_session_id,
)
from session_scope import scoped_session_file


class TestPendingRecordingGate(_PendingRecordingTestBase):
    """_check_pending_recording_gate 单元测试。"""

    def test_no_marker_returns_empty(self):
        level, hint = _check_pending_recording_gate(self.cwd, "sess-001")
        self.assertEqual(level, "")
        self.assertEqual(hint, "")

    def test_null_marker_returns_empty(self):
        self._write_state(pending_recording=None)
        level, hint = _check_pending_recording_gate(self.cwd, "sess-001")
        self.assertEqual(level, "")
        self.assertEqual(hint, "")

    def test_own_session_with_diu_dirty_blocks(self):
        from datetime import datetime, timezone as _tz
        now_iso = datetime.now(_tz.utc).isoformat()
        self._write_state(pending_recording={
            "task_id": 7,
            "target_status": "Done",
            "session_id": "sess-own",
            "released_at": now_iso,
        })
        self._touch_file(".diwu/dtask.toml")

        level, hint = _check_pending_recording_gate(self.cwd, "sess-own")
        self.assertEqual(level, "block")
        self.assertIn("/drec", hint)

    def test_own_session_diu_clean_no_block(self):
        from datetime import datetime, timezone as _tz
        now_iso = datetime.now(_tz.utc).isoformat()
        self._write_state(pending_recording={
            "task_id": 7,
            "target_status": "Done",
            "session_id": "sess-own",
            "released_at": now_iso,
        })
        subprocess.run(
            ["git", "add", ".diwu/dtask-state.toml"],
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
        from datetime import datetime, timezone as _tz, timedelta
        stale_time = (datetime.now(_tz.utc) - timedelta(minutes=35)).isoformat()
        self._write_state(pending_recording={
            "task_id": 3,
            "target_status": "InReview",
            "session_id": "sess-old",
            "released_at": stale_time,
        })
        self._touch_file(".diwu/dtask.toml")

        level, hint = _check_pending_recording_gate(self.cwd, "sess-old")
        self.assertEqual(level, "warn")
        self.assertIn("过期", hint)

    def test_other_session_silent(self):
        from datetime import datetime, timezone as _tz
        now_iso = datetime.now(_tz.utc).isoformat()
        self._write_state(pending_recording={
            "task_id": 5,
            "target_status": "Done",
            "session_id": "sess-other",
            "released_at": now_iso,
        })
        self._touch_file(".diwu/dtask.toml")

        level, hint = _check_pending_recording_gate(self.cwd, "sess-mine")
        self.assertEqual(level, "")
        self.assertEqual(hint, "")

    def test_corrupted_state_file_safe(self):
        state_path = os.path.join(self.cwd, ".diwu", "dtask-state.toml")
        with open(state_path, "w") as f:
            f.write("{broken json!!!")

        level, hint = _check_pending_recording_gate(self.cwd, "sess-001")
        self.assertEqual(level, "")
        self.assertEqual(hint, "")


class TestDiuDirty(_PendingRecordingTestBase):
    """_check_diu_dirty 独立测试。"""

    def test_diu_dirty_detects_dtask_toml_change(self):
        self._touch_file(".diwu/dtask.toml")
        has_dirty, files = _check_diu_dirty(self.cwd)
        self.assertTrue(has_dirty)
        self.assertTrue(any("dtask.toml" in f for f in files))

    def test_diu_dirty_detects_recording_file_change(self):
        self._touch_file(".diwu/recording/session-test.md")
        has_dirty, files = _check_diu_dirty(self.cwd)
        self.assertTrue(has_dirty)
        self.assertTrue(any("recording" in f for f in files))

    def test_diu_dirty_ignores_code_changes(self):
        self._touch_file("src/main.py")
        has_dirty, files = _check_diu_dirty(self.cwd)
        self.assertFalse(has_dirty)
        self.assertEqual(files, [])


class TestResolveStopSessionId(unittest.TestCase):
    """_resolve_stop_session_id 独立测试。"""

    def test_resolves_from_event_id(self):
        result = _resolve_stop_session_id("event-sid-123", "/tmp/fake")
        self.assertEqual(result, "event-sid-123")

    def test_falls_back_to_env_var(self):
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


if __name__ == '__main__':
    unittest.main()
