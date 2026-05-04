#!/usr/bin/env python3
"""diwu-flow dstat: 项目状态只读聚合。

纯读取：dtask.json / recording/ / decisions.md / git / archive/
不修改任何文件，优雅降级（I5: 缺失数据源输出 null/warning 而非报错退出）。
CLI 入口：python3 scripts/dstat.py [--deep] --cwd <proj>
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# 将 scripts/ 加入路径以导入 common
sys.path.insert(0, str(Path(__file__).parent))
from common import load_json_or_empty, rel_time  # noqa: E402


def _run_git(cwd: Path, *args) -> str:
    """执行 git 命令，返回 stdout；非 git 目录返回空字符串（I5 graceful degrade）。"""
    try:
        r = subprocess.run(
            ["git"] + list(args),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


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


def get_tasks_summary(diwu_dir: Path) -> dict:
    """从 dtask.json 提取任务状态分布。"""
    data = load_json_or_empty(diwu_dir / "dtask.json")
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
    """获取 git 状态信息。I5: 非 git 目录返回 null 字段。"""
    branch = _run_git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if not branch:
        return {"branch": None, "clean": None, "recent_commit": None, "not_git": True}
    status_short = _run_git(cwd, "status", "--short")
    clean = len(status_short) == 0
    recent = _run_git(cwd, "log", "--oneline", "-1")
    return {
        "branch": branch,
        "clean": clean,
        "dirty_files": 0 if clean else len(status_short.split("\n")),
        "recent_commit": recent,
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
                  git_info: dict, archive: dict, deep: bool = False) -> str:
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
            log = _run_git(Path.cwd(), "log", "--oneline", "-10")
            if log:
                for l in log.split("\n")[:10]:
                    lines.append(f"  {l}")
            diff_stat = _run_git(Path.cwd(), "diff", "--stat")
            if diff_stat:
                lines.append("")
                lines.append("  **未提交变更**:")
                for dl in diff_stat.split("\n")[:20]:
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
        # 需要重新读取原始数据获取详情
        # 此处留占位——详情需要从 dtask.json 的完整 tasks 列表中提取 InProgress/InSpec
        lines.append("(详见 dtask.json 中 InProgress/InSpec 任务)")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="diwu-flow 项目状态聚合")
    parser.add_argument("--deep", action="store_true", help="深度模式：追加活跃任务详情+git详细")
    parser.add_argument("--cwd", type=str, default=".", help="项目根目录")
    args = parser.parse_args()

    cwd = Path(args.cwd).resolve()
    diwu_dir = cwd / ".diwu"

    summary = get_tasks_summary(diwu_dir)
    sessions = get_recent_sessions(diwu_dir / "recording")
    decisions = get_recent_decisions(diwu_dir / "decisions.md")
    git_info = get_git_status(cwd)
    archive = get_archive_status(diwu_dir / "archive")

    formatted = format_output(summary, sessions, decisions, git_info, archive, deep=args.deep)

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
    if not (diwu_dir / "dtask.json").exists():
        warnings.append("dtask.json 不存在")
    if warnings:
        result["warnings"] = warnings

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
