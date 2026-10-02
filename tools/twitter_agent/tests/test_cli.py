"""Subprocess interface tests for CLI commands and JSON output."""

import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tools.twitter_agent.cli import main


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.state_dir = Path(self.temp_dir) / '.twitter-agent'
        self.base_cmd = [sys.executable, '-m', 'tools.twitter_agent', '--state-dir', str(self.state_dir)]

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_reply_prepare_and_removed_supervise_command(self):
        prepared = subprocess.run(
            self.base_cmd + ['reply', 'prepare', '123', '--text', 'Hello'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(prepared.returncode, 0)
        body = json.loads(prepared.stdout)
        self.assertTrue(body['ok'])
        self.assertEqual(body['data']['draft']['state'], 'pending')
        self.assertFalse(body['data']['browser_prepared'])

        # The separate supervisor command has been removed.
        supervisor = subprocess.run(
            self.base_cmd + ['supervise'],
            input='approve 123\n',
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(supervisor.returncode, 0)
        supervisor_out = json.loads(supervisor.stdout)
        self.assertFalse(supervisor_out['ok'])
        self.assertEqual(supervisor_out['error']['code'], 'invalid_arguments')
        self.assertEqual(supervisor.returncode, 2)

    def test_invalid_arguments_emits_json_exit_2(self):
        res = subprocess.run(
            self.base_cmd + ['nonexistent_command'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 2)
        body = json.loads(res.stdout)
        self.assertFalse(body['ok'])
        self.assertEqual(body['error']['code'], 'invalid_arguments')

    def test_no_approve_subcommand_exists(self):
        res = subprocess.run(
            self.base_cmd + ['approve', '123'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 2)
        body = json.loads(res.stdout)
        self.assertFalse(body['ok'])

    def test_pause_resume_status_cancel_lifecycle(self):
        # Prepare a draft
        subprocess.run(
            self.base_cmd + ['reply', 'prepare', '123', '--text', 'Test text'],
            capture_output=True,
            text=True,
            check=True,
        )

        # Status
        status_res = subprocess.run(
            self.base_cmd + ['status'],
            capture_output=True,
            text=True,
            check=True,
        )
        status_data = json.loads(status_res.stdout)['data']
        self.assertFalse(status_data['paused'])
        self.assertEqual(len(status_data['pending_drafts']), 1)
        draft_id = status_data['pending_drafts'][0]['id']

        # Pause
        pause_res = subprocess.run(
            self.base_cmd + ['pause'],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertTrue(json.loads(pause_res.stdout)['data']['paused'])

        # Resume
        resume_res = subprocess.run(
            self.base_cmd + ['resume'],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertFalse(json.loads(resume_res.stdout)['data']['paused'])

        # Cancel
        cancel_res = subprocess.run(
            self.base_cmd + ['cancel', draft_id],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(json.loads(cancel_res.stdout)['data']['draft']['state'], 'cancelled')

    def test_queue_jsonl_atomic_import(self):
        valid_jsonl = Path(self.temp_dir) / 'queue.jsonl'
        valid_jsonl.write_text(
            '{"target": "100", "text": "First"}\n{"target": "101", "text": "Second"}\n',
            encoding='utf-8',
        )
        res = subprocess.run(
            self.base_cmd + ['queue', str(valid_jsonl)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        body = json.loads(res.stdout)
        self.assertEqual(len(body['data']['drafts']), 2)

        # Malformed jsonl
        bad_jsonl = Path(self.temp_dir) / 'bad.jsonl'
        bad_jsonl.write_text(
            '{"target": "200", "text": "Third"}\nnot valid json\n',
            encoding='utf-8',
        )
        bad_res = subprocess.run(
            self.base_cmd + ['queue', str(bad_jsonl)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(bad_res.returncode, 2)
        bad_body = json.loads(bad_res.stdout)
        self.assertEqual(bad_body['error']['code'], 'invalid_jsonl')

    def test_duplicate_enqueue_returns_existing_draft(self):
        res1 = subprocess.run(
            self.base_cmd + ['reply', 'prepare', '123', '--text', 'Same text'],
            capture_output=True,
            text=True,
            check=True,
        )
        res2 = subprocess.run(
            self.base_cmd + ['reply', 'prepare', '123', '--text', 'Same text'],
            capture_output=True,
            text=True,
            check=True,
        )
        draft1 = json.loads(res1.stdout)['data']['draft']
        draft2 = json.loads(res2.stdout)['data']['draft']
        self.assertEqual(draft1['id'], draft2['id'])

    def test_help_flag_prints_human_readable_text_and_exits_0(self):
        res = subprocess.run(
            self.base_cmd + ['--help'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn('Terminal-operated X DOM CLI', res.stdout)

    def test_reply_submit_dispatches_without_interactive_prompt(self):
        prepared = subprocess.run(
            self.base_cmd + ['reply', 'prepare', '123', '--text', 'Hello'],
            capture_output=True, text=True, check=True,
        )
        draft = json.loads(prepared.stdout)['data']['draft']
        with patch('tools.twitter_agent.cli.Browser') as browser, \
                patch('tools.twitter_agent.cli.submit_draft',
                      return_value={**draft, 'state': 'submitted'}) as submit, \
                patch('sys.stdout', new_callable=io.StringIO) as output:
            code = main(['--state-dir', str(self.state_dir), 'reply', 'submit', draft['id']])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output.getvalue())['ok'])
        self.assertEqual(submit.call_args.args[2], draft['id'])
        browser.assert_called_once()

    def test_watchlist_cli_commands(self):
        # Add
        add_res = subprocess.run(
            self.base_cmd + ['watchlist', 'add', '@sama', '--notes', 'OpenAI'],
            capture_output=True, text=True, check=True
        )
        self.assertTrue(json.loads(add_res.stdout)['ok'])

        # List
        list_res = subprocess.run(
            self.base_cmd + ['watchlist', 'list'],
            capture_output=True, text=True, check=True
        )
        data = json.loads(list_res.stdout)['data']
        self.assertEqual(len(data['watchlist']), 1)
        self.assertEqual(data['watchlist'][0]['handle'], 'sama')

        # Remove
        rem_res = subprocess.run(
            self.base_cmd + ['watchlist', 'remove', 'sama'],
            capture_output=True, text=True, check=True
        )
        self.assertTrue(json.loads(rem_res.stdout)['ok'])

    def test_watch_command_empty_watchlist(self):
        res = subprocess.run(
            self.base_cmd + ['watch'],
            capture_output=True, text=True, check=True
        )
        data = json.loads(res.stdout)['data']
        self.assertEqual(data['opportunities'], [])
        self.assertIn('Watchlist is empty', data['message'])

    def test_watch_command_with_posts_and_ranking(self):
        import io
        from unittest.mock import MagicMock, patch
        from tools.twitter_agent.cli import main
        from tools.twitter_agent.store import Store

        store = Store(self.state_dir)
        store.add_watchlist('sama', notes='OpenAI CEO')
        store.add_watchlist('karpathy', notes='AI researcher')

        fake_posts_sama = {
            'posts': [
                {'id': '10', 'text': 'Sama tweet 1', 'score': 0.5},
                {'id': '11', 'text': 'Sama tweet 2', 'score': 0.9},
            ]
        }
        fake_posts_karpathy = {
            'posts': [
                {'id': '20', 'text': 'Karpathy tweet 1', 'score': 0.8},
                {'id': '10', 'text': 'Duplicate tweet', 'score': 0.5},
            ]
        }

        def mock_read_posts(page, mode, query, limit=10):
            if 'sama' in query:
                return fake_posts_sama
            return fake_posts_karpathy

        mock_browser_inst = MagicMock()
        mock_browser_inst.__enter__.return_value = mock_browser_inst
        mock_browser_inst.__exit__.return_value = None
        mock_browser_inst.page = MagicMock()

        captured = io.StringIO()
        with patch('tools.twitter_agent.cli.Browser', return_value=mock_browser_inst), \
             patch('tools.twitter_agent.cli.read_posts', side_effect=mock_read_posts), \
             patch('sys.stdout', captured):
            code = main(['--state-dir', str(self.state_dir), 'watch', '--limit', '2'])
            self.assertEqual(code, 0)

        out = json.loads(captured.getvalue())
        self.assertTrue(out['ok'])
        opps = out['data']['opportunities']
        self.assertEqual(len(opps), 2)
        # Highest score first (0.9 Sama tweet 2)
        self.assertEqual(opps[0]['id'], '11')
        self.assertEqual(opps[0]['watchlist_handle'], 'sama')
        self.assertEqual(opps[0]['watchlist_notes'], 'OpenAI CEO')
        # Second highest score (0.8 Karpathy tweet 1)
        self.assertEqual(opps[1]['id'], '20')
        self.assertEqual(opps[1]['watchlist_handle'], 'karpathy')
        self.assertEqual(opps[1]['watchlist_notes'], 'AI researcher')

    def test_watch_command_invalid_limits(self):
        res = subprocess.run(
            self.base_cmd + ['watch', '--limit', '0'],
            capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 2)
        data = json.loads(res.stdout)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['code'], 'invalid_limit')

        res_poll = subprocess.run(
            self.base_cmd + ['watch', '--poll', '-5'],
            capture_output=True, text=True
        )
        self.assertEqual(res_poll.returncode, 2)
        data_poll = json.loads(res_poll.stdout)
        self.assertFalse(data_poll['ok'])
        self.assertEqual(data_poll['error']['code'], 'invalid_arguments')

    @patch('tools.twitter_agent.cli.read_posts')
    @patch('tools.twitter_agent.cli.Browser')
    def test_search_window_minutes_and_min_score(self, mock_browser_cls, mock_read_posts):
        mock_browser = MagicMock()
        mock_browser_cls.return_value.__enter__.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_read_posts.return_value = {
            'posts': [
                {'id': '1', 'text': 'High score', 'score': 85.0},
                {'id': '2', 'text': 'Low score', 'score': 65.0},
            ],
            'scrolls': 1,
            'reason': 'limit_reached',
            'partial': False,
        }

        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, \
             patch('time.time', return_value=1790715600.0):
            ret = main(['search', 'AI', '--window-minutes', '60', '--min-score', '80.0'])
            self.assertEqual(ret, 0)
            res = json.loads(mock_stdout.getvalue())
            self.assertTrue(res['ok'])
            # Verify query has since_time
            called_query = mock_read_posts.call_args[0][2]
            self.assertIn('AI', called_query)
            self.assertIn('since_time:1790712000', called_query)
            # Verify filtered posts
            self.assertEqual(len(res['data']['posts']), 1)
            self.assertEqual(res['data']['posts'][0]['id'], '1')

    def test_search_invalid_window_minutes(self):
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            ret = main(['search', 'AI', '--window-minutes', '0'])
            self.assertEqual(ret, 2)
            res = json.loads(mock_stdout.getvalue())
            self.assertFalse(res['ok'])
            self.assertEqual(res['error']['code'], 'invalid_window_minutes')

    def test_search_invalid_min_score(self):
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            ret = main(['search', 'AI', '--min-score', '101'])
            self.assertEqual(ret, 2)
            res = json.loads(mock_stdout.getvalue())
            self.assertFalse(res['ok'])
            self.assertEqual(res['error']['code'], 'invalid_min_score')

    @patch('tools.twitter_agent.cli.read_posts')
    @patch('tools.twitter_agent.cli.Browser')
    def test_watch_topics_discovery(self, mock_browser_cls, mock_read_posts):
        mock_browser = MagicMock()
        mock_browser_cls.return_value.__enter__.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.page = mock_page

        def mock_read(page, mode, query, limit):
            if 'AI' in query:
                return {'posts': [{'id': '10', 'text': 'AI post', 'score': 90.0}]}
            elif 'LLM' in query:
                return {'posts': [{'id': '10', 'text': 'AI post dup', 'score': 90.0}, {'id': '20', 'text': 'LLM post', 'score': 75.0}]}
            return {'posts': []}

        mock_read_posts.side_effect = mock_read

        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, \
             patch('time.time', return_value=1790715600.0):
            ret = main(['watch', '--topics', 'AI, LLM', '--window-minutes', '30', '--min-score', '80.0'])
            self.assertEqual(ret, 0)
            res = json.loads(mock_stdout.getvalue())
            self.assertTrue(res['ok'])
            opps = res['data']['opportunities']
            self.assertEqual(len(opps), 1)
            self.assertEqual(opps[0]['id'], '10')

            # Verify query calls included window-minutes and suffix
            call_queries = [call[0][2] for call in mock_read_posts.call_args_list]
            self.assertTrue(any('AI min_faves:5 lang:en -filter:links since_time:' in q for q in call_queries))
            self.assertTrue(any('LLM min_faves:5 lang:en -filter:links since_time:' in q for q in call_queries))

    @patch('tools.twitter_agent.cli.read_posts')
    @patch('tools.twitter_agent.cli.Browser')
    def test_watch_topics_default_uses_curated_topics(self, mock_browser_cls, mock_read_posts):
        mock_browser = MagicMock()
        mock_browser_cls.return_value.__enter__.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.page = mock_page
        mock_read_posts.return_value = {'posts': [{'id': '1', 'text': 'Shipped v1', 'score': 95.0}]}

        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            ret = main(['watch', '--topics'])
            self.assertEqual(ret, 0)
            res = json.loads(mock_stdout.getvalue())
            self.assertTrue(res['ok'])
            opps = res['data']['opportunities']
            self.assertEqual(len(opps), 1)
            self.assertEqual(opps[0]['topic'], 'AI')

            call_queries = [call[0][2] for call in mock_read_posts.call_args_list]
            # Verify quoted topic phrasing
            self.assertTrue(any('"just shipped" min_faves:5 lang:en -filter:links' in q for q in call_queries))
            self.assertTrue(any('AI min_faves:5 lang:en -filter:links' in q for q in call_queries))

    def test_watch_invalid_window_minutes(self):
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            ret = main(['watch', '--topics', 'AI', '--window-minutes', '0'])
            self.assertEqual(ret, 2)
            res = json.loads(mock_stdout.getvalue())
            self.assertFalse(res['ok'])
            self.assertEqual(res['error']['code'], 'invalid_window_minutes')

    def test_watch_invalid_min_score(self):
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            ret = main(['watch', '--min-score', '-1.0'])
            self.assertEqual(ret, 2)
            res = json.loads(mock_stdout.getvalue())
            self.assertFalse(res['ok'])
            self.assertEqual(res['error']['code'], 'invalid_min_score')

        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            ret = main(['watch', '--min-score', '105.0'])
            self.assertEqual(ret, 2)
            res = json.loads(mock_stdout.getvalue())
            self.assertFalse(res['ok'])
            self.assertEqual(res['error']['code'], 'invalid_min_score')

    @patch('tools.twitter_agent.cli.read_posts')
    @patch('tools.twitter_agent.cli.Browser')
    def test_watch_watchlist_with_min_score(self, mock_browser_cls, mock_read_posts):
        from tools.twitter_agent.store import Store
        store = Store(self.state_dir)
        store.add_watchlist('sama', notes='OpenAI CEO')

        mock_browser = MagicMock()
        mock_browser_cls.return_value.__enter__.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.page = mock_page

        mock_read_posts.return_value = {
            'posts': [
                {'id': '10', 'text': 'High', 'score': 90.0},
                {'id': '20', 'text': 'Low', 'score': 50.0},
            ]
        }

        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            ret = main(['--state-dir', str(self.state_dir), 'watch', '--min-score', '80.0'])
            self.assertEqual(ret, 0)
            res = json.loads(mock_stdout.getvalue())
            self.assertTrue(res['ok'])
            opps = res['data']['opportunities']
            self.assertEqual(len(opps), 1)
            self.assertEqual(opps[0]['id'], '10')
            self.assertEqual(opps[0]['watchlist_handle'], 'sama')

    def test_report_help_subprocess(self):
        res = subprocess.run(
            self.base_cmd + ['report', '--help'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn('--topics-file', res.stdout)
        self.assertIn('--window-hours', res.stdout)
        self.assertIn('--per-topic', res.stdout)
        self.assertIn('--candidate-limit', res.stdout)
        self.assertIn('--output-dir', res.stdout)

    def test_report_default_uses_topic_folder(self):
        from tools.twitter_agent.cli import build_parser
        args = build_parser().parse_args(['report'])
        expected = Path(__file__).parent.parent / 'topics' / 'topics.json'
        self.assertEqual(args.topics_file.resolve(), expected.resolve())
        self.assertTrue(args.topics_file.is_file())

    def test_report_invalid_budget_does_not_connect(self):
        invalid_args_cases = [
            ['--candidate-limit', '1'],
            ['--candidate-limit', '101'],
            ['--window-hours', '0'],
            ['--window-hours', '-5'],
            ['--per-topic', '0'],
            ['--per-topic', '15', '--candidate-limit', '10'],
        ]
        for extra in invalid_args_cases:
            with patch('tools.twitter_agent.cli.Browser') as browser, \
                 patch('sys.stdout', new_callable=io.StringIO) as out:
                code = main(['--state-dir', str(self.state_dir), 'report'] + extra)
                self.assertEqual(code, 2, msg=f"Failed on {extra}")
                body = json.loads(out.getvalue())
                self.assertFalse(body['ok'])
                self.assertEqual(body['error']['code'], 'invalid_arguments')
                browser.assert_not_called()

    def test_report_invalid_topics_file_exits_2(self):
        with patch('tools.twitter_agent.cli.Browser') as browser, \
             patch('sys.stdout', new_callable=io.StringIO) as out:
            bad_path = Path(self.temp_dir) / 'nonexistent_topics.json'
            code = main(['--state-dir', str(self.state_dir), 'report', '--topics-file', str(bad_path)])
            self.assertEqual(code, 2)
            body = json.loads(out.getvalue())
            self.assertFalse(body['ok'])
            self.assertEqual(body['error']['code'], 'invalid_topics_file')
            browser.assert_not_called()

    @patch('tools.twitter_agent.cli.write_report')
    @patch('tools.twitter_agent.cli.collect_report')
    @patch('tools.twitter_agent.cli.Browser')
    @patch('tools.twitter_agent.cli.time.time', return_value=1700000000.0)
    def test_report_happy_path_exit_0(self, mock_time, mock_browser_cls, mock_collect, mock_write):
        dummy_report = {
            'partial': False,
            'summary': {'total_topics': 1, 'by_status': {'ok': 1}},
            'coverage': 'bounded_sample',
            'window': {'start': 1699913600, 'end': 1700000000},
        }
        mock_collect.return_value = dummy_report
        mock_write.return_value = {
            'run_dir': '/tmp/report-123',
            'evidence_json': '/tmp/report-123/evidence.json',
            'report_markdown': '/tmp/report-123/report.md',
        }
        mock_browser = MagicMock()
        mock_browser_cls.return_value.__enter__.return_value = mock_browser

        with patch('sys.stdout', new_callable=io.StringIO) as out:
            code = main(['--state-dir', str(self.state_dir), 'report', '--window-hours', '24'])
            self.assertEqual(code, 0)
            body = json.loads(out.getvalue())
            self.assertTrue(body['ok'])
            data = body['data']
            self.assertEqual(data['artifacts']['run_dir'], '/tmp/report-123')
            self.assertFalse(data['partial'])
            self.assertEqual(data['window']['end'], 1700000000)
            self.assertEqual(data['window']['start'], 1700000000 - 24 * 3600)

    @patch('tools.twitter_agent.cli.write_report')
    @patch('tools.twitter_agent.cli.collect_report')
    @patch('tools.twitter_agent.cli.Browser')
    def test_report_degraded_path_exit_4(self, mock_browser_cls, mock_collect, mock_write):
        dummy_report = {
            'partial': True,
            'summary': {'total_topics': 1, 'by_status': {'partial': 1}},
            'coverage': 'bounded_sample',
            'window': {'start': 100, 'end': 200},
        }
        mock_collect.return_value = dummy_report
        mock_write.return_value = {
            'run_dir': '/tmp/report-deg',
            'evidence_json': '/tmp/report-deg/evidence.json',
            'report_markdown': '/tmp/report-deg/report.md',
        }
        mock_browser = MagicMock()
        mock_browser_cls.return_value.__enter__.return_value = mock_browser

        with patch('sys.stdout', new_callable=io.StringIO) as out:
            code = main(['--state-dir', str(self.state_dir), 'report'])
            self.assertEqual(code, 4)
            body = json.loads(out.getvalue())
            self.assertTrue(body['ok'])
            self.assertTrue(body['data']['partial'])

    @patch('tools.twitter_agent.cli.collect_report')
    @patch('tools.twitter_agent.cli.Browser')
    def test_report_write_failure_exit_1(self, mock_browser_cls, mock_collect):
        from tools.twitter_agent.models import AgentError
        mock_collect.return_value = {'partial': False}
        mock_browser = MagicMock()
        mock_browser_cls.return_value.__enter__.return_value = mock_browser

        # Point output-dir to an existing file to trigger write_report failure
        file_dir = Path(self.temp_dir) / 'file.txt'
        file_dir.write_text('bad', encoding='utf-8')

        with patch('sys.stdout', new_callable=io.StringIO) as out:
            code = main(['--state-dir', str(self.state_dir), 'report', '--output-dir', str(file_dir)])
            self.assertEqual(code, 1)
            body = json.loads(out.getvalue())
            self.assertFalse(body['ok'])
            self.assertEqual(body['error']['code'], 'report_write_failed')
