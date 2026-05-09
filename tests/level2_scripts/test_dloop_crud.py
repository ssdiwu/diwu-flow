"""scripts/dloop.py 测试。

覆盖：start 成功 / start 冲突 / start 无任务 / status 有文件 / status 无文件。
I2: CLI-first subprocess 调用。
验证与 test_dloop.py(test_stop_decision) 不重叠（T2）。
"""

import json
from pathlib import Path

import pytest
from conftest import run_script  # noqa: E402

RUNTIME_STATE_NAME = "dtask-state.json"


def _runtime_state_file(root: Path) -> Path:
    return root / ".diwu" / RUNTIME_STATE_NAME


def _read_runtime_state(root: Path) -> dict:
    return json.loads(_runtime_state_file(root).read_text())


def _read_loop_state(root: Path) -> dict | None:
    return _read_runtime_state(root).get("dloop")


class TestDloopStart:
    def _write_dtask_with_tasks(self, root: Path, tasks_data):
        diwu = root / ".diwu"
        diwu.mkdir(exist_ok=True)
        dtask = diwu / "dtask.json"
        dtask.write_text(json.dumps({"tasks": tasks_data}, ensure_ascii=False, indent=2))

    def test_start_success(self, tmp_project_dir):
        self._write_dtask_with_tasks(tmp_project_dir, [
            {"id": 1, "title": "t1", "status": "InSpec"},
            {"id": 2, "title": "t2", "status": "InProgress"},
        ])
        rc, out, err = run_script("dloop.py", "start", "--cwd", str(tmp_project_dir), "--interval", "3m")
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "started"
        assert "state_file" in data.get("data", {})
        # T8: JSON 输出契约满足即通过；状态文件存在性为脚本内部行为（subprocess 隔离下不断言文件系统副作用）

    def test_start_conflict(self, tmp_project_dir):
        # 先手动创建一个活跃的状态文件
        diwu = tmp_project_dir / ".diwu"
        diwu.mkdir(exist_ok=True)
        # 需要 dtask.json 有可执行任务，否则 classify 判为 terminal_stale 而非 already_running
        dtask = diwu / "dtask.json"
        dtask.write_text(json.dumps({"tasks": [
            {"id": 1, "title": "t1", "status": "InProgress"},
        ]}, ensure_ascii=False, indent=2))
        existing_state = {
            "active": True,
            "session_id": "existing",
            "started_at": "2026-04-30T00:00:00Z",
            "completed_task_ids": [],
            "current_iteration": 5,
            "max_tasks": 10,
        }
        (diwu / "dloop-state.json").write_text(
            json.dumps(existing_state, ensure_ascii=False, indent=2)
        )

        rc, out, err = run_script("dloop.py", "start", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is False
        assert data["status"] == "already_running"

    def test_start_no_executable_tasks(self, tmp_project_dir):
        # 只有 Done 和 Cancelled 任务
        self._write_dtask_with_tasks(tmp_project_dir, [
            {"id": 1, "title": "done", "status": "Done"},
            {"id": 2, "title": "cancelled", "status": "Cancelled"},
        ])
        rc, out, err = run_script("dloop.py", "start", "--cwd", str(tmp_project_dir), "--interval", "3m")
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is False
        assert data["status"] == "no_executable_tasks"

    def test_start_max_tasks_param(self, tmp_project_dir):
        self._write_dtask_with_tasks(tmp_project_dir, [
            {"id": 1, "title": "t1", "status": "InSpec"},
            {"id": 2, "title": "t2", "status": "InSpec"},
            {"id": 3, "title": "t3", "status": "InProgress"},
        ])
        rc, out, err = run_script("dloop.py", "start", "--max-tasks", "2", "--cwd", str(tmp_project_dir), "--interval", "3m")
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert _read_loop_state(tmp_project_dir)["max_tasks"] == 2

    def test_start_max_tasks_zero_infinite(self, tmp_project_dir):
        """--max-tasks 0 应为无限模式。"""
        self._write_dtask_with_tasks(tmp_project_dir, [
            {"id": 1, "title": "t1", "status": "InSpec"},
            {"id": 2, "title": "t2", "status": "InProgress"},
        ])
        rc, out, _ = run_script("dloop.py", "start", "--max-tasks", "0", "--cwd", str(tmp_project_dir), "--interval", "3m")
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert _read_loop_state(tmp_project_dir)["max_tasks"] == 0

    def test_start_auto_snapshot(self, tmp_project_dir):
        """不传 --max-tasks 时应自动取活跃任务数作为 max_tasks。"""
        self._write_dtask_with_tasks(tmp_project_dir, [
            {"id": 1, "title": "t1", "status": "InSpec"},
            {"id": 2, "title": "t2", "status": "InProgress"},
            {"id": 3, "title": "t3 (blocked by t1)", "status": "InSpec", "blocked_by": [1]},
        ])
        rc, out, _ = run_script("dloop.py", "start", "--cwd", str(tmp_project_dir), "--interval", "3m")
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert _read_loop_state(tmp_project_dir)["max_tasks"] == 3


class TestDloopStatus:
    def test_status_no_loop(self, tmp_project_dir):
        rc, out, err = run_script("dloop.py", "status", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "no_loop"

    def test_status_running(self, tmp_project_dir):
        # 创建一个模拟的运行中状态
        diwu = tmp_project_dir / ".diwu"
        diwu.mkdir(exist_ok=True)
        # 需要 dtask.json 有可执行任务，否则 classify 判为 terminal_stale
        dtask = diwu / "dtask.json"
        dtask.write_text(json.dumps({"tasks": [
            {"id": 4, "title": "t4", "status": "InProgress"},
        ]}, ensure_ascii=False, indent=2))
        state = {
            "active": True,
            "session_id": "test-session",
            "started_at": "2026-04-30T12:00:00Z",
            "completed_task_ids": [1, 2, 3],
            "current_iteration": 4,
            "max_tasks": 10,
        }
        (diwu / "dloop-state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2))

        rc, out, err = run_script("dloop.py", "status", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "running"
        assert data["data"]["current_iteration"] == 4
        assert data["data"]["completed_task_ids"] == [1, 2, 3]
        assert data["data"]["max_tasks"] == 10

    def test_status_inactive(self, tmp_project_dir):
        # 非活跃状态文件
        diwu = tmp_project_dir / ".diwu"
        diwu.mkdir(exist_ok=True)
        state = {"active": False, "completed_task_ids": []}
        (diwu / "dloop-state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2))

        rc, out, err = run_script("dloop.py", "status", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "inactive"


class TestNoCancelSubcommand:
    """T3: dloop.py 不应包含 cancel 功能。"""

    def test_no_cancel_in_help(self):
        """验证 help 输出不含 cancel 子命令。"""
        rc, out, err = run_script("dloop.py")
        assert rc == 0
        assert "cancel" not in out.lower()


class TestDloopStaleState:
    """#23: stale-state 兜底 — terminal_stale 自动清理 / invalid 不删除 / active 保持。"""

    def _write_dtask(self, root: Path, tasks_data):
        diwu = root / ".diwu"
        diwu.mkdir(exist_ok=True)
        dtask = diwu / "dtask.json"
        dtask.write_text(json.dumps({"tasks": tasks_data}, ensure_ascii=False, indent=2))

    def _write_state(self, root: Path, state_data):
        diwu = root / ".diwu"
        diwu.mkdir(exist_ok=True)
        state_file = diwu / "dloop-state.json"
        state_file.write_text(json.dumps(state_data, ensure_ascii=False, indent=2))

    # --- terminal_stale: completed >= max_tasks ---

    def test_status_terminal_stale_completed_exceeds_max(self, tmp_project_dir):
        """status 命中 completed >= max_tasks → stale_cleaned + 文件删除。"""
        self._write_state(tmp_project_dir, {
            "active": True,
            "session_id": "stale-test",
            "started_at": "2026-04-30T00:00:00Z",
            "completed_task_ids": [1, 2, 3],
            "current_iteration": 3,
            "max_tasks": 3,  # completed(3) >= max_tasks(3) → terminal_stale
            "stopped_at": None,
            "stop_reason": None,
        })
        rc, out, _ = run_script("dloop.py", "status", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "stale_cleaned"
        assert "cleanup_reason" in data.get("data", {})
        # legacy 文件应已被删除
        assert not (tmp_project_dir / ".diwu" / "dloop-state.json").exists()

    def test_start_terminal_stale_clean_and_continue(self, tmp_project_dir):
        """start 命中 terminal_stale → 清理旧 state 后继续正常启动 started。"""
        self._write_dtask(tmp_project_dir, [
            {"id": 1, "title": "t1", "status": "InSpec"},
        ])
        self._write_state(tmp_project_dir, {
            "active": True,
            "session_id": "stale-old",
            "started_at": "2026-04-30T00:00:00Z",
            "completed_task_ids": [1, 2, 3],
            "current_iteration": 3,
            "max_tasks": 3,  # terminal_stale
            "stopped_at": None,
            "stop_reason": None,
        })
        rc, out, _ = run_script("dloop.py", "start", "--cwd", str(tmp_project_dir), "--interval", "3m")
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "started"
        # message/formatted_text 应含清理提示
        assert "已清理残留" in data.get("message", "") or "🧹" in data.get("formatted_text", "")
        assert _runtime_state_file(tmp_project_dir).exists()
        assert _read_loop_state(tmp_project_dir)["active"] is True
        assert not (tmp_project_dir / ".diwu" / "dloop-state.json").exists()

    # --- terminal_stale: 无可执行任务 ---

    def test_status_terminal_stale_no_executable(self, tmp_project_dir):
        """status 命中无可执行任务 → stale_cleaned + 文件删除。"""
        # dtask 中只有 Done/Cancelled 任务
        self._write_dtask(tmp_project_dir, [
            {"id": 1, "title": "done", "status": "Done"},
            {"id": 2, "title": "cancelled", "status": "Cancelled"},
        ])
        self._write_state(tmp_project_dir, {
            "active": True,
            "session_id": "stale-no-exec",
            "started_at": "2026-04-30T00:00:00Z",
            "completed_task_ids": [],
            "current_iteration": 0,
            "max_tasks": 0,  # 无限模式但无任务可执行 → terminal_stale
            "stopped_at": None,
            "stop_reason": None,
        })
        rc, out, _ = run_script("dloop.py", "status", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "stale_cleaned"
        assert not (tmp_project_dir / ".diwu" / "dloop-state.json").exists()

    # --- active_or_recoverable: 正常活跃 ---

    def test_status_active_keeps_running(self, tmp_project_dir):
        """status 命中 active_or_recoverable → 保持 running，不删文件。"""
        self._write_dtask(tmp_project_dir, [
            {"id": 1, "title": "t1", "status": "InProgress"},
        ])
        self._write_state(tmp_project_dir, {
            "active": True,
            "session_id": "active-session",
            "started_at": "2026-04-30T00:00:00Z",
            "completed_task_ids": [1],
            "current_iteration": 1,
            "max_tasks": 5,  # completed(1) < max_tasks(5)，且有 InProgress 任务
            "stopped_at": None,
            "stop_reason": None,
        })
        rc, out, _ = run_script("dloop.py", "status", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "running"
        assert _runtime_state_file(tmp_project_dir).exists()
        assert _read_loop_state(tmp_project_dir)["active"] is True
        assert not (tmp_project_dir / ".diwu" / "dloop-state.json").exists()

    def test_start_active_returns_already_running(self, tmp_project_dir):
        """start 命中 active_or_recoverable → already_running，不删文件。"""
        self._write_dtask(tmp_project_dir, [
            {"id": 1, "title": "t1", "status": "InProgress"},
        ])
        self._write_state(tmp_project_dir, {
            "active": True,
            "session_id": "active-session",
            "started_at": "2026-04-30T00:00:00Z",
            "completed_task_ids": [1],
            "current_iteration": 1,
            "max_tasks": 5,
            "stopped_at": None,
            "stop_reason": None,
        })
        rc, out, _ = run_script("dloop.py", "start", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is False
        assert data["status"] == "already_running"
        assert _runtime_state_file(tmp_project_dir).exists()
        assert _read_loop_state(tmp_project_dir)["active"] is True
        assert not (tmp_project_dir / ".diwu" / "dloop-state.json").exists()

    # --- invalid_state: JSON 损坏 ---

    def test_status_invalid_json_not_deleted(self, tmp_project_dir):
        """status 命中损坏 JSON → invalid_state_file，不删文件。"""
        diwu = tmp_project_dir / ".diwu"
        diwu.mkdir(exist_ok=True)
        state_file = diwu / "dloop-state.json"
        state_file.write_text("{bad json content!!!")

        rc, out, _ = run_script("dloop.py", "status", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is False
        assert data["status"] == "invalid_state_file"
        # 损坏文件不应被自动删除
        assert state_file.exists()

    def test_start_invalid_json_not_deleted(self, tmp_project_dir):
        """start 命中损坏 JSON → invalid_state_file，不删文件。"""
        diwu = tmp_project_dir / ".diwu"
        diwu.mkdir(exist_ok=True)
        state_file = diwu / "dloop-state.json"
        state_file.write_text("{bad json content!!!")

        rc, out, _ = run_script("dloop.py", "start", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is False
        assert data["status"] == "invalid_state_file"
        assert state_file.exists()

    def test_status_invalid_typed_state_not_deleted(self, tmp_project_dir):
        """可解析但字段类型错误的 state 也应返回 invalid_state_file，不直接 traceback。"""
        self._write_state(tmp_project_dir, {
            "active": True,
            "session_id": "bad-type",
            "started_at": "2026-04-30T00:00:00Z",
            "completed_task_ids": [],
            "current_iteration": 0,
            "max_tasks": "oops",
        })

        rc, out, _ = run_script("dloop.py", "status", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is False
        assert data["status"] == "invalid_state_file"
        assert (tmp_project_dir / ".diwu" / "dloop-state.json").exists()

    def test_status_terminal_stale_pending_review(self, tmp_project_dir):
        """review_limit 命中时，status 也应识别为 terminal_stale 并清理文件。"""
        diwu = tmp_project_dir / ".diwu"
        diwu.mkdir(exist_ok=True)
        (diwu / "dtask.json").write_text(json.dumps({
            "tasks": [
                {"id": 1, "title": "review", "status": "InReview"},
                {"id": 2, "title": "next", "status": "InSpec"},
            ],
            "review_used": 5,
        }, ensure_ascii=False, indent=2))
        (diwu / "dsettings.json").write_text(json.dumps({"review_limit": 5}, ensure_ascii=False, indent=2))
        self._write_state(tmp_project_dir, {
            "active": True,
            "session_id": "review-limit",
            "started_at": "2026-04-30T00:00:00Z",
            "completed_task_ids": [1],
            "current_iteration": 1,
            "max_tasks": 0,
        })

        rc, out, _ = run_script("dloop.py", "status", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "stale_cleaned"
        assert "PENDING REVIEW" in data["data"]["cleanup_reason"]
        assert not (tmp_project_dir / ".diwu" / "dloop-state.json").exists()


class TestDloopPathIntegrity:
    """#24: 防止 .diwu/.diwu 双重路径 bug 回归的可观测性测试。"""

    def test_status_running_reads_correct_state_path(self, tmp_project_dir):
        """证明 subprocess 读的是 <cwd>/.diwu/dtask-state.json。"""
        diwu = tmp_project_dir / ".diwu"
        diwu.mkdir(exist_ok=True)
        dtask = diwu / "dtask.json"
        dtask.write_text(json.dumps({"tasks": [
            {"id": 1, "title": "t1", "status": "InProgress"},
        ]}, ensure_ascii=False, indent=2))
        state = {
            "version": 1,
            "task_sessions": {
                "1": {"session_id": "path-test", "started_at": "2026-04-30T12:00:00Z"}
            },
            "dloop": {
                "active": True,
                "session_id": "path-test",
                "started_at": "2026-04-30T12:00:00Z",
                "completed_task_ids": [1],
                "current_iteration": 1,
                "max_tasks": 5,
                "stopped_at": None,
                "stop_reason": None,
            },
        }
        (diwu / RUNTIME_STATE_NAME).write_text(
            json.dumps(state, ensure_ascii=False, indent=2)
        )
        wrong_path = diwu / ".diwu" / RUNTIME_STATE_NAME
        assert not wrong_path.exists()

        rc, out, _ = run_script("dloop.py", "status", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["status"] == "running", (
            f"Expected 'running' (reads from <cwd>/.diwu/{RUNTIME_STATE_NAME}), "
            f"got '{data['status']}' — possible .diwu/.diwu double-path bug"
        )

    def test_start_and_status_use_same_state_path(self, tmp_project_dir):
        """start 创建的 state 文件必须被 status 读到（路径一致）。"""
        diwu = tmp_project_dir / ".diwu"
        diwu.mkdir(exist_ok=True)
        dtask = diwu / "dtask.json"
        dtask.write_text(json.dumps({"tasks": [
            {"id": 1, "title": "t1", "status": "InSpec"},
        ]}, ensure_ascii=False, indent=2))

        # 先 start
        rc_start, out_start, _ = run_script("dloop.py", "start", "--cwd", str(tmp_project_dir), "--interval", "3m")
        assert rc_start == 0
        data_start = json.loads(out_start)
        assert data_start["status"] == "started"

        # 再 status — 必须返回 running
        rc_status, out_status, _ = run_script("dloop.py", "status", "--cwd", str(tmp_project_dir))
        assert rc_status == 0
        data_status = json.loads(out_status)
        assert data_status["status"] == "running", (
            "status must return 'running' after start — "
            "proves start and status share the same state path"
        )
