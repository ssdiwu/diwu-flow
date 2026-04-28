"""Stop hook: continuous_mode decision tree + OS notification + task formatter.

Contains the core decision logic for what happens when a Stop event fires:
- InProgress tasks → continue (with snapshot)
- InReview tasks → review buffer management
- InSpec tasks available → auto-advance or stop
- No active tasks → completion summary
"""
import json
import os
import platform
import subprocess
import sys


def notify(msg):
    """Send OS notification (macOS/Linux)."""
    if platform.system() == 'Darwin':
        os.system(
            f'osascript -e \'display notification "{msg}" '
            f'with title "diwu-workflow" sound name "Glass"\' 2>/dev/null'
        )
    else:
        os.system(f'notify-send "diwu-workflow" "{msg}" 2>/dev/null')
    if os.path.exists('/dev/tty'):
        open('/dev/tty', 'w').write('\a')


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


def decide(tasks, settings, data, task_json_path, additional_prompts):
    """Run continuous_mode decision tree.

    Args:
        tasks: full task list
        settings: dsettings dict
        data: raw task.json dict (for saving review_used)
        task_json_path: path to task.json
        additional_prompts: list of (level, hint) from integrity/archive checks

    Returns:
        (should_continue: bool, output_dict) for json print + sys.exit
    """
    # Anti-loop: if stop_hook_active is already set, skip injection
    if data.get('stop_hook_active'):
        return True, {}

    continuous_mode = settings.get('continuous_mode', True)
    done_ids = {t['id'] for t in tasks if t['status'] == 'Done'}
    is_unblocked = lambda t: all(bid in done_ids for bid in t.get('blocked_by', []))

    ip = [t for t in tasks if t['status'] == 'InProgress']
    rev = [t for t in tasks if t['status'] == 'InReview']
    nx = [t for t in tasks if t['status'] == 'InSpec' and is_unblocked(t)]

    # Merge additional prompts from integrity/archive checks
    extra = ''
    for level, hint in additional_prompts:
        if level == 'block':
            extra += f'\n\n⚠ {hint}'
        elif level in ('warning', 'info'):
            extra += f'\n\nℹ {hint}'

    # --- InProgress: snapshot + continue ---
    if ip:
        t = ip[0]
        base = format_task('继续完成当前任务：', t) + extra
        return True, {'decision': 'block', 'reason': base}

    # --- InReview: review buffer ---
    if rev:
        rlim = settings.get('review_limit', data.get('review_limit', 5))
        rused = data.get('review_used', 0)
        if rused >= rlim:
            notify(f'InReview 任务已达 {len(rev)} 个，请人工验收后继续')
            return False, {'continue': False}
        if nx:
            if not continuous_mode:
                done_tasks = [t for t in tasks if t['status'] == 'Done']
                remaining = [t for t in tasks if t['status'] not in ('Done', 'Cancelled')]
                summary = (
                    'CONTINUOUS_MODE_COMPLETE - continuous_mode 已关闭\n'
                    f'已完成: {len(done_tasks)} 个任务\n'
                    f'下一任务: Task#{nx[0]["id"]} {nx[0].get("title", "")} (InSpec)\n'
                    f'剩余: ' + ', '.join(
                        f'#{t["id"]}({t["status"]})' for t in remaining
                    )
                )
                return True, {'decision': 'block', 'reason': summary}

            data['review_used'] = rused + 1
            open(task_json_path, 'w').write(json.dumps(data, indent=2, ensure_ascii=False))

            base = format_task(
                f'继续执行下一个任务 (review buffer {rused + 1}/{rlim}):', nx[0]
            ) + extra
            return True, {'decision': 'block', 'reason': base}

    # --- No InProgress/InReview: final state ---
    if 'review_used' in data and data['review_used'] > 0:
        data['review_used'] = 0
        open(task_json_path, 'w').write(json.dumps(data, indent=2, ensure_ascii=False))

    if nx:
        if not continuous_mode:
            done_tasks = [t for t in tasks if t['status'] == 'Done']
            remaining = [t for t in tasks if t['status'] not in ('Done', 'Cancelled')]
            summary = (
                'CONTINUOUS_MODE_COMPLETE - continuous_mode 已关闭\n'
                f'已完成: {len(done_tasks)} 个任务\n'
                f'下一任务: Task#{nx[0]["id"]} {nx[0].get("title", "")} (InSpec)\n'
                f'剩余: ' + ', '.join(
                    f'#{t["id"]}({t["status"]})' for t in remaining
                )
            )
            return True, {'decision': 'block', 'reason': summary}

        base = format_task('继续执行下一个任务：', nx[0]) + extra
        return True, {'decision': 'block', 'reason': base}

    # Truly nothing to do
    return False, {}
