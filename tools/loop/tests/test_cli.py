"""CLI dispatch regressions: command names, project scoping and no-collection paths."""

import contextlib
import io
import json
from unittest.mock import patch

from support import LoopTestCase
from tools.loop import cli, collect, project_init, storage, workflow


class CliTest(LoopTestCase):
    def _main(self, argv):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            cli.main(argv)
        return json.loads(stream.getvalue())

    def test_cli_register_without_product_schema(self):
        self._main(['--project', str(self.root), 'register', '--post', '1',
                    '--url', 'https://www.facebook.com/reel/999',
                    '--published-at', '2026-01-01T00:00:00Z'])
        state = json.loads(self.state_path.read_text())
        self.assertEqual(state['publications'][0]['post'], 1)
        self.assertEqual(self.status()['current_stage'], 'register')

    def test_cli_requires_explicit_project(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(['status'])

    def test_project_hypothesis_mapping_is_optional_and_scoped(self):
        root = self.root / 'custom-project'
        storage.save(root / 'custom/hypotheses.json', {'hypotheses': [{'post': 17}]})
        project_init.bootstrap_project(root, self.page_id, hypotheses_file='custom/hypotheses.json')
        command = ['--project', str(root), 'register', '--post', '18',
                   '--url', 'https://www.facebook.com/reel/999',
                   '--published-at', '2026-01-01T00:00:00Z']
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(command)
        state = json.loads((root / 'loop/publications.json').read_text())
        self.assertEqual(state['publications'], [])

    def test_cli_due_reports_placement_checkpoints(self):
        pub = self.entry
        pub['metrics_status'] = 'collected'
        storage.save(self.state_path, {
            'schema_version': 2,
            'publications': [pub],
            'placements': [{
                'id': 'pl-orig-1', 'publication_id': pub['id'], 'kind': 'original_page',
                'checkpoints': {
                    '24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'collected'},
                    '7d': {'due_at': '2026-01-08T00:00:00Z', 'status': 'pending'},
                },
            }],
        })
        with patch.object(storage, 'now', return_value=storage.timestamp('2026-01-09T00:00:00Z')):
            due = self._main(['--project', str(self.root), 'due'])
        self.assertEqual([(item['placement_id'], item['checkpoint']) for item in due],
                         [('pl-orig-1', '7d')])
        self.assertEqual(self.status()['current_stage'], 'checkpoints')
        self.assertEqual(self.status()['state'], 'waiting')

    def test_compare_and_prepare_review_dispatch_without_collection(self):
        self.make_cycle_state()
        cycle_res = self.run_cycle()
        run_id = cycle_res['run_id']
        run_dir = self.root / 'loop/runs' / run_id
        (run_dir / 'review-bundle.json').unlink()

        with patch.object(collect.subprocess, 'run',
                          side_effect=AssertionError('compare must not collect')):
            compared = self._main(['--project', str(self.root), 'compare', '--run', run_id])
            self.assertEqual(compared['status'], 'compared')
            self.assertEqual(compared['comparison_file'], f'loop/runs/{run_id}/comparison.json')
            self.assertFalse((run_dir / 'review-bundle.json').exists())

            prepared = self._main(['--project', str(self.root), 'prepare-review', '--run', run_id])
            self.assertEqual(prepared['status'], 'review_prepared')
            self.assertTrue((run_dir / 'review-bundle.json').exists())
            self.assertTrue(prepared['summary'])

        with self.assertRaises(ValueError):
            cli.main(['--project', str(self.root), 'compare', '--run', 'missing-run'])

    def test_status_command_includes_projection(self):
        result = self._main(['--project', str(self.root), 'status'])
        self.assertIn('pending_work', result)
        self.assertIn('status', result)
        self.assertEqual(result['status']['schema_version'], 3)

    def test_cli_review_and_approval_report_stage_handoffs(self):
        self.make_cycle_state()
        cycle_res = self.run_cycle()
        run_id = cycle_res['run_id']
        review_file = self.root / 'review-input.json'
        storage.save(review_file, {
            'observation': 'One snapshot', 'limitation': 'No inquiry data',
            'suggestions': [{'id': 'sug-1'}],
        })
        recorded = self._main(['--project', str(self.root), 'review', '--run', run_id,
                               '--file', str(review_file)])
        self.assertEqual(recorded['status'], 'proposed')
        self.assertEqual(self.status()['current_stage'], 'approval')

        approved = self._main(['--project', str(self.root), 'approve-review',
                               '--run', run_id, '--proposals', 'sug-1'])
        self.assertEqual(approved['status'], 'approved')
        self.assertEqual(self.status()['state'], 'completed')
