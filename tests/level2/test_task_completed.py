"""L2 tests for task_completed.py — loop tracking behavior."""

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
TASK_COMPLETED_SCRIPT = PROJECT_ROOT / "hooks" / "scripts" / "task_completed.py"
RUNTIME_STATE_NAME = ".diwu/dtask-state.toml"


def _run_task_completed(tmp_path, event_data):
    """Run task_completed.py with given event data via stdin."""
    env = os.environ.copy()
    env["DIWU_SILENT"] = "1"
    result = subprocess.run(
        [sys.executable, str(TASK_COMPLETED_SCRIPT)],
        input=json.dumps(event_data),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
    )
    return result


def _make_dtask(tmp_path, tasks):
    import tomli_w
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.toml").write_bytes(
        tomli_w.dumps({"tasks": tasks}).encode('utf-8')
    )


def _make_runtime_state(tmp_path, dloop=None, task_sessions=None):
    import tomli_w
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    state = {
        "version": 1,
        "task_sessions": task_sessions or {},
        "dloop": dloop,
    }

    def _strip_none(obj):
        if isinstance(obj, dict):
            return {k: _strip_none(v) for k, v in obj.items() if v is not None}
        if isinstance(obj, list):
            return [_strip_none(item) for item in obj]
        return obj

    with open(diwu / "dtask-state.toml", "wb") as f:
        tomli_w.dump(_strip_none(state), f)


class TestTaskCompletedLoopTracking:
    """task_completed.py 的 loop completed_task_ids 追踪行为。"""

    def test_match_session_appends_once(self, tmp_path):
        """loop active + event.task 存在 → append 到 completed_task_ids。"""
        _make_dtask(tmp_path, [
            {"id": 5, "title": "T5", "status": "Done"},
        ])
        _make_runtime_state(tmp_path, dloop={
            "active": True,
            "session_id": "session-match",
            "started_at": "2026-04-30T12:00:00Z",
            "completed_task_ids": [1, 2],
            "current_iteration": 2,
            "max_tasks": 5,
            "stopped_at": None,
            "stop_reason": None,
        }, task_sessions={
            "5": {"session_id": "session-match", "started_at": "2026-04-30T12:00:00Z"}
        })

        result = _run_task_completed(tmp_path, {
            "task": {"id": 5, "title": "T5", "status": "Done"},
            "sessionId": "session-match",
        })

        # 脚本本身始终 exit 0
        assert result.returncode == 0
        state = tomllib.loads((tmp_path / RUNTIME_STATE_NAME).read_bytes().decode())
        assert state["dloop"]["completed_task_ids"] == [1, 2, 5]

    def test_missing_event_task_no_append(self, tmp_path):
        """event.task 缺失 → 不追加（不用 fallback heuristic）。"""
        _make_dtask(tmp_path, [
            {"id": 5, "title": "T5", "status": "Done"},
        ])
        _make_runtime_state(tmp_path, dloop={
            "active": True,
            "session_id": "session-match",
            "started_at": "2026-04-30T12:00:00Z",
            "completed_task_ids": [1],
            "current_iteration": 1,
            "max_tasks": 5,
            "stopped_at": None,
            "stop_reason": None,
        })

        # event.task 完全缺失，只有 sessionId
        result = _run_task_completed(tmp_path, {
            "sessionId": "session-match",
        })

        assert result.returncode == 0
        state = tomllib.loads((tmp_path / RUNTIME_STATE_NAME).read_bytes().decode())
        assert state["dloop"]["completed_task_ids"] == [1]

    def test_duplicate_done_no_double_append(self, tmp_path):
        """同一 task_id 再次 Done → 不重复追加。"""
        _make_dtask(tmp_path, [
            {"id": 5, "title": "T5", "status": "Done"},
        ])
        _make_runtime_state(tmp_path, dloop={
            "active": True,
            "session_id": "session-match",
            "started_at": "2026-04-30T12:00:00Z",
            "completed_task_ids": [1, 5],
            "current_iteration": 2,
            "max_tasks": 5,
            "stopped_at": None,
            "stop_reason": None,
        })

        result = _run_task_completed(tmp_path, {
            "task": {"id": 5, "title": "T5", "status": "Done"},
            "sessionId": "session-match",
        })

        assert result.returncode == 0
        state = tomllib.loads((tmp_path / RUNTIME_STATE_NAME).read_bytes().decode())
        assert state["dloop"]["completed_task_ids"] == [1, 5]

    def test_reminder_off_still_counts(self, tmp_path):
        """recording_reminder=false 时 Done 事件仍触发 loop 追踪和 owner 清理。

        验证修复后行为：reminder sys.exit(0) 在所有 bookkeeping 之后，
        所以即使 reminder 关闭，owner 清理 + loop 追踪仍正常执行。
        """
        _make_dtask(tmp_path, [
            {"id": 5, "title": "T5", "status": "Done"},
        ])
        # 有 owner 条目让 clear_task_owner 能成功
        _make_runtime_state(tmp_path, dloop={
            "active": True,
            "session_id": "session-match",
            "started_at": "2026-04-30T12:00:00Z",
            "completed_task_ids": [1],
            "current_iteration": 1,
            "max_tasks": 5,
            "stopped_at": None,
            "stop_reason": None,
        }, task_sessions={
            "5": {"session_id": "session-match", "started_at": "2026-04-30T12:00:00Z"}
        })
        (tmp_path / ".diwu" / "dsettings.toml").write_text(
            "dloop_review_cap = 5\n\nreminder_on_taskdone = false\n", encoding="utf-8"
        )

        result = _run_task_completed(tmp_path, {
            "task": {"id": 5, "title": "T5", "status": "Done"},
            "sessionId": "session-match",
        })

        assert result.returncode == 0
        state = tomllib.loads((tmp_path / RUNTIME_STATE_NAME).read_bytes().decode())
        assert state["dloop"]["completed_task_ids"] == [1, 5]  # 仍然计数！

    def test_unconfirmed_done_no_append(self, tmp_path):
        """Done 事件但 clear_task_owner 失败（无 owner 条目）→ 不追加 loop 计数。

        验证修复前 bug：owner 清理失败时 task id 不应被记账。
        """
        _make_dtask(tmp_path, [
            {"id": 5, "title": "T5", "status": "Done"},
        ])
        # task_sessions 为空 → clear_task_owner 会失败（找不到 owner）
        _make_runtime_state(tmp_path, dloop={
            "active": True,
            "session_id": "session-match",
            "started_at": "2026-04-30T12:00:00Z",
            "completed_task_ids": [1],
            "current_iteration": 1,
            "max_tasks": 5,
            "stopped_at": None,
            "stop_reason": None,
        }, task_sessions={})

        result = _run_task_completed(tmp_path, {
            "task": {"id": 5, "title": "T5", "status": "Done"},
            "sessionId": "session-match",
        })

        assert result.returncode == 0
        state = tomllib.loads((tmp_path / RUNTIME_STATE_NAME).read_bytes().decode())
        assert state["dloop"]["completed_task_ids"] == [1]  # owner 清理失败，不应追加

    def test_inprogress_task_no_append(self, tmp_path):
        """event.task 存在但 status=InProgress → 不追加到 completed_task_ids。"""
        _make_dtask(tmp_path, [
            {"id": 5, "title": "T5", "status": "InProgress"},  # 注意不是 Done
        ])
        _make_runtime_state(tmp_path, dloop={
            "active": True,
            "session_id": "session-match",
            "started_at": "2026-04-30T12:00:00Z",
            "completed_task_ids": [1],
            "current_iteration": 1,
            "max_tasks": 5,
            "stopped_at": None,
            "stop_reason": None,
        })

        result = _run_task_completed(tmp_path, {
            "task": {"id": 5, "title": "T5", "status": "InProgress"},  # InProgress
            "sessionId": "session-match",
        })

        assert result.returncode == 0
        state = tomllib.loads((tmp_path / RUNTIME_STATE_NAME).read_bytes().decode())
        assert state["dloop"]["completed_task_ids"] == [1]  # 不应追加 5
