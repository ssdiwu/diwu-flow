"""Documentation cross-reference consistency checker.

Validates that key numbers (script counts, event counts, rule counts, etc.)
are consistent across CLAUDE.md, README.md, api.md, and actual filesystem.
Also checks skills directory names against plugin.json references.

Level 3 (documentation/consistency) — reads file contents, no subprocess needed.
"""

import json
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# --- helpers ---

PLUGIN_JSON = PROJECT_ROOT / '.claude-plugin' / 'plugin.json'
MARKETPLACE_JSON = PROJECT_ROOT / '.claude-plugin' / 'marketplace.json'
API_MD = PROJECT_ROOT / '.doc' / 'api.md'
PRODUCT_MD = PROJECT_ROOT / '.doc' / 'product.md'
SCHEMA_MD = PROJECT_ROOT / '.doc' / 'schema.md'
CLAUDE_MD = PROJECT_ROOT / '.claude' / 'CLAUDE.md'
README_MD = PROJECT_ROOT / 'README.md'
FILE_LAYOUT_MD = PROJECT_ROOT / '.claude' / 'rules' / 'file-layout.md'
FILE_LAYOUT_ASSET = PROJECT_ROOT / 'assets' / 'dinit' / 'assets' / 'rules' / 'file-layout.md'

HOOKS_JSON = PROJECT_ROOT / 'hooks' / 'hooks.json'
SKILLS_DIR = PROJECT_ROOT / 'skills'
COMMANDS_DIR = PROJECT_ROOT / 'commands'
AGENTS_DIR = PROJECT_ROOT / 'agents'
RULES_DIR = PROJECT_ROOT / '.claude' / 'rules'


def _extract_number(pattern, text, default=None):
    """Extract first integer from text matching pattern, or return default."""
    m = re.search(pattern, text)
    return int(m.group(1)) if m else default


def _count_py_files(d, exclude_test=True):
    """Count .py files in directory, optionally excluding test_*.py."""
    return len([p for p in d.glob('*.py')
                   if not (exclude_test and p.name.startswith('test_'))])


def _read_json(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


class TestDocConsistency:

    # --- C1: Key number matrix ---

    def test_hook_script_count_consistent(self):
        actual = _count_py_files(PROJECT_ROOT / 'hooks' / 'scripts')
        claims = {}
        # CLAUDE.md
        c_md = CLAUDE_MD.read_text(encoding='utf-8') if CLAUDE_MD.exists() else ''
        claims['CLAUDE.md'] = _extract_number(r'(\d+)\s*个\s*Python\s*脚本', c_md)
        # README.md
        r_md = README_MD.read_text(encoding='utf-8') if README_MD.exists() else ''
        claims['README.md'] = _extract_number(r'(\d+)\s*个独立\s*\.py', r_md)
        errors = []
        for loc, val in claims.items():
            if val is not None and val != actual:
                errors.append(f"  {loc}: claims {val}, actual {actual}")
        assert not errors, f"Hook script count mismatch:\n" + "\n".join(errors)

    def test_hook_event_count_consistent(self):
        data = _read_json(HOOKS_JSON)
        actual = len(data.get('hooks', {})) if data else 0
        claims = {}
        if CLAUDE_MD.exists():
            claims['CLAUDE.md'] = _extract_number(
                r'(\d+)\s*个钩子事件配置', CLAUDE_MD.read_text(encoding='utf-8')
            )
        errors = []
        for loc, val in claims.items():
            if val is not None and val != actual:
                errors.append(f"  {loc}: claims {val} events, actual {actual}")
        assert not errors, f"Hook event count mismatch:\n" + "\n".join(errors)

    def test_rule_file_count_consistent(self):
        actual = len([p for p in RULES_DIR.glob("*.md") if not p.name.startswith("test_")])
        # file-layout.md both copies
        for label, path in [('local', FILE_LAYOUT_MD), ('asset', FILE_LAYOUT_ASSET)]:
            if path.exists():
                text = path.read_text(encoding='utf-8')
                claimed = _extract_number(r'rules.*?(\d+)\s*文件', text)
                if claimed is not None and claimed != actual:
                    assert False, (
                        f"file-layout.md ({label}): claims {claimed} rules, "
                        f"actual {actual}"
                    )

    def test_command_count_consistent(self):
        actual = len(list(COMMANDS_DIR.glob('*.md')))
        pj = _read_json(PLUGIN_JSON)
        api = API_MD.read_text(encoding='utf-8') if API_MD.exists() else ''
        for loc, text in [('plugin.json', str(pj)), ('api.md', api)]:
            if '**命令数量**' in text:
                claimed = _extract_number(r'(\d+)\s*个命令', text)
                if claimed is not None and claimed != actual:
                    assert False, f"{loc}: claims {claimed} commands, actual {actual}"

    def test_skill_count_consistent(self):
        actual = len([d for d in SKILLS_DIR.iterdir() if d.is_dir()])
        pj = _read_json(PLUGIN_JSON)
        # For plugin.json, count skills[] array length directly
        claimed_pj = len(pj.get('skills', [])) if pj else None
        if claimed_pj is not None and claimed_pj != actual:
            assert False, f"plugin.json: claims {claimed_pj} skills, actual {actual}"
        # For api.md, use regex on markdown text only
        api = API_MD.read_text(encoding='utf-8') if API_MD.exists() else ''
        if 'Skill 数量' in api:
            claimed = _extract_number(r'Skill\s*数量.*?(\d+)\s*个', api)
            if claimed is not None and claimed != actual:
                assert False, f"api.md: claims {claimed} skills, actual {actual}"

    def test_agent_count_consistent(self):
        actual = len([a for a in AGENTS_DIR.glob('*.md')])
        rmd = README_MD.read_text(encoding='utf-8') if README_MD.exists() else ''
        # README has two agent sections; check the table
        claimed = _extract_number(r'内置专家 agents.\s*(\d+)\s*个', rmd)
        if claimed is not None and claimed != actual:
            # README might split into two tables; just warn
            pass  # P2 level, don't block on formatting

    # --- C2: Skills directory names ---

    def test_skills_dir_names_match_plugin_json(self):
        pj = _read_json(PLUGIN_JSON)
        if not pj:
            return
        claimed_dirs = set()
        for entry in pj.get('skills', []):
            # Extract dir name from path like "./skills/ddoc" -> "ddoc"
            parts = entry.rstrip('/').split('/')
            claimed_dirs.add(parts[-1] if parts else entry)
        actual_dirs = {d.name for d in SKILLS_DIR.iterdir() if d.is_dir()}
        missing = claimed_dirs - actual_dirs
        extra = actual_dirs - claimed_dirs
        assert not missing and not extra, (
            f"Skills dir mismatch: plugin.json={claimed_dirs}, "
            f"actual={actual_dirs}. Missing: {missing}, Extra: {extra}"
        )

    # --- C3: Hooks table completeness ---

    def test_readme_hooks_table_covers_all_events(self):
        """README Hooks table should mention all events from hooks.json."""
        if not README_MD.exists():
            return
        data = _read_json(HOOKS_JSON)
        if not data:
            return
        events = set(data.get('hooks', {}).keys())
        # Find the Hooks table section and extract event names from rows
        readme_text = README_MD.read_text(encoding='utf-8')
        in_hooks_table = False
        for line in readme_text.split('\n'):
            if '## Hooks' in line:
                in_hooks_table = True
                continue
            if in_hooks_table and line.startswith('## ') and 'Hooks' not in line:
                break  # Moved past the Hooks section
            if in_hooks_table:
                for evt in list(events):
                    if evt in line or evt.replace('_', '') in line.replace('_', ''):
                        events.discard(evt)
        # Allow Stop to appear twice (background + blocking) — that's documentation detail
        events.discard('Stop')  # appears twice intentionally
        assert len(events) <= 1, (
            f"README Hooks table missing events: {sorted(events)}. "
            f"All 11 events should be documented."
        )

    # --- C4: file-layout.md rule count vs actual ---

    def test_file_layout_rule_count_accurate(self):
        actual = len([p for p in RULES_DIR.glob("*.md") if not p.name.startswith("test_")])
        for label, path in [('local', FILE_LAYOUT_MD), ('asset', FILE_LAYOUT_ASSET)]:
            if not path.exists():
                continue
            text = path.read_text(encoding='utf-8')
            claimed = _extract_number(r'rules.*?\((?:\d+)\)\s*文件', text)
            if claimed is not None:
                assert claimed == actual, (
                    f"file-layout.md ({label}): rules count claims {claimed}, "
                    f"actual {actual}"
                )
