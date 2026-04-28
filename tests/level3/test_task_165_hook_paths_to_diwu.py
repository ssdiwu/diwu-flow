from pathlib import Path
import subprocess

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
HOOKS_DIR = PROJECT_ROOT / "hooks" / "scripts"
TASK_JSON_PATH = PROJECT_ROOT / ".claude" / "dtask.json"

RUNTIME_TARGETS = [
    "dtask.json",
    "recording",
    "decisions.md",
    "dsettings.json",
    "project-pitfalls.md",
    "archive",
]

# Round 3 清理后：hooks.json 正式注册的全部脚本
EXPECTED_DIWU_FILES = {
    "task_completed.py": [".diwu/dsettings.json", ".diwu/dtask.json", ".diwu/recording/", ".diwu/decisions.md"],
    "drift_detect_pre.py": [".diwu/dtask.json", ".diwu/dsettings.json"],
    "context_monitor.py": [".diwu/dsettings.json", ".diwu/.context_monitor_cache.json"],
    "stop_decision.py": [".diwu/dtask.json", ".diwu/dsettings.json"],
    "stop_archive.py": [".diwu/dtask.json", ".diwu/dsettings.json", ".diwu/recording"],
    "pre_compact.py": [".diwu/dtask.json", ".diwu/recording"],
    "session_start.py": [],
    "task_created_validate.py": [".diwu/dtask.json"],
    # 以下为规划中/未实现：
    # inject_errors_decisions.py, stop_background.py,
    # post_tool_use_failure.py, post_tool_reminder.py, subagent_stop.py
}


def test_runtime_paths_move_to_diwu_in_hook_scripts():
    for name, expected_paths in EXPECTED_DIWU_FILES.items():
        script_path = HOOKS_DIR / name
        if not script_path.exists():
            continue  # 跳过未迁移的脚本
        text = script_path.read_text(encoding="utf-8")
        for expected in expected_paths:
            assert expected in text, f"{name} 缺少 {expected}"


def test_hook_scripts_no_longer_reference_claude_runtime_paths():
    offenders = []
    for path in HOOKS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for target in RUNTIME_TARGETS:
            needle = f".claude/{target}"
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert offenders == [], "仍有 .claude 运行时路径残留: " + ", ".join(offenders)


def test_task_created_validate_uses_relative_diwu_task_path():
    text = (HOOKS_DIR / "task_created_validate.py").read_text(encoding="utf-8")
    assert 'TASK_JSON_PATH = ".diwu/dtask.json"' in text
    assert "/Users/diwu/Documents/codes/Githubs/diwu-workflow/.claude/dtask.json" not in text


def test_hook_scripts_py_compile():
    files = [str(p) for p in HOOKS_DIR.glob("*.py")]
    subprocess.run(["python3", "-m", "py_compile", *files], check=True, cwd=PROJECT_ROOT)
