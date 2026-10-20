"""Tests for stage 3 collection: paid fallback, dashboards and buyer actions."""

import copy
import json
from unittest.mock import patch

from support import LoopTestCase
from tools.loop import collect, project_init, storage


class CollectTest(LoopTestCase):
    def test_collect_once_nulls_receipt_and_review(self):
        from tools.loop import review
        self.collect()
        self.assertEqual(self.entry['snapshot']['views'], 23)
        self.assertIsNone(self.entry['snapshot']['comments'])
        self.assertIsNone(self.entry['snapshot']['qualified_inquiries'])
        self.assertGreater(self.entry['snapshot']['age_hours'], 24)
        self.assertEqual(self.entry['review_status'], 'pending')
        self.assertTrue((self.root / self.entry['receipt_file']).exists())
        count = len(self.calls)
        self.assertEqual(self.collect(), [])
        self.assertEqual(len(self.calls), count)
        review.review(self.entry, {'observation': '23 views',
                                   'limitation': 'No inquiry data',
                                   'next_test': 'Application-first opening'})
        self.assertEqual(self.entry['review_status'], 'reviewed')
        self.assertEqual(self.entry['reviews'][0]['run_url'], self.receipt['run_url'])

    def test_budget_ceiling(self):
        self.collect('0.00187')
        self.assertFalse(any(args[0] == 'run' for args in self.calls))
        self.assertEqual(self.entry['metrics_status'], 'pending')
        for value in ('NaN', '-1', 'Infinity'):
            with self.assertRaises(ValueError):
                self.collect(value)

    def test_timeout_keeps_saved_key(self):
        def fail(*args):
            if args[0] == 'run':
                saved = json.loads(self.state_path.read_text())['publications'][0]
                self.assertIn('idempotency_key', saved)
                raise RuntimeError('Transport outcome unknown')
            return self.fake(*args)
        with self.assertRaises(RuntimeError):
            self.collect(call=fail)
        key = self.entry['idempotency_key']
        self.collect()
        dispatched = next(args for args in self.calls if args[0] == 'run')
        self.assertEqual(dispatched[dispatched.index('--idempotency-key') + 1], key)

    def test_receipt_recovers_without_new_paid_call(self):
        storage.save(self.root / 'sources/post-metrics' / (self.entry['id'] + '-24h.run.json'),
                     self.receipt)
        self.collect()
        self.assertFalse(any(args[0] == 'run' for args in self.calls))
        self.assertEqual(self.entry['metrics_status'], 'collected')

    def test_no_result_is_not_zero_or_automatic_retry(self):
        self.receipt['output'] = {'success': False}
        self.collect()
        self.assertEqual(self.entry['metrics_status'], 'needs_attention')
        self.assertNotIn('snapshot', self.entry)
        self.assertEqual(self.collect(), [])

    def test_identity_mismatch(self):
        self.receipt['output']['author']['id'] = 'someone-else'
        self.collect()
        self.assertEqual(self.entry['metrics_status'], 'needs_attention')
        self.assertNotIn('snapshot', self.entry)

    def test_dashboard_checkpoint_collects_once_without_glasser(self):
        self.entry['insights_url'] = 'https://www.facebook.com/content/insights/?content_id=test'
        evidence = self.root / 'sources/post-metrics' / (self.entry['id'] + '-24h.insights.json')

        def fake_cli(*args, **kwargs):
            storage.save(evidence, {'capture_complete': True,
                                    'profile': {'url': f'https://www.facebook.com/profile.php?id={self.page_id}'},
                                    'records': [{
                                        'observed_at': '2026-01-02T00:05:00Z',
                                        'url': self.entry['insights_url'],
                                        'post_metrics': {'views': 23, 'viewers': 1,
                                                         'average_percentage_watched': 100,
                                                         'qualified_inquiries': None},
                                    }]})

        with patch.object(collect.subprocess, 'run', side_effect=fake_cli) as cli:
            collect.collect_insights(self.state, self.state_path, project_root=self.root,
                                     page_id=self.page_id, at=self.at)
            self.assertEqual(self.entry['metrics_source'], 'facebook_insights_dashboard')
            self.assertEqual(self.entry['snapshot']['viewers'], 1)
            self.assertEqual(self.entry['review_status'], 'pending')
            self.assertEqual(self.entry['charge_usd'], '0.00')
            self.assertEqual(collect.collect_insights(
                self.state, self.state_path, project_root=self.root,
                page_id=self.page_id, at=self.at), [])
            self.assertEqual(cli.call_count, 1)
            args = cli.call_args.args[0]
            self.assertEqual(args[args.index('--page-id') + 1], self.page_id)
            self.assertEqual(cli.call_args.kwargs['cwd'], storage.REPO_ROOT)

    def test_record_buyer_action(self):
        action_data = {
            'contact_key': 'user-hash-abc',
            'intent': 'paper-sample-request',
            'status': 'qualified',
            'agreed_next_step': 'ship_sample_kit',
            'publication_id': self.entry['id'],
        }
        res = collect.record_action(self.root, action_data)
        self.assertEqual(res['status'], 'qualified')
        actions_file = self.root / 'loop/actions.jsonl'
        lines = actions_file.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])['contact_key'], 'user-hash-abc')

    def test_two_projects_do_not_share_state_or_receipts(self):
        other_root = self.root / 'unrelated-project'
        project_init.bootstrap_project(other_root, '789')
        self.collect()
        self.assertEqual(json.loads((other_root / 'loop/publications.json').read_text())['publications'], [])
        self.assertEqual(list((other_root / 'sources/post-metrics').glob('*.json')), [])
        self.assertEqual(storage.load_project(other_root)['page_id'], '789')
        other_state = copy.deepcopy({'publications': [self.entry]})
        other_entry = other_state['publications'][0]
        other_entry['metrics_status'] = 'pending'

        def other_call(*args):
            result = self.fake(*args)
            if args[0] == 'run':
                result['output']['author']['id'] = '789'
            return result

        collect.collect(other_state, other_root / 'loop/publications.json', '0.00188',
                        project_root=other_root, page_id='789', call=other_call, at=self.at)
        self.assertEqual(other_entry['metrics_status'], 'collected')
        self.assertEqual(json.loads((self.root / self.entry['receipt_file']).read_text())['output']['author']['id'],
                         self.page_id)
        self.assertEqual(json.loads((other_root / other_entry['receipt_file']).read_text())['output']['author']['id'],
                         '789')
