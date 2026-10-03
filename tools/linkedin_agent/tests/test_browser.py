"""Mocked CDP lifecycle and offline Chromium DOM coverage; never visits LinkedIn."""

import subprocess
import io
import json
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import Mock, patch

from playwright.sync_api import sync_playwright

from tools.linkedin_agent.models import AgentError


class BrowserLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.context = Mock()
        self.chrome = Mock(contexts=[self.context])
        self.runtime = Mock()
        self.runtime.chromium.connect_over_cdp.return_value = self.chrome
        self.factory = patch('playwright.sync_api.sync_playwright').start()
        self.factory.return_value.start.return_value = self.runtime
        self.addCleanup(patch.stopall)

    def connected_browser(self, **kwargs):
        from tools.linkedin_agent.browser import Browser
        return Browser(**kwargs)

    def test_cdp_endpoint_and_timeout(self):
        with self.connected_browser(endpoint='http://localhost:9333', timeout_ms=3210):
            self.runtime.chromium.connect_over_cdp.assert_called_once_with(
                'http://localhost:9333', timeout=3210)

    def test_user_browser_is_not_closed(self):
        with self.connected_browser() as connection:
            connection.new_page()
        self.chrome.close.assert_not_called()
        self.runtime.stop.assert_called_once()

    def test_only_owned_tabs_are_closed(self):
        existing = Mock()
        self.context.pages = [existing]
        with self.connected_browser() as connection:
            owned = connection.new_page()
            owned.set_default_timeout.assert_called_once_with(15000)
        owned.close.assert_called_once()
        existing.close.assert_not_called()

    def test_preserved_page_is_left_open(self):
        with self.connected_browser() as connection:
            page = connection.new_page()
            connection.preserve_page(page)
            connection.preserve_page(page)
        page.close.assert_not_called()
        self.runtime.stop.assert_called_once()

    def test_cleanup_on_body_exception(self):
        with self.assertRaisesRegex(ValueError, 'body'):
            with self.connected_browser() as connection:
                page = connection.new_page()
                raise ValueError('body')
        page.close.assert_called_once()
        self.runtime.stop.assert_called_once()

    def test_page_close_failure_does_not_prevent_disconnect(self):
        with self.connected_browser() as connection:
            page = connection.new_page()
            page.close.side_effect = RuntimeError('closed already')
        self.runtime.stop.assert_called_once()

    def test_missing_context_is_structured_and_disconnects(self):
        self.chrome.contexts = []
        with self.assertRaises(AgentError) as caught:
            with self.connected_browser():
                self.fail('Should not enter without a context')
        self.assertEqual(caught.exception.code, 'no_browser_context')
        self.assertTrue(caught.exception.human_action_required)
        self.runtime.stop.assert_called_once()
        self.chrome.close.assert_not_called()

    def test_connection_failure_is_structured_and_disconnects(self):
        self.runtime.chromium.connect_over_cdp.side_effect = RuntimeError('offline')
        with self.assertRaises(AgentError) as caught:
            with self.connected_browser():
                self.fail('Should not enter while offline')
        self.assertEqual(caught.exception.code, 'browser_connection_failed')
        self.assertTrue(caught.exception.human_action_required)
        self.runtime.stop.assert_called_once()

    def test_secret_endpoint_is_used_but_not_exposed_on_connection_failure(self):
        endpoint = 'wss://user:password@example.test/path-token?query-token=secret#fragment-token'
        self.runtime.chromium.connect_over_cdp.side_effect = RuntimeError(endpoint)
        with self.assertRaises(AgentError) as caught:
            with self.connected_browser(endpoint=endpoint):
                self.fail('offline')
        self.runtime.chromium.connect_over_cdp.assert_called_once_with(endpoint, timeout=15000)
        for secret in ('user', 'password', 'path-token', 'query-token', 'secret', 'fragment-token'):
            self.assertNotIn(secret, str(caught.exception))

    def test_cli_connection_failure_omits_endpoint_and_underlying_exception(self):
        from tools.linkedin_agent.cli import main
        endpoint = 'https://user:password@example.test/path-token?query-token=secret#fragment-token'
        self.runtime.chromium.connect_over_cdp.side_effect = RuntimeError(endpoint)
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(['--cdp', endpoint, 'doctor'])
        self.assertEqual(status, 3)
        self.assertEqual(json.loads(stdout.getvalue())['error']['code'], 'browser_connection_failed')
        for secret in ('password', 'path-token', 'query-token', 'fragment-token', 'Traceback'):
            self.assertNotIn(secret, stdout.getvalue() + stderr.getvalue())
        self.runtime.chromium.connect_over_cdp.assert_called_once_with(endpoint, timeout=15000)

    def test_nonpositive_timeouts_are_rejected_before_connection(self):
        for timeout in (0, -1):
            with self.subTest(timeout=timeout), self.assertRaises(AgentError) as caught:
                self.connected_browser(timeout_ms=timeout)
            self.assertEqual(caught.exception.code, 'invalid_timeout')
        self.factory.assert_not_called()

    def test_disconnected_operations_are_structured(self):
        connection = self.connected_browser()
        for operation in (connection.new_page, connection.doctor):
            with self.assertRaises(AgentError) as caught:
                operation()
            self.assertEqual(caught.exception.code, 'browser_not_connected')
        with connection:
            pass
        with self.assertRaises(AgentError):
            connection.new_page()


class SyntheticDOMTests(unittest.TestCase):
    MODERN_HOME = ('<nav><button aria-label="Home, 1 new notification" aria-current="true">'
                   '<span>Home</span></button></nav>')
    MODERN_START = ('<div role="button" tabindex="0" id="start-post">'
                    '<div aria-label="Start a post">Start a post</div></div>')

    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.chrome = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.chrome.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.chrome.new_page()
        self.addCleanup(self.page.close)

    def assert_block(self, html, code):
        from tools.linkedin_agent.selectors import detect_block
        self.page.set_content(html)
        with self.assertRaises(AgentError) as caught:
            detect_block(self.page)
        self.assertEqual(caught.exception.code, code)
        self.assertTrue(caught.exception.human_action_required)

    def test_login_form_requires_human_authentication(self):
        self.assert_block('<form action="/uas/login-submit"><input name="session_key">'
                          '<input name="session_password" type="password"></form>',
                          'not_authenticated')

    def test_checkpoint_form_requires_human_intervention(self):
        self.assert_block('<form action="/checkpoint/challenge/verify">'
                          '<input name="pin"></form>', 'browser_challenge')

    def test_captcha_requires_human_intervention(self):
        self.assert_block('<iframe title="captcha" src="about:blank"></iframe>',
                          'browser_challenge')

    def test_checkpoint_takes_priority_over_login(self):
        self.assert_block('<form action="/checkpoint/challenge">'
                          '<input name="session_password"></form>', 'browser_challenge')

    def test_login_and_checkpoint_urls(self):
        from tools.linkedin_agent.selectors import detect_block
        for url, code in [('https://www.linkedin.com/login', 'not_authenticated'),
                          ('https://www.linkedin.com/uas/login', 'not_authenticated'),
                          ('https://www.linkedin.com/checkpoint/challenge', 'browser_challenge')]:
            with self.subTest(url=url), self.assertRaises(AgentError) as caught:
                detect_block(Mock(url=url, locator=self.page.locator))
            self.assertEqual(caught.exception.code, code)

    def test_authenticated_feed_is_not_blocked(self):
        from tools.linkedin_agent.selectors import detect_block
        self.page.set_content('<nav id="global-nav"><a href="/feed/">Home</a></nav>'
                              '<button>Start a post</button>')
        self.assertIsNone(detect_block(self.page))

    def test_hidden_login_form_does_not_block_authenticated_feed(self):
        from tools.linkedin_agent.selectors import detect_block
        self.page.set_content('<input name="session_password" style="display:none">')
        self.assertIsNone(detect_block(self.page))

    def run_doctor(self, html, navigation_error=None, after_start_wait=None, endpoint='http://127.0.0.1:9222',
                   feed_url='https://www.linkedin.com/feed/'):
        from tools.linkedin_agent.browser import Browser
        # Each doctor invocation owns and closes its own page, including subtests.
        dom_page = self.chrome.new_page()
        self.addCleanup(dom_page.close)
        page = Mock(wraps=dom_page)
        page.url = feed_url
        if after_start_wait:
            from tools.linkedin_agent import selectors

            def locate(selector):
                locator = dom_page.locator(selector)
                if selector != selectors.START_POST:
                    return locator
                wrapped = Mock(wraps=locator)

                def wait(**kwargs):
                    locator.wait_for(**kwargs)
                    # Mutate real DOM at the end of the second readiness wait.
                    dom_page.evaluate(after_start_wait)

                wrapped.wait_for.side_effect = wait
                return wrapped

            page.locator.side_effect = locate

        def navigate(*args, **kwargs):
            dom_page.set_content(html)
            if navigation_error:
                raise navigation_error

        page.goto.side_effect = navigate
        context = Mock()
        context.new_page.return_value = page
        runtime = Mock()
        runtime.chromium.connect_over_cdp.return_value = Mock(contexts=[context])
        with patch('playwright.sync_api.sync_playwright') as factory:
            factory.return_value.start.return_value = runtime
            with Browser(endpoint=endpoint, timeout_ms=150) as connection:
                result = connection.doctor()
        runtime.chromium.connect_over_cdp.assert_called_once_with(endpoint, timeout=150)
        page.goto.assert_called_once_with('https://www.linkedin.com/feed/',
                                          wait_until='domcontentloaded', timeout=150)
        page.close.assert_called_once()
        return result

    def test_doctor_authenticated_feed(self):
        result = self.run_doctor('<nav id="global-nav"><a href="/feed/">Home</a></nav>'
                                 '<button>Start a post</button>')
        self.assertEqual(result, {'connected': True, 'authenticated': True,
                                  })

    def test_doctor_accepts_current_home_navigation_button(self):
        self.assertEqual(self.run_doctor(self.MODERN_HOME + '<button>Start a post</button>'),
                         {'connected': True, 'authenticated': True})

    def test_doctor_accepts_focusable_start_post_container(self):
        self.assertEqual(self.run_doctor('<nav id="global-nav"><a href="/feed/">Home</a></nav>'
                                        + self.MODERN_START),
                         {'connected': True, 'authenticated': True})

    def test_doctor_accepts_modern_for_you_feed_without_opening_composer(self):
        self.assertEqual(self.run_doctor(self.MODERN_HOME + self.MODERN_START,
                                        feed_url='https://www.linkedin.com/feed/foryou/'),
                         {'connected': True, 'authenticated': True})

    def test_modern_start_post_selector_clicks_container_not_label(self):
        from tools.linkedin_agent import selectors
        self.page.set_content(self.MODERN_START + '<script>window.clicked=null;'
                              'document.querySelector("#start-post").onclick=event=>'
                              'window.clicked=event.currentTarget.id;</script>')
        start_post = selectors.wait_for_selector_or_block(self.page, selectors.START_POST, 150)
        self.assertEqual(start_post.get_attribute('id'), 'start-post')
        start_post.click()
        self.assertEqual(self.page.evaluate('window.clicked'), 'start-post')

    def test_doctor_rejects_modern_and_mixed_layout_ambiguity(self):
        for html in (
            self.MODERN_HOME * 2 + self.MODERN_START,
            self.MODERN_HOME + self.MODERN_START * 2,
            self.MODERN_HOME + '<nav id="global-nav"><a href="/feed/">Home</a></nav>'
            + self.MODERN_START,
            self.MODERN_HOME + self.MODERN_START + '<button>Start a post</button>',
            self.MODERN_HOME + self.MODERN_START
            + self.MODERN_START.replace('id="start-post"', 'style="display:none"'),
        ):
            with self.subTest(html=html), self.assertRaises(AgentError) as caught:
                self.run_doctor(html)
            self.assertEqual(caught.exception.code, 'ambiguous_selector')

    def test_doctor_does_not_accept_unscoped_or_incomplete_semantic_controls(self):
        for home in (
            '<a href="/feed/">Home</a>',
            '<button aria-label="Home, 1 new notification" aria-current="true">Home</button>',
            '<nav><button aria-label="Home, 1 new notification">Home</button></nav>',
            '<nav><button aria-label="Home, 1 new notification" aria-current="false">Home</button></nav>',
            '<nav><button aria-label="Notifications" aria-current="true">Home</button></nav>',
            '<nav><button aria-label="Home, 1 new notification" aria-current="true">Other</button></nav>',
        ):
            with self.subTest(home=home), self.assertRaises(AgentError) as caught:
                self.run_doctor(home + self.MODERN_START)
            self.assertEqual(caught.exception.code, 'dom_timeout')
        for start in (
            '<div aria-label="Start a post">Start a post</div>',
            '<div role="button"><div aria-label="Start a post">Start a post</div></div>',
            '<div tabindex="0"><div aria-label="Start a post">Start a post</div></div>',
            '<div role="button" tabindex="0">Start a post</div>',
        ):
            with self.subTest(start=start), self.assertRaises(AgentError) as caught:
                self.run_doctor('<nav id="global-nav"><a href="/feed/">Home</a></nav>' + start)
            self.assertEqual(caught.exception.code, 'dom_timeout')

    def test_doctor_omits_secret_bearing_endpoint(self):
        result = self.run_doctor('<nav id="global-nav"><a href="/feed/">Home</a></nav>'
                                 '<button>Start a post</button>',
                                 endpoint='https://user:password@example.test/path-token?query-token=secret#fragment-token')
        self.assertEqual(result, {'connected': True, 'authenticated': True})

    def test_doctor_waits_for_delayed_controls(self):
        result = self.run_doctor('<script>setTimeout(() => {document.body.innerHTML = '
                                 '\'<nav id="global-nav"><a href="/feed/">Home</a></nav>'
                                 '<button>Start a post</button>\';}, 30)</script>')
        self.assertTrue(result['authenticated'])

    def test_doctor_rejects_login_checkpoint_and_unknown_dom(self):
        for html, code in [('<input name="session_password">', 'not_authenticated'),
                           ('<form action="/checkpoint/challenge"></form>', 'browser_challenge'),
                           ('<main>Unknown page</main>', 'dom_timeout')]:
            with self.subTest(code=code), self.assertRaises(AgentError) as caught:
                self.run_doctor(html)
            self.assertEqual(caught.exception.code, code)

    def test_doctor_rechecks_blocks_after_wait_timeout(self):
        with self.assertRaises(AgentError) as caught:
            self.run_doctor('<script>setTimeout(() => {document.body.innerHTML = '
                            '\'<input name="session_password">\';}, 30)</script>')
        self.assertEqual(caught.exception.code, 'not_authenticated')

    def test_doctor_rejects_ambiguous_controls(self):
        with self.assertRaises(AgentError) as caught:
            self.run_doctor('<nav id="global-nav"><a href="/feed/">Home</a></nav>'
                            '<button>Start a post</button><button>Start a post</button>')
        self.assertEqual(caught.exception.code, 'ambiguous_selector')

    def test_doctor_rechecks_home_removed_during_start_post_wait(self):
        with self.assertRaises(AgentError) as caught:
            self.run_doctor('<nav id="global-nav"><a href="/feed/">Home</a></nav>'
                            '<button>Start a post</button>',
                            after_start_wait='document.querySelector("#global-nav a").remove()')
        self.assertEqual(caught.exception.code, 'dom_timeout')

    def test_doctor_rechecks_home_duplicated_during_start_post_wait(self):
        with self.assertRaises(AgentError) as caught:
            self.run_doctor('<nav id="global-nav"><a href="/feed/">Home</a></nav>'
                            '<button>Start a post</button>',
                            after_start_wait='document.querySelector("#global-nav").innerHTML += '
                                             '\'<a href="/feed/">Home</a>\'')
        self.assertEqual(caught.exception.code, 'ambiguous_selector')

    def test_doctor_rechecks_home_hidden_during_start_post_wait(self):
        with self.assertRaises(AgentError) as caught:
            self.run_doctor('<nav id="global-nav"><a href="/feed/">Home</a></nav>'
                            '<button>Start a post</button>',
                            after_start_wait='document.querySelector("#global-nav").style.display = "none"')
        self.assertEqual(caught.exception.code, 'dom_timeout')

    def test_doctor_rechecks_start_post_visibility_after_wait(self):
        with self.assertRaises(AgentError) as caught:
            self.run_doctor('<nav id="global-nav"><a href="/feed/">Home</a></nav>'
                            '<button>Start a post</button>',
                            after_start_wait='document.querySelector("button").style.display = "none"')
        self.assertEqual(caught.exception.code, 'dom_timeout')

    def test_doctor_classifies_navigation_failure(self):
        with self.assertRaises(AgentError) as caught:
            self.run_doctor('<main>Offline</main>', RuntimeError('offline'))
        self.assertEqual(caught.exception.code, 'browser_navigation_failed')

    def test_doctor_detects_checkpoint_even_on_navigation_failure(self):
        with self.assertRaises(AgentError) as caught:
            self.run_doctor('<form action="/checkpoint/challenge"></form>', RuntimeError('redirect'))
        self.assertEqual(caught.exception.code, 'browser_challenge')


class LauncherTests(unittest.TestCase):
    def test_help_uses_shared_profile_and_port(self):
        script = Path(__file__).resolve().parents[1] / 'launch_browser.sh'
        result = subprocess.run(['bash', str(script), '--port', '9333', '--data-dir',
                                 '/unused/profile with spaces', '--help'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('chrome-twitter-profile', result.stdout)
        self.assertIn('9222', result.stdout)


if __name__ == '__main__':
    unittest.main()
