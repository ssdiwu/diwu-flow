#!/bin/bash
# release.sh — 从私有 main 生成干净的公开版本
#
# 用法:
#   ./release.sh v0.0.1                    # 创建 release 分支 + tag
#   ./release.sh v0.0.1 --push-public      # 额外推送到公开 remote
#
# 前提:
#   - 当前在 main 分支，工作区干净
#   - 公开 remote 已配置: git remote add public <公开仓库-url>

set -euo pipefail

VERSION="${1:?用法: $0 <版本号> 如 v0.0.1}"
PUSH_PUBLIC="${2:-}"

PRIVATE_REPO="origin"
PUBLIC_REMOTE="public"
RELEASE_BRANCH="release/${VERSION}"

echo "=== diwu-flow 发布脚本 ==="
echo "版本: $VERSION"
echo "发布分支: $RELEASE_BRANCH"

# 检查前置条件
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    echo "✗ 工作区有未提交变更，请先 commit"
    exit 1
fi

BRANCH="$(git branch --show-current)"
if [ "$BRANCH" != "main" ]; then
    echo "✗ 请在 main 分支上执行此脚本（当前: $BRANCH）"
    exit 1
fi

# 从 main 创建发布分支
echo ""
echo "→ 创建发布分支: $RELEASE_BRANCH"
git checkout -b "$RELEASE_BRANCH" main

# 排除不应公开的文件（git rm --cached 不删本地文件，只从分支移除）
echo "→ 清理敏感文件..."
git rm -r --cached .diwu/ 2>/dev/null || true
git rm --cached dtask.json 2>/dev/null || true
git rm -r --cached recording/ 2>/dev/null || true
git rm --cached continue-here.md 2>/dev/null || true
git rm --cached decisions.md 2>/dev/null || true

# 确保 .gitattributes 存在（控制 git archive 行为）
git add .gitattributes 2>/dev/null || true

# 提交清理结果
git commit -m "release: ${VERSION} (cleaned for public)

排除内容:
- .diwu/ (运行时状态)
- dtask.json (任务数据)
- recording/ (session 记录)
- continue-here.md, decisions.md (临时/内部文件)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>" || {
    echo "ℹ 无需清理的文件，跳过 commit"
}

# 打 tag
echo ""
echo "→ 打标签: $VERSION"
git tag -a "$VERSION" -m "diwu-flow ${VERSION}"

# 推送私有仓库的发布分支和 tag
echo ""
echo "→ 推送到私有仓库 ($PRIVATE_REPO)"
git push "$PRIVATE_REPO" "$RELEASE_BRANCH"
git push "$PRIVATE_REPO" "$VERSION"

# 可选：推送到公开仓库
if [ "$PUSH_PUBLIC" = "--push-public" ]; then
    if ! git remote get-url "$PUBLIC_REMOTE" >/dev/null 2>&1; then
        echo "✗ 公开 remote '$PUBLIC_REMOTE' 未配置"
        echo "  请先执行: git remote add public <公开仓库-git-url>"
        exit 1
    fi
    echo ""
    echo "→ 推送到公开仓库 ($PUBLIC_REMOTE → main)"
    git push "$PUBLIC_REMOTE" "${RELEASE_BRANCH}:main"
    git push "$PUBLIC_REMOTE" "$VERSION"
    echo ""
    echo "✓ 公开版本已推送"
fi

# 切回 main
echo ""
echo "→ 切回 main 分支"
git checkout main

echo ""
echo "=== 发布完成 ==="
echo "  私有分支: $RELEASE_BRANCH (已推送到 origin)"
echo "  标签: $VERSION (已推送)"
if [ "$PUSH_PUBLIC" = "--push-public" ]; then
    echo "  公开仓库: main (已推送)"
fi
