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
                assert target.startswith("../../skills/")


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
