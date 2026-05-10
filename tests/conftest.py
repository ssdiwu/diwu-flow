"""pytest 共享 fixture"""
import json, os, shutil, tempfile, pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()


def write_dtask_toml(root: Path, tasks: list) -> None:
    """Write dtask.toml to a project root directory."""
    diwu = root / ".diwu"
    diwu.mkdir(exist_ok=True)
    data = {"tasks": tasks}
    import tomli_w
    with open(diwu / "dtask.toml", "wb") as f:
        tomli_w.dump(data, f)


def read_dtask_toml(root: Path) -> dict:
    """Read dtask.toml from a project root directory."""
    import tomllib
    with open(root / ".diwu" / "dtask.toml", "rb") as f:
        return tomllib.load(f)


def write_runtime_toml(root: Path, state: dict) -> None:
    """Write dtask-state.toml to a project root directory. Removes None values for tomli_w compatibility."""
    diwu = root / ".diwu"
    diwu.mkdir(exist_ok=True)

    def _remove_none(obj):
        if isinstance(obj, dict):
            return {k: _remove_none(v) for k, v in obj.items() if v is not None}
        if isinstance(obj, list):
            return [_remove_none(v) for v in obj]
        return obj

    cleaned = _remove_none(state)
    import tomli_w
    with open(diwu / "dtask-state.toml", "wb") as f:
        tomli_w.dump(cleaned, f)


def read_runtime_toml(root: Path) -> dict:
    """Read dtask-state.toml from a project root directory."""
    import tomllib
    with open(root / ".diwu" / "dtask-state.toml", "rb") as f:
        return tomllib.load(f)


@pytest.fixture
def project_root():
    return PROJECT_ROOT


@pytest.fixture
def json_files():
    """发现项目下所有 .json 文件"""
    def _find(pattern="*.json", root=None):
        root = root or PROJECT_ROOT
        return [str(p) for p in Path(root).rglob(pattern)]
    return _find


@pytest.fixture
def tmp_project_dir(tmp_path):
    """创建临时项目目录，模拟 .claude 结构"""
    project = tmp_path / "project"
    project.mkdir()
    (project / ".claude").mkdir()
    return project


@pytest.fixture
def sample_task_toml(tmp_path):
    """生成示例 dtask.toml"""
    import tomli_w
    task_file = tmp_path / "dtask.toml"
    data = {
        "tasks": [
            {
                "id": 1,
                "title": "示例任务",
                "description": "测试任务",
                "acceptance": ["Given x When y Then z"],
                "steps": ["1. 测试步骤"],
                "category": "functional",
                "status": "InDraft"
            }
        ]
    }
    task_file.write_bytes(tomli_w.dumps(data).encode('utf-8'))
    return task_file
