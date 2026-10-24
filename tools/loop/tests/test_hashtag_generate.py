"""Offline tests for hashtag prompt generation and response import."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from tools.loop.viral_analyzer import hashtag_common as hc
from tools.loop.viral_analyzer import hashtag_generate as hg


def write_campaign(root, slug='test-campaign'):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'product-marketing.json').write_text(json.dumps({
        'marketing_goal': 'Find paper distributors and product testers',
        'product': {'catalog': [{'name': 'CAMPAIGN-FACT-MARKER',
                                'applications': ['wedding invitations']}],
                    'unique': {'note': 'UNUSED-UNIQUE-MARKER'}},
        'sales_information': {'phone': '0904642276', 'email': 'private@example.com'},
        'customer_profile': {'viewer_age': '18-24', 'leads': ['Private Lead']},
    }))
    return root


def build_args(root, run='run-1', **overrides):
    values = {
        'project': str(root), 'run': run, 'platform': 'instagram',
        'market_language': 'vi', 'application': 'paper packaging workshop',
        'hypothesis': 1, 'new_test': None, 'seed_evidence': None,
        'max_candidates': 4,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def response_for(root, run, candidates, **overrides):
    context = json.loads((hc.artifact_directory(root, run) / 'context.json').read_text())
    envelope = {
        'schema_version': 1, 'campaign': context['campaign'], 'run_id': run,
        'context_sha256': context['context_sha256'], 'platform': context['platform'],
        'candidates': candidates,
    }
    envelope.update(overrides)
    return envelope


def candidate(**overrides):
    item = {
        'id': 'c1', 'kind': 'hashtag', 'text': '#thiepcuoi', 'language': 'vi',
        'application': 'wedding invitations', 'connection': 'invitation workshop buyer',
        'context_sources': ['product-marketing.json'], 'rationale': 'plausible branch',
        'alternative_meanings': ['wedding photos'], 'priority': 1,
        'origin': 'generated_unverified', 'evidence_ref': None,
    }
    item.update(overrides)
    return item


class GenerateTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = write_campaign(Path(self.temp.name) / 'test-campaign')

    def tearDown(self):
        self.temp.cleanup()

    def write_response(self, candidates, **overrides):
        path = Path(self.temp.name) / 'response.json'
        path.write_text(json.dumps(response_for(self.root, 'run-1', candidates, **overrides)))
        return path

    def test_prompt_uses_campaign_facts_and_redacts_private_fields(self):
        result, _ = hg.build_prompt(build_args(self.root))
        self.assertTrue(result['ok'], result)
        self.assertFalse(result['collection_blocked'])
        prompt = (self.root / result['prompt_path']).read_text()
        self.assertIn('CAMPAIGN-FACT-MARKER', prompt)
        self.assertNotIn('Sample product 1', prompt)
        self.assertNotIn('0904642276', prompt)
        self.assertNotIn('private@example.com', prompt)
        self.assertNotIn('viewer_age', prompt)
        self.assertNotIn('Private Lead', prompt)
        self.assertNotIn('UNUSED-UNIQUE-MARKER', prompt)
        context = json.loads((self.root / result['context_path']).read_text())
        self.assertEqual([item['path'] for item in context['sources']],
                         ['product-marketing.json'])
        self.assertEqual(set(context['context']),
                         {'campaign', 'goal', 'product', 'history', 'seed_evidence', 'prior_analysis'})

    def test_new_run_has_only_brief_report_and_artifacts_at_top_level(self):
        result, _ = hg.build_prompt(build_args(self.root))
        run = hc.run_directory(self.root, 'run-1')
        self.assertEqual({path.name for path in run.iterdir()},
                         {'brief.md', 'report.md', 'artifacts'})
        self.assertTrue(result['context_path'].endswith('/artifacts/context.json'))
        self.assertTrue(result['prompt_path'].endswith('/artifacts/prompt.md'))
        self.assertIn('pending', (run / 'report.md').read_text())

    def test_legacy_flat_runs_resume_without_moving_evidence(self):
        result, _ = hg.build_prompt(build_args(self.root))
        run = hc.run_directory(self.root, 'run-1')
        for path in (run / 'artifacts').iterdir():
            path.rename(run / path.name)
        (run / 'artifacts').rmdir()
        repeated, _ = hg.build_prompt(build_args(self.root))
        self.assertEqual(result['context_sha256'], repeated['context_sha256'])
        self.assertEqual(hc.artifact_directory(self.root, 'run-1'), run)
        response = self.write_response([candidate()])
        imported, _ = hg.import_response(SimpleNamespace(
            project=str(self.root), run='run-1', response=str(response)))
        self.assertTrue(imported['ok'], imported)
        self.assertTrue((run / 'candidates.json').exists())

    def test_ambiguous_layout_is_rejected(self):
        hg.build_prompt(build_args(self.root))
        run = hc.run_directory(self.root, 'run-1')
        (run / 'context.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'ambiguous run layout'):
            hc.artifact_directory(self.root, 'run-1')

    def test_legacy_expansion_only_run_keeps_receipt_location(self):
        run = hc.run_directory(self.root, 'old-expansion')
        (run / 'expansion/calls').mkdir(parents=True)
        self.assertEqual(hc.artifact_directory(self.root, 'old-expansion'), run)

    def test_prior_analysis_is_optional_bounded_context_not_fresh_evidence(self):
        base = self.root / 'sources/viral'
        for relative, text in {
            'past/report.md': 'Past finding: workshop demos fit. Contact private@example.com',
            'past/relevance.json': json.dumps({'finding': 'Consumer wedding clips missed'}),
            'run-1/report.md': 'CURRENT-RUN-EXCLUDED',
            'past/raw/analysis.json': '{"note": "RAW-EXCLUDED"}',
            'past/review-prompt.md': 'PROMPT-EXCLUDED',
            'past/large-analysis.md': 'x' * (hc.MAX_PRIOR_ANALYSIS_BYTES + 1),
        }.items():
            path = base / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        result, _ = hg.build_prompt(build_args(self.root))
        self.assertTrue(result['ok'], result)
        self.assertFalse(result['collection_blocked'])
        context = json.loads((self.root / result['context_path']).read_text())
        self.assertEqual({item['path'] for item in context['context']['prior_analysis']},
                         {'sources/viral/past/report.md', 'sources/viral/past/relevance.json'})
        prompt = (self.root / result['prompt_path']).read_text()
        self.assertIn('workshop demos fit', prompt)
        for excluded in ('CURRENT-RUN-EXCLUDED', 'RAW-EXCLUDED', 'PROMPT-EXCLUDED',
                         'private@example.com'):
            self.assertNotIn(excluded, prompt)
        self.assertTrue(any('exceeds' in warning for warning in result['warnings']))
        path = self.write_response([candidate(context_sources=[
            'product-marketing.json', 'sources/viral/past/report.md'])])
        imported, _ = hg.import_response(SimpleNamespace(
            project=str(self.root), run='run-1', response=str(path)))
        self.assertTrue(imported['ok'], imported)

    def test_prior_analysis_does_not_follow_links_outside_campaign(self):
        outside = Path(self.temp.name) / 'other-report.md'
        outside.write_text('OTHER-CAMPAIGN-SECRET')
        base = self.root / 'sources/viral'
        base.mkdir(parents=True)
        (base / 'linked-report.md').symlink_to(outside)
        result, _ = hg.build_prompt(build_args(self.root))
        self.assertTrue(result['ok'], result)
        self.assertNotIn('OTHER-CAMPAIGN-SECRET',
                         (self.root / result['prompt_path']).read_text())

    def test_prior_analysis_file_count_is_bounded(self):
        base = self.root / 'sources/viral/past'
        base.mkdir(parents=True)
        for index in range(hc.MAX_PRIOR_ANALYSES + 2):
            (base / f'analysis-{index}.md').write_text(f'Finding {index}')
        result, _ = hg.build_prompt(build_args(self.root))
        context = json.loads((self.root / result['context_path']).read_text())
        self.assertEqual(len(context['context']['prior_analysis']), hc.MAX_PRIOR_ANALYSES)
        self.assertTrue(any('limited to' in warning for warning in result['warnings']))

    def test_missing_product_brief_blocks_collection(self):
        (self.root / 'product-marketing.json').unlink()
        result, _ = hg.build_prompt(build_args(self.root))
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['collection_blocked'])
        self.assertEqual(result['gaps'][0]['kind'], 'missing_context')
        self.assertEqual(result['conflicts'], [])

    def test_cold_start_generates_and_imports_without_history(self):
        history = self.root / hc.HISTORY_RELATIVE
        self.assertFalse(history.exists())
        result, _ = hg.build_prompt(build_args(self.root))
        self.assertTrue(result['ok'], result)
        context = json.loads((self.root / result['context_path']).read_text())
        self.assertEqual(context['context']['history'], [])
        self.assertEqual(context['context']['prior_analysis'], [])
        self.assertIn('cold start', (self.root / result['prompt_path']).read_text())
        self.assertIn('import-response', result['next_action'])
        path = self.write_response([candidate()])
        imported, _ = hg.import_response(SimpleNamespace(
            project=str(self.root), run='run-1', response=str(path)))
        self.assertTrue(imported['ok'], imported)
        self.assertFalse(history.exists())  # Proposals are not verification evidence.

    def test_unrelated_files_do_not_affect_context_or_collection(self):
        result, _ = hg.build_prompt(build_args(self.root))
        self.assertTrue(result['ok'], result)
        self.assertFalse(result['collection_blocked'])
        for relative in ('brand/brand.yaml', 'customer/profile.json',
                         'posts/hypothesis.json', 'loop/config.json', 'loop/AGENTS.md'):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('INVALID-UNRELATED-CONTEXT')
        repeated, _ = hg.build_prompt(build_args(self.root))
        self.assertTrue(repeated['ok'], repeated)
        self.assertFalse(repeated['collection_blocked'])
        self.assertEqual(result['context_sha256'], repeated['context_sha256'])

    def test_invalid_product_brief_blocks_collection(self):
        for text in ('{bad json', '[]', '{}',
                     '{"marketing_goal": "Find buyers", "product": {"catalog": []}}'):
            with self.subTest(text=text):
                (self.root / 'product-marketing.json').write_text(text)
                result, _ = hg.build_prompt(build_args(self.root))
                self.assertTrue(result['collection_blocked'])
                self.assertTrue(result['gaps'])

    def test_cli_does_not_require_hypothesis_or_new_test(self):
        args = hg._parser().parse_args([
            'build-prompt', '--project', str(self.root), '--run', 'run-1',
            '--platform', 'instagram', '--market-language', 'vi',
            '--application', 'wedding invitations'])
        result, _ = args.command_func(args)
        self.assertTrue(result['ok'], result)
        self.assertFalse(result['collection_blocked'])

    def test_oversized_context_is_rejected(self):
        (self.root / 'product-marketing.json').write_text('x' * (hc.MAX_CONTEXT_FILE_BYTES + 1))
        result, _ = hg.build_prompt(build_args(self.root))
        self.assertFalse(result['ok'])
        self.assertTrue(any('context limit' in error for error in result['errors']))

    def test_import_valid_response_and_duplicate_rejection(self):
        hg.build_prompt(build_args(self.root))
        path = self.write_response([candidate()])
        result, _ = hg.import_response(SimpleNamespace(
            project=str(self.root), run='run-1', response=str(path)))
        self.assertTrue(result['ok'], result)
        saved = json.loads((self.root / result['candidates_path']).read_text())
        self.assertEqual(saved['candidates'][0]['normalized_text'], 'thiepcuoi')

        duplicate = self.write_response([candidate(id='c2')])
        result, _ = hg.import_response(SimpleNamespace(
            project=str(self.root), run='run-1', response=str(duplicate)))
        self.assertFalse(result['ok'])
        self.assertTrue(any('duplicated' in error for error in result['errors']))

    def test_import_rejects_campaign_isolation_and_unknown_sources(self):
        hg.build_prompt(build_args(self.root))
        path = self.write_response([candidate()], campaign='other-campaign')
        result, _ = hg.import_response(SimpleNamespace(
            project=str(self.root), run='run-1', response=str(path)))
        self.assertFalse(result['ok'])
        self.assertTrue(any('campaign' in error for error in result['errors']))

        path = self.write_response([candidate(context_sources=['brand/missing.md'])])
        result, _ = hg.import_response(SimpleNamespace(
            project=str(self.root), run='run-1', response=str(path)))
        self.assertFalse(result['ok'])
        self.assertTrue(any('unknown' in error for error in result['errors']))

    def test_observed_origin_requires_matching_seed_excerpt(self):
        seeds = Path(self.temp.name) / 'seeds.json'
        seeds.write_text(json.dumps([{'id': 'seed-1', 'platform': 'tiktok',
                                      'excerpt': 'xuong in thiep cuoi #thiepcuoi'}]))
        hg.build_prompt(build_args(self.root, seed_evidence=str(seeds)))
        path = self.write_response([candidate(origin='observed', evidence_ref='seed-1')])
        result, _ = hg.import_response(SimpleNamespace(
            project=str(self.root), run='run-1', response=str(path)))
        self.assertTrue(result['ok'], result)

        path = self.write_response([candidate(origin='observed', evidence_ref='missing')])
        result, _ = hg.import_response(SimpleNamespace(
            project=str(self.root), run='run-1', response=str(path)))
        self.assertFalse(result['ok'])

    def test_invalid_response_is_preserved_for_inspection(self):
        hg.build_prompt(build_args(self.root))
        path = Path(self.temp.name) / 'bad.json'
        path.write_text('{not json')
        result, _ = hg.import_response(SimpleNamespace(
            project=str(self.root), run='run-1', response=str(path)))
        self.assertFalse(result['ok'])
        self.assertTrue((self.root / result['raw_path']).is_file())


if __name__ == '__main__':
    unittest.main()
