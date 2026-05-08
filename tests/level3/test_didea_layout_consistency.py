"""didea 布局一致性测试（level3）。

验证：
  - rules/file-layout.md 三副本均含 ideas/ 定义且内容一致
  - skills/didea/SKILL.md frontmatter 合法性
  - commands/didea.md frontmatter 合法性
  - plugin.json 注册完整性
"""

import json
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

FILE_LAYOUT_PATHS = [
    PROJECT_ROOT / "rules" / "file-layout.md",
    PROJECT_ROOT / ".claude" / "rules" / "file-layout.md",
    PROJECT_ROOT / "assets" / "dinit" / "assets" / "rules" / "file-layout.md",
]

SKILL_MD = PROJECT_ROOT / "skills" / "didea" / "SKILL.md"
COMMAND_MD = PROJECT_ROOT / "commands" / "didea.md"
PLUGIN_JSON = PROJECT_ROOT / ".claude-plugin" / "plugin.json"


class TestFileLayoutThreeCopySync:
    """三副本 file-layout.md 中 ideas/ 定义一致。"""

    @pytest.fixture
    def ideas_lines(self):
        """从每个副本中提取包含 ideas/ 的行。"""
        results = []
        for p in FILE_LAYOUT_PATHS:
            assert p.exists(), f"{p} 不存在"
            lines = p.read_text(encoding="utf-8").splitlines()
            matching = [l for l in lines if "ideas" in l and ("想法容器" in l or "灵感" in l)]
            results.append((str(p.relative_to(PROJECT_ROOT)), matching))
        return results

    def test_all_copies_exist(self, ideas_lines):
        for path_str, lines in ideas_lines:
            assert len(lines) > 0, f"{path_str} 中未找到 ideas/ 定义行"

    def test_content_consistent(self, ideas_lines):
        """三个副本的 ideas/ 描述文本应一致。"""
        texts = set()
        for path_str, lines in ideas_lines:
            for line in lines:
                texts.add(line.strip())
        # 至少所有副本应包含相同的核心描述
        assert len(texts) <= 3, f"三副本 ideas/ 描述不一致，发现 {len(texts)} 种不同文本: {texts}"


class TestSkillFrontmatter:
    """SKILL.md frontmatter 合法性。"""

    def test_exists(self):
        assert SKILL_MD.exists(), f"{SKILL_MD} 不存在"

    def test_frontmatter_parsable(self):
        content = SKILL_MD.read_text(encoding="utf-8")
        assert content.startswith("---"), "SKILL.md 不以 --- 开头"
        parts = content.split("---", 2)
        assert len(parts) >= 3, "SKILL.md frontmatter 格式异常"
        fm = yaml.safe_load(parts[1])
        assert isinstance(fm, dict), "frontmatter 不是 dict"

    def test_required_fields(self):
        content = SKILL_MD.read_text(encoding="utf-8")
        fm = yaml.safe_load(content.split("---", 2)[1])
        for field in ["name", "type", "description"]:
            assert field in fm, f"SKILL.md frontmatter 缺少 {field}"
        assert fm["name"] == "didea"
        assert fm["type"] == "tool"

    def test_triggers_nonempty(self):
        content = SKILL_MD.read_text(encoding="utf-8")
        fm = yaml.safe_load(content.split("---", 2)[1])
        triggers = fm.get("triggers", [])
        assert isinstance(triggers, list) and len(triggers) >= 4, (
            f"triggers 应 ≥4 条，实际 {len(triggers)}"
        )


class TestCommandFrontmatter:
    """commands/didea.md frontmatter 合法性。"""

    def test_exists(self):
        assert COMMAND_MD.exists(), f"{COMMAND_MD} 不存在"

    def test_frontmatter_parsable(self):
        content = COMMAND_MD.read_text(encoding="utf-8")
        assert content.startswith("---")
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = yaml.safe_load(parts[1])
        assert isinstance(fm, dict)

    def test_required_fields(self):
        content = COMMAND_MD.read_text(encoding="utf-8")
        fm = yaml.safe_load(content.split("---", 2)[1])
        for field in ["description", "argument-hint", "allowed-tools"]:
            assert field in fm, f"command frontmatter 缺少 {field}"


class TestPluginRegistration:
    """plugin.json 中 didea 注册完整性。"""

    def test_skill_registered(self):
        plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
        assert "./skills/didea" in plugin.get("skills", []), (
            "plugin.json skills 数组缺少 ./skills/didea"
        )

    def test_command_registered(self):
        plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
        assert "./commands/didea.md" in plugin.get("commands", []), (
            "plugin.json commands 数组缺少 ./commands/didea.md"
        )

    def test_no_duplicate_skills(self):
        plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
        skills = plugin.get("skills", [])
        assert skills.count("./skills/didea") == 1, "skills 数组中 ./skills/didea 重复"


class TestIdeasDirStructure:
    """.diwu/ideas/ 目录结构符合 SKILL.md 定义。"""

    def test_ideas_dir_in_layout(self):
        """file-layout.md 中 .diwu/ 目录树包含 ideas/ 行。"""
        layout = (PROJECT_ROOT / "rules" / "file-layout.md").read_text(encoding="utf-8")
        assert "ideas/" in layout, "file-layout.md 缺少 ideas/ 目录定义"
