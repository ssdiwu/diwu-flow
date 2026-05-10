#!/usr/bin/env python3
"""diwu-flow dstat: 项目状态只读聚合。

纯读取：dtask.toml / recording/ / decisions.md / .git / archive/
不修改任何文件，优雅降级（I5: 缺失数据源输出 null/warning 而非报错退出）。
CLI 入口：python3 scripts/dstat.py [--deep] --cwd <proj>
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# 将 scripts/ 和 hooks/scripts/ 加入路径以导入 common / _fs_snapshot
SCRIPTS_DIR = Path(__file__).parent
HOOKS_SCRIPTS_DIR = SCRIPTS_DIR.parent / "hooks" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(HOOKS_SCRIPTS_DIR))

from _fs_snapshot import get_git_metadata, get_worktree_changes  # noqa: E402
from common import DIWU_DIR, DTASK_TOML, DECISIONS_FILE, RECORDING_DIR, ARCHIVE_DIR, load_toml_or_empty, rel_time  # noqa: E402


def _read_recent_lines(path: Path, n: int = 20) -> str:
    """读取文件最后 N 行。不存在返回空字符串。"""
    if not path.exists():
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except OSError:
        return ""


def get_tasks_summary(cwd: Path) -> dict:
    """从 dtask.toml 提取任务状态分布。"""
    data = load_toml_or_empty(cwd / DTASK_TOML)
    tasks = data.get("tasks", []) if isinstance(data, dict) else []
    summary = {"total": len(tasks), "InSpec": 0, "InProgress": 0, "InReview": 0, "Done": 0, "Blocked": 0, "Cancelled": 0}
    for t in tasks:
        if not isinstance(t, dict):
            continue
        s = t.get("status", "")
        if s == "InSpec":
            summary["InSpec"] += 1
        elif s in ("InProgress", "InProcess"):
            summary["InProgress"] += 1
        elif s == "InReview":
            summary["InReview"] += 1
        elif s == "Done":
            summary["Done"] += 1
        elif s == "Cancelled":
            summary["Cancelled"] += 1
        elif "BLOCKED" in s.upper() or (isinstance(t.get("blocked_by"), list) and t["blocked_by"]):
            # 检查是否有未解除的 blocked_by
            summary["Blocked"] += 1
    return summary


def get_recent_sessions(recording_dir: Path) -> list:
    """取最新 1-2 个 session 文件信息。"""
    if not recording_dir.is_dir():
        return []
    files = sorted(recording_dir.glob("session-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    result = []
    for f in files[:2]:
        stat = f.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        result.append({"filename": f.name, "relative_time": rel_time(mtime), "path": str(f)})
    return result


def get_recent_decisions(decisions_path: Path, max_n: int = 3) -> list:
    """从 decisions.md 提取最近 N 条决策摘要。"""
    text = _read_recent_lines(decisions_path, max_n * 5)
    if not text:
        return []
    # 简单按行分割，过滤空行，取前 max_n 条有内容的行
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    decisions = []
    for line in lines[:max_n]:
        decisions.append(line)
    return decisions


def get_git_status(cwd: Path) -> dict:
    """获取 git 状态信息，零 git 子进程。"""
    meta = get_git_metadata(cwd)
    if not meta.is_git_repo:
        return {
            "branch": None,
            "clean": None,
            "recent_commit": None,
            "recent_commits": [],
            "diff_stat_lines": [],
            "dirty_files": None,
            "not_git": True,
        }

    changes = get_worktree_changes(cwd)
    clean = changes.is_clean
    recent = None
    if meta.recent_commits:
        rc = meta.recent_commits[0]
        recent = f"{rc['hash']} {rc['subject']}"

    diff_stat_lines = []
    for path in changes.modified[:20]:
        diff_stat_lines.append(f"M {path}")
    for path in changes.untracked[:20 - len(diff_stat_lines)]:
        diff_stat_lines.append(f"?? {path}")

    return {
        "branch": meta.branch,
        "clean": clean,
        "dirty_files": len(changes.all_changed_files),
        "recent_commit": recent,
        "recent_commits": meta.recent_commits,
        "diff_stat_lines": diff_stat_lines,
        "not_git": False,
    }


def get_archive_status(archive_dir: Path) -> dict:
    """归档状态统计。"""
    if not archive_dir.is_dir():
        return {"last_archive": None, "task_archives": 0, "recording_archives": 0}
    task_archives = list(archive_dir.glob("task_archive_*.json"))
    rec_archives = list((archive_dir / "recording").glob("**/*.md"))
    last = None
    if task_archives or rec_archives:
        all_files = task_archives + rec_archives
        latest = max(all_files, key=lambda p: p.stat().st_mtime)
        mtime = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc).isoformat()
        last = rel_time(mtime)
    return {"last_archive": last, "task_archives": len(task_archives), "recording_archives": len(rec_archives)}


def format_output(summary: dict, sessions: list, decisions: list,
                  git_info: dict, archive: dict, deep: bool = False,
                  diwu_dir: Path | None = None) -> str:
    """格式化输出文本，完全复刻 SKILL.md ASCII 表格。"""
    lines = []
    lines.append("## 项目状态概览\n")

    # 任务进度表
    s = summary
    lines.append("### 任务进度")
    lines.append("┌──────────┬────────┬────────┬────────┬────────┐")
    lines.append(f"│ 总数     │ InSpec │ InProg │ Review │ Done   │")
    lines.append(f"│ {s['total']:<8} │ {s['InSpec']:<6} │ {s['InProgress']:<6} │ {s['InReview']:<6} │ {s['Done']:<6} │")
    lines.append("└──────────┴────────┴────────┴────────┴────────┘")
    blocked_str = f"{s['Blocked']}" if s['Blocked'] > 0 else "0"
    cancelled_str = f"{s['Cancelled']}" if s['Cancelled'] > 0 else "0"
    lines.append(f"\nBlocked: {blocked_str} | Cancelled: {cancelled_str}\n")

    # 最近 Session
    lines.append("### 最近 Session")
    if sessions:
        for sess in sessions:
            lines.append(f"- **{sess['filename']}** ({sess['relative_time']})")
    else:
        lines.append("- 无 session 记录")
    lines.append("")

    # 近期决策
    lines.append("### 近期决策")
    if decisions:
        for i, d in enumerate(decisions, 1):
            lines.append(f"{i}. {d}")
    else:
        lines.append("- (暂无设计决策记录)")
    lines.append("")

    # Git 状态
    lines.append("### Git 状态")
    if git_info.get("not_git"):
        lines.append("- 非 git 目录（或 git 不可用）")
    else:
        b = git_info["branch"]
        ws = "clean" if git_info["clean"] else f"dirty ({git_info['dirty_files']} files)"
        rc = git_info["recent_commit"] or "(无提交记录)"
        lines.append(f"- 分支: {b}")
        lines.append(f"- 工作区: {ws}")
        lines.append(f"- 最近提交: {rc}")

        if deep:
            lines.append("")
            lines.append("**Git 详细信息**:")
            recent_commits = git_info.get("recent_commits", [])
            if recent_commits:
                for item in recent_commits[:10]:
                    lines.append(f"  {item['hash']} {item['subject']}")
            diff_stat_lines = git_info.get("diff_stat_lines", [])
            if diff_stat_lines:
                lines.append("")
                lines.append("  **未提交变更**:")
                for dl in diff_stat_lines[:20]:
                    lines.append(f"  {dl}")
    lines.append("")

    # 归档状态
    lines.append("### 归档状态")
    la = archive["last_archive"] or "从未"
    lines.append(f"- 上次归档: {la}")
    lines.append(f"- 待归档任务文件: {archive['task_archives']} | 待归档 Session 文件: {archive['recording_archives']}")

    # Deep 模式追加活跃任务详情
    if deep:
        lines.append("")
        lines.append("**活跃任务详情**:")
        raw = load_toml_or_empty(diwu_dir / "dtask.toml")
        active_tasks = [t for t in raw.get("tasks", []) if isinstance(t, dict) and t.get("status") in ("InProgress", "InSpec")]
        if active_tasks:
            for t in active_tasks[:5]:
                lines.append(f"  Task#{t.get('id', '?')}: {t.get('title', '')} [{t.get('status')}]")
        else:
            lines.append("  (无活跃任务)")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="diwu-flow 项目状态聚合")
    parser.add_argument("--deep", action="store_true", help="深度模式：追加活跃任务详情+git详细")
    parser.add_argument("--cwd", type=str, default=".", help="项目根目录")
    args = parser.parse_args()

    cwd = Path(args.cwd).resolve()
    diwu_dir = cwd / DIWU_DIR

    summary = get_tasks_summary(cwd)
    sessions = get_recent_sessions(cwd / RECORDING_DIR)
    decisions = get_recent_decisions(cwd / DECISIONS_FILE)
    git_info = get_git_status(cwd)
    archive = get_archive_status(cwd / ARCHIVE_DIR)

    formatted = format_output(summary, sessions, decisions, git_info, archive, deep=args.deep, diwu_dir=diwu_dir)

    # T8: 输出 JSON 结构化结果 + formatted_text
    result = {
        "ok": True,
        "status": "ok",
        "summary": {
            "tasks": summary,
            "recent_sessions": len(sessions),
            "recent_decisions": len(decisions),
            "git_branch": git_info.get("branch"),
            "archive_last": archive["last_archive"],
        },
        "formatted_text": formatted,
    }

    # warnings 字段（I5: 降级信息）
    warnings = []
    if git_info.get("not_git"):
        warnings.append("非 git 目录，git 信息不可用")
    if not (cwd / DTASK_TOML).exists():
        warnings.append("dtask.toml 不存在")
    if warnings:
        result["warnings"] = warnings

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
