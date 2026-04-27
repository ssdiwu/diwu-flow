"""L2 unit tests for stop_archive.py — compile + detection logic."""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest


class TestCompile:
    """Verify stop_archive.py compiles without errors."""

    def test_import(self):
        """Module can be imported."""
        from hooks.scripts.stop_archive import (
            check,
            check_task_archive,
            check_recording_archive,
            _load_settings,
        )
        assert callable(check)
        assert callable(check_task_archive)
        assert callable(check_recording_archive)
        assert callable(_load_settings)


class TestLoadSettings:
    """Settings loading with fallbacks."""

    def test_default_when_missing(self, tmp_path, monkeypatch):
        """Returns defaults when dsettings.json missing."""
        monkeypatch.chdir(tmp_path)
        from hooks.scripts.stop_archive import _load_settings

        s = _load_settings()
        assert s["task_archive_threshold"] == 20
        assert s["recording_archive_threshold"] == 50
        assert s["recording_retention_days"] == 30

    def test_custom_values(self, tmp_path, monkeypatch):
        """Reads custom values from dsettings.json."""
        ds = tmp_path / ".diwu"
        ds.mkdir()
        (ds / "dsettings.json").write_text(
            json.dumps({
                "task_archive_threshold": 10,
                "recording_archive_threshold": 20,
                "recording_retention_days": 7,
            })
        )
        monkeypatch.chdir(tmp_path)
        from hooks.scripts.stop_archive import _load_settings

        s = _load_settings()
        assert s["task_archive_threshold"] == 10
        assert s["recording_archive_threshold"] == 20
        assert s["recording_retention_days"] == 7

    def test_corrupted_json_fallback(self, tmp_path, monkeypatch):
        """Falls back to defaults on corrupted JSON."""
        ds = tmp_path / ".diwu"
        ds.mkdir()
        (ds / "dsettings.json").write_text("{invalid json}")
        monkeypatch.chdir(tmp_path)
        from hooks.scripts.stop_archive import _load_settings

        s = _load_settings()
        assert s["task_archive_threshold"] == 20  # default preserved


class TestTaskArchive:
    """Task archive detection — 5 scenarios."""

    @pytest.fixture
    def sample_tasks(self):
        return [
            {"id": i, "status": "Done"} for i in range(15)
        ] + [
            {"id": i + 15, "status": "Cancelled"} for i in range(8)
        ] + [
            {"id": 24, "status": "InProgress"},
            {"id": 25, "status": "InSpec"},
        ]

    def test_below_threshold(self, sample_tasks):
        """23 terminal tasks < 20? No wait, 23 >= 20. Let me use fewer."""
        tasks = [{"id": 1, "status": "Done"}, {"id": 2, "status": "InProgress"}]
        from hooks.scripts.stop_archive import check_task_archive

        needs, count, thresh, msg = check_task_archive({"task_archive_threshold": 20}, tasks)
        assert needs is False
        assert count == 1
        assert msg == ""

    def test_at_threshold_exact(self):
        """Exactly at threshold triggers."""
        tasks = [{"id": i, "status": "Done"} for i in range(20)]
        from hooks.scripts.stop_archive import check_task_archive

        needs, count, thresh, msg = check_task_archive({"task_archive_threshold": 20}, tasks)
        assert needs is True
        assert count == 20
        assert "[ARCHIVE_CHECK]" in msg

    def test_above_threshold(self):
        """Above threshold triggers with correct count."""
        tasks = (
            [{"id": i, "status": "Done"} for i in range(18)]
            + [{"id": i + 18, "status": "Cancelled"} for i in range(10)]
        )
        from hooks.scripts.stop_archive import check_task_archive

        needs, count, thresh, msg = check_task_archive({"task_archive_threshold": 20}, tasks)
        assert needs is True
        assert count == 28
        assert "28" in msg

    def test_only_counts_terminal(self):
        """Only counts Done + Cancelled, ignores active statuses."""
        tasks = (
            [{"id": i, "status": "Done"} for i in range(5)]
            + [{"id": i + 5, "status": "InProgress"} for i in range(100)]
            + [{"id": i + 105, "status": "InSpec"} for i in range(100)]
        )
        from hooks.scripts.stop_archive import check_task_archive

        needs, count, thresh, msg = check_task_archive({"task_archive_threshold": 20}, tasks)
        assert needs is False
        assert count == 5

    def test_custom_threshold(self):
        """Respects custom threshold from settings."""
        tasks = [{"id": i, "status": "Done"} for i in range(15)]
        from hooks.scripts.stop_archive import check_task_archive

        needs, count, thresh, msg = check_task_archive({"task_archive_threshold": 10}, tasks)
        assert needs is True
        assert thresh == 10


class TestRecordingArchive:
    """Recording archive detection — 5 scenarios (dual-condition OR)."""

    def test_empty_directory(self, tmp_path, monkeypatch):
        """Empty recording dir → no trigger."""
        rec_dir = tmp_path / ".diwu" / "recording"
        rec_dir.mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        from hooks.scripts.stop_archive import check_recording_archive

        needs, total, old, ct, dt, msg = check_recording_archive({})
        assert needs is False
        assert total == 0

    def test_count_triggers(self, tmp_path, monkeypatch):
        """File count >= threshold triggers (condition A)."""
        rec_dir = tmp_path / ".diwu" / "recording"
        rec_dir.mkdir(parents=True)
        for i in range(55):
            (rec_dir / f"session-2026-04-{i:02d}.md").write_text("test")
        monkeypatch.chdir(tmp_path)
        from hooks.scripts.stop_archive import check_recording_archive

        needs, total, old, ct, dt, msg = check_recording_archive(
            {"recording_archive_threshold": 50, "recording_retention_days": 30}
        )
        assert needs is True
        assert total == 55
        assert "[ARCHIVE_CHECK]" in msg

    def test_age_triggers(self, tmp_path, monkeypatch):
        """Old file triggers even if count below threshold (condition B)."""
        rec_dir = tmp_path / ".diwu" / "recording"
        rec_dir.mkdir(parents=True)
        # Create one recent file and one very old file
        (rec_dir / "session-recent.md").write_text("new")
        old_file = rec_dir / "session-old.md"
        old_file.write_text("old")
        # Set mtime to 60 days ago
        old_mtime = time.time() - (60 * 86400)
        os.utime(old_file, (old_mtime, old_mtime))
        monkeypatch.chdir(tmp_path)
        from hooks.scripts.stop_archive import check_recording_archive

        needs, total, old, ct, dt, msg = check_recording_archive(
            {"recording_archive_threshold": 50, "recording_retention_days": 30}
        )
        assert needs is True
        assert old >= 1

    def test_no_trigger_both_conditions_false(self, tmp_path, monkeypatch):
        """No trigger when both conditions false."""
        rec_dir = tmp_path / ".diwu" / "recording"
        rec_dir.mkdir(parents=True)
        # 3 recent files, well below threshold
        for i in range(3):
            f = rec_dir / f"session-{i}.md"
            f.write_text("recent")
        monkeypatch.chdir(tmp_path)
        from hooks.scripts.stop_archive import check_recording_archive

        needs, total, old, ct, dt, msg = check_recording_archive(
            {"recording_archive_threshold": 50, "recording_retention_days": 30}
        )
        assert needs is False
        assert msg == ""

    def test_non_md_files_ignored(self, tmp_path, monkeypatch):
        """Non-.md files are not counted as session files."""
        rec_dir = tmp_path / ".diwu" / "recording"
        rec_dir.mkdir(parents=True)
        # Create many non-md files that should be ignored
        for i in range(60):
            (rec_dir / f"file{i}.txt").write_text("not a session")
        # Only 2 md files
        (rec_dir / "session-1.md").write_text("real session")
        (rec_dir / "session-2.md").write_text("real session")
        monkeypatch.chdir(tmp_path)
        from hooks.scripts.stop_archive import check_recording_archive

        needs, total, old, ct, dt, msg = check_recording_archive(
            {"recording_archive_threshold": 50, "recording_retention_days": 30}
        )
        assert needs is False
        assert total == 2  # only .md files counted


class TestIntegration:
    """Integration tests — check() main entry point."""

    def test_no_action_needed(self, tmp_path, monkeypatch):
        """Clean state → empty result list."""
        # Setup minimal environment
        diwu = tmp_path / ".diwu"
        diwu.mkdir()
        (diwu / "dtask.json").write_text(json.dumps({"tasks": []}))
        rec_dir = diwu / "recording"
        rec_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        from hooks.scripts.stop_archive import check

        results = check()
        assert results == []

    def test_task_and_recording_both_trigger(self, tmp_path, monkeypatch):
        """Both tracks trigger → 2 messages returned."""
        diwu = tmp_path / ".diwu"
        diwu.mkdir()

        # Task: 25 Done tasks
        tasks = [{"id": i, "status": "Done"} for i in range(25)]
        (diwu / "dtask.json").write_text(json.dumps({"tasks": tasks}))

        # Recording: 55 session files
        rec_dir = diwu / "recording"
        rec_dir.mkdir()
        for i in range(55):
            (rec_dir / f"s-{i}.md").write_text("session")

        monkeypatch.chdir(tmp_path)
        from hooks.scripts.stop_archive import check

        results = check()
        assert len(results) == 2
        levels = [r[0] for r in results]
        assert all(l == "info" for l in levels)
        messages = [r[1] for r in results]
        assert any("[ARCHIVE_CHECK]" in m for m in messages)
        assert any("Task archive" in m for m in messages)
        assert any("Recording archive" in m for m in messages)

    def test_check_accepts_explicit_args(self):
        """check() accepts explicit settings and tasks (no auto-load)."""
        from hooks.scripts.stop_archive import check

        settings = {
            "task_archive_threshold": 5,
            "recording_archive_threshold": 99999,
            "recording_retention_days": 99999,
        }
        tasks = [{"id": i, "status": "Done"} for i in range(10)]

        results = check(settings=settings, tasks=tasks)
        # At least task archive should trigger; recording suppressed by high threshold
        assert any("Task archive" in r[1] for r in results)

    def test_missing_dtask_file_graceful(self, tmp_path, monkeypatch):
        """Missing dtask file → task check skipped, no crash."""
        diwu = tmp_path / ".diwu"
        diwu.mkdir()
        # No dtask file created
        monkeypatch.chdir(tmp_path)
        from hooks.scripts.stop_archive import check

        results = check()
        # Should not crash; may have recording results but no task results
        assert isinstance(results, list)
