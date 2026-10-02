import json
import tempfile
import unittest
from pathlib import Path

from tools.twitter_agent.models import AgentError
from tools.twitter_agent.topic_config import load_topics, build_topic_query


class TopicConfigTests(unittest.TestCase):
    def test_query_preserves_phrases_and_scopes_time(self):
        topic = {
            'id': 'ai',
            'name': 'AI',
            'search_keywords': ['"agent orchestration"', 'AI security', 'CrewAI']
        }
        self.assertEqual(
            build_topic_query(topic, start=100, end=200),
            '("agent orchestration" OR "AI security" OR CrewAI) since_time:100 until_time:200'
        )

    def test_duplicate_ids_rejected(self):
        topic = {'id': 'ai', 'name': 'AI', 'search_keywords': ['AI']}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'topics.json'
            path.write_text(json.dumps({'topics': [topic, topic]}), encoding='utf-8')
            with self.assertRaises(AgentError) as raised:
                load_topics(path)
        self.assertEqual(raised.exception.code, 'invalid_topics_file')

    def test_file_read_and_json_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'nonexistent.json'
            with self.assertRaises(AgentError) as raised:
                load_topics(p)
            self.assertEqual(raised.exception.code, 'invalid_topics_file')

            invalid_utf8 = Path(directory) / 'bad_utf8.json'
            invalid_utf8.write_bytes(b'\xff\xfe\xfa')
            with self.assertRaises(AgentError) as raised:
                load_topics(invalid_utf8)
            self.assertEqual(raised.exception.code, 'invalid_topics_file')

            malformed_json = Path(directory) / 'bad.json'
            malformed_json.write_text('{topics: [}', encoding='utf-8')
            with self.assertRaises(AgentError) as raised:
                load_topics(malformed_json)
            self.assertEqual(raised.exception.code, 'invalid_topics_file')

    def test_schema_structure_validations(self):
        cases = [
            ([], 'must be a JSON object'),
            ({}, "missing required 'topics' list"),
            ({'topics': 'not a list'}, "'topics' must be a list"),
            ({'topics': []}, "'topics' list cannot be empty"),
            ({'topics': ['not a dict']}, 'topics[0]: must be an object'),
            ({'topics': [{'name': 'AI', 'search_keywords': ['AI']}]}, "topics[0]: missing required 'id'"),
            ({'topics': [{'id': '', 'name': 'AI', 'search_keywords': ['AI']}]}, "topics[0].id: cannot be empty"),
            ({'topics': [{'id': 'ai', 'search_keywords': ['AI']}]}, "topics[0]: missing required 'name'"),
            ({'topics': [{'id': 'ai', 'name': ' ', 'search_keywords': ['AI']}]}, "topics[0].name: cannot be empty"),
            ({'topics': [{'id': 'ai', 'name': 'AI'}]}, "topics[0]: missing required 'search_keywords'"),
            ({'topics': [{'id': 'ai', 'name': 'AI', 'search_keywords': 'not a list'}]}, "topics[0].search_keywords: must be a list"),
            ({'topics': [{'id': 'ai', 'name': 'AI', 'search_keywords': []}]}, "topics[0].search_keywords: cannot be empty"),
            ({'topics': [{'id': 'ai', 'name': 'AI', 'search_keywords': [123]}]}, "topics[0].search_keywords[0]: must be a string"),
            ({'topics': [{'id': 'ai', 'name': 'AI', 'search_keywords': ['   ']}]}, "topics[0].search_keywords[0]: cannot be empty"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            for payload, expected_snippet in cases:
                path = Path(directory) / 'case.json'
                path.write_text(json.dumps(payload), encoding='utf-8')
                with self.assertRaises(AgentError, msg=f'Failed on {payload}') as raised:
                    load_topics(path)
                self.assertEqual(raised.exception.code, 'invalid_topics_file')
                self.assertIn(expected_snippet, raised.exception.message)

    def test_keyword_syntax_and_operators_rejected(self):
        invalid_keywords = [
            '""',
            '"   "',
            '"unbalanced',
            'unbalanced"',
            'embedded"quote',
            '"embedded"quote"',
            'foo\nbar',
            'foo\tbar',
            'has:colon',
            'has(paren)',
            'AND',
            'OR',
            'NOT',
        ]
        for kw in invalid_keywords:
            topic = {'id': 't1', 'name': 'Topic 1', 'search_keywords': [kw]}
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'kw.json'
                path.write_text(json.dumps({'topics': [topic]}), encoding='utf-8')
                with self.assertRaises(AgentError, msg=f'Failed to reject {kw!r}') as raised:
                    load_topics(path)
                self.assertEqual(raised.exception.code, 'invalid_topics_file')

            # Also check build_topic_query raises AgentError
            with self.assertRaises(AgentError, msg=f'build_topic_query did not reject {kw!r}'):
                build_topic_query(topic, start=10, end=20)

    def test_bundled_topics_json_validates_cleanly(self):
        bundled_path = Path(__file__).parent.parent / 'topics' / 'topics.json'
        configured = json.loads(bundled_path.read_text(encoding='utf-8'))['topics']
        topics = load_topics(bundled_path)
        self.assertTrue(topics)
        self.assertEqual(topics, configured)
        # Verify every configured topic is preserved and produces a query.
        for topic in topics:
            with self.subTest(topic=topic['id']):
                query = build_topic_query(topic, start=1000, end=2000)
                self.assertTrue(query.startswith('('))
                self.assertIn('since_time:1000 until_time:2000', query)

    def test_all_topic_folder_configs_validate(self):
        folder = Path(__file__).parent.parent / 'topics'
        configs = list(folder.glob('*.json'))
        self.assertTrue(configs)
        for path in configs:
            with self.subTest(config=path.name):
                for topic in load_topics(path):
                    self.assertIn('since_time:100 until_time:200',
                                  build_topic_query(topic, start=100, end=200))

    def test_template_matches_reference_config_fields(self):
        folder = Path(__file__).parent.parent / 'topics'
        template = json.loads((folder / 'template.json').read_text(encoding='utf-8'))
        reference = json.loads((folder / 'topics_vietnam_blockchain_legal.json').read_text(encoding='utf-8'))
        self.assertEqual(set(template), set(reference))
        for topic in template['topics']:
            self.assertEqual(set(topic), set(reference['topics'][0]))
        # Report validation preserves the contextual fields rather than dropping them.
        self.assertEqual(load_topics(folder / 'template.json'), template['topics'])


if __name__ == '__main__':
    unittest.main()
