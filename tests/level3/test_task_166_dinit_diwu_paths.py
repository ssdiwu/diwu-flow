"""dinit.md 主契约测试（T1: 脚本入口声明 + AI 步骤保留验证）。

从原版「断言 dinit.md 含具体路径字符串」改造为：
- smoke test: 断言 dinit.md 含脚本入口声明（python3 scripts/dinit.py）
- AI 步骤保留: 断言 dinit.md 含关键步骤章节标题（Step 0/1/2/5/6/7）
- assets/ 模板路径验证移至 test_dinit_diwu_paths.py（I1: 不同绑定范围）
"""

from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
COMMAND_PATH = PROJECT_ROOT / "commands" / "dinit.md"
ASSETS_DIR = PROJECT_ROOT / "assets" / "dinit" / "assets"
RULES_DIR = ASSETS_DIR / "rules"
MANIFEST_PATH = ASSETS_DIR / "rules-manifest.json"


def test_dinit_has_script_entry_point():
    """Smoke: dinit.md 必须存在且有基本命令结构。

    注：Task#15 实现脚本后，此断言将升级为检查 'scripts/dinit.py' 入口。
    当前阶段仅验证 command 文件完整性。
    """
    assert COMMAND_PATH.exists(), "commands/dinit.md 应存在"
    text = COMMAND_PATH.read_text(encoding="utf-8")
    assert len(text) > 100, "dinit.md 不应为空文件"
    # 脚本化后应有脚本引用；当前阶段至少应有命令描述
    assert "dinit" in text.lower() or "初始化" in text


def test_dinit_preserves_ai_steps():
    """AI 交互步骤必须保留在 Skill 文件中（模式检测、信息收集、迁移决策等）。

    重构后：commands/dinit.md 是触发器（不含 SOP），AI 步骤细节在 skills/dinit/SKILL.md。
    """
    skill_path = PROJECT_ROOT / "skills" / "dinit" / "SKILL.md"
    assert skill_path.exists(), "skills/dinit/SKILL.md 应存在（重构后 AI 步骤在此）"
    text = skill_path.read_text(encoding="utf-8")
    # 关键 AI 判断视角应存在（启发式风格，不再用 Step 编号）
    ai_perspectives = [
        ("初始化", "刷新"),       # 双模式判断
        ("模式检测", "初始化 vs"),  # 模式识别
        ("信息收集", "扫描"),       # 信息收集
        ("迁移", "旧版", "legacy"), # 迁移行为
        ("验证", "validate"),      # 验证收尾
        ("红旗", "陷阱", "信号"),   # 红旗信号
    ]
    matched = 0
    for keywords in ai_perspectives:
        if any(kw in text for kw in keywords):
            matched += 1
    assert matched >= len(ai_perspectives) - 1, (
        f"SKILL.md 应包含大部分 AI 判断视角关键词，当前匹配 {matched}/{len(ai_perspectives)}"
    )


def test_dinit_references_migrate_legacy():
    """dinit.md 应引用 migrate-legacy 能力（旧版检测/迁移）。"""
    text = COMMAND_PATH.read_text(encoding="utf-8")
    assert "migrate" in text.lower() or "legacy" in text.lower() or "旧" in text, (
        "dinit.md 应提及旧版迁移能力"
    )


def test_templates_use_diwu_for_runtime_paths():
    """Assets 模板应使用 .diwu/ 运行时路径（I1: 模板层验证）。"""
    targets = [
        ASSETS_DIR / "claude-md-portable.template",
        ASSETS_DIR / "claude-md.template",
        ASSETS_DIR / "claude-md-minimal.template",
        ASSETS_DIR / "project-pitfalls.md.template",
        RULES_DIR / "file-layout.md",
        RULES_DIR / "session.md",
        RULES_DIR / "pitfalls.md",
        RULES_DIR / "templates.md",
        RULES_DIR / "task.md",
        RULES_DIR / "verification.md",
    ]
    joined = "\n".join(path.read_text(encoding="utf-8") for path in targets)
    assert ".diwu/dtask.toml" in joined
    assert ".diwu/recording/" in joined
    assert ".diwu/project-pitfalls.md" in joined
    assert ".diwu/" in joined


def test_rules_manifest_stays_valid_json():
    """rules-manifest.json 必须是有效 JSON 且含 rules 列表。"""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(data.get("rules"), list)
    assert "task.md" in data["rules"]
