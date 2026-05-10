"""Layer 2 Hook 脚本回归测试: drift_detect_pre.py

覆盖 acceptance:
1. 文件存在性且非空
2. Python 语法正确（py_compile）
3. 退出码始终为 0（无 sys.exit(1)）
4. edit_streak 检测：连续 Edit/Write 达阈值时输出 continue: True + 提醒
5. pure_discussion 检测：非编辑操作超阈值时输出提醒
6. repetitive_loop 检测：滑窗内重复操作时输出提醒
"""
import json, os, py_compile, re, subprocess, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
SCRIPT = PROJECT_ROOT / "hooks" / "scripts" / "drift_detect_pre.py"

# 全局 PID 计数器，确保每个测试用例使用独立 ctx 文件
_PID_COUNTER = 99900


def _next_pid():
    global _PID_COUNTER
    _PID_COUNTER += 1
    return str(_PID_COUNTER)


def _run_with_fixed_pid(pid, tool_name, tool_input="", cwd=None, env=None):
    """运行 drift_detect_pre.py，使用 DIWU_SESSION_ID 隔离 ctx 文件。

    返回 (returncode, parsed_stdout_dict, stderr)
    """
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    full_env["DIWU_TOOL_NAME"] = tool_name
    full_env["DIWU_SESSION_ID"] = str(pid)
    if tool_input:
        full_env["DIWU_TOOL_INPUT"] = tool_input

    wrapper = (
        f"import os, sys; "
        f"exec(open(r'{SCRIPT}').read())"
    )
    result = subprocess.run(
        [sys.executable, "-c", wrapper],
        capture_output=True,
        text=True,
        cwd=cwd or str(PROJECT_ROOT),
        env=full_env,
    )
    stdout_data = result.stdout.strip()
    parsed = {}
    if stdout_data:
        try:
            parsed = json.loads(stdout_data)
        except json.JSONDecodeError:
            pass
    return result.returncode, parsed, result.stderr


def _cleanup_ctx(pid):
    """清理指定 PID 的 ctx 文件"""
    ctx_file = Path(f"/tmp/diwu_ctx_{pid}")
    ctx_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Acceptance 1: 文件存在性且非空
# ---------------------------------------------------------------------------
def test_file_exists_and_nonempty():
    """drift_detect_pre.py 存在且非空"""
    assert SCRIPT.exists(), f"脚本不存在: {SCRIPT}"
    content = SCRIPT.read_text()
    assert len(content.strip()) > 0, "脚本文件为空"


# ---------------------------------------------------------------------------
# Acceptance 2: Python 语法正确（py_compile）
# ---------------------------------------------------------------------------
def test_python_syntax_valid():
    """py_compile 编译通过，无语法错误"""
    py_compile.compile(str(SCRIPT), doraise=True)


# ---------------------------------------------------------------------------
# Acceptance 3: 退出码始终为 0（扫描源码确认无 sys.exit(1)）
# ---------------------------------------------------------------------------
def test_exit_code_always_zero():
    """源码中不存在 sys.exit(1) 或 sys.exit(非零)，所有路径都是 exit(0) 或正常返回"""
    source = SCRIPT.read_text()
    exit_calls = re.findall(r'sys\.exit\(([^)]*)\)', source)
    for arg in exit_calls:
        arg_stripped = arg.strip()
        assert arg_stripped in ('0', '',), (
            f"发现非零退出码: sys.exit({arg}) —— 脚本应始终 exit 0"
        )


# ---------------------------------------------------------------------------
# Acceptance 4: edit_streak 检测
# ---------------------------------------------------------------------------
class TestEditStreakDetection:
    """连续 Edit/Write 达 EDIT_STREAK_LIMIT (5) 时输出 continue: True + 提醒"""

    def test_below_threshold_no_output(self, tmp_path):
        """连续 4 次 Edit 未达阈值 → 无输出（每次不同文件避免 repetitive_loop）"""
        pid = _next_pid()
        _cleanup_ctx(pid)
        base_env = {"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)}
        try:
            for i in range(4):
                inp = json.dumps({"file_path": f"/tmp/below_{i}.py"})
                rc, out, _ = _run_with_fixed_pid(
                    pid, "Edit", inp,
                    cwd=str(tmp_path), env={**base_env},
                )
                assert rc == 0, f"第 {i+1} 次 Edit 应 exit 0"
            assert not out.get("continue"), "未达阈值时不应输出 continue: True"
        finally:
            _cleanup_ctx(pid)

    def test_at_threshold_outputs_continue(self, tmp_path):
        """连续 5 次 Edit 达阈值 → 输出 continue: True 且含 drift 提醒"""
        pid = _next_pid()
        _cleanup_ctx(pid)
        base_env = {"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)}
        try:
            for i in range(5):
                inp = json.dumps({"file_path": f"/tmp/at_{i}.py"})
                rc, out, _ = _run_with_fixed_pid(
                    pid, "Edit", inp,
                    cwd=str(tmp_path), env={**base_env},
                )
                assert rc == 0, f"第 {i+1} 次 Edit 应 exit 0"
            assert out.get("continue") is True, "达阈值时应输出 continue: True"
            prompt = out.get("additionalSystemPrompt", "")
            assert "drift" in prompt.lower() or "编辑" in prompt, (
                f"应包含 drift/编辑提醒，实际: {prompt}"
            )
        finally:
            _cleanup_ctx(pid)

    def test_bash_resets_edit_count(self, tmp_path):
        """Bash 操作重置 edit_count → 需要重新累积到 5 才触发"""
        pid = _next_pid()
        _cleanup_ctx(pid)
        base_env = {"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)}
        try:
            for i in range(3):
                inp = json.dumps({"file_path": f"/tmp/reset_before_{i}.py"})
                _run_with_fixed_pid(pid, "Edit", inp,
                                       cwd=str(tmp_path), env={**base_env})
            rc, out, _ = _run_with_fixed_pid(pid, "Bash", "",
                                                cwd=str(tmp_path), env={**base_env})
            assert rc == 0
            assert not out.get("continue"), "Bash 后 edit_count 应重置"

            for i in range(4):
                inp = json.dumps({"file_path": f"/tmp/reset_after_{i}.py"})
                rc, out, _ = _run_with_fixed_pid(pid, "Edit", inp,
                                                   cwd=str(tmp_path), env={**base_env})
                assert not out.get("continue"), f"Bash 后第 {i+1} 次 Edit 不应触发"
        finally:
            _cleanup_ctx(pid)


# ---------------------------------------------------------------------------
# Acceptance 5: pure_discussion 检测
# ---------------------------------------------------------------------------
class TestPureDiscussionDetection:
    """非编辑操作超 DISCUSSION_LIMIT (8) 时输出提醒"""

    def test_non_edit_ops_accumulate(self, tmp_path):
        """连续 Read 操作累积 discuss_count → 第 8 次触发"""
        pid = _next_pid()
        _cleanup_ctx(pid)
        base_env = {"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)}
        try:
            for i in range(8):
                inp = json.dumps({"file_path": f"/tmp/discuss_{i}.py"})
                rc, out, _ = _run_with_fixed_pid(
                    pid, "Read", inp,
                    cwd=str(tmp_path), env={**base_env},
                )
                assert rc == 0
                if i < 7:
                    assert not out.get("continue"), f"第 {i+1} 次 Read 不应触发"
            assert out.get("continue") is True, "8 次 Read 后应触发 pure_discussion"
            prompt = out.get("additionalSystemPrompt", "")
            assert "drift" in prompt.lower() or "讨论" in prompt or "操作" in prompt, (
                f"应包含讨论/操作提醒，实际: {prompt}"
            )
        finally:
            _cleanup_ctx(pid)

    def test_edit_resets_discuss_count(self, tmp_path):
        """Edit/Write 操作重置 discuss_count"""
        pid = _next_pid()
        _cleanup_ctx(pid)
        base_env = {"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)}
        try:
            for i in range(7):
                inp = json.dumps({"file_path": f"/tmp/dreset_{i}.py"})
                _run_with_fixed_pid(pid, "Read", inp,
                                      cwd=str(tmp_path), env={**base_env})
            rc, out, _ = _run_with_fixed_pid(
                pid, "Edit", '{"file_path": "/tmp/test.py"}',
                cwd=str(tmp_path), env={**base_env},
            )
            assert rc == 0
            assert not out.get("continue"), "Edit 后 discuss_count 应重置"

            for i in range(8):
                inp = json.dumps({"file_path": f"/tmp/dafter_{i}.py"})
                rc, out, _ = _run_with_fixed_pid(
                    pid, "Read", inp,
                    cwd=str(tmp_path), env={**base_env},
                )
                if i < 7:
                    assert not out.get("continue"), f"Edit 后第 {i+1} 次 Read 不应触发"
            assert out.get("continue") is True
        finally:
            _cleanup_ctx(pid)


# ---------------------------------------------------------------------------
# Acceptance 6: repetitive_loop 检测
# ---------------------------------------------------------------------------
class TestRepetitiveLoopDetection:
    """滑窗内重复操作时输出提醒"""

    def test_repetitive_calls_trigger_warning(self, tmp_path):
        """预设 loop_buf 构造触发条件"""
        pid = _next_pid()
        _cleanup_ctx(pid)
        base_env = {"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)}
        ctx_file = Path(f"/tmp/diwu_ctx_{pid}")
        loop_sig = "Edit:" + json.dumps({"file_path": "/tmp/loop_test.py"})
        entries = [loop_sig] * 6
        ctx_file.write_text(json.dumps({
            "edit_count": 0,
            "discuss_count": 0,
            "loop_buf": entries,
        }))
        try:
            rc, out, _ = _run_with_fixed_pid(
                pid, "Edit", json.dumps({"file_path": "/tmp/loop_test.py"}),
                cwd=str(tmp_path), env={**base_env},
            )
            assert rc == 0
            assert out.get("continue") is True, "重复循环模式应触发"
            prompt = out.get("additionalSystemPrompt", "")
            assert "重复" in prompt or "循环" in prompt or "loop" in prompt.lower(), (
                f"应包含重复/循环提醒，实际: {prompt}"
            )
        finally:
            _cleanup_ctx(pid)

    def test_different_calls_no_trigger(self, tmp_path):
        """不同参数的调用不触发重复检测"""
        pid = _next_pid()
        _cleanup_ctx(pid)
        base_env = {"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)}
        try:
            for i in range(4):
                inp = json.dumps({"file_path": f"/tmp/diff_{i}.py"})
                rc, out, _ = _run_with_fixed_pid(
                    pid, "Edit", inp,
                    cwd=str(tmp_path), env={**base_env},
                )
                assert rc == 0
                assert not out.get("continue"), f"不同参数的第 {i+1} 次调用不应触发"
        finally:
            _cleanup_ctx(pid)
