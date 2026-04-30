"""L2 tests for stop_decision.py — continuous_mode decision tree."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'hooks', 'scripts'))
from stop_decision import decide, format_task, hook_session_id
import tempfile as _tmpmod

_TEST_CWD = None


def _get_test_cwd():
    global _TEST_CWD
    if _TEST_CWD is None:
        _TEST_CWD = _tmpmod.mkdtemp()
    return _TEST_CWD


class TestFormatTask(unittest.TestCase):
    """Test format_task helper."""

    def test_format_contains_task_info(self):
        t = {'id': 5, 'title': 'Do X', 'description': 'desc',
             'acceptance': ['G W T'], 'steps': ['s1']}
        result = format_task('prefix:', t)
        self.assertIn('Task#5', result)
        self.assertIn('Do X', result)
        self.assertIn('desc', result)

    def test_format_contains_acceptance_and_steps(self):
        t = {'id': 1, 'title': 'T', 'description': '',
             'acceptance': ['Given A When B Then C'],
             'steps': ['step one']}
        result = format_task('go:', t)
        self.assertIn('Given A When B Then C', result)
        self.assertIn('step one', result)


class TestHookSessionId(unittest.TestCase):
    """Stop hook session id normalization."""

    def test_prefers_session_id(self):
        event = {"session_id": "snake", "sessionId": "camel"}
        self.assertEqual(hook_session_id(event), "snake")

    def test_accepts_sessionId(self):
        event = {"sessionId": "camel-only"}
        self.assertEqual(hook_session_id(event), "camel-only")


class TestDecideInProgress(unittest.TestCase):
    """Test decide() when InProgress task exists."""

    def test_inprogress_returns_continue(self):
        tasks = [{'id': 1, 'title': 'Active', 'status': 'InProgress',
                  'description': '', 'acceptance': [], 'steps': []}]
        settings = {'continuous_mode': True}
        runtime_state = {
            'version': 1,
            'task_sessions': {
                '1': {'session_id': 'session-a', 'started_at': '2026-04-30T12:00:00Z'}
            },
            'dloop': None,
        }
        should_continue, output = decide(
            tasks, settings, {}, '.diwu/dtask.json', _get_test_cwd(), [], None,
            runtime_state=runtime_state, session_id='session-a'
        )
        self.assertTrue(should_continue)
        self.assertEqual(output.get('decision'), 'block')
        self.assertIn('Active', output.get('reason', ''))

    def test_inprogress_without_owner_returns_invalid(self):
        tasks = [{'id': 1, 'title': 'Active', 'status': 'InProgress',
                  'description': '', 'acceptance': [], 'steps': []}]
        should_continue, output = decide(
            tasks, {'continuous_mode': True}, {}, '.diwu/dtask.json', _get_test_cwd(), [], None,
            runtime_state={'version': 1, 'task_sessions': {}, 'dloop': None}, session_id='session-a'
        )
        self.assertFalse(should_continue)
        self.assertEqual(output.get('decision'), 'missing_owner')


class TestDecideInReview(unittest.TestCase):
    """Test decide() when only InReview tasks exist."""

    def test_inreview_within_limit_advances(self):
        """Default mode: InReview + InSpec but no InProgress -> allow stop."""
        tasks = [{'id': 1, 'status': 'InReview', 'title': 'R',
                  'description': '', 'acceptance': [], 'steps': []},
                 {'id': 2, 'status': 'InSpec', 'title': 'Next',
                  'description': '', 'acceptance': [], 'steps': [], 'blocked_by': []}]
        settings = {'continuous_mode': True, 'review_limit': 5}
        data = {'review_used': 0}
        # New behavior: no dloop-state -> default mode -> allow stop
        should_continue, output = decide(tasks, settings, data, '.diwu/t.json', _get_test_cwd(), [], None)
        self.assertFalse(should_continue)

    def test_inreview_at_limit_stops(self):
        tasks = [{'id': 1, 'status': 'InReview', 'title': 'R',
                  'description': '', 'acceptance': [], 'steps': []}]
        settings = {'continuous_mode': True, 'review_limit': 5}
        data = {'review_used': 5}  # at limit
        # Patch notify to avoid /dev/tty OSError in test env
        import stop_decision
        _orig_notify = stop_decision.notify
        stop_decision.notify = lambda msg: None
        try:
            should_continue, output = decide(tasks, settings, data, '.diwu/t.json', _get_test_cwd(), [], None)
        finally:
            stop_decision.notify = _orig_notify
        self.assertFalse(should_continue)


class TestDecideInSpec(unittest.TestCase):
    """Test decide() when InSpec tasks available."""

    def test_inspec_auto_advances(self):
        """Default mode: InSpec but no InProgress -> allow stop (no auto-continue)."""
        tasks = [{'id': 3, 'status': 'InSpec', 'title': 'Ready',
                  'description': '', 'acceptance': [], 'steps': [], 'blocked_by': []}]
        settings = {'continuous_mode': True}
        # New behavior: no dloop-state -> default mode -> allows stop
        should_continue, output = decide(tasks, settings, {}, '.diwu/t.json', _get_test_cwd(), [], None)
        self.assertFalse(should_continue)
        self.assertEqual(output, {})


class TestDecideEmpty(unittest.TestCase):
    """Test decide() when no active tasks."""

    def test_no_tasks_returns_stop(self):
        settings = {'continuous_mode': True}
        should_continue, output = decide([], settings, {}, '.diwu/t.json', _get_test_cwd(), [], None)
        self.assertFalse(should_continue)
        self.assertEqual(output, {})


class TestDecideContinuousModeOff(unittest.TestCase):
    """Test decide() with continuous_mode=False."""

    def test_inspec_continuous_off_returns_summary(self):
        """Default mode: InSpec + no InProgress -> allow stop (no auto-continue)."""
        tasks = [{'id': 1, 'status': 'InSpec', 'title': 'T',
                  'description': '', 'acceptance': [], 'steps': [], 'blocked_by': []},
                 {'id': 99, 'status': 'Done', 'title': 'Done1',
                  'description': '', 'acceptance': [], 'steps': []}]
        settings = {'continuous_mode': False}
        # New behavior: default mode allows stop when no InProgress task
        should_continue, output = decide(tasks, settings, {}, '.diwu/t.json', _get_test_cwd(), [], None)
        self.assertFalse(should_continue)
        self.assertEqual(output, {})  # No block decision = allow stop


if __name__ == '__main__':
    unittest.main()
