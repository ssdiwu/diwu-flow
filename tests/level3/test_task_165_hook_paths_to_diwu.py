from pathlib import Path
import subprocess

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
HOOKS_DIR = PROJECT_ROOT / "hooks" / "scripts"
TASK_JSON_PATH = PROJECT_ROOT / ".claude" / "dtask.json"

RUNTIME_TARGETS = [
    "dtask.json",
    "recording",
    "decisions.md",
    "dsettings.toml",
    "project-pitfalls.md",
    "archive",
]

# Round 4: hooks.json 注册的脚本 + 被调度器调用的库模块
EXPECTED_DIWU_FILES = {
    # hooks.json 直接注册的入口脚本
    "task_completed.py": [".diwu/dsettings.toml", ".diwu/dtask.json", ".diwu/recording/", ".diwu/decisions.md"],
    "drift_detect_pre.py": [".diwu/dsettings.toml"],
    "context_monitor.py": [".diwu/dsettings.toml", ".diwu/.context_monitor_cache"],
    "plan_exit_hint.py": [],
    "task_entry_guard.py": [".diwu/dtask.json", ".diwu/dtask-state.json", ".diwu/recording", ".diwu/decisions.md"],
    "stop_decision.py": [".diwu/dtask.json", ".diwu/dsettings.toml"],
    "pre_compact.py": [".diwu/recording"],
    "session_start.py": [],
    "task_created_validate.py": [".diwu/dtask.json"],
    # 库模块（被 stop_decision.py 内部 import 调用，非独立 hook 入口）
    "stop_archive.py": [".diwu/dtask.json", ".diwu/dsettings.toml", ".diwu/recording"],
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
    assert str(PROJECT_ROOT / ".claude" / "dtask.json") not in text


def test_hook_scripts_py_compile():
    files = [str(p) for p in HOOKS_DIR.glob("*.py")]
    subprocess.run(["python3", "-m", "py_compile", *files], check=True, cwd=PROJECT_ROOT)
