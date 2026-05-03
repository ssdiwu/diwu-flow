"""L2 tests for plan-guard hard block + marker lifecycle."""

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
PLAN_EXIT_SCRIPT = PROJECT_ROOT / "hooks" / "scripts" / "plan_exit_hint.py"
TASK_GUARD_SCRIPT = PROJECT_ROOT / "hooks" / "scripts" / "task_entry_guard.py"
DTASK_TRANSITION_SCRIPT = PROJECT_ROOT / "scripts" / "dtask_transition.py"


def _run_script(script_path, payload, cwd):
    result = subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )
    return result


def _setup_dtask(tmp_path, status="InSpec", task_id=1):
    """创建含指定状态任务的 dtask.json。"""
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.json").write_text(
        json.dumps({"tasks": [{"id": task_id, "title": f"T{task_id}", "status": status}]}),
        encoding="utf-8",
    )


def _setup_dloop_state(tmp_path, active=True, session_id=""):
    """创建含 dloop 状态的 dtask-state.json。"""
    state_path = tmp_path / ".diwu" / "dtask-state.json"
    state_path.parent.mkdir(exist_ok=True)
    dloop = {"active": active, "session_id": session_id} if active else {"active": False}
    state_path.write_text(json.dumps({"dloop": dloop}), encoding="utf-8")


def test_plan_exit_hint_emits_additional_context(tmp_path):
    payload = {"hook_event_name": "PreToolUse", "tool_name": "ExitPlanMode", "cwd": str(tmp_path)}
    result = _run_script(PLAN_EXIT_SCRIPT, payload, tmp_path)

    assert result.returncode == 0
    output = json.loads(result.stdout)
    hook_output = output["hookSpecificOutput"]
    assert hook_output["hookEventName"] == "PreToolUse"
    assert "additionalContext" in hook_output
    assert "permissionDecision" not in hook_output
    assert "/dtask" in hook_output["additionalContext"]
    assert "已批准" not in hook_output["additionalContext"]
    assert "门控提醒" in hook_output["additionalContext"]


def test_task_entry_guard_soft_warns_without_dtask(tmp_path):
    """Non-doc files without active task: soft warning (exit 0) with stderr message."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "cwd": str(tmp_path),
        "tool_input": {"file_path": str(tmp_path / "src" / "feature.py")},
    }
    result = _run_script(TASK_GUARD_SCRIPT, payload, tmp_path)

    assert result.returncode == 0  # Soft warning, not hard block
    assert "diwu-task-guard" in result.stderr


def test_task_entry_guard_allows_md_without_dtask(tmp_path):
    """.md files are whitelisted regardless of dtask state."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "cwd": str(tmp_path),
        "tool_input": {"file_path": str(tmp_path / "README.md")},
    }
    result = _run_script(TASK_GUARD_SCRIPT, payload, tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


def test_task_entry_guard_allows_when_active_task_exists(tmp_path):
    diwu = tmp_path / ".diwu"
    diwu.mkdir()
    (diwu / "dtask.json").write_text(
        json.dumps({
            "tasks": [
                {"id": 1, "title": "x", "status": "InSpec"},
            ]
        }),
        encoding="utf-8",
    )
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "cwd": str(tmp_path),
        "tool_input": {"file_path": str(tmp_path / "src" / "feature.py")},
    }
    result = _run_script(TASK_GUARD_SCRIPT, payload, tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


def test_task_entry_guard_allows_workflow_file_write(tmp_path):
    diwu = tmp_path / ".diwu"
    recording = diwu / "recording"
    recording.mkdir(parents=True)
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "cwd": str(tmp_path),
        "tool_input": {"file_path": str(recording / "session-1.md")},
    }
    result = _run_script(TASK_GUARD_SCRIPT, payload, tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


def test_task_entry_guard_allows_runtime_state_write(tmp_path):
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "cwd": str(tmp_path),
        "tool_input": {"file_path": str(tmp_path / ".diwu" / "dtask-state.json")},
    }
    result = _run_script(TASK_GUARD_SCRIPT, payload, tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


# ── marker lifecycle tests ──────────────────────────────────────


def _run_guard(tmp_path, tool_name="Edit", file_path=None, event_overrides=None):
    payload = {
        "session_id": "test-session",
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "cwd": str(tmp_path),
        "tool_input": {"file_path": file_path or str(tmp_path / "src" / "main.py")},
    }
    if event_overrides:
        payload.update(event_overrides)
    result = subprocess.run(
        [sys.executable, str(TASK_GUARD_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    return result


def _run_plan_exit(tmp_path, plan_text, session_id="test-session", event_overrides=None):
    payload = {
        "session_id": session_id,
        "tool_name": "ExitPlanMode",
        "cwd": str(tmp_path),
        "tool_input": {"plan": plan_text},
    }
    if event_overrides:
        payload.update(event_overrides)
    result = subprocess.run(
        [sys.executable, str(PLAN_EXIT_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    return result


def test_exit_plan_mode_small_plan_no_marker(tmp_path):
    """ExitPlanMode + 小 plan（<20 行）-> 不创建 marker。"""
    result = _run_plan_exit(tmp_path, "\n".join(["# Plan line"] * 10))
    assert result.returncode == 0
    marker = tmp_path / ".claude" / ".plan-active"
    assert not marker.exists(), "小 plan 不应创建 marker"


def test_exit_plan_mode_big_plan_creates_marker_with_path(tmp_path):
    """ExitPlanMode + 大 plan（>=20 行）-> 创建 marker JSON。"""
    result = _run_plan_exit(tmp_path, "\n".join(["# Plan line"] * 25))
    assert result.returncode == 0
    marker = tmp_path / ".claude" / ".plan-active"
    assert marker.exists(), "大 plan 应创建 marker"
    content = json.loads(marker.read_text(encoding="utf-8"))
    assert content["version"] == 2
    assert content["source"] == "tool_input.plan"
    assert content["session_id"] == "test-session"
    assert content["line_count"] == 25


def test_marker_with_big_plan_triggers_hard_block(tmp_path):
    """ExitPlanMode 写入 marker 后，同 session 无活跃任务 → hard block (exit 2)。"""
    result = _run_plan_exit(tmp_path, "\n".join(["# Plan line"] * 25))
    assert result.returncode == 0
    # 无活跃任务的 dtask
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.json").write_text(json.dumps({"tasks": []}))

    result = _run_guard(tmp_path)
    assert result.returncode == 2, f"应 hard block (exit 2) 但 got {result.returncode}"
    assert "HARD BLOCK" in result.stderr


def test_stale_plan_no_block(tmp_path):
    """legacy path marker 指向不存在文件 → 不触发 hard block。"""
    marker = tmp_path / ".claude" / ".plan-active"
    marker.parent.mkdir(exist_ok=True)
    fake_plan = "/tmp/nonexistent-stale-plan.md"
    marker.write_text(fake_plan + "\n", encoding="utf-8")
    assert marker.exists()

    # 无活跃任务的 dtask
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.json").write_text(json.dumps({"tasks": []}))

    result = _run_guard(tmp_path)
    assert result.returncode == 0, f"stale plan 不应 hard block，got {result.returncode}"
    # marker 应被自动清理
    assert not marker.exists(), "stale marker 应被自动清理"


def test_stale_marker_empty_no_block(tmp_path):
    """marker 为空文件 → 不触发 hard block（旧格式兼容）。"""
    marker = tmp_path / ".claude" / ".plan-active"
    marker.parent.mkdir(exist_ok=True)
    marker.write_text("", encoding="utf-8")  # 空内容

    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.json").write_text(json.dumps({"tasks": []}))

    result = _run_guard(tmp_path)
    assert result.returncode == 0, f"空 marker 不应 hard block，got {result.returncode}"


def test_legacy_path_marker_with_big_plan_still_blocks(tmp_path):
    """legacy path marker 指向真实大 plan 时，仍应 hard block。"""
    plan_file = tmp_path / "legacy-plan.md"
    plan_file.write_text("\n".join(["# Plan line"] * 25), encoding="utf-8")

    marker = tmp_path / ".claude" / ".plan-active"
    marker.parent.mkdir(exist_ok=True)
    marker.write_text(str(plan_file) + "\n", encoding="utf-8")

    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.json").write_text(json.dumps({"tasks": []}))

    result = _run_guard(tmp_path)
    assert result.returncode == 2, f"legacy path marker 应继续 hard block，got {result.returncode}"
    assert "HARD BLOCK" in result.stderr


def test_marker_from_other_session_is_cleaned(tmp_path):
    """JSON marker 属于旧 session 时，应清理并放行。"""
    marker = tmp_path / ".claude" / ".plan-active"
    marker.parent.mkdir(exist_ok=True)
    marker.write_text(
        json.dumps({"version": 2, "source": "tool_input.plan", "session_id": "old-session", "line_count": 25}),
        encoding="utf-8",
    )

    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.json").write_text(json.dumps({"tasks": []}))

    result = _run_guard(tmp_path, event_overrides={"session_id": "new-session"})
    assert result.returncode == 0, f"旧 session marker 不应 hard block，got {result.returncode}"
    assert not marker.exists(), "跨 session 的 stale marker 应被自动清理"


def test_active_task_bypasses_hard_block(tmp_path):
    """有活跃任务时即使 marker 存在也不触发 hard block。"""
    result = _run_plan_exit(tmp_path, "\n".join(["# Plan line"] * 25))
    assert result.returncode == 0

    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.json").write_text(
        json.dumps({"tasks": [{"id": 1, "status": "InSpec", "title": "T"}]})
    )

    result = _run_guard(tmp_path)
    assert result.returncode == 0, "有活跃任务不应 hard block"


def test_mark_inspec_cleans_marker(tmp_path):
    """mark-inspec 成功后应清理 .plan-active marker。"""
    # 准备环境
    marker = tmp_path / ".claude" / ".plan-active"
    marker.parent.mkdir(exist_ok=True)
    marker.touch()
    assert marker.exists()

    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.json").write_text(
        json.dumps({"tasks": [{"id": 1, "title": "T", "status": "InDraft"}]})
    )

    # 执行 mark-inspec
    result = subprocess.run(
        [sys.executable, str(DTASK_TRANSITION_SCRIPT),
         "mark-inspec", "--task-ids", "1", "--cwd", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert not marker.exists(), "marker 应被 mark-inspec 清理"


# ── Dloop guard 分支测试（PreToolUse exit 语义）──


class TestDloopGuard:
    """task_entry_guard.py dloop fail-fast guard 的 6 分支判定矩阵。

    PreToolUse 退出码语义：exit(0)=允许 / exit(1)=非阻塞错误 / exit(2)=拒绝工具调用。
    """

    def test_1_inactive_allows(self, tmp_path):
        """dloop inactive → 放行 exit(0)。"""
        _setup_dtask(tmp_path)
        result = _run_guard(tmp_path)
        assert result.returncode == 0

    def test_2_dummy_sid_with_owner_allows(self, tmp_path):
        """dloop active + dummy SID + owner event SID → 首轮未绑定，放行。"""
        _setup_dtask(tmp_path)
        _setup_dloop_state(tmp_path, session_id="dloop-20260501-123456")
        result = _run_guard(tmp_path, event_overrides={"session_id": "real-owner-sid"})
        assert result.returncode == 0

    def test_3_dummy_sid_with_foreign_also_allows(self, tmp_path):
        """[KNOWN TRADEOFF] dloop active + dummy SID + foreign event SID → 放行。

        dummy 窗口内无法验证所有权（SID 尚未由 Stop 事件绑定），当前设计选择放行。
        此窗口通常极短（/dloop start → 首 Stop），且改 dloop.py start 即可消除。
        本测试锁定此行为，防止未来无意识变更将其改为 block（会误拦 owner）。
        """
        _setup_dtask(tmp_path)
        _setup_dloop_state(tmp_path, session_id="dloop-20260501-123456")
        result = _run_guard(tmp_path, event_overrides={"session_id": "foreign-sid"})
        assert result.returncode == 0  # 显式断言 tradeoff 行为

    def test_4_real_sid_owner_match_allows(self, tmp_path):
        """dloop active + real SID 匹配 → owner 执行任务，放行。"""
        _setup_dtask(tmp_path)
        _setup_dloop_state(tmp_path, session_id="loop-owner-sid")
        result = _run_guard(tmp_path, event_overrides={"session_id": "loop-owner-sid"})
        assert result.returncode == 0

    def test_5_real_sid_non_owner_blocks(self, tmp_path):
        """dloop active + real SID 不匹配 → non-owner，硬阻止 exit(2)。"""
        _setup_dtask(tmp_path)
        _setup_dloop_state(tmp_path, session_id="loop-owner-sid")
        result = _run_guard(tmp_path, event_overrides={"session_id": "other-session"})
        assert result.returncode == 2
        assert "diwu-dloop-guard" in result.stderr

    def test_6_real_sid_no_event_sid_blocks(self, tmp_path):
        """dloop active + 无 event session_id → 未知调用者，硬阻止 exit(2)。

        直接构造不含 session_id/sessionId 字段的完整 payload，
        因为 event_overrides={} 无法删除已有字段。
        """
        _setup_dtask(tmp_path)
        _setup_dloop_state(tmp_path, session_id="loop-owner-sid")
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "cwd": str(tmp_path),
            "tool_input": {"file_path": str(tmp_path / "src" / "main.py")},
            # 故意不传 session_id / sessionId
        }
        result = subprocess.run(
            [sys.executable, str(TASK_GUARD_SCRIPT)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 2
        assert "diwu-dloop-guard" in result.stderr
