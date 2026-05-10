"""L2 tests for _fs_snapshot.py — zero-git metadata + worktree detection."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hooks.scripts._fs_snapshot import (
    get_git_metadata,
    get_project_snapshot,
    get_worktree_changes,
)


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=repo, check=True, capture_output=True)
    (repo / "tracked.txt").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init commit"], cwd=repo, check=True, capture_output=True)
    return repo


class TestGetGitMetadata:
    def test_non_git_directory_graceful(self, tmp_path: Path):
        meta = get_git_metadata(tmp_path)
        assert meta.is_git_repo is False
        assert meta.branch is None
        assert meta.recent_commits == []

    def test_reads_branch_and_recent_commit(self, tmp_git_repo: Path):
        meta = get_git_metadata(tmp_git_repo)
        assert meta.is_git_repo is True
        assert meta.branch is not None
        assert meta.head_hash is not None
        assert len(meta.recent_commits) >= 1
        assert meta.recent_commits[0]["subject"] == "init commit"

    def test_packed_refs_fallback(self, tmp_git_repo: Path):
        subprocess.run(["git", "pack-refs", "--all"], cwd=tmp_git_repo, check=True, capture_output=True)
        head_ref = tmp_git_repo / ".git" / "refs" / "heads"
        if head_ref.exists():
            for p in head_ref.rglob("*"):
                if p.is_file():
                    p.unlink()
        meta = get_git_metadata(tmp_git_repo)
        assert meta.is_git_repo is True
        assert meta.head_hash is not None


class TestGetWorktreeChanges:
    def test_clean_repo(self, tmp_git_repo: Path):
        changes = get_worktree_changes(tmp_git_repo)
        assert changes.is_clean is True
        assert changes.modified == []
        assert changes.untracked == []

    def test_detects_modified_tracked_file(self, tmp_git_repo: Path):
        (tmp_git_repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        changes = get_worktree_changes(tmp_git_repo)
        assert "tracked.txt" in changes.modified
        assert changes.is_clean is False

    def test_detects_untracked_file(self, tmp_git_repo: Path):
        (tmp_git_repo / "new.txt").write_text("new\n", encoding="utf-8")
        changes = get_worktree_changes(tmp_git_repo)
        assert "new.txt" in changes.untracked
        assert changes.is_clean is False

    def test_detects_diu_dirty_without_marking_code_dirty(self, tmp_git_repo: Path):
        diwu = tmp_git_repo / ".diwu"
        diwu.mkdir(exist_ok=True)
        (diwu / "dtask.toml").write_text('{"tasks": []}', encoding="utf-8")
        changes = get_worktree_changes(tmp_git_repo)
        assert any(p.endswith(".diwu/dtask.toml") for p in changes.diu_dirty)
        assert changes.has_code_changes is False

    def test_unsupported_index_version_degrades_safely(self, tmp_git_repo: Path):
        index_path = tmp_git_repo / ".git" / "index"
        raw = bytearray(index_path.read_bytes())
        raw[4:8] = (4).to_bytes(4, "big")
        index_path.write_bytes(raw)
        changes = get_worktree_changes(tmp_git_repo)
        assert isinstance(changes.modified, list)
        assert isinstance(changes.untracked, list)


class TestGetProjectSnapshot:
    def test_returns_both_structures(self, tmp_git_repo: Path):
        changes, meta = get_project_snapshot(tmp_git_repo)
        assert hasattr(changes, "modified")
        assert hasattr(meta, "branch")
        assert meta.is_git_repo is True
