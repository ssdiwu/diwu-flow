import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from dtask_state import runtime_state_path, sync_runtime_state  # noqa: E402


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_sync_creates_standard_runtime_state(tmp_project_dir):
    dtask = {"tasks": []}
    result = sync_runtime_state(tmp_project_dir, dtask, persist=True, ensure_exists=True)
    assert result.ok is True
    state = json.loads(runtime_state_path(tmp_project_dir).read_text(encoding="utf-8"))
    assert state["version"] == 1
    assert state["task_sessions"] == {}
    assert state["dloop"] is None


def test_sync_cleans_stale_owner(tmp_project_dir):
    _write_json(
        runtime_state_path(tmp_project_dir),
        {
            "version": 1,
            "task_sessions": {
                "1": {"session_id": "sid-1", "started_at": "2026-04-30T12:00:00Z"}
            },
            "dloop": None,
        },
    )
    dtask = {"tasks": [{"id": 1, "title": "done", "status": "Done"}]}
    result = sync_runtime_state(tmp_project_dir, dtask, persist=True, ensure_exists=True)
    assert result.ok is True
    assert result.cleaned_task_ids == [1]
    state = json.loads(runtime_state_path(tmp_project_dir).read_text(encoding="utf-8"))
    assert state["task_sessions"] == {}


def test_sync_rejects_multiple_tasks_for_same_session(tmp_project_dir):
    _write_json(
        runtime_state_path(tmp_project_dir),
        {
            "version": 1,
            "task_sessions": {
                "1": {"session_id": "same-session", "started_at": "2026-04-30T12:00:00Z"},
                "2": {"session_id": "same-session", "started_at": "2026-04-30T12:05:00Z"},
            },
            "dloop": None,
        },
    )
    dtask = {
        "tasks": [
            {"id": 1, "title": "a", "status": "InProgress"},
            {"id": 2, "title": "b", "status": "InProgress"},
        ]
    }
    result = sync_runtime_state(tmp_project_dir, dtask, persist=False)
    assert result.ok is False
    assert "同一 session" in result.reason


def test_sync_rejects_status_field_in_task_sessions(tmp_project_dir):
    _write_json(
        runtime_state_path(tmp_project_dir),
        {
            "version": 1,
            "task_sessions": {
                "1": {
                    "session_id": "sid-1",
                    "started_at": "2026-04-30T12:00:00Z",
                    "status": "InProgress",
                }
            },
            "dloop": None,
        },
    )
    result = sync_runtime_state(tmp_project_dir, {"tasks": []}, persist=False)
    assert result.ok is False
    assert "status" in result.reason


def test_sync_migrates_legacy_dloop_state(tmp_project_dir):
    legacy = tmp_project_dir / ".diwu" / "dloop-state.json"
    _write_json(
        legacy,
        {
            "active": True,
            "session_id": "loop-session",
            "started_at": "2026-04-30T12:00:00Z",
            "completed_task_ids": [1],
            "current_iteration": 1,
            "max_tasks": 3,
            "stopped_at": None,
            "stop_reason": None,
        },
    )
    result = sync_runtime_state(tmp_project_dir, {"tasks": []}, persist=True, ensure_exists=True)
    assert result.ok is True
    assert result.migrated_legacy_loop is True
    state = json.loads(runtime_state_path(tmp_project_dir).read_text(encoding="utf-8"))
    assert state["dloop"]["session_id"] == "loop-session"
    assert not legacy.exists()


# ---------------------------------------------------------------------------
# pending_recording 单元测试（直接 import dtask_state 模块函数）
# ---------------------------------------------------------------------------

from dtask_state import (  # noqa: E402
    _normalize_loop,
    _normalize_pending_recording,
    clear_pending_recording,
    default_runtime_state,
    is_cron_mode,
    set_pending_recording,
    sync_runtime_state,
)


def test_default_includes_null_pending_recording():
    """default_runtime_state() 含 pending_recording: None。"""
    state = default_runtime_state()
    assert state.get("pending_recording") is None


def test_normalize_preserves_valid_pending_recording():
    """合法的 pending_recording dict 通过 normalize。"""
    valid = {
        "task_id": 1,
        "target_status": "Done",
        "released_at": "2026-05-01T00:00:00Z",
        "session_id": "sid-1",
    }
    result, err = _normalize_pending_recording(valid)
    assert err is None
    assert result == valid


@pytest.mark.parametrize("invalid_value", [
    "string",
    42,
    [],
    {"task_id": -1},                          # 负数 task_id
    {"task_id": "not-int"},                   # 非法 task_id 类型
    {"task_id": 1},                           # 缺少必填字段
    {"task_id": 1, "target_status": ""},      # 空 target_status
    {"task_id": 1, "target_status": "Done", "released_at": 123},  # released_at 非字符串
    {"task_id": 1, "target_status": "Done", "released_at": "", "session_id": ""},  # 空字符串
])
def test_normalize_rejects_invalid_pending_recording(invalid_value):
    """非法的 pending_recording 值被 normalize 拒绝。"""
    result, err = _normalize_pending_recording(invalid_value)
    assert err is not None
    assert result is None


def test_sync_self_heal_clears_deleted_task_marker(tmp_project_dir):
    """sync 时 pending_recording 指向不存在的 task_id → 自动清除标记。"""
    dtask = {"tasks": [{"id": 1, "title": "a", "status": "Done"}]}
    state_with_stale = {
        "version": 1,
        "task_sessions": {},
        "dloop": None,
        "pending_recording": {
            "task_id": 999,
            "target_status": "Done",
            "released_at": "2026-05-01T00:00:00Z",
            "session_id": "sid-stale",
        },
    }
    _write_json(runtime_state_path(tmp_project_dir), state_with_stale)
    result = sync_runtime_state(tmp_project_dir, dtask, persist=True)
    assert result.ok is True
    final = json.loads(runtime_state_path(tmp_project_dir).read_text(encoding="utf-8"))
    assert final.get("pending_recording") is None


def test_sync_self_heal_clears_status_mismatch_marker(tmp_project_dir):
    """sync 时 pending_recording 的 target_status 与任务实际 status 不匹配 → 自动清除。"""
    dtask = {"tasks": [{"id": 1, "title": "a", "status": "InProgress"}]}
    state_with_mismatch = {
        "version": 1,
        "task_sessions": {},
        "dloop": None,
        "pending_recording": {
            "task_id": 1,
            "target_status": "Done",       # 实际状态是 InProgress
            "released_at": "2026-05-01T00:00:00Z",
            "session_id": "sid-x",
        },
    }
    _write_json(runtime_state_path(tmp_project_dir), state_with_mismatch)
    result = sync_runtime_state(tmp_project_dir, dtask, persist=True)
    assert result.ok is True
    final = json.loads(runtime_state_path(tmp_project_dir).read_text(encoding="utf-8"))
    assert final.get("pending_recording") is None


# ---------------------------------------------------------------------------
# _normalize_loop mode / cron_job_id 字段测试
# ---------------------------------------------------------------------------

def _valid_loop_base(**overrides):
    base = {
        "active": True,
        "session_id": "test-sid",
        "started_at": "2026-05-09T00:00:00Z",
        "completed_task_ids": [],
        "current_iteration": 0,
        "max_tasks": 0,
        "stopped_at": None,
        "stop_reason": None,
    }
    base.update(overrides)
    return base


def test_normalize_loop_accepts_session_mode():
    """默认 mode=session（显式传入）通过校验。"""
    result, err = _normalize_loop(_valid_loop_base(mode="session"))
    assert err is None
    assert result["mode"] == "session"


def test_normalize_loop_accepts_cron_mode():
    """mode=cron 通过校验。"""
    result, err = _normalize_loop(_valid_loop_base(
        mode="cron", cron_job_id="job-123"
    ))
    assert err is None
    assert result["mode"] == "cron"
    assert result["cron_job_id"] == "job-123"


def test_normalize_loop_defaults_mode_to_session():
    """无 mode 字段时默认为 'session'。"""
    loop = {
        "active": True,
        "session_id": "test-sid",
        "started_at": "2026-05-09T00:00:00Z",
        "completed_task_ids": [],
        "current_iteration": 0,
        "max_tasks": 0,
        "stopped_at": None,
        "stop_reason": None,
        # 故意不传 mode 字段
    }
    result, err = _normalize_loop(loop)
    assert err is None
    assert result["mode"] == "session"


def test_normalize_loop_rejects_invalid_mode():
    """非法 mode 值被拒绝。"""
    result, err = _normalize_loop(_valid_loop_base(mode="invalid-mode"))
    assert err is not None
    assert "mode" in err
    assert result is None


def test_normalize_loop_rejects_non_string_cron_job_id():
    """cron_job_id 非字符串被拒绝。"""
    result, err = _normalize_loop(_valid_loop_base(mode="cron", cron_job_id=12345))
    assert err is not None
    assert "cron_job_id" in err


def test_normalize_loop_accepts_null_cron_job_id():
    """cron_job_id=null 通过（可选字段）。"""
    result, err = _normalize_loop(_valid_loop_base(mode="cron", cron_job_id=None))
    assert err is None
    assert result["cron_job_id"] is None


def test_is_cron_mode_helper():
    """is_cron_mode() helper 函数正确判断。"""
    assert is_cron_mode({"mode": "cron"}) is True
    assert is_cron_mode({"mode": "session"}) is False
    assert is_cron_mode({}) is False  # 无 mode 字段
    assert is_cron_mode(None) is False
    assert is_cron_mode("not-a-dict") is False


def test_normalize_loop_preserves_cron_fields_in_sync(tmp_project_dir):
    """集成：sync_runtime_state 正确保留 mode 和 cron_job_id 字段。"""
    state_with_cron = {
        "version": 1,
        "task_sessions": {},
        "dloop": _valid_loop_base(
            mode="cron", cron_job_id="sync-job-abc"
        ),
    }
    _write_json(runtime_state_path(tmp_project_dir), state_with_cron)
    result = sync_runtime_state(tmp_project_dir, {"tasks": []}, persist=False)
    assert result.ok is True
    dloop = result.state.get("dloop")
    assert dloop is not None
    assert dloop["mode"] == "cron"
    assert dloop["cron_job_id"] == "sync-job-abc"
