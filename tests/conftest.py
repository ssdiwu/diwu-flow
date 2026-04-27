"""pytest 共享 fixture"""
import json, os, shutil, tempfile, pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()


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
def sample_task_json(tmp_path):
    """生成示例 dtask.json"""
    task_file = tmp_path / "dtask.json"
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
    task_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return task_file
