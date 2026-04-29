#!/bin/bash
# drelease.sh — 从私有 main 生成干净的公开版本（worktree 隔离模式）
#
# 用法:
#   ./drelease.sh v0.0.5                    # 创建 release tag + 推送私有
#   ./drelease.sh v0.0.5 --push-public      # 额外推送到公开 remote
#
# 设计:
#   - git worktree 隔离操作，main 工作树永不被碰
#   - public main 与 origin main 保持同步（仅 tip 过滤 .diwu/ 等）
#   - cleanup trap 确保 worktree 总是被移除
#
# 安全:
#   - 只 force-push 到 public（你拥有）
#   - 永不 force-push 到 origin（私有协作仓库）
#   - 推送使用 commit SHA 解引用（处理 annotated tag）

set -euo pipefail

VERSION="${1:?用法: $0 <版本号> 如 v0.0.5}"
PUSH_PUBLIC="${2:-}"

PRIVATE_REPO="origin"
PUBLIC_REMOTE="public"

echo "=== diwu-flow 发布脚本 ==="
echo "版本: $VERSION"

# --- 前置检查 ---

if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    echo "✗ 工作区有未提交变更，请先 commit"
    exit 1
fi

BRANCH="$(git branch --show-current)"
if [ "$BRANCH" != "main" ]; then
    echo "✗ 请在 main 分支上执行此脚本（当前: $BRANCH）"
    exit 1
fi

if git tag -l "$VERSION" | grep -q "$VERSION"; then
    echo "✗ 标签 $VERSION 已存在"
    exit 1
fi

MAIN_SHA=$(git rev-parse HEAD)

# --- 创建隔离 worktree ---

WORKTREE_DIR=$(mktemp -d -t diwu-release-XXXXXX)

cleanup() {
    echo "→ 清理 worktree: $WORKTREE_DIR"
    git worktree remove "$WORKTREE_DIR" --force 2>/dev/null || true
    git worktree prune 2>/dev/null || true
    rm -rf "$WORKTREE_DIR" 2>/dev/null || true
}
trap cleanup EXIT

echo ""
echo "→ 创建 worktree: $WORKTREE_DIR"
git worktree add "$WORKTREE_DIR" --detach HEAD > /dev/null

# --- 在 worktree 中清理敏感文件 ---

echo "→ 清理敏感文件（仅在 worktree 中）..."
pushd "$WORKTREE_DIR" > /dev/null

git rm -r --cached .diwu/ 2>/dev/null || true
git rm --cached dtask.json 2>/dev/null || true
git rm -r --cached recording/ 2>/dev/null || true
git rm --cached continue-here.md 2>/dev/null || true
git rm --cached decisions.md 2>/dev/null || true
git add .gitattributes 2>/dev/null || true

if git diff --cached --quiet 2>/dev/null; then
    echo "ℹ 无需清理的文件，复用 main commit"
    RELEASE_SHA="$MAIN_SHA"
else
    git commit -m "release: ${VERSION} (cleaned for public)

排除内容:
- .diwu/ (运行时状态)
- dtask.json (任务数据)
- recording/ (session 记录)
- continue-here.md, decisions.md (临时/内部文件)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
    RELEASE_SHA=$(git rev-parse HEAD)
fi

# 打 annotated tag
echo "→ 打标签: $VERSION → ${RELEASE_SHA:0:7}"
git tag -a "$VERSION" -m "diwu-flow ${VERSION}" "$RELEASE_SHA"

popd > /dev/null

# --- 推送到私有仓库 ---

echo ""
echo "→ 推送到私有仓库 ($PRIVATE_REPO)"
git push "$PRIVATE_REPO" "${RELEASE_SHA}:refs/heads/release/${VERSION}"
git push "$PRIVATE_REPO" "refs/tags/${VERSION}"

# --- 推送到公开仓库 ---

if [ "$PUSH_PUBLIC" = "--push-public" ]; then
    if ! git remote get-url "$PUBLIC_REMOTE" >/dev/null 2>&1; then
        echo "✗ 公开 remote '$PUBLIC_REMOTE' 未配置"
        echo "  请先执行: git remote add public <公开仓库-git-url>"
        exit 1
    fi
    echo ""
    echo "→ 推送到公开仓库 ($PUBLIC_REMOTE → main)"
    git fetch "$PUBLIC_REMOTE" 2>/dev/null || true
    # 使用 SHA 而非 tag 引用（annotated tag 需要解引用）
    git push "$PUBLIC_REMOTE" "+${RELEASE_SHA}:refs/heads/main"
    git push "$PUBLIC_REMOTE" "+refs/tags/${VERSION}"
    echo ""
    echo "✓ 公开版本已推送"
fi

# --- 完成 ---

echo ""
echo "=== 发布完成 ==="
echo "  本地 main: ${MAIN_SHA:0:7}（未受影响）"
echo "  私有分支: release/$VERSION → ${RELEASE_SHA:0:7}"
echo "  标签: $VERSION"
if [ "$PUSH_PUBLIC" = "--push-public" ]; then
    echo "  公开仓库: main → ${RELEASE_SHA:0:7}"
fi
