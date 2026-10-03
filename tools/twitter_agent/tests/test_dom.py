"""Local fixture browser tests for DOM extraction and browser lifecycle."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from playwright.sync_api import sync_playwright

from tools.twitter_agent import dom
from tools.twitter_agent.browser import Browser
from tools.twitter_agent.models import AgentError, draft_digest
from tools.twitter_agent.posts import read_posts
from tools.twitter_agent.replies import inspect_reply, prepare_reply, submit_reply


class DomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()

    def test_extraction_uses_dom_identifiers(self):
        self.page.set_content('''<article data-testid="customTweet">
  <div data-testid="User-Name">Alice @alice</div>
  <a href="/alice/status/123"><time>now</time></a>
  <div data-testid="tweetText">Outer text</div>
  <div data-testid="quoteTweet">
    <div data-testid="tweetText">Quoted text</div>
    <a href="/bob/status/456"><time>earlier</time></a>
  </div>
  <button data-testid="reply">2</button>
  <button data-testid="retweet">3</button>
  <button data-testid="like">4</button>
  <a href="/alice/status/123/analytics">1K</a>
</article>''')
        with patch.object(dom, 'ARTICLE', 'article[data-testid="customTweet"]'):
            post = read_posts(self.page, 'timeline', None, 1)['posts'][0]
        self.assertEqual(post['id'], '123')
        self.assertEqual(post['text'], 'Outer text')
        self.assertEqual(post['metrics'], {
            'replies': 2, 'retweets': 3, 'likes': 4, 'views': 1000, 'total': 9,
        })

    def test_textless_outer_tweet_with_quoted_tweet(self):
        self.page.set_content('''<article data-testid="tweet">
  <div data-testid="User-Name">Alice @alice</div>
  <a href="/alice/status/123"><time datetime="2026-09-29T10:00:00Z">now</time></a>
  <div role="link"><div data-testid="tweetText">Quoted text</div>
    <a href="/bob/status/456"><time>earlier</time></a></div>
</article>''')
        result = read_posts(self.page, 'timeline', None, 1)
        self.assertEqual(len(result['posts']), 1)
        self.assertEqual(result['posts'][0]['id'], '123')
        self.assertEqual(result['posts'][0]['url'], 'https://x.com/i/status/123')
        self.assertEqual(result['posts'][0]['text'], '')
        self.assertEqual(result['posts'][0]['author']['handle'], '@alice')
        self.assertEqual(result['posts'][0]['timestamp'], '2026-09-29T10:00:00Z')

    def test_dom_is_inside_quote_preserves_anchor_time(self):
        self.page.set_content('''<article data-testid="tweet">
  <div data-testid="User-Name">Alice @alice</div>
  <a role="link" href="/alice/status/123"><time datetime="2026-09-29T10:00:00Z">now</time></a>
  <div data-testid="tweetText">Hello anchor time</div>
</article>''')
        result = read_posts(self.page, 'timeline', None, 1)
        self.assertEqual(len(result['posts']), 1)
        self.assertEqual(result['posts'][0]['timestamp'], '2026-09-29T10:00:00Z')
        self.assertFalse(result['posts'][0].get('is_ad', False))

    def test_dom_ad_detection(self):
        self.page.set_content('''<article data-testid="tweet">
  <div data-testid="User-Name">Sponsor @sponsor</div>
  <a href="/sponsor/status/999"><time datetime="2026-09-29T10:00:00Z">now</time></a>
  <span>Ad</span>
  <div data-testid="tweetText">Sponsored post</div>
</article>''')
        result = read_posts(self.page, 'timeline', None, 1)
        self.assertEqual(len(result['posts']), 1)
        self.assertTrue(result['posts'][0].get('is_ad', False))

    def test_empty_timeline(self):
        self.page.set_content('<div data-testid="primaryColumn"><div>No posts here</div></div>')
        result = read_posts(self.page, 'timeline', None, 5)
        self.assertEqual(result['posts'], [])
        self.assertEqual(result['reason'], 'no_progress')

    def test_duplicate_virtualized_posts_deduplicated(self):
        # Multiple articles with same tweet ID
        self.page.set_content('''<div>
  <article data-testid="tweet">
    <div data-testid="User-Name">Alice @alice</div>
    <a href="/alice/status/101"><time datetime="2026-09-29T10:00:00Z">now</time></a>
    <div data-testid="tweetText">First post</div>
  </article>
  <article data-testid="tweet">
    <div data-testid="User-Name">Bob @bob</div>
    <a href="/bob/status/102"><time datetime="2026-09-29T10:01:00Z">now</time></a>
    <div data-testid="tweetText">Second post</div>
  </article>
  <article data-testid="tweet">
    <div data-testid="User-Name">Alice @alice</div>
    <a href="/alice/status/101"><time datetime="2026-09-29T10:00:00Z">now</time></a>
    <div data-testid="tweetText">First post duplicate</div>
  </article>
</div>''')
        result = read_posts(self.page, 'timeline', None, 10)
        self.assertEqual(len(result['posts']), 2)
        self.assertEqual([p['id'] for p in result['posts']], ['101', '102'])

    def test_scroll_budget_stops_at_limit(self):
        articles = ''.join(f'''<article data-testid="tweet">
          <div data-testid="User-Name">User{i} @user{i}</div>
          <a href="/user{i}/status/{1000 + i}"><time>now</time></a>
          <div data-testid="tweetText">Post number {i}</div>
        </article>''' for i in range(10))
        self.page.set_content(f'<div>{articles}</div>')
        result = read_posts(self.page, 'timeline', None, 3)
        self.assertEqual(len(result['posts']), 3)
        self.assertEqual(result['reason'], 'limit_reached')
        self.assertFalse(result['partial'])

    def test_limit_validation(self):
        with self.assertRaises(AgentError) as ctx:
            read_posts(self.page, 'timeline', None, 0)
        self.assertEqual(ctx.exception.code, 'invalid_limit')

        with self.assertRaises(AgentError) as ctx:
            read_posts(self.page, 'timeline', None, 101)
        self.assertEqual(ctx.exception.code, 'invalid_limit')

    def test_thread_mode_identifies_target(self):
        self.page.set_content('''<div>
  <article data-testid="tweet">
    <div data-testid="User-Name">Target Author @author</div>
    <a href="/author/status/555"><time>now</time></a>
    <div data-testid="tweetText">Target post</div>
  </article>
  <article data-testid="tweet">
    <div data-testid="User-Name">Reply Author @replier</div>
    <a href="/replier/status/556"><time>now</time></a>
    <div data-testid="tweetText">A reply</div>
  </article>
</div>''')
        result = read_posts(self.page, 'thread', '555', 5)
        self.assertTrue(result['partial'])
        self.assertIsNotNone(result['target'])
        self.assertEqual(result['target']['id'], '555')
        self.assertEqual(len(result['posts']), 2)

    def test_block_detection_raises_typed_error(self):
        self.page.set_content('<div>Your account has been locked</div>')
        with self.assertRaises(AgentError) as ctx:
            read_posts(self.page, 'timeline', None, 5)
        self.assertEqual(ctx.exception.code, 'account_blocked')

    def test_lifecycle_preserves_existing_tabs(self):
        mock_playwright = MagicMock()
        mock_chromium = MagicMock()
        mock_playwright.chromium = mock_chromium
        mock_cdp_browser = MagicMock()
        mock_chromium.connect_over_cdp.return_value = mock_cdp_browser

        mock_context = MagicMock()
        mock_cdp_browser.contexts = [mock_context]
        existing_page1 = MagicMock()
        existing_page2 = MagicMock()
        mock_context.pages = [existing_page1, existing_page2]

        temp_page = MagicMock()
        mock_context.new_page.return_value = temp_page

        with patch('tools.twitter_agent.browser.sync_playwright') as mock_sync:
            mock_sync.return_value.start.return_value = mock_playwright
            browser = Browser(endpoint='http://127.0.0.1:9222')
            with browser:
                page = browser.new_page()
                self.assertEqual(page, temp_page)

        # Temp page was closed
        temp_page.close.assert_called_once()
        # Existing pages were NEVER closed
        existing_page1.close.assert_not_called()
        existing_page2.close.assert_not_called()
        # CDP browser.close() was NOT called on user's browser
        mock_cdp_browser.close.assert_not_called()
        # Playwright was stopped
        mock_playwright.stop.assert_called_once()

    def test_prepare_and_inspect_reply(self):
        self.page.set_content('''<div>
  <article data-testid="tweet">
    <div data-testid="User-Name">Alice @alice</div>
    <a href="/alice/status/777"><time>now</time></a>
    <div data-testid="tweetText">Hello world</div>
    <button data-testid="reply">Reply</button>
  </article>
  <div role="dialog" style="display:none;">
    <div data-testid="tweetTextarea_0" contenteditable="true"></div>
    <button data-testid="tweetButton">Post</button>
  </div>
</div>''')
        # Simulate dialog appearing when reply clicked
        self.page.evaluate('''() => {
            const btn = document.querySelector('button[data-testid="reply"]');
            btn.addEventListener('click', () => {
                document.querySelector('div[role="dialog"]').style.display = 'block';
            });
        }''')

        with tempfile.TemporaryDirectory() as tmp_dir:
            draft = {
                'id': 'd1',
                'target_id': '777',
                'target_url': 'https://x.com/i/status/777',
                'text': 'Nice tweet!',
                'digest': draft_digest('777', 'Nice tweet!'),
            }
            res = prepare_reply(self.page, draft, Path(tmp_dir))
            self.assertEqual(res['target_id'], '777')
            self.assertEqual(res['reply_text'], 'Nice tweet!')

            digest = inspect_reply(self.page, draft)
            self.assertEqual(digest, draft['digest'])

    def test_quoted_target_confusion_raises_target_not_found(self):
        self.page.set_content('''<article data-testid="tweet">
  <div data-testid="User-Name">Alice @alice</div>
  <a href="/alice/status/111"><time>now</time></a>
  <div role="link">
    <a href="/bob/status/222"><time>earlier</time></a>
  </div>
</article>''')
        with tempfile.TemporaryDirectory() as tmp_dir:
            draft = {'id': 'd2', 'target_id': '222', 'target_url': 'https://x.com/i/status/222', 'text': 'Hi'}
            with self.assertRaises(AgentError) as ctx:
                prepare_reply(self.page, draft, Path(tmp_dir))
            self.assertEqual(ctx.exception.code, 'target_not_found')

    def test_disabled_submit_button_detected(self):
        self.page.set_content('''<div role="dialog">
  <div data-testid="tweetTextarea_0" contenteditable="true">Hello</div>
  <button data-testid="tweetButton" aria-disabled="true">Post</button>
</div>''')
        draft = {'id': 'd3', 'target_id': '111', 'text': 'Hello'}
        with self.assertRaises(AgentError) as ctx:
            inspect_reply(self.page, draft)
        self.assertEqual(ctx.exception.code, 'submit_disabled')

    def test_submit_reply_confirmed_new_reply(self):
        self.page.set_content('''<div>
  <div data-testid="SideNav_AccountSwitcher_Button">@alice</div>
  <div role="dialog">
    <div data-testid="tweetTextarea_0" contenteditable="true">My reply text</div>
    <button data-testid="tweetButton">Post</button>
  </div>
  <div id="timeline"></div>
</div>''')
        # Simulate click appending a new tweet
        self.page.evaluate('''() => {
            const btn = document.querySelector('button[data-testid="tweetButton"]');
            btn.addEventListener('click', () => {
                const article = document.createElement('article');
                article.setAttribute('data-testid', 'tweet');
                article.innerHTML = `
                    <div data-testid="User-Name">Alice @alice</div>
                    <a href="/alice/status/888"><time>now</time></a>
                    <div data-testid="tweetText">My reply text</div>
                `;
                document.getElementById('timeline').appendChild(article);
            });
        }''')

        with tempfile.TemporaryDirectory() as tmp_dir:
            draft = {
                'id': 'd4',
                'target_id': '111',
                'text': 'My reply text',
                'digest': draft_digest('111', 'My reply text'),
            }
            outcome = submit_reply(self.page, draft, Path(tmp_dir))
            self.assertEqual(outcome['state'], 'submitted')
            self.assertEqual(outcome['reply_id'], '888')

    def test_submit_reply_composer_closed_without_new_reply_is_uncertain(self):
        self.page.set_content('''<div>
  <div data-testid="SideNav_AccountSwitcher_Button">@alice</div>
  <div role="dialog">
    <div data-testid="tweetTextarea_0" contenteditable="true">Uncertain text</div>
    <button data-testid="tweetButton">Post</button>
  </div>
</div>''')
        self.page.evaluate('''() => {
            const btn = document.querySelector('button[data-testid="tweetButton"]');
            btn.addEventListener('click', () => {
                document.querySelector('div[role="dialog"]').remove();
            });
        }''')

        with tempfile.TemporaryDirectory() as tmp_dir:
            draft = {
                'id': 'd5',
                'target_id': '111',
                'text': 'Uncertain text',
                'digest': draft_digest('111', 'Uncertain text'),
            }
            outcome = submit_reply(self.page, draft, Path(tmp_dir))
            self.assertEqual(outcome['state'], 'uncertain')
            self.assertEqual(outcome['reason'], 'confirmation_timeout')

    def test_tweet_scoring_algorithm(self):
        from tools.twitter_agent.posts import score_tweet
        # Fresh post (< 5 min), low replies (< 10), high velocity
        fresh_post = {
            'timestamp': '2026-09-29T20:56:00Z',
            'metrics': {'replies': 3, 'retweets': 20, 'likes': 100, 'total': 123}
        }
        # Reference now = 2026-09-29T21:00:00Z (4 min old)
        now_ts = 1790715600.0  # Unix timestamp corresponding to 21:00:00Z
        fresh_post_ts = 1790715360.0 # 20:56:00Z (4 min earlier)

        score_fresh = score_tweet(fresh_post, now=now_ts, post_timestamp_override=fresh_post_ts)
        self.assertGreater(score_fresh, 75.0)

        # Stale post (> 45 min), saturated replies (> 100)
        stale_post = {
            'timestamp': '2026-09-29T20:00:00Z',
            'metrics': {'replies': 150, 'retweets': 200, 'likes': 500, 'total': 850}
        }
        stale_post_ts = 1790712000.0 # 60 min earlier
        score_stale = score_tweet(stale_post, now=now_ts, post_timestamp_override=stale_post_ts)
        self.assertLess(score_stale, 40.0)
        self.assertGreater(score_fresh, score_stale)

    def test_read_posts_attaches_score(self):
        self.page.set_content('''<article data-testid="tweet">
  <div data-testid="User-Name">Alice @alice</div>
  <a href="/alice/status/123"><time datetime="2026-09-29T10:00:00Z">now</time></a>
  <div data-testid="tweetText">Hello</div>
</article>''')
        result = read_posts(self.page, 'timeline', None, 1)
        self.assertEqual(len(result['posts']), 1)
        self.assertIn('score', result['posts'][0])
        self.assertIsInstance(result['posts'][0]['score'], float)

    def test_score_tweet_ad_detection_zero(self):
        from tools.twitter_agent.posts import score_tweet
        ad_post = {
            'is_ad': True,
            'timestamp': '2026-09-29T21:00:00Z',
            'metrics': {'replies': 2, 'retweets': 50, 'likes': 200, 'total': 252}
        }
        self.assertEqual(score_tweet(ad_post), 0.0)

    def test_score_tweet_relative_timestamp(self):
        from tools.twitter_agent.posts import score_tweet
        now_ts = 1790715600.0
        # 3m old -> age_minutes = 3.0 -> age_factor = 1.0 (40 pts)
        fresh_post = {
            'timestamp': '3m',
            'metrics': {'replies': 2, 'retweets': 10, 'likes': 50, 'total': 62}
        }
        score_fresh = score_tweet(fresh_post, now=now_ts)
        self.assertGreater(score_fresh, 75.0)

        # 2h old -> age_minutes = 120.0 -> age_factor = 0.1 (4 pts)
        stale_post = {
            'timestamp': '2h',
            'metrics': {'replies': 2, 'retweets': 10, 'likes': 50, 'total': 62}
        }
        score_stale = score_tweet(stale_post, now=now_ts)
        self.assertLess(score_stale, 55.0)
        self.assertGreater(score_fresh, score_stale)


class SearchModeTests(unittest.TestCase):
    @patch('tools.twitter_agent.posts.selectors.detect_block', return_value=None)
    def test_top_navigation(self, _detect):
        from urllib.parse import parse_qs, urlsplit
        page = MagicMock()
        page.url = 'https://x.com/home'
        page.evaluate.return_value = [{'id': '1', 'metrics': {'total': 0}}]
        read_posts(page, 'search', 'AI agents', limit=1, search_mode='top')
        params = parse_qs(urlsplit(page.goto.call_args.args[0]).query)
        self.assertEqual(params['q'], ['AI agents'])
        self.assertEqual(params['f'], ['top'])

    @patch('tools.twitter_agent.posts.selectors.detect_block', return_value=None)
    def test_latest_default_navigation(self, _detect):
        from urllib.parse import parse_qs, urlsplit
        page = MagicMock()
        page.url = 'https://x.com/home'
        page.evaluate.return_value = [{'id': '1', 'metrics': {'total': 0}}]
        read_posts(page, 'search', 'AI agents', limit=1)
        params = parse_qs(urlsplit(page.goto.call_args.args[0]).query)
        self.assertEqual(params['q'], ['AI agents'])
        self.assertEqual(params['f'], ['live'])

    def test_invalid_search_mode_raises(self):
        page = MagicMock()
        with self.assertRaises(AgentError) as raised:
            read_posts(page, 'search', 'AI agents', limit=1, search_mode='invalid_mode')
        self.assertEqual(raised.exception.code, 'invalid_search_mode')
