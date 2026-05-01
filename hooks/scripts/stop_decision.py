"""Stop hook: default single-task mode + dloop mode."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HOOKS_DIR))
SHARED_SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SHARED_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SHARED_SCRIPTS_DIR)

from dloop_state import get_terminal_stop_reason  # noqa: E402

_DUMMY_PREFIX = "dloop-"  # dloop.py start 生成的 dummy session_id 前缀
from dtask_state import (  # noqa: E402
    clear_loop_state,
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


def _load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


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


def decide_default_mode(tasks, settings, data, task_json_path, additional_prompts, runtime_state, session_id, cwd=None):
    extra = _prompt_suffix(additional_prompts)
    resolution = resolve_session_inprogress_task(tasks, runtime_state or {}, session_id or "")

    if resolution.is_match:
        return True, {"decision": "block", "reason": format_task("继续完成当前任务（断点恢复）：", resolution.task) + extra}

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
            "输入 /drun 继续执行，或 /dloop 启动连续循环。"
        )
        print(summary, file=sys.stderr)

    # Soft reminder: check if session had decisions that should be recorded
    decision_hint = _check_decision_reminder(cwd)
    if decision_hint:
        print(f"\n{decision_hint}", file=sys.stderr)

    return False, {}


def decide_loop_mode(tasks, settings, data, task_json_path, loop_state, cwd, additional_prompts, runtime_state, session_id):
    max_tasks = loop_state.get("max_tasks", 0)
    iteration = loop_state.get("current_iteration", 0)
    extra = _prompt_suffix(additional_prompts)

    resolution = resolve_session_inprogress_task(tasks, runtime_state or {}, session_id or "")
    if resolution.is_match:
        return True, {
            "decision": "block",
            "reason": format_task(f"🔄 dloop iteration {iteration + 1} | 继续当前任务（断点恢复）：", resolution.task) + extra,
        }
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

    in_review = [task for task in tasks if task.get("status") == "InReview"]

    stop_reason = get_terminal_stop_reason(tasks, settings=settings, data=data, loop_state_data=loop_state)
    if stop_reason is not None:
        notify(f"dloop 循环结束：{stop_reason}")
        loop_state["active"] = False
        loop_state["stopped_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        loop_state["stop_reason"] = stop_reason
        report = _generate_phase_report(loop_state, stop_reason, tasks)
        clear_loop_state(runtime_state)
        save_runtime_state(cwd, runtime_state, remove_legacy=True)
        # 安全网：确认落盘文件中 dloop 已被清空（防止 active=true 被 commit）
        _verify_dloop_cleared(cwd)
        print(report, file=sys.stderr)
        return False, {}

    # 未命中停止条件 → 迭代计数 + 委托 /drun 执行下一轮
    next_iteration = iteration + 1
    loop_state["current_iteration"] = next_iteration
    save_runtime_state(cwd, runtime_state, remove_legacy=True)

    # InReview 计数更新（停止条件输入数据，保留原有语义）
    if in_review:
        data["review_used"] = data.get("review_used", 0) + 1
        _save_task_data(task_json_path, data)

    # completed_task_ids 由 task_completed.py 在 Done 事件时精确追加
    # 此处只读不写，用于 max_tasks 判断和阶段报告

    return True, {
        "decision": "block",
        "reason": (
            f"dloop iteration {next_iteration}/{f'∞' if max_tasks == 0 else max_tasks} | "
            f"请继续执行 /drun 完成下一轮任务"
        ) + extra,
    }


def decide(tasks, settings, data, task_json_path, cwd, additional_prompts, loop_state, runtime_state=None, session_id=""):
    if loop_state is not None:
        return decide_loop_mode(
            tasks, settings, data, task_json_path, loop_state, cwd, additional_prompts, runtime_state or {}, session_id
        )
    return decide_default_mode(tasks, settings, data, task_json_path, additional_prompts, runtime_state or {}, session_id, cwd)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stop hook: dual-mode decision")
    parser.add_argument("--task-json", default=".diwu/dtask.json", help="Path to dtask.json")
    parser.add_argument("--settings-json", default=".diwu/dsettings.json", help="Path to dsettings.json")
    args = parser.parse_args()

    stdin_data = {}
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
            if raw.strip():
                stdin_data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            pass

    if stdin_data.get("stop_hook_active", False):
        print(json.dumps({"continue": False}, ensure_ascii=False))
        sys.exit(0)

    cwd = stdin_data.get("cwd") or os.getcwd()
    task_json_path = os.path.join(cwd, args.task_json) if not os.path.isabs(args.task_json) else args.task_json
    settings_path = os.path.join(cwd, args.settings_json) if not os.path.isabs(args.settings_json) else args.settings_json
    data = _load_json(task_json_path)
    settings = _load_json(settings_path)
    tasks = data.get("tasks", [])

    sync_result = sync_runtime_state(cwd, data, persist=True)
    if sync_result.is_invalid:
        print(f"[STOP_HINT] dtask-state.json 无效：{sync_result.reason}。请检查文件格式或执行 /dinit validate 修复", file=sys.stderr)
        sys.exit(0)

    runtime_state = sync_result.state
    loop_state = runtime_loop_state(runtime_state)
    session_id = hook_session_id(stdin_data)

    if loop_state is not None:
        loop_sid = loop_state.get("session_id", "")

        # 分支1: Stop event 缺失 session_id → 阻止驱动循环（exit 1）
        if not session_id:
            print("[STOP_HINT] Stop 事件缺少 session_id，跳过 dloop 驱动", file=sys.stderr)
            sys.exit(1)

        # 分支2: 首次绑定 — dummy ID 替换为真实 session_id（一次性）
        elif loop_sid.startswith(_DUMMY_PREFIX):
            loop_state["session_id"] = session_id
            save_runtime_state(cwd, runtime_state, remove_legacy=True)

        # 分支3: 已绑定但不匹配 → 退出 loop mode
        elif loop_sid != session_id:
            loop_state = None
        # else: 匹配 → 进入 loop mode（原有正常路径）

    additional_prompts = []
    try:
        import stop_archive

        additional_prompts = stop_archive.check(settings=settings, tasks=tasks, cwd=cwd)
    except Exception:
        pass

    should_continue, output = decide(
        tasks,
        settings,
        data,
        task_json_path,
        cwd,
        additional_prompts,
        loop_state,
        runtime_state=runtime_state,
        session_id=session_id,
    )
    if output:
        print(json.dumps(output, ensure_ascii=False))
    sys.exit(0 if should_continue else 1)
