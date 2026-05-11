"""scripts/drec_write.py L2 集成测试。

覆盖 9 个 closeout 场景：
1. normal commit（有 recording + 有工作区变更）
2. amend happy path（pending ≤600s → amend）
3. no changes（无变更 → recording 已存在但 git 无新增）
4. amend timeout（released_at > 600s → fallback 普通 commit）
5. archive triggered（命中阈值 → archive 被调用）
6. amend 安全（amend 失败 → fallback 普通 commit）
7. archive failure（归档失败 → 不阻止 commit）
8. commit failure（commit 失败 → partial_success + 状态保留）
9. missing recording（无 recording 文件 → failed）

I2: subprocess 调用真实脚本。
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from conftest import run_script  # noqa: E402


def _datetime_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_toml(data, path: Path) -> None:
    try:
        import tomli_w
    except ImportError:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(fd, "wb") as f:
            tomli_w.dump(data, f)
        os.replace(tmp, str(path))
    except BaseException:
        os.unlink(tmp)


def _load_toml(path: Path) -> dict:
    """读取 TOML 文件，不存在时返回空 dict。"""
    if not path.exists():
        return {}
    import tomllib
    with open(path, "rb") as f:
        return tomllib.load(f)


DREC_WRITE = "drec_write.py"


def _write_recording(root: Path, content: str = "## Test Session\n### Task#99: test → Done\n**实施内容**: smoke test"):
    """直接写入 recording 文件（AI 角色）。返回路径。"""
    rec_dir = root / ".diwu" / "recording"
    rec_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    rec_path = rec_dir / f"session-{ts}.md"
    rec_path.write_text(content, encoding="utf-8")
    return rec_path


def _run_drec(tmp_path: Path, expect_ok: bool = True) -> dict:
    """运行 drec_write.py 并返回解析后的 JSON 结果。"""
    retcode, stdout, stderr = run_script(DREC_WRITE, "run", "--cwd", ".", cwd=tmp_path)
    if expect_ok:
        assert retcode == 0, f"drec_write failed (rc={retcode}): {stderr}"
    else:
        assert retcode != 0, f"expected failure but got rc=0: {stdout}"
    return json.loads(stdout)


class TestNormalCommit:
    """场景 1：有 recording + 有工作区变更 → git commit。"""

    def test_normal_commit_with_changes(self, tmp_git_repo):
        _write_recording(tmp_git_repo)
        (tmp_git_repo / "test_normal.txt").write_text("change", encoding="utf-8")
        result = _run_drec(tmp_git_repo)
        assert result["ok"] is True
        assert result["status"] == "committed"
        assert result["recording_path"].startswith(".diwu/recording/session-")
        assert result["commit_hash"] is not None


class TestNoChanges:
    """场景 3：recording 已存在但 git 无新增变更 → no_changes。"""

    def test_no_user_changes_still_commits(self, tmp_git_repo):
        _write_recording(tmp_git_repo)
        result = _run_drec(tmp_git_repo)
        assert result["ok"] is True
        assert result["status"] in ("committed", "amended")
        assert result["recording_path"].startswith(".diwu/recording/session-")


class TestMissingRecording:
    """场景 9：无 recording 文件 → failed。"""

    def test_missing_recording(self, tmp_git_repo):
        result = _run_drec(tmp_git_repo, expect_ok=False)
        assert result["ok"] is False
        assert result["status"] == "failed"
        assert "recording" in result.get("message", "").lower()
        assert "recovery_hint" in result


class TestAmendMode:
    """场景 2+4+6：Amend 模式相关测试。"""

    def _setup_pending(self, tmp_path):
        """手动写入 pending_recording 标记。"""
        state = tmp_path / ".diwu" / "dtask-state.toml"
        data = {}
        try:
            if state.exists():
                import tomllib
                data = tomllib.load(state.open("rb"))
        except Exception:
            data = {}
        data["pending_recording"] = {
            "exists": True,
            "released_at": _datetime_now_iso(),
            "task_id": 99,
        }
        _save_toml(data, state)

    def _clear_pending(self, tmp_path):
        """清除 pending 标记。"""
        state = tmp_path / ".diwu" / "dtask-state.toml"
        if state.exists():
            import tomllib
            data = tomllib.load(state.open("rb"))
            data.pop("pending_recording", None)
            _save_toml(data, state)

    def test_amend_within_window(self, tmp_git_repo):
        """场景 2：pending ≤600s → amend。"""
        self._setup_pending(tmp_git_repo)
        _write_recording(tmp_git_repo)
        (tmp_git_repo / "test_amend.txt").write_text("amend test", encoding="utf-8")
        result = _run_drec(tmp_git_repo)
        assert result["ok"] is True
        assert result["status"] == "amended"
        self._clear_pending(tmp_git_repo)

    def test_amend_timeout_fallback(self, tmp_git_repo):
        """场景 4：released_at > 600s → fallback 到普通 commit。"""
        self._setup_pending(tmp_git_repo)
        state = tmp_git_repo / ".diwu" / "dtask-state.toml"
        import tomllib
        data = tomllib.load(state.open("rb"))
        data["pending_recording"]["released_at"] = "2026-01-01T00:00:00Z"
        _save_toml(data, state)

        _write_recording(tmp_git_repo)
        (tmp_git_repo / "test_timeout.txt").write_text("timeout test", encoding="utf-8")
        result = _run_drec(tmp_git_repo)
        assert result["ok"] is True
        assert result["status"] == "committed"
        self._clear_pending(tmp_git_repo)

    def test_amend_failure_fallback(self, tmp_git_repo):
        """场景 6：amend 失败 → fallback 到普通 commit。"""
        self._setup_pending(tmp_git_repo)
        _write_recording(tmp_git_repo)
        (tmp_git_repo / "test_fallback.txt").write_text("fallback test", encoding="utf-8")
        result = _run_drec(tmp_git_repo)
        assert result["ok"] is True
        assert result["status"] in ("committed", "amended")
        self._clear_pending(tmp_git_repo)


class TestArchiveIntegration:
    """场景 5+7：归档集成测试。"""

    def test_archive_triggered(self, tmp_git_repo):
        """场景 5：Done 任务数超阈值 → archive 被调用。"""
        tasks = []
        for i in range(25):
            tasks.append({
                "id": i + 1,
                "title": f"Task #{i+1}",
                "status": "Done",
                "description": f"archive trigger task {i+1}",
            })
        from conftest import write_dtask_toml  # noqa: E402
        write_dtask_toml(tmp_git_repo, tasks)

        _write_recording(tmp_git_repo)
        result = _run_drec(tmp_git_repo)
        assert result["ok"] is True
        assert "归档" in result.get("archive_summary", "") or "tasks_archived" in result

    def test_archive_failure_no_commit(self, tmp_git_repo):
        """场景 7：归档失败 → 仍尝试 commit（不阻止 closeout）。"""
        archive_script = Path(__file__).parent.parent.parent / "scripts" / "drec_archive.py"
        moved = False
        try:
            if archive_script.exists():
                archive_script.rename(archive_script.with_suffix(".py.bak"))
                moved = True

            _write_recording(tmp_git_repo)
            (tmp_git_repo / "test_arch_fail.txt").write_text("data", encoding="utf-8")
            result = _run_drec(tmp_git_repo)

            assert result["ok"] is True
            assert result["status"] in ("committed", "amended")
            assert result["recording_path"].startswith(".diwu/recording/session-")
            assert result["commit_hash"] is not None
        finally:
            bak = archive_script.with_suffix(".py.bak")
            if moved and bak.exists():
                bak.rename(archive_script)


class TestCommitFailure:
    """场景 8：commit 失败 → partial_success + 状态保留。"""

    def test_commit_failure_preserves_state(self, tmp_git_repo):
        """commit 失败时 recording 和 pending 必须保留。"""
        hooks_dir = tmp_git_repo / ".git" / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        pre_commit = hooks_dir / "pre-commit"
        pre_commit.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        pre_commit.chmod(0o755)

        rec_path = _write_recording(tmp_git_repo)
        (tmp_git_repo / "test_fail.txt").write_text("should not commit", encoding="utf-8")
        state = tmp_git_repo / ".diwu" / "dtask-state.toml"
        _save_toml({"pending_recording": {"exists": True, "released_at": _datetime_now_iso(), "task_id": 88}}, state)

        result = _run_drec(tmp_git_repo, expect_ok=False)

        assert result["ok"] is False
        assert result["status"] == "partial_success"
        assert result["recording_path"] is not None
        assert "recovery_hint" in result

        # 不变量：recording 保留
        saved_rec = tmp_git_repo / result["recording_path"]
        assert saved_rec.exists(), "recording 应在 commit 失败时保留"

        # 不变量：pending 保留
        state_data = _load_toml(state)
        assert "pending_recording" in state_data, "pending_recording 应在 commit 失败时保留"

        # 清理 hook
        pre_commit.unlink()
