from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
ASSETS = PROJECT_ROOT / "assets" / "dinit" / "assets"
RULES = ASSETS / "rules"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_rules_manifest_description_mentions_claude_rules():
    manifest = json.loads(_read(ASSETS / "rules-manifest.json"))
    assert ".claude/rules/" in manifest["description"]
    assert ".diwu/rules/" not in manifest["description"]


def test_claude_templates_keep_claude_rule_paths_and_diwu_runtime_paths():
    targets = [
        ASSETS / "claude-md-portable.template",
        ASSETS / "claude-md.template",
        ASSETS / "claude-md-minimal.template",
    ]
    for path in targets:
        text = _read(path)
        assert ".claude/" in text, f"{path.name} 应保留 .claude/ 配置路径"
        assert ".diwu/" in text, f"{path.name} 应包含 .diwu/ 运行时路径"
        assert ".diwu/CLAUDE.md" not in text, f"{path.name} 不应再引用 .diwu/CLAUDE.md"
        assert ".diwu/rules/" not in text, f"{path.name} 不应把 .diwu/rules/ 写成主路径"


def test_rule_templates_with_runtime_paths_contain_diwu():
    """验证关键规则模板包含正确的路径引用"""
    # file-layout.md 描述 .diwu/ 运行时目录结构（已从 .claude/ 迁移至 .diwu/）
    file_layout = _read(RULES / "file-layout.md")
    assert ".diwu/" in file_layout
    assert "rules/" in file_layout
    # 不应再引用旧的 .claude/ 作为运行时路径（.claude-plugin 除外）
    assert ".claude/rules/" not in file_layout

    # CLAUDE.md 模板必须包含运行时路径 .diwu/
    for tmpl_name in ["claude-md-portable.template", "claude-md.template", "claude-md-minimal.template"]:
        text = _read(ASSETS / tmpl_name)
        assert ".diwu/" in text, f"{tmpl_name} 应包含 .diwu/ 运行时路径"


def test_rules_readme_describes_split_layout():
    text = _read(RULES / "README.md")
    # rules README 描述 .claude/ 下的目录结构（配置层）
    assert ".claude/" in text and "目录结构" in text


def test_no_lessons_template_exists():
    assert not (ASSETS / "lessons.md.template").exists()


def test_constraints_template_is_generic():
    text = _read(RULES / "constraints.md")
    assert text.startswith("# 架构约束")
    assert "diwu-workflow 架构约束" not in text
    assert "State Machines" not in text
    assert "Data Ownership" not in text
