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


class TestCheckpointFunction(unittest.TestCase):
    """Test checkpoint() writes session file correctly (no task association)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        os.makedirs('.diwu/recording', exist_ok=True)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_checkpoint_creates_checkpoint_file(self):
        cm.checkpoint(cwd='.')
        checkpoints = [f for f in os.listdir('.diwu/recording')
                       if f.startswith('checkpoint-') and f.endswith('.md')]
        self.assertTrue(len(checkpoints) > 0)
        with open(os.path.join('.diwu/recording', checkpoints[0])) as f:
            content = f.read()
        self.assertIn('[Auto Checkpoint]', content)

    def test_checkpoint_no_task_reference(self):
        """checkpoint 内容不包含 Task# 引用。"""
        cm.checkpoint(cwd='.')
        checkpoints = [f for f in os.listdir('.diwu/recording')
                       if f.startswith('checkpoint-') and f.endswith('.md')]
        self.assertTrue(len(checkpoints) > 0)
        with open(os.path.join('.diwu/recording', checkpoints[0])) as f:
            content = f.read()
        self.assertNotIn('Task#', content)

    def test_checkpoint_always_succeeds(self):
        """checkpoint() always creates file regardless of task state."""
        cm.checkpoint(cwd='.')
        checkpoints = [f for f in os.listdir('.diwu/recording')
                       if f.startswith('checkpoint-') and f.endswith('.md')]
        self.assertTrue(len(checkpoints) > 0)


class TestReadonlyToolSets(unittest.TestCase):
    """Verify RD_TOOLS and WR_TOOLS sets are non-empty and disjoint."""

    def test_rd_tools_nonempty(self):
        self.assertTrue(len(cm.RD_TOOLS) > 0)

    def test_wr_tools_nonempty(self):
        self.assertTrue(len(cm.WR_TOOLS) > 0)

    def test_sets_are_disjoint(self):
        overlap = cm.RD_TOOLS & cm.WR_TOOLS
        self.assertEqual(overlap, set(), f'RD and WR tools should be disjoint, got: {overlap}')


class TestCwdScopedPaths(unittest.TestCase):
    def test_cache_path_roots_at_project_cwd(self):
        tmpdir = tempfile.mkdtemp()
        try:
            cp = cm._cache_path('sess-123', tmpdir)
            self.assertTrue(cp.startswith(tmpdir))
            self.assertTrue(cp.endswith('.diwu/.context_monitor_cache_sess-123.json'))
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_save_cache_does_not_write_under_process_cwd(self):
        project_root = tempfile.mkdtemp()
        rogue_cwd = tempfile.mkdtemp()
        orig_cwd = os.getcwd()
        try:
            os.chdir(rogue_cwd)
            cm._save_cache({'rd_count': 1, 'wr_count': 2, 'checkpoint_written': False}, 'sess-x', project_root)
            expected = os.path.join(project_root, '.diwu', '.context_monitor_cache_sess-x.json')
            misplaced = os.path.join(rogue_cwd, '.diwu', '.context_monitor_cache_sess-x.json')
            self.assertTrue(os.path.exists(expected))
            self.assertFalse(os.path.exists(misplaced))
        finally:
            os.chdir(orig_cwd)
            import shutil
            shutil.rmtree(project_root, ignore_errors=True)
            shutil.rmtree(rogue_cwd, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
