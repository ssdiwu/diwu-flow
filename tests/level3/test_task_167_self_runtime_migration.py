from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
CLAUDE_DIR = PROJECT_ROOT / ".claude"
DIWU_DIR = PROJECT_ROOT / ".diwu"

RUNTIME_FILES = [
    "dtask.json",
    "recording",
    "decisions.md",
    "dsettings.json",
    "archive",
    "continue-here.md",
]
NATIVE_CLAUDE_FILES = [
    "CLAUDE.md",
    "rules",
    "skills",
    "examples",
]


def test_runtime_files_moved_to_diwu():
    assert DIWU_DIR.exists()
    for name in RUNTIME_FILES:
        assert (DIWU_DIR / name).exists(), name



def test_claude_keeps_only_native_mechanisms_after_migration():
    for name in RUNTIME_FILES:
        assert not (CLAUDE_DIR / name).exists(), name
    for name in NATIVE_CLAUDE_FILES:
        assert (CLAUDE_DIR / name).exists(), name



def test_migration_preserves_task_count_and_recording_sessions():
    task_data = json.loads((DIWU_DIR / "dtask.json").read_text(encoding="utf-8"))
    assert isinstance(task_data.get("tasks"), list)
    sessions = sorted((DIWU_DIR / "recording").glob("session-*.md"))
    assert sessions, "expected migrated session files"
