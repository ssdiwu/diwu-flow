"""level2_scripts 测试共享 fixture

I2: CLI-first 策略 — 默认通过 subprocess 调用脚本验证 CLI 契约
I3: tmp_git_repo fixture 初始化 git repo 但不断言分支名（兼容不同 git 默认分支）
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


@pytest.fixture
def tmp_project_dir(tmp_path):
    """创建临时项目目录，模拟 .diwu 结构。"""
    project = tmp_path / "project"
    project.mkdir()
    (project / ".diwu").mkdir()
    return project


@pytest.fixture
def tmp_git_repo(tmp_path):
    """初始化一个临时 git 仓库（已有一条 commit）。

    I3: 配置 user.name/email 但不断言当前分支名（main/master 取决于 git init.defaultBranch）。
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    # 避免影响全局 git config
    env = os.environ.copy()
    env["GIT_CONFIG_COUNT"] = "2"
    env["GIT_CONFIG_KEY_0"] = "user.name"
    env["GIT_CONFIG_VALUE_0"] = "Test User"
    env["GIT_CONFIG_KEY_1"] = "user.email"
    env["GIT_CONFIG_VALUE_1"] = "test@example.com"

    subprocess.run(
        ["git", "init"], cwd=repo, check=True, capture_output=True, env=env
    )
    test_file = repo / "README.md"
    test_file.write_text("# test\n")
    subprocess.run(
        ["git", "add", "."], cwd=repo, check=True, capture_output=True, env=env
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=env,
    )
    return repo


def assert_rel_time_shape(text: str):
    """I4: 断言相对时间输出包含分钟前/小时前/天前等合法结构。

    不断言具体数值（时间敏感），只断言格式形状。
    """
    assert text is not None
    assert isinstance(text, str)
    # 至少包含一个已知的时间单位关键词
    keywords = ["分钟前", "小时前", "天前", "刚刚"]
    has_any = any(kw in text for kw in keywords)
    # 也允许纯日期格式 YYYY-MM-DD 作为兜底
    is_date = len(text) == 10 and text[4] == "-" and text[7] == "-"
    assert has_any or is_date, (
        f"相对时间 '{text}' 不匹配任何已知格式，"
        f"期望含 {keywords} 之一或日期格式 YYYY-MM-DD"
    )


def run_script(script_name: str, *args, cwd=None, env=None):
    """I2: CLI-first 辅助 — 通过 subprocess 运行 scripts/ 下的脚本。

    Returns (returncode, stdout, stderr).
    可选 env: dict，合并到默认环境变量（覆盖同名键）。
    """
    script = SCRIPTS_DIR / script_name
    base_env = os.environ.copy()
    base_env["DIWU_SILENT"] = "1"
    if env:
        base_env.update(env)
    result = subprocess.run(
        [sys.executable, str(script)] + list(args),
        capture_output=True,
        text=True,
        cwd=cwd or str(PROJECT_ROOT),
        env=base_env,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def write_dtask_toml(root: Path, tasks: list) -> None:
    """Write dtask.toml to a project root directory."""
    import tomli_w
    diwu = root / ".diwu"
    diwu.mkdir(exist_ok=True)
    data = {"tasks": tasks}
    with open(diwu / "dtask.toml", "wb") as f:
        tomli_w.dump(data, f)


def write_runtime_toml(root: Path, state: dict) -> None:
    """Write dtask-state.toml to a project root directory. Removes None values for tomli_w compatibility."""
    import tomli_w
    diwu = root / ".diwu"
    diwu.mkdir(exist_ok=True)

    def _remove_none(obj):
        if isinstance(obj, dict):
            return {k: _remove_none(v) for k, v in obj.items() if v is not None}
        if isinstance(obj, list):
            return [_remove_none(v) for v in obj]
        return obj

    cleaned = _remove_none(state)
    with open(diwu / "dtask-state.toml", "wb") as f:
        tomli_w.dump(cleaned, f)


def read_runtime_toml(root: Path) -> dict:
    """Read dtask-state.toml from a project root directory."""
    import tomllib
    with open(root / ".diwu" / "dtask-state.toml", "rb") as f:
        return tomllib.load(f)


def read_dtask_toml(root: Path) -> dict:
    """Read dtask.toml from a project root directory."""
    import tomllib
    with open(root / ".diwu" / "dtask.toml", "rb") as f:
        return tomllib.load(f)
