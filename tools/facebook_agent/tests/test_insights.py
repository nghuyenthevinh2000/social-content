"""Offline checks for Insights navigation and labeled metric extraction."""

import base64
import unittest
from urllib.parse import quote

from tools.facebook_agent.insights import post_metrics, validate_url, READ_ONLY_LABELS, SNAPSHOT
from tools.facebook_agent.models import AgentError


class InsightsTest(unittest.TestCase):
    def test_rendered_gender_segments_and_discovery_tab(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content('''<div><h2>Who viewed your content</h2><button>Age and gender</button>
                    <div><span>25-34</span><div data-metric="MALE" style="width:95.8%;height:8px"></div><span>95.8%</span></div>
                    <div><span>35-44</span><div data-metric="FEMALE" style="width:4.2%;height:8px"></div><span>4.2%</span></div></div>
                    <div><h2>How people find your content</h2><button aria-pressed="false">Traffic</button>
                    <button aria-pressed="true">Source</button><div>Search<br>4.2%</div></div>''')
                data = page.evaluate(SNAPSHOT)
                self.assertEqual([(item['age'], item['gender'], item['bar_width'])
                                  for item in data['age_gender_segments']],
                                 [('25-34', 'MALE', '95.8%'), ('35-44', 'FEMALE', '4.2%')])
                self.assertEqual(data['discovery_panels'][0]['selected_tab'], 'Source')
            finally:
                browser.close()

    def test_post_metrics_and_unknowns(self):
        result = post_metrics('Post insights\nViews\n23\nViewers\n1\n'
                              'Audience retention\nAverage watch time: 25s\n'
                              'More viewers dropped off at the 0:01 mark\n'
                              '3-second views\n6\nWatch time\n4:13\n'
                              'Average percentage watched\n100%\nPlayer 10-second view rate\n--\n'
                              '0\nReactions\n0\nClicks\n0\nComments\n0\nShares\n'
                              'Who viewed your content\nAge and gender\n25-34\n100%\nLink clicks')
        self.assertEqual(result['views'], 23)
        self.assertEqual(result['viewers'], 1)
        self.assertEqual(result['watch_time_seconds'], 253)
        self.assertEqual(result['largest_dropoff_seconds'], 1)
        self.assertEqual(result['average_percentage_watched'], 100)
        self.assertIsNone(result['player_10_second_view_rate'])
        self.assertIsNone(result['qualified_inquiries'])
        self.assertEqual(result['reported_age_percentages'], {'25-34': 100.0})

    def test_page_and_missing_metrics_not_zero(self):
        self.assertIsNone(post_metrics('Audience overview\nNot enough data to show yet.'))
        result = post_metrics('Post insights\nViews\n1,234\nViewers\n3')
        self.assertEqual(result['views'], 1234)
        self.assertIsNone(result['average_percentage_watched'])
        self.assertIsNone(result['comments'])

    def test_navigation_is_read_only_and_page_bound(self):
        page_id = '61595289277974'
        token = quote(base64.b64encode(f'S:_I{page_id}:123:123'.encode()).decode())
        url = f'https://www.facebook.com/content/insights/?content_id={token}'
        self.assertEqual(validate_url(url, page_id), url)
        for bad in ('https://evil.example/insights/',
                    'https://www.facebook.com/professional_dashboard_evil/',
                    'https://www.facebook.com/professional_dashboard/?page_id=123',
                    'https://www.facebook.com/content/insights/?content_id=invalid'):
            with self.assertRaises(AgentError):
                validate_url(bad, page_id)
        for label in ('Publish', 'Create a post', 'Delete', 'Boost post'):
            self.assertNotIn(label, READ_ONLY_LABELS)


if __name__ == '__main__':
    unittest.main()
