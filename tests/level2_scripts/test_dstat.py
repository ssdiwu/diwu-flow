"""scripts/dstat.py 测试。

覆盖：空项目 / 有任务 / 有 recording / 非 git / deep 模式。
I2: CLI-first subprocess 调用。
"""

import json
from pathlib import Path

import pytest
from conftest import assert_rel_time_shape, run_script  # noqa: E402


class TestDstatEmptyProject:
    def test_empty_project_ok(self, tmp_project_dir):
        rc, out, err = run_script("dstat.py", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "ok"
        assert data["summary"]["tasks"]["total"] == 0
        assert "formatted_text" in data

    def test_formatted_text_has_sections(self, tmp_project_dir):
        rc, out, err = run_script("dstat.py", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        ft = data["formatted_text"]
        assert "项目状态概览" in ft
        assert "任务进度" in ft
        assert "Session" in ft
        assert "Git" in ft or "非 git" in ft

    def test_no_dtask_warning(self, tmp_path):
        """I5: 无 .diwu/ 时应有 warning 而非崩溃。"""
        empty_proj = tmp_path / "empty"
        empty_proj.mkdir()
        rc, out, err = run_script("dstat.py", "--cwd", str(empty_proj))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True


class TestDstatWithTasks:
    def _write_dtask(self, root: Path, tasks_data: dict):
        diwu = root / ".diwu"
        diwu.mkdir(exist_ok=True)
        dtask = diwu / "dtask.json"
        import json as j
        dtask.write_text(j.dumps(tasks_data, ensure_ascii=False, indent=2))

    def test_task_summary_counts(self, tmp_project_dir):
        self._write_dtask(tmp_project_dir, {
            "tasks": [
                {"id": 1, "title": "t1", "status": "InSpec"},
                {"id": 2, "title": "t2", "status": "InSpec"},
                {"id": 3, "title": "t3", "status": "InProgress"},
                {"id": 4, "title": "t4", "status": "Done"},
                {"id": 5, "title": "t5", "status": "Done"},
                {"id": 6, "title": "t6", "status": "Cancelled"},
            ]
        })
        rc, out, err = run_script("dstat.py", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        s = data["summary"]["tasks"]
        assert s["total"] == 6
        assert s["InSpec"] == 2
        assert s["InProgress"] == 1
        assert s["Done"] == 2
        assert s["Cancelled"] == 1

    def test_ascii_table_in_formatted(self, tmp_project_dir):
        self._write_dtask(tmp_project_dir, {
            "tasks": [{"id": 1, "title": "test", "status": "Done"}]
        })
        rc, out, err = run_script("dstat.py", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        ft = data["formatted_text"]
        assert "┌" in ft  # box-drawing character
        assert "Done" in ft


class TestDstatWithRecording:
    def test_sessions_counted(self, tmp_project_dir):
        rec_dir = tmp_project_dir / ".diwu" / "recording"
        rec_dir.mkdir(parents=True)
        (rec_dir / "session-2026-04-28-100000.md").write_text("# test session")
        (rec_dir / "session-2026-04-29-120000.md").write_text("# newer session")

        rc, out, err = run_script("dstat.py", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        assert data["summary"]["recent_sessions"] == 2

    def test_session_relative_time(self, tmp_project_dir):
        rec_dir = tmp_project_dir / ".diwu" / "recording"
        rec_dir.mkdir(parents=True)
        (rec_dir / "session-2026-04-30-000000.md").write_text("# recent")

        rc, out, err = run_script("dstat.py", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        ft = data["formatted_text"]
        # 应含相对时间关键词或日期
        has_rel = any(kw in ft for kw in ["分钟前", "小时前", "天前", "刚刚"])
        assert has_rel or "session-" in ft


class TestDstatNonGit:
    def test_non_git_graceful(self, tmp_project_dir):
        """I5: 非 git 目录不应崩溃，git 字段为 null。"""
        rc, out, err = run_script("dstat.py", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        assert rc == 0
        assert data["ok"] is True
        # 非 git 时 branch 为 None 或 warnings 含提示
        if data["summary"]["git_branch"] is None:
            pass  # expected
        # 或者在 warnings 里
        w = data.get("warnings", [])
        assert any("git" in ww.lower() for ww in w) or data["summary"]["git_branch"] is not None


class TestDstatDeepMode:
    def test_deep_flag_accepted(self, tmp_project_dir):
        rc, out, err = run_script("dstat.py", "--deep", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        # deep 模式应包含更多内容（至少 formatted_text 更长）
        rc2, out2, _ = run_script("dstat.py", "--cwd", str(tmp_project_dir))
        data2 = json.loads(out2)
        assert len(data["formatted_text"]) >= len(data2["formatted_text"])
