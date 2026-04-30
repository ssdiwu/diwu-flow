"""L2 tests for task_created_validate.py — cycle detection."""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
VALIDATE_SCRIPT = PROJECT_ROOT / "hooks" / "scripts" / "task_created_validate.py"


def _task(**overrides):
    """Build a minimal valid task dict, overriding with kwargs."""
    base = {
        "id": 0, "title": "T", "description": "desc",
        "acceptance": ["Given x When y Then z"],
        "steps": ["step1"], "category": "functional", "status": "InDraft",
        "blocked_by": [],
    }
    base.update(overrides)
    return base


def _run_validate(tmp_path, task_dict, full_tasks=None):
    diwu = tmp_path / ".diwu"
    diwu.mkdir(exist_ok=True)
    if full_tasks is None:
        full_tasks = [task_dict]
    (diwu / "dtask.json").write_text(
        json.dumps({"tasks": full_tasks}, ensure_ascii=False, indent=2)
    )
    payload = {"task": task_dict}
    result = subprocess.run(
        [sys.executable, str(VALIDATE_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    return result


def test_fan_out_dag_no_crash(tmp_path):
    """扇出 DAG（1->[2,3,4]）不应崩溃且应检测为无循环。"""
    task = _task(id=1, title="T1", blocked_by=[2, 3, 4])
    full_tasks = [
        task,
        _task(id=2, title="T2"),
        _task(id=3, title="T3"),
        _task(id=4, title="T4"),
    ]
    result = _run_validate(tmp_path, task, full_tasks)
    assert result.returncode == 0, f"应 exit 0 但 got {result.returncode}, stderr={result.stderr}"


def test_linear_chain_ok(tmp_path):
    """单链 A->B->C 应无循环。"""
    full_tasks = [
        _task(id=10, title="T10", blocked_by=[11]),
        _task(id=11, title="T11", blocked_by=[12]),
        _task(id=12, title="T12"),
    ]
    result = _run_validate(tmp_path, full_tasks[0], full_tasks)
    assert result.returncode == 0, f"单链不应报循环, got {result.returncode}"


def test_real_cycle_detected(tmp_path):
    """真实循环 A->B->C->A 应被检测。"""
    full_tasks = [
        _task(id=101, title="A", blocked_by=[102]),
        _task(id=102, title="B", blocked_by=[103]),
        _task(id=103, title="C", blocked_by=[101]),
    ]
    result = _run_validate(tmp_path, full_tasks[0], full_tasks)
    assert result.returncode == 1, f"循环应被检测到, got {result.returncode}"
    assert "循环" in result.stderr or "cycle" in result.stderr.lower()
