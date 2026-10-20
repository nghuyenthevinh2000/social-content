"""Shared offline fixtures for tools/loop stage tests."""

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.loop import project_init, register, storage


class LoopTestCase(unittest.TestCase):
    page_id = '456'

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        project_init.bootstrap_project(self.root, self.page_id)
        self.state_path = self.root / 'loop/publications.json'
        self.state = {'publications': []}
        self.entry = register.register(
            self.state, 3, 'https://www.facebook.com/reel/123', '2026-01-01T00:00:00Z')
        self.at = storage.timestamp('2026-01-02T00:00:00Z')
        self.calls = []
        self.receipt = {
            'id': 'run-1', 'run_url': 'https://app.glasser.ai/runs/run-1',
            'status': 'COMPLETED', 'charge_usd': '0.00188',
            'completed_at': '2026-01-02T00:05:00Z',
            'provider_response': {'http_status': 200},
            'output': {'success': True, 'url': self.entry['url'],
                       'author': {'id': self.page_id},
                       'view_count': 23, 'like_count': 0, 'share_count': 0,
                       'comment_count': None, 'video': {'length_in_second': 10}},
        }

    def fake(self, *args):
        self.calls.append(args)
        if args[0] == 'search':
            return {'task_id': 'tsk_test'}
        if args[0] == 'inspect':
            return {'price': {'rule': {'type': 'flat', 'amount_usd': '0.00188'},
                              'charges': {'NO_RESULT': '0.00188'}}}
        return copy.deepcopy(self.receipt)

    def collect(self, budget='0.00188', at=None, call=None):
        from tools.loop import collect as collect_module
        return collect_module.collect(self.state, self.state_path, budget,
                                      project_root=self.root, page_id=self.page_id,
                                      call=call or self.fake, at=at or self.at)

    def save_state(self, state=None):
        storage.save(self.state_path, state if state is not None else self.state)

    def make_cycle_state(self, *, kind='original_page', insights_url=None,
                         visible_at='2026-01-01T00:00:00Z', due_at='2026-01-02T00:00:00Z',
                         checkpoint='24h', status='pending', post_id=1,
                         url='https://www.facebook.com/reel/111'):
        pub = register.register(self.state, post_id, url, '2026-01-01T00:00:00Z')
        state = {
            'schema_version': 2,
            'publications': [pub],
            'placements': [{
                'id': 'pl-orig-1', 'publication_id': pub['id'], 'kind': kind,
                'permalink': pub['url'],
                'insights_url': insights_url or 'https://www.facebook.com/insights/111',
                'visibility': 'visible', 'visible_at': visible_at,
                'checkpoints': {checkpoint: {'due_at': due_at, 'status': status}},
            }],
        }
        self.save_state(state)
        return pub, state

    def default_runner(self, *, insights_fails=False, lib_placements=None,
                       import_posts=None, observed_at='2026-01-02T01:00:00Z',
                       metrics=None, export_fails=False, import_fails=False):
        """Return a subprocess.run stand-in for the three Facebook collectors."""
        import subprocess

        def runner(cmd, **kwargs):
            self.calls.append(list(cmd))
            if 'content-library' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps(
                    {'placements': lib_placements if lib_placements is not None else []}))
            elif 'insights-export' in cmd:
                if export_fails:
                    return subprocess.CompletedProcess(args=cmd, returncode=1,
                                                       stdout='', stderr='export failed')
                Path(cmd[cmd.index('--output') + 1]).write_text('Date,Reactions\n2026-01-01,0\n')
            elif 'insights-import' in cmd:
                if import_fails:
                    Path(cmd[cmd.index('--output') + 1]).unlink(missing_ok=True)
                    return subprocess.CompletedProcess(args=cmd, returncode=1,
                                                       stdout='', stderr='import failed')
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps(
                    {'posts': import_posts if import_posts is not None else []}))
            elif 'insights' in cmd:
                if insights_fails:
                    return subprocess.CompletedProcess(args=cmd, returncode=1,
                                                       stdout='', stderr='insights error')
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [{
                        'observed_at': observed_at,
                        'post_metrics': metrics if metrics is not None else {'views': 100},
                    }],
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0,
                                               stdout='ok', stderr='')

        return runner

    def run_cycle(self, runner=None, **kwargs):
        from tools.loop import workflow
        return workflow.cycle(self.root, runner=runner or self.default_runner(), **kwargs)

    def status(self):
        return json.loads((self.root / 'loop/status.json').read_text())

    def run_manifest(self, run_id):
        return json.loads((self.root / 'loop/runs' / run_id / 'manifest.json').read_text())
