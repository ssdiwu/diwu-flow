"""scripts/common.py 单元测试

覆盖：plugin_root / load_json_optional / load_json_or_empty / save_json
      / ensure_dir / rel_time / error_exit / max_task_id (CLI)
"""

import json
import os
import sys
from pathlib import Path

import pytest

# 确保 scripts/ 在 import 路径中（单元测试直接 import，不经过 subprocess）
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import common  # noqa: E402
from conftest import assert_rel_time_shape, run_script  # noqa: E402


class TestPluginRoot:
    def test_returns_path(self):
        root = common.plugin_root()
        assert isinstance(root, Path)
        assert root.is_dir()

    def test_points_to_project_root(self):
        root = common.plugin_root()
        # scripts/ 的父目录应包含 commands/ 或 skills/
        assert (root / "commands").is_dir() or (root / "skills").is_dir()


class TestLoadJsonOptional:
    def test_file_not_exists_returns_default(self, tmp_path):
        missing = tmp_path / "no_such.json"
        result = common.load_json_optional(missing, default={"key": "val"})
        assert result == {"key": "val"}

    def test_file_not_exists_none_default(self, tmp_path):
        missing = tmp_path / "no_such.json"
        result = common.load_json_optional(missing, default=None)
        assert result is None

    def test_valid_json(self, tmp_path):
        f = tmp_path / "good.json"
        f.write_text(json.dumps({"a": 1}, ensure_ascii=False))
        result = common.load_json_optional(f)
        assert result == {"a": 1}

    def test_corrupted_json_exits(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{broken")
        with pytest.raises(SystemExit) as exc_info:
            common.load_json_optional(f)
        assert exc_info.value.code == 1


class TestLoadJsonOrEmpty:
    def test_file_not_exists_returns_empty_dict(self, tmp_path):
        missing = tmp_path / "no_such.json"
        result = common.load_json_or_empty(missing)
        assert result == {}

    def test_valid_json(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text(json.dumps([1, 2, 3]))
        result = common.load_json_or_empty(f)
        assert result == [1, 2, 3]


class TestSaveJson:
    def test_write_and_read_back(self, tmp_path):
        dest = tmp_path / "out.json"
        data = {"num": 42, "text": "你好"}
        common.save_json(data, dest)
        assert dest.exists()
        with open(dest, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_indent_two(self, tmp_path):
        dest = tmp_path / "pretty.json"
        common.save_json({"a": 1}, dest)
        text = dest.read_text(encoding="utf-8")
        # indent=2 应产生多行输出（非单行压缩）
        assert "\n" in text
        lines = text.strip().split("\n")
        assert len(lines) > 1

    def test_ensure_ascii_false(self, tmp_path):
        dest = tmp_path / "unicode.json"
        common.save_json({"msg": "中文测试"}, dest)
        text = dest.read_text(encoding="utf-8")
        assert "中文测试" in text

    def test_creates_parent_dir(self, tmp_path):
        dest = tmp_path / "sub" / "deep" / "out.json"
        common.save_json({}, dest)
        assert dest.exists()

    def test_atomic_replace(self, tmp_path):
        """T7: 验证写入是原子的（不应出现半写文件）。"""
        dest = tmp_path / "atomic.json"
        for i in range(20):
            common.save_json({"iter": i}, dest)
            with open(dest, encoding="utf-8") as f:
                data = json.load(f)
            # 每次读取都应是完整 JSON
            assert data == {"iter": i}


class TestEnsureDir:
    def test_creates_dir(self, tmp_path):
        d = tmp_path / "new_dir"
        common.ensure_dir(d)
        assert d.is_dir()

    def test_idempotent(self, tmp_path):
        d = tmp_path / "existing"
        d.mkdir()
        common.ensure_dir(d)  # 不应抛异常
        assert d.is_dir()


class TestRelTime:
    def test_just_now(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        result = common.rel_time(now)
        assert result == "刚刚"

    def test_shape_minutes(self):
        assert_rel_time_shape(common.rel_time("刚刚"))

    def test_raw_string_passthrough(self):
        bad = "not-a-date"
        result = common.rel_time(bad)
        assert result == bad


class TestMaxTaskIdCLI:
    def test_empty_project(self, tmp_project_dir):
        rc, out, err = run_script("common.py", "--max-task-id", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["max_id"] == 0
        assert data["source"] == "empty"

    def test_with_dtask_json(self, tmp_project_dir):
        dtask = tmp_project_dir / ".diwu" / "dtask.json"
        dtask.write_text(json.dumps({
            "tasks": [
                {"id": 3, "title": "t3", "status": "Done"},
                {"id": 7, "title": "t7", "status": "InProgress"},
            ]
        }, ensure_ascii=False, indent=2))
        rc, out, err = run_script("common.py", "--max-task-id", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["max_id"] == 7
        assert data["source"] == "dtask.json"

    def test_with_archive_higher_id(self, tmp_project_dir):
        # dtask.json has id=3, archive has id=5 → should pick 5
        dtask = tmp_project_dir / ".diwu" / "dtask.json"
        dtask.write_text(json.dumps({
            "tasks": [{"id": 3, "title": "t3", "status": "Done"}]
        }, ensure_ascii=False, indent=2))

        archive_dir = tmp_project_dir / ".diwu" / "archive"
        archive_dir.mkdir()
        archive_file = archive_dir / "task_archive_2026-04.json"
        archive_file.write_text(json.dumps({
            "tasks": [{"id": 5, "title": "t5", "status": "Done"}]
        }, ensure_ascii=False, indent=2))

        rc, out, err = run_script("common.py", "--max-task-id", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["max_id"] == 5
        assert "archive" in data["source"]

    def test_corrupted_dtask_json(self, tmp_project_dir):
        dtask = tmp_project_dir / ".diwu" / "dtask.json"
        dtask.write_text("{broken json")
        rc, out, err = run_script("common.py", "--max-task-id", "--cwd", str(tmp_project_dir))
        assert rc == 1  # exit 1 on corruption
        data = json.loads(out)
        assert data["ok"] is False
        assert "损坏" in data.get("error", "")
