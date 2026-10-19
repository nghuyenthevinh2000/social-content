"""Benchmark preflight must not browse or spend without credentials/approval."""

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from tools.facebook_agent.cli import main


class BenchmarkTests(unittest.TestCase):
    def test_missing_credentials_does_not_start_browser(self):
        output = io.StringIO()
        with patch.dict('os.environ', {'TYPESAFE_API_KEY': ''}), patch('tools.facebook_agent.reel_benchmark.Browser') as browser, contextlib.redirect_stdout(output):
            code = main(['benchmark-reels', '--page-id', '61595289277974',
                         '--product-dir', 'local/paper-ink-product',
                         '--output-dir', 'must-not-be-created', '--approve-api'])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(output.getvalue())['error']['code'], 'missing_credentials')
        browser.assert_not_called()


if __name__ == '__main__':
    unittest.main()
