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
    echo "  agents/  → 3 个核心执行 Agent（默认路径自动发现）"
    echo "  commands/ → 12 个薄壳命令"
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

    # Plugin bootstrap: OpenCode plugin manifest
    # Note: OpenCode plugin API is evolving; this provides the declaration layer.
    # Actual tool registration depends on the target OpenCode version's plugin SDK.
    cat > "$OC_DIR/plugins/diwu-flow.ts" << 'PLUGIN_EOF'
/**
 * diwu-flow OpenCode Plugin Declaration
 *
 * This file declares the diwu-flow plugin for OpenCode.
 * The skills/ and agents/ directories are symlinked separately (see above).
 *
 * Command mapping (triggered via /command or agent dispatch):
 *   drun     → skills/drun/SKILL.md      (auto execution engine)
 *   dtask    → skills/dtask/SKILL.md     (task planning wizard)
 *   dinit    → commands/dinit.md          (CC-only init orchestrator)
 *   dprd     → skills/dprd/SKILL.md      (PRD requirements analysis)
 *   dadr     → commands/dadr.md           (ADR architecture decision record)
 *   ddoc     → skills/ddoc/SKILL.md      (document generator)
 *   dcorr    → skills/dcorr/SKILL.md     (correction diagnostics)
 *   dstat    → skills/dstat/SKILL.md     (project status snapshot)
 */
export const config = {
  name: "diwu-flow",
  version: "0.0.10",
};

export default config;
PLUGIN_EOF

    echo "✓ OpenCode: plugin + skills/agents symlink 已创建到 .opencode/"
    echo "  skills/  → 10 个 Skill（SKILL.md 自动发现）"
    echo "  agents/  → 3 个核心执行 Agent（.md 自动发现）"
    echo "  commands/ → 12 个 command（.md 自动发现）"
    echo "  plugins/diwu-flow.ts → 插件声明 + Command 索引（12 个 command 映射）"
}

uninstall() {
    echo "Uninstalling diwu-flow symlinks..."

    # 安全删除辅助函数：只删除指向 FLOW_ROOT 规范化路径下的 symlink
    _safe_rm_symlinks() {
        local dir="$1"
        [ -d "$dir" ] || return 0
        # 预计算 FLOW_ROOT 的真实路径（解析 symlink 和 ..）
        local normalized_root
        normalized_root=$(realpath "$FLOW_ROOT" 2>/dev/null) || echo "$FLOW_ROOT"

        find "$dir" -type l | while read -r link; do
            target=$(readlink "$link" 2>/dev/null) || continue
            # 规范化 target 路径后做精确前缀匹配（排除 sibling/backup 等非本 repo 路径）
            local norm_target="$target"
            if [[ "$target" = /* ]]; then
                norm_target=$(realpath "$target" 2>/dev/null) || echo "$target"
            fi
            # realpath 规范化后：必须在 FLOW_ROOT 树内才算 diwu-flow 的 symlink（路径边界检查防 sibling 误删）
            if [[ "$(realpath -q -- "$norm_target" 2>/dev/null)" == "$normalized_root" || "$(realpath -q -- "$norm_target" 2>/dev/null)" == "$normalized_root"/* ]]; then
                rm -f "$link"
            fi
        done
        # 清理空目录
        find "$dir" -type d -empty -delete 2>/dev/null || true
    }

    # Codex cleanup
    _safe_rm_symlinks "$HOME/.codex/skills"
    _safe_rm_symlinks "$HOME/.codex/agents"

    # OpenCode cleanup
    if [ -d ".opencode" ]; then
        rm -f ".opencode/plugins/diwu-flow.ts" 2>/dev/null || true
        _safe_rm_symlinks ".opencode/skills"
        _safe_rm_symlinks ".opencode/agents"
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
