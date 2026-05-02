#!/bin/bash
# drelease.sh — 发布公开版本（worktree 隔离模式）
#
# 用法:
#   ./drelease.sh v0.0.5                    # 只打 tag + 推 origin
#   ./drelease.sh v0.0.5 --push-public      # 额外推送到公开仓库（clean 版，无 .diwu/）
#
# 流程:
#   1. 先推送到 origin/main（私有仓库，包含 .diwu/）
#   2. 从当前 HEAD 创建临时 worktree，在 worktree 中清理敏感文件
#   3. 将 clean commit 推送到 public/main
#   4. 清理 worktree
#
# 前提:
#   - 当前在 main 分支，工作区干净
#   - 公开 remote 已配置: git remote add public <url>

set -euo pipefail

VERSION="${1:?用法: $0 <版本号> 如 v0.0.5}"
PUSH_PUBLIC="${2:-}"

PRIVATE_REPO="origin"
PUBLIC_REMOTE="public"
WORKTREE_DIR=$(mktemp -d -t diwu-release-XXXXXX)
ORIGINAL_DIR=$(pwd)

cleanup() {
    echo ""
    echo "→ 清理临时 worktree"
    cd /
    git worktree remove --force "$WORKTREE_DIR" 2>/dev/null || true
    rm -rf "$WORKTREE_DIR" 2>/dev/null || true
}
trap cleanup EXIT

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

# --- Step 1: 先推送到 origin/main（私有仓库，包含 .diwu/）---

echo ""
echo "=== Step 1: 推送到私有仓库 ==="
echo "→ 推送到 $PRIVATE_REPO/main"
git push "$PRIVATE_REPO" "main"

echo "→ 打标签: $VERSION"
git tag -a "$VERSION" -m "diwu-flow ${VERSION}"
git push "$PRIVATE_REPO" "refs/tags/${VERSION}"
echo "✓ 私有仓库已推送（含 .diwu/）"

# --- Step 2: 创建 worktree，在 worktree 中清理敏感文件 ---

echo ""
echo "=== Step 2: 创建 worktree 并清理敏感文件 ==="
HEAD_SHA=$(git rev-parse HEAD)
git worktree add "$WORKTREE_DIR" --detach "$HEAD_SHA"
echo "  worktree: $WORKTREE_DIR"

# 在 worktree 中清理
cd "$WORKTREE_DIR"
git config user.email "release@diwu-flow"
git config user.name "diwu-flow release"

# 删除敏感文件
for f in .diwu .claude; do
    if [ -e "$f" ]; then
        rm -rf "$f"
        git add -A "$f" 2>/dev/null || true
        echo "  已删除: $f/"
    fi
done

# 提交 clean 版本
if git diff --cached --quiet; then
    echo "  无需额外清理（已是 clean 状态）"
    CLEAN_SHA=$HEAD_SHA
else
    git commit -m "release: ${VERSION} (public clean)"
    CLEAN_SHA=$(git rev-parse HEAD)
    echo "  clean commit: ${CLEAN_SHA:0:8}"
fi

# --- Step 3: 推送到公开仓库 ---

if [ "$PUSH_PUBLIC" = "--push-public" ]; then
    if ! git -C "$ORIGINAL_DIR" remote get-url "$PUBLIC_REMOTE" >/dev/null 2>&1; then
        echo "✗ 公开 remote '$PUBLIC_REMOTE' 未配置"
        echo "  请先执行: git remote add public <公开仓库-git-url>"
        exit 1
    fi
    echo ""
    echo "=== Step 3: 推送到公开仓库 ==="
    echo "→ 推送 clean commit 到 $PUBLIC_REMOTE/main"
    git push --force "$PUBLIC_REMOTE" "${CLEAN_SHA}:refs/heads/main"

    # 同步历史 tags（防止遗漏）——仅推送 public 缺少的
    LOCAL_TAGS=$(git tag -l 'v*' 2>/dev/null)
    REMOTE_TAGS=$(git ls-remote --tags "$PUBLIC_REMOTE" 2>/dev/null | grep -oE 'refs/tags/v[^ ^]+' | sed 's|refs/tags/||')
    for t in $LOCAL_TAGS; do
        if [ "$t" = "$VERSION" ]; then continue; fi
        if ! echo "$REMOTE_TAGS" | grep -qx "$t"; then
            git push "$PUBLIC_REMOTE" "refs/tags/${t}" 2>/dev/null || true
            echo "  补推历史 tag: $t"
        fi
    done

    # public tag 必须指向 clean commit（非 origin commit）
    if [ "$CLEAN_SHA" != "$HEAD_SHA" ]; then
        TEMP_TAG="${VERSION}-public"
        git tag -a "$TEMP_TAG" "$CLEAN_SHA" -m "diwu-flow ${VERSION} (public clean)"
        git push "$PUBLIC_REMOTE" "refs/tags/${TEMP_TAG}:refs/tags/${VERSION}"
        git tag -d "$TEMP_TAG"
        echo "→ 公开 tag $VERSION → ${CLEAN_SHA:0:8} (clean commit)"
    else
        git push "$PUBLIC_REMOTE" "refs/tags/${VERSION}"
        echo "→ 公开 tag $VERSION (已是 clean)"
    fi

    echo ""
    echo "✓ 公开仓库已推送（无 .diwu/）"
fi

# --- 完成 ---

echo ""
echo "=== 发布完成 ==="
echo "  main (origin): $(git -C "$ORIGINAL_DIR" rev-parse --short HEAD)"
echo "  标签: $VERSION"
if [ "$PUSH_PUBLIC" = "--push-public" ]; then
    echo "  公开仓库 (public): ${CLEAN_SHA:0:8} (clean)"
fi
