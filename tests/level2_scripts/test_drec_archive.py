"""scripts/drec_archive.py 测试。

覆盖：task 归档 / recording 移动+月份分片 / 幂等性 / 无需归档场景 / 踩坑聚合。
I2: CLI-first subprocess 调用。
"""

import json
import os
import time
from pathlib import Path

import pytest

from conftest import run_script  # noqa: E402


class TestArchiveTasks:
    """Task 轨道归档测试：Done/Cancelled 任务追加到 archive/ 并从 dtask.json 移除。"""

    def _write_dtask(self, root: Path, tasks: list):
        diwu = root / ".diwu"
        diwu.mkdir(exist_ok=True)
        (diwu / "dtask.json").write_text(
            json.dumps({"tasks": tasks}, ensure_ascii=False, indent=2)
        )

    def _write_settings(self, root: Path, overrides: dict = None):
        diwu = root / ".diwu"
        diwu.mkdir(exist_ok=True)
        settings = {
            "task_archive_limit": 20,
            "recording_file_limit": 50,
            "recording_keep_days": 30,
        }
        if overrides:
            settings.update(overrides)
        lines = []
        for k, v in settings.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, str):
                lines.append(f'{k} = "{v}"')
            else:
                lines.append(f"{k} = {v}")
        (diwu / "dsettings.toml").write_text("\n".join(lines) + "\n")

    def test_archive_tasks_basic(self, tmp_project_dir):
        """25 个 Done 任务 → 归档到 task_archive_YYYY-MM.json，dtask.json 清空。"""
        self._write_settings(tmp_project_dir, {"task_archive_limit": 20})
        tasks = [
            {"id": i, "title": f"task-{i}", "status": "Done", "description": f"desc {i}"}
            for i in range(1, 26)
        ]
        self._write_dtask(tmp_project_dir, tasks)

        rc, out, err = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["tasks_archived"] == 25

        # 验证 archive 文件存在且包含 25 个任务（标准 dict 格式）
        archive_dir = tmp_project_dir / ".diwu" / "archive"
        archive_files = list(archive_dir.glob("task_archive_*.json"))
        assert len(archive_files) >= 1
        archived_raw = json.loads(archive_files[0].read_text())
        # 兼容 dict（标准格式）和 list（旧格式）
        archived_tasks = archived_raw.get("tasks", []) if isinstance(archived_raw, dict) else archived_raw
        assert len(archived_tasks) == 25
        archived_ids = {t["id"] for t in archived_tasks}
        assert archived_ids == set(range(1, 26))

        # 验证 dtask.json 已移除已归档任务
        remaining = json.loads((tmp_project_dir / ".diwu" / "dtask.json").read_text())
        assert len(remaining["tasks"]) == 0

    def test_archive_tasks_id_dedup(self, tmp_project_dir):
        """幂等：重复执行不产生重复条目（按 id 去重）。"""
        self._write_settings(tmp_project_dir, {"task_archive_limit": 3})
        tasks = [
            {"id": 1, "title": "t1", "status": "Done"},
            {"id": 2, "title": "t2", "status": "Done"},
            {"id": 3, "title": "t3", "status": "Done"},
        ]
        self._write_dtask(tmp_project_dir, tasks)

        # 第一次执行
        rc1, out1, _ = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        assert rc1 == 0
        data1 = json.loads(out1)
        assert data1["tasks_archived"] == 3

        # 写入新任务（含 id 冲突）
        tasks2 = [
            {"id": 4, "title": "t4", "status": "Done"},
            {"id": 5, "title": "t5", "status": "Done"},
            {"id": 1, "title": "t1-new", "status": "Done"},  # 与归档中 id=1 冲突
        ]
        self._write_dtask(tmp_project_dir, tasks2)

        # 第二次执行
        rc2, out2, _ = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        assert rc2 == 0
        data2 = json.loads(out2)
        # 只有 id=4,5 是新的，id=1 应被去重
        assert data2["tasks_archived"] == 2

        # 验证 archive 文件无重复 id（兼容 dict/list 格式）
        archive_file = list((tmp_project_dir / ".diwu" / "archive").glob("task_archive_*.json"))[0]
        archived_raw = json.loads(archive_file.read_text())
        archived_tasks = archived_raw.get("tasks", []) if isinstance(archived_raw, dict) else archived_raw
        archived_ids = [t["id"] for t in archived_tasks]
        assert len(archived_ids) == len(set(archived_ids))  # 无重复

    def test_archive_tasks_below_threshold(self, tmp_project_dir):
        """低于阈值时不归档。"""
        self._write_settings(tmp_project_dir, {"task_archive_limit": 20})
        tasks = [
            {"id": i, "title": f"t{i}", "status": "Done"}
            for i in range(1, 10)
        ]
        self._write_dtask(tmp_project_dir, tasks)

        rc, out, _ = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        assert data["tasks_archived"] == 0
        assert data["recordings_moved"] == 0


class TestArchiveRecordingsMove:
    """Recording 轨道归档测试：移动文件到 archive/recording/YYYY-MM/ 分片目录。"""

    def _setup(self, root: Path, settings_overrides=None):
        diwu = root / ".diwu"
        diwu.mkdir(exist_ok=True)
        rec_dir = diwu / "recording"
        rec_dir.mkdir(exist_ok=True)

        settings = {
            "task_archive_limit": 20,
            "recording_file_limit": 50,
            "recording_keep_days": 30,
        }
        if settings_overrides:
            settings.update(settings_overrides)
        lines = []
        for k, v in settings.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, str):
                lines.append(f'{k} = "{v}"')
            else:
                lines.append(f"{k} = {v}")
        (diwu / "dsettings.toml").write_text("\n".join(lines) + "\n")
        return rec_dir

    def test_recording_move_by_month(self, tmp_project_dir):
        """月份分片验收：session-2026-04-* 进 2026-04/，session-2026-05-* 进 2026-05/。"""
        rec_dir = self._setup(
            tmp_project_dir,
            {"recording_file_limit": 5, "recording_keep_days": 1},
        )
        # 创建 6 个文件（超过 threshold=5）
        for i in range(6):
            fname = f"session-2026-04-{27 + i:02d}-100000.md"
            (rec_dir / fname).write_text(f"# session April {i}")

        # 创建 3 个 5 月的文件
        for i in range(3):
            fname = f"session-2026-05-0{i + 1:02d}-100000.md"
            (rec_dir / fname).write_text(f"# session May {i}")
            # 设置 mtime 为较旧时间以触发超龄
            old_time = time.time() - (2 * 86400)  # 2 天前
            os.utime(rec_dir / fname, (old_time, old_time))

        rc, out, err = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["recordings_moved"] > 0

        # 验证分片目录结构
        archive_rec = tmp_project_dir / ".diwu" / "archive" / "recording"
        apr_dir = archive_rec / "2026-04"
        may_dir = archive_rec / "2026-05"

        # 至少有文件被移动到月份目录
        assert apr_dir.is_dir() or may_dir.is_dir()

        # 验证移动后的文件在正确的月份目录下
        if apr_dir.exists():
            apr_files = list(apr_dir.glob("session-2026-04-*.md"))
            assert len(apr_files) > 0, "April session 文件应在 2026-04/ 目录"

        if may_dir.exists():
            may_files = list(may_dir.glob("session-2026-05-*.md"))
            assert len(may_files) > 0, "May session 文件应在 2026-05/ 目录"

    def test_recording_two_round_rules(self, tmp_project_dir):
        """两轮规则验证：先移超龄，再按 mtime 从旧到新继续移直到 < threshold。"""
        rec_dir = self._setup(
            tmp_project_dir,
            {"recording_file_limit": 5, "recording_keep_days": 30},
        )

        # 创建 10 个文件，均未超龄（mtime 很近），但总数 > threshold
        now = time.time()
        for i in range(10):
            fname = f"session-2026-05-0{i + 1:02d}-100000.md"
            fpath = rec_dir / fname
            fpath.write_text(f"# session {i}")
            # 设置递增的 mtime（i=0 最旧）
            fpath_utime = now - ((10 - i) * 3600)  # 0号最旧（10小时前）
            os.utime(fpath, (fpath_utime, fpath_utime))

        rc, out, _ = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        assert data["ok"] is True

        # 剩余文件数应严格 < threshold (5)
        remaining = list(rec_dir.glob("*.md"))
        assert len(remaining) < 5, f"剩余 {len(remaining)} 个文件，应严格 < 5"


class TestIdempotent:
    """幂等性测试：重复执行不报错、不重复归档。"""

    def test_task_idempotent(self, tmp_project_dir):
        """连续两次 run，第二次 tasks_archived=0。"""
        diwu = tmp_project_dir / ".diwu"
        diwu.mkdir(exist_ok=True)
        (diwu / "dsettings.toml").write_text(
            'task_archive_limit = 3\n'
            'recording_file_limit = 50\n'
            'recording_keep_days = 30\n'
        )
        (diwu / "dtask.json").write_text(json.dumps({
            "tasks": [
                {"id": 1, "title": "t1", "status": "Done"},
                {"id": 2, "title": "t2", "status": "Done"},
                {"id": 3, "title": "t3", "status": "Done"},
                {"id": 99, "title": "active", "status": "InProgress"},
            ]
        }, ensure_ascii=False, indent=2))

        # 第一次
        rc1, out1, _ = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        data1 = json.loads(out1)
        assert data1["tasks_archived"] == 3

        # 第二次（dtask.json 中只剩 InProgress 任务）
        rc2, out2, _ = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        data2 = json.loads(out2)
        assert data2["tasks_archived"] == 0
        assert data2["ok"] is True

    def test_recording_idempotent(self, tmp_project_dir):
        """文件已移动后再次运行不报错。"""
        diwu = tmp_project_dir / ".diwu"
        diwu.mkdir(exist_ok=True)
        (diwu / "dsettings.toml").write_text(
            'task_archive_limit = 999\n'
            'recording_file_limit = 2\n'
            'recording_keep_days = 1\n'
        )

        rec_dir = diwu / "recording"
        rec_dir.mkdir(exist_ok=True)
        f = rec_dir / "session-2026-04-28-100000.md"
        f.write_text("# test")
        old_time = time.time() - (2 * 86400)
        os.utime(str(f), (old_time, old_time))

        # 第一次：移动文件
        rc1, out1, _ = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        data1 = json.loads(out1)
        assert data1["recordings_moved"] == 1

        # 第二次：源文件已不存在
        rc2, out2, _ = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        data2 = json.loads(out2)
        assert data2["ok"] is True  # 不崩溃


class TestNoArchiveNeeded:
    """无需归档的边界场景。"""

    def test_empty_project(self, tmp_project_dir):
        """空项目（无 dtask.json 无 recording）不报错。"""
        rc, out, _ = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        assert data["ok"] is True
        assert data["tasks_archived"] == 0
        assert data["recordings_moved"] == 0

    def test_only_active_tasks(self, tmp_project_dir):
        """只有 InSpec/InProgress 任务时不触发 task 归档。"""
        diwu = tmp_project_dir / ".diwu"
        diwu.mkdir(exist_ok=True)
        (diwu / "dsettings.toml").write_text(
            'task_archive_limit = 3\n'
            'recording_file_limit = 50\n'
            'recording_keep_days = 30\n'
        )
        (diwu / "dtask.json").write_text(json.dumps({
            "tasks": [
                {"id": 1, "title": "t1", "status": "InSpec"},
                {"id": 2, "title": "t2", "status": "InProgress"},
            ]
        }, ensure_ascii=False, indent=2))

        rc, out, _ = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        assert data["ok"] is True
        assert data["tasks_archived"] == 0


class TestAggregatePitfalls:
    """踩坑聚合测试：从 moved files 扫描并聚合到 project-pitfalls.md。"""

    def _make_session_with_pitfalls(self, content: str, filename: str) -> str:
        """生成含踩坑段落的 session 内容。"""
        return f"## Session 2026-04-28 12:00:00\n### Task#1: test -> Done\n**实施内容**: work\n### 本次踩坑/经验\n{content}\n"

    def test_aggregate_from_moved_files(self, tmp_project_dir):
        """moved file 含踩坑数据时正确聚合到 project-pitfalls.md。"""
        diwu = tmp_project_dir / ".diwu"
        diwu.mkdir(exist_ok=True)
        (diwu / "dsettings.toml").write_text(
            'task_archive_limit = 999\n'
            'recording_file_limit = 2\n'
            'recording_keep_days = 1\n'
        )

        rec_dir = diwu / "recording"
        rec_dir.mkdir(exist_ok=True)

        # 创建带踩坑的 session 文件
        pitfall_content = "- [环境漂移] CI 超时 → 缺代理配置 → 误判为性能问题 → 先检查环境变量\n"
        session_text = self._make_session_with_pitfalls(pitfall_content, "session-2026-04-28-120000.md")
        f = rec_dir / "session-2026-04-28-120000.md"
        f.write_text(session_text)
        old_time = time.time() - (2 * 86400)
        os.utime(str(f), (old_time, old_time))

        # 再创建一个文件满足 threshold
        f2 = rec_dir / "session-2026-04-29-120000.md"
        f2.write_text("# empty session")
        os.utime(str(f2), (old_time, old_time))

        rc, out, _ = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        assert data["ok"] is True
        assert data["pitfalls_aggregated"] >= 1

        # 验证 project-pitfalls.md 存在且含聚合内容
        pitfalls_path = diwu / "project-pitfalls.md"
        assert pitfalls_path.exists()
        content = pitfalls_path.read_text(encoding="utf-8")
        assert "环境漂移" in content
        assert "session-2026-04-28-120000.md" in content  # 来源列规范

    def test_no_pitfalls_skip(self, tmp_project_dir):
        """session 文件无踩坑数据（最低合法答案）时跳过聚合。"""
        diwu = tmp_project_dir / ".diwu"
        diwu.mkdir(exist_ok=True)
        (diwu / "dsettings.toml").write_text(
            'task_archive_limit = 999\n'
            'recording_file_limit = 2\n'
            'recording_keep_days = 1\n'
        )

        rec_dir = diwu / "recording"
        rec_dir.mkdir(exist_ok=True)

        # 使用最低合法答案
        minimal = "本轮无显著误判，实施路径符合预期。\n"
        session_text = self._make_session_with_pitfalls(minimal, "session-2026-05-01-100000.md")
        f = rec_dir / "session-2026-05-01-100000.md"
        f.write_text(session_text)
        old_time = time.time() - (2 * 86400)
        os.utime(str(f), (old_time, old_time))

        f2 = rec_dir / "session-2026-05-02-100000.md"
        f2.write_text("# another")
        os.utime(str(f2), (old_time, old_time))

        rc, out, _ = run_script("drec_archive.py", "run", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        assert data["ok"] is True
        assert data["pitfalls_aggregated"] == 0  # 最低合法答案不应被聚合
