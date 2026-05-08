"""Layer 1: Agents 配置完整性测试 — 防止 regression 导致 agents 不加载

覆盖范围：
1. 统一 Agent（agents/）：5 个 Agent（explorer / implementer / verifier / architect / debugger）
2. Verifier 专项：frontmatter 完整性（tools/memory/maxTurns）
3. Model 合理性：每个核心 Agent 的 model 字段是否匹配其职责
4. Description 触发词：每个 description 是否包含触发词
5. plugin.json 声明：不声明 agents 字段（使用默认路径）、commands/skills 合法
"""
import json
import yaml
import pytest
from pathlib import Path


AGENTS_DIR = "agents"
ALL_AGENTS = ["explorer", "implementer", "verifier", "architect", "debugger"]

CORE_AGENT_MODEL_EXPECTATIONS = {
    "explorer": {"required_model": "haiku", "reason": "只读探索，必须用快速廉价模型"},
    "implementer": {"required_model": "sonnet", "reason": "代码实施，必须用质量保证模型"},
    "verifier": {"allowed_models": [None, "haiku", "sonnet", "inherit"], "reason": "独立验收需推理与验证能力（继承父会话）"},
    "architect": {"required_model": "sonnet", "reason": "技术审稿需要推理与分析能力"},
    "debugger": {"required_model": "sonnet", "reason": "异常诊断需要推理与运行诊断命令能力"},
}

AGENT_REQUIRED_FIELDS = {
    "explorer": ["tools"],
    "implementer": ["tools"],
    "verifier": ["tools"],
    "architect": ["tools"],
    "debugger": ["tools"],
}

VERIFIER_REQUIRED_TOOLS = {"Read", "Grep", "Glob", "Bash"}
VERIFIER_FORBIDDEN_TOOLS = {"Edit", "Write"}


def _load_agent_frontmatter(agent_path: Path) -> dict:
    """解析 agent .md 文件的 YAML frontmatter"""
    with open(agent_path, encoding="utf-8") as f:
        content = f.read()
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            return yaml.safe_load(content[3:end])
    return {}


class TestAgentsDirExists:
    """agents 目录必须存在且包含全部 5 个 agent"""

    def test_agents_dir_exists(self, project_root):
        assert (project_root / AGENTS_DIR).is_dir()

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_file_exists(self, project_root, agent_name):
        path = project_root / AGENTS_DIR / f"{agent_name}.md"
        assert path.exists(), f"agent 文件不存在: {path}"

    def test_agents_dir_contains_only_core_agents(self, project_root):
        actual = sorted(p.stem for p in (project_root / AGENTS_DIR).glob("*.md")
                        if p.stem != "README")
        assert actual == sorted(ALL_AGENTS), f"agents/ 目录应只包含 5 个 agent，实际: {actual}"


class TestAgentFrontmatterCompleteness:
    """所有核心 Agent 必须包含完整的 frontmatter 字段"""

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_has_required_name_field(self, project_root, agent_name):
        path = project_root / AGENTS_DIR / f"{agent_name}.md"
        fm = _load_agent_frontmatter(path)
        assert "name" in fm, f"{agent_name}.md 缺少必填字段 'name'"
        assert fm["name"] == agent_name, f"{agent_name}.md 的 name 不匹配"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_has_required_description_field(self, project_root, agent_name):
        path = project_root / AGENTS_DIR / f"{agent_name}.md"
        fm = _load_agent_frontmatter(path)
        assert "description" in fm, f"{agent_name}.md 缺少必填字段 'description'"
        assert isinstance(fm["description"], str) and fm["description"].strip(), f"{agent_name}.md 的 description 不能为空"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_has_complete_frontmatter(self, project_root, agent_name):
        path = project_root / AGENTS_DIR / f"{agent_name}.md"
        fm = _load_agent_frontmatter(path)
        required = AGENT_REQUIRED_FIELDS.get(agent_name, [])
        for field in required:
            assert field in fm, f"{agent_name}.md frontmatter 缺少字段 '{field}'"


class TestCoreAgentModelSuitability:
    """核心 Agent 的 model 选择必须与职责匹配"""

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_core_agent_model_suitable(self, project_root, agent_name):
        path = project_root / AGENTS_DIR / f"{agent_name}.md"
        fm = _load_agent_frontmatter(path)
        expectation = CORE_AGENT_MODEL_EXPECTATIONS[agent_name]
        actual_model = fm.get("model")
        if "required_model" in expectation:
            assert actual_model == expectation["required_model"], (
                f"{agent_name}.md 的 model 必须为 '{expectation['required_model']}'"
                f"（实际='{actual_model}'）。{expectation['reason']}"
            )
        else:
            assert actual_model in expectation["allowed_models"], (
                f"{agent_name}.md 的 model='{actual_model}' 不在允许范围内 "
                f"{expectation['allowed_models']}。{expectation['reason']}"
            )


class TestExplorerToolsReadonly:
    """explorer 作为只读探索代理，不应有 Edit/Write 工具"""

    def test_explorer_tools_are_readonly(self, project_root):
        path = project_root / AGENTS_DIR / "explorer.md"
        fm = _load_agent_frontmatter(path)
        tools = fm.get("tools", [])
        forbidden = {"Edit", "Write"}
        actual_set = set(tools) if tools else set()
        overlap = actual_set & forbidden
        assert not overlap, f"explorer 不应有写操作工具，发现: {overlap}"


class TestImplementerHasWriteTools:
    """implementer 作为实施代理，必须有编辑能力工具"""

    def test_implementer_has_write_tools(self, project_root):
        path = project_root / AGENTS_DIR / "implementer.md"
        fm = _load_agent_frontmatter(path)
        tools = fm.get("tools", [])
        assert "Edit" in tools or "Write" in tools, "implementer 必须包含 Edit 或 Write 工具"


class TestAgentDescriptionHasTriggerWord:
    """每个 Agent 的 description 必须包含触发词以便 Claude Code 自动调度"""

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_description_has_trigger_word(self, project_root, agent_name):
        path = project_root / AGENTS_DIR / f"{agent_name}.md"
        fm = _load_agent_frontmatter(path)
        desc = fm.get("description", "")
        trigger_patterns = ["use proactively", "Use proactively", "当需要", "当涉及", "触发"]
        has_trigger = any(p.lower() in desc.lower() for p in trigger_patterns)
        assert has_trigger, (
            f"agent {agent_name}.md 的 description 缺少触发词。"
            f"\n当前 description: {desc[:120]}..."
        )


class TestVerifierAgentCompleteness:
    """verifier agent 的 frontmatter 完整性专项验证"""

    def test_verifier_has_all_required_fields(self, project_root):
        path = project_root / AGENTS_DIR / "verifier.md"
        fm = _load_agent_frontmatter(path)
        required = AGENT_REQUIRED_FIELDS["verifier"]
        for field in required:
            assert field in fm, f"verifier.md 缺少必填字段 '{field}'"

    def test_verifier_tools_contains_required(self, project_root):
        path = project_root / AGENTS_DIR / "verifier.md"
        fm = _load_agent_frontmatter(path)
        tools = set(fm.get("tools", []))
        missing = VERIFIER_REQUIRED_TOOLS - tools
        assert not missing, f"verifier 缺少必要的验证工具: {missing}"

    def test_verifier_tools_forbids_edit(self, project_root):
        path = project_root / AGENTS_DIR / "verifier.md"
        fm = _load_agent_frontmatter(path)
        tools = set(fm.get("tools", []))
        forbidden_found = tools & VERIFIER_FORBIDDEN_TOOLS
        assert not forbidden_found, f"verifier 不应有写操作工具，发现: {forbidden_found}"

    def test_verifier_has_memory_field(self, project_root):
        path = project_root / AGENTS_DIR / "verifier.md"
        fm = _load_agent_frontmatter(path)
        assert "memory" in fm, "verifier 应包含 memory 字段"
        assert isinstance(fm["memory"], bool), f"memory 应为 bool, 实际: {type(fm['memory'])}"

    def test_verifier_has_max_turns_field(self, project_root):
        path = project_root / AGENTS_DIR / "verifier.md"
        fm = _load_agent_frontmatter(path)
        assert "maxTurns" in fm, "verifier 应包含 maxTurns 字段"
        assert isinstance(fm["maxTurns"], int) and fm["maxTurns"] > 0, (
            f"maxTurns 应为正整数, 实际: {fm.get('maxTurns')}"
        )

    def test_verifier_deprecated_permission_mode_field_removed(self, project_root):
        path = project_root / AGENTS_DIR / "verifier.md"
        fm = _load_agent_frontmatter(path)
        assert "permissionMode" not in fm, "verifier 不应包含不支持的 permissionMode 字段"




class TestArchitectAgentCompleteness:
    """architect agent 的 frontmatter 完整性专项验证"""

    def test_architect_has_required_fields(self, project_root):
        path = project_root / AGENTS_DIR / "architect.md"
        fm = _load_agent_frontmatter(path)
        required = AGENT_REQUIRED_FIELDS.get("architect", [])
        for field in required:
            assert field in fm, f"architect.md 缺少必填字段 '{field}'"

    def test_architect_model_suitable(self, project_root):
        path = project_root / AGENTS_DIR / "architect.md"
        fm = _load_agent_frontmatter(path)
        expectation = CORE_AGENT_MODEL_EXPECTATIONS["architect"]
        actual_model = fm.get("model")
        if "required_model" in expectation:
            assert actual_model == expectation["required_model"], (
                f"architect.md 的 model 必须为 '{expectation['required_model']}'"
                f"（实际='{actual_model}'）。{expectation['reason']}"
            )

    def test_architect_tools_are_readonly(self, project_root):
        """architect 作为技术审稿代理，不应有 Edit/Write/Bash 工具"""
        path = project_root / AGENTS_DIR / "architect.md"
        fm = _load_agent_frontmatter(path)
        tools = fm.get("tools", [])
        forbidden = {"Edit", "Write", "Bash"}
        actual_set = set(tools) if tools else set()
        overlap = actual_set & forbidden
        assert not overlap, f"architect 不应有写操作/运行命令工具，发现: {overlap}"

    def test_architect_has_memory_and_maxturns(self, project_root):
        path = project_root / AGENTS_DIR / "architect.md"
        fm = _load_agent_frontmatter(path)
        assert "memory" in fm, "architect 应包含 memory 字段"
        assert isinstance(fm["memory"], bool), f"memory 应为 bool, 实际: {type(fm['memory'])}"
        assert "maxTurns" in fm, "architect 应包含 maxTurns 字段"
        assert isinstance(fm["maxTurns"], int) and fm["maxTurns"] > 0

    def test_architect_description_has_trigger(self, project_root):
        path = project_root / AGENTS_DIR / "architect.md"
        fm = _load_agent_frontmatter(path)
        desc = fm.get("description", "")
        has_trigger = any(p in desc.lower() for p in ["use proactively", "当需要", "触发", "自动触发"])
        assert has_trigger, (
            f"agent architect.md 的 description 缺少触发词。\n当前 description: {desc[:120]}..."
        )


class TestDebuggerAgentCompleteness:
    """debugger agent 的 frontmatter 完整性专项验证"""

    def test_debugger_has_required_fields(self, project_root):
        path = project_root / AGENTS_DIR / "debugger.md"
        fm = _load_agent_frontmatter(path)
        required = AGENT_REQUIRED_FIELDS.get("debugger", [])
        for field in required:
            assert field in fm, f"debugger.md 缺少必填字段 '{field}'"

    def test_debugger_model_suitable(self, project_root):
        path = project_root / AGENTS_DIR / "debugger.md"
        fm = _load_agent_frontmatter(path)
        expectation = CORE_AGENT_MODEL_EXPECTATIONS["debugger"]
        actual_model = fm.get("model")
        if "required_model" in expectation:
            assert actual_model == expectation["required_model"], (
                f"debugger.md 的 model 必须为 '{expectation['required_model']}'"
                f"（实际='{actual_model}'）。{expectation['reason']}"
            )

    def test_debugger_has_bash_for_diagnostics(self, project_root):
        """debugger 作为异常调查代理，需要 Bash 运行诊断命令"""
        path = project_root / AGENTS_DIR / "debugger.md"
        fm = _load_agent_frontmatter(path)
        tools = set(fm.get("tools", []))
        assert "Bash" in tools, "debugger 必须包含 Bash 工具用于运行诊断命令"

    def test_debugger_no_edit_write_tools(self, project_root):
        """debugger 不直接修代码，不应有 Edit/Write 工具"""
        path = project_root / AGENTS_DIR / "debugger.md"
        fm = _load_agent_frontmatter(path)
        tools = set(fm.get("tools", []))
        forbidden = {"Edit", "Write"}
        found = tools & forbidden
        assert not found, f"debugger 不应有代码编辑工具，发现: {found}"

    def test_debugger_has_memory_and_maxturns(self, project_root):
        path = project_root / AGENTS_DIR / "debugger.md"
        fm = _load_agent_frontmatter(path)
        assert "memory" in fm, "debugger 应包含 memory 字段"
        assert isinstance(fm["maxTurns"], int) and fm["maxTurns"] > 0

    def test_debugger_description_has_trigger(self, project_root):
        path = project_root / AGENTS_DIR / "debugger.md"
        fm = _load_agent_frontmatter(path)
        desc = fm.get("description", "")
        has_trigger = any(p in desc.lower() for p in ["use proactively", "当需要", "触发", "异常"])
        assert has_trigger, (
            f"agent debugger.md 的 description 缺少触发词。\n当前 description: {desc[:120]}..."
        )
class TestPluginJsonAgentsDeclaration:
    """plugin.json 的 agents 策略：使用默认路径，不声明 agents 字段"""

    def test_agents_field_not_declared_uses_default(self, project_root):
        plugin_json_path = project_root / ".claude-plugin" / "plugin.json"
        with open(plugin_json_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "agents" not in data, (
            f"plugin.json 不应声明 agents 字段（使用默认路径自动发现），"
            f"当前值='{data.get('agents')}'"
        )

    def test_agents_dir_at_plugin_root(self, project_root):
        agents_at_root = (project_root / "agents").is_dir()
        agents_in_claude_plugin = (project_root / ".claude-plugin" / "agents").exists()
        assert agents_at_root, "插件根目录缺少 agents/ 目录"
        assert not agents_in_claude_plugin, (
            "agents/ 错误地放在了 .claude-plugin/ 内。"
            "只有 plugin.json 属于 .claude-plugin/"
        )

    def test_commands_field_valid(self, project_root):
        plugin_json_path = project_root / ".claude-plugin" / "plugin.json"
        with open(plugin_json_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "commands" in data, "plugin.json 缺少 commands 字段"
        commands = data["commands"]
        assert isinstance(commands, list) and len(commands) > 0, "plugin.json 的 commands 不能为空列表"
        for cmd in commands:
            cmd_path = project_root / cmd
            assert cmd_path.exists(), f"plugin.json 引用的命令文件不存在: {cmd}"

    def test_skills_field_valid(self, project_root):
        plugin_json_path = project_root / ".claude-plugin" / "plugin.json"
        with open(plugin_json_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "skills" in data, "plugin.json 缺少 skills 字段"
        skills = data["skills"]
        assert isinstance(skills, list) and len(skills) > 0, "plugin.json 的 skills 不能为空列表"
        for skill in skills:
            skill_path = project_root / skill
            assert skill_path.exists(), f"plugin.json 引用的 skill 目录不存在: {skill}"

    def test_no_invalid_fields_in_plugin_json(self, project_root):
        plugin_json_path = project_root / ".claude-plugin" / "plugin.json"
        with open(plugin_json_path, encoding="utf-8") as f:
            data = json.load(f)
        known_top_level_fields = {
            "name", "version", "description", "commands", "skills",
            "author", "license", "keywords", "repository",
        }
        unknown = set(data.keys()) - known_top_level_fields
        assert not unknown, f"plugin.json 包含未知顶层字段: {unknown}"


class TestVersionSync:
    """plugin.json、marketplace.json 与 CLAUDE.md 版本号必须一致"""

    def test_plugin_and_marketplace_version_match(self, project_root):
        plugin_json_path = project_root / ".claude-plugin" / "plugin.json"
        marketplace_json_path = project_root / ".claude-plugin" / "marketplace.json"

        with open(plugin_json_path, encoding="utf-8") as f:
            plugin_data = json.load(f)
        with open(marketplace_json_path, encoding="utf-8") as f:
            marketplace_data = json.load(f)

        plugin_version = plugin_data["version"]
        marketplace_plugins = marketplace_data.get("plugins", [])
        target = next(
            (p for p in marketplace_plugins if p.get("name") == plugin_data.get("name")),
            None,
        )

        assert target is not None, f"marketplace.json 中未找到插件 {plugin_data.get('name')}"
        assert target.get("version") == plugin_version, (
            f"plugin.json version={plugin_version} 与 "
            f"marketplace.json version={target.get('version')} 不一致"
        )

    def test_claude_md_version_reference_matches_plugin(self, project_root):
        plugin_json_path = project_root / ".claude-plugin" / "plugin.json"
        claude_md_path = project_root / ".claude" / "CLAUDE.md"

        with open(plugin_json_path, encoding="utf-8") as f:
            plugin_data = json.load(f)
        plugin_version = plugin_data["version"]
        claude_text = claude_md_path.read_text(encoding="utf-8")

        assert "插件版本" in claude_text and plugin_version in claude_text, (
            f"CLAUDE.md 应包含插件版本 {plugin_version} 的引用"
        )
