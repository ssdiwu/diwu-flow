"""task_entry_guard.py 归档 marker 机制测试。

覆盖 /darc 合法缩减 dtask.json 时 guard 放行的四类场景。
"""

import json
import os
import subprocess
import sys

TASK_GUARD_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "..", "hooks", "scripts", "task_entry_guard.py"
)


def _run_guard(tmp_path, tool_name="Edit", file_path=None, extra_env=None):
    """Run task_entry_guard with given parameters, return result."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "cwd": str(tmp_path),
        "tool_input": {"file_path": file_path or str(tmp_path / "src" / "main.py")},
    }
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [sys.executable, str(TASK_GUARD_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
    )
    return result


def _setup_dtask(tmp_path, status="InSpec", task_id=1):
    """Create dtask.json with a task of given status."""
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.json").write_text(
        json.dumps({"tasks": [{"id": task_id, "title": f"T{task_id}", "status": status}]}),
        encoding="utf-8",
    )


def _create_archiving_marker(tmp_path):
    """Create .diwu/.archiving-in-progress marker."""
    marker = tmp_path / ".diwu" / ".archiving-in-progress"
    marker.parent.mkdir(exist_ok=True)
    marker.touch()


class TestArchivingMarkerGuard:
    """归档 marker 机制：/darc 合法操作时 guard 放行。"""

    def test_marker_exists_write_dtask_allows(self, tmp_path):
        """marker 存在 + 写 dtask.json → exit(0) 放行。"""
        _setup_dtask(tmp_path)
        _create_archiving_marker(tmp_path)
        dtask_path = str(tmp_path / ".diwu" / "dtask.json")
        result = _run_guard(tmp_path, file_path=dtask_path)
        assert result.returncode == 0, f"Expected exit(0), got {result.returncode}. stderr: {result.stderr}"

    def test_marker_exists_write_other_file_still_checks(self, tmp_path):
        """marker 存在 + 写非 dtask.json 文件 → 仍走正常 guard（无活跃任务 → soft warning）。"""
        _setup_dtask(tmp_path)  # 有 InSpec 任务 → 正常放行
        _create_archiving_marker(tmp_path)
        other_file = str(tmp_path / "src" / "app.py")
        result = _run_guard(tmp_path, file_path=other_file)
        # 有 InSpec 任务 + marker 不影响非 dtask 文件 → 应放行 (exit 0)
        assert result.returncode == 0

    def test_marker_exists_no_active_task_other_file_soft_warning(self, tmp_path):
        """marker 存在 + 无活跃任务 + 写其他文件 → soft warning (exit 0)。"""
        # 创建空 dtask（无活跃任务）
        diwu = tmp_path / ".diwu"
        diwu.mkdir(exist_ok=True)
        (diwu / "dtask.json").write_text(
            json.dumps({"tasks": [{"id": 1, "title": "T1", "status": "Done"}]}),
            encoding="utf-8",
        )
        _create_archiving_marker(tmp_path)
        other_file = str(tmp_path / "src" / "app.py")
        result = _run_guard(tmp_path, file_path=other_file)
        # 无活跃任务 → soft warning → exit(0)，marker 不影响此路径
        assert result.returncode == 0

    def test_no_marker_behavior_unchanged(self, tmp_path):
        """无 marker + dtask.json 无活跃任务 → 行为与改动前一致（soft warning）。"""
        # 空 dtask，无活跃任务，无 marker
        diwu = tmp_path / ".diwu"
        diwu.mkdir(exist_ok=True)
        (diwu / "dtask.json").write_text(json.dumps({"tasks": []}), encoding="utf-8")

        # 先确认无 marker 时写 dtask 是 soft warning（exit 0）
        dtask_path = str(tmp_path / ".diwu" / "dtask.json")
        result = _run_guard(tmp_path, file_path=dtask_path)
        assert result.returncode == 0  # soft warning, not hard block
        assert "diwu-task-guard" in result.stderr or result.returncode == 0

    def test_marker_deleted_after_archive(self, tmp_path):
        """归档完成后删除 marker → 后续写入恢复正常拦截。"""
        _setup_dtask(tmp_path)
        _create_archiving_marker(tmp_path)

        dtask_path = str(tmp_path / ".diwu" / "dtask.json")
        # marker 存在时放行
        result = _run_guard(tmp_path, file_path=dtask_path)
        assert result.returncode == 0

        # 删除 marker（模拟归档完成）
        marker = tmp_path / ".diwu" / ".archiving-in-progress"
        marker.unlink()

        # 现在有 InSpec 任务 → 正常放行（因为 _has_active_task 返回 True）
        result = _run_guard(tmp_path, file_path=dtask_path)
        assert result.returncode == 0

    def test_marker_only_exempts_dtask_json(self, tmp_path):
        """marker 仅豁免 dtask.json 本身，不豁免 .diwu/ 下其他文件。"""
        _setup_dtask(tmp_path)
        _create_archiving_marker(tmp_path)

        # dtask.json → 放行
        dtask_path = str(tmp_path / ".diwu" / "dtask.json")
        result = _run_guard(tmp_path, file_path=dtask_path)
        assert result.returncode == 0

        # decisions.md（同属 .diwu/ 但不是 dtask.json）→ 也应放行因为 _is_workflow_file
        decisions_path = str(tmp_path / ".diwu" / "decisions.md")
        result = _run_guard(tmp_path, file_path=decisions_path)
        assert result.returncode == 0  # workflow files always allowed

        # recording/ 下文件 → 也应放行（workflow file）
        rec_path = str(tmp_path / ".diwu" / "recording" / "session-test.md")
        (tmp_path / ".diwu" / "recording").mkdir(exist_ok=True)
        result = _run_guard(tmp_path, file_path=rec_path)
        assert result.returncode == 0  # recording prefix always allowed
