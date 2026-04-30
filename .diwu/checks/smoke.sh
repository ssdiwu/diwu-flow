#!/bin/bash
# diwu-flow 基线验证脚本
# 在 /drun 执行前自动运行，确认环境健康度

set -euo pipefail

FLOW_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ERRORS=0

echo "🔍 diwu-flow 基线验证..."

# 1. 依赖检查：pytest 可用
echo "📦 检查 pytest..."
if ! command -v pytest >/dev/null 2>&1; then
    echo "  ❌ pytest 未安装"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✅ pytest 可用"
fi

# 2. 构建检查：pytest 全量回归
echo "🏗️  运行全量回归测试..."
cd "$FLOW_ROOT"
if pytest tests/ -q --tb=short; then
    echo "  ✅ 全量测试通过"
else
    echo "  ❌ 测试失败"
    ERRORS=$((ERRORS + 1))
fi

# 3. 插件元数据检查
echo "🧩 检查插件元数据..."
PLUGIN_JSON="$FLOW_ROOT/.claude-plugin/plugin.json"
if [ -f "$PLUGIN_JSON" ]; then
    if python3 -c "import json; json.load(open('$PLUGIN_JSON'))" 2>/dev/null; then
        echo "  ✅ plugin.json 合法"
    else
        echo "  ❌ plugin.json 格式错误"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "  ❌ plugin.json 缺失"
    ERRORS=$((ERRORS + 1))
fi

# 4. Skill 结构检查（12 个 skill 各含 SKILL.md）
echo "📚 检查 Skill 结构..."
SKILL_COUNT=$(find "$FLOW_ROOT/skills" -maxdepth 2 -name 'SKILL.md' | wc -l | tr -d ' ')
if [ "$SKILL_COUNT" -eq 12 ]; then
    echo "  ✅ ${SKILL_COUNT} 个 Skill 结构完整"
else
    echo "  ❌ Skill 数量异常（期望 12，实际 ${SKILL_COUNT}）"
    ERRORS=$((ERRORS + 1))
fi

# 5. Rules 清单检查
echo "📋 检查 Rules 清单..."
if [ -f "$FLOW_ROOT/assets/dinit/assets/rules-manifest.json" ]; then
    if python3 -c "import json; json.load(open('$FLOW_ROOT/assets/dinit/assets/rules-manifest.json'))" 2>/dev/null; then
        RULE_COUNT=$(python3 -c "import json; print(len(json.load(open('$FLOW_ROOT/assets/dinit/assets/rules-manifest.json'))['rules']))")
        echo "  ✅ rules-manifest.json 合法（$RULE_COUNT 条 rules）"
    else
        echo "  ❌ rules-manifest.json 格式错误"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "  ❌ rules-manifest.json 缺失"
    ERRORS=$((ERRORS + 1))
fi

# 6. Hooks 结构检查
echo "⚓ 检查 hooks..."
if [ -f "$FLOW_ROOT/hooks/hooks.json" ]; then
    if python3 -c "import json; json.load(open('$FLOW_ROOT/hooks/hooks.json'))" 2>/dev/null; then
        echo "  ✅ hooks.json 合法"
    else
        echo "  ❌ hooks.json 格式错误"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "  ❌ hooks.json 缺失"
    ERRORS=$((ERRORS + 1))
fi

# 关键 hook 脚本存在性检查
HOOK_SCRIPTS="drift_detect_pre.py context_monitor.py stop_decision.py pre_compact.py session_start.py task_completed.py task_created_validate.py"
for script in $HOOK_SCRIPTS; do
    if [ -f "$FLOW_ROOT/hooks/scripts/$script" ]; then
        : # 静默通过
    else
        echo "  ❌ hooks/scripts/$script 缺失"
        ERRORS=$((ERRORS + 1))
    fi
done
echo "  ✅ 关键 hook 脚本齐全"

# 汇总
if [ "$ERRORS" -eq 0 ]; then
    echo ""
    echo "✅ 基线验证全部通过"
    exit 0
else
    echo ""
    echo "❌ 基线验证失败：$ERRORS 项未通过"
    exit 1
fi
