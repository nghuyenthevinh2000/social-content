"""Offline tests for hashtag probe planning, collection, review and history."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from tools.loop.viral_analyzer import hashtag_common as hc
from tools.loop.viral_analyzer import hashtag_generate as hg
from tools.loop.viral_analyzer import hashtag_verify as hv
from test_hashtag_generate import (build_args, candidate, response_for,
                                   write_campaign)


def write_schema(root, kinds=('hashtag',)):
    endpoints = []
    for kind in kinds:
        field = 'hashtag' if kind == 'hashtag' else 'query'
        path = '/v1/instagram/search/hashtag' if kind == 'hashtag' else '/v1/instagram/search/keyword'
        endpoints.append({
            'platform': 'instagram', 'kind': kind, 'endpoint': path,
            'method_field': field, 'price_usd': '0.0019',
            'fixed': {'limit': 3}, 'max_results': 3, 'ranking_filter': 'reels',
        })
    path = Path(root) / 'schema.json'
    path.write_text(json.dumps({'provider': 'scrapecreators', 'currency': 'USD',
                                'endpoints': endpoints}))
    return path


def prepare(root, run, candidates, platform='instagram', market_language='vi'):
    hg.build_prompt(build_args(root, run=run, platform=platform,
                               market_language=market_language, max_candidates=6))
    response = Path(root) / f'response-{run}.json'
    response.write_text(json.dumps(response_for(root, run, candidates)))
    result, _ = hg.import_response(SimpleNamespace(project=str(root), run=run,
                                                   response=str(response)))
    assert result['ok'], result


def plan(root, run, schema, ceiling=None):
    result, _ = hv.plan_probes(SimpleNamespace(
        project=str(root), run=run, schema=str(schema),
        max_calls=20, ceiling=ceiling))
    return result


def collect(root, run, fake, ceiling='1.00', resume=False, execute=True):
    result, _ = hv.collect_probes(SimpleNamespace(
        project=str(root), run=run, plan=None, execute=execute,
        ceiling=ceiling, resume=resume, run_func=fake))
    return result


def item(index, creator=None, caption=None):
    return {
        'id': f'video-{index}', 'url': f'https://www.instagram.com/reel/video-{index}/',
        'caption': caption or f'caption {index}',
        'owner': {'username': creator or f'creator-{index}'},
    }


def provider_response(items, charge='0.0019'):
    return {'run_id': 'provider-run-1', 'run_url': 'https://app.glasser.ai/runs/1',
            'charge_usd': charge, 'data': items}


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


def failure(returncode, stderr):
    return {'returncode': returncode, 'stdout': '', 'stderr': stderr}


def review_document(root, run, phase='probe', labels=None):
    context = json.loads((root / 'sources/viral' / run / 'context.json').read_text())
    plan_doc = json.loads((root / 'sources/viral' / run / 'plan.json').read_text())
    evaluations = []
    for call in plan_doc['calls']:
        samples = json.loads((root / 'sources/viral' / run / 'calls'
                              / f"{call['call_id']}.samples.json").read_text())
        chosen = labels or ['direct_application', 'direct_application', 'adjacent_process']
        evaluations.append({
            'call_id': call['call_id'],
            'reason': 'sample-level reason',
            'samples': [{
                'sample_id': sample['sample_id'],
                'label': chosen[index % len(chosen)],
                'reason': 'observed evidence supports this label',
                'evidence': [sample.get('url') or 'caption quote'],
                'observed': {'application': 'paper packaging', 'language': 'vi',
                             'tag_present': True},
            } for index, sample in enumerate(samples['reviewed'])],
        })
    return {
        'schema_version': 1, 'campaign': context['campaign'], 'run_id': run,
        'phase': phase, 'reviewer': 'test-agent', 'reviewer_type': 'agent',
        'checked_at': '2026-10-24T05:00:00Z', 'prompt_version': hc.PROMPT_VERSION,
        'model': 'test-model', 'evaluations': evaluations,
    }


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = write_campaign(Path(self.temp.name) / 'test-campaign')
        self.run = 'run-1'
        prepare(self.root, self.run, [candidate()])
        self.schema = write_schema(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def review(self, document, **overrides):
        path = Path(self.temp.name) / 'review.json'
        path.write_text(json.dumps(document))
        values = {'project': str(self.root), 'run': self.run, 'review': str(path),
                  'plan': None, 'correction': False, 'human_corrected': False}
        values.update(overrides)
        result, _ = hv.record_review(SimpleNamespace(**values))
        return result

    def test_plan_separates_hashtag_and_keyword_fields(self):
        run = 'mixed-run'
        prepare(self.root, run, [candidate(id='c1', kind='hashtag', text='#thiepcuoi'),
                                 candidate(id='c2', kind='keyword',
                                           text='in ấn thiệp cưới')])
        schema = write_schema(self.root, kinds=('hashtag', 'keyword'))
        result = plan(self.root, run, schema)
        self.assertTrue(result['ok'], result)
        document = json.loads((self.root / result['plan_path']).read_text())
        by_kind = {call['kind']: call for call in document['calls']}
        self.assertEqual(by_kind['hashtag']['request'], {'limit': 3, 'hashtag': 'thiepcuoi'})
        self.assertEqual(by_kind['keyword']['request'],
                         {'limit': 3, 'query': 'in ấn thiệp cưới'})
        self.assertNotEqual(by_kind['hashtag']['endpoint'], by_kind['keyword']['endpoint'])

    def test_plan_blocks_on_missing_context(self):
        run = 'blocked-run'
        (self.root / 'product-marketing.json').write_text('{}')
        hg.build_prompt(build_args(self.root, run=run))
        response = Path(self.root) / 'blocked.json'
        response.write_text(json.dumps(response_for(self.root, run, [candidate()])))
        imported, _ = hg.import_response(SimpleNamespace(project=str(self.root), run=run,
                                                         response=str(response)))
        self.assertTrue(imported['ok'], imported)
        result = plan(self.root, run, self.schema)
        self.assertFalse(result['ok'])
        self.assertTrue(any('blocked' in error for error in result['errors']))

    def test_plan_rejects_ceiling_overflow(self):
        result = plan(self.root, self.run, self.schema, ceiling='0.001')
        self.assertFalse(result['ok'])
        self.assertTrue(any('ceiling' in error for error in result['errors']))

    def test_dry_run_does_not_dispatch_or_write(self):
        self.assertTrue(plan(self.root, self.run, self.schema)['ok'])

        def explode(call, key):
            raise AssertionError('dry-run must not dispatch')

        result = collect(self.root, self.run, explode, execute=False)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['calls'][0]['action'], 'would_run')
        self.assertFalse((self.root / 'sources/viral' / self.run
                          / 'calls').exists())

    def test_budget_stops_before_dispatch(self):
        self.assertTrue(plan(self.root, self.run, self.schema)['ok'])
        fake = FakeProvider(provider_response([item(1), item(2), item(3)]))
        result = collect(self.root, self.run, fake, ceiling='0.001')
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['outcomes'][0]['outcome'], 'budget_exceeded')
        self.assertEqual(fake.calls, [])
        self.assertFalse((self.root / 'sources/viral' / self.run
                          / 'calls/call-instagram-hashtag-01.status.json').exists())

    def test_collect_keeps_first_three_unique_and_retains_skips(self):
        self.assertTrue(plan(self.root, self.run, self.schema)['ok'])
        duplicate = item(1)
        inaccessible = {'caption': None, 'is_available': False}
        fake = FakeProvider(provider_response([
            item(1), duplicate, inaccessible, item(2), item(3), item(4)]))
        result = collect(self.root, self.run, fake)
        self.assertEqual(result['outcomes'][0]['outcome'], 'success', result)
        samples = json.loads((self.root / 'sources/viral' / self.run / 'calls'
                              / 'call-instagram-hashtag-01.samples.json').read_text())
        self.assertEqual([entry['video_id'] for entry in samples['reviewed']],
                         ['video-1', 'video-2', 'video-3'])
        reasons = [entry['reason'] for entry in samples['skipped']]
        self.assertIn('duplicate', reasons)
        self.assertIn('inaccessible', reasons)
        status = json.loads((self.root / 'sources/viral' / self.run / 'calls'
                             / 'call-instagram-hashtag-01.status.json').read_text())
        self.assertEqual(status['charge_usd'], '0.0019')
        self.assertTrue(status['idempotency_key'])

    def test_provider_failures_are_distinct_and_do_not_create_samples(self):
        cases = {
            'not-found': (failure(1, '404 not found'), 'not_found'),
            'auth': (failure(1, '401 unauthorized'), 'auth_failed'),
            'unsupported': (failure(1, 'unsupported endpoint'), 'unsupported'),
            'empty': ({'returncode': 0, 'stdout': '{}', 'stderr': ''}, 'empty_response'),
            'inaccessible': ({'returncode': 0, 'stderr': '',
                              'stdout': json.dumps({'data': [
                                  {'caption': None, 'is_available': False}]})},
                             'inaccessible'),
            'error': (failure(1, 'boom'), 'provider_error'),
        }
        for run, (response, expected) in cases.items():
            prepare(self.root, run, [candidate()])
            self.assertTrue(plan(self.root, run, self.schema)['ok'], run)
            fake = FakeProvider(response)
            result = collect(self.root, run, fake)
            self.assertEqual(result['outcomes'][0]['outcome'], expected, run)
            self.assertFalse((self.root / 'sources/viral' / run / 'calls'
                              / 'call-instagram-hashtag-01.samples.json').exists(), run)

    def test_successful_retry_is_a_noop(self):
        self.assertTrue(plan(self.root, self.run, self.schema)['ok'])
        fake = FakeProvider(provider_response([item(1), item(2), item(3)]))
        self.assertEqual(collect(self.root, self.run, fake)['outcomes'][0]['outcome'], 'success')
        second = collect(self.root, self.run, fake)
        self.assertEqual(second['outcomes'][0]['action'], 'skipped_completed')
        self.assertEqual(len(fake.calls), 1)

    def test_ambiguous_retry_needs_resume_and_reuses_key(self):
        self.assertTrue(plan(self.root, self.run, self.schema)['ok'])
        first = FakeProvider(failure(1, 'boom'))
        collect(self.root, self.run, first)
        status_path = (self.root / 'sources/viral' / self.run / 'calls'
                       / 'call-instagram-hashtag-01.status.json')
        first_key = json.loads(status_path.read_text())['idempotency_key']
        second = FakeProvider(provider_response([item(1), item(2), item(3)]))
        blocked = collect(self.root, self.run, second)
        self.assertEqual(blocked['outcomes'][0]['action'], 'needs_reconciliation')
        self.assertEqual(second.calls, [])
        resumed = collect(self.root, self.run, second, resume=True)
        self.assertEqual(resumed['outcomes'][0]['outcome'], 'success')
        self.assertEqual(second.calls[0][1], first_key)
        self.assertEqual(json.loads(status_path.read_text())['attempts'], 2)

    def test_review_counts_decision_history_and_correction(self):
        self.assertTrue(plan(self.root, self.run, self.schema)['ok'])
        fake = FakeProvider(provider_response([item(1, creator='a'), item(2, creator='b'),
                                               item(3, creator='c')]))
        collect(self.root, self.run, fake)
        document = review_document(self.root, self.run)
        result = self.review(document)
        self.assertTrue(result['ok'], result)
        history_path = self.root / hc.HISTORY_RELATIVE
        history = json.loads(history_path.read_text())
        evaluation = history['platforms']['instagram']['thiepcuoi']['evaluations'][0]
        self.assertEqual((evaluation['hits'], evaluation['misses'], evaluation['unknowns']),
                         (2, 1, 0))
        self.assertEqual(evaluation['decision'], 'promising')
        self.assertEqual(evaluation['unique_reviewed'], 3)
        self.assertEqual(evaluation['collection_status'], 'complete')
        self.assertEqual(evaluation['query_kind'], 'hashtag')
        self.assertEqual([row['label'] for row in evaluation['sample_labels']],
                         ['direct_application', 'direct_application', 'adjacent_process'])
        self.assertTrue(evaluation['sample_labels'][0]['url'].startswith('https://'))

        retry = self.review(document)
        self.assertEqual(retry['merges'][0]['status'], 'noop')

        corrected = review_document(self.root, self.run,
                                    labels=['direct_application'] * 3)
        correction = self.review(corrected, correction=True)
        self.assertTrue(correction['ok'], correction)
        evaluations = json.loads(history_path.read_text())['platforms']['instagram']['thiepcuoi']['evaluations']
        self.assertEqual(len(evaluations), 2)
        self.assertEqual(evaluations[1]['supersedes'], evaluations[0]['evaluation_id'])
        self.assertEqual(evaluations[1]['hits'], 3)

        repeat = self.review(corrected)
        self.assertTrue(repeat['ok'], repeat)
        self.assertEqual(repeat['merges'][0]['status'], 'noop')

        conflict = self.review(review_document(
            self.root, self.run, labels=['adjacent_process'] * 3))
        self.assertFalse(conflict['ok'])
        self.assertTrue(any('correction' in error for error in conflict['errors']))

    def test_unknown_labels_produce_insufficient_evidence(self):
        run = 'unknown-run'
        prepare(self.root, run, [candidate()])
        self.assertTrue(plan(self.root, run, self.schema)['ok'])
        collect(self.root, run, FakeProvider(provider_response(
            [item(1), item(2), item(3)])))
        document = review_document(self.root, run,
                                   labels=['insufficient_evidence'] * 3)
        result = self.review(document, run=run)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['records'][0]['decision'], 'insufficient_evidence')
        self.assertEqual(result['records'][0]['unknowns'], 3)

    def test_two_samples_cannot_be_promising(self):
        run = 'short-run'
        prepare(self.root, run, [candidate()])
        self.assertTrue(plan(self.root, run, self.schema)['ok'])
        collect(self.root, run, FakeProvider(provider_response([item(1), item(2)])))
        document = review_document(self.root, run)
        result = self.review(document, run=run)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['records'][0]['decision'], 'insufficient_evidence')
        self.assertEqual(result['records'][0]['collection_status'], 'incomplete')

    def test_review_rejects_missing_samples_without_history_write(self):
        self.assertTrue(plan(self.root, self.run, self.schema)['ok'])
        collect(self.root, self.run, FakeProvider(provider_response(
            [item(1), item(2), item(3)])))
        document = review_document(self.root, self.run)
        document['evaluations'][0]['samples'].pop()
        result = self.review(document)
        self.assertFalse(result['ok'])
        self.assertFalse((self.root / hc.HISTORY_RELATIVE).exists())

    def test_keyword_and_hashtag_history_identity_stay_separate(self):
        run = 'tiktok-run'
        prepare(self.root, run, [candidate(id='c1', kind='hashtag', text='#thiepcuoi'),
                                 candidate(id='c2', kind='keyword',
                                           text='in ấn thiệp cưới')],
                platform='tiktok')
        schema = write_schema(self.root, kinds=('hashtag', 'keyword'))
        document = json.loads(schema.read_text())
        for endpoint in document['endpoints']:
            endpoint['platform'] = 'tiktok'
        schema.write_text(json.dumps(document))
        self.assertTrue(plan(self.root, run, schema)['ok'])
        fake = FakeProvider(provider_response([item(1), item(2), item(3)]),
                            provider_response([item(4), item(5), item(6)]))
        self.assertEqual([row['outcome'] for row in collect(self.root, run, fake)['outcomes']],
                         ['success', 'success'])
        result = self.review(review_document(self.root, run), run=run)
        self.assertTrue(result['ok'], result)
        platforms = json.loads((self.root / hc.HISTORY_RELATIVE).read_text())['platforms']['tiktok']
        self.assertIn('thiepcuoi', platforms)
        self.assertIn('keyword:in ấn thiệp cưới', platforms)
        self.assertEqual(platforms['thiepcuoi']['query_kind'], 'hashtag')
        self.assertEqual(platforms['keyword:in ấn thiệp cưới']['query_kind'], 'keyword')

    def test_history_preserves_legacy_entries_and_explicit_version(self):
        history_path = self.root / hc.HISTORY_RELATIVE
        history_path.parent.mkdir(parents=True, exist_ok=True)
        legacy = {
            'schema_version': '1.0.0', 'campaign': self.root.name,
            'updated_at': '2026-10-24T00:00:00Z', 'platforms': {
                'instagram': {'oldtag': {
                    'original_tag': '#oldtag', 'normalized_tag': 'oldtag',
                    'evaluations': [{'evaluation_id': 'legacy-1', 'hits': 0,
                                     'misses': 3, 'unknowns': 0,
                                     'unique_reviewed': 3,
                                     'decision': 'deferred_for_context',
                                     'source_endpoint': '/v1/instagram/search/hashtag'}],
                }},
            },
        }
        history_path.write_text(json.dumps(legacy))
        self.assertTrue(plan(self.root, self.run, self.schema)['ok'])
        collect(self.root, self.run, FakeProvider(provider_response(
            [item(1), item(2), item(3)])))
        self.assertTrue(self.review(review_document(self.root, self.run))['ok'])
        saved = json.loads(history_path.read_text())
        self.assertEqual(saved['platforms']['instagram']['oldtag']['evaluations'][0],
                         legacy['platforms']['instagram']['oldtag']['evaluations'][0])
        report, _ = hv.history_report(SimpleNamespace(project=str(self.root),
                                                      platform=None, key=None))
        old = next(row for row in report['entries'] if row['key'] == 'oldtag')
        self.assertTrue(old['legacy_kind_inferred'])
        self.assertEqual(old['query_kind'], 'hashtag')

        history_path.write_text(json.dumps({**legacy, 'schema_version': 1}))
        with self.assertRaises(ValueError):
            hv.history_report(SimpleNamespace(project=str(self.root),
                                              platform=None, key=None))

    def test_build_review_prompt_packages_samples(self):
        self.assertTrue(plan(self.root, self.run, self.schema)['ok'])
        collect(self.root, self.run, FakeProvider(provider_response(
            [item(1, caption='tag caption'), item(2), item(3)])))
        result, _ = hv.build_review_prompt(SimpleNamespace(
            project=str(self.root), run=self.run, plan=None))
        self.assertTrue(result['ok'], result)
        prompt = (self.root / result['review_prompt_path']).read_text()
        self.assertIn('tag caption', prompt)
        self.assertIn('paper packaging workshop', prompt)
        self.assertIn('direct_application', prompt)

    def test_web_evidence_is_separate_from_native_calls(self):
        self.assertTrue(plan(self.root, self.run, self.schema)['ok'])
        evidence = Path(self.temp.name) / 'web.json'
        evidence.write_text(json.dumps({'queries': [
            {'query': '#thiepcuoi', 'platform': 'instagram',
             'results': [{'url': 'https://www.instagram.com/reel/x/', 'snippet': 'tag alone'}]},
            {'query': '#thiepcuoi thiep cuoi', 'platform': 'instagram',
             'results': [{'url': 'https://www.instagram.com/reel/y/', 'snippet': 'qualified'}]},
        ]}))
        result, _ = hv.plan_probes(SimpleNamespace(
            project=str(self.root), run=self.run, schema=str(self.schema),
            max_calls=20, ceiling=None, web_evidence=str(evidence)))
        self.assertTrue(result['ok'], result)
        document = json.loads((self.root / result['plan_path']).read_text())
        self.assertEqual(len(document['calls']), 1)
        self.assertEqual(len(document['web_evidence']), 2)

    def test_batch_history_conflict_writes_nothing(self):
        hc.append_evaluation(
            self.root, 'instagram', 'shared',
            {'evaluation_id': 'eval-a', 'probe_id': 'probe-a', 'phase': 'probe',
             'hits': 1, 'misses': 2, 'unknowns': 0, 'unique_reviewed': 3,
             'decision': 'mixed', 'query_kind': 'hashtag'},
            original_term='#shared', normalized_term='shared')
        with self.assertRaises(hc.HistoryConflict):
            hc.append_evaluations(self.root, [
                {'platform': 'instagram', 'key': 'other',
                 'record': {'evaluation_id': 'eval-b', 'probe_id': 'probe-b',
                            'phase': 'probe', 'hits': 1, 'misses': 2,
                            'unknowns': 0, 'unique_reviewed': 3,
                            'decision': 'mixed', 'query_kind': 'hashtag'}},
                {'platform': 'instagram', 'key': 'shared',
                 'record': {'evaluation_id': 'eval-a', 'probe_id': 'probe-a',
                            'phase': 'probe', 'hits': 3, 'misses': 0,
                            'unknowns': 0, 'unique_reviewed': 3,
                            'decision': 'promising', 'query_kind': 'hashtag'}},
            ])
        history = json.loads((self.root / hc.HISTORY_RELATIVE).read_text())
        self.assertNotIn('other', history['platforms']['instagram'])
        self.assertEqual(len(history['platforms']['instagram']['shared']['evaluations']), 1)

    def test_seed_credentials_are_rejected(self):
        problems = hc.Problems()
        seeds = hc.bounded_seeds([{'id': 's1', 'url': 'https://user:pass@example.com/x',
                                   'excerpt': 'term'}], problems)
        self.assertEqual(seeds, [])
        self.assertTrue(any('credentials' in error for error in problems.errors))

    def test_concurrent_style_appends_keep_both_evaluations(self):
        for probe in ('probe-a', 'probe-b'):
            hc.append_evaluation(
                self.root, 'instagram', 'shared',
                {'evaluation_id': f'eval-{probe}', 'probe_id': probe,
                 'phase': 'probe', 'hits': 1, 'misses': 2, 'unknowns': 0,
                 'unique_reviewed': 3, 'decision': 'mixed',
                 'query_kind': 'hashtag'},
                original_term='#shared', normalized_term='shared')
        history = json.loads((self.root / hc.HISTORY_RELATIVE).read_text())
        evaluations = history['platforms']['instagram']['shared']['evaluations']
        self.assertEqual([item['probe_id'] for item in evaluations],
                         ['probe-a', 'probe-b'])


if __name__ == '__main__':
    unittest.main()
