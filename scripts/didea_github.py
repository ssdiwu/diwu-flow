#!/usr/bin/env python3
"""diwu-flow didea_github: ideas/ 与 GitHub Issue 双向同步。

push: 创建 GitHub Issue 并回写 url 到 idea frontmatter
pull: 检查 Issue 状态变化（可选）
CLI 入口：python3 scripts/didea_github.py <action> [options] --cwd <proj>
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import error_exit  # noqa: E402


def _check_gh_auth() -> bool:
    """检查 gh CLI 是否已认证。"""
    try:
        r = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _gh_issue_create(title: str, body: str) -> str:
    """调用 gh issue create，返回 issue URL 或 error_exit。"""
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            error_exit(f"gh issue create 失败: {r.stderr.strip()}")
        # 输出通常包含 URL
        output = r.stdout.strip()
        # 尝试从输出中提取 URL
        for line in output.split("\n"):
            if line.startswith("https://") and "issues" in line:
                return line.strip()
        return output
    except subprocess.TimeoutExpired:
        error_exit("gh issue create 超时（30s）")


def _parse_idea_body(filepath: Path) -> str:
    """从 idea .md 文件提取正文作为 issue body（描述区块）。"""
    content = filepath.read_text(encoding="utf-8")
    # 跳过 frontmatter，提取 ## 描述 区块内容
    lines = content.split("\n")
    in_desc = False
    desc_lines = []
    for line in lines:
        if line.startswith("## 描述"):
            in_desc = True
            continue
        if in_desc:
            if line.startswith("## "):
                break
            desc_lines.append(line)
    return "\n".join(desc_lines).strip() or "(无描述)"


def _get_ideas_dir(cwd: Path) -> Path:
    return cwd / ".diwu" / "ideas"


def _find_idea_file(ideas_dir: Path, idea_id: int) -> Path | None:
    """通过 id 查找 idea 文件。"""
    if not ideas_dir.is_dir():
        return None
    import yaml
    for f in sorted(ideas_dir.glob("*.md")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                content = fh.read()
            if not content.startswith("---"):
                continue
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue
            fm = yaml.safe_load(parts[1])
            if isinstance(fm, dict) and fm.get("id") == idea_id:
                return f
        except Exception:
            continue
    return None


def cmd_push(args, cwd: Path):
    """推送 idea 到 GitHub Issue。"""
    ideas_dir = _get_ideas_dir(cwd)
    filepath = _find_idea_file(ideas_dir, args.id)

    if not filepath or not filepath.exists():
        error_exit(f"Idea #{args.id} 不存在或文件缺失")

    # 二次确认：必须显式确认才推送
    if not args.yes:
        print(json.dumps({
            "ok": True,
            "status": "confirmation_required",
            "data": {
                "id": args.id,
                "message": "即将将 Idea 推送为 GitHub Issue。确认后请加 --yes 参数重新执行。",
            },
        }, ensure_ascii=False, indent=2))
        return

    # 检查 gh 认证
    if not _check_gh_auth():
        error_exit("gh CLI 未认证或不可用。请先运行 'gh auth login'")

    import yaml
    # 读取 frontmatter 获取标题
    content = filepath.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    fm = yaml.safe_load(parts[1])
    if not isinstance(fm, dict):
        error_exit(f"Idea #{args.id}: frontmatter 解析失败")

    title = filepath.stem  # 文件名（用户语言标题）
    body = _parse_idea_body(filepath)

    # 可选：追加元数据到 body
    if args.with_metadata:
        meta = f"\n\n---\n*From diwu-flow idea #{args.id}*"
        body += meta

    # 创建 issue
    url = _gh_issue_create(title, body)

    # 回写 github_issue_url 到 frontmatter
    now = _update_fm_field(filepath, "github_issue_url", url)

    print(json.dumps({
        "ok": True,
        "status": "pushed",
        "data": {
            "id": args.id,
            "github_issue_url": url,
            "updated_at": now,
        },
    }, ensure_ascii=False, indent=2))


def cmd_pull(args, cwd: Path):
    """从 GitHub Issue 拉取状态更新（可选实现）。"""
    ideas_dir = _get_ideas_dir(cwd)
    filepath = _find_idea_file(ideas_dir, args.id)

    if not filepath or not filepath.exists():
        error_exit(f"Idea #{args.id} 不存在")

    import yaml
    content = filepath.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    fm = yaml.safe_load(parts[1])
    if not isinstance(fm, dict):
        error_exit("frontmatter 解析失败")

    issue_url = fm.get("github_issue_url", "")
    if not issue_url:
        error_exit(f"Idea #{args.id} 未关联 GitHub Issue，无法 pull")

    if not _check_gh_auth():
        error_exit("gh CLI 未认证或不可用")

    try:
        r = subprocess.run(
            ["gh", "issue", "view", issue_url, "--json", "state,title"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            error_exit(f"gh issue view 失败: {r.stderr.strip()}")

        import json as j
        issue_data = j.loads(r.stdout)
        state = issue_data.get("state", "unknown")

        print(json.dumps({
            "ok": True,
            "status": "pulled",
            "data": {
                "id": args.id,
                "issue_state": state,
                "issue_title": issue_data.get("title"),
                "issue_url": issue_url,
            },
        }, ensure_ascii=False, indent=2))

    except subprocess.TimeoutExpired:
        error_exit("gh issue view 超时")


# ── 内部工具 ──────────────────────────────────────────────

def _update_fm_field(filepath: Path, field: str, value) -> str:
    """更新 frontmatter 字段并返回 updated_at 时间戳。"""
    from datetime import datetime, timezone
    import yaml
    content = filepath.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    fm = yaml.safe_load(parts[1])
    if not isinstance(fm, dict):
        error_exit(f"{filepath}: frontmatter 不是 dict")
    fm[field] = value
    now = datetime.now(timezone.utc).isoformat()
    fm["updated_at"] = now
    new_fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()
    filepath.write_text(f"---\n{new_fm_str}\n---{parts[2]}", encoding="utf-8")
    return now


# ─── CLI 入口 ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="diwu-flow ideas GitHub 同步")
    sub = parser.add_subparsers(dest="action")

    p_push = sub.add_parser("push", help="推送 Idea 为 GitHub Issue")
    p_push.add_argument("--id", type=int, required=True, help="Idea ID")
    p_push.add_argument("--yes", action="store_true", help="跳过二次确认直接推送")
    p_push.add_argument("--with-metadata", action="store_true", help="body 末尾附加来源信息")
    p_push.add_argument("--cwd", type=str, default=".")

    p_pull = sub.add_parser("pull", help="拉取 GitHub Issue 状态")
    p_pull.add_argument("--id", type=int, required=True, help="Idea ID")
    p_pull.add_argument("--cwd", type=str, default=".")

    args = parser.parse_args()
    if not args.action:
        parser.print_help(); sys.exit(0)

    cwd = Path(args.cwd).resolve()
    if args.action == "push":
        cmd_push(args, cwd)
    elif args.action == "pull":
        cmd_pull(args, cwd)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
