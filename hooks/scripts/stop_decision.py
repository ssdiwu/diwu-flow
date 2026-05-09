"""Stop hook: default single-task mode + dloop cron mode.

执行顺序依赖（dloop 模式）：
  task_completed.py (TaskCompleted 事件) → 写 dloop.completed_task_ids
  stop_decision.py   (Stop 事件)            → 读 completed_task_ids + iteration 递增
两个 hook 由 CC 框架在不同事件上触发，执行顺序不确定。
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

from _shared import setup_sys_path, load_json_fallback, load_stdin_event  # noqa: E402

setup_sys_path()

from dloop_state import get_terminal_stop_reason  # noqa: E402
from session_scope import read_scoped_session_id  # noqa: E402

from dtask_state import (  # noqa: E402
    clear_loop_state,
    is_cron_mode,
    loop_state as runtime_loop_state,
    resolve_session_inprogress_task,
    save_runtime_state,
    sync_runtime_state,
)


def _verify_dloop_cleared(cwd: str) -> None:
    """安全网：确认 dtask-state.json 落盘中 dloop 已清空，防止 active=true 被 commit。"""
    try:
        state_path = os.path.join(cwd, ".diwu", "dtask-state.json")
        with open(state_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if saved.get("dloop") is not None and saved.get("dloop", {}).get("active") is True:
            print("[DLOOP_WARN] dtask-state.json 仍含 active=True 的 dloop 状态，commit 前请确认已清理", file=sys.stderr)
    except (OSError, json.JSONDecodeError):
        pass


def _repair_action(status: str) -> str:
    """返回修复命令名：missing_owner/owner_mismatch → adopt，其余 → claim"""
    return "adopt" if status in ("missing_owner", "owner_mismatch") else "claim"


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


def format_task(prefix, task):
    return (
        prefix + "\n\n"
        + f'Task#{task["id"]}: {task.get("title", task.get("description", ""))}\n'
        + f'任务描述：{task.get("description", "")}\n\n'
        + "验收条件：\n"
        + "\n".join(f"  - {item}" for item in task.get("acceptance", [])) + "\n\n"
        + "实施步骤：\n"
        + "\n".join(f"  {i + 1}. {step}" for i, step in enumerate(task.get("steps", []))) + "\n\n"
        + "按 workflow.md 流程执行。"
    )


def _save_task_data(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError:
        pass


def _generate_phase_report(loop_state, stop_reason, tasks):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    completed_ids = loop_state.get("completed_task_ids", [])
    iteration = loop_state.get("current_iteration", 0)
    max_tasks = loop_state.get("max_tasks", 0)
    started_at = loop_state.get("started_at", "unknown")

    done_tasks = [task for task in tasks if task["status"] == "Done" and task["id"] in set(completed_ids)]
    remaining = [task for task in tasks if task["status"] not in ("Done", "Cancelled")]

    report = []
    report.append("=" * 50)
    report.append("🏁 DLOOP 阶段报告")
    report.append("=" * 50)
    report.append("")
    report.append(f"停止原因 : {stop_reason}")
    report.append(f"启动时间   : {started_at}")
    report.append(f"结束时间   : {now}")
    report.append(f"总迭代次数 : {iteration}")
    report.append(f"任务上限   : {'无限' if max_tasks == 0 else max_tasks}")
    report.append("")
    report.append("--- 已完成任务 ---")
    if done_tasks:
        for task in done_tasks:
            report.append(f"  ✅ Task#{task['id']} {task['title']}")
    else:
        report.append("  （无）")
    report.append("")
    report.append("--- 剩余任务 ---")
    if remaining:
        for task in remaining:
            icon = {"InSpec": "📋", "InProgress": "🔄", "InReview": "👀"}.get(task["status"], "❓")
            report.append(f"  {icon} Task#{task['id']} {task['title']} [{task['status']}]")
    else:
        report.append("  （全部完成）")
    report.append("")
    report.append("=" * 50)
    return "\n".join(report)


def _prompt_suffix(additional_prompts):
    extra = ""
    for level, hint in additional_prompts:
        if level == "block":
            extra += f"\n\n⚠ {hint}"
        elif level in ("warning", "info"):
            extra += f"\n\nℹ {hint}"
    return extra


def _check_decision_reminder(cwd):
    """If recent session recording mentions decisions but decisions.md is empty/missing,
    return an info-level reminder prompt. Otherwise return empty string."""
    if not cwd:
        return ""
    import glob as _glob

    decisions_path = os.path.join(cwd, ".diwu", "decisions.md")
    # If decisions.md already has content, no need to remind
    if os.path.exists(decisions_path):
        try:
            with open(decisions_path, encoding="utf-8") as f:
                content = f.read().strip()
            if len(content) > 10:  # non-trivial content
                return ""
        except OSError:
            pass

    # Check latest 2 session recordings for decision-related keywords
    recording_dir = os.path.join(cwd, ".diwu", "recording")
    if not os.path.isdir(recording_dir):
        return ""

    sessions = sorted(
        _glob.glob(os.path.join(recording_dir, "session-*.md")),
        key=os.path.getmtime,
        reverse=True,
    )[:2]

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


def _check_recording_reminder(cwd):
    """If working directory has code changes but .diwu/recording/ has no recent session,
    return an info-level reminder suggesting /drec. Non-blocking."""
    if not cwd:
        return ""
    import glob as _glob
    import subprocess as _sp
    import time

    # Check for code changes (exclude .diwu/ internal state files)
    try:
        result = _sp.run(
            ["git", "status", "--short"],
            cwd=cwd, capture_output=True, text=True, timeout=10
        )
        raw = result.stdout
        lines = raw.splitlines() if raw.strip() else []
        # git status --short 格式: "XY path"（X=index Y=worktree，各 1 字符 + 空格 + 路径）
        # 首字符可能为空格（如 " M path" 表示仅工作区修改），
        # 用 split(None, 1) 提取路径更稳健，不受 strip/前导空格影响。
        code_changes = []
        for l in lines:
            parts = l.split(None, 1)
            if len(parts) == 2:
                path = parts[1]
                if path and not path.startswith(".diwu/"):
                    code_changes.append(path)
        if not code_changes:
            return ""
    except (OSError, _sp.TimeoutExpired):
        return ""

    # Check latest recording session file
    recording_dir = os.path.join(cwd, ".diwu", "recording")
    if not os.path.isdir(recording_dir):
        return (
            "\n"
            "检测到代码变更，建议先 /drec 记录本次 session "
            "（详见 drec §原子 Commit 职责）"
        )

    sessions = sorted(
        _glob.glob(os.path.join(recording_dir, "session-*.md")),
        key=os.path.getmtime,
        reverse=True,
    )
    if not sessions:
        return (
            "\n"
            "检测到代码变更，建议先 /drec 记录本次 session "
            "（详见 drec §原子 Commit 职责）"
        )

    # Compare timestamps: 如果最新 recording 早于代码变更（recording 过时），则提醒
    # 取代码变更文件中最近修改时间与 recording 时间对比
    latest_recording_mtime = os.path.getmtime(sessions[0])
    # 覆盖 staged + unstaged + untracked 三类变更（排除 .diwu/ 内部状态）
    try:
        # staged + unstaged
        diff_result = _sp.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=10
        )
        changed_files = diff_result.stdout.strip().split("\n") if diff_result.stdout.strip() else []
        # 追加 untracked 新文件（排除 .diwu/ 和 .gitignore 匹配项）
        untracked_result = _sp.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=cwd, capture_output=True, text=True, timeout=10
        )
        if untracked_result.stdout.strip():
            for uf in untracked_result.stdout.strip().split("\n"):
                uf = uf.strip()
                if uf and not uf.startswith(".diwu/"):
                    changed_files.append(uf)
        latest_code_mtime = 0
        for f in changed_files:
            f = f.strip()
            if f and not f.startswith(".diwu/"):
                fpath = os.path.join(cwd, f)
                if os.path.exists(fpath):
                    latest_code_mtime = max(latest_code_mtime, os.path.getmtime(fpath))
        # 如果没有可比较的文件变更时间，退回到绝对时间窗口判断
        if latest_code_mtime == 0:
            is_stale = (time.time() - latest_recording_mtime > 120)
        else:
            is_stale = (latest_code_mtime > latest_recording_mtime)
    except (OSError, _sp.TimeoutExpired):
        is_stale = (time.time() - latest_recording_mtime > 120)

    if is_stale:
        return (
            "\n"
            "检测到代码变更，最近 recording 已超过 5 分钟，建议先 /drec 更新记录 "
            "（详见 drec §原子 Commit 职责）"
        )

    return ""


def _check_diu_dirty(cwd) -> tuple[bool, list[str]]:
    """检测 .diwu/ 内部状态文件是否有未提交变更。

    与 _check_recording_reminder() 互补：
    - recording reminder 排除 .diwu/（关注代码变更）
    - 本函数专注 .diwu/（关注状态文件变更）

    返回 (has_dirty, dirty_files)。
    """
    DIU_DIRTY_PREFIXES = (
        ".diwu/dtask.json",
        ".diwu/dtask-state.json",
        ".diwu/recording/",
    )

    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=cwd, capture_output=True, text=True, timeout=10,
        )
        raw = result.stdout
        lines = raw.splitlines() if raw.strip() else []
    except (OSError, subprocess.TimeoutExpired):
        return False, []

    dirty = []
    for l in lines:
        # git status --short 格式: "XY path"（X=index Y=worktree，各 1 字符 + 空格 + 路径）
        # 首字符可能为空格（如 " M path" 表示仅工作区修改），
        # 用 split(maxsplit=1) 提取路径更稳健，不受 strip/前导空格影响。
        parts = l.split(None, 1)
        if len(parts) == 2:
            path = parts[1]
            if any(path.startswith(p) or path == p for p in DIU_DIRTY_PREFIXES):
                dirty.append(path)

    # 补充：未跟踪文件（git status --short 不列出目录内文件）
    if not dirty:
        try:
            untracked_result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=cwd, capture_output=True, text=True, timeout=10,
            )
            if untracked_result.stdout.strip():
                for uf in untracked_result.stdout.strip().split("\n"):
                    uf = uf.strip()
                    if any(uf.startswith(p) or uf == p for p in DIU_DIRTY_PREFIXES):
                        dirty.append(uf)
        except (OSError, subprocess.TimeoutExpired):
            pass

    return len(dirty) > 0, dirty


_STALE_THRESHOLD_SECS = 30 * 60  # 30 分钟


def _check_pending_recording_gate(cwd, current_session_id=""):
    """检测 pending_recording 标记 + .diwu/ dirty → 强制门控提示。

    返回 (level, hint):
      ("block", hint)  — 本次 session 的 release + 有 .diwu/ 未提交变更 + ≤30min
      ("warn", hint)   — stale 标记 / 其他 session / 工作区干净但标记存在且 stale
      ("", "")         — 无标记，无需处理
    """
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

    has_diu_dirty, _ = _check_diu_dirty(cwd)

    task_id = pr.get("task_id", "?")
    target_status = pr.get("target_status", "?")
    pr_session_id = pr.get("session_id", "")

    is_own_session = bool(current_session_id and current_session_id == pr_session_id)

    # 非 owner session 完全静默：/drec 需要任务执行上下文，
    # 非 owner 不可能拥有该上下文，block/warn 均无意义
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


def decide_default_mode(tasks, settings, data, task_json_path, additional_prompts, runtime_state, session_id, cwd=None):
    extra = _prompt_suffix(additional_prompts)
    resolved_sid = _resolve_stop_session_id(session_id or "", cwd or "")
    resolution = resolve_session_inprogress_task(tasks, runtime_state or {}, resolved_sid)

    if resolution.is_match and resolution.task.get("status") == "InProgress":
        return True, {"decision": "block", "reason": format_task("继续完成当前任务（断点恢复）：", resolution.task) + extra}

    # is_match 但 status 非 InProgress → stale task_sessions entry，降级为 hint
    if resolution.is_match:
        task_id = resolution.task.get("id") if resolution.task else "?"
        print(
            f"[STOP_HINT] Task#{task_id} task_sessions 有 stale owner 但当前状态为 "
            f"{resolution.task.get('status')}（非 InProgress），已跳过断点恢复。",
            file=sys.stderr,
        )
        return False, {}

    if resolution.status in ("missing_owner", "owner_mismatch", "invalid_runtime_state"):
        task_id = resolution.task.get("id") if resolution.task else "?"
        action = _repair_action(resolution.status)
        plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "<plugin-root>")
        hint = (
            f"[STOP_HINT] {resolution.reason}。"
            f" 请先执行 {action} 补全 owner 记录后再继续："
            f" python3 {plugin_root}/scripts/dtask_transition.py "
            f"{action} --task-id {task_id} --session-id \"$SESSION_ID\" --cwd <proj>"
        )
        print(hint, file=sys.stderr)
        return False, {}

    done_ids = {task["id"] for task in tasks if task.get("status") == "Done"}
    executable = [
        task for task in tasks
        if task.get("status") == "InSpec"
        and all(blocker_id in done_ids for blocker_id in task.get("blocked_by", []))
    ]
    if executable:
        summary = (
            "当前无进行中任务，Session 结束。\n"
            f'可执行任务: Task#{executable[0]["id"]} {executable[0].get("title", "")} (InSpec)\n'
            "输入 /drun 继续执行，或 /dloop 启动 cron 批量循环。"
        )
        print(summary, file=sys.stderr)

    # Soft reminder: check if session had decisions that should be recorded
    decision_hint = _check_decision_reminder(cwd)
    if decision_hint:
        print(f"\n{decision_hint}", file=sys.stderr)

    # Soft reminder: check if code changes exist without recent recording
    recording_hint = _check_recording_reminder(cwd)
    if recording_hint:
        print(recording_hint, file=sys.stderr)

    # Layer 1: pending_recording 强制门控
    pr_level, pr_hint = _check_pending_recording_gate(cwd, resolved_sid)
    if pr_level == "block":
        return True, {"decision": "block", "reason": pr_hint + extra}
    elif pr_level == "warn":
        print(pr_hint, file=sys.stderr)

    return False, {}


def decide_cron_mode(tasks, settings, data, task_json_path, loop_state, cwd,
                     additional_prompts, runtime_state, session_id=""):
    """Cron 模式停止判定：只判断是否终止，不驱动循环续跑。

    cron 模式的每次 iteration 是独立 session，Stop hook 触发时：
    - InProgress 任务且 owner 匹配 → block（与 default_mode 行为一致）
    - 终止条件命中 → 生成报告 + 清理 dloop + 提示执行 /dstop
    - 未终止 → 返回 (False, {}) 允许 session 自然结束（等下次 Cron 触发）
    """
    extra = _prompt_suffix(additional_prompts)

    # InProgress 任务阻断：与 decide_default_mode 行为一致
    resolved_sid = _resolve_stop_session_id(session_id or "", cwd or "")
    resolution = resolve_session_inprogress_task(tasks, runtime_state or {}, resolved_sid)
    if resolution.is_match and resolution.task.get("status") == "InProgress":
        return True, {"decision": "block", "reason": format_task("继续完成当前任务（断点恢复）：", resolution.task) + extra}

    max_tasks = loop_state.get("max_tasks", 0)
    iteration = loop_state.get("current_iteration", 0)

    stop_reason = get_terminal_stop_reason(
        tasks, settings=settings, data=data, loop_state_data=loop_state
    )
    if stop_reason is not None:
        notify(f"dloop cron 循环结束：{stop_reason}")
        loop_state["active"] = False
        loop_state["stopped_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        loop_state["stop_reason"] = stop_reason
        report = _generate_phase_report(loop_state, stop_reason, tasks)
        cron_job_id = loop_state.get("cron_job_id")
        clear_loop_state(runtime_state)
        save_runtime_state(cwd, runtime_state, remove_legacy=True)
        _verify_dloop_cleared(cwd)
        print(report, file=sys.stderr)
        if cron_job_id:
            print(
                f"[STOP_HINT] dloop cron 模式已终止（{stop_reason}）。"
                f"请执行 /dstop 清理 CronJob({cron_job_id})",
                file=sys.stderr,
            )
        else:
            print(
                "[STOP_HINT] dloop cron 模式已停止。请执行 /dstop 清理资源。",
                file=sys.stderr,
            )
        return False, {}

    # 未终止 → session 自然结束，等下次 Cron 触发
    _cron_completed = len(loop_state.get("completed_task_ids", []))
    print(
        f"[STOP_HINT] [dloop-cron] iteration {iteration} 完成，"
        f"等待下次 Cron 触发（completed: {_cron_completed} tasks）",
        file=sys.stderr,
    )
    return False, {}


def decide(tasks, settings, data, task_json_path, cwd, additional_prompts, loop_state, runtime_state=None, session_id=""):
    if loop_state is not None:
        return decide_cron_mode(
            tasks, settings, data, task_json_path, loop_state, cwd,
            additional_prompts, runtime_state or {}, session_id,
        )
    return decide_default_mode(tasks, settings, data, task_json_path, additional_prompts, runtime_state or {}, session_id, cwd)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stop hook: dual-mode decision")
    parser.add_argument("--task-json", default=".diwu/dtask.json", help="Path to dtask.json")
    parser.add_argument("--settings-json", default=".diwu/dsettings.json", help="Path to dsettings.json")
    args = parser.parse_args()

    stdin_data = load_stdin_event(check_tty=True)

    if stdin_data.get("stop_hook_active", False):
        print(json.dumps({"continue": False}, ensure_ascii=False))
        sys.exit(0)

    cwd = stdin_data.get("cwd") or os.getcwd()
    task_json_path = os.path.join(cwd, args.task_json) if not os.path.isabs(args.task_json) else args.task_json
    settings_path = os.path.join(cwd, args.settings_json) if not os.path.isabs(args.settings_json) else args.settings_json
    data = load_json_fallback(task_json_path)
    settings = load_json_fallback(settings_path)
    tasks = data.get("tasks", [])

    sync_result = sync_runtime_state(cwd, data, persist=True)
    if sync_result.is_invalid:
        print(f"[STOP_HINT] dtask-state.json 无效：{sync_result.reason}。请检查文件格式或执行 /dinit validate 修复", file=sys.stderr)
        sys.exit(0)

    runtime_state = sync_result.state
    loop_state = runtime_loop_state(runtime_state)

    # Fallback: task_completed.py (TaskCompleted 事件) 和 stop_decision.py (Stop 事件)
    # 由 CC 框架在不同事件上触发，执行顺序不确定。如果 stop_decision 先于
    # task_completed 执行，completed_task_ids 可能尚未包含最新 Done 任务。
    # 仅在 dloop 模式下生效（loop_state 非 None）。
    # important: 用 initial_done_ids 快照排除历史 Done，只计入本轮新增完成。
    _effective_completed_for_check = []
    if loop_state is not None:
        current_completed = loop_state.get("completed_task_ids", [])
        initial_done = set(loop_state.get("initial_done_ids", []))
        done_ids_from_json = {t["id"] for t in tasks if t.get("status") == "Done"}
        # 只补充本轮新增的 Done（排除 dloop start 时已存在的）
        new_done_ids = [tid for tid in done_ids_from_json
                        if tid not in current_completed and tid not in initial_done]
        _effective_completed_for_check = current_completed + new_done_ids
    event_session_id = hook_session_id(stdin_data)
    session_id = _resolve_stop_session_id(event_session_id, cwd)

    additional_prompts = []
    try:
        import stop_archive

        additional_prompts = stop_archive.check(settings=settings, tasks=tasks, cwd=cwd)
    except (ImportError, AttributeError, OSError):
        pass

    # 将 effective completed_task_ids 传入 decide，
    # 使 get_terminal_stop_reason() 的 max_tasks 判断基于完整数据。
    # 使用副本避免污染运行态 loop_state（不写回 dtask-state.json）。
    decide_loop_state = loop_state
    if loop_state is not None and _effective_completed_for_check:
        original_completed = loop_state.get("completed_task_ids", [])
        if len(_effective_completed_for_check) > len(original_completed):
            decide_loop_state = {**loop_state, "completed_task_ids": _effective_completed_for_check}

    should_continue, output = decide(
        tasks,
        settings,
        data,
        task_json_path,
        cwd,
        additional_prompts,
        decide_loop_state,
        runtime_state=runtime_state,
        session_id=session_id,
    )
    if output:
        print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)
