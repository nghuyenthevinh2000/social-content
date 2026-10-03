"""Offline image-post confirmation, approval, and shared quota tests."""

from pathlib import Path
import tempfile
import unittest

from tools.twitter_agent.models import AgentError
from tools.twitter_agent.publish import publish, reserve_attempt, verify_response
from tools.twitter_agent.store import Store


class PublishTests(unittest.TestCase):
    def payload(self, text, media=None):
        return {'data': {'create_tweet': {'tweet_results': {'result': {
            'rest_id': '123', 'legacy': {'full_text': text, 'extended_entities': {
                'media': media if media is not None else [{'type': 'photo', 'url': 'https://t.co/photo'}],
            }},
        }}}}}

    def test_exact_text_and_appended_image_link(self):
        for returned in ('Hello 🤣', 'Hello 🤣 https://t.co/photo'):
            self.assertEqual(verify_response(self.payload(returned), 'Hello 🤣')['state'], 'submitted')

    def test_changed_text_or_missing_photo_is_uncertain(self):
        for payload in (self.payload('Different'), self.payload('Hello', []), {},
                        self.payload('Hello https://t.co/other')):
            with self.assertRaises(AgentError):
                verify_response(payload, 'Hello')

    def test_visibility_wrapper(self):
        payload = self.payload('Hello')
        result = payload['data']['create_tweet']['tweet_results']
        result['result'] = {'__typename': 'TweetWithVisibilityResults', 'tweet': result['result']}
        self.assertEqual(verify_response(payload, 'Hello')['image_count'], 1)

    def test_approval_required_before_browser_or_file_access(self):
        with self.assertRaises(AgentError) as caught:
            publish('Hello', Path('/does/not/exist'), None, '', 'alice')
        self.assertEqual(caught.exception.code, 'approval_required')

    def test_quota_reservation_requires_lock_and_honors_spacing(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(Path(root), clock=lambda: 10000)
            with self.assertRaises(AgentError):
                reserve_attempt(store, {})
            with store.submission_lock():
                reserve_attempt(store, {'text': 'Hello'})
                with self.assertRaises(AgentError) as caught:
                    reserve_attempt(store, {})
                self.assertEqual(caught.exception.code, 'rate_limited')
            events = store.status()['recent_events']
            self.assertEqual(sum(e['kind'] == 'submission_started' for e in events), 1)

    def test_paused_submissions_are_not_reserved(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(Path(root))
            store.set_paused(True)
            with store.submission_lock(), self.assertRaises(AgentError) as caught:
                reserve_attempt(store, {})
            self.assertEqual(caught.exception.code, 'paused')


if __name__ == '__main__':
    unittest.main()
