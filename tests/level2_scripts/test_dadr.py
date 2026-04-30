"""scripts/dadr.py 测试。

覆盖：next-number（空目录/有文件/跳号）/ create（首次/指定编号/README 缺失重建/
重复编号）/ update-status（正常/不存在）/ README 索引格式。
I2: CLI-first subprocess 调用。
"""

import json
from pathlib import Path

import pytest
from conftest import run_script  # noqa: E402


class TestDadrNextNumber:
    def test_empty_dir(self, tmp_project_dir):
        rc, out, err = run_script("dadr.py", "next-number", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["data"]["next_number"] == 1
        assert data["data"]["formatted"] == "ADR-001"

    def test_with_existing_adrs(self, tmp_project_dir):
        adr_dir = tmp_project_dir / ".doc" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "ADR-001-test.md").write_text("# ADR-001")
        (adr_dir / "ADR-003-other.md").write_text("# ADR-003")

        rc, out, err = run_script("dadr.py", "next-number", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["data"]["next_number"] == 4  # max(1,3) + 1


class TestDadrCreate:
    def test_create_first_adr(self, tmp_project_dir):
        rc, out, err = run_script(
            "dadr.py", "create",
            "--title", "使用 PostgreSQL 替代 SQLite",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "created"
        assert data["data"]["number"] == 1
        assert data["data"]["formatted"] == "ADR-001"

        # 验证文件存在且含骨架关键字
        adr_file = Path(data["data"]["file"])
        assert adr_file.exists()
        content = adr_file.read_text()
        assert "ADR-001" in content
        assert "**Status**: Proposed" in content
        assert "## Context" in content
        assert "## Options Considered" in content

        # 验证 README 已创建
        readme = adr_file.parent / "README.md"
        assert readme.exists()
        readme_content = readme.read_text()
        assert "ADR-001" in readme_content
        assert "PostgreSQL" in readme_content

    def test_create_with_number(self, tmp_project_dir):
        rc, out, err = run_script(
            "dadr.py", "create",
            "--title", "引入 Redis 缓存",
            "--number", "5",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["data"]["number"] == 5
        assert data["data"]["formatted"] == "ADR-005"
        assert len(list((tmp_project_dir / ".doc" / "adr").glob("ADR-005-*.md"))) >= 1

    def test_create_rebuilds_missing_readme(self, tmp_project_dir):
        """T11: README 缺失时扫描现有 ADR 重建索引。"""
        adr_dir = tmp_project_dir / ".doc" / "adr"
        adr_dir.mkdir(parents=True)

        # 先手动创建一个 ADR（模拟已有记录）
        existing = adr_dir / "ADR-002-old-decision.md"
        existing.write_text("# ADR-002: Old Decision\n\n**Status**: Accepted\n\n## Context\nOld stuff\n")

        # 不创建 README — create 应自动重建
        rc, out, err = run_script(
            "dadr.py", "create",
            "--title", "新决策",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True

        # README 应包含旧 ADR 和新 ADR 两行
        readme = adr_dir / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert "ADR-002" in content
        assert "ADR-003" in content  # 新的应该是 003（max=2 + 1）

    def test_create_duplicate_rejected(self, tmp_project_dir):
        """重复编号应返回错误。"""
        # 先创建一个
        run_script("dadr.py", "create", "--title", "First", "--cwd", str(tmp_project_dir))

        # 再尝试用相同编号创建
        rc, out, err = run_script(
            "dadr.py", "create",
            "--title", "Duplicate",
            "--number", "1",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is False
        assert data["status"] == "file_exists"


class TestDadrUpdateStatus:
    def test_update_status_success(self, tmp_project_dir):
        # 先创建
        run_script("dadr.py", "create", "--title", "Test ADR", "--cwd", str(tmp_project_dir))

        rc, out, err = run_script(
            "dadr.py", "update-status",
            "--number", "1",
            "--status", "Accepted",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["data"]["new_status"] == "Accepted"

        # 验证文件已更新
        adr_files = list((tmp_project_dir / ".doc" / "adr").glob("ADR-001-*.md"))
        assert len(adr_files) == 1
        content = adr_files[0].read_text()
        assert "**Status**: Accepted" in content

        # 验证 README 同步更新
        readme = (tmp_project_dir / ".doc" / "adr" / "README.md")
        if readme.exists():
            readme_content = readme.read_text()
            assert "Accepted" in readme_content

    def test_update_status_not_found(self, tmp_project_dir):
        rc, out, err = run_script(
            "dadr.py", "update-status",
            "--number", "99",
            "--status", "Accepted",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is False
        assert data["status"] == "not_found"


class TestDadrFormattedText:
    """验证 formatted_text 字段存在性。"""

    def test_create_has_formatted_text(self, tmp_project_dir):
        rc, out, err = run_script(
            "dadr.py", "create",
            "--title", "Formatted test",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert "formatted_text" in data
        assert "📝" in data["formatted_text"]
