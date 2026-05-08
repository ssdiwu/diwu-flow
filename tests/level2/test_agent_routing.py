"""Level 2: Agent 路由判断测试
"""
import yaml, pytest

AGENTS_DIR = "agents"

def _load_fm(p):
    t = p.read_text()
    if t.startswith("---"):
        end = t.find("---", 3)
        return yaml.safe_load(t[3:end]) if end > 0 else {}
    return {}

class TestArchitectDomainIsolation:
    def test_architect_dtask_domain(self, project_root):
        d = _load_fm(project_root / AGENTS_DIR / "architect.md")
        assert "dtask" in d.get("description", "").lower() or "定义域" in d.get("description", "")

    def test_architect_no_drun(self, project_root):
        d = _load_fm(project_root / AGENTS_DIR / "architect.md")
        desc = d.get("description", "")
        assert not ("drun" in desc.lower() and "执行域" in desc.lower() and "不属于" not in desc)

    def test_architect_body_dtask(self, project_root):
        body = (project_root / AGENTS_DIR / "architect.md").read_text()
        assert "dtask 定义域" in body or "dtask 主归属" in body

class TestDebuggerDomainIsolation:
    def test_debugger_drun_domain(self, project_root):
        d = _load_fm(project_root / AGENTS_DIR / "debugger.md")
        assert "drun" in d.get("description", "").lower() or "执行域" in d.get("description", "")

    def test_debugger_no_dcorr(self, project_root):
        d = _load_fm(project_root / AGENTS_DIR / "debugger.md")
        assert "不替 dcorr" in d.get("description", "")

    def test_debugger_body_drun(self, project_root):
        body = (project_root / AGENTS_DIR / "debugger.md").read_text()
        assert "drun 执行域" in body

class TestDebuggerPriority:
    def test_debugger_priority_over_explorer(self, project_root):
        drun = (project_root / "skills/drun/SKILL.md").read_text()
        assert "优先于 explorer" in drun or "直接优先" in drun

    def test_debugger_no_edit_write(self, project_root):
        d = _load_fm(project_root / AGENTS_DIR / "debugger.md")
        assert set(d.get("tools", [])) & {"Edit", "Write"} == set()

    def test_debugger_chain(self, project_root):
        body = (project_root / AGENTS_DIR / "debugger.md").read_text()
        assert "implementer" in body and "verifier" in body
