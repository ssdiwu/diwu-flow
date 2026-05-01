"""L2 tests for plan-guard hard block + marker lifecycle."""

import json
import os
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


def _run_guard(tmp_path, tool_name="Edit", file_path=None):
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "cwd": str(tmp_path),
        "tool_input": {"file_path": file_path or str(tmp_path / "src" / "main.py")},
    }
    result = subprocess.run(
        [sys.executable, str(TASK_GUARD_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    return result


def _run_plan_exit(tmp_path):
    payload = {"tool_name": "ExitPlanMode", "cwd": str(tmp_path)}
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
    plan_dir = Path.home() / ".claude" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "test-small-plan.md"
    plan_file.write_text("\n".join(["# Plan line"] * 10), encoding="utf-8")

    payload = {
        "tool_name": "ExitPlanMode",
        "cwd": str(tmp_path),
        "tool_input": {"file_path": str(plan_file)},
    }
    result = subprocess.run(
        [sys.executable, str(PLAN_EXIT_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0
    marker = tmp_path / ".claude" / ".plan-active"
    assert not marker.exists(), "小 plan 不应创建 marker"

    # 清理
    plan_file.unlink()


def test_exit_plan_mode_big_plan_creates_marker_with_path(tmp_path):
    """ExitPlanMode + 大 plan（>=20 行）-> 创建 marker 且内容为路径。"""
    plan_dir = Path.home() / ".claude" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "test-big-plan.md"
    plan_file.write_text("\n".join(["# Plan line"] * 25), encoding="utf-8")

    payload = {
        "tool_name": "ExitPlanMode",
        "cwd": str(tmp_path),
        "tool_input": {"file_path": str(plan_file)},
    }
    result = subprocess.run(
        [sys.executable, str(PLAN_EXIT_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0
    marker = tmp_path / ".claude" / ".plan-active"
    assert marker.exists(), "大 plan 应创建 marker"
    content = marker.read_text().strip()
    assert content == str(plan_file), f"marker 内容应为 plan 路径，实际: {content}"

    # 清理
    plan_file.unlink()


def test_marker_with_big_plan_triggers_hard_block(tmp_path):
    """marker(含有效 plan 路径) + 大 plan 文件 + 无活跃任务 → hard block (exit 2)。"""
    # 创建大 plan 文件
    plan_dir = Path.home() / ".claude" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "test-big-plan.md"
    plan_file.write_text("\n".join(["# Plan line"] * 25), encoding="utf-8")

    # 创建 marker，写入 plan 路径
    marker = tmp_path / ".claude" / ".plan-active"
    marker.parent.mkdir(exist_ok=True)
    marker.write_text(str(plan_file) + "\n", encoding="utf-8")

    # 无活跃任务的 dtask
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    (diwu / "dtask.json").write_text(json.dumps({"tasks": []}))

    result = _run_guard(tmp_path)
    assert result.returncode == 2, f"应 hard block (exit 2) 但 got {result.returncode}"
    assert "HARD BLOCK" in result.stderr

    # 清理
    plan_file.unlink()


def test_stale_plan_no_block(tmp_path):
    """marker 记录的 plan 文件已不存在 → 不触发 hard block。"""
    # 创建 marker 指向一个不存在的 plan
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


def test_active_task_bypasses_hard_block(tmp_path):
    """有活跃任务时即使 marker 存在也不触发 hard block。"""
    # 创建一个真实存在的 plan 文件供 marker 引用
    plan_dir = Path.home() / ".claude" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "test-bypass-plan.md"
    plan_file.write_text("\n".join(["# Plan line"] * 25), encoding="utf-8")

    marker = tmp_path / ".claude" / ".plan-active"
    marker.parent.mkdir(exist_ok=True)
    marker.write_text(str(plan_file) + "\n", encoding="utf-8")

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
