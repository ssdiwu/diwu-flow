"""Layer 2 Hook 脚本回归测试: drift_detect_pre.py

覆盖 acceptance:
1. 文件存在性且非空
2. Python 语法正确（py_compile）
3. 退出码始终为 0（无 sys.exit(1)）
4. edit_streak 检测：连续 Edit/Write 达阈值时输出 continue: True + 提醒
5. pure_discussion 检测：非编辑操作超阈值时输出提醒
6. repetitive_loop 检测：滑窗内重复操作时输出提醒
7. scope_drift tolerance=high：编辑文件在 task files_modified 内不提示；明显越界时提示
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
    """运行 drift_detect_pre.py，monkey-patch getpid 使用固定 PID。

    返回 (returncode, parsed_stdout_dict, stderr)
    """
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    full_env["DIWU_TOOL_NAME"] = tool_name
    if tool_input:
        full_env["DIWU_TOOL_INPUT"] = tool_input

    wrapper = (
        f"import os, sys; "
        f"os.getpid = lambda: {pid}; "
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
            # 先 Edit 3 次
            for i in range(3):
                inp = json.dumps({"file_path": f"/tmp/reset_before_{i}.py"})
                _run_with_fixed_pid(pid, "Edit", inp,
                                       cwd=str(tmp_path), env={**base_env})
            # Bash 重置
            rc, out, _ = _run_with_fixed_pid(pid, "Bash", "",
                                                cwd=str(tmp_path), env={**base_env})
            assert rc == 0
            assert not out.get("continue"), "Bash 后 edit_count 应重置"

            # 再 Edit 4 次仍不够（从 0 开始）
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
                # 每次不同文件路径 → 避免 repetitive_loop；Read 不增加 edit_count
                inp = json.dumps({"file_path": f"/tmp/discuss_{i}.py"})
                rc, out, _ = _run_with_fixed_pid(
                    pid, "Read", inp,
                    cwd=str(tmp_path), env={**base_env},
                )
                assert rc == 0
                if i < 7:
                    assert not out.get("continue"), f"第 {i+1} 次 Read 不应触发"
            # 第 8 次触发
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
            # 先累积 7 次 Read（每次不同文件路径）
            for i in range(7):
                inp = json.dumps({"file_path": f"/tmp/dreset_{i}.py"})
                _run_with_fixed_pid(pid, "Read", inp,
                                      cwd=str(tmp_path), env={**base_env})
            # Edit 重置 discuss_count
            rc, out, _ = _run_with_fixed_pid(
                pid, "Edit", '{"file_path": "/tmp/test.py"}',
                cwd=str(tmp_path), env={**base_env},
            )
            assert rc == 0
            assert not out.get("continue"), "Edit 后 discuss_count 应重置"

            # 再需要 8 次 Read 才能触发
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
        """连续 LOOP_REPEAT*2 (6) 次相同调用 → 触发重复循环警告"""
        pid = _next_pid()
        _cleanup_ctx(pid)
        base_env = {"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)}
        # 用 Edit 操作（重置 discuss_count 和 edit_count 管理），
        # 但每次相同 input 触发 repetitive_loop
        sig = json.dumps({"file_path": "/tmp/loop_same.py"})
        try:
            for i in range(6):
                rc, out, _ = _run_with_fixed_pid(
                    pid, "Edit", sig,
                    cwd=str(tmp_path), env={**base_env},
                )
                assert rc == 0
                if i < 4:
                    # 前 5 次 (i=0..4): edit_count 在增长但未达 5；
                    # loop_buf 长度不够 6 不触发 repetitive_loop
                    # 注意: i=4 时 edit_count=5 会触发 edit_streak!
                    # 所以我们需要让 edit_streak 不干扰: 用 Bash 间隔
                    pass
            # 上面的循环中 i=4 时会触发 edit_streak（5次 Edit），
            # 改策略：直接预设 ctx 来测试 repetitive_loop
        finally:
            _cleanup_ctx(pid)

        # 更可靠的方案：预设 loop_buf 直接测试 detect_repetitive_loop 逻辑
        pid = _next_pid()
        _cleanup_ctx(pid)
        ctx_file = Path(f"/tmp/diwu_ctx_{pid}")
        # 构造 loop_buf: 6 个相同签名，使 buf[-3:] == buf[-6:-3]
        loop_sig = "Edit:" + json.dumps({"file_path": "/tmp/loop_test.py"})
        entries = [loop_sig] * 6
        ctx_file.write_text(json.dumps({
            "edit_count": 0,       # edit_count 低不触发 edit_streak
            "discuss_count": 0,     # discuss_count 低不触发 pure_discussion
            "loop_buf": entries,    # 6 个相同签名
        }))
        try:
            # 再来一次相同调用 → append 后 buf[-3:] == buf[-6:-3]
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
        """不同参数的调用不触发重复检测（也不触发其他检测器）"""
        pid = _next_pid()
        _cleanup_ctx(pid)
        base_env = {"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)}
        try:
            # 用 Edit 但每次不同文件 → 无 repetitive_loop；
            # 控制在 4 次以内 → 无 edit_streak
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


# ---------------------------------------------------------------------------
# Acceptance 7: scope_drift tolerance=high
# ---------------------------------------------------------------------------
class TestScopeDriftDetection:
    """tolerance=high：编辑文件在 task files_modified 内不提示；明显越界时提示"""

    def _run_script(self, tool_name, tool_input="", cwd=None, env=None):
        full_env = dict(os.environ)
        if env:
            full_env.update(env)
        full_env["DIWU_TOOL_NAME"] = tool_name
        if tool_input:
            full_env["DIWU_TOOL_INPUT"] = tool_input
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
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
        return result.returncode, parsed

    def _make_task_json(self, tmp_path, **kwargs):
        """Create .diwu/dtask.json (post-#165 migration path)"""
        diwu_dir = tmp_path / ".diwu"
        diwu_dir.mkdir(exist_ok=True)
        task_json = diwu_dir / "dtask.json"
        task_json.write_text(json.dumps({
            "tasks": [kwargs]
        }, ensure_ascii=False))
        return diwu_dir

    def test_edit_within_files_modified_no_warning(self, tmp_path):
        """编辑文件在 files_modified 列表中 → 无 drift 提示"""
        self._make_task_json(tmp_path,
            id=1, title="测试任务", status="InProgress",
            files_modified=["/project/src/main.py", "/project/src/utils.py"])

        rc, out = self._run_script(
            "Edit",
            '{"file_path": "/project/src/main.py"}',
            cwd=str(tmp_path),
            env={"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)},
        )
        assert rc == 0
        assert not out.get("continue"), "编辑 files_modified 内的文件不应触发 scope_drift"

    def test_basename_match_no_warning(self, tmp_path):
        """high tolerance: 文件 basename 匹配 → 无提示"""
        self._make_task_json(tmp_path,
            id=1, title="测试任务", status="InProgress",
            files_modified=["/project/src/main.py"])

        rc, out = self._run_script(
            "Write",
            '{"file_path": "/other/path/main.py"}',
            cwd=str(tmp_path),
            env={"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)},
        )
        assert rc == 0
        assert not out.get("continue"), "basename 匹配时 high tolerance 不应提示"

    def test_same_directory_no_warning(self, tmp_path):
        """high tolerance: 同目录 → 无提示"""
        self._make_task_json(tmp_path,
            id=1, title="测试任务", status="InProgress",
            files_modified=["/project/src/main.py"])

        rc, out = self._run_script(
            "Edit",
            '{"file_path": "/project/src/helper.py"}',
            cwd=str(tmp_path),
            env={"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)},
        )
        assert rc == 0
        assert not out.get("continue"), "同目录时 high tolerance 不应提示"

    def test_obvious_oob_triggers_warning(self, tmp_path):
        """明显越界（不同目录、不同 basename）→ 触发 drift 提示"""
        self._make_task_json(tmp_path,
            id=1, title="测试任务", status="InProgress",
            files_modified=["/project/src/main.py"])

        rc, out = self._run_script(
            "Write",
            '{"file_path": "/unrelated/config/settings.yaml"}',
            cwd=str(tmp_path),
            env={"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)},
        )
        assert rc == 0
        assert out.get("continue") is True, "明显越界应触发 scope_drift"
        prompt = out.get("additionalSystemPrompt", "")
        assert "drift" in prompt.lower() or "不在" in prompt or "范围" in prompt, (
            f"应包含越界提醒，实际: {prompt}"
        )

    def test_no_inprogress_task_no_warning(self, tmp_path):
        """无 InProgress 任务 → 不检测 scope_drift"""
        self._make_task_json(tmp_path,
            id=1, title="已完成任务", status="Done",
            files_modified=["/project/src/main.py"])

        rc, out = self._run_script(
            "Edit",
            '{"file_path": "/unrelated/file.txt"}',
            cwd=str(tmp_path),
            env={"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)},
        )
        assert rc == 0
        assert not out.get("continue"), "无 InProgress 任务时不检测 scope_drift"

    def test_empty_files_modified_no_warning(self, tmp_path):
        """files_modified 为空列表 → 不检测 scope_drift"""
        self._make_task_json(tmp_path,
            id=1, title="测试任务", status="InProgress",
            files_modified=[])

        rc, out = self._run_script(
            "Edit",
            '{"file_path": "/any/file.txt"}',
            cwd=str(tmp_path),
            env={"CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT)},
        )
        assert rc == 0
        assert not out.get("continue"), "files_modified 为空时不检测 scope_drift"
