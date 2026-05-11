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
RECORDING_PREFIX = "[recording]"

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


# ── 主流程 ─────────────────────────────────────────


def run(cwd: str = ".") -> dict:
    """主入口：检测已有 recording → 归档 → git commit。

    Args:
        cwd: 项目根目录路径字符串。

    Returns:
        结果字典。
    """
    root = Path(cwd).resolve()

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

    # Step 5: 构造 commit message
    ts = _now_timestamp()
    if amend_mode:
        commit_msg = f"{RECORDING_PREFIX} Session {ts} — updated"
    else:
        commit_msg = f"{RECORDING_PREFIX} Session {ts} — closeout"

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
        }

    if result == "no_changes":
        _clear_pending(root)
        return {
            "ok": True,
            "status": "no_changes",
            "recording_path": str(rec_path.relative_to(root)),
            "commit_hash": None,
            "archive_summary": archive_summary,
        }

    # Step 7: amend 失败时的 fallback
    if amend_mode and not success:
        fallback_msg = f"{RECORDING_PREFIX} Session {ts} — closeout (amend fallback)"
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
            }
        success, result = success2, result2

    # Step 8: closeout 成功 → 清除 pending
    _clear_pending(root)

    return {
        "ok": True,
        "status": "committed" if not amend_mode else "amended",
        "recording_path": str(rec_path.relative_to(root)),
        "commit_hash": result,
        "archive_summary": archive_summary,
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
