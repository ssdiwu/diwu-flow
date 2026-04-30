"""scripts/dend.py 测试。

覆盖：无状态文件 / 有状态文件取消 / 状态文件含多任务。
I2: CLI-first subprocess 调用。
"""

import json
from pathlib import Path

import pytest
from conftest import run_script  # noqa: E402

RUNTIME_STATE_NAME = "dtask-state.json"


class TestDendNoState:
    def test_no_state_file(self, tmp_project_dir):
        rc, out, err = run_script("dend.py", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "no_loop"
        assert "无活跃" in data.get("message", "")


class TestDendCancel:
    def _write_state(self, root: Path, **overrides):
        diwu = root / ".diwu"
        diwu.mkdir(exist_ok=True)
        state = diwu / RUNTIME_STATE_NAME
        default = {
            "version": 1,
            "task_sessions": {},
            "dloop": {
                "active": True,
                "session_id": "test-session",
                "started_at": "2026-04-30T00:00:00Z",
                "completed_task_ids": [1, 2],
                "current_iteration": 3,
                "max_tasks": 10,
                "stopped_at": None,
                "stop_reason": None,
            },
        }
        default["dloop"].update(overrides)
        state.write_text(json.dumps(default, ensure_ascii=False, indent=2))

    def test_cancel_with_tasks(self, tmp_project_dir):
        self._write_state(tmp_project_dir, completed_task_ids=[1, 2], current_iteration=3)

        state_file = tmp_project_dir / ".diwu" / RUNTIME_STATE_NAME
        assert state_file.exists()

        rc, out, err = run_script("dend.py", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "cancelled"
        assert data["completed_count"] == 2
        assert data["iteration"] == 3

        runtime_state = json.loads(state_file.read_text())
        assert runtime_state["dloop"] is None

    def test_cancel_many_tasks(self, tmp_project_dir):
        self._write_state(tmp_project_dir, completed_task_ids=list(range(1, 11)), current_iteration=8)

        rc, out, err = run_script("dend.py", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["completed_count"] == 10

    def test_cancel_empty_completed(self, tmp_project_dir):
        self._write_state(tmp_project_dir, completed_task_ids=[], current_iteration=1)

        rc, out, err = run_script("dend.py", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["completed_count"] == 0
        assert data["status"] == "cancelled"

    def test_formatted_text_present(self, tmp_project_dir):
        self._write_state(tmp_project_dir, completed_task_ids=[5], current_iteration=2)

        rc, out, err = run_script("dend.py", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        ft = data.get("formatted_text", "")
        assert "已取消" in ft
        assert "已完成任务数: 1" in ft
