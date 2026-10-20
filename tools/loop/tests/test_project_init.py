"""Offline tests for tools/loop/project_init.py:

python3 -m unittest discover -s tools/loop/tests
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.loop import project_init


class ProjectInitTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.page_id = '123456789'

    def test_dry_run_writes_nothing(self):
        target = self.root / 'dry-run-target'
        res = project_init.bootstrap_project(target, self.page_id, dry_run=True)
        self.assertTrue(res['dry_run'])
        self.assertFalse(target.exists())
        self.assertIn('product-marketing.json', res['would_create_files'])
        self.assertIn('posts/1/facebook-ad.md', res['would_create_files'])
        self.assertIn('loop/publications.json', res['would_create_files'])

    def test_live_bootstrap_creates_complete_layout(self):
        target = self.root / 'live-target'
        res = project_init.bootstrap_project(target, self.page_id, marketing_goal='Bán giấy mỹ thuật')
        self.assertEqual(res['status'], 'initialized')
        self.assertEqual(res['schema_version'], 2)

        # 1. Product catalog
        catalog_path = target / 'product-marketing.json'
        self.assertTrue(catalog_path.exists())
        catalog = json.loads(catalog_path.read_text())
        self.assertEqual(catalog['marketing_goal'], 'Bán giấy mỹ thuật')
        self.assertTrue(len(catalog['product']['catalog']) >= 1)

        # 2. Posts & hypothesis
        hypo_path = target / 'posts/hypothesis.json'
        self.assertTrue(hypo_path.exists())
        hypo = json.loads(hypo_path.read_text())
        self.assertEqual(len(hypo['hypotheses']), 1)
        self.assertEqual(hypo['hypotheses'][0]['post'], 1)

        post_1_path = target / 'posts/1/facebook-ad.md'
        self.assertTrue(post_1_path.exists())
        self.assertIn('Bài 1', post_1_path.read_text())

        # 3. Loop state & guides
        state_path = target / 'loop/publications.json'
        self.assertTrue(state_path.exists())
        state = json.loads(state_path.read_text())
        self.assertEqual(state['schema_version'], 2)
        self.assertEqual(state['publications'], [])
        self.assertEqual(state['placements'], [])

        self.assertTrue((target / 'loop/config.json').exists())
        self.assertTrue((target / 'loop/README.md').exists())
        self.assertTrue((target / 'loop/AGENTS.md').exists())
        self.assertTrue((target / 'loop/runs').exists())
        self.assertTrue((target / 'sources/post-metrics/exports').exists())
        self.assertTrue((target / 'sources/post-metrics/captures').exists())
        self.assertTrue((target / 'sources/post-metrics/normalized').exists())
        self.assertTrue((target / 'brand-assets').exists())
        self.assertTrue((target / 'customer').exists())

    def test_idempotent_rerun_preserves_custom_edits(self):
        target = self.root / 'rerun-target'
        project_init.bootstrap_project(target, self.page_id)

        # Custom edit
        catalog_path = target / 'product-marketing.json'
        catalog = json.loads(catalog_path.read_text())
        catalog['marketing_goal'] = 'Customized Goal'
        catalog_path.write_text(json.dumps(catalog))

        # Re-run
        project_init.bootstrap_project(target, self.page_id)
        reloaded = json.loads(catalog_path.read_text())
        self.assertEqual(reloaded['marketing_goal'], 'Customized Goal')

    def test_conflicting_page_id_fails(self):
        target = self.root / 'conflict-target'
        project_init.bootstrap_project(target, self.page_id)
        with self.assertRaises(ValueError):
            project_init.bootstrap_project(target, '999999999')


if __name__ == '__main__':
    unittest.main()
