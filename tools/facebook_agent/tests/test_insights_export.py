"""Offline tests for joining daily exports with rendered dashboard evidence."""

import base64
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.facebook_agent.insights_export import enrich_snapshot, import_export
from tools.facebook_agent.models import AgentError


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.csv = self.root / 'export.csv'
        self.output = self.root / 'joined.json'
        self.row = {'Post ID': '123', 'Page ID': '456', 'Title': 'Line one\nLine two',
                    'Publish time': '10/18/2026 21:40', 'Permalink': 'https://www.facebook.com/reel/789/',
                    'Date': '10/19/2026', 'Average Seconds viewed': '12.234',
                    'Comments': '0', 'Reactions': '0', 'Shares': '0', 'Seconds viewed': '36.703'}

    def write_rows(self, rows):
        with self.csv.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(self.row))
            writer.writeheader()
            writer.writerows(rows)

    def test_daily_rows_and_averages_are_not_mixed(self):
        self.write_rows([self.row, {**self.row, 'Date': '10/20/2026', 'Average Seconds viewed': '27.099',
                                   'Seconds viewed': '216.792'}])
        import_export(self.csv, self.output, '456')
        data = json.loads(self.output.read_text())['posts'][0]
        self.assertAlmostEqual(data['export_period_totals']['seconds_viewed'], 253.495)
        self.assertIsNone(data['average_seconds_viewed_aggregate'])
        self.assertIsNone(data['publish_timezone'])
        self.assertEqual(len(data['daily']), 2)
        self.assertEqual(data['title'], 'Line one\nLine two')

    def test_duplicate_exact_rows_not_double_counted(self):
        self.write_rows([self.row, self.row])
        import_export(self.csv, self.output, '456')
        data = json.loads(self.output.read_text())
        self.assertEqual(data['duplicate_rows_ignored'], 1)
        self.assertEqual(len(data['posts'][0]['daily']), 1)

    def test_conflicting_duplicates_and_nonfinite_values_rejected(self):
        self.write_rows([self.row, {**self.row, 'Shares': '1'}])
        with self.assertRaises(AgentError):
            import_export(self.csv, self.output, '456')
        for bad in ('NaN', 'inf', '-1'):
            self.write_rows([{**self.row, 'Shares': bad}])
            with self.assertRaises(AgentError):
                import_export(self.csv, self.output, '456')

    def test_join_is_by_post_id_not_title_or_position(self):
        self.write_rows([self.row])
        token = base64.b64encode(b'S:_I456:123:123').decode()
        source = self.root / 'dashboard.json'
        source.write_text(json.dumps({'profile': {'url': 'https://www.facebook.com/profile.php?id=456'},
                                     'records': [{'url': 'https://www.facebook.com/content/insights/?content_id=' + token,
                                                  'stage': 'Source', 'observed_at': '2026-10-20T00:00:00Z',
                                                  'text': 'Post insights\nViews\n24',
                                                  'age_gender_segments': [{'age': '25-34', 'gender': 'MALE',
                                                                           'bar_width': '95.8%'}],
                                                  'discovery_panels': [{'selected_tab': 'Source',
                                                                         'text': 'Traffic\nSource\nSearch\n4.2%'}]}]}))
        import_export(self.csv, self.output, '456', [source])
        data = json.loads(self.output.read_text())
        self.assertEqual(data['unmatched_dashboard_snapshots'], [])
        snapshot = data['posts'][0]['dashboard_snapshots'][0]
        self.assertEqual(snapshot['age_and_gender'][0]['gender'], 'MALE')
        self.assertEqual(snapshot['age_and_gender'][0]['percentage'], 95.8)
        self.assertEqual(snapshot['how_people_find_content'][0]['tab'], 'Source')
        self.assertEqual(snapshot['how_people_find_content'][0]['percentages'], {'Search': 4.2})

    def test_missing_daily_values_and_wrong_page(self):
        self.write_rows([{**self.row, 'Seconds viewed': ''}])
        import_export(self.csv, self.output, '456')
        data = json.loads(self.output.read_text())['posts'][0]
        self.assertIsNone(data['export_period_totals']['seconds_viewed'])
        with self.assertRaises(AgentError):
            import_export(self.csv, self.root / 'wrong.json', '999')

    def test_summary_csv_import_without_daily_column(self):
        summary_row = {
            'Post ID': '123',
            'Page ID': '456',
            'Title': 'Summary Video',
            'Publish time': '10/18/2026 21:40',
            'Permalink': 'https://www.facebook.com/reel/789/',
            'Reactions': '25',
            'Comments': '5',
            'Shares': '2',
            'Seconds viewed': '500.5',
            'Average Seconds viewed': '20.0'
        }
        with self.csv.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(summary_row))
            writer.writeheader()
            writer.writerow(summary_row)
        import_export(self.csv, self.output, '456')
        data = json.loads(self.output.read_text())['posts'][0]
        self.assertEqual(data['breakdown'], 'summary')
        self.assertEqual(data['export_period_totals']['reactions'], 25.0)
        self.assertEqual(data['export_period_totals']['comments'], 5.0)
        self.assertEqual(data['average_seconds_viewed_aggregate'], 20.0)


if __name__ == '__main__':
    unittest.main()
