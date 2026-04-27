from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
COMMAND_PATH = PROJECT_ROOT / "commands" / "dinit.md"
ASSETS_DIR = PROJECT_ROOT / "assets" / "dinit" / "assets"
RULES_DIR = ASSETS_DIR / "rules"
AGENTS_DIR = ASSETS_DIR / "agents"
MANIFEST_PATH = ASSETS_DIR / "rules-manifest.json"

RUNTIME_PATHS = [
    ".diwu/dtask.json",
    ".diwu/recording/",
    ".diwu/decisions.md",
    ".diwu/dsettings.json",
    ".diwu/project-pitfalls.md",
    ".diwu/continue-here.md",
    ".diwu/archive/",
    ".diwu/checks/",
]
OLD_RUNTIME_PATHS = [
    ".claude/recording/",
    ".claude/decisions.md",
    ".claude/dsettings.json",
    ".claude/project-pitfalls.md",
    ".claude/archive/",
    ".claude/continue-here.md",
]


def test_dinit_moves_runtime_outputs_to_diwu():
    text = COMMAND_PATH.read_text(encoding="utf-8")
    for expected in RUNTIME_PATHS:
        assert expected in text
    assert "lessons.md" not in text


def test_dinit_documents_legacy_runtime_migration_detection():
    text = COMMAND_PATH.read_text(encoding="utf-8")
    assert "`.diwu/` 是否**不存在**" in text
    assert "输出迁移指引或执行自动迁移" in text
    for expected in OLD_RUNTIME_PATHS:
        assert expected in text


def test_templates_use_diwu_for_runtime_paths():
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
        RULES_DIR / "workflow.md",
    ]
    joined = "\n".join(path.read_text(encoding="utf-8") for path in targets)
    assert ".diwu/dtask.json" in joined
    assert ".diwu/recording/" in joined
    # decisions.md 在 hook 脚本中引用，模板文件中不一定出现
    assert ".diwu/project-pitfalls.md" in joined
    # checks/ 在 hook 脚本和 session.md 中引用，CLAUDE.md 模板中不一定出现
    assert ".diwu/" in joined  # 至少有运行时路径前缀


def test_rules_manifest_stays_valid_json():
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(data.get("rules"), list)
    assert "task.md" in data["rules"]
