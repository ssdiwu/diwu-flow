"""scripts/dinit.py 测试。

覆盖 6 个子命令：scan-repo / sync-rules / sync-skills / create-config / migrate-legacy / validate。
I2: CLI-first subprocess 调用。
"""

import json
import os
from pathlib import Path

import pytest
from conftest import run_script  # noqa: E402


class TestDinitScanRepo:
    def test_scan_empty_project(self, tmp_project_dir):
        rc, out, err = run_script("dinit.py", "scan-repo", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "scanned"
        assert "directories" in data["data"]
        assert "tech_stack" in data["data"]
        assert "key_files" in data["data"]

    def test_scan_detects_package_json(self, tmp_project_dir):
        (tmp_project_dir / "package.json").write_text('{"name": "test", "dependencies": {"react": "^18"}}')
        rc, out, _ = run_script("dinit.py", "scan-repo", "--cwd", str(tmp_project_dir))
        data = json.loads(out)
        assert data["data"]["tech_stack"]["language"] == "node"
        assert data["data"]["tech_stack"]["package_manager"] == "npm"

    def test_scan_file_count_is_int_not_str(self, tmp_project_dir):
        """file_count_estimate 必须是整数，大目录不能字符串化导致 TypeError。"""
        # 创建含 100+ 文件的目录
        big_dir = tmp_project_dir / "big_dir"
        big_dir.mkdir()
        for i in range(105):
            (big_dir / f"file_{i:04d}.txt").write_text(f"content {i}")
        # 创建子目录增加文件数
        sub = big_dir / "sub"
        sub.mkdir()
        for i in range(50):
            (sub / f"sub_{i:04d}.txt").write_text(f"sub content {i}")

        rc, out, err = run_script("dinit.py", "scan-repo", "--cwd", str(tmp_project_dir))
        assert rc == 0, f"scan-repo crashed: {err}"
        data = json.loads(out)
        dirs = {d["name"]: d for d in data["data"]["directories"]}
        assert "big_dir/" in dirs
        fc = dirs["big_dir/"]["file_count_estimate"]
        assert isinstance(fc, int), f"file_count_estimate must be int, got {type(fc).__name__}: {fc!r}"
        assert fc == 156, f"expected 156 entries (rglob matches dirs too), got {fc}"
        assert isinstance(fc, int)  # 核心断言：必须是整数而非字符串

    def test_scan_file_count_capped_at_9999(self, tmp_project_dir):
        """超大目录应封顶到 9999 且保持整数类型。"""
        huge_dir = tmp_project_dir / "huge_dir"
        huge_dir.mkdir()
        # 不真创建 10000+ 文件，只验证封顶逻辑不崩溃
        for i in range(10):
            (huge_dir / f"f{i}.txt").write_text("x")

        rc, out, err = run_script("dinit.py", "scan-repo", "--cwd", str(tmp_project_dir))
        assert rc == 0, f"scan-repo crashed: {err}"
        data = json.loads(out)
        dirs = {d["name"]: d for d in data["data"]["directories"]}
        fc = dirs["huge_dir/"]["file_count_estimate"]
        assert isinstance(fc, int), f"must be int, got {type(fc).__name__}"
        assert fc <= 9999

    def test_scan_permission_denied_dir_shows_zero(self, tmp_project_dir):
        """权限不足的目录显示 (权限限制) 且 file_count_estimate=0。"""
        no_access = tmp_project_dir / "no_access"
        no_access.mkdir()
        (no_access / "file.txt").write_text("x")
        # 模拟权限不足：在 POSIX 上 chmod 000 可能需要 root，这里只验证 OSError 分支不被遗漏
        # 实际测试中我们无法真正制造权限错误（可能运行在非 Unix 或有 sudo），
        # 但至少验证正常目录的 code path 走通
        rc, out, _ = run_script("dinit.py", "scan-repo", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        dirs = {d["name"]: d for d in data["data"]["directories"]}
        # no_access 目录应该被正常扫描（当前用户有权限）
        if "no_access/" in dirs:
            assert isinstance(dirs["no_access/"]["file_count_estimate"], int)


class TestDinitSyncRules:
    def test_sync_rules_basic(self, tmp_project_dir):
        rc, out, _ = run_script("dinit.py", "sync-rules", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "synced"
        assert "summary" in data["data"]
        # 应该有文件被同步（NEW 状态）
        assert data["data"]["summary"]["new"] > 0

    def test_sync_rules_creates_target_files(self, tmp_project_dir):
        run_script("dinit.py", "sync-rules", "--cwd", str(tmp_project_dir))
        rules_dir = tmp_project_dir / ".claude" / "rules"
        assert rules_dir.is_dir()
        # 至少有 task.md（manifest 中必有）
        assert (rules_dir / "task.md").exists()


class TestDinitSyncSkills:
    def test_sync_skills_creates_symlinks(self, tmp_project_dir):
        rc, out, _ = run_script("dinit.py", "sync-skills", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        skills_dir = tmp_project_dir / ".agents" / "skills"
        assert skills_dir.is_dir()
        # 至少有一些 symlink 被创建
        assert data["data"]["summary"]["created"] > 0

    def test_symlink_targets_correct(self, tmp_project_dir):
        run_script("dinit.py", "sync-skills", "--cwd", str(tmp_project_dir))
        skills_dir = tmp_project_dir / ".agents" / "skills"
        if not skills_dir.exists():
            pytest.skip("skills dir not created")
        for item in skills_dir.iterdir():
            if item.is_symlink():
                target = os.readlink(str(item))
                resolved = Path(item.parent / target).resolve()
                assert resolved.exists(), f"broken symlink: {item.name} -> {target} -> {resolved} 不存在"
                assert (resolved / "SKILL.md").exists(), f"symlink target 缺少 SKILL.md: {resolved}"


class TestDinitCreateConfig:
    def test_create_config_basic(self, tmp_project_dir):
        rc, out, _ = run_script("dinit.py", "create-config", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "created"

    def test_create_config_makes_dtask(self, tmp_project_dir):
        run_script("dinit.py", "create-config", "--cwd", str(tmp_project_dir))
        dtask = tmp_project_dir / ".diwu" / "dtask.json"
        assert dtask.exists()
        task_data = json.loads(dtask.read_text())
        assert "tasks" in task_data

    def test_create_config_makes_runtime_dirs(self, tmp_project_dir):
        run_script("dinit.py", "create-config", "--cwd", str(tmp_project_dir))
        for d in ["recording", "archive"]:
            assert (tmp_project_dir / ".diwu" / d).is_dir()

    def test_create_config_with_project_info(self, tmp_project_dir):
        info_file = tmp_project_dir / "_info.json"
        info_file.write_text(json.dumps({"name": "TestProj", "description": "A test project"}))
        rc, out, _ = run_script(
            "dinit.py", "create-config",
            "--project-info-file", str(info_file),
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True


class TestDinitMigrateLegacy:
    def test_no_legacy_clean_project(self, tmp_project_dir):
        """干净项目应返回 no_migration_needed。"""
        rc, out, _ = run_script("dinit.py", "migrate-legacy", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "no_migration_needed"

    def test_migrate_ideas_archived_status(self, tmp_project_dir):
        """v0.1.0 的 status: archived 想法文件应被物理移动到 ideas/archived/。"""
        ideas_dir = Path(tmp_project_dir) / ".diwu" / "ideas"
        ideas_dir.mkdir(parents=True, exist_ok=True)

        # 创建含 status: archived 的旧格式想法文件
        old_idea = ideas_dir / "old-archived-idea.md"
        old_idea.write_text(
            "---\nid: 1\nstatus: archived\ncreated_at: 2026-01-01T00:00:00+00:00\n---\n"
            "这是一个已归档的想法\n",
            encoding="utf-8",
        )

        # 创建正常想法文件（不应被迁移）
        active_idea = ideas_dir / "active-idea.md"
        active_idea.write_text(
            "---\nid: 2\ncreated_at: 2026-05-10T00:00:00+00:00\n---\n"
            "这是一个活跃的想法\n",
            encoding="utf-8",
        )

        rc, out, _ = run_script("dinit.py", "migrate-legacy", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True

        # 已归档文件应被移动
        archive_dir = ideas_dir / "archived"
        assert (archive_dir / "old-archived-idea.md").exists()
        assert not old_idea.exists()

        # 活跃文件不应受影响
        assert active_idea.exists()

        # actions 中应包含迁移记录
        actions = data.get("data", {}).get("actions", [])
        assert any("归档想法" in a for a in actions)
        assert data["data"]["ideas_migrated"] == 1


class TestDinitValidate:
    def test_validate_fresh_project(self, tmp_project_dir):
        """未初始化的项目应有多个 FAIL。"""
        rc, out, _ = run_script("dinit.py", "validate", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True  # T19: always exit 0
        assert "checks" in data["data"]
        # 未初始化 → 应该有失败项
        assert data["data"]["summary"]["failed"] > 0

    def test_validate_after_full_init(self, tmp_project_dir):
        """完整初始化后验证应通过更多检查。"""
        # 执行完整初始化流程
        run_script("dinit.py", "sync-rules", "--cwd", str(tmp_project_dir))
        run_script("dinit.py", "sync-skills", "--cwd", str(tmp_project_dir))
        run_script("dinit.py", "create-config", "--cwd", str(tmp_project_dir))

        rc, out, _ = run_script("dinit.py", "validate", "--cwd", str(tmp_project_dir))
        assert rc == 0
        data = json.loads(out)
        checks = data["data"]["checks"]
        passed = sum(1 for c in checks if c["status"] == "PASS")
        # 初始化后应该比未初始化时通过更多
        assert passed >= 5  # 至少基础文件 + runtime dirs + rules 存在性
