import copy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from tools.twitter_agent.models import AgentError
from tools.twitter_agent.report import select_candidates


def make_post(pid, timestamp, total, is_ad=False, score=0, **extra):
    return {
        'id': pid,
        'url': f'https://x.com/i/status/{pid}',
        'author': {'name': 'Test', 'handle': '@test'},
        'text': f'Evidence for {pid}',
        'timestamp': timestamp,
        'is_ad': is_ad,
        'score': score,
        'metrics': {
            'likes': total,
            'retweets': 0,
            'replies': 0,
            'views': 100,
            'total': total,
        },
        **extra,
    }


def make_obs(item, mode='top', observed_at='2026-09-30T12:01:00Z'):
    return {'post': item, 'mode': mode, 'observed_at': observed_at}


class SelectionTests(unittest.TestCase):
    def test_rank_after_time_filter_and_not_opportunity_score(self):
        end = int(datetime(2026, 9, 30, 12, tzinfo=timezone.utc).timestamp())
        start = end - 86400
        result = select_candidates([
            make_obs(make_post('1', '2026-09-30T11:00:00Z', 2, score=99)),
            make_obs(make_post('2', '2026-09-30T10:00:00Z', 200)),
            make_obs(make_post('3', '2026-09-30T12:00:00Z', 999)),  # end boundary: excluded
            make_obs(make_post('4', '2026-09-29T12:00:00Z', 100)),  # start boundary: included
        ], start=start, end=end, per_topic=2)

        self.assertEqual(result['selected_ids'], ['2', '4'])
        self.assertEqual(result['counts']['excluded_outside_window'], 1)
        self.assertEqual(result['counts']['selected'], 2)
        self.assertEqual(result['counts']['eligible'], 3)

    def test_exclusions_order_and_reasons(self):
        end = int(datetime(2026, 9, 30, 12, tzinfo=timezone.utc).timestamp())
        start = end - 86400

        observations = [
            # Ad takes precedence
            make_obs(make_post('ad1', '2026-09-30T10:00:00Z', 500, is_ad=True)),
            # Invalid timestamps
            make_obs(make_post('no_ts', None, 100)),
            make_obs(make_post('bad_ts', 'invalid-date', 100)),
            make_obs(make_post('naive_ts', '2026-09-30T10:00:00', 100)),  # naive
            # Outside interval
            make_obs(make_post('too_old', '2026-09-29T11:59:59Z', 100)),
            make_obs(make_post('too_new', '2026-09-30T12:00:00Z', 100)),
            # Eligible
            make_obs(make_post('good1', '2026-09-30T10:00:00Z', 50)),
        ]
        result = select_candidates(observations, start=start, end=end, per_topic=5)
        counts = result['counts']
        self.assertEqual(counts['excluded_ads'], 1)
        self.assertEqual(counts['excluded_invalid_timestamp'], 3)
        self.assertEqual(counts['excluded_outside_window'], 2)
        self.assertEqual(counts['eligible'], 1)
        self.assertEqual(counts['selected'], 1)
        self.assertEqual(result['selected_ids'], ['good1'])

        cand_map = {c['id']: c for c in result['candidates']}
        self.assertEqual(cand_map['ad1']['exclusion_reason'], 'ad')
        self.assertEqual(cand_map['no_ts']['exclusion_reason'], 'invalid_timestamp')
        self.assertEqual(cand_map['bad_ts']['exclusion_reason'], 'invalid_timestamp')
        self.assertEqual(cand_map['naive_ts']['exclusion_reason'], 'invalid_timestamp')
        self.assertEqual(cand_map['too_old']['exclusion_reason'], 'outside_window')
        self.assertEqual(cand_map['too_new']['exclusion_reason'], 'outside_window')
        self.assertIsNone(cand_map['good1']['exclusion_reason'])

    def test_duplicate_handling_replaces_post_and_preserves_modes(self):
        end = int(datetime(2026, 9, 30, 12, tzinfo=timezone.utc).timestamp())
        start = end - 86400

        first = make_post('p1', '2026-09-30T10:00:00Z', 10)
        second = make_post('p1', '2026-09-30T10:00:00Z', 20)  # updated metrics
        obs = [
            make_obs(first, mode='top', observed_at='2026-09-30T12:01:00Z'),
            make_obs(second, mode='latest', observed_at='2026-09-30T12:02:00Z'),
        ]
        result = select_candidates(obs, start=start, end=end, per_topic=5)
        self.assertEqual(result['counts']['collected'], 2)
        self.assertEqual(result['counts']['unique'], 1)
        self.assertEqual(result['counts']['duplicates'], 1)
        self.assertEqual(len(result['candidates']), 1)
        cand = result['candidates'][0]
        # Should keep second observation metrics, not sum them
        self.assertEqual(cand['metrics']['total'], 20)
        self.assertEqual(cand['observed_at'], '2026-09-30T12:02:00Z')
        self.assertEqual(cand['source_modes'], ['top', 'latest'])

    def test_ties_and_invariants(self):
        end = int(datetime(2026, 9, 30, 12, tzinfo=timezone.utc).timestamp())
        start = end - 86400

        # Same engagement (total=50) -> tiebreak by newer timestamp, then ascending ID
        p_old = make_post('a1', '2026-09-30T09:00:00Z', 50)
        p_new_b = make_post('b1', '2026-09-30T10:00:00Z', 50)
        p_new_a = make_post('a2', '2026-09-30T10:00:00Z', 50)

        obs = [make_obs(p_old), make_obs(p_new_b), make_obs(p_new_a)]
        obs_copy = copy.deepcopy(obs)

        result = select_candidates(obs, start=start, end=end, per_topic=2)
        # a2 and b1 have newer timestamp than a1.
        # Between a2 and b1 (same ts, same total), ascending ID: a2 then b1.
        self.assertEqual(result['selected_ids'], ['a2', 'b1'])

        # Verify input non-mutation
        self.assertEqual(obs, obs_copy)

        # Invariant checks:
        c = result['counts']
        self.assertEqual(c['collected'] - c['unique'], c['duplicates'])
        self.assertEqual(
            c['unique'],
            c['eligible'] + c['excluded_ads'] + c['excluded_invalid_timestamp'] + c['excluded_outside_window']
        )


class CollectionTests(unittest.TestCase):
    @patch('tools.twitter_agent.report.read_posts')
    def test_budget_and_empty_topic_coverage(self, reader):
        from tools.twitter_agent.report import collect_report
        reader.return_value = {'posts': [], 'reason': 'no_progress', 'scrolls': 3}
        topics = [
            {'id': 'ai', 'name': 'AI', 'search_keywords': ['AI']},
            {'id': 'zk', 'name': 'ZK', 'search_keywords': ['ZK']}
        ]
        result = collect_report(
            object(), topics, topics_file='topics.json',
            start=100, end=86500, per_topic=2, candidate_limit=5
        )
        self.assertEqual([t['id'] for t in result['topics']], ['ai', 'zk'])
        self.assertEqual([c.kwargs['limit'] for c in reader.call_args_list], [3, 2, 3, 2])
        self.assertEqual(
            [c.kwargs['search_mode'] for c in reader.call_args_list],
            ['top', 'latest', 'top', 'latest']
        )
        self.assertTrue(all(t['status'] == 'empty' for t in result['topics']))
        self.assertFalse(result['partial'])
        self.assertEqual(result['summary']['by_status']['empty'], 2)

    @patch('tools.twitter_agent.report.read_posts')
    def test_two_topic_membership_and_selection(self, reader):
        from tools.twitter_agent.report import collect_report
        # Shared post 'shared_1' returned for both topic 'ai' and topic 'agent'
        p_shared = make_post('shared_1', '2026-09-30T10:00:00Z', 100)
        p_ai = make_post('ai_only', '2026-09-30T10:00:00Z', 50)
        p_agent = make_post('agent_only', '2026-09-30T10:00:00Z', 70)

        reader.side_effect = [
            {'posts': [p_shared, p_ai], 'reason': 'limit_reached', 'scrolls': 1},  # ai top
            {'posts': [], 'reason': 'no_progress', 'scrolls': 1},                  # ai latest
            {'posts': [p_shared, p_agent], 'reason': 'limit_reached', 'scrolls': 1}, # agent top
            {'posts': [], 'reason': 'no_progress', 'scrolls': 1},                  # agent latest
        ]
        topics = [
            {'id': 'ai', 'name': 'AI', 'search_keywords': ['AI']},
            {'id': 'agent', 'name': 'Agent', 'search_keywords': ['Agent']}
        ]
        result = collect_report(
            object(), topics, topics_file='topics.json',
            start=0, end=2000000000, per_topic=5, candidate_limit=10
        )
        self.assertEqual(result['topics'][0]['selected_ids'], ['shared_1', 'ai_only'])
        self.assertEqual(result['topics'][1]['selected_ids'], ['shared_1', 'agent_only'])
        self.assertEqual(result['summary']['selected_topic_entries'], 4)
        self.assertEqual(result['summary']['unique_selected_posts'], 3)
        self.assertTrue(all(t['status'] == 'ok' for t in result['topics']))

    @patch('tools.twitter_agent.report.read_posts')
    def test_recoverable_error_followed_by_success(self, reader):
        from tools.twitter_agent.report import collect_report
        from tools.twitter_agent.models import AgentError
        reader.side_effect = [
            AgentError('dom_timeout', 'DOM timed out'),
            {'posts': [make_post('p1', '2026-09-30T10:00:00Z', 50)], 'reason': 'limit_reached', 'scrolls': 1}
        ]
        topics = [{'id': 'ai', 'name': 'AI', 'search_keywords': ['AI']}]
        result = collect_report(
            object(), topics, topics_file='topics.json',
            start=0, end=2000000000, per_topic=5, candidate_limit=10
        )
        self.assertEqual(result['topics'][0]['status'], 'partial')
        self.assertTrue(result['partial'])
        self.assertEqual(result['topics'][0]['selected_ids'], ['p1'])

    @patch('tools.twitter_agent.report.read_posts')
    def test_playwright_error_normalized(self, reader):
        from tools.twitter_agent.report import collect_report
        from playwright.sync_api import Error as PlaywrightError
        reader.side_effect = PlaywrightError('Navigation failed')
        topics = [{'id': 'ai', 'name': 'AI', 'search_keywords': ['AI']}]
        result = collect_report(
            object(), topics, topics_file='topics.json',
            start=0, end=2000000000, per_topic=5, candidate_limit=10
        )
        self.assertEqual(result['topics'][0]['status'], 'error')
        self.assertTrue(result['partial'])
        s0_err = result['topics'][0]['searches'][0]['error']
        self.assertEqual(s0_err['code'], 'browser_navigation_failed')
        self.assertIn('Navigation failed', s0_err['message'])

    @patch('tools.twitter_agent.report.read_posts')
    def test_timeout_overrides_status_to_partial(self, reader):
        from tools.twitter_agent.report import collect_report
        reader.return_value = {
            'posts': [make_post('p1', '2026-09-30T10:00:00Z', 50)],
            'reason': 'timeout',
            'scrolls': 2
        }
        topics = [{'id': 'ai', 'name': 'AI', 'search_keywords': ['AI']}]
        result = collect_report(
            object(), topics, topics_file='topics.json',
            start=0, end=2000000000, per_topic=5, candidate_limit=10
        )
        self.assertEqual(result['topics'][0]['status'], 'partial')
        self.assertTrue(result['partial'])

    @patch('tools.twitter_agent.report.read_posts')
    def test_fatal_error_stops_and_skips_remaining(self, reader):
        from tools.twitter_agent.report import collect_report
        from tools.twitter_agent.models import AgentError
        reader.side_effect = [
            {'posts': [make_post('p1', '2026-09-30T10:00:00Z', 50)], 'reason': 'limit_reached', 'scrolls': 1},
            AgentError('account_blocked', 'Account was blocked'),
        ]
        topics = [
            {'id': 't1', 'name': 'T1', 'search_keywords': ['T1']},
            {'id': 't2', 'name': 'T2', 'search_keywords': ['T2']}
        ]
        result = collect_report(
            object(), topics, topics_file='topics.json',
            start=0, end=2000000000, per_topic=5, candidate_limit=10
        )
        self.assertTrue(result['partial'])
        # t1 succeeded first search, failed second with fatal
        self.assertEqual(result['topics'][0]['status'], 'partial')
        self.assertEqual(result['topics'][0]['selected_ids'], ['p1'])
        # t2 was never run -> skipped
        self.assertEqual(result['topics'][1]['status'], 'skipped')
        for s in result['topics'][1]['searches']:
            self.assertEqual(s['reason'], 'skipped')
            self.assertEqual(s['collected'], 0)
            self.assertIsNone(s['observed_at'])
            self.assertIsNone(s['error'])

    @patch('tools.twitter_agent.report.read_posts')
    def test_fatal_error_on_last_topic(self, reader):
        from tools.twitter_agent.report import collect_report
        from tools.twitter_agent.models import AgentError
        reader.side_effect = AgentError('not_authenticated', 'Not authenticated')
        topics = [{'id': 'last', 'name': 'Last', 'search_keywords': ['Last']}]
        result = collect_report(
            object(), topics, topics_file='topics.json',
            start=0, end=2000000000, per_topic=5, candidate_limit=10
        )
        self.assertEqual(result['topics'][0]['status'], 'error')
        self.assertTrue(result['partial'])
        self.assertEqual(result['topics'][0]['searches'][1]['reason'], 'skipped')

    @patch('tools.twitter_agent.report.read_posts')
    def test_unexpected_runtime_error_propagates(self, reader):
        from tools.twitter_agent.report import collect_report
        reader.side_effect = RuntimeError('Disk explosion')
        topics = [{'id': 't1', 'name': 'T1', 'search_keywords': ['T1']}]
        with self.assertRaises(RuntimeError):
            collect_report(
                object(), topics, topics_file='topics.json',
                start=0, end=2000000000, per_topic=5, candidate_limit=10
            )


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        import json
        import tempfile
        from tools.twitter_agent.report import collect_report, write_report

        # Build a rich multi-status fixture
        p_selected = make_post(
            '1001', '2026-09-30T10:00:00Z', 150,
            text="<script>alert('xss')</script> # NotAHeading `code` [link](http://bad.com)"
        )
        p_unselected = make_post(
            '1002', '2026-09-30T09:00:00Z', 5,
            text="Should not be selected"
        )
        topics = [
            {'id': 't_ok', 'name': 'Topic OK', 'search_keywords': ['ok']},
            {'id': 't_empty', 'name': 'Topic Empty', 'search_keywords': ['empty']},
            {'id': 't_partial', 'name': 'Topic Partial', 'search_keywords': ['partial']},
            {'id': 't_skipped', 'name': 'Topic Skipped', 'search_keywords': ['skipped']},
        ]
        with patch('tools.twitter_agent.report.read_posts') as reader:
            reader.side_effect = [
                # t_ok: top, latest
                {'posts': [p_selected, p_unselected], 'reason': 'limit_reached', 'scrolls': 1},
                {'posts': [], 'reason': 'no_progress', 'scrolls': 1},
                # t_empty: top, latest
                {'posts': [], 'reason': 'no_progress', 'scrolls': 1},
                {'posts': [], 'reason': 'no_progress', 'scrolls': 1},
                # t_partial: top fails, latest with fatal
                AgentError('dom_timeout', 'Top failed'),
                AgentError('account_blocked', 'Fatal block'),
            ]
            start_ts = int(datetime(2026, 9, 30, 0, tzinfo=timezone.utc).timestamp())
            end_ts = int(datetime(2026, 10, 1, 0, tzinfo=timezone.utc).timestamp())
            self.report = collect_report(
                object(), topics, topics_file='topics.json',
                start=start_ts, end=end_ts, per_topic=1, candidate_limit=5
            )

    def test_two_writes_preserve_both_runs(self):
        import json
        import re
        import tempfile
        from pathlib import Path
        from tools.twitter_agent.report import write_report

        with tempfile.TemporaryDirectory() as directory:
            first = write_report(self.report, Path(directory))
            second = write_report(self.report, Path(directory))
            self.assertNotEqual(first['run_dir'], second['run_dir'])
            first_name = Path(first['run_dir']).name
            second_name = Path(second['run_dir']).name
            self.assertTrue(re.match(r'^report-\d{8}-\d{6}$', first_name), f"Expected report-YYYYMMDD-HHMMSS, got {first_name}")
            self.assertTrue(re.match(r'^report-\d{8}-\d{6}-1$', second_name), f"Expected collision suffix, got {second_name}")
            for paths in (first, second):
                self.assertNotIn('report_markdown', paths)
                self.assertFalse((Path(paths['run_dir']) / 'report.md').exists())
                saved = json.loads(Path(paths['evidence_json']).read_text(encoding='utf-8'))
                self.assertEqual(saved, self.report)

    def test_write_report_failure_on_file_output_dir(self):
        import tempfile
        from pathlib import Path
        from tools.twitter_agent.models import AgentError
        from tools.twitter_agent.report import write_report

        with tempfile.TemporaryDirectory() as directory:
            file_as_dir = Path(directory) / 'not_a_dir.txt'
            file_as_dir.write_text('hello', encoding='utf-8')
            with self.assertRaises(AgentError) as raised:
                write_report(self.report, file_as_dir)
            self.assertEqual(raised.exception.code, 'report_write_failed')

    def test_write_report_failure_on_atomic_replace_cleans_up(self):
        import tempfile
        from pathlib import Path
        from tools.twitter_agent.models import AgentError
        from tools.twitter_agent.report import write_report

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(Path, 'replace', side_effect=[OSError('Disk error')]):
                with self.assertRaises(AgentError) as raised:
                    write_report(self.report, Path(directory))
                self.assertEqual(raised.exception.code, 'report_write_failed')


if __name__ == '__main__':
    unittest.main()


