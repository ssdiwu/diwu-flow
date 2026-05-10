"""Stop hook: default single-task mode + dloop cron mode.

执行顺序依赖（dloop 模式）：
  task_completed.py (TaskCompleted 事件) → 写 dloop.completed_task_ids
  stop_decision.py   (Stop 事件)            → 读 completed_task_ids + iteration 递增
两个 hook 由 CC 框架在不同事件上触发，执行顺序不确定。

性能优化：所有 git 子进程调用在 __main__ 入口处统一执行一次，
解析结果通过参数传递给下游检查函数，避免重复调用。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field

import platform

from _shared import setup_sys_path, load_json_fallback, load_stdin_event  # noqa: E402

setup_sys_path()

from dloop_state import get_terminal_stop_reason  # noqa: E402
from session_scope import read_scoped_session_id  # noqa: E402

from dtask_state import (  # noqa: E402
    clear_loop_state,
    is_cron_mode,
    loop_state as runtime_loop_state,
    save_runtime_state,
    sync_runtime_state,
)


# ── Git 结果缓存（入口处填充一次，下游只读）─────────────────


@dataclass(frozen=True)
class _GitInfo:
    """Parsed results from a single round of git subprocess calls."""
    status_lines: list[str] = field(default_factory=list)
    diff_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)

    @property
    def has_code_changes(self) -> bool:
        return any(not p.startswith(".diwu/") for p in self.status_lines if len(p.split(None, 1)) == 2)

    @property
    def code_change_paths(self) -> list[str]:
        out = []
        for line in self.status_lines:
            parts = line.split(None, 1)
            if len(parts) == 2:
                path = parts[1]
                if path and not path.startswith(".diwu/"):
                    out.append(path)
        return out

    @property
    def all_changed_files(self) -> list[str]:
        files = list(self.diff_files)
        for f in self.untracked_files:
            f = f.strip()
            if f and f not in files:
                files.append(f)
        return files

    @property
    def diu_dirty_files(self) -> list[str]:
        prefixes = (".diwu/dtask.json", ".diwu/dtask-state.json", ".diwu/recording/")
        dirty = []
        for line in self.status_lines:
            parts = line.split(None, 1)
            if len(parts) == 2:
                path = parts[1]
                if any(path.startswith(p) or path == p for p in prefixes):
                    dirty.append(path)
        for uf in self.untracked_files:
            uf = uf.strip()
            if any(uf.startswith(p) or uf == p for p in prefixes):
                dirty.append(uf)
        return dirty


def _run_git_checks(cwd: str, timeout: int = 10) -> _GitInfo:
    """Run git status / diff / ls-files exactly once. Returns parsed _GitInfo."""
    status_lines: list[str] = []
    diff_files: list[str] = []
    untracked: list[str] = []

    try:
        r = subprocess.run(
            ["git", "status", "--short"],
            cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
        status_lines = r.stdout.splitlines() if r.stdout.strip() else []
    except (OSError, subprocess.TimeoutExpired):
        pass

    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
        diff_files = [f for f in r.stdout.strip().split("\n") if f.strip()] if r.stdout.strip() else []
    except (OSError, subprocess.TimeoutExpired):
        pass

    try:
        r = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
        untracked = [f for f in r.stdout.strip().split("\n") if f.strip()] if r.stdout.strip() else []
    except (OSError, subprocess.TimeoutExpired):
        pass

    return _GitInfo(status_lines=status_lines, diff_files=diff_files, untracked_files=untracked)


# ── Recording 目录扫描（入口处扫一次）───────────────────────


def _scan_recording_files(cwd: str) -> list[str]:
    """Return recording session files sorted by mtime desc. Empty list if dir missing."""
    import glob as _glob

    rec_dir = os.path.join(cwd, ".diwu", "recording")
    if not os.path.isdir(rec_dir):
        return []
    return sorted(
        _glob.glob(os.path.join(rec_dir, "session-*.md")),
        key=os.path.getmtime,
        reverse=True,
    )


# ── 通知（无变更）──────────────────────────────────────────


def notify(msg):
    """Send OS notification (macOS/Linux)."""
    if os.environ.get("DIWU_SILENT") == "1":
        return
    try:
        safe_msg = msg.replace("'", "'\\''").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
        if platform.system() == "Darwin":
            subprocess.run(
                ["osascript", "-e", f'display notification "{safe_msg}" with title "diwu-flow" sound name "Glass"'],
                capture_output=True,
            )
        else:
            subprocess.run(["notify-send", "diwu-flow", safe_msg], capture_output=True)
    except (OSError, FileNotFoundError):
        pass
    try:
        if os.path.exists("/dev/tty"):
            open("/dev/tty", "w").write("\a")
    except OSError:
        pass


def hook_session_id(event: dict) -> str:
    return event.get("session_id") or event.get("sessionId") or ""


def _resolve_stop_session_id(event_session_id: str, cwd: str = "") -> str:
    """Stop Hook 的 session_id 解析：event → env → scoped session file → empty downgrade。

    与 dtask_transition._resolve_session_id() 的差异 ——
    本函数**不生成** drun-<timestamp> fallback SID。
    原因：Stop Hook 生成的 fallback SID 不可能等于 release 时写入的 session_id，
    生成出来只会制造假不匹配，导致 block 命中率下降。
    返回空字符串时，调用方应将"本次 session"判定降级为 warn。
    """
    if event_session_id:
        return event_session_id

    env_sid = os.environ.get("CLAUDE_SESSION_ID", "")
    if env_sid:
        return env_sid

    file_sid = read_scoped_session_id(cwd)
    if file_sid:
        return file_sid

    return ""


def _prompt_suffix(additional_prompts):
    extra = ""
    for level, hint in additional_prompts:
        if level == "block":
            extra += f"\n\n⚠ {hint}"
        elif level in ("warning", "info"):
            extra += f"\n\nℹ {hint}"
    return extra


# ── B 组检查函数（接受预计算结果，不再自行调用 git）─────────


def _check_decision_reminder(cwd, recording_files=None):
    """If recent session recording mentions decisions but decisions.md is empty/missing,
    return an info-level reminder prompt. Otherwise return empty string."""
    if not cwd:
        return ""

    decisions_path = os.path.join(cwd, ".diwu", "decisions.md")
    if os.path.exists(decisions_path):
        try:
            with open(decisions_path, encoding="utf-8") as f:
                content = f.read().strip()
            if len(content) > 10:
                return ""
        except OSError:
            pass

    sessions = (recording_files or [])[:2]
    decision_keywords = ["DECISION TRACE", "设计决策", "架构决策", "选定方案", "备选方案"]
    for s_path in sessions:
        try:
            with open(s_path, encoding="utf-8") as f:
                text = f.read()
            if any(kw in text for kw in decision_keywords):
                return (
                    "ℹ 检测到本轮 Session 包含设计决策记录，"
                    "请确认已追加到 .diwu/decisions.md"
                    "（详见 /drec §设计决策记录）"
                )
        except OSError:
            pass
    return ""


def _check_recording_reminder(cwd, git_info=None, recording_files=None):
    """If working directory has code changes but .diwu/recording/ has no recent session,
    return an info-level reminder suggesting /drec. Non-blocking.

    短路：无代码变更时直接返回空串，跳过文件时间戳比对。"""
    if not cwd:
        return ""

    gi = git_info
    if gi is None:
        gi = _run_git_checks(cwd)

    code_changes = gi.code_change_paths
    if not code_changes:
        return ""

    sessions = recording_files
    if sessions is None:
        sessions = _scan_recording_files(cwd)

    if not sessions:
        return (
            "\n"
            "检测到代码变更，建议先 /drec 记录本次 session "
            "（详见 drec §原子 Commit 职责）"
        )

    latest_recording_mtime = os.path.getmtime(sessions[0])

    changed_files = gi.all_changed_files
    latest_code_mtime = 0
    for f in changed_files:
        f = f.strip()
        if f and not f.startswith(".diwu/"):
            fpath = os.path.join(cwd, f)
            if os.path.exists(fpath):
                latest_code_mtime = max(latest_code_mtime, os.path.getmtime(fpath))

    if latest_code_mtime == 0:
        is_stale = (time.time() - latest_recording_mtime > 120)
    else:
        is_stale = (latest_code_mtime > latest_recording_mtime)

    if is_stale:
        return (
            "\n"
            "检测到代码变更，最近 recording 已超过 5 分钟，建议先 /drec 更新记录 "
            "（详见 drec §原子 Commit 职责）"
        )

    return ""


def _check_diu_dirty(cwd, git_info=None) -> tuple[bool, list[str]]:
    """检测 .diwu/ 内部状态文件是否有未提交变更。"""
    gi = git_info
    if gi is None:
        gi = _run_git_checks(cwd)

    dirty = gi.diu_dirty_files
    return len(dirty) > 0, dirty


_STALE_THRESHOLD_SECS = 30 * 60  # 30 分钟


def _check_pending_recording_gate(cwd, current_session_id="", git_info=None):
    """检测 pending_recording 标记 + .diwu/ dirty → 强制门控提示。"""
    if not cwd:
        return "", ""

    state_path = os.path.join(cwd, ".diwu", "dtask-state.json")
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return "", ""

    pr = state.get("pending_recording")
    if not pr or not isinstance(pr, dict):
        return "", ""

    released_at = pr.get("released_at", "")
    try:
        from datetime import datetime, timezone as _tz
        release_dt = datetime.fromisoformat(released_at)
        age_secs = (datetime.now(_tz.utc) - release_dt).total_seconds()
    except (ValueError, TypeError):
        age_secs = float('inf')

    is_stale = age_secs > _STALE_THRESHOLD_SECS

    has_diu_dirty, _ = _check_diu_dirty(cwd, git_info=git_info)

    task_id = pr.get("task_id", "?")
    target_status = pr.get("target_status", "?")
    pr_session_id = pr.get("session_id", "")

    is_own_session = bool(current_session_id and current_session_id == pr_session_id)

    if not is_own_session:
        return "", ""

    if not has_diu_dirty:
        if is_stale:
            return ("warn", (
                f"[PENDING_REC] Task#{task_id} ({target_status}) 的 pending_recording "
                f"标记已超过 {int(age_secs // 60)} 分钟且工作区干净。\n"
                f"如已完成 /drec，请确认标记已清除；否则可能需要手动清理。"
            ))
        return "", ""

    if not is_stale:
        return ("block", (
            f"\n⛔ [PENDING_REC] Task#{task_id} 已 release 为 {target_status} "
            f"但尚未执行 /drec 记录并 commit。\n"
            f".diwu/ 存在未提交变更，原子性要求：每个 Done 任务对应一次可回溯 commit。\n"
            f"**请立即执行 /drec** 完成记录与 commit 后再继续。"
        ))

    if is_stale:
        return ("warn", (
            f"\nℹ [PENDING_REC] 检测到过期 pending_recording 标记 "
            f"(Task#{task_id}, {int(age_secs // 60)} 分钟前)。\n"
            f"建议确认是否需要补执行 /drec。"
        ))


_FRESH_RECORDING_SECS = 300  # 5 分钟内有过 recording → 跳过 git 检查


def _needs_git_for_recording(recording_files, cwd):
    """Fast heuristic: if latest recording is fresh, skip git for recording reminder."""
    if not recording_files:
        return True  # No recordings at all → need to check
    try:
        age = time.time() - os.path.getmtime(recording_files[0])
        return age > _FRESH_RECORDING_SECS
    except OSError:
        return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stop hook: B group checks")
    parser.add_argument("--task-json", default=".diwu/dtask.json", help="Path to dtask.json")
    parser.add_argument("--settings-toml", default=".diwu/dsettings.toml", help="Path to dsettings.toml")
    args = parser.parse_args()

    stdin_data = load_stdin_event(check_tty=True)

    if stdin_data.get("stop_hook_active", False):
        print(json.dumps({"continue": False}, ensure_ascii=False))
        sys.exit(0)

    cwd = stdin_data.get("cwd") or os.getcwd()

    event_session_id = hook_session_id(stdin_data)
    session_id = _resolve_stop_session_id(event_session_id, cwd)

    # ── Phase 1: 零 git 快速路径 ────────────────────────
    # 大多数 Stop hook 调用是"干净"场景：无 pending_recording、decisions.md 已有内容、
    # 最近有新鲜 recording。这种情况下完全不需要任何 git 子进程。
    recording_files = _scan_recording_files(cwd)

    # 1a. pending_recording 门控（只需读 dtask-state.json，无需 git）
    pr_level, pr_hint = _check_pending_recording_gate(cwd, session_id, git_info=None)

    # 1b. block 级别必须知道 .diwu/ dirty 状态 → 需要进入 slow path
    needs_git = pr_level == "block"

    # 1c. decision reminder（只需读 decisions.md + recording 文件头）
    decision_hint = _check_decision_reminder(cwd, recording_files=recording_files)
    if decision_hint:
        print(f"\n{decision_hint}", file=sys.stderr)

    # 1d. recording reminder 快速判断：最近 5 分钟内有 recording → 跳过
    if not _needs_git_for_recording(recording_files, cwd):
        # Fast path 命中：输出已有的非 git 提示后直接退出
        if pr_level == "warn":
            print(pr_hint, file=sys.stderr)
        sys.exit(0)

    # ── Phase 2: 按需 git 慢速路径 ────────────────────────
    # 只有以下情况才到达这里：
    #   - pending_recording 为 block 级别（需检查 .diwu/ dirty）
    #   - 或 recording 不够新鲜（需检查是否有未记录的代码变更）
    needs_git = True
    git_info = _run_git_checks(cwd)

    # 重新评估 pending_recording（这次带 git_info 可准确判断 dirty）
    if pr_level == "block":
        pr_level, pr_hint = _check_pending_recording_gate(cwd, session_id, git_info=git_info)

    recording_hint = _check_recording_reminder(cwd, git_info=git_info, recording_files=recording_files)
    if recording_hint:
        print(recording_hint, file=sys.stderr)

    # B group: archive check (轻量 I/O，不涉及 git)
    additional_prompts = []
    try:
        import stop_archive
        additional_prompts = stop_archive.check(cwd=cwd)
    except (ImportError, AttributeError, OSError):
        pass

    extra = _prompt_suffix(additional_prompts)

    if pr_level == "block":
        output = {"decision": "block", "reason": pr_hint + extra}
        print(json.dumps(output, ensure_ascii=False))
    elif pr_level == "warn":
        print(pr_hint, file=sys.stderr)

    sys.exit(0)
