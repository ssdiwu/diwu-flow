#!/usr/bin/env python3
"""diwu-flow drec: recording closeout 脚本

检测 AI 已写入的 recording 文件，执行归档 + git commit/amend + 清理 pending。

CLI: python3 scripts/drec_write.py run --cwd <proj>

契约:
  前置: AI 已写入 .diwu/recording/session-{timestamp}.md（由 date 命令获取时间戳）
  输出: stdout JSON {ok, status, recording_path, commit_hash, archive_summary}
  失败时 ok=false + message + recovery_hint
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (  # noqa: E402
    DIWU_DIR,
    DTASK_STATE_TOML,
    RECORDING_DIR,
    error_exit,
    load_toml_or_empty,
    save_toml,
)

# ── 常量 ──────────────────────────────────────────────

PENDING_KEY = "pending_recording"
AMEND_WINDOW_SECONDS = 600  # 10 分钟

# Category → 中文前缀映射（Task#96 约定）
_CATEGORY_PREFIX_MAP = {
    "functional": "[功能]",
    "ui": "[界面]",
    "bugfix": "[修复]",
    "refactor": "[重构]",
    "infra": "[基建]",
    "release": "[发版]",
}

# ── 工具函数 ────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_timestamp() -> str:
    """生成 commit message 用的时间戳（非文件名时间戳）。"""
    return datetime.now().strftime("%Y-%m-%d-%H%M%S")


def _run_git(cwd: Path, *args) -> subprocess.CompletedProcess:
    """执行 git 命令，返回 CompletedProcess。"""
    return subprocess.run(
        ["git"] + list(args),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _git_head_subject(cwd: Path) -> str | None:
    """获取 HEAD commit 的 subject 行。"""
    cp = _run_git(cwd, "log", "-1", "--format=%s")
    if cp.returncode == 0:
        return cp.stdout.strip()
    return None


def _git_has_unpushed(cwd: Path) -> bool:
    """检查 HEAD 是否有未 push 的提交。保守返回 True（禁止 amend）。"""
    cp = _run_git(cwd, "rev-parse", "@{u}", "HEAD")
    if cp.returncode != 0:
        return True
    lines = cp.stdout.strip().splitlines()
    if len(lines) < 2:
        return True
    upstream, head = lines[0], lines[1]
    if upstream == head:
        return False
    cp2 = _run_git(cwd, "merge-base", "--is-ancestor", head, upstream)
    return cp2.returncode != 0


def _find_latest_recording(cwd: Path) -> Path | None:
    """扫描 recording/ 目录，返回 mtime 最新的 session 文件。无则返回 None。"""
    rec_dir = cwd / RECORDING_DIR
    if not rec_dir.exists():
        return None
    session_files = sorted(
        rec_dir.glob("session-*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return session_files[0] if session_files else None


def _load_pending(cwd: Path) -> dict | None:
    """读取 pending_recording 标记。"""
    state_path = cwd / DTASK_STATE_TOML
    data = load_toml_or_empty(state_path)
    pending = data.get(PENDING_KEY)
    if not pending:
        return None
    if isinstance(pending, dict):
        return pending
    return {"exists": bool(pending)}


def _clear_pending(cwd: Path) -> bool:
    """清除 pending_recording 标记。"""
    try:
        cp = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "dtask_transition.py"),
             "clear-pending", "--cwd", str(cwd)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return cp.returncode == 0
    except Exception:
        return False


def _should_amend(cwd: Path, pending: dict) -> bool:
    """判定是否进入 Amend 模式（去 git 化方案）。

    有 pending + released_at ≤ 600s → 尝试 amend。
    """
    if not pending:
        return False
    released_at = pending.get("released_at")
    if not released_at:
        return False
    try:
        release_dt = datetime.fromisoformat(released_at)
        if release_dt.tzinfo is None:
            release_dt = release_dt.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - release_dt).total_seconds()
        if elapsed > AMEND_WINDOW_SECONDS:
            return False
    except (ValueError, TypeError):
        return False
    return True


def _run_archive(cwd: Path) -> dict:
    """调用 drec_archive.py 执行归档。"""
    archive_script = Path(__file__).parent / "drec_archive.py"
    try:
        cp = subprocess.run(
            [sys.executable, str(archive_script), "run", "--cwd", str(cwd)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if cp.returncode == 0 and cp.stdout.strip():
            return json.loads(cp.stdout.strip())
        return {"ok": True, "tasks_archived": 0, "recordings_moved": 0}
    except Exception as e:
        return {"ok": False, "error": str(e), "tasks_archived": 0, "recordings_moved": 0}


def _git_commit(cwd: Path, message: str, amend: bool = False) -> tuple[bool, str]:
    """执行 git add + commit。返回 (success, hash_or_error)。"""
    add_cp = _run_git(cwd, "add", "-A")
    if add_cp.returncode != 0:
        return False, f"git add 失败: {add_cp.stderr.strip()}"

    status_cp = _run_git(cwd, "status", "--porcelain")
    if not status_cp.stdout.strip():
        return True, "no_changes"

    if amend:
        cp = _run_git(cwd, "commit", "--amend", "-m", message)
    else:
        cp = _run_git(cwd, "commit", "-m", message)

    if cp.returncode != 0:
        return False, f"git commit 失败: {cp.stderr.strip()}"

    hash_cp = _run_git(cwd, "rev-parse", "HEAD")
    if hash_cp.returncode == 0:
        return True, hash_cp.stdout.strip()
    return True, "(hash unavailable)"


# ── Gap 检测（G1/G2/G3） ───────────────────────


def _get_changed_files_since_head(cwd: Path) -> set[str]:
    """获取相对于 HEAD 的变更文件集合（git diff）。"""
    try:
        cp = _run_git(cwd, "diff", "--name-only", "HEAD")
        if cp.returncode == 0 and cp.stdout.strip():
            return set(cp.stdout.strip().splitlines())
    except Exception:
        pass
    return set()


def _get_git_status_files(cwd: Path) -> list[str]:
    """获取 git status 中有变更的文件（含 staged + unstaged + untracked）。"""
    try:
        cp = _run_git(cwd, "status", "--porcelain")
        if cp.returncode == 0 and cp.stdout.strip():
            files = []
            for line in cp.stdout.strip().splitlines():
                parts = line.split(None, 1)
                if len(parts) >= 2:
                    files.append(parts[1])
            return files
    except Exception:
        pass
    return []


# ── 前缀读取（Task#96：AI 判断，脚本只读） ─────────


def _read_commit_prefix(rec_path: Path | None) -> str:
    """从 AI 写入的 recording 中读取已决定的中文前缀。

    职责边界：前缀由 AI 根据实际变更内容判断并写入 recording 的 Category 行。
    脚本只做读取，不做启发式推断。
    """
    if not rec_path or not rec_path.exists():
        return "[记录]"
    try:
        text = rec_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "category" not in line.lower():
                continue
            # 用 rsplit 取冒号后的值（兼容 **Category:** / **Category** : 等格式）
            parts = line.rsplit(":", 1)
            if len(parts) < 2:
                continue
            raw = parts[1].strip().strip("*").strip()
            cat = raw.split()[0].lower().rstrip(",") if raw else ""
            if cat:
                return _CATEGORY_PREFIX_MAP.get(cat, "[记录]")
    except Exception:
        pass
    return "[记录]"


def _check_g1_rules_vs_doc(cwd: Path, changed_files: set[str]) -> dict:
    """G1: rules/skills/agents 变更 vs .doc/ 更新。"""
    diwu_dirs = {"rules", "skills", "agents"}
    doc_dir = cwd / ".doc"
    changed_diwu = [f for f in changed_files
                    if any(f.startswith(d + "/") or f == d or f.startswith(d + "\\")
                        for d in diwu_dirs)]
    if not changed_diwu:
        return {"check": "G1", "status": "SYNCED", "detail": "无 rules/skills/agents 变更"}

    # 检查 .doc/ 中是否有对应更新
    doc_changed = any(".doc/" in f or f.startswith(".doc\\") or f.startswith(".doc/")
                       for f in changed_files)
    if doc_changed:
        return {"check": "G1", "status": "SYNCED",
                "detail": f"rules/skills/agents 变更 {len(changed_diwu)} 个文件，.doc/ 也有更新"}

    # .doc/ 存在但本次未更新
    if not doc_dir.exists():
        return {"check": "G1", "status": "GAP_DETECTED",
                "detail": f"rules/skills/agents 变更 {len(changed_diwu)} 个文件，.doc/ 目录不存在"}

    return {"check": "G1", "status": "GAP_DETECTED",
            "detail": f"rules/skills/agents 变更 {', '.join(changed_diwu[:3])} 等 {len(changed_diwu)} 个文件，.doc/ 未同步更新"}


def _check_g2_dfeat_doc_sync(cwd: Path, changed_files: set[str]) -> dict:
    """G2: dfeat.doc_sync 要求 vs 实际 .doc/ 更新。"""
    dfeat_dir = cwd / ".diwu" / "dfeat"
    if not dfeat_dir.is_dir():
        return {"check": "G2", "status": "SYNCED", "detail": "无 dfeat 目录"}

    # 扫描有 doc_scope 声明的 dfeat
    try:
        import tomllib
        has_pending = False
        details = []
        for f in sorted(dfeat_dir.glob("*.toml")):
            if not (f.name.startswith("active_") or f.name.startswith("hold_")):
                continue
            try:
                data = tomllib.load(open(f, "rb"))
            except Exception:
                continue
            remote = data.get("remote", {})
            scope = remote.get("doc_scope")
            trigger = remote.get("trigger", "none")
            if not scope or trigger == "none":
                continue
            # 检查声明的 doc 文件是否在变更中
            doc_targets = []
            for item in scope:
                if isinstance(item, str):
                    doc_targets.append(item)
                elif isinstance(item, dict):
                    doc_targets.append(item.get("path", ""))
            # 简化判断：.doc/ 下是否有任何文件被修改
            doc_modified = any(any(t in cf or cf.endswith(t) for t in doc_targets)
                            for cf in changed_files)
            if not doc_modified and doc_targets:
                has_pending = True
                slug = data.get("id", {}).get("slug", f.stem)
                details.append(f"{slug}: doc_scope 声明 {len(doc_targets)} 个目标文件未同步")
        if has_pending:
            return {"check": "G2", "status": "GAP_DETECTED",
                    "detail": "; ".join(details)}
        return {"check": "G2", "status": "SYNCED", "detail": "无未满足的 doc_sync 要求"}
    except Exception:
        return {"check": "G2", "status": "SYNCED", "detail": "检查跳过（解析异常）"}


def _check_g3_version_changelog(cwd: Path, changed_files: set[str]) -> dict:
    """G3: 版本号 vs CHANGELOG。"""
    plugin_json = cwd / ".claude-plugin" / "plugin.json"
    changelog = cwd / "CHANGELOG.md"
    if not plugin_json.exists():
        return {"check": "G3", "status": "SYNCED", "detail": "无 plugin.json"}

    try:
        import json as _json
        pj = _json.loads(plugin_json.read_text(encoding="utf-8"))
        version = pj.get("version", "")
    except Exception:
        return {"check": "G3", "status": "SYNCED", "detail": "plugin.json 解析失败"}

    if not changelog.exists():
        return {"check": "G3", "status": "GAP_DETECTED",
                "detail": f"版本 {version} 但 CHANGELOG.md 不存在"}

    # 检查 CHANGELOG 是否在变更中
    changelog_modified = "CHANGELOG.md" in changed_files or \
                          str(changelog.relative_to(cwd)) in changed_files
    if changelog_modified:
        return {"check": "G3", "status": "SYNCED",
                "detail": f"CHANGELOG 已随版本 {version} 更新"}

    return {"check": "G3", "status": "SYNCED",
            "detail": f"CHANGELOG 未在本轮变更中（版本 {version}，可能已在之前更新）"}


def run_gap_detection(cwd: Path) -> dict:
    """执行 G1/G2/G3 三档 gap 检测。不阻塞 closeout。"""
    # 使用 git status 而非 git diff，因为 closeout 前文件可能未 staged
    changed = _get_git_status_files(cwd)
    if not changed:
        return {
            "gap_conclusion": "SYNCED",
            "checks": [],
            "message": "无代码变更，跳过 gap 检测",
        }

    g1 = _check_g1_rules_vs_doc(cwd, changed)
    g2 = _check_g2_dfeat_doc_sync(cwd, changed)
    g3 = _check_g3_version_changelog(cwd, changed)

    checks = [g1, g2, g3]
    gaps = [c for c in checks if c["status"] == "GAP_DETECTED"]
    conclusion = "GAP_DETECTED" if gaps else "SYNCED"

    return {
        "gap_conclusion": conclusion,
        "checks": checks,
        "message": f"GAP_DETECTED ({len(gaps)}/{len(checks)})" if gaps else "全部 SYNCED",
    }


# ── 远程镜像集成（fire-and-forget） ─────────────────


def _push_gap_comment(cwd: Path, gap_result: dict) -> None:
    """gap 检测为 GAP_DETECTED 时，向有 Issue 的 dfeat 推送 gap 评论。"""
    try:
        import subprocess as _sp
        remote_script = Path(__file__).parent / "dfeat_remote.py"
        if not remote_script.exists():
            return
        conclusion = gap_result.get("gap_conclusion", "")
        checks = gap_result.get("checks", [])
        lines = ["### Gap 检测结果", ""]
        for c in checks:
            lines.append(f"| {c['check']} | {c['status']} | {c.get('detail', '')} |")
        lines += ["", f"结论: {conclusion}", "", "*由 drec closeout 自动推送*"]
        body = "\n".join(lines)

        # 对所有有 Issue 的 active/hold dfeat 发评论
        dfeat_dir = cwd / ".diwu" / "dfeat"
        if not dfeat_dir.is_dir():
            return
        for f in sorted(dfeat_dir.iterdir()):
            if not f.is_file() or not f.suffix == ".toml":
                continue
            if not (f.name.startswith("active_") or f.name.startswith("hold_")):
                continue
            slug = f.name.split("_", 1)[1].replace(".toml", "") if "_" in f.name else ""
            _sp.run(
                [sys.executable, str(remote_script), "comment",
                 "--slug", slug, "--cwd", str(cwd), "--body", body],
                capture_output=True, timeout=30,
            )
    except Exception:
        pass


def _push_closeout_comment(cwd: Path, commit_hash: str) -> None:
    """closeout 成功后，向有 Issue 的 dfeat 推送 session 摘要评论。"""
    try:
        import subprocess as _sp
        remote_script = Path(__file__).parent / "dfeat_remote.py"
        if not remote_script.exists() or not commit_hash:
            return
        rec_path = _find_latest_recording(cwd)
        session_name = rec_path.name if rec_path else "unknown"
        body = (
            f"### Closeout 完成\n\n"
            f"- **commit**: `{commit_hash}`\n"
            f"- **recording**: {session_name}\n"
            f"- **time**: {_now_iso()}\n\n"
            f"*由 drec closeout 自动推送*"
        )

        dfeat_dir = cwd / ".diwu" / "dfeat"
        if not dfeat_dir.is_dir():
            return
        for f in sorted(dfeat_dir.iterdir()):
            if not f.is_file() or not f.suffix == ".toml":
                continue
            if not (f.name.startswith("active_") or f.name.startswith("hold_")):
                continue
            slug = f.name.split("_", 1)[1].replace(".toml", "") if "_" in f.name else ""
            _sp.run(
                [sys.executable, str(remote_script), "comment",
                 "--slug", slug, "--cwd", str(cwd), "--body", body],
                capture_output=True, timeout=30,
            )
    except Exception:
        pass


def _try_close_done_issues(cwd: Path) -> None:
    """closeout 时关闭所有 stage=Done 的 dfeat 对应 Issue。"""
    try:
        import subprocess as _sp
        remote_script = Path(__file__).parent / "dfeat_remote.py"
        if not remote_script.exists():
            return

        import tomllib as _tl
        dfeat_dir = cwd / ".diwu" / "dfeat"
        if not dfeat_dir.is_dir():
            return
        for f in sorted(dfeat_dir.iterdir()):
            if not f.is_file() or not f.suffix == ".toml":
                continue
            if not (f.name.startswith("active_") or f.name.startswith("hold_")):
                continue
            try:
                data = _tl.load(open(f, "rb"))
                stage = data.get("current_state", {}).get("stage", "")
                if stage == "Done":
                    slug = f.name.split("_", 1)[1].replace(".toml", "") if "_" in f.name else ""
                    _sp.run(
                        [sys.executable, str(remote_script), "close-issue",
                         "--slug", slug, "--cwd", str(cwd),
                         "--reason", "dfeat 已进入 Done 阶段"],
                        capture_output=True, timeout=30,
                    )
            except Exception:
                continue
    except Exception:
        pass


# ── 主流程 ─────────────────────────────────────────


def run(cwd: str = ".") -> dict:
    """主入口：检测已有 recording → 归档 → git commit。

    Args:
        cwd: 项目根目录路径字符串。

    Returns:
        结果字典。
    """
    root = Path(cwd).resolve()
    gap_result = {"gap_conclusion": "SYNCED", "checks": [], "message": "跳过（无 recording）"}

    # Step 1: 检测 AI 已写入的 recording 文件
    rec_path = _find_latest_recording(root)
    if rec_path is None:
        return {
            "ok": False,
            "status": "failed",
            "message": "未找到 recording 文件",
            "recovery_hint": (
                "AI 应先通过 `date '+%Y-%m-%d %H:%M:%S'` 获取时间戳，"
                "然后写入 .diwu/recording/session-{timestamp}.md，再调用本脚本"
            ),
            "gap_detection": gap_result,
        }

    # Step 2: 读取 pending_recording
    pending = _load_pending(root)

    # Step 3: 判定 amend
    amend_mode = _should_amend(root, pending)

    # Step 4: 归档
    archive_result = _run_archive(root)
    archive_ok = archive_result.get("ok", False)
    archive_summary = "无待归档内容"
    if archive_ok and archive_result.get("tasks_archived", 0) > 0:
        archive_summary = (
            f"归档 {archive_result['tasks_archived']} 个任务、"
            f"{archive_result.get('recordings_moved', 0)} 个 recording"
        )
    elif not archive_ok:
        archive_summary = f"归档异常: {archive_result.get('error', 'unknown')}"

    # Step 4.5: Gap 检测（G1/G2/G3，不阻塞 closeout）
    gap_result = run_gap_detection(root)

    # Step 4.6: Gap 检测 → 远程评论（fire-and-forget）
    if gap_result.get("gap_conclusion") == "GAP_DETECTED":
        _push_gap_comment(root, gap_result)

    # Step 5: 构造 commit message（动态前缀推断）
    ts = _now_timestamp()
    prefix = _read_commit_prefix(rec_path)
    if amend_mode:
        commit_msg = f"{prefix} Session {ts} — updated"
    else:
        commit_msg = f"{prefix} Session {ts} — closeout"

    # Step 6: git commit / amend
    success, result = _git_commit(root, commit_msg, amend=amend_mode)

    if not success:
        return {
            "ok": False,
            "status": "partial_success",
            "recording_path": str(rec_path.relative_to(root)),
            "commit_hash": None,
            "archive_summary": archive_summary,
            "message": result,
            "recovery_hint": (
                f"recording 已存在于 {rec_path.name}，pending_recording 保留。"
                f"解决 git 问题后重试"
            ),
            "gap_detection": gap_result,
        }

    if result == "no_changes":
        _clear_pending(root)
        return {
            "ok": True,
            "status": "no_changes",
            "recording_path": str(rec_path.relative_to(root)),
            "commit_hash": None,
            "archive_summary": archive_summary,
            "gap_detection": gap_result,
        }

    # Step 7: amend 失败时的 fallback
    if amend_mode and not success:
        fallback_msg = f"{prefix} Session {ts} — closeout (amend fallback)"
        success2, result2 = _git_commit(root, fallback_msg, amend=False)
        if not success2:
            return {
                "ok": False,
                "status": "partial_success",
                "recording_path": str(rec_path.relative_to(root)),
                "commit_hash": None,
                "archive_summary": archive_summary,
                "message": f"amend 和普通 commit 均失败: {result2}",
                "recovery_hint": "recording 和 pending 均保留，手动处理后重试",
                "gap_detection": gap_result,
            }
        success, result = success2, result2

    # Step 8: closeout 成功 → 远程评论 + 关闭 Issue（fire-and-forget）
    _push_closeout_comment(root, result)
    _try_close_done_issues(root)

    # Step 9: 清除 pending
    _clear_pending(root)

    return {
        "ok": True,
        "status": "committed" if not amend_mode else "amended",
        "recording_path": str(rec_path.relative_to(root)),
        "commit_hash": result,
        "archive_summary": archive_summary,
        "gap_detection": gap_result,
    }


# ── CLI ────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="diwu-flow recording closeout")
    parser.add_argument("command", choices=["run"], help="执行 closeout")
    parser.add_argument("--cwd", type=str, default=".", help="项目根目录")
    args = parser.parse_args()

    result = run(cwd=args.cwd)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
