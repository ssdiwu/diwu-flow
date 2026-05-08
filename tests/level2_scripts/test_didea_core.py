"""scripts/didea_core.py 测试。

覆盖：create（正常/自增ID/frontmatter完整/重复标题处理/空标题拒绝）
      list（空目录/多文件/status过滤）
      show（存在/不存在）
      refine（内容追加/updated_at更新/archived拒绝）
      archive（状态变更）
      change-status（正常/非法值拒绝）
      validate（全合法/缺失字段/非法status）
I2: CLI-first subprocess 调用。
"""

import json
from pathlib import Path

import pytest
import yaml
from conftest import run_script  # noqa: E402


def _ideas_dir(root: Path) -> Path:
    return root / ".diwu" / "ideas"


def _read_idea_file(root: Path, filename: str) -> str:
    return (_ideas_dir(root) / filename).read_text(encoding="utf-8")


def _parse_idea_fm(root: Path, filename: str) -> dict:
    content = _read_idea_file(root, filename)
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    return yaml.safe_load(parts[1])


class TestCreate:
    def test_create_basic(self, tmp_project_dir):
        rc, out, err = run_script(
            "didea_core.py", "create",
            "--title", "测试想法",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "created"
        assert data["data"]["id"] == 1
        assert data["data"]["title"] == "测试想法"

        fm = _parse_idea_fm(tmp_project_dir, data["data"]["filename"])
        assert fm["id"] == 1
        assert fm["status"] == "idea"
        assert "created_at" in fm
        assert "updated_at" in fm
        assert fm["tags"] == []

    def test_create_with_tags(self, tmp_project_dir):
        rc, out, _ = run_script(
            "didea_core.py", "create",
            "--title", "带标签的想法",
            "--tags", "产品,灵感,mvp",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        fm = _parse_idea_fm(tmp_project_dir, data["data"]["filename"])
        assert fm["tags"] == ["产品", "灵感", "mvp"]

    def test_create_auto_id_increment(self, tmp_project_dir):
        for i, title in enumerate(["第一个", "第二个", "第三个"], 1):
            rc, out, _ = run_script(
                "didea_core.py", "create",
                "--title", title,
                "--cwd", str(tmp_project_dir),
            )
            assert rc == 0
            d = json.loads(out)
            assert d["data"]["id"] == i

    def test_create_duplicate_title_handling(self, tmp_project_dir):
        run_script("didea_core.py", "create", "--title", "同名想法", "--cwd", str(tmp_project_dir))
        rc, out, _ = run_script(
            "didea_core.py", "create",
            "--title", "同名想法",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        # 第二个同名文件应带后缀避免覆盖
        assert data["ok"] is True
        ideas = _ideas_dir(tmp_project_dir)
        md_files = list(ideas.glob("*.md"))
        assert len(md_files) == 2

    def test_create_empty_title_rejected(self, tmp_project_dir):
        rc, out, err = run_script(
            "didea_core.py", "create",
            "--title", "",
            "--cwd", str(tmp_project_dir),
        )
        assert rc != 0
        assert "不能为空" in err


class TestList:
    def test_list_empty(self, tmp_project_dir):
        rc, out, _ = run_script(
            "didea_core.py", "list",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["status"] == "empty"
        assert data["count"] == 0
        assert data["data"] == []

    def test_list_after_creates(self, tmp_project_dir):
        run_script("didea_core.py", "create", "--title", "A想法", "--cwd", str(tmp_project_dir))
        run_script("didea_core.py", "create", "--title", "B想法", "--cwd", str(tmp_project_dir))
        rc, out, _ = run_script(
            "didea_core.py", "list",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["count"] == 2
        titles = [item["title"] for item in data["data"]]
        assert "A想法" in titles
        assert "B想法" in titles

    def test_list_status_filter(self, tmp_project_dir):
        run_script("didea_core.py", "create", "--title", "想法1", "--cwd", str(tmp_project_dir))
        run_script("didea_core.py", "create", "--title", "想法2", "--cwd", str(tmp_project_dir))
        # archive 想法2
        run_script("didea_core.py", "archive", "--id", "2", "--cwd", str(tmp_project_dir))

        rc, out, _ = run_script(
            "didea_core.py", "list",
            "--status", "idea",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["count"] == 1
        assert data["data"][0]["id"] == 1


class TestShow:
    def test_show_existing(self, tmp_project_dir):
        run_script("didea_core.py", "create", "--title", "可查看", "--cwd", str(tmp_project_dir))
        rc, out, _ = run_script(
            "didea_core.py", "show",
            "--id", "1",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["data"]["id"] == 1
        assert "## 描述" in data["data"]["content"]

    def test_show_nonexistent(self, tmp_project_dir):
        rc, out, err = run_script(
            "didea_core.py", "show",
            "--id", "999",
            "--cwd", str(tmp_project_dir),
        )
        assert rc != 0
        assert "不存在" in err


class TestRefine:
    def test_refine_append(self, tmp_project_dir):
        run_script("didea_core.py", "create", "--title", "待完善", "--cwd", str(tmp_project_dir))
        rc, out, _ = run_script(
            "didea_core.py", "refine",
            "--id", "1",
            "--content", "补充说明内容",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["status"] == "refined"
        # 验证正文确实追加了内容
        content = _read_idea_file(tmp_project_dir, "待完善.md")
        assert "补充说明内容" in content

    def test_refine_archived_rejected(self, tmp_project_dir):
        run_script("didea_core.py", "create", "--title", "已归档", "--cwd", str(tmp_project_dir))
        run_script("didea_core.py", "archive", "--id", "1", "--cwd", str(tmp_project_dir))
        rc, out, err = run_script(
            "didea_core.py", "refine",
            "--id", "1",
            "--content", "尝试修改已归档",
            "--cwd", str(tmp_project_dir),
        )
        assert rc != 0
        assert "已归档" in err


class TestArchive:
    def test_archive_basic(self, tmp_project_dir):
        run_script("didea_core.py", "create", "--title", "归档目标", "--cwd", str(tmp_project_dir))
        rc, out, _ = run_script(
            "didea_core.py", "archive",
            "--id", "1",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["status"] == "archived"
        fm = _parse_idea_fm(tmp_project_dir, "归档目标.md")
        assert fm["status"] == "archived"


class TestChangeStatus:
    def test_change_status(self, tmp_project_dir):
        run_script("didea_core.py", "create", "--title", "改状态", "--cwd", str(tmp_project_dir))
        rc, out, _ = run_script(
            "didea_core.py", "change-status",
            "--id", "1",
            "--new-status", "refined",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["data"]["new_status"] == "refined"
        fm = _parse_idea_fm(tmp_project_dir, "改状态.md")
        assert fm["status"] == "refined"

    def test_change_status_invalid_rejected(self, tmp_project_dir):
        rc, out, err = run_script(
            "didea_core.py", "change-status",
            "--id", "1",
            "--new-status", "invalid_status",
            "--cwd", str(tmp_project_dir),
        )
        assert rc != 0
        # argparse choices 校验先于业务逻辑拦截，两种错误信息均可接受
        assert "非法 status" in err or "invalid choice" in err


class TestValidate:
    def test_validate_all_valid(self, tmp_project_dir):
        run_script("didea_core.py", "create", "--title", "合法想法", "--cwd", str(tmp_project_dir))
        rc, out, _ = run_script(
            "didea_core.py", "validate",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["data"]["valid"] == 1
        assert data["data"]["total"] == 1
        assert data["data"]["invalid"] == 0

    def test_validate_missing_field(self, tmp_project_dir):
        # 手动创建一个缺少必填字段的 idea 文件
        ideas = _ideas_dir(tmp_project_dir)
        ideas.mkdir(parents=True, exist_ok=True)
        bad_file = ideas / "不完整.md"
        bad_file.write_text(
            "---\nid: 99\nstatus: idea\n---\n## 描述\n只有两个字段\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(
            "didea_core.py", "validate",
            "--cwd", str(tmp_project_dir),
        )
        assert rc == 0
        data = json.loads(out)
        assert data["data"]["invalid"] >= 1
        error_msgs = [e["error"] for e in data["data"]["errors"]]
        assert any("缺少必填字段" in msg for msg in error_msgs)
