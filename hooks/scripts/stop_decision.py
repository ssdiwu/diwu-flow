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

from dloop_state import get_executable_tasks, get_terminal_stop_reason  # noqa: E402
from dtask_state import (  # noqa: E402
    clear_loop_state,
    loop_state as runtime_loop_state,
    resolve_session_inprogress_task,
    save_runtime_state,
    sync_runtime_state,
)


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
        print(resolution.reason, file=sys.stderr)
        return False, {"decision": resolution.status, "reason": resolution.reason}

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
        print(resolution.reason, file=sys.stderr)
        return False, {"decision": resolution.status, "reason": resolution.reason}

    next_tasks = [task for task in get_executable_tasks(tasks) if task.get("status") == "InSpec"]
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
        print(report, file=sys.stderr)
        return False, {}

    next_iteration = iteration + 1
    loop_state["current_iteration"] = next_iteration
    save_runtime_state(cwd, runtime_state, remove_legacy=True)

    if in_review:
        data["review_used"] = data.get("review_used", 0) + 1
        _save_task_data(task_json_path, data)

    target = next_tasks[0]
    return True, {
        "decision": "block",
        "reason": format_task(
            f"🔄 dloop iteration {next_iteration}/{f'∞' if max_tasks == 0 else max_tasks} | 继续执行下一个任务：",
            target,
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
    data = _load_json(args.task_json)
    settings = _load_json(args.settings_json)
    tasks = data.get("tasks", [])

    sync_result = sync_runtime_state(cwd, data, persist=True)
    if sync_result.is_invalid:
        output = {
            "decision": "invalid_runtime_state",
            "reason": f"dtask-state.json 无效：{sync_result.reason}",
        }
        print(json.dumps(output, ensure_ascii=False))
        sys.exit(1)

    runtime_state = sync_result.state
    loop_state = runtime_loop_state(runtime_state)
    session_id = hook_session_id(stdin_data)

    if loop_state is not None:
        loop_session_id = loop_state.get("session_id", "")
        if loop_session_id and session_id and loop_session_id != session_id:
            loop_state = None

    additional_prompts = []
    try:
        import stop_archive

        additional_prompts = stop_archive.check(settings=settings, tasks=tasks)
    except Exception:
        pass

    should_continue, output = decide(
        tasks,
        settings,
        data,
        args.task_json,
        cwd,
        additional_prompts,
        loop_state,
        runtime_state=runtime_state,
        session_id=session_id,
    )
    if output:
        print(json.dumps(output, ensure_ascii=False))
    sys.exit(0 if should_continue else 1)
