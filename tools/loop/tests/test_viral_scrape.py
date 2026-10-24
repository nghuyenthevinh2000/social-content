"""Offline tests for the tested-target viral scraper gate and captures."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from test_hashtag_generate import write_campaign
from tools.loop.viral_analyzer import hashtag_common as hc
from tools.loop.viral_analyzer import viral_scrape as vs


def add_evaluation(root, platform, key, decision, *, kind='hashtag',
                   endpoint=None, evaluation_id='eval-1'):
    endpoint = endpoint or ('/v1/instagram/search/hashtag' if kind == 'hashtag'
                            else '/v1/tiktok/search/keyword')
    hc.append_evaluation(
        root, platform, hc.history_key(kind, key),
        {'evaluation_id': evaluation_id, 'probe_id': f'probe-{key}', 'phase': 'probe',
         'checked_at': '2026-10-24T00:00:00Z', 'application': 'paper packaging',
         'market_language': 'vi', 'source_endpoint': endpoint,
         'ranking_filter': 'reels', 'hits': 2, 'misses': 1, 'unknowns': 0,
         'unique_reviewed': 3, 'decision': decision, 'query_kind': kind},
        original_term=('#' + key) if kind == 'hashtag' else key,
        normalized_term=key)


def schema_file(root, endpoints):
    path = Path(root) / 'schema.json'
    path.write_text(json.dumps({'provider': 'scrapecreators', 'currency': 'USD',
                                'endpoints': endpoints}))
    return path


def endpoint(platform='instagram', kind='hashtag', price='0.0019'):
    return {
        'platform': platform, 'kind': kind,
        'endpoint': (f'/v1/{platform}/search/{kind}'),
        'method_field': 'hashtag' if kind == 'hashtag' else 'query',
        'price_usd': price, 'fixed': {'limit': 10}, 'max_results': 10,
        'ranking_filter': 'reels',
    }


def scrape_args(root, schema, **overrides):
    values = {'project': str(root), 'run': 'run-1', 'schema': str(schema),
              'platform': None, 'limit': None, 'ceiling': None,
              'execute': False, 'resume': False, 'run_func': None}
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeProvider:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, call, key):
        self.calls.append((call, key))
        response = self.responses.pop(0)
        if isinstance(response, dict) and 'returncode' in response:
            return response
        return {'returncode': 0, 'stdout': json.dumps(response), 'stderr': ''}


def instagram_response(*items):
    return {'output': {'reels': list(items)}}


def tiktok_response(*items):
    return {'output': {'search_item_list': [{'aweme_info': item} for item in items]}}


class ViralScrapeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = write_campaign(Path(self.temp.name) / 'test-campaign')
        self.schema = schema_file(self.root, [endpoint()])

    def tearDown(self):
        self.temp.cleanup()

    def test_gate_blocks_untested_targets(self):
        add_evaluation(self.root, 'instagram', 'thiepcuoi', 'mixed')
        result, _ = vs.scrape(scrape_args(self.root, self.schema))
        self.assertFalse(result['ok'])
        self.assertTrue(any('no tested hashtag targets' in error
                            for error in result['errors']))

    def test_preview_is_read_only(self):
        add_evaluation(self.root, 'instagram', 'thiepcuoi', 'promising')
        result, _ = vs.scrape(scrape_args(self.root, self.schema))
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['mode'], 'preview')
        self.assertEqual(len(result['calls']), 1)
        self.assertFalse((hc.artifact_directory(self.root, 'run-1') / 'expansion').exists())

    def test_execute_writes_captures_and_keeps_missing_metrics_null(self):
        add_evaluation(self.root, 'instagram', 'thiepcuoi', 'promising')
        fake = FakeProvider(instagram_response(
            {'id': 'r1', 'url': 'https://www.instagram.com/reel/r1/',
             'caption': 'thiep cuoi', 'play_count': 100, 'like_count': 7,
             'comment_count': 2, 'user': {'username': 'creator-a'}},
            {'id': 'r2', 'caption': 'no metrics', 'user': {'username': 'creator-b'}},
        ))
        result, _ = vs.scrape(scrape_args(self.root, self.schema, execute=True,
                                          ceiling='1.00', run_func=fake))
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['candidates'], 2)
        document = json.loads((self.root / result['candidates_path']).read_text())
        first, second = document['candidates']
        self.assertEqual(first['metrics'], {'views': 100, 'likes': 7,
                                            'comments': 2, 'shares': None})
        self.assertIsNone(second['metrics']['views'])
        self.assertEqual(first['gate_decision'], 'promising')
        calls = hc.artifact_directory(self.root, 'run-1') / 'expansion/calls'
        for suffix in ('request.json', 'response.json', 'status.json', 'items.json'):
            self.assertTrue((calls / f'scrape-instagram-hashtag-01.{suffix}').is_file())

    def test_budget_below_total_dispatches_nothing(self):
        add_evaluation(self.root, 'instagram', 'thiepcuoi', 'promising')
        fake = FakeProvider(instagram_response({'id': 'r1', 'caption': 'x'}))
        result, _ = vs.scrape(scrape_args(self.root, self.schema, execute=True,
                                          ceiling='0.001', run_func=fake))
        self.assertFalse(result['ok'])
        self.assertEqual(fake.calls, [])

    def test_retry_is_noop_and_unconfirmed_needs_resume(self):
        add_evaluation(self.root, 'instagram', 'thiepcuoi', 'promising')
        fake = FakeProvider(instagram_response({'id': 'r1', 'caption': 'x'}))
        first, _ = vs.scrape(scrape_args(self.root, self.schema, execute=True,
                                         ceiling='1.00', run_func=fake))
        self.assertTrue(first['ok'], first)
        second, _ = vs.scrape(scrape_args(self.root, self.schema, execute=True,
                                          ceiling='1.00', run_func=fake))
        self.assertEqual(second['outcomes'][0]['action'], 'skipped_completed')
        self.assertEqual(len(fake.calls), 1)

        failed = FakeProvider({'returncode': 1, 'stdout': '', 'stderr': 'boom'})
        run = 'retry-run'
        result, _ = vs.scrape(scrape_args(self.root, self.schema, run=run,
                                          execute=True, ceiling='1.00',
                                          run_func=failed))
        self.assertEqual(result['outcomes'][0]['outcome'], 'provider_error')
        blocked, _ = vs.scrape(scrape_args(self.root, self.schema, run=run,
                                           execute=True, ceiling='1.00',
                                           run_func=failed))
        self.assertEqual(blocked['outcomes'][0]['action'], 'needs_reconciliation')
        success = FakeProvider(instagram_response({'id': 'r1', 'caption': 'x'}))
        resumed, _ = vs.scrape(scrape_args(self.root, self.schema, run=run,
                                           execute=True, ceiling='1.00',
                                           resume=True, run_func=success))
        self.assertTrue(resumed['ok'], resumed)
        self.assertEqual(success.calls[0][1], failed.calls[0][1])

    def test_hashtag_and_keyword_use_separate_endpoints(self):
        add_evaluation(self.root, 'instagram', 'thiepcuoi', 'promising')
        add_evaluation(self.root, 'tiktok', 'in ấn thiệp cưới', 'limited_expand',
                       kind='keyword', evaluation_id='eval-tt-1')
        schema = schema_file(self.root, [
            endpoint('instagram', 'hashtag'),
            endpoint('tiktok', 'keyword', price='0.0020'),
        ])
        fake = FakeProvider(
            instagram_response({'id': 'r1', 'caption': 'ig'}),
            tiktok_response({'aweme_id': 'tt1', 'desc': 'tt',
                             'author': {'unique_id': 'ttuser'},
                             'statistics': {'play_count': 50, 'digg_count': 3,
                                            'comment_count': 1, 'share_count': 2}}),
        )
        result, _ = vs.scrape(scrape_args(self.root, schema, execute=True,
                                          ceiling='1.00', run_func=fake))
        self.assertTrue(result['ok'], result)
        calls = {call[0]['query_kind']: call for call in fake.calls}
        self.assertEqual(calls['hashtag'][0]['endpoint'], '/v1/instagram/search/hashtag')
        self.assertEqual(calls['keyword'][0]['endpoint'], '/v1/tiktok/search/keyword')
        document = json.loads((self.root / result['candidates_path']).read_text())
        tiktok = next(item for item in document['candidates']
                      if item['platform'] == 'tiktok')
        self.assertEqual(tiktok['metrics'], {'views': 50, 'likes': 3,
                                             'comments': 1, 'shares': 2})
        self.assertEqual(tiktok['url'], 'https://www.tiktok.com/@ttuser/video/tt1')

    def test_missing_schema_endpoint_blocks(self):
        add_evaluation(self.root, 'tiktok', 'in ấn', 'promising', kind='keyword')
        result, _ = vs.scrape(scrape_args(self.root, self.schema))
        self.assertFalse(result['ok'])
        self.assertTrue(any('no schema endpoint' in error for error in result['errors']))

    def test_blocked_run_context_blocks(self):
        add_evaluation(self.root, 'instagram', 'thiepcuoi', 'promising')
        run_dir = self.root / 'sources/viral/run-1'
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / 'context.json').write_text(json.dumps({'collection_blocked': True}))
        result, _ = vs.scrape(scrape_args(self.root, self.schema))
        self.assertFalse(result['ok'])
        self.assertTrue(any('blocked' in error for error in result['errors']))

    def test_legacy_integer_history_version_fails(self):
        path = self.root / hc.HISTORY_RELATIVE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'schema_version': 1, 'campaign': self.root.name,
                                    'platforms': {}}))
        result, _ = vs.scrape(scrape_args(self.root, self.schema))
        self.assertFalse(result['ok'])
        self.assertTrue(any('schema_version' in error for error in result['errors']))


if __name__ == '__main__':
    unittest.main()
