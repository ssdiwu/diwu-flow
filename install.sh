#!/bin/bash
# diwu-flow 多平台安装脚本
# ./install.sh --platform <cc|codex|opencode|all>
# ./install.sh --uninstall
# ./install.sh --uninstall --dry-run

set -euo pipefail

FLOW_ROOT="$(cd "$(dirname "$0")" && pwd)"

usage() {
    echo "Usage: $0 --platform <cc|codex|opencode|all>"
    echo "       $0 --uninstall [--dry-run] [--verbose]"
    exit 1
}

install_cc() {
    echo "✓ Claude Code: plugin.json 已就绪"
    echo "  skills/  → 9 个 Skill（可直接调用或通过 /command 触发）"
    echo "  agents/  → 3 个核心执行 Agent（默认路径自动发现）"
    echo "  commands/ → 11 个薄壳命令"
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
 *   ddoc     → skills/ddoc/SKILL.md      (document generator, forward/reverse modes)
 *   dcorr    → skills/dcorr/SKILL.md     (correction diagnostics)
 *   dstat    → skills/dstat/SKILL.md     (project status snapshot)
 */
export const config = {
  name: "diwu-flow",
  version: "0.0.12",
};

export default config;
PLUGIN_EOF

    echo "✓ OpenCode: plugin + skills/agents symlink 已创建到 .opencode/"
    echo "  skills/  → 9 个 Skill（SKILL.md 自动发现）"
    echo "  agents/  → 3 个核心执行 Agent（.md 自动发现）"
    echo "  commands/ → 11 个 command（.md 自动发现）"
    echo "  plugins/diwu-flow.ts → 插件声明 + Command 索引（11 个 command 映射）"
}

uninstall() {
    if [ "$DRY_RUN" = true ]; then
        echo "Dry-run: scanning diwu-flow symlinks..."
    else
        echo "Uninstalling diwu-flow symlinks..."
    fi

    _normalize_path_shell() {
        local path="$1"
        local old_ifs part normalized
        local -a parts

        [[ "$path" = /* ]] || path="$PWD/$path"

        normalized=""
        old_ifs="$IFS"
        IFS="/"
        read -r -a parts <<< "$path"
        IFS="$old_ifs"

        for part in "${parts[@]}"; do
            case "$part" in
                ""|.) ;;
                ..)
                    if [[ "$normalized" == */* ]]; then
                        normalized="${normalized%/*}"
                    else
                        normalized=""
                    fi
                    ;;
                *) normalized="${normalized:+$normalized/}$part" ;;
            esac
        done

        printf '/%s\n' "$normalized"
    }

    _normalize_path() {
        local path="$1"
        local base="${2:-}"
        local resolved

        if [[ -n "$base" && "$path" != /* ]]; then
            path="$base/$path"
        fi

        if command -v realpath >/dev/null 2>&1; then
            if resolved=$(realpath "$path" 2>/dev/null); then
                printf '%s\n' "$resolved"
                return 0
            fi
        fi

        if command -v python3 >/dev/null 2>&1; then
            if resolved=$(python3 - "$path" <<'PY'
import os
import sys

print(os.path.realpath(sys.argv[1]))
PY
            ); then
                printf '%s\n' "$resolved"
                return 0
            fi
        fi

        _normalize_path_shell "$path"
    }

    _is_under_flow_root() {
        local normalized_root="$1"
        local norm_target="$2"

        [[ "$norm_target" == "$normalized_root" || "$norm_target" == "$normalized_root"/* ]]
    }

    # 安全删除辅助函数：只删除指向 FLOW_ROOT 规范化路径下的 symlink
    _safe_rm_symlinks() {
        local dir="$1"
        [ -d "$dir" ] || return 0
        local normalized_root
        normalized_root=$(_normalize_path "$FLOW_ROOT")

        find "$dir" -type l | while read -r link; do
            local target link_dir norm_target

            target=$(readlink "$link" 2>/dev/null) || continue
            link_dir=$(dirname "$link")
            norm_target=$(_normalize_path "$target" "$link_dir") || continue

            # 必须在 FLOW_ROOT 树内才算 diwu-flow 的 symlink（路径边界检查防 sibling 误删）
            if _is_under_flow_root "$normalized_root" "$norm_target"; then
                if [ "$DRY_RUN" = true ]; then
                    echo "Would remove symlink: $link -> $norm_target"
                else
                    if [ "$VERBOSE" = true ]; then
                        echo "Removing symlink: $link -> $norm_target"
                    fi
                    rm -f "$link"
                fi
            fi
        done
        # 清理空目录
        if [ "$DRY_RUN" = false ]; then
            find "$dir" -type d -empty -delete 2>/dev/null || true
        fi
    }

    # Codex cleanup
    _safe_rm_symlinks "$HOME/.codex/skills"
    _safe_rm_symlinks "$HOME/.codex/agents"

    # OpenCode cleanup
    if [ -d ".opencode" ]; then
        if [ -f ".opencode/plugins/diwu-flow.ts" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo "Would remove file: .opencode/plugins/diwu-flow.ts"
            else
                if [ "$VERBOSE" = true ]; then
                    echo "Removing file: .opencode/plugins/diwu-flow.ts"
                fi
                rm -f ".opencode/plugins/diwu-flow.ts" 2>/dev/null || true
            fi
        fi
        _safe_rm_symlinks ".opencode/skills"
        _safe_rm_symlinks ".opencode/agents"
        if [ "$DRY_RUN" = false ]; then
            find ".opencode" -type d -empty -delete 2>/dev/null || true
        fi
    fi

    if [ "$DRY_RUN" = true ]; then
        echo "✓ Dry-run complete"
    else
        echo "✓ Uninstall complete"
    fi
}

# Main
PLATFORM=""
UNINSTALL=false
DRY_RUN=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --platform)
            [ $# -ge 2 ] || usage
            PLATFORM="$2"
            shift 2
            ;;
        --uninstall) UNINSTALL=true; shift ;;
        --dry-run) DRY_RUN=true; VERBOSE=true; shift ;;
        --verbose) VERBOSE=true; shift ;;
        *) usage ;;
    esac
done

if [ "$UNINSTALL" != true ] && { [ "$DRY_RUN" = true ] || [ "$VERBOSE" = true ]; }; then
    usage
fi

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
