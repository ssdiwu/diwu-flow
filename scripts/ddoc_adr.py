#!/usr/bin/env python3
"""diwu-flow ddoc: ADR 子模式脚本（编号分配 + 文件骨架 + 索引维护）。

作为 /ddoc --mode adr 的后端，提供 next-number/create/update-status 三个子命令。
AI 保留 Step 1-2（澄清问题 + 内容撰写）由 SKILL.md 定义。
T11: README 缺失时扫描重建索引；固定语义 {ok, status, data?}。
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ensure_dir  # noqa: E402

ADR_DIR = ".doc/adr"
ADR_README = "README.md"

# ADR 骨架模板（不含 Context/Options/Decision/Consequences — 由 AI 填写）
ADR_SKELETON = """# ADR-{number}: {title}

**Status**: {status}
**Date**: {date}

## Context
<!-- AI 在 Step 2 澄清后填入具体背景、数据、约束 -->

## Options Considered
- **[方案A]**: 优点 / 缺点
- **[方案B]**: 优点 / 缺点

## Decision
<!-- AI 填写决策理由和选择 -->

## Consequences
- ✅ 正面影响
- ⚠️ 注意事项 / 风险
"""


def _scan_adr_numbers(adr_dir: Path) -> list[int]:
    """扫描 .doc/adr/ 下所有 ADR-NNN*.md 的编号。"""
    numbers = []
    if not adr_dir.is_dir():
        return numbers
    for f in adr_dir.glob("ADR-*.md"):
        m = re.match(r"ADR-(\d+)", f.name)
        if m:
            numbers.append(int(m.group(1)))
    return sorted(numbers)


def _readme_path(adr_dir: Path) -> Path:
    return adr_dir / ADR_README


def _parse_readme_index(readme_path: Path) -> list[dict]:
    """解析 README.md 索引表格，返回 [{number, title, status, summary}]。

    解析失败返回空列表（不 crash）。
    """
    if not readme_path.exists():
        return []
    rows = []
    in_table = False
    for line in readme_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and ("编号" in stripped or "ID" in stripped.lower()):
            in_table = True
            continue
        if in_table:
            if not stripped.startswith("|"):
                break
            # 跳过分隔行 |---|---|...
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            parts = [p.strip() for p in stripped.split("|")[1:-1]]
            if parts and parts[0] and parts[0].startswith("ADR-"):
                m = re.match(r"(\d+)", parts[0])
                if m:
                    rows.append({
                        "number": int(m.group(1)),
                        "full_id": parts[0],
                        "title": parts[1] if len(parts) > 1 else "",
                        "status": parts[2] if len(parts) > 2 else "",
                        "summary": parts[3] if len(parts) > 3 else "",
                    })
    return rows


def _build_readme_content(rows: list[dict]) -> str:
    """从索引行列表构建完整 README 内容。"""
    lines = ["# ADR 索引", ""]
    lines.append("| 编号 | 标题 | 状态 | 摘要（一句话） |")
    lines.append("|------|------|------|--------------|")
    for r in rows:
        lines.append(
            f"| {r['full_id']} | {r['title']} | {r['status']} | {r['summary']} |"
        )
    return "\n".join(lines) + "\n"


def cmd_next_number(cwd: Path) -> dict:
    """返回下一个 ADR 编号。"""
    adr_dir = cwd / ADR_DIR
    numbers = _scan_adr_numbers(adr_dir)
    next_num = (numbers[-1] + 1) if numbers else 1
    return {
        "ok": True,
        "status": "ok",
        "data": {"next_number": next_num, "formatted": f"ADR-{next_num:03d}"},
    }


def cmd_create(cwd: Path, title: str, number: int | None = None,
               status: str = "Proposed") -> dict:
    """创建 ADR 文件并更新索引。

    T11: README 缺失时先扫描现有 ADR 重建索引再追加。
    """
    adr_dir = cwd / ADR_DIR
    ensure_dir(adr_dir)

    # 确定编号
    if number is None:
        numbers = _scan_adr_numbers(adr_dir)
        number = (numbers[-1] + 1) if numbers else 1

    formatted_num = f"{number:03d}"
    slug = title.lower().replace(" ", "-")[:50]
    # 清理 slug 只保留安全字符
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    filename = f"ADR-{formatted_num}-{slug}.md"
    filepath = adr_dir / filename

    # 检查同编号是否已有文件（不同标题会生成不同 slug）
    existing = list(adr_dir.glob(f"ADR-{formatted_num}-*.md"))
    if existing or (adr_dir / f"ADR-{formatted_num}.md").exists():
        return {
            "ok": False,
            "status": "file_exists",
            "message": f"ADR-{formatted_num} 已存在: {existing[0] if existing else adr_dir / f'ADR-{formatted_num}.md'}",
            "formatted_text": f"❌ ADR-{formatted_num} 文件已存在，请使用不同编号或标题",
        }

    # 写入骨架
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    content = ADR_SKELETON.format(
        number=formatted_num, title=title, status=status, date=date_str
    )
    filepath.write_text(content, encoding="utf-8")

    # 更新 README
    readme_path = _readme_path(adr_dir)
    if readme_path.exists():
        rows = _parse_readme_index(readme_path)
    else:
        # T11: README 缺失 → 扫描现有 ADR 重建索引
        rows = []
        for f in sorted(adr_dir.glob("ADR-*.md")):
            if f.name == filename:
                continue
            m = re.match(r"ADR-(\d+)-(.+)\.md$", f.name)
            if m:
                # 从文件首行提取标题
                first_line = f.read_text(encoding="utf-8").splitlines()[0] if f.exists() else ""
                t = first_line.replace(f"# ADR-{m.group(1)}: ", "") if first_line else m.group(2)
                rows.append({
                    "number": int(m.group(1)),
                    "full_id": f"ADR-{m.group(1)}",
                    "title": t.replace("-", " ") if t else m.group(2),
                    "status": "Proposed",
                    "summary": "",
                })
        rows.sort(key=lambda r: r["number"])

    # 追加当前新建 ADR
    rows.append({
        "number": number,
        "full_id": f"ADR-{formatted_num}",
        "title": title,
        "status": status,
        "summary": "",
    })

    readme_content = _build_readme_content(rows)
    readme_path.write_text(readme_content, encoding="utf-8")

    return {
        "ok": True,
        "status": "created",
        "data": {
            "file": str(filepath),
            "number": number,
            "formatted": f"ADR-{formatted_num}",
        },
        "message": f"创建 ADR-{formatted_num}: {title} → {filepath}",
        "formatted_text": (
            f"📝 ADR-{formatted_num} 已创建\n"
            f"   文件: {filepath}\n"
            f"   状态: {status}\n"
            f"   索引: {readme_path} 已更新"
        ),
    }


def cmd_update_status(cwd: Path, number: int, new_status: str) -> dict:
    """更新已有 ADR 的 Status 行并同步 README。"""
    adr_dir = cwd / ADR_DIR
    formatted_num = f"{number:03d}"

    # 找到目标 ADR 文件
    target_file = None
    for f in adr_dir.glob(f"ADR-{formatted_num}-*.md"):
        target_file = f
        break

    if not target_file:
        # 也尝试匹配无后缀的命名
        exact = adr_dir / f"ADR-{formatted_num}.md"
        if exact.exists():
            target_file = exact

    if not target_file:
        return {
            "ok": False,
            "status": "not_found",
            "message": f"未找到 ADR-{formatted_num}",
            "formatted_text": f"❌ 未找到 ADR-{formatted_num}",
        }

    # 更新 Status 行
    content = target_file.read_text(encoding="utf-8")
    content = re.sub(
        r"^\*\*Status\*\*: .+",
        f"**Status**: {new_status}",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    target_file.write_text(content, encoding="utf-8")

    # 同步 README
    readme_path = _readme_path(adr_dir)
    if readme_path.exists():
        rows = _parse_readme_index(readme_path)
        updated = False
        if rows:
            for r in rows:
                if r["number"] == number:
                    r["status"] = new_status
                    updated = True
                    break
            if updated:
                readme_content = _build_readme_content(rows)
                readme_path.write_text(readme_content, encoding="utf-8")
        else:
            # Fallback: 解析失败时用正则直接替换 Status 列
            content = readme_path.read_text(encoding="utf-8")
            # 匹配 | ADR-NNN | ... | OldStatus | ... |
            pattern = rf"(\| ADR-{formatted_num} \| .+? \| )(.+?)( \|)"
            new_content = re.sub(pattern, rf"\g<1>{new_status}\3", content)
            if new_content != content:
                readme_path.write_text(new_content, encoding="utf-8")

    return {
        "ok": True,
        "status": "updated",
        "data": {"file": str(target_file), "new_status": new_status},
        "message": f"ADR-{formatted_num} 状态更新为 {new_status}",
        "formatted_text": (
            f"✏️ ADR-{formatted_num} 状态已更新\n"
            f"   新状态: {new_status}\n"
            f"   文件: {target_file}"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="diwu-flow ADR 管理")
    sub = parser.add_subparsers(dest="command")

    # next-number
    p_nn = sub.add_parser("next-number", help="获取下一个 ADR 编号")
    p_nn.add_argument("--cwd", type=str, default=".")

    # create
    p_cr = sub.add_parser("create", help="创建新 ADR")
    p_cr.add_argument("--title", type=str, required=True, help="ADR 标题")
    p_cr.add_argument("--number", type=int, default=None, help="指定编号（自动分配省略）")
    p_cr.add_argument("--status", type=str, default="Proposed", help="初始状态")
    p_cr.add_argument("--cwd", type=str, default=".")

    # update-status
    p_us = sub.add_parser("update-status", help="更新 ADR 状态")
    p_us.add_argument("--number", type=int, required=True, help="ADR 编号")
    p_us.add_argument("--status", type=str, required=True, help="新状态")
    p_us.add_argument("--cwd", type=str, default=".")

    args = parser.parse_args()
    cwd = Path(args.cwd).resolve()

    if args.command == "next-number":
        result = cmd_next_number(cwd)
    elif args.command == "create":
        result = cmd_create(cwd, args.title, args.number, args.status)
    elif args.command == "update-status":
        result = cmd_update_status(cwd, args.number, args.status)
    else:
        parser.print_help()
        result = {"ok": True, "status": "help"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
