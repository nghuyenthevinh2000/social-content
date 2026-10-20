"""Tests for storage primitives: paths, config, writes and evidence records."""

import json
from pathlib import Path

from support import LoopTestCase
from tools.loop import project_init, storage


class StorageTest(LoopTestCase):
    def test_timestamp_requires_timezone(self):
        self.assertEqual(storage.timestamp('2026-01-01T00:00:00Z').isoformat(),
                         '2026-01-01T00:00:00+00:00')
        with self.assertRaises(ValueError):
            storage.timestamp('2026-01-01T00:00:00')

    def test_save_is_atomic_json(self):
        path = self.root / 'loop/nested/value.json'
        storage.save(path, {'b': 2, 'a': 'ủ'})
        self.assertEqual(json.loads(path.read_text()), {'b': 2, 'a': 'ủ'})
        self.assertFalse(path.with_suffix('.json.tmp').exists())

    def test_project_file_rejects_escape_and_absolute_paths(self):
        with self.assertRaises(ValueError):
            storage.project_file(self.root, '../other-project.json')
        with self.assertRaises(ValueError):
            storage.project_file(self.root, str(self.root / 'inside.json'))
        self.assertEqual(storage.project_file(self.root, 'loop/config.json'),
                         (self.root / 'loop/config.json').resolve())

    def test_project_initialization_and_optional_hypotheses(self):
        self.assertEqual(storage.load_project(self.root)['page_id'], self.page_id)
        state = json.loads(self.state_path.read_text())
        state['publications'].append(self.entry)
        storage.save(self.state_path, state)
        project_init.bootstrap_project(self.root, self.page_id)
        self.assertEqual(json.loads(self.state_path.read_text()), state)
        with self.assertRaises(ValueError):
            project_init.bootstrap_project(self.root, '999')
        with self.assertRaises(ValueError):
            project_init.bootstrap_project(self.root, 'not-a-page')

    def test_hypothesis_file_is_project_scoped(self):
        storage.save(self.root / 'custom/hypotheses.json', {'hypotheses': [{'post': 17}]})
        config = {'hypotheses_file': 'custom/hypotheses.json'}
        self.assertEqual(storage.load_hypotheses(self.root, config)['hypotheses'][0]['post'], 17)
        self.assertEqual(storage.load_hypotheses(self.root, {}), {})

    def test_dry_run_writes_nothing(self):
        new_dir = self.root / 'brand-new-project'
        res = project_init.bootstrap_project(new_dir, '999111', dry_run=True)
        self.assertTrue(res['dry_run'])
        self.assertFalse(new_dir.exists())

    def test_gap_deduplication(self):
        gaps = [
            {'kind': 'csv_export_failed', 'detail': 'same'},
            {'kind': 'csv_export_failed', 'detail': 'same'},
            {'kind': 'unresolved_group_identity', 'placement_id': 'row-a', 'detail': 'same'},
            {'kind': 'unresolved_group_identity', 'placement_id': 'row-b', 'detail': 'same'},
        ]
        self.assertEqual(len(storage.dedupe_gaps(gaps)), 3)

    def test_evidence_reuse_requires_path_hash_and_type(self):
        path = self.root / 'sources/post-metrics/captures/run/content-library.json'
        storage.save(path, {'placements': []})
        manifest = {'evidence_files': [{
            'path': str(path.relative_to(self.root)),
            'sha256': storage.sha256_file(path),
            'type': 'content_library',
        }]}
        self.assertEqual(storage.check_reusable_evidence(
            self.root, manifest, str(path.relative_to(self.root)), 'content_library'),
            (True, 'ok'))
        self.assertEqual(storage.check_reusable_evidence(
            self.root, manifest, str(path.relative_to(self.root)), 'post_insights'),
            (False, 'type_mismatch'))
        path.write_text('{}')
        self.assertEqual(storage.check_reusable_evidence(
            self.root, manifest, str(path.relative_to(self.root)), 'content_library'),
            (False, 'hash_mismatch'))

    def test_repair_path_allocates_siblings(self):
        captures = Path(self.root / 'captures')
        manifest = {'repair_attempts': {}}
        first = storage.repair_path(captures, 'sources/captures/shot.insights.json', manifest)
        self.assertEqual(first.name, 'shot.insights-repair1.json')
        first.parent.mkdir(parents=True)
        first.write_text('{}')
        second = storage.repair_path(captures, 'sources/captures/shot.insights.json', manifest)
        self.assertEqual(second.name, 'shot.insights-repair2.json')
