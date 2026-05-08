#!/usr/bin/env python3
"""diwu-flow drec: 归档自动化脚本

执行双轨归档：Task 轨道（Done/Cancelled 任务序列化到 archive/）和
Recording 轨道（session 文件按月份分片移动到 archive/recording/YYYY-MM/）。
包含踩坑聚合协议和归档摘要更新。

CLI 入口: python3 scripts/drec_archive.py run --cwd <proj>
"""

import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DIWU_DIR, ARCHIVE_DIR, DTASK_JSON, DSETTINGS_JSON, PITFALLS_FILE, RECORDING_DIR, save_json  # noqa: E402

# ── 本文件特有常量（不在 common.py 中） ──────────
LAST_SUMMARY = ".last_archive_summary.json"

DEFAULTS = {
    "task_archive_threshold": 20,
    "recording_archive_threshold": 30,
    "recording_retention_days": 30,
}

# ─── 工具函数 ──────────────────────────────────────────


def _p(cwd: Path, *parts) -> Path:
    """拼接 cwd 下的路径（常量已含 .diwu/ 前缀）。"""
    return cwd / Path(*parts)


def _load_json(path: Path):
    """加载 JSON，不存在返回 None，损坏抛异常。"""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_settings(cwd: Path) -> dict:
    """加载 dsettings.json，缺失字段用默认值补全。"""
    settings_path = _p(cwd, DSETTINGS_JSON)
    raw = _load_json(settings_path)
    result = dict(DEFAULTS)
    if raw and isinstance(raw, dict):
        for k in DEFAULTS:
            if k in raw:
                result[k] = raw[k]
    return result


def _now_iso() -> str:
    """返回当前 UTC ISO 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


def _current_month() -> str:
    """返回当前年月字符串 YYYY-MM。"""
    return datetime.now().strftime("%Y-%m")


# ─── Task 轨道归档 ─────────────────────────────────────


def archive_tasks(cwd: Path, tasks: list, settings: dict) -> int:
    """将 Done/Cancelled 任务追加到 archive/task_archive_YYYY-MM.json。

    按 id 去重（幂等安全），写入后从 dtask.json 移除已归档任务。

    Args:
        cwd: 项目根目录。
        tasks: dtask.json 中的完整任务列表。
        settings: 阈值配置字典。

    Returns:
        实际归档的任务数（0 表示无需归档）。
    """
    terminal = [t for t in tasks if t.get("status") in ("Done", "Cancelled")]
    if not terminal:
        return 0

    threshold = settings.get("task_archive_threshold", DEFAULTS["task_archive_threshold"])
    if len(terminal) < threshold:
        return 0

    archive_dir = _p(cwd, ARCHIVE_DIR)
    archive_dir.mkdir(parents=True, exist_ok=True)

    month = _current_month()
    archive_file = archive_dir / f"task_archive_{month}.json"

    # 读取已有归档（按 id 去重）
    # 兼容旧格式（dict 含 tasks 键）和新格式（纯 list）
    existing = []
    existing_ids = set()
    if archive_file.exists():
        raw = _load_json(archive_file)
        if isinstance(raw, dict):
            existing = raw.get("tasks", []) or []
        elif isinstance(raw, list):
            existing = raw
        else:
            existing = []
        existing_ids = {t["id"] for t in existing if isinstance(t, dict) and "id" in t}

    # 追加新任务（跳过已存在的 id）
    new_tasks = [t for t in terminal if t.get("id") not in existing_ids]
    if not new_tasks:
        return 0

    merged = existing + new_tasks
    # 始终写标准 dict 格式，保持与四月归档一致
    archive_payload = {
        "archived_at": _now_iso(),
        "source": str(DTASK_JSON),
        "tasks": merged,
        "count": len(merged),
    }
    save_json(archive_payload, archive_file)

    # 从 dtask.json 移除已归档任务
    task_path = _p(cwd, DTASK_JSON)
    data = _load_json(task_path) or {"tasks": []}
    archived_ids = {t["id"] for t in new_tasks}
    remaining = [t for t in data.get("tasks", []) if t.get("id") not in archived_ids]
    data["tasks"] = remaining
    save_json(data, task_path)

    return len(new_tasks)


# ─── Recording 轨道归档 ─────────────────────────────────


def _extract_session_month(filename: str) -> str:
    """从 session 文件名提取月份。

    格式: session-YYYY-MM-DD-HHMMSS.md → YYYY-MM
    """
    m = re.match(r"session-(\d{4}-\d{2})", filename)
    if m:
        return m.group(1)
    # fallback: 用文件修改时间的月份
    return ""


def archive_recordings(cwd: Path, settings: dict) -> list:
    """按两轮规则移动 recording 文件到 archive/recording/YYYY-MM/。

    选文件规则：
      1. 第一轮：移除所有超龄文件（mtime > retention_days 天）。
      2. 若剩余文件数仍 >= threshold，按 mtime 从旧到新继续移直到活跃目录严格 < threshold。

    分片规则：YYYY-MM 取 session 文件名自身月份。

    Args:
        cwd: 项目根目录。
        settings: 阈值配置字典。

    Returns:
        移动的文件绝对路径列表（用于后续踩坑聚合）。
    """
    rec_dir = _p(cwd, RECORDING_DIR)
    if not rec_dir.is_dir():
        return []

    ct = settings.get("recording_archive_threshold", DEFAULTS["recording_archive_threshold"])
    rd = settings.get("recording_retention_days", DEFAULTS["recording_retention_days"])

    now = time.time()
    cutoff = now - (rd * 86400)

    # 收集所有 .md 文件及其元信息
    files_info = []
    for name in os.listdir(rec_dir):
        if name.endswith(".md"):
            fpath = rec_dir / name
            if fpath.is_file():
                mtime = os.path.getmtime(fpath)
                files_info.append((name, fpath, mtime))

    if not files_info:
        return []

    total = len(files_info)
    old_files = [(n, p, mt) for n, p, mt in files_info if mt < cutoff]

    to_move_names = set()

    # 第一轮：所有超龄文件
    for name, _, _ in old_files:
        to_move_names.add(name)

    # 第二轮：若剩余仍 >= threshold，按 mtime 从旧到新继续移
    remaining_count = total - len(to_move_names)
    if remaining_count >= ct:
        # 排除已选的超龄文件，按 mtime 升序排列
        candidates = sorted(
            [(n, p, mt) for n, p, mt in files_info if n not in to_move_names],
            key=lambda x: x[2],
        )
        need_remove = remaining_count - ct + 1  # 确保严格 <
        for i in range(min(need_remove, len(candidates))):
            to_move_names.add(candidates[i][0])

    if not to_move_names:
        return []

    # 执行移动
    archive_base = _p(cwd, ARCHIVE_DIR, "recording")
    moved_paths = []

    for name, src_path, _ in files_info:
        if name not in to_move_names:
            continue

        month = _extract_session_month(name)
        if not month:
            # fallback: 用当前月
            month = _current_month()

        dest_dir = archive_base / month
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / name

        shutil.move(str(src_path), str(dest_path))
        moved_paths.append(str(dest_path))

    return moved_paths


# ─── 踩坑聚合（9 步协议）───────────────────────────────


# 匹配 ### 本次踩坑/经验 段落
_PITFALL_SECTION_RE = re.compile(
    r"###\s*本次踩坑[\/]?.*经验\s*\n(.*?)(?=\n###\s|\Z)",
    re.DOTALL,
)

# 匹配单条踩坑条目: - [类别] 现象 → 根因 → 误判 → 正确做法
_PITFALL_ENTRY_RE = re.compile(r"-\s*\[([^\]]+)\]\s*(.+)")

# 六类合法标签
_VALID_CATEGORIES = {
    "环境漂移", "数据缺口", "读层现象", "路由护栏契约",
    "验证误读", "分层未拆清", "其他",
}


def aggregate_pitfalls(cwd: Path, moved_file_paths: list) -> int:
    """9 步踩坑聚合协议。

    从已移动的 recording 文件中扫描踩坑段落，按类别聚类后
    追加到 project-pitfalls.md。

    Args:
        cwd: 项目根目录。
        moved_file_paths: 已移动的 recording 文件路径列表。

    Returns:
        新增的踩坑条目数。
    """
    if not moved_file_paths:
        return 0

    # Step 4a: 扫描每个文件的踩坑段落
    file_pitfalls = {}  # filename -> [(category, text)]
    for fpath_str in moved_file_paths:
        fpath = Path(fpath_str)
        if not fpath.exists():
            continue
        try:
            content = fpath.read_text(encoding="utf-8")
        except OSError:
            continue

        entries = []
        for match in _PITFALL_SECTION_RE.finditer(content):
            section_text = match.group(1)
            # 跳过最低合法答案
            if "无显著误判" in section_text and "符合预期" in section_text:
                continue
            for entry_match in _PITFALL_ENTRY_RE.finditer(section_text):
                cat = entry_match.group(1).strip()
                text = entry_match.group(2).strip()
                if cat and text:
                    entries.append((cat, text))

        if entries:
            file_pitfalls[fpath.name] = entries

    if not file_pitfalls:
        return 0  # Step 4i: 无数据跳过

    # Step 4c+4d: 按类别聚类，同 session 同类别合并
    aggregated_by_category = {}  # category -> [(filename, merged_text)]
    for filename, entries in file_pitfalls.items():
        by_cat = {}
        for cat, text in entries:
            # 标准化类别名
            normalized = cat if cat in _VALID_CATEGORIES else "其他"
            if normalized not in by_cat:
                by_cat[normalized] = []
            by_cat[normalized].append(text)

        for cat, texts in by_cat.items():
            merged = "; ".join(texts)  # Step 4d: 同类合并用 ; 连接
            if cat not in aggregated_by_category:
                aggregated_by_category[cat] = []
            aggregated_by_category[cat].append((filename, merged))

    # Step 4g: 追加写入 project-pitfalls.md
    pitfalls_path = _p(cwd, PITFALLS_FILE)
    new_count = 0

    lines_to_append = []
    # Step 4b: 来源追踪 — 用 ## Source: 分隔符
    source_sessions = sorted(file_pitfalls.keys())
    lines_to_append.append(f"\n## Source: archive-aggregate-{_now_iso()[:10]}\n")

    for cat in sorted(aggregated_by_category.keys()):
        for filename, merged_text in aggregated_by_category[cat]:
            # Step 4h: 来源列写具体文件名
            line = f"- [{cat}] {merged_text} （来源: {filename}）"
            lines_to_append.append(line)
            new_count += 1

    if new_count == 0:
        return 0

    # 追加模式写入
    mode = "a" if pitfalls_path.exists() else "w"
    if not pitfalls_path.exists():
        # 新建时写入标题
        with open(pitfalls_path, "w", encoding="utf-8") as f:
            f.write("# 项目高频误判表\n\n")
            f.writelines(lines_to_append)
    else:
        with open(pitfalls_path, "a", encoding="utf-8") as f:
            f.writelines(lines_to_append)

    return new_count


# ─── 归档摘要更新 ──────────────────────────────────────


def update_summary(
    cwd: Path,
    task_count: int,
    rec_count: int,
    files: list,
) -> None:
    """写入/更新 .diwu/archive/.last_archive_summary.json。"""
    summary_path = _p(cwd, ARCHIVE_DIR, LAST_SUMMARY)
    summary = {
        "archived_at": _now_iso(),
        "tasks_archived": task_count,
        "recordings_moved": rec_count,
        "files": files,
    }
    save_json(summary, summary_path)


# ─── 主入口 ────────────────────────────────────────────


def run(cwd: str = ".") -> dict:
    """主入口：执行完整的双轨归档流程。

    Args:
        cwd: 项目根目录路径字符串。

    Returns:
        结果字典: {ok, tasks_archived, recordings_moved, pitfalls_aggregated, files}
    """
    root = Path(cwd).resolve()

    settings = _load_settings(root)

    # 加载任务
    task_path = _p(root, DTASK_JSON)
    task_data = _load_json(task_path) or {"tasks": []}
    tasks = task_data.get("tasks", [])

    results = {
        "ok": True,
        "tasks_archived": 0,
        "recordings_moved": 0,
        "pitfalls_aggregated": 0,
        "files": [],
    }

    # Task 轨道归档
    task_count = archive_tasks(root, tasks, settings)
    results["tasks_archived"] = task_count
    if task_count > 0:
        month = _current_month()
        results["files"].append(f"{DIWU_DIR}/{ARCHIVE_DIR}/task_archive_{month}.json")

    # Recording 轨道归档
    moved = archive_recordings(root, settings)
    results["recordings_moved"] = len(moved)
    results["files"].extend(moved)

    # 踩坑聚合
    if moved:
        pitfall_count = aggregate_pitfalls(root, moved)
        results["pitfalls_aggregated"] = pitfall_count

    # 更新摘要
    if task_count > 0 or moved:
        update_summary(root, task_count, len(moved), results["files"])

    return results


# ─── CLI ────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="diwu-flow 归档执行器")
    parser.add_argument("command", choices=["run"], help="执行归档")
    parser.add_argument("--cwd", type=str, default=".", help="项目根目录")
    args = parser.parse_args()

    result = run(cwd=args.cwd)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
