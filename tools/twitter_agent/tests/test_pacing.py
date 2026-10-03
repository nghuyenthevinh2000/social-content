"""Deterministic randomized-delay and browsing integration tests without sleeping."""

import unittest
from unittest.mock import Mock, patch

from tools.twitter_agent.models import AgentError
from tools.twitter_agent.pacing import ActionPacer, get_pacer
from tools.twitter_agent.posts import read_posts


class PacingTests(unittest.TestCase):
    def make_pacer(self):
        rng = Mock()
        rng.randint.return_value = 50
        rng.uniform.side_effect = lambda low, high: low
        sleep = Mock()
        return ActionPacer(sleep=sleep, rng=rng), sleep, rng

    def test_action_ranges(self):
        pacer, sleep, rng = self.make_pacer()
        for action, bounds in ActionPacer.DELAYS.items():
            pacer.wait(action)
            rng.uniform.assert_called_with(*bounds)
            sleep.assert_called_with(bounds[0])
        self.assertEqual(pacer.actions, 4)

    def test_break_after_random_action_budget_and_resample(self):
        for budget in (50, 100):
            with self.subTest(budget=budget):
                rng = Mock()
                rng.randint.side_effect = [budget, 75]
                rng.uniform.side_effect = lambda low, high: high
                sleep = Mock()
                pacer = ActionPacer(sleep=sleep, rng=rng)
                for _ in range(budget):
                    pacer.wait('scroll')
                self.assertEqual(sleep.call_count, budget)
                pacer.wait('search')
                self.assertEqual([c.args[0] for c in sleep.call_args_list[-2:]], [60.0, 10.0])
                self.assertEqual(pacer.actions, 1)
                self.assertEqual(pacer.break_after, 75)
                self.assertEqual([c.args for c in rng.randint.call_args_list], [(50, 100), (50, 100)])

    def test_invalid_action_does_not_sleep_or_count(self):
        pacer, sleep, _ = self.make_pacer()
        with self.assertRaises(KeyError):
            pacer.wait('invalid')
        sleep.assert_not_called()
        self.assertEqual(pacer.actions, 0)

    def test_default_pacer_is_shared(self):
        with patch('tools.twitter_agent.pacing._default_pacer', None):
            self.assertIs(get_pacer(), get_pacer())

    @patch('tools.twitter_agent.posts.selectors.detect_block', return_value=None)
    @patch('tools.twitter_agent.posts.get_pacer')
    def test_navigation_categories(self, get_pacer_mock, detect_block):
        cases = [('timeline', None, 'navigation'), ('thread', '123', 'navigation'),
                 ('search', '#AI', 'search'), ('search', 'AI', 'search'),
                 ('search', 'from:alice', 'profile')]
        for mode, value, action in cases:
            with self.subTest(mode=mode, value=value):
                page = Mock()
                page.url = 'https://x.com/home'
                page.evaluate.return_value = [{'id': '123'}]
                get_pacer_mock.return_value.wait.reset_mock()
                read_posts(page, mode, value, limit=1)
                get_pacer_mock.return_value.wait.assert_called_once_with(action)
                page.goto.assert_called_once()

    @patch('tools.twitter_agent.posts.selectors.detect_block', return_value=None)
    @patch('tools.twitter_agent.posts.get_pacer')
    def test_scroll_waits_excluded_from_active_timeout(self, get_pacer_mock, detect_block):
        page = Mock()
        page.url = 'https://x.com/home'
        page.evaluate.return_value = []
        get_pacer_mock.return_value.wait.return_value = 60.0
        # Start at 0; a 60-second pacing break occurs before the first scroll.
        with patch('tools.twitter_agent.posts.time.time', side_effect=[0, 0, 60]):
            result = read_posts(page, 'timeline', limit=1)
        self.assertEqual(result['scrolls'], 2)
        self.assertEqual(result['reason'], 'no_progress')
        self.assertEqual([c.args[0] for c in get_pacer_mock.return_value.wait.call_args_list],
                         ['navigation', 'scroll', 'scroll'])

    @patch('tools.twitter_agent.posts.get_pacer')
    def test_blocked_page_never_waits_or_navigates(self, get_pacer_mock):
        page = Mock()
        page.url = 'https://x.com/home'
        with patch('tools.twitter_agent.posts.selectors.detect_block',
                   return_value=AgentError('account_blocked', 'Blocked')):
            with self.assertRaises(AgentError):
                read_posts(page, 'search', '#AI')
        get_pacer_mock.assert_not_called()
        page.goto.assert_not_called()
