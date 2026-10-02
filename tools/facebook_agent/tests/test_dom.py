"""Real Playwright tests against intercepted local HTML, never Facebook."""

import base64
from pathlib import Path
import tempfile
import unittest

from playwright.sync_api import sync_playwright

from tools.facebook_agent.models import AgentError
from tools.facebook_agent.posting import publish, inspect_profile


FIXTURE = '''<!doctype html><html><body>
<h1>Alice Example</h1><button>Edit profile</button>
<button onclick="document.querySelector('[role=dialog]').hidden=false">
What's on your mind, Alice?</button>
<div role="dialog" aria-label="Create post" hidden>
  <h2>Create post</h2><h3>Alice Example</h3>
  <button id="audience" aria-label="Edit privacy">Friends</button>
  <div role="textbox" contenteditable="true" style="white-space: pre-wrap" aria-label="What's on your mind, Alice?"></div>
  <input type="file" accept="image/*" onchange="document.querySelector('#preview').hidden=false">
  <button id="preview" aria-label="Remove photo" hidden>Remove photo</button>
  <button id="post" onclick="submitPost()">Post</button>
</div>
<script>
window.clicks = 0;
function submitPost() {
  window.clicks++;
  window.submittedText = document.querySelector('[role=textbox]').innerText;
  document.querySelector('[role=dialog]').hidden=true;
  let toast=document.createElement('div'); toast.setAttribute('role','status');
  toast.textContent='Your post has been shared.'; document.body.appendChild(toast);
}
</script></body></html>'''


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
        self.context = self.browser.new_context(offline=True)
        self.page = self.context.new_page()
        self.page.set_default_timeout(500)
        self.html = FIXTURE

        def route(request):
            # Playwright does not route subsequent requests in an HTTP redirect
            # chain. Use same-origin history instead, keeping fixtures offline.
            request.fulfill(body=self.html + "<script>history.replaceState(null, '', '/alice.example')</script>",
                            content_type='text/html')

        self.page.route('**/*', route)

    def tearDown(self):
        self.context.close()

    def test_publishes_exact_text_once(self):
        result = publish(self.page, 'Hello 👋\nWorld', timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(result['profile']['name'], 'Alice Example')
        self.assertEqual(result['audience'], 'Friends')
        self.assertEqual(self.page.evaluate('window.clicks'), 1)
        self.assertEqual(self.page.evaluate('window.submittedText'), 'Hello 👋\nWorld')

    def test_publishes_image_after_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'photo.png'
            image.write_bytes(base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII='))
            result = publish(self.page, 'Photo', image=image, timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(self.page.locator('input').evaluate('(el) => el.files[0].name'), 'photo.png')
        self.assertEqual(self.page.evaluate('window.clicks'), 1)

    def test_missing_confirmation_is_uncertain_not_retry(self):
        self.html = FIXTURE.replace("toast.textContent='Your post has been shared.'", "toast.textContent='Working'")
        result = publish(self.page, 'Hello', timeout_ms=200)
        self.assertEqual(result['status'], 'uncertain')
        self.assertEqual(self.page.evaluate('window.clicks'), 1)

    def test_old_success_toast_does_not_confirm_new_post(self):
        self.html = FIXTURE.replace('<h1>', '<div role="status">Your post has been shared.</div><h1>')
        self.html = self.html.replace("toast.textContent='Your post has been shared.'", "toast.textContent='Working'")
        self.assertEqual(publish(self.page, 'Hello', timeout_ms=200)['status'], 'uncertain')

    def test_foreign_profile_cannot_post(self):
        self.html = FIXTURE.replace('<button>Edit profile</button>', '')
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Hello', timeout_ms=200)
        self.assertEqual(error.exception.code, 'not_personal_profile')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_page_management_controls_rejected(self):
        self.html = FIXTURE.replace('<h1>', '<button>Manage Page</button><h1>')
        with self.assertRaises(AgentError):
            publish(self.page, 'Hello', timeout_ms=200)
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_ambiguous_post_buttons_stop_before_click(self):
        self.html = FIXTURE.replace('<button id="post"', '<button>Post</button><button id="post"')
        with self.assertRaises(AgentError):
            publish(self.page, 'Hello', timeout_ms=200)
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_changed_text_stops_before_click(self):
        self.html = FIXTURE.replace('contenteditable="true"',
                                    'contenteditable="true" oninput="this.textContent=\'Changed\'"')
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Hello', timeout_ms=200)
        self.assertEqual(error.exception.code, 'content_changed')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_disabled_post_stops_before_click(self):
        self.html = FIXTURE.replace('<button id="post"', '<button disabled id="post"')
        with self.assertRaises(AgentError):
            publish(self.page, 'Hello', timeout_ms=200)
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_missing_image_preview_stops_before_click(self):
        self.html = FIXTURE.replace("document.querySelector('#preview').hidden=false", 'void(0)')
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'photo.png'
            image.write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 20)
            with self.assertRaises(AgentError):
                publish(self.page, 'Photo', image=image, timeout_ms=200)
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_actor_must_match_profile(self):
        self.html = FIXTURE.replace('<h3>Alice Example</h3>', '<h3>Other User</h3>')
        with self.assertRaises(AgentError):
            publish(self.page, 'Hello', timeout_ms=200)
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_doctor_returns_profile_without_opening_composer(self):
        result = inspect_profile(self.page, timeout_ms=500)
        self.assertEqual(result['name'], 'Alice Example')
        self.assertFalse(self.page.get_by_role('dialog').is_visible())

    def test_login_required(self):
        self.html = '<input name="email"><input name="pass"><button>Log in</button>'
        with self.assertRaises(AgentError) as error:
            inspect_profile(self.page, timeout_ms=200)
        self.assertEqual(error.exception.code, 'not_authenticated')

    def test_challenge_stops_before_click(self):
        self.html = FIXTURE + "<script>history.replaceState(null, '', '/checkpoint')</script>"
        # The fixture's final history update is intentionally overridden here.
        self.page.route('**/*', lambda route: route.fulfill(body=self.html, content_type='text/html'))
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Hello', timeout_ms=200)
        self.assertEqual(error.exception.code, 'browser_challenge')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_audience_change_stops_before_click(self):
        self.html = FIXTURE.replace('contenteditable="true"',
            'contenteditable="true" oninput="document.getElementById(\'audience\').textContent=\'Public\'"')
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(error.exception.code, 'audience_changed')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_uncertain_when_post_handler_fails(self):
        self.html = FIXTURE.replace('window.clicks++;', "window.clicks++; throw new Error('Lost connection');")
        result = publish(self.page, 'Hello', timeout_ms=200)
        self.assertEqual(result['status'], 'uncertain')
        self.assertEqual(self.page.evaluate('window.clicks'), 1)

    def test_preserves_whitespace(self):
        result = publish(self.page, '  Hello  ', timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(self.page.evaluate('window.submittedText'), '  Hello  ')

    def test_restored_photo_rejected_for_text_only_request(self):
        self.html = FIXTURE.replace('aria-label="Remove photo" hidden', 'aria-label="Remove photo"')
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(error.exception.code, 'unexpected_attachment')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_restored_video_rejected(self):
        self.html = FIXTURE.replace('aria-label="Remove photo" hidden', 'aria-label="Remove video"')
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(error.exception.code, 'unexpected_attachment')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_unexpected_photo_added_during_fill_is_rejected(self):
        self.html = FIXTURE.replace('contenteditable="true"',
            'contenteditable="true" oninput="document.getElementById(\'preview\').hidden=false"')
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(error.exception.code, 'unexpected_attachment')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_text_equal_to_profile_name_is_valid(self):
        result = publish(self.page, 'Alice Example', timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(self.page.evaluate('window.submittedText'), 'Alice Example')

    def test_visibility_does_not_require_playwright_151(self):
        from unittest.mock import patch
        from playwright.sync_api import Locator
        original = Locator.filter

        def filter_150(locator, **kwargs):
            if 'visible' in kwargs:
                raise TypeError('Playwright 1.50 does not support visible=')
            return original(locator, **kwargs)

        # 1.50 also misroutes Locator.is_enabled to is_editable internally.
        with patch.object(Locator, 'filter', filter_150), patch.object(
                Locator, 'is_enabled', side_effect=RuntimeError('Broken in Playwright 1.50')):
            result = publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
