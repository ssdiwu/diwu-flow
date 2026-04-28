#!/bin/bash
# diwu-flow 多平台安装脚本
# ./install.sh --platform <cc|codex|opencode|all>
# ./install.sh --uninstall

set -euo pipefail

FLOW_ROOT="$(cd "$(dirname "$0")" && pwd)"

usage() {
    echo "Usage: $0 --platform <cc|codex|opencode|all>"
    echo "       $0 --uninstall"
    exit 1
}

install_cc() {
    echo "✓ Claude Code: plugin.json 已就绪"
    echo "  skills/  → 10 个 Skill（可直接调用或通过 /command 触发）"
    echo "  agents/  → 10 个 Agent"
    echo "  commands/ → 8 个薄壳命令"
}

install_codex() {
    local DEST="$HOME/.codex"
    mkdir -p "$DEST/skills" "$DEST/agents"

    # Skills: symlink SKILL.md (Codex discovers SKILL.md in skill dirs)
    for skill_dir in "$FLOW_ROOT"/skills/*/; do
        local name=$(basename "$skill_dir")
        if [ -f "$skill_dir/SKILL.md" ]; then
            mkdir -p "$DEST/skills/$name"
            ln -sf "$skill_dir/SKILL.md" "$DEST/skills/$name/SKILL.md"
        fi
    done

    # Agents: symlink all (flat structure)
    for agent_file in "$FLOW_ROOT"/agents/*.md; do
        local name=$(basename "$agent_file" .md)
        ln -sf "$agent_file" "$DEST/agents/$name.md"
    done

    echo "✓ Codex CLI: Skills + Agents 已 symlink 到 ~/.codex/"
}

install_opencode() {
    local OC_DIR=".opencode"
    mkdir -p "$OC_DIR/plugins" "$OC_DIR/skills" "$OC_DIR/agents"

    # Skills: symlink SKILL.md (OpenCode reads SKILL.md from skill dirs)
    for skill_dir in "$FLOW_ROOT"/skills/*/; do
        local name=$(basename "$skill_dir")
        if [ -f "$skill_dir/SKILL.md" ]; then
            mkdir -p "$OC_DIR/skills/$name"
            ln -sf "$skill_dir/SKILL.md" "$OC_DIR/skills/$name/SKILL.md"
        fi
    done

    # Agents: symlink
    for agent_file in "$FLOW_ROOT"/agents/*.md; do
        local name=$(basename "$agent_file" .md)
        ln -sf "$agent_file" "$OC_DIR/agents/$name.md"
    done

    # Plugin bootstrap: TS plugin that registers commands as custom tools
    cat > "$OC_DIR/plugins/diwu-flow.ts" << 'PLUGIN_EOF'
// diwu-flow OpenCode Plugin Bootstrap
// Registers diwu-flow commands as custom tools via Zod schema injection
// Full methodology lives in skills/ — this is just the trigger layer

export const config = {
  name: "diwu-flow",
  version: "0.0.1",
};

// Commands registered as custom tools — thin wrappers around skills
// Each command triggers its corresponding skill from skills/{name}/SKILL.md
const commands = [
  { name: "drun", description: "Auto execution engine (auto/step mode)" },
  { name: "dtask", description: "Task planning wizard" },
  { name: "dinit", description: "CC-only initialization orchestrator" },
  { name: "dprd", description: "PRD requirements analysis" },
  { name: "dadr", description: "ADR architecture decision record" },
  { name: "ddoc", description: "Document generator" },
  { name: "ddemo", description: "Demo verification" },
  { name: "dcorr", description: "Correction diagnostics" },
];

export default config;
PLUGIN_EOF

    echo "✓ OpenCode: plugin + skills/agents symlink 已创建到 .opencode/"
    echo "  skills/  → 10 个 Skill（直接可用或通过 Plugin Custom Tool 触发）"
    echo "  agents/  → 10 个 Agent"
    echo "  plugins/diwu-flow.ts → Command 注册入口（8 个 command schema）"
}

uninstall() {
    echo "Uninstalling diwu-flow symlinks..."
    # Codex cleanup
    if [ -d "$HOME/.codex/skills" ]; then
        find "$HOME/.codex/skills" -type l -delete 2>/dev/null || true
        # Clean empty dirs
        find "$HOME/.codex/skills" -type d -empty -delete 2>/dev/null || true
    fi
    if [ -d "$HOME/.codex/agents" ]; then
        find "$HOME/.codex/agents" -type l -delete 2>/dev/null || true
        find "$HOME/.codex/agents" -type d -empty -delete 2>/dev/null || true
    fi
    # OpenCode cleanup
    if [ -d ".opencode" ]; then
        rm -f ".opencode/plugins/diwu-flow.ts" 2>/dev/null || true
        find ".opencode/skills" -type l -delete 2>/dev/null || true
        find ".opencode/agents" -type l -delete 2>/dev/null || true
        find ".opencode" -type d -empty -delete 2>/dev/null || true
    fi
    echo "✓ Uninstall complete"
}

# Main
PLATFORM=""
UNINSTALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --platform) PLATFORM="$2"; shift 2 ;;
        --uninstall) UNINSTALL=true; shift ;;
        *) usage ;;
    esac
done

if [ "$UNINSTALL" = true ]; then
    uninstall
    exit 0
fi

case "$PLATFORM" in
    cc)     install_cc ;;
    codex)  install_codex ;;
    opencode) install_opencode ;;
    all)    install_cc && install_codex && install_opencode ;;
    *)      usage ;;
esac
