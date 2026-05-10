#!/usr/bin/env python3
"""PreToolUse drift detection: edit_streak / pure_discussion / repetitive_loop / scope_drift.

Lightweight injection only — never blocks (exit code always 0).
Tolerance: high (only obvious drift triggers a prompt).
"""

import json, os, sys, re, time, tomllib

try:
    from _shared import load_json_fallback  # noqa: E402
except (ImportError, ModuleNotFoundError):
    def load_json_fallback(path):
        if not os.path.exists(path):
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

CTX_PREFIX = '/tmp/diwu_ctx_'
TASK_FILE = '.diwu/dtask.json'
SETTINGS_FILE = '.diwu/dsettings.toml'
EDIT_STREAK_LIMIT = 5
DISCUSSION_LIMIT = 8
LOOP_REPEAT = 3


def _get_sid():
    """Get sessionId from environment variable (set by hook runner)."""
    return os.environ.get("DIWU_SESSION_ID", "") or str(os.getpid())


def _cleanup_stale_tmp():
    """Remove expired /tmp/diwu_ctx_* files on startup."""
    import glob
    try:
        for fp in glob.glob(CTX_PREFIX + '*'):
            try:
                age = time.time() - os.path.getmtime(fp)
                if age > 3600:  # 1 hour stale threshold
                    os.remove(fp)
            except OSError:
                pass
    except OSError:
        pass


# Run cleanup once on module load
_cleanup_stale_tmp()


def _ctx_path():
    return CTX_PREFIX + _get_sid()


def _save(p, d):
    try:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
            f.write('\n')
    except OSError:
        pass


def _extract_fp(input_str):
    """Extract file path from tool input JSON."""
    try:
        inp = json.loads(input_str) if isinstance(input_str, str) else {}
        return inp.get('file_path', '') or inp.get('path', '')
    except (json.JSONDecodeError, TypeError):
        m = re.search(r'["\']?(/?[\w./-]+\.\w+)["\']?', input_str or '')
        return m.group(1) if m else ''


# --- detectors ---

def detect_edit_streak(ctx, tool_name):
    if tool_name in ('Edit', 'Write'):
        ctx['edit_count'] = ctx.get('edit_count', 0) + 1
    elif tool_name == 'Bash':
        ctx['edit_count'] = 0
    else:
        ctx['edit_count'] = max(0, ctx.get('edit_count', 0) - 1)

    if ctx['edit_count'] >= EDIT_STREAK_LIMIT:
        return ('[drift] 连续 %d 次编辑未验证，建议运行 lint/build/test 确认正确性。') % ctx['edit_count']
    return None


def detect_pure_discussion(ctx, tool_name):
    if tool_name in ('Edit', 'Write'):
        ctx['discuss_count'] = 0
    else:
        ctx['discuss_count'] = ctx.get('discuss_count', 0) + 1

    if ctx.get('discuss_count', 0) >= DISCUSSION_LIMIT:
        return '[drift] 连续多次非文件修改操作，如讨论已收敛请落地为具体改动或验证步骤。'
    return None


def detect_repetitive_loop(ctx, tool_name, input_str=''):
    sig = tool_name + ':' + (input_str[:80] if input_str else '')
    buf = ctx.get('loop_buf', [])
    buf.append(sig)
    buf = buf[-LOOP_REPEAT * 2:]
    ctx['loop_buf'] = buf

    if len(buf) >= LOOP_REPEAT * 2 and buf[-LOOP_REPEAT:] == buf[-LOOP_REPEAT * 2:-LOOP_REPEAT]:
        return '[drift] 检测到重复循环模式（连续 %d 次相同调用），请检查是否陷入死循环。' % LOOP_REPEAT
    return None


def detect_scope_drift(tool_name, input_str=''):
    if tool_name not in ('Edit', 'Write'):
        return None
    fp = _extract_fp(input_str)
    if not fp:
        return None
    task = load_json_fallback(TASK_FILE)
    it = [t for t in task.get('tasks', []) if t.get('status') == 'InProgress']
    if not it:
        return None
    allowed = it[0].get('files_modified', [])
    if not allowed:
        return None
    # high tolerance: same basename or same directory → OK
    for a in allowed:
        if os.path.basename(a) in fp or a in fp or fp in a:
            return None
        ad, fd = os.path.dirname(a), os.path.dirname(fp)
        if ad and fd and ad == fd:
            return None
    return ('[drift] 编辑文件 %s 不在 Task#%d 的 files_modified 范围内，确认是否必要越界。') % (fp, it[0]['id'])


def _load_settings():
    """Load drift detection settings from dsettings.toml."""
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "rb") as f:
            return tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def main():
    tool_name = os.environ.get('DIWU_TOOL_NAME', '')
    input_str = os.environ.get('DIWU_TOOL_INPUT', '')
    settings = _load_settings()
    if settings.get('drift_detection', {}).get('enabled') == False:
        sys.exit(0)

    ctx = load_json_fallback(_ctx_path())
    prompts = [r for r in [
        detect_edit_streak(ctx, tool_name),
        detect_pure_discussion(ctx, tool_name),
        detect_repetitive_loop(ctx, tool_name, input_str),
        detect_scope_drift(tool_name, input_str),
    ] if r]

    _save(_ctx_path(), ctx)
    if prompts:
        # Append skill pointer to drift warnings
        prompts.append('> 退化信号处理：/dcorr 或 Read .claude/rules/pitfalls.md（Layer 1 六类泛化模式）')
        print(json.dumps({'continue': True, 'additionalSystemPrompt': '\n'.join(prompts)}))
    sys.exit(0)


if __name__ == '__main__':
    main()
