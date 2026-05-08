"""scripts/didea_github.py 测试。

覆盖：push（确认拦截 / 不存在idea / 未认证 / 成功+url回写）
      pull（无关联url拒绝 / 成功拉取状态）

测试策略：
- 确认拦截、不存在idea、无关联 url：通过 subprocess CLI 测试（I2 约定）
- 需要 mock gh CLI 的场景：直接 import 函数单元测试（跨进程边界无法 patch subprocess.run）
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from conftest import run_script  # noqa: E402

# 直接导入待测函数（绕过 subprocess 边界，允许 mock）
sys_path = str(Path(__file__).parent.parent.parent / "scripts")
import sys
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

# 延迟导入避免 conftest 阶段副作用
def _import_github_module():
    import importlib
    return importlib.import_module("didea_github")


@pytest.fixture
def idea_for_push(tmp_project_dir):
    """创建一个可用于 push/pull 测试的 idea。"""
    rc, out, _ = run_script(
        "didea_core.py", "create",
        "--title", "推送目标",
        "--body", "这是描述内容用于 issue body",
        "--cwd", str(tmp_project_dir),
    )
    assert rc == 0
    data = json.loads(out)
    return data["data"]["id"], data["data"]["filename"]


def _read_idea_fm(tmp_project_dir, filename):
    content = (tmp_project_dir / ".diwu" / "ideas" / filename).read_text(encoding="utf-8")
    parts = content.split("---", 2)
    return yaml.safe_load(parts[1])


class TestPushCLI:
    """通过 subprocess CLI 测试不需要 mock 的路径。"""

    def test_push_requires_confirmation(self, idea_for_push, tmp_project_dir):
        idea_id, _ = idea_for_push
        rc, out, _ = run_script(
            "didea_github.py", "push",
            "--id", str(idea_id),
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["status"] == "confirmation_required"
        assert "确认后请加 --yes" in data["data"]["message"]

    def test_push_nonexistent_idea(self, tmp_project_dir):
        rc, out, err = run_script(
            "didea_github.py", "push",
            "--id", "999",
            "--yes",
            "--cwd", str(tmp_project_dir),
        )
        assert rc != 0
        assert "不存在" in err


class TestPushUnit:
    """直接 import 函数，mock gh CLI 测试核心逻辑。"""

    def test_push_success_url_writeback(self, idea_for_push, tmp_project_dir):
        mod = _import_github_module()
        idea_id, filename = idea_for_push

        with patch.object(mod, "_check_gh_auth", return_value=True), \
             patch.object(mod, "_gh_issue_create", return_value="https://github.com/test/repo/issues/42"):
            mod.cmd_push(
                type("Args", (), {"id": idea_id, "yes": True, "with_metadata": False})(),
                Path(str(tmp_project_dir)),
            )

        fm = _read_idea_fm(tmp_project_dir, filename)
        assert fm.get("github_issue_url") == "https://github.com/test/repo/issues/42"

    def test_push_no_auth_fails_unit(self, idea_for_push, tmp_project_dir):
        mod = _import_github_module()
        idea_id, _ = idea_for_push

        with patch.object(mod, "_check_gh_auth", return_value=False):
            with pytest.raises(SystemExit) as exc_info:
                mod.cmd_push(
                    type("Args", (), {"id": idea_id, "yes": True, "with_metadata": False})(),
                    Path(str(tmp_project_dir)),
                )
            assert exc_info.value.code == 1

    def test_push_with_metadata_in_body(self, idea_for_push, tmp_project_dir):
        mod = _import_github_module()
        idea_id, _ = idea_for_push

        captured_body = []

        def _capture_create(title, body):
            captured_body.append(body)
            return "https://github.com/test/repo/issues/1"

        with patch.object(mod, "_check_gh_auth", return_value=True), \
             patch.object(mod, "_gh_issue_create", side_effect=_capture_create), \
             patch.object(mod, "_update_fm_field", return_value="now"):
            mod.cmd_push(
                type("Args", (), {"id": idea_id, "yes": True, "with_metadata": True})(),
                Path(str(tmp_project_dir)),
            )

        assert len(captured_body) == 1
        assert "From diwu-flow idea" in captured_body[0]


class TestPullCLI:
    """通过 subprocess CLI 测试。"""

    def test_pull_no_url_rejected(self, idea_for_push, tmp_project_dir):
        idea_id, _ = idea_for_push
        rc, out, err = run_script(
            "didea_github.py", "pull",
            "--id", str(idea_id),
            "--cwd", str(tmp_project_dir),
        )
        assert rc != 0
        assert "未关联" in err


class TestPullUnit:
    """直接 import 函数测试 pull 逻辑。"""

    def test_pull_success_state(self, idea_for_push, tmp_project_dir):
        mod = _import_github_module()
        idea_id, filename = idea_for_push

        # 写入 github_issue_url
        fm = _read_idea_fm(tmp_project_dir, filename)
        fm["github_issue_url"] = "https://github.com/test/repo/issues/42"
        content = (tmp_project_dir / ".diwu" / "ideas" / filename).read_text(encoding="utf-8")
        parts = content.split("---", 2)
        new_fm = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()
        (tmp_project_dir / ".diwu" / "ideas" / filename).write_text(
            f"---\n{new_fm}\n---{parts[2]}", encoding="utf-8"
        )

        mock_view_result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout='{"state":"open","title":"推送目标","url":"https://github.com/test/repo/issues/42"}',
            stderr="",
        )

        with patch.object(mod, "_check_gh_auth", return_value=True), \
             patch("subprocess.run", return_value=mock_view_result):
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                mod.cmd_pull(
                    type("Args", (), {"id": idea_id})(),
                    Path(str(tmp_project_dir)),
                )
            data = json.loads(f.getvalue())
            assert data["status"] == "pulled"
            assert data["data"]["issue_state"] == "open"
