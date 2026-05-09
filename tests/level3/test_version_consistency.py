"""Version number consistency checker.

Validates that version numbers are synchronized across all locations
that define the plugin version. Truth source: .claude-plugin/plugin.json.

Level 3 (consistency) — reads file contents, no subprocess needed.
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

PLUGIN_JSON = PROJECT_ROOT / '.claude-plugin' / 'plugin.json'
MARKETPLACE_JSON = PROJECT_ROOT / '.claude-plugin' / 'marketplace.json'
INSTALL_SH = PROJECT_ROOT / 'install.sh'


def _read_plugin_version():
    with open(PLUGIN_JSON) as f:
        return json.load(f)['version']


def _read_marketplace_versions():
    with open(MARKETPLACE_JSON) as f:
        d = json.load(f)
    plugins = d.get('plugins', [])
    return {
        'marketplace.top': d.get('version', ''),
        'marketplace.plugins[0]': plugins[0].get('version', '') if plugins else '',
    }


def _read_install_sh_version():
    text = INSTALL_SH.read_text()
    m = re.search(r'version:\s*"([^"]+)"', text)
    return m.group(1) if m else ''


class TestVersionConsistency:

    def test_plugin_json_has_version(self):
        ver = _read_plugin_version()
        assert ver, "plugin.json 缺少 version 字段"
        assert re.match(r'\d+\.\d+\.\d+', ver), f"version 格式异常: {ver}"

    def test_marketplace_top_level_matches(self):
        expected = _read_plugin_version()
        actual = _read_marketplace_versions()['marketplace.top']
        assert actual == expected, (
            f"marketplace.json 顶层 version 不一致:"
            f" 期望={expected}, 实际={actual}"
        )

    def test_marketplace_plugins_entry_matches(self):
        expected = _read_plugin_version()
        actual = _read_marketplace_versions()['marketplace.plugins[0]']
        assert actual == expected, (
            f"marketplace.json plugins[0].version 不一致:"
            f" 期望={expected}, 实际={actual}"
        )

    def test_install_sh_matches(self):
        expected = _read_plugin_version()
        actual = _read_install_sh_version()
        assert actual == expected, (
            f"install.sh 内嵌 version 不一致:"
            f" 期望={expected}, 实际={actual}"
        )
