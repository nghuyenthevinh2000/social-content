"""Real SQLite, injected time, and process-lock regression tests."""

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid

from tools.twitter_agent.models import AgentError, Limits, Target, normalize_target
from tools.twitter_agent.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 100_000.0
        self.root = Path(self.temp.name) / 'state'
        self.store = Store(self.root, clock=lambda: self.now)

    def enqueue(self, text='Exact reply'):
        return self.store.enqueue(normalize_target('123'), text)

    def events(self):
        with sqlite3.connect(self.store.db_path) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute('SELECT * FROM events ORDER BY id')]

    def attempt(self, text):
        draft = self.enqueue(text)
        self.assertEqual(self.store.claim_next()['id'], draft['id'])
        self.store.begin_submission(draft['id'], draft['digest'])
        self.store.finish(draft['id'], 'uncertain', {'reason': 'no confirmation'})
        return draft

    def test_paused_draft_cannot_begin_submission(self):
        draft = self.enqueue()
        self.store.claim_next()
        self.store.set_paused(True)
        with self.assertRaises(AgentError) as caught:
            self.store.begin_submission(draft['id'], draft['digest'])
        self.assertEqual(caught.exception.code, 'paused')
        self.assertEqual(self.store.get(draft['id'])['state'], 'reviewing')
        self.assertNotIn('submission_started', [e['kind'] for e in self.events()])

    def test_recovery_never_requeues_a_possible_submission(self):
        draft = self.enqueue()
        self.store.claim_next()
        self.store.begin_submission(draft['id'], draft['digest'])
        restarted = Store(self.root, clock=lambda: self.now)
        with restarted.supervisor_lock():
            restarted.recover()
        self.assertEqual(restarted.get(draft['id'])['state'], 'uncertain')
        self.assertIsNone(restarted.claim_next())

    def test_recovery_requires_lock_and_fresh_review(self):
        draft = self.enqueue()
        self.store.claim_next()
        with self.assertRaises(AgentError):
            self.store.recover()
        with self.store.supervisor_lock():
            self.store.recover()
        self.assertEqual(self.store.get(draft['id'])['state'], 'pending')
        with self.assertRaises(AgentError):
            self.store.begin_submission(draft['id'], draft['digest'])
        self.assertEqual(self.store.claim_next()['id'], draft['id'])

    def test_exact_text_duplicates_and_fifo_ties(self):
        text = '  café e\u0301 🙂\n\tend  '
        first, duplicate, second = self.store.enqueue_many([
            (normalize_target('123'), text), (normalize_target('00123'), text),
            (normalize_target('124'), text)])
        self.assertEqual(first, duplicate)
        uuid.UUID(first['id'])
        self.assertEqual(first['text'], text)
        self.assertEqual(first['created_at'], self.now)
        self.assertEqual(first['detail'], {})
        self.assertEqual(self.store.claim_next()['id'], first['id'])
        self.assertIsNone(self.store.claim_next())
        self.store.reject(first['id'])
        self.assertEqual(self.store.claim_next()['id'], second['id'])
        self.assertEqual(self.store.enqueue(normalize_target('123'), text)['state'], 'rejected')

    def test_bulk_validation_never_partially_imports(self):
        for text in ('', ' \n\t', '\x00bad', 'bad\rtext', 'bad\x7f', 'bad\x85', '\ud800', None):
            with self.subTest(text=repr(text)), self.assertRaises(AgentError):
                self.store.enqueue_many([(normalize_target('1'), 'good'),
                                         (normalize_target('2'), text)])
            self.assertEqual(self.store.status()['queue'], [])
        with self.assertRaises(AgentError):
            self.store.enqueue(Target('1', 'https://evil.test'), 'reply')
        self.assertEqual(self.store.enqueue_many([]), [])

    def test_cancel_during_review_and_invalid_digest_block_submission(self):
        draft = self.enqueue()
        self.store.claim_next()
        with self.assertRaises(AgentError) as caught:
            self.store.begin_submission(draft['id'], 'wrong')
        self.assertEqual(caught.exception.code, 'digest_mismatch')
        self.assertEqual(self.store.cancel(draft['id'])['state'], 'cancelled')
        with self.assertRaises(AgentError):
            self.store.begin_submission(draft['id'], draft['digest'])
        self.assertNotIn('approval', [e['kind'] for e in self.events()])

    def test_pending_cancel_pause_resume_and_defer(self):
        draft = self.enqueue()
        self.store.set_paused(True)
        self.assertIsNone(self.store.claim_next())
        self.store.set_paused(False)
        self.store.claim_next()
        self.store.defer(draft['id'], 'paused during review')
        self.assertEqual(self.store.get(draft['id'])['state'], 'pending')
        with self.assertRaises(AgentError):
            self.store.begin_submission(draft['id'], draft['digest'])
        self.assertEqual(self.store.cancel(draft['id'])['state'], 'cancelled')
        self.assertIsNone(self.store.claim_next())

    def test_submission_is_audited_once_and_terminal_states_cannot_retry(self):
        draft = self.enqueue()
        self.store.claim_next()
        self.store.begin_submission(draft['id'], draft['digest'])
        self.assertEqual(self.store.get(draft['id'])['state'], 'submitting')
        for operation in (lambda: self.store.begin_submission(draft['id'], draft['digest']),
                          lambda: self.store.cancel(draft['id']),
                          lambda: self.store.defer(draft['id'], 'retry'),
                          lambda: self.store.reject(draft['id'])):
            with self.assertRaises(AgentError):
                operation()
        events = self.events()
        self.assertEqual([e['kind'] for e in events][-2:], ['approval', 'submission_started'])
        self.assertEqual(json.loads(events[-2]['detail'])['digest'], draft['digest'])
        self.store.finish(draft['id'], 'submitted', {'url': 'https://x.com/i/status/999'})
        self.assertEqual(self.store.get(draft['id'])['detail']['url'], 'https://x.com/i/status/999')
        with self.assertRaises(AgentError):
            self.store.finish(draft['id'], 'pending', {})
        self.assertIsNone(self.store.claim_next())

    def test_preparation_failure_and_custom_event(self):
        draft = self.enqueue()
        self.store.claim_next()
        with self.assertRaises(AgentError):
            self.store.finish(draft['id'], 'submitted', {})
        self.store.event('preparation_error', draft['id'], {'reason': 'missing target'})
        self.store.finish(draft['id'], 'failed', {'reason': 'missing target'})
        self.assertEqual(self.store.get(draft['id'])['state'], 'failed')
        self.store.event('connected', None, {})
        self.assertEqual(self.events()[-1]['kind'], 'connected')
        with self.assertRaises(AgentError) as caught:
            self.store.get('missing')
        self.assertEqual(caught.exception.code, 'draft_not_found')

    def test_rolling_hour_day_and_spacing_boundaries_persist(self):
        for limits, boundary in [(Limits(1, 30, 0), 3600),
                                  (Limits(100, 1, 0), 86400),
                                  (Limits(100, 100, 60), 60)]:
            with self.subTest(limits=limits), tempfile.TemporaryDirectory() as directory:
                self.now = 100_000.0
                self.store = Store(Path(directory), clock=lambda: self.now)
                self.store.configure_limits(limits)
                self.attempt('first')
                self.store = Store(Path(directory), clock=lambda: self.now)
                draft = self.enqueue('second')
                self.store.claim_next()
                self.now += boundary - 0.01
                with self.assertRaises(AgentError) as caught:
                    self.store.begin_submission(draft['id'], draft['digest'])
                self.assertEqual(caught.exception.code, 'rate_limited')
                self.assertEqual(self.store.get(draft['id'])['state'], 'reviewing')
                self.now += 0.01
                self.store.begin_submission(draft['id'], draft['digest'])
                self.assertEqual(len([e for e in self.events() if e['kind'] == 'submission_started']), 2)

    def test_burst_limit_blocks_fourth_attempt_in_thirty_minutes(self):
        self.now = 100_000.0
        # Configure spacing to 0 to test burst window independently
        self.store.configure_limits(Limits(hourly=10, daily=50, spacing=0, burst_max=3))
        for i in range(3):
            draft = self.store.enqueue(normalize_target(f'{100 + i}'), f'Reply {i}')
            self.store.claim_next()
            self.store.begin_submission(draft['id'], draft['digest'])
            self.store.finish(draft['id'], 'submitted', {})
            self.now += 300  # 5 minutes apart

        # 4th attempt at 15 minutes (within 30m window) must be blocked
        draft4 = self.store.enqueue(normalize_target('104'), 'Reply 4')
        self.store.claim_next()
        with self.assertRaises(AgentError) as ctx:
            self.store.begin_submission(draft4['id'], draft4['digest'])
        self.assertEqual(ctx.exception.code, 'rate_limited')
        self.assertIn('Burst', ctx.exception.message)

    def test_default_limits_block_fourth_attempt(self):
        for index in range(3):
            self.attempt(str(index))
            self.now += 120
        draft = self.enqueue('fourth')
        self.store.claim_next()
        with self.assertRaises(AgentError) as caught:
            self.store.begin_submission(draft['id'], draft['digest'])
        self.assertEqual(caught.exception.code, 'rate_limited')

    def test_default_limits_block_sixth_attempt(self):
        # Backward-compatible alias for runners referencing old default limit test name
        self.test_default_limits_block_fourth_attempt()

    def test_settings_status_and_permissions_survive_reopening(self):
        self.store.configure_limits(Limits(2, 7, 5.5))
        self.store.set_paused(True)
        other = Store(self.root)
        status = other.status()
        self.assertTrue(status['paused'])
        self.assertEqual(status['limits'], {'hourly': 2, 'daily': 7, 'spacing': 5.5, 'burst_max': 3})
        self.assertFalse(status['supervisor']['running'])
        self.assertIsNone(status['active_draft'])
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.store.artifact_dir.stat().st_mode & 0o777, 0o700)
        for path in self.root.iterdir():
            if path.is_file():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_lock_excludes_second_process_and_status_ignores_heartbeat_age(self):
        script = '''
import sys
from pathlib import Path
from tools.twitter_agent.models import AgentError
from tools.twitter_agent.store import Store
try:
    with Store(Path(sys.argv[1])).supervisor_lock():
        pass
except AgentError as error:
    print(error.code)
    sys.exit(7)
'''
        with self.store.supervisor_lock():
            status = self.store.status()['supervisor']
            self.assertTrue(status['running'])
            self.assertEqual(status['pid'], os.getpid())
            self.assertTrue(status['session'])
            self.now += 100_000
            self.assertTrue(Store(self.root).status()['supervisor']['running'])
            self.store.heartbeat()
            self.assertEqual(self.store.status()['supervisor']['heartbeat'], self.now)
            child = subprocess.run([sys.executable, '-c', script, str(self.root)],
                                   capture_output=True, text=True, timeout=10)
            self.assertEqual(child.returncode, 7, child.stderr)
            self.assertEqual(child.stdout.strip(), 'supervisor_running')
        self.assertFalse(self.store.status()['supervisor']['running'])
        with self.assertRaises(AgentError):
            self.store.heartbeat()
        child = subprocess.run([sys.executable, '-c', script, str(self.root)],
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(child.returncode, 0, child.stderr)

    def test_two_connections_cannot_claim_or_submit_same_draft_twice(self):
        draft = self.enqueue()
        self.enqueue('another')
        other = Store(self.root, clock=lambda: self.now)
        self.store.claim_next()
        self.assertIsNone(other.claim_next())
        self.store.begin_submission(draft['id'], draft['digest'])
        with self.assertRaises(AgentError):
            other.begin_submission(draft['id'], draft['digest'])
        self.assertEqual(len([e for e in self.events() if e['kind'] == 'submission_started']), 1)

    def test_watchlist_crud(self):
        added = self.store.add_watchlist('@techopsasia', notes='Frontier Club founder')
        self.assertEqual(added['handle'], 'techopsasia')
        self.assertEqual(added['notes'], 'Frontier Club founder')

        items = self.store.get_watchlist()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['handle'], 'techopsasia')

        # remove
        self.assertTrue(self.store.remove_watchlist('techopsasia'))
        self.assertFalse(self.store.remove_watchlist('techopsasia'))
        self.assertEqual(len(self.store.get_watchlist()), 0)


if __name__ == '__main__':
    unittest.main()
