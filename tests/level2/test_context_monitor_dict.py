"""L2 tests for context_monitor.py — dict-mapped threshold actions + _cfg cache."""
import json
import os
import sys
import tempfile
import types
import unittest

# Load context_monitor source without triggering module-level sys.exit
_scripts_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'hooks', 'scripts')
cm = types.ModuleType('context_monitor')

with open(os.path.join(_scripts_dir, 'context_monitor.py')) as f:
    code = compile(f.read(), 'context_monitor.py', 'exec')
    _orig_exit = sys.exit
    sys.exit = lambda *a, **k: None
    try:
        exec(code, cm.__dict__)
    finally:
        sys.exit = _orig_exit


class TestCfgDefaults(unittest.TestCase):
    """Test _cfg() default values and caching."""

    def test_cfg_returns_defaults_when_no_settings_file(self):
        tmpdir = tempfile.mkdtemp()
        orig_settings = cm.SETTINGS
        cm.SETTINGS = os.path.join(tmpdir, 'nonexistent_dsettings.toml')
        try:
            result = cm._cfg()
            self.assertIn('warning', result)
            self.assertIn('critical', result)
            self.assertIn('delay', result)
            self.assertEqual(result['warning'], 30)
            self.assertEqual(result['critical'], 50)
            self.assertEqual(result['delay'], 10)
        finally:
            cm.SETTINGS = orig_settings
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cfg_reads_custom_values(self):
        tmpdir = tempfile.mkdtemp()
        settings_path = os.path.join(tmpdir, 'dsettings.toml')
        with open(settings_path, 'w') as f:
            f.write('ctxmon_warn_at = 20\n'
                    'ctxmon_checkpoint_at = 40\n'
                    'ctxmon_checkpoint_delay = 5\n')

        orig_settings = cm.SETTINGS
        cm.SETTINGS = settings_path
        try:
            result = cm._cfg()
            self.assertEqual(result['warning'], 20)
            self.assertEqual(result['critical'], 40)
            self.assertEqual(result['delay'], 5)
        finally:
            cm.SETTINGS = orig_settings
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestDictMappingStructure(unittest.TestCase):
    """Verify threshold action dict structure exists and covers expected levels."""

    def test_defaults_contain_all_three_thresholds(self):
        defaults = cm.DEFAULTS
        self.assertIn('warning', defaults)
        self.assertIn('critical', defaults)
        self.assertIn('delay', defaults)
        for k, v in defaults.items():
            self.assertIsInstance(v, int, f'{k} should be int, got {type(v)}')


class TestReadonlyToolSets(unittest.TestCase):
    """Verify RD_TOOLS and WR_TOOLS sets are non-empty and disjoint."""

    def test_rd_tools_nonempty(self):
        self.assertTrue(len(cm.RD_TOOLS) > 0)

    def test_wr_tools_nonempty(self):
        self.assertTrue(len(cm.WR_TOOLS) > 0)

    def test_sets_are_disjoint(self):
        overlap = cm.RD_TOOLS & cm.WR_TOOLS
        self.assertEqual(overlap, set(), f'RD and WR tools should be disjoint, got: {overlap}')


class TestTempDirCachePaths(unittest.TestCase):
    """Cache files go to tempdir (cross-platform), not to project directory."""

    def test_cache_path_uses_tempdir(self):
        cp = cm._cache_path('sess-123')
        temp_root = tempfile.gettempdir()
        self.assertTrue(cp.startswith(temp_root))
        self.assertTrue(cp.endswith('diwu_ctxmon_sess-123.json'))

    def test_save_cache_writes_to_tempdir_not_project_dir(self):
        sid = 'test-sess-x'
        project_root = tempfile.mkdtemp()
        try:
            cm._save_cache({'rd_count': 1, 'wr_count': 2}, sid, project_root)
            expected = cm._cache_path(sid)
            self.assertTrue(os.path.exists(expected))
            # 确认没有写到项目目录下
            project_cache = os.path.join(project_root, '.diwu')
            if os.path.exists(project_cache):
                caches = [f for f in os.listdir(project_cache) if f.startswith('.context_monitor')]
                self.assertEqual(caches, [], f'不应在项目目录生成缓存文件: {caches}')
        finally:
            import shutil
            shutil.rmtree(project_root, ignore_errors=True)

    def test_load_cache_returns_defaults_when_missing(self):
        sid = 'nonexistent-session'
        cache = cm._load_cache(sid)
        self.assertEqual(cache['rd_count'], 0)
        self.assertEqual(cache['wr_count'], 0)


if __name__ == '__main__':
    unittest.main()
