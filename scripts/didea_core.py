#!/usr/bin/env python3
"""diwu-flow didea_core: ideas/ 容器 CRUD 操作。

create / list / show / refine / archive / validate
CLI 入口：python3 scripts/didea_core.py <action> [options] --cwd <proj>
"""

import argparse
import json
import os
import re
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DIWU_DIR, error_exit  # noqa: E402

IDEAS_DIR = ".diwu/ideas"
ARCHIVE_DIR = ".diwu/ideas/archived"
ILLEGAL_CHARS_RE = re.compile(r'[\\/:*?"<>|]')


def _ideas_dir(cwd: Path) -> Path:
    return cwd / IDEAS_DIR


def _archive_dir(cwd: Path) -> Path:
    return cwd / ARCHIVE_DIR


def _scan_ideas(ideas_path: Path) -> list[dict]:
    if not ideas_path.is_dir():
        return []
    results = []
    for f in sorted(ideas_path.glob("*.md")):
        fm = _parse_frontmatter(f)
        if fm:
            fm["filename"] = f.name
            fm["filepath"] = str(f)
            results.append(fm)
    results.sort(key=lambda x: x.get("id", 0))
    return results


def _parse_frontmatter(filepath: Path) -> dict | None:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        import yaml
        fm = yaml.safe_load(parts[1])
        return fm if isinstance(fm, dict) else None
    except Exception:
        return None


def _next_id(ideas_path: Path) -> int:
    ideas = _scan_ideas(ideas_path)
    if not ideas:
        return 1
    return max((fm.get("id", 0) for fm in ideas if isinstance(fm.get("id"), int)), default=0) + 1


def _sanitize_filename(title: str) -> str:
    cleaned = ILLEGAL_CHARS_RE.sub("", title).strip()
    if len(cleaned) > 80:
        cleaned = cleaned[:80].rstrip()
    return cleaned or "untitled"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cmd_create(args, cwd: Path):
    ideas_path = _ideas_dir(cwd)
    ideas_path.mkdir(parents=True, exist_ok=True)

    title = args.title.strip()
    if not title:
        error_exit("title 不能为空")

    next_id = _next_id(ideas_path)
    filename = _sanitize_filename(title) + ".md"
    filepath = ideas_path / filename

    if filepath.exists():
        stem = _sanitize_filename(title)
        filename = f"{stem}-{next_id}.md"
        filepath = ideas_path / filename

    now = _now_iso()
    body = args.body or ""
    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]

    frontmatter = {
        "id": next_id,
        "created_at": now,
        "updated_at": now,
        "source_session": "",
        "github_issue_url": "",
        "linked_task_ids": [],
        "tags": tags,
    }

    import yaml
    content_lines = [
        "---",
        yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True).strip(),
        "---",
        "",
        "## 描述",
        body or "(待补充)",
        "",
        "## Why now",
        "",
        "## Next candidate action",
        "",
    ]
    filepath.write_text("\n".join(content_lines), encoding="utf-8")

    print(json.dumps({
        "ok": True, "status": "created",
        "data": {"id": next_id, "filename": filename, "filepath": str(filepath), "title": title},
    }, ensure_ascii=False, indent=2))


def cmd_list(args, cwd: Path):
    ideas_path = _ideas_dir(cwd)
    ideas = _scan_ideas(ideas_path)

    items = [{
        "id": fm.get("id"),
        "title": fm.get("filename", "").removesuffix(".md"),
        "updated_at": fm.get("updated_at"),
    } for fm in ideas]

    print(json.dumps({
        "ok": True, "status": "ok" if items else "empty",
        "count": len(items), "data": items,
    }, ensure_ascii=False, indent=2))


def cmd_show(args, cwd: Path):
    ideas_path = _ideas_dir(cwd)
    ideas = _scan_ideas(ideas_path)
    target = next((fm for fm in ideas if fm.get("id") == args.id), None)
    if not target:
        error_exit(f"Idea #{args.id} 不存在")

    content = Path(target["filepath"]).read_text(encoding="utf-8")
    print(json.dumps({
        "ok": True, "status": "ok",
        "data": {"id": target.get("id"), "filename": target.get("filename"), "content": content},
    }, ensure_ascii=False, indent=2))


def cmd_refine(args, cwd: Path):
    ideas_path = _ideas_dir(cwd)
    ideas = _scan_ideas(ideas_path)

    target_fm = next((fm for fm in ideas if fm.get("id") == args.id), None)
    if not target_fm:
        error_exit(f"Idea #{args.id} 不存在")
    target = Path(target_fm["filepath"])

    if not (args.content or "").strip():
        error_exit("refine 需要提供 --content 参数")

    now = _now_iso()
    content = target.read_text(encoding="utf-8")
    target.write_text(content.rstrip() + f"\n\n{args.content}\n", encoding="utf-8")
    _update_frontmatter_field(target, "updated_at", now)

    print(json.dumps({
        "ok": True, "status": "refined",
        "data": {"id": args.id, "updated_at": now},
    }, ensure_ascii=False, indent=2))


def cmd_archive(args, cwd: Path):
    ideas_path = _ideas_dir(cwd)
    ideas = _scan_ideas(ideas_path)
    target_fm = next((fm for fm in ideas if fm.get("id") == args.id), None)
    if not target_fm:
        error_exit(f"Idea #{args.id} 不存在")

    target = Path(target_fm["filepath"])
    archive_path = _archive_dir(cwd)
    archive_path.mkdir(parents=True, exist_ok=True)

    now = _now_iso()
    archived_file = archive_path / target.name
    shutil.move(str(target), str(archived_file))
    _update_frontmatter_field(archived_file, "updated_at", now)

    print(json.dumps({
        "ok": True, "status": "archived",
        "data": {"id": args.id, "archived_to": str(archived_file), "updated_at": now},
    }, ensure_ascii=False, indent=2))


def cmd_validate(args, cwd: Path):
    ideas_path = _ideas_dir(cwd)
    if not ideas_path.is_dir():
        print(json.dumps({"ok": True, "status": "ok", "data": {"total": 0, "valid": 0, "errors": []}}, ensure_ascii=False))
        return

    required_fields = {"id", "created_at", "updated_at"}
    errors, valid, total = [], 0, 0

    for f in sorted(ideas_path.glob("*.md")):
        total += 1
        fm = _parse_frontmatter(f)
        if not fm:
            errors.append({"file": f.name, "error": "frontmatter 解析失败或不存在"})
            continue
        missing = required_fields - set(fm.keys())
        if missing:
            errors.append({"file": f.name, "error": f"缺少必填字段: {missing}"})
            continue
        valid += 1

    print(json.dumps({
        "ok": True, "status": "ok" if not errors else "warnings",
        "data": {"total": total, "valid": valid, "invalid": len(errors), "errors": errors},
    }, ensure_ascii=False, indent=2))


def _update_frontmatter_field(filepath: Path, field: str, value):
    import yaml
    content = filepath.read_text(encoding="utf-8")
    if not content.startswith("---"):
        error_exit(f"{filepath}: 无 frontmatter")
    parts = content.split("---", 2)
    if len(parts) < 3:
        error_exit(f"{filepath}: frontmatter 格式异常")
    fm = yaml.safe_load(parts[1])
    if not isinstance(fm, dict):
        error_exit(f"{filepath}: frontmatter 不是 dict")
    fm[field] = value
    new_fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()
    filepath.write_text(f"---\n{new_fm_str}\n---{parts[2]}", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="diwu-flow ideas CRUD 核心")
    sub = parser.add_subparsers(dest="action")

    p = sub.add_parser("create"); p.add_argument("--title", required=True); p.add_argument("--body", default=""); p.add_argument("--tags", default=""); p.add_argument("--cwd", default=".")
    p = sub.add_parser("list"); p.add_argument("--cwd", default=".")
    p = sub.add_parser("show"); p.add_argument("--id", type=int, required=True); p.add_argument("--cwd", default=".")
    p = sub.add_parser("refine"); p.add_argument("--id", type=int, required=True); p.add_argument("--content", required=True); p.add_argument("--cwd", default=".")
    p = sub.add_parser("archive"); p.add_argument("--id", type=int, required=True); p.add_argument("--cwd", default=".")
    p = sub.add_parser("validate"); p.add_argument("--cwd", default=".")

    args = parser.parse_args()
    if not args.action:
        parser.print_help(); sys.exit(0)

    dispatch = {
        "create": lambda: cmd_create(args, Path(args.cwd).resolve()),
        "list": lambda: cmd_list(args, Path(args.cwd).resolve()),
        "show": lambda: cmd_show(args, Path(args.cwd).resolve()),
        "refine": lambda: cmd_refine(args, Path(args.cwd).resolve()),
        "archive": lambda: cmd_archive(args, Path(args.cwd).resolve()),
        "validate": lambda: cmd_validate(args, Path(args.cwd).resolve()),
    }
    fn = dispatch.get(args.action)
    if fn:
        fn()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
