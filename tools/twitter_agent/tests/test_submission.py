"""Offline one-shot reply submission and no-retry tests."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools.twitter_agent.models import AgentError, normalize_target
from tools.twitter_agent.store import Store
from tools.twitter_agent.submission import submit_draft


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name))
        self.draft = self.store.enqueue(normalize_target('123'), 'Hello')
        self.browser = Mock()
        self.prepare = patch('tools.twitter_agent.submission.prepare_reply').start()
        self.inspect = patch('tools.twitter_agent.submission.inspect_reply',
                             return_value=self.draft['digest']).start()
        self.submit = patch('tools.twitter_agent.submission.submit_reply',
                            return_value={'state': 'submitted', 'reply_id': '999'}).start()
        self.addCleanup(patch.stopall)

    def run_submission(self):
        return submit_draft(self.store, self.browser, self.draft['id'])

    def test_direct_submission_without_decision_callback(self):
        self.assertEqual(self.run_submission()['state'], 'submitted')
        self.submit.assert_called_once()

    def test_only_selected_draft_is_claimed(self):
        second = self.store.enqueue(normalize_target('456'), 'Second')
        self.inspect.return_value = second['digest']
        result = submit_draft(self.store, self.browser, second['id'])
        self.assertEqual(result['id'], second['id'])
        self.assertEqual(self.store.get(self.draft['id'])['state'], 'pending')

    def test_preparation_failure_does_not_click(self):
        self.prepare.side_effect = AgentError('target_not_found', 'Missing')
        with self.assertRaises(AgentError):
            self.run_submission()
        self.assertEqual(self.store.get(self.draft['id'])['state'], 'failed')
        self.submit.assert_not_called()

    def test_changed_composer_does_not_click(self):
        self.inspect.return_value = 'changed'
        with self.assertRaises(AgentError):
            self.run_submission()
        self.submit.assert_not_called()

    def test_uncertain_attempt_cannot_be_submitted_again(self):
        self.submit.side_effect = RuntimeError('Connection lost')
        self.assertEqual(self.run_submission()['state'], 'uncertain')
        with self.assertRaises(AgentError):
            self.run_submission()
        self.submit.assert_called_once()

    def test_paused_draft_remains_pending(self):
        self.store.set_paused(True)
        with self.assertRaises(AgentError):
            self.run_submission()
        self.assertEqual(self.store.get(self.draft['id'])['state'], 'pending')
        self.prepare.assert_not_called()

    def test_quota_failure_does_not_click(self):
        self.store.event('submission_started', None, {})
        with self.assertRaises(AgentError) as caught:
            self.run_submission()
        self.assertEqual(caught.exception.code, 'rate_limited')
        self.submit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
