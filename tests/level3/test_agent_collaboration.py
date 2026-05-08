"""Level 3: Agent 协作一致性测试
"""
import pytest
from pathlib import Path

AGENTS_DIR = "agents"

class TestAgentCountMatchesReadme:
    def test_readme_five_agents(self, project_root):
        r = (project_root / AGENTS_DIR / "README.md").read_text()
        rows = [l for l in r.split(chr(10)) if l.startswith("| **") and "Agent" not in l and "---" not in l]
        assert len(rows) == 5, f'Got {len(rows)} rows'

    def test_readme_all_listed(self, project_root):
        r = (project_root / AGENTS_DIR / "README.md").read_text()
        for n in ["explorer","implementer","verifier","architect","debugger"]:
            assert f"| **{n}**" in r or f"| {n} |" in r, f'Missing {n}'

class TestDomainSeparation:
    def test_architect_dtask_not_drun(self, project_root):
        r = (project_root / AGENTS_DIR / "README.md").read_text()
        ar = [l for l in r.split(chr(10)) if "architect" in l and "|" in l][0]
        assert "dtask" in ar.lower()
        assert not ("drun 执行域" in ar and "不属于" not in ar)

    def test_debugger_drun_not_dtask(self, project_root):
        r = (project_root / AGENTS_DIR / "README.md").read_text()
        dr = [l for l in r.split(chr(10)) if "debugger" in l and "|" in l][0]
        assert "drun" in dr.lower()
        assert not ("dtask 定义域" in dr and "不属于" not in dr)

class TestExistingChainStable:
    def test_explorer_readonly(self, project_root):
        r = (project_root / AGENTS_DIR / "README.md").read_text()
        er = [l for l in r.split(chr(10)) if "explorer" in l and "|" in l][0]
        assert "只读" in er or "不修改" in er

    def test_implementer_writes(self, project_root):
        r = (project_root / AGENTS_DIR / "README.md").read_text()
        ir = [l for l in r.split(chr(10)) if l.startswith("| **implementer**")][0]
        assert "代码修改" in ir or "写代码" in ir

    def test_verifier_verifies(self, project_root):
        r = (project_root / AGENTS_DIR / "README.md").read_text()
        vr = [l for l in r.split(chr(10)) if l.startswith("| **verifier**")][0]
        assert "独立验收" in vr or "验收" in vr
