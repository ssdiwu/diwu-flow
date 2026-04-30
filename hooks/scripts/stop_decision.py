"""Stop hook: dual-mode decision engine — default single-task / dloop loop mode.

Mode selection:
- Default (no .diwu/dloop-state.json): InProgress -> block (breakpoint recovery); else allow stop.
- Loop (.diwu/dloop-state.json exists + active): read state file, iterate, check stop conditions.
- On loop completion: auto-generate phase report + cleanup state file.
"""
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

DLOOP_STATE_PATH = ".diwu/dloop-state.json"
HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HOOKS_DIR))
SHARED_SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SHARED_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SHARED_SCRIPTS_DIR)

from dloop_state import get_executable_tasks, get_terminal_stop_reason  # noqa: E402


def notify(msg):
    """Send OS notification (macOS/Linux). Shell-safe via subprocess.

    可通过环境变量 DIWU_SILENT=1 禁用通知（测试环境）。
    """
    if os.environ.get("DIWU_SILENT") == "1":
        return
    try:
        safe_msg = msg.replace("'", "'\\''").replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
        if platform.system() == 'Darwin':
            subprocess.run(
                ['osascript', '-e', f'display notification "{safe_msg}" with title "diwu-flow" sound name "Glass"'],
                capture_output=True,
            )
        else:
            subprocess.run(
                ['notify-send', 'diwu-flow', safe_msg],
                capture_output=True,
            )
    except (OSError, FileNotFoundError):
        pass  # Notification not available (e.g., test environment)
    try:
        if os.path.exists('/dev/tty'):
            open('/dev/tty', 'w').write('\a')
    except OSError:
        pass  # No TTY available


def hook_session_id(event: dict) -> str:
    """Accept both session_id and sessionId event shapes."""
    return event.get("session_id") or event.get("sessionId") or ""


def format_task(prefix, t):
    """Format a task dict into a readable prompt string."""
    return (
        prefix + '\n\n'
        + f'Task#{t["id"]}: {t.get("title", t.get("description", ""))}\n'
        + f'任务描述：{t.get("description", "")}\n\n'
        + '验收条件：\n'
        + '\n'.join(f'  - {a}' for a in t.get("acceptance", [])) + '\n\n'
        + '实施步骤：\n'
        + '\n'.join(f'  {i+1}. {s}' for i, s in enumerate(t.get("steps", []))) + '\n\n'
        + '按 workflow.md 流程执行。'
    )


def _load_json(path):
    """Load JSON file, returning empty dict on missing/invalid."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _load_loop_state(cwd):
    """Load dloop-state.json if it exists. Returns dict or None."""
    path = os.path.join(cwd, DLOOP_STATE_PATH) if cwd else DLOOP_STATE_PATH
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not data.get("active"):
            return None
        return data
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _save_loop_state(cwd, state):
    """Atomically save dloop-state.json."""
    path = os.path.join(cwd, DLOOP_STATE_PATH) if cwd else DLOOP_STATE_PATH
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _cleanup_loop_state(cwd):
    """Remove dloop-state.json after loop ends."""
    path = os.path.join(cwd, DLOOP_STATE_PATH) if cwd else DLOOP_STATE_PATH
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _generate_phase_report(loop_state, stop_reason, tasks):
    """Generate a phase report from loop state data.

    Returns a formatted multi-line string suitable for stdout/stderr output.
    This report is auto-emitted when dloop completes (any stop condition).
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    completed_ids = loop_state.get("completed_task_ids", [])
    iteration = loop_state.get("current_iteration", 0)
    max_tasks = loop_state.get("max_tasks", 0)
    started_at = loop_state.get("started_at", "unknown")

    # Build task summary from dtask.json
    done_tasks = [t for t in tasks if t['status'] == 'Done' and t['id'] in set(completed_ids)]
    remaining = [t for t in tasks if t['status'] not in ('Done', 'Cancelled')]

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
        for t in done_tasks:
            report.append(f"  ✅ Task#{t['id']} {t['title']}")
    else:
        report.append("  （无）")
    report.append("")
    report.append("--- 剩余任务 ---")
    if remaining:
        for t in remaining:
            status_icon = {"InSpec": "📋", "InProgress": "🔄", "InReview": "👀"}.get(t['status'], "❓")
            report.append(f"  {status_icon} Task#{t['id']} {t['title']} [{t['status']}]")
    else:
        report.append("  （全部完成）")
    report.append("")
    report.append("=" * 50)

    return "\n".join(report)


def decide_default_mode(tasks, settings, data, task_json_path, additional_prompts):
    """Default mode: no active dloop. Only block for InProgress breakpoint recovery."""
    done_ids = {t['id'] for t in tasks if t['status'] == 'Done'}
    is_unblocked = lambda t: all(bid in done_ids for bid in t.get('blocked_by', []))

    ip = [t for t in tasks if t['status'] == 'InProgress']

    extra = ''
    for level, hint in additional_prompts:
        if level == 'block':
            extra += f'\n\n⚠ {hint}'
        elif level in ('warning', 'info'):
            extra += f'\n\nℹ {hint}'

    if ip:
        t = ip[0]
        base = format_task('继续完成当前任务（断点恢复）：', t) + extra
        return True, {'decision': 'block', 'reason': base}

    nx = [t for t in tasks if t['status'] == 'InSpec' and is_unblocked(t)]
    if nx:
        summary = (
            '当前无进行中任务，Session 结束。\n'
            f'可执行任务: Task#{nx[0]["id"]} {nx[0].get("title", "")} (InSpec)\n'
            f'输入 /drun 继续执行，或 /dloop 启动连续循环。'
        )
        print(summary, file=sys.stderr)

    return False, {}


def decide_loop_mode(tasks, settings, data, task_json_path, loop_state, cwd, additional_prompts):
    """Loop mode: dloop-state.json exists and active. Drive continuous execution."""
    max_tasks = loop_state.get("max_tasks", 0)
    iteration = loop_state.get("current_iteration", 0)

    extra = ''
    for level, hint in additional_prompts:
        if level == 'block':
            extra += f'\n\n⚠ {hint}'
        elif level in ('warning', 'info'):
            extra += f'\n\nℹ {hint}'

    ip = [t for t in tasks if t['status'] == 'InProgress']
    nx = [task for task in get_executable_tasks(tasks) if task.get('status') == 'InSpec']
    rev = [t for t in tasks if t['status'] == 'InReview']

    # --- InProgress: always block (breakpoint recovery takes priority) ---
    if ip:
        t = ip[0]
        base = format_task(f'🔄 dloop iteration {iteration + 1} | 继续当前任务（断点恢复）：', t) + extra
        return True, {'decision': 'block', 'reason': base}

    stop_reason = get_terminal_stop_reason(tasks, settings=settings, data=data, loop_state=loop_state)
    should_stop = stop_reason is not None

    if should_stop:
        # --- LOOP COMPLETE: generate phase report + cleanup ---
        notify(f'dloop 循环结束：{stop_reason}')

        # Finalize state
        loop_state["active"] = False
        loop_state["stopped_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        loop_state["stop_reason"] = stop_reason

        # Generate phase report
        report = _generate_phase_report(loop_state, stop_reason, tasks)

        # Cleanup state file
        _cleanup_loop_state(cwd)

        # Output report to stderr (visible to user)
        print(report, file=sys.stderr)

        return False, {}

    # --- Continue loop: increment iteration, pick next task ---
    next_iteration = iteration + 1
    loop_state["current_iteration"] = next_iteration
    _save_loop_state(cwd, loop_state)

    target = nx[0]

    base = format_task(
        f'🔄 dloop iteration {next_iteration}/{f"∞" if max_tasks == 0 else max_tasks} | 继续执行下一个任务：',
        target,
    ) + extra

    # Track review usage
    if rev:
        if 'review_used' not in data:
            data['review_used'] = 0
        data['review_used'] = data.get('review_used', 0) + 1
        try:
            with open(task_json_path, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    return True, {'decision': 'block', 'reason': base}


def decide(tasks, settings, data, task_json_path, cwd, additional_prompts, loop_state):
    """Route to default mode or loop mode based on dloop-state.json."""
    if loop_state is not None:
        return decide_loop_mode(tasks, settings, data, task_json_path, loop_state, cwd, additional_prompts)
    else:
        return decide_default_mode(tasks, settings, data, task_json_path, additional_prompts)


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

    stop_hook_active = stdin_data.get("stop_hook_active", False)
    if stop_hook_active:
        print(json.dumps({"continue": False}, ensure_ascii=False))
        sys.exit(0)

    cwd = stdin_data.get("cwd") or os.getcwd()

    data = _load_json(args.task_json)
    settings = _load_json(args.settings_json)
    tasks = data.get("tasks", [])

    loop_state = _load_loop_state(cwd)

    # Session isolation
    if loop_state is not None:
        hook_session = hook_session_id(stdin_data)
        state_session = loop_state.get("session_id", "")
        if state_session and hook_session and state_session != hook_session:
            loop_state = None

    additional_prompts = []
    try:
        import stop_archive
        archive_results = stop_archive.check(settings=settings, tasks=tasks)
        additional_prompts = archive_results
    except Exception:
        pass

    should_continue, output = decide(
        tasks, settings, data, args.task_json, cwd, additional_prompts, loop_state
    )
    if output:
        print(json.dumps(output, ensure_ascii=False))
    sys.exit(0 if should_continue else 1)
