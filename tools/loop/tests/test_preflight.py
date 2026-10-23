"""Offline content-policy, research, visual and approval regressions."""

import contextlib
import io
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zlib

from tools.loop import cli, preflight, storage


SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 60" width="120" height="60">
<rect width="120" height="60" fill="#FBFBF9"/>
<text x="5" y="30" font-family="Inter, sans-serif" fill="#0F172A">Evidence</text>
</svg>'''


def png(width=240, height=120):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + b'\xfb\xfb\xf9' * width) * height))
            + chunk(b'IEND', b''))


class ContentFixture:
    """Reusable temporary project; all evidence/decisions are synthetic fixtures."""
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.directory = self.root / 'posts/2'
        self.directory.mkdir(parents=True)
        self.config = {
            'page_id': '123', 'hypotheses_file': 'posts/hypothesis.json',
            'allowed_channels': ['facebook_page'],
            'content_policy': {
                'schema_version': 1, 'tokens_file': 'brand/tokens.json',
                'guidelines_file': 'brand/guidelines.md', 'require_visual': True,
                'required_cta': ['phone: 123', 'team@example.org'],
                'research': {'min_primary_statutes': 2, 'min_case_studies': 1,
                             'primary_hosts': ['official.test']},
            },
        }
        self.write('loop/config.json', self.config)
        self.write('AGENTS.md', '# Fixture project rules')
        self.write('brand/guidelines.md', '# Fixture brand rules')
        self.write('brand/tokens.json', {'colors': {'canvas': '#FBFBF9', 'ink': '#0F172A',
                                                  'accent': '#C25E2E'}, 'fonts': ['Inter'], 'render_scale': 2})
        self.write('posts/hypothesis.json', {'hypotheses': [{'post': 2}]})
        self.write('posts/2/research.md', '# Fixture dossier\n[Official evidence](https://official.test/a)\nCase analysis recorded.')
        self.evidence = {'schema_version': 1, 'sources': [], 'claims': [
            {'claim': 'Fixture legal claim', 'source_ids': ['s0', 's1', 's2'],
             'limitations': 'Synthetic fixture only, not legal advice.'}]}
        for i, kind in enumerate(('primary_statute', 'primary_statute', 'case_study')):
            self.evidence['sources'].append({
                'id': f's{i}', 'type': kind, 'title': f'Fixture evidence {i}',
                'url': f'https://official.test/document/{i}', 'jurisdiction': 'Fixture',
                'checked_at': '2026-01-02', 'effective_date': '2026-01-01',
                'provisions': ['Article 1'], 'analysis': 'Synthetic source analysis and observed outcome.'})
        self.write('posts/2/research.json', self.evidence)
        self.text = 'Exact approved copy. phone: 123 / team@example.org'
        self.write('posts/2/facebook-ad.md', self.text + '\n')
        self.write('posts/2/visual.svg', SVG)
        (self.directory / 'visual.png').write_bytes(png())
        self.manifest = {'schema_version': 1, 'channel': 'facebook_page', 'copy': 'facebook-ad.md',
                         'visual': {'source': 'visual.svg', 'image': 'visual.png'}, 'groups': []}
        self.write('posts/2/content.json', self.manifest)

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, dict):
            storage.save(path, value)
        else:
            path.write_text(value, encoding='utf-8')

    def research_review(self):
        return preflight.record_decision(self.root, 2, kind='research', reviewer='Fixture human', approved=True)

    def approve(self):
        self.research_review()
        return preflight.record_decision(self.root, 2, kind='content', reviewer='Fixture human',
                                         approved=True, visual_reviewed=True)

    def error(self, stage='publish'):
        result = preflight.check(self.root, 2, stage)
        self.assertFalse(result['ok'], result)
        return result['errors'][0]['code']

    def publication(self, **overrides):
        values = dict(project=self.root, post=2, page_id='123', text=self.text,
                      image=self.directory / 'visual.png')
        return preflight.require_publication(**{**values, **overrides})


class ContentGateTest(ContentFixture, unittest.TestCase):
    def test_valid_pipeline_requires_two_distinct_human_decisions(self):
        self.assertTrue(preflight.check(self.root, 2, 'research')['ok'])
        self.assertEqual(self.error('draft'), 'missing_artifact')
        self.research_review()
        self.assertTrue(preflight.check(self.root, 2, 'draft')['ok'])
        self.assertTrue(preflight.check(self.root, 2, 'visual')['ok'])
        self.assertEqual(self.error(), 'missing_artifact')
        self.approve()
        self.assertTrue(preflight.check(self.root, 2)['ok'])
        self.assertEqual(self.publication(), '123')

    def test_preflight_never_writes(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        preflight.check(self.root, 2, 'research')
        preflight.check(self.root, 2, 'publish')
        after = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_missing_empty_and_placeholder_dossier(self):
        path = self.directory / 'research.md'
        path.unlink()
        self.assertEqual(self.error('research'), 'missing_artifact')
        for text in ('', 'TODO: research later'):
            path.write_text(text)
            self.assertEqual(self.error('research'), 'research_empty')

    def test_source_counts_and_case_requirement(self):
        self.evidence['sources'] = self.evidence['sources'][:2]
        self.write('posts/2/research.json', self.evidence)
        self.assertEqual(self.error('research'), 'research_count')

    def test_official_host_is_not_a_substring_match(self):
        self.evidence['sources'][0]['url'] = 'https://official.test.evil.test/law'
        self.write('posts/2/research.json', self.evidence)
        self.assertEqual(self.error('research'), 'research_primary_host')

    def test_statute_provisions_required(self):
        self.evidence['sources'][0]['provisions'] = []
        self.write('posts/2/research.json', self.evidence)
        self.assertEqual(self.error('research'), 'research_provisions')

    def test_future_and_inactive_law_dates(self):
        self.evidence['sources'][0]['checked_at'] = '2999-01-01'
        self.write('posts/2/research.json', self.evidence)
        self.assertEqual(self.error('research'), 'research_date')
        self.evidence['sources'][0]['checked_at'] = '2026-01-02'
        self.evidence['sources'][0]['effective_date'] = '2026-02-01'
        self.write('posts/2/research.json', self.evidence)
        self.assertEqual(self.error('research'), 'research_date')

    def test_duplicate_sources_do_not_count(self):
        self.evidence['sources'][1]['url'] = self.evidence['sources'][0]['url']
        self.write('posts/2/research.json', self.evidence)
        self.assertEqual(self.error('research'), 'research_duplicate')

    def test_unknown_claim_source_rejected(self):
        self.evidence['claims'][0]['source_ids'] = ['missing']
        self.write('posts/2/research.json', self.evidence)
        self.assertEqual(self.error('research'), 'research_claims')

    def test_channel_lock_only_scans_selected_post(self):
        self.write('posts/1/linkedin-post.md', 'Historical draft stays untouched.')
        self.assertTrue(preflight.check(self.root, 2, 'research')['ok'])
        self.write('posts/2/linkedin-post.md', 'Unauthorized current draft.')
        self.assertEqual(self.error('research'), 'channel_artifact')
        self.assertTrue((self.root / 'posts/1/linkedin-post.md').exists())

    def test_manifest_channel_rejected(self):
        self.research_review()
        self.manifest['channel'] = 'linkedin'
        self.write('posts/2/content.json', self.manifest)
        self.assertEqual(self.error('draft'), 'channel')

    def test_cta_required(self):
        self.research_review()
        self.write('posts/2/facebook-ad.md', 'No contact information')
        self.assertEqual(self.error('draft'), 'copy_cta')

    def test_artifact_path_escape_and_symlink_escape(self):
        self.research_review()
        self.manifest['copy'] = '../hypothesis.json'
        self.write('posts/2/content.json', self.manifest)
        self.assertEqual(self.error('draft'), 'invalid_artifact')
        self.manifest['copy'] = 'outside.md'
        self.write('posts/2/content.json', self.manifest)
        (self.directory / 'outside.md').symlink_to(self.root / 'AGENTS.md')
        self.assertEqual(self.error('draft'), 'invalid_artifact')

    def test_missing_visual_and_rendered_png(self):
        self.research_review()
        (self.directory / 'visual.png').unlink()
        self.assertEqual(self.error('visual'), 'missing_artifact')
        del self.manifest['visual']
        self.write('posts/2/content.json', self.manifest)
        self.assertEqual(self.error('visual'), 'visual_missing')

    def test_svg_palette_canvas_font_and_css(self):
        self.research_review()
        variants = [
            (SVG.replace('#0F172A', '#00FF00'), 'visual_palette'),
            (SVG.replace('#FBFBF9', '#0F172A'), 'visual_canvas'),
            (SVG.replace('Inter, sans-serif', 'Arial, sans-serif'), 'visual_font'),
            (SVG.replace('fill="#0F172A"', 'style="fill:#0F172A"'), 'visual_svg'),
            (SVG.replace('</svg>', '<linearGradient id="g"/></svg>'), 'visual_svg'),
            (SVG.replace('</svg>', '<rect width="120" height="60" fill="#0F172A"/></svg>'), 'visual_canvas'),
        ]
        for source, code in variants:
            with self.subTest(code=code):
                self.write('posts/2/visual.svg', source)
                self.assertEqual(self.error('visual'), code)

    def test_png_dimensions(self):
        self.research_review()
        (self.directory / 'visual.png').write_bytes(png(120, 60))
        self.assertEqual(self.error('visual'), 'visual_dimensions')

    def test_approval_flags_required(self):
        with self.assertRaises(preflight.GateError):
            preflight.record_decision(self.root, 2, kind='research', reviewer='Fixture human')
        self.research_review()
        with self.assertRaises(preflight.GateError):
            preflight.record_decision(self.root, 2, kind='content', reviewer='Fixture human', approved=True)

    def test_changed_research_invalidates_both_decisions(self):
        self.approve()
        self.write('posts/2/research.md', 'Changed dossier and interpretation.')
        self.assertEqual(self.error(), 'stale_approval')

    def test_changed_copy_media_and_policy_invalidate_approval(self):
        self.approve()
        for relative in ('posts/2/facebook-ad.md', 'posts/2/visual.svg', 'posts/2/visual.png',
                         'brand/guidelines.md', 'AGENTS.md'):
            path = self.root / relative
            original = path.read_bytes()
            with self.subTest(path=relative):
                path.write_bytes(original + b'\n')
                self.assertEqual(self.error(), 'stale_approval')
                path.write_bytes(original)
        self.config['content_policy']['required_cta'].append('Exact approved')
        self.write('loop/config.json', self.config)
        self.assertEqual(self.error(), 'stale_approval')

    def test_receipt_cannot_replace_visual_attestation(self):
        self.approve()
        path = self.directory / 'content-approval.json'
        approval = json.loads(path.read_text())
        approval['visual_reviewed'] = False
        storage.save(path, approval)
        self.assertEqual(self.error(), 'visual_review')

    def test_exact_text_image_page_and_groups_enforced(self):
        self.approve()
        for override in ({'text': self.text + '\n'}, {'image': None}, {'page_id': '456'},
                         {'groups': ['Unapproved group']}, {'video': 'video.mp4'}):
            with self.subTest(override=override), self.assertRaises(preflight.GateError):
                self.publication(**override)

    def test_approved_group_list_is_hash_bound(self):
        self.manifest['groups'] = ['Fixture group']
        self.write('posts/2/content.json', self.manifest)
        self.approve()
        self.assertEqual(self.publication(groups=['Fixture group']), '123')
        with self.assertRaises(preflight.GateError):
            self.publication()

    def test_managed_page_cannot_omit_project(self):
        with patch.object(preflight, 'managed_projects', return_value=[self.root]):
            with self.assertRaises(preflight.GateError):
                preflight.require_publication(page_id='123', text='Unscoped content')

    def test_managed_page_discovery(self):
        with TemporaryDirectory() as repo:
            config = Path(repo) / 'local/fixture/loop/config.json'
            storage.save(config, self.config)
            with patch.object(storage, 'REPO_ROOT', Path(repo)):
                self.assertEqual(preflight.managed_projects('123'), [config.parent.parent.resolve()])
                self.assertEqual(preflight.managed_projects('456'), [])

    def test_text_only_policy_and_legacy_measurement_compatibility(self):
        self.config['content_policy'] = {'schema_version': 1}
        self.write('loop/config.json', self.config)
        del self.manifest['visual']
        self.write('posts/2/content.json', self.manifest)
        preflight.record_decision(self.root, 2, kind='content', reviewer='Fixture human', approved=True)
        self.assertEqual(self.publication(image=None), '123')
        del self.config['content_policy']
        self.write('loop/config.json', self.config)
        self.assertEqual(storage.load_project(self.root)['page_id'], '123')
        self.assertEqual(self.error(), 'missing_policy')

    def test_cli_preflight_structured_error_and_no_state_writes(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as exc:
            cli.main(['--project', str(self.root), 'preflight', '--post', '2'])
        self.assertEqual(exc.exception.code, 2)
        self.assertFalse(json.loads(output.getvalue())['ok'])
        self.assertFalse((self.root / 'loop/status.json').exists())
        self.assertFalse((self.root / 'loop/.engine.lock').exists())

    def test_cli_decisions_and_preflight_success(self):
        commands = [
            ['review-research', '--post', '2', '--reviewer', 'Fixture human', '--approved'],
            ['approve-content', '--post', '2', '--reviewer', 'Fixture human', '--approved', '--visual-reviewed'],
            ['preflight', '--post', '2'],
        ]
        for args in commands:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                cli.main(['--project', str(self.root), *args])
            self.assertTrue(json.loads(output.getvalue())['ok'])

    def test_invalid_policy_and_unknown_post(self):
        self.assertEqual(preflight.check(self.root, 99, 'research')['errors'][0]['code'], 'unknown_post')
        self.config['content_policy']['research']['min_primary_statutes'] = -1
        self.write('loop/config.json', self.config)
        self.assertEqual(self.error('research'), 'invalid_policy')

    def test_registration_audits_but_never_discards_confirmed_facts(self):
        for approved in (False, True):
            with self.subTest(approved=approved):
                if approved:
                    self.approve()
                self.write('loop/publications.json', {'schema_version': 2, 'publications': [], 'placements': []})
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    cli.main(['--project', str(self.root), 'register', '--post', '2',
                              '--url', 'https://www.facebook.com/123/posts/999',
                              '--published-at', '2026-01-02T00:00:00Z'])
                publication = json.loads(output.getvalue())
                self.assertEqual(publication['url'], 'https://www.facebook.com/123/posts/999')
                self.assertEqual(publication['registered_content_preflight']['ok'], approved)
                saved = json.loads((self.root / 'loop/publications.json').read_text())
                self.assertEqual(saved['publications'][0], publication)


class RoutingContractTest(unittest.TestCase):
    def test_keyword_description_and_root_routing(self):
        root = Path(__file__).resolve().parents[3]
        skill = (root / '.agents/skills/social-campaign/SKILL.md').read_text()
        frontmatter = skill.split('---')[1].lower()
        for keyword in ('social projects', 'social posts', 'drafting', 'posting', 'publishing', 'campaigns'):
            self.assertIn(keyword, frontmatter)
        self.assertNotIn('block l&c', frontmatter)
        instructions = (root / 'AGENTS.md').read_text()
        self.assertIn('Load `social-campaign` before authoring', instructions)
        self.assertIn('allowed_channels', instructions)
        self.assertIn('Explicitly read', skill)

    def test_public_cli_contract_covers_operational_workarounds(self):
        root = Path(__file__).resolve().parents[3]
        instructions = (root / 'AGENTS.md').read_text()
        skill = (root / '.agents/skills/social-campaign/SKILL.md').read_text()
        for term in ('post --text-file', 'private-helper probes', 'not repository development/tests'):
            self.assertIn(term, instructions)
        for term in ('--text-file <COPY_FILE>', 'Capability gaps', 'content-library --page-id',
                     'never select solely by recency'):
            self.assertIn(term, skill)
