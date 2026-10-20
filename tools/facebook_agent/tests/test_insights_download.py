"""Offline validation and browser-fixture coverage for Content CSV downloads."""

import json
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from urllib.parse import quote

from tools.facebook_agent.insights_export import export_csv, report_id_from_url, validate_download
from tools.facebook_agent.models import AgentError


class DownloadTest(unittest.TestCase):
    def test_report_reused_without_browser_or_another_file(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / 'original.csv'
            original.write_text('Post ID,Page ID\n123,456\n')
            (root / 'old.export.json').write_text(json.dumps({
                'profile': {'url': 'https://www.facebook.com/profile.php?id=456'},
                'report_id': '789', 'status': 'download_not_received'}))
            (root / 'verified.export.json').write_text(json.dumps({
                'profile': {'url': 'https://www.facebook.com/profile.php?id=456'},
                'report_id': '789', 'status': 'downloaded', 'output': str(original),
                'sha256': hashlib.sha256(original.read_bytes()).hexdigest()}))
            result = export_csv(None, '456', root / 'duplicate.csv', report_id='789')
            self.assertEqual(result['status'], 'reused')
            self.assertEqual(result['output'], str(original))
            self.assertFalse((root / 'duplicate.csv').exists())

    def test_uncertain_download_blocks_before_browser(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            audit = root / 'attempt.export.json'
            data = {'profile': {'url': 'https://www.facebook.com/profile.php?id=456'},
                    'report_id': '789', 'status': 'download_not_received'}
            audit.write_text(json.dumps(data))
            with self.assertRaises(AgentError) as error:
                export_csv(None, '456', root / 'retry.csv', report_id='789')
            self.assertEqual(error.exception.code, 'export_uncertain')
            data.update(status='downloaded', output=str(root / 'missing.csv'), sha256='incorrect')
            audit.write_text(json.dumps(data))
            with self.assertRaises(AgentError):
                export_csv(None, '456', root / 'retry.csv', report_id='789')

    def test_report_id_from_rendered_download_link(self):
        target = 'https://scontent.test.fbcdn.net/path/file.123?_nc=test'
        self.assertEqual(report_id_from_url('https://l.facebook.com/l.php?u=' + quote(target)), '123')
        self.assertEqual(report_id_from_url(target), '123')
        self.assertIsNone(report_id_from_url('https://evil.example/file.123'))

    def test_csv_validation_checks_identity_and_format(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'data.csv'
            path.write_text('Post ID,Page ID,Title\n123,456,"two\nlines"\n')
            self.assertEqual(validate_download(path, '456')['rows'], 1)
            with self.assertRaises(AgentError):
                validate_download(path, '789')
            path.write_text('<html>Sign in</html>')
            with self.assertRaises(AgentError):
                validate_download(path, '456')

    def test_existing_file_refused_before_browser_access(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'data.csv'
            path.write_text('user data')
            with self.assertRaises(AgentError):
                export_csv(None, '456', path)
            self.assertEqual(path.read_text(), 'user data')

    def test_create_history_and_download_one_new_report(self):
        from playwright.sync_api import sync_playwright
        html = '''<button onclick="menu()">Export data</button><main id="ui"></main>
        <script>
        let created = false;
        function menu() {ui.innerHTML = `<div role="menu">
          <button role="menuitem" onclick="history()">Report history</button>
          <button role="menuitem" onclick="report()">Create new data report</button></div>`;}
        function history() {ui.innerHTML = `<div role="dialog"><h2>Report history</h2>
          <button onclick="ui.innerHTML=''">Close</button>
          <a href="https://scontent.test.fbcdn.net/report.42">Download</a>
          ${created ? '<a target="_blank" href="https://scontent.test.fbcdn.net/report.123">Download</a>' : ''}</div>`;}
        function report() {ui.innerHTML = `<div role="dialog"><h2>Create data report</h2>
          <button>Content\nView data for your posts, reels, videos and more.</button>
          <p>Last 28 days</p><button onclick="created=true;ui.innerHTML=''">Create report (.csv)</button></div>`;}
        </script>'''
        with TemporaryDirectory() as temp, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(accept_downloads=True)
                context.route('https://www.facebook.com/**', lambda route: route.fulfill(body=html, content_type='text/html'))
                context.route('https://scontent.test.fbcdn.net/**', lambda route: route.fulfill(
                    body='Post ID,Page ID,Title\n123,456,Example\n',
                    headers={'content-type': 'text/csv', 'content-disposition': 'attachment; filename="report.csv"'}))
                page = context.new_page()
                stub = SimpleNamespace(page=page, timeout_ms=5000, keep_page=False,
                                       check_authenticated=lambda **_: {'url': 'https://www.facebook.com/profile.php?id=456'})
                path = Path(temp) / 'download.csv'
                result = export_csv(stub, '456', path, download_timeout_seconds=10)
                self.assertEqual(result['status'], 'downloaded')
                self.assertEqual(result['rows'], 1)
                audit = json.loads(path.with_suffix('.export.json').read_text())
                self.assertEqual(audit['existing_report_ids'], ['42'])
                self.assertEqual(audit['report_id'], '123')
                self.assertTrue(path.exists())
                self.assertFalse(path.with_suffix('.csv.download').exists())
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
