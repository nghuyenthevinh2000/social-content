"""Tests for supervisor review loop, human decisions, and submission boundaries."""

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tools.twitter_agent.models import AgentError, normalize_target
from tools.twitter_agent.store import Store
from tools.twitter_agent.supervisor import review_once, supervise


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store = Store(Path(self.temp_dir))
        self.page = MagicMock()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_reject_never_clicks(self):
        draft = self.store.enqueue(normalize_target('123'), 'Reviewed text')
        with patch('tools.twitter_agent.supervisor.prepare_reply', return_value={'target_id': '123'}), \
             patch('tools.twitter_agent.supervisor.submit_reply') as submit:
            handled = review_once(self.store, self.page, lambda review: 'reject')
        self.assertTrue(handled)
        submit.assert_not_called()
        self.assertEqual(self.store.get(draft['id'])['state'], 'rejected')

    def test_defer_returns_to_pending(self):
        draft = self.store.enqueue(normalize_target('123'), 'Reviewed text')
        with patch('tools.twitter_agent.supervisor.prepare_reply', return_value={'target_id': '123'}), \
             patch('tools.twitter_agent.supervisor.submit_reply') as submit:
            handled = review_once(self.store, self.page, lambda review: 'defer')
        self.assertTrue(handled)
        submit.assert_not_called()
        self.assertEqual(self.store.get(draft['id'])['state'], 'pending')

    def test_changed_text_requires_new_review(self):
        draft = self.store.enqueue(normalize_target('123'), 'Reviewed text')
        with patch('tools.twitter_agent.supervisor.prepare_reply', return_value={'target_id': '123'}), \
             patch('tools.twitter_agent.supervisor.inspect_reply', return_value='different_digest'), \
             patch('tools.twitter_agent.supervisor.submit_reply') as submit:
            handled = review_once(self.store, self.page, lambda review: 'approve')
        self.assertTrue(handled)
        submit.assert_not_called()
        self.assertEqual(self.store.get(draft['id'])['state'], 'pending')

    def test_approved_and_matching_calls_submit_and_finishes_submitted(self):
        draft = self.store.enqueue(normalize_target('123'), 'Reviewed text')
        with patch('tools.twitter_agent.supervisor.prepare_reply', return_value={'target_id': '123'}), \
             patch('tools.twitter_agent.supervisor.inspect_reply', return_value=draft['digest']), \
             patch('tools.twitter_agent.supervisor.submit_reply', return_value={'state': 'submitted', 'reply_id': '999'}) as submit:
            handled = review_once(self.store, self.page, lambda review: 'approve')
        self.assertTrue(handled)
        submit.assert_called_once()
        self.assertEqual(self.store.get(draft['id'])['state'], 'submitted')

    def test_submission_exception_results_in_uncertain_state(self):
        draft = self.store.enqueue(normalize_target('123'), 'Reviewed text')
        with patch('tools.twitter_agent.supervisor.prepare_reply', return_value={'target_id': '123'}), \
             patch('tools.twitter_agent.supervisor.inspect_reply', return_value=draft['digest']), \
             patch('tools.twitter_agent.supervisor.submit_reply', side_effect=RuntimeError('Network dropped')):
            handled = review_once(self.store, self.page, lambda review: 'approve')
        self.assertTrue(handled)
        self.assertEqual(self.store.get(draft['id'])['state'], 'uncertain')

    def test_preparation_failure_marks_draft_failed(self):
        draft = self.store.enqueue(normalize_target('123'), 'Reviewed text')
        with patch('tools.twitter_agent.supervisor.prepare_reply', side_effect=AgentError('target_not_found', 'Post not found')), \
             patch('tools.twitter_agent.supervisor.submit_reply') as submit:
            handled = review_once(self.store, self.page, lambda review: 'approve')
        self.assertTrue(handled)
        submit.assert_not_called()
        self.assertEqual(self.store.get(draft['id'])['state'], 'failed')

    def test_review_once_returns_false_when_queue_empty(self):
        handled = review_once(self.store, self.page, lambda review: 'approve')
        self.assertFalse(handled)

    def test_supervisor_hud_displays_strategy_metrics(self):
        self.store.add_watchlist('alice', 'Core target')
        draft = self.store.enqueue(normalize_target('123'), 'Test reply')
        captured_stderr = []
        with patch('tools.twitter_agent.supervisor.prepare_reply', return_value={'target_id': '123', 'target_author': '@alice', 'target_url': 'https://x.com/i/status/123'}), \
             patch('sys.stderr.write', side_effect=captured_stderr.append):
            # Test default prompt rendering
            from tools.twitter_agent.supervisor import _render_strategy_hud
            hud_text = _render_strategy_hud(self.store, {'target_author': '@alice', 'target_id': '123'})
            self.assertIn('WATCHLIST TARGET', hud_text)

    def test_supervisor_hud_deboost_warning_and_clean_state(self):
        from tools.twitter_agent.supervisor import _render_strategy_hud
        draft = self.store.enqueue(normalize_target('123'), 'Test reply')
        now = self.store.clock()

        # Burst count < 2: no deboost warning
        with self.store._transaction() as db:
            self.store._event(db, 'submission_started', draft['id'], {}, now - 200)
        hud_text = _render_strategy_hud(self.store, {'target_author': '@bob', 'target_id': '123'})
        self.assertNotIn('DEBOOST WARNING', hud_text)
        self.assertNotIn('WATCHLIST TARGET', hud_text)

        # Burst count >= 2: deboost warning present
        with self.store._transaction() as db:
            self.store._event(db, 'submission_started', draft['id'], {}, now - 100)
        hud_text = _render_strategy_hud(self.store, {'target_author': '@bob', 'target_id': '123'})
        self.assertIn('DEBOOST WARNING', hud_text)
        self.assertIn('[⚠️ DEBOOST WARNING: High burst frequency]', hud_text)



