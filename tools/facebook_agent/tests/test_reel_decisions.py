"""Offline Jev integration contracts; no paid requests or live browser."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.facebook_agent.cli import main
from tools.facebook_agent.reel_decisions import decide, prepare, product_context


def response(promotion=0.99, unrelated=0.99, evidence='0', confidence=0.99):
    return SimpleNamespace(
        nouls={key: SimpleNamespace(noul=value) for key, value in
               [('explicit_promotion', promotion), ('unrelated_offer', unrelated)]},
        choices={key: SimpleNamespace(choice=evidence, confidence=confidence)
                 for key in ('promotion_evidence', 'offer_evidence')},
        model='jev-test', usage=SimpleNamespace(model_dump=lambda **kwargs: {'input_tokens': 10, 'output_tokens': 5}))


class DecisionTests(unittest.TestCase):
    def test_default_allow_and_explicit_exclusion(self):
        for label, text, promotion, unrelated, expected in [
            ('explicit English course', 'Đăng ký khóa IELTS, giảm 30%', .99, .99, 'exclude'),
            ('explicit skincare', 'Buy this skincare set through my affiliate link', .99, .99, 'exclude'),
            ('unclear intent', 'Có gì hay hôm nay?', .5, .99, 'allow'),
            ('ordinary dancing', 'Nhảy vui cùng bạn bè', .02, .99, 'allow'),
            ('daily life', 'Một ngày bình thường', .01, .99, 'allow'),
            ('ordinary English lesson', 'Learn these three English words', .1, .99, 'allow'),
            ('relevant paper offer', 'Nhắn thử giấy Nhung đỏ', .99, .01, 'allow'),
        ]:
            with self.subTest(label=label):
                self.assertEqual(decide(response(promotion, unrelated), {'0': text})['decision'], expected)

    def test_no_exclusion_without_source_evidence_or_confident_selection(self):
        for result in [response(evidence='none'), response(evidence='missing'), response(confidence=.5)]:
            self.assertEqual(decide(result, {'0': 'Caption'})['decision'], 'allow')

    def test_invalid_probabilities_fail_instead_of_becoming_allow(self):
        for value in [float('nan'), float('inf'), -1, 2, True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                decide(response(promotion=value), {'0': 'Caption'})

    def test_audience_is_independent_of_default_allow_promotion_policy(self):
        answer = response(promotion=.02, unrelated=.02)
        answer.nouls['vietnamese_audience'] = SimpleNamespace(noul=.99)
        judged = decide(answer, {'0': 'Nhảy vui cùng bạn bè'})
        self.assertEqual(judged['decision'], 'allow')
        self.assertTrue(judged['audience_match'])
        answer.nouls['vietnamese_audience'].noul = .5
        judged = decide(answer, {'0': 'Unclear audience'})
        self.assertEqual(judged['decision'], 'allow')
        self.assertFalse(judged['audience_match'])

    def test_questions_see_product_and_untrusted_text_not_business_links(self):
        product = {'product': {'catalog': ['colored paper']}}
        state, questions = prepare({'text': 'Dance\nFollow', 'links': [{'url': 'private-business-link'}]}, product)
        self.assertEqual(state['our_offer'], product)
        self.assertNotIn('private-business-link', json.dumps(state))
        self.assertEqual(questions['offer_evidence'].criteria['none'], 'No explicit evidence or unclear.')
        self.assertIn('untrusted', questions['explicit_promotion'].instructions)


class JudgmentCliTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / 'observations.json'
        self.source.write_text(json.dumps({'records': [{'order': 1, 'text': 'Đăng ký khóa IELTS, giảm 30%', 'url': 'https://www.facebook.com/reel/123'}]}))
        (self.root / 'product-marketing.json').write_text(json.dumps({
            'product': {'catalog': [{'name': 'Colored paper'}]}, 'marketing_goal': 'Trial customers',
            'customer_profile': ['DO NOT SEND PRIVATE LEADS'], 'sales_information': {'phone': 'private'}}))
        self.output = self.root / 'judgments.json'

    def invoke(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(['judge-reels', '--input', str(self.source), '--product-dir', str(self.root),
                         '--output', str(self.output), *extra])
        return code, json.loads(out.getvalue())

    def test_dry_run_no_browser_no_api_and_no_private_leads(self):
        with patch('tools.facebook_agent.cli.Browser') as browser, patch('tools.facebook_agent.reel_decisions.TypeSafeClient') as client:
            code, result = self.invoke('--dry-run')
        self.assertEqual(code, 0)
        self.assertEqual(result['data']['judged'], 0)
        client.assert_not_called()
        browser.assert_not_called()
        self.assertNotIn('PRIVATE LEADS', self.output.read_text())
        self.assertNotIn('phone', json.dumps(product_context(self.root)))

    def test_requires_approval_and_credentials_without_api(self):
        with patch.dict('os.environ', {'TYPESAFE_API_KEY': ''}), patch('tools.facebook_agent.reel_decisions.TypeSafeClient') as client:
            code, _ = self.invoke()
            self.assertEqual(code, 2)
            code, result = self.invoke('--approve-api')
        self.assertEqual(code, 3)
        self.assertEqual(result['error']['code'], 'missing_credentials')
        client.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_success_saves_evidence_without_touching_raw_or_browser(self):
        before = self.source.read_bytes()
        with patch.dict('os.environ', {'TYPESAFE_API_KEY': 'test-key'}), patch('tools.facebook_agent.cli.Browser') as browser, patch('tools.facebook_agent.reel_decisions.TypeSafeClient') as client:
            client.return_value.__enter__.return_value.system_one.return_value = response()
            code, result = self.invoke('--approve-api')
        self.assertEqual(code, 0)
        self.assertEqual(result['data']['excluded'], 1)
        self.assertEqual(json.loads(self.output.read_text())['records'][0]['promotion_evidence'], 'Đăng ký khóa IELTS, giảm 30%')
        self.assertEqual(before, self.source.read_bytes())
        browser.assert_not_called()

    def test_timing_and_target_stop_after_one_allowed_vietnamese_reel(self):
        self.source.write_text(json.dumps({'records': [
            {'order': 1, 'text': 'Đời thường'}, {'order': 2, 'text': 'Du lịch'}]}))
        answer = response(promotion=.01, unrelated=.01, evidence='none')
        answer.nouls['vietnamese_audience'] = SimpleNamespace(noul=.99)
        with patch.dict('os.environ', {'TYPESAFE_API_KEY': 'test-key'}), patch('tools.facebook_agent.reel_decisions.TypeSafeClient') as client:
            client.return_value.__enter__.return_value.system_one.return_value = answer
            code, result = self.invoke('--approve-api', '--vietnamese-audience', '--target-count', '1')
        self.assertEqual(code, 0)
        self.assertEqual(result['data']['selected'], 1)
        saved = json.loads(self.output.read_text())
        self.assertEqual(saved['unprocessed_records'], 1)
        self.assertGreaterEqual(saved['elapsed_seconds'], 0)
        self.assertGreaterEqual(saved['records'][0]['request_seconds'], 0)

    def test_failure_reported_not_misrepresented_as_allow(self):
        with patch.dict('os.environ', {'TYPESAFE_API_KEY': 'test-key'}), patch('tools.facebook_agent.reel_decisions.TypeSafeClient') as client:
            client.return_value.__enter__.return_value.system_one.side_effect = RuntimeError('secret-provider-detail')
            code, result = self.invoke('--approve-api')
        self.assertEqual(code, 3)
        saved = json.loads(self.output.read_text())
        self.assertEqual(saved['status'], 'failed')
        self.assertEqual(saved['records'], [])
        self.assertNotIn('secret-provider-detail', json.dumps(result))

    def test_existing_output_and_bad_threshold_do_not_call_api(self):
        with patch('tools.facebook_agent.reel_decisions.TypeSafeClient') as client:
            code, _ = self.invoke('--dry-run', '--threshold', 'nan')
            self.assertEqual(code, 2)
            self.output.write_text('original')
            code, _ = self.invoke('--dry-run')
        self.assertEqual(code, 2)
        self.assertEqual(self.output.read_text(), 'original')
        client.assert_not_called()


if __name__ == '__main__':
    unittest.main()
