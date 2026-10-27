"""Real Playwright tests against intercepted local HTML, never Facebook."""

import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from tools.facebook_agent.models import AgentError
from tools.facebook_agent.posting import publish, inspect_profile
from tools.loop import preflight
from tools.loop.tests.test_preflight import ContentFixture


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

    def test_fresh_confirmation_returns_observed_permalink(self):
        self.html = FIXTURE.replace("toast.textContent='Your post has been shared.';",
            "toast.innerHTML='Your post has been shared. <a href=\"/alice.example/posts/pfbidNew?ref=toast\">View post</a>';" )
        result = publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(result['permalink'], 'https://www.facebook.com/alice.example/posts/pfbidNew')
        self.assertEqual(result['permalink_status'], 'observed')
        self.assertEqual(result['registration_status'], 'ready')
        self.assertEqual(self.page.evaluate('window.clicks'), 1)

    def test_missing_permalink_does_not_make_confirmed_post_uncertain(self):
        result = publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertIsNone(result['permalink'])
        self.assertEqual(result['registration_status'], 'needs_permalink')
        self.assertIn('Do not repost', result['next_action'])
        self.assertEqual(self.page.evaluate('window.clicks'), 1)

    def test_old_toast_and_feed_links_are_never_permalink_fallbacks(self):
        self.html = FIXTURE.replace('<h1>', '''
            <div role="status">Your post has been shared.
              <a href="/alice.example/posts/111">View old post</a></div>
            <a href="/alice.example/posts/222">Newest feed post</a><h1>''')
        result = publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertIsNone(result['permalink'])

    def test_ambiguous_or_external_confirmation_links_are_not_guessed(self):
        cases = [
            ('<a href="/alice.example/posts/111">One</a><a href="/alice.example/posts/222">Two</a>', 'ambiguous'),
            ('<a href="https://evil.test/alice.example/posts/111">View post</a>', 'not_exposed'),
            ('<a href="/someone.else/posts/111">View post</a>', 'not_exposed'),
            ('<a href="/professional_dashboard/content/insights/111">Insights</a>', 'not_exposed'),
        ]
        for links, expected in cases:
            with self.subTest(expected=expected):
                self.html = FIXTURE.replace("toast.textContent='Your post has been shared.';",
                                          'toast.innerHTML=' + repr('Your post has been shared. ' + links) + ';')
                result = publish(self.page, 'Hello', timeout_ms=500)
                self.assertEqual(result['status'], 'confirmed')
                self.assertIsNone(result['permalink'])
                self.assertEqual(result['permalink_status'], expected)
                self.assertEqual(self.page.evaluate('window.clicks'), 1)

    def test_permalink_extraction_error_preserves_confirmation(self):
        with patch('tools.facebook_agent.posting._confirmation_permalink', side_effect=RuntimeError('Fixture DOM changed')):
            result = publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertIsNone(result['permalink'])
        self.assertEqual(result['permalink_status'], 'unavailable')
        self.assertEqual(self.page.evaluate('window.clicks'), 1)

    def test_page_permalink_query_preserves_identity_and_rejects_mismatch(self):
        self.page.unroute('**/*')
        self.page.route('**/*', lambda route: route.fulfill(
            body=self.html + "<script>history.replaceState(null, '', '/profile.php?id=123')</script>",
            content_type='text/html'))
        for actor, expected in (('123', 'observed'), ('456', 'not_exposed')):
            with self.subTest(actor=actor):
                links = f'<a href="/permalink.php?story_fbid=999&amp;id={actor}&amp;ref=toast">View post</a>'
                self.html = FIXTURE.replace('<h1>', '<button>Manage Page</button><h1>').replace(
                    "toast.textContent='Your post has been shared.';",
                    'toast.innerHTML=' + repr('Your post has been shared. ' + links) + ';')
                result = publish(self.page, 'Hello', page_id='123', timeout_ms=500)
                self.assertEqual(result['permalink_status'], expected)
                if actor == '123':
                    self.assertEqual(result['permalink'], 'https://www.facebook.com/permalink.php?story_fbid=999&id=123')
                else:
                    self.assertIsNone(result['permalink'])

    def test_policy_is_rechecked_immediately_before_submit(self):
        checks = []

        def guard(**kwargs):
            checks.append(kwargs)
            if len(checks) == 3:
                raise AgentError('content_policy', 'Fixture approval became stale.', True)
            return kwargs.get('page_id')

        with patch('tools.facebook_agent.posting.check_campaign', side_effect=guard):
            with self.assertRaises(AgentError) as error:
                publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(error.exception.code, 'content_policy')
        self.assertEqual(len(checks), 3)
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_real_file_change_during_composer_invalidates_approval(self):
        fixture = ContentFixture()
        fixture.addCleanup = self.addCleanup
        fixture.setUp()
        fixture.config['content_policy'] = {'schema_version': 1}
        fixture.write('loop/config.json', fixture.config)
        del fixture.manifest['visual']
        fixture.write('posts/2/content.json', fixture.manifest)
        preflight.record_decision(fixture.root, 2, kind='content', reviewer='Fixture human', approved=True)
        # Make the intercepted HTML an explicitly active Page with an exact ID.
        self.html = FIXTURE.replace('<h1>', '<button>Manage Page</button><h1>')
        self.html += "<script>history.replaceState(null, '', '/profile.php?id=123')</script>"
        # Existing route appends its own history call; preserve the fixture Page URL
        # through a locally intercepted navigation override.
        self.page.unroute('**/*')
        self.page.route('**/*', lambda route: route.fulfill(body=self.html, content_type='text/html'))
        original_fill = fixture.text
        with patch('tools.facebook_agent.posting._confirmation') as confirmation:
            def changed_before_final_check(page):
                fixture.write('posts/2/facebook-ad.md', original_fill + 'Changed during composer')
                return page.locator('[role="status"]')
            confirmation.side_effect = changed_before_final_check
            with self.assertRaises(AgentError) as error:
                publish(self.page, fixture.text, project=fixture.root, post=2, page_id='123',
                        page_name='Alice Example', timeout_ms=500)
        self.assertEqual(error.exception.code, 'content_policy')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_waits_for_delayed_composer_trigger(self):
        self.html = FIXTURE.replace('<button onclick=', '<button id="composer-trigger" hidden onclick=', 1)
        self.html += "<script>setTimeout(() => document.getElementById('composer-trigger').hidden=false, 100)</script>"
        result = publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(self.page.evaluate('window.clicks'), 1)

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

    def test_explicit_active_page_can_publish(self):
        self.html = FIXTURE.replace('<h1>', '<button>Manage Page</button><h1>')
        result = publish(self.page, 'Page post', timeout_ms=500, page_name='Alice Example')
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(result['profile']['type'], 'page')
        self.assertEqual(self.page.evaluate('window.clicks'), 1)

    def test_page_requires_matching_name_and_active_page_controls(self):
        for control, name in (('Manage Page', 'Wrong Page'),
                              ('Switch into Page', 'Alice Example'),
                              ('', 'Alice Example')):
            with self.subTest(control=control, name=name):
                self.html = FIXTURE.replace('<h1>', f'<button>{control}</button><h1>')
                with self.assertRaises(AgentError):
                    publish(self.page, 'Page post', timeout_ms=200, page_name=name)
                self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_page_composer_identity_must_match_even_if_text_names_page(self):
        self.html = FIXTURE.replace('<h1>', '<button>Manage Page</button><h1>').replace(
            '<h3>Alice Example</h3>', '<h3>Wrong Page</h3>')
        with self.assertRaises(AgentError):
            publish(self.page, 'Alice Example', timeout_ms=200, page_name='Alice Example')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_page_doctor_does_not_open_composer(self):
        self.html = FIXTURE.replace('<h1>', '<button>Manage Page</button><h1>')
        result = inspect_profile(self.page, timeout_ms=500, page_name='Alice Example')
        self.assertEqual(result['type'], 'page')
        self.assertFalse(self.page.get_by_role('dialog').is_visible())

    def test_page_id_must_match_active_me_url(self):
        self.html = FIXTURE.replace('<h1>', '<button>Manage Page</button><h1>')
        self.page.unroute('**/*')
        self.page.route('**/*', lambda route: route.fulfill(
            body=self.html + "<script>history.replaceState(null, '', '/profile.php?id=123')</script>",
            content_type='text/html'))
        result = publish(self.page, 'Page post', timeout_ms=500, page_id='123')
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(result['profile']['name'], 'Alice Example')
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Wrong page', timeout_ms=200, page_id='456')
        self.assertEqual(error.exception.code, 'page_identity_mismatch')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_page_id_does_not_mistake_management_heading_for_author(self):
        self.html = FIXTURE.replace('<h1>Alice Example</h1>',
                                    '<h1>Manage Page</h1><h2>Alice Example</h2>')
        self.html = self.html.replace('<body>', '<body><button>Manage Page</button>')
        self.page.unroute('**/*')
        self.page.route('**/*', lambda route: route.fulfill(
            body=self.html + "<script>history.replaceState(null, '', '/profile.php?id=123')</script>",
            content_type='text/html'))
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Page post', timeout_ms=200, page_id='123')
        self.assertEqual(error.exception.code, 'ambiguous_dom')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)
        result = inspect_profile(self.page, timeout_ms=200, page_id='123', page_name='Alice Example')
        self.assertEqual(result['name'], 'Alice Example')

    def test_duplicate_page_labels_allowed_only_with_matching_page_id(self):
        self.html = FIXTURE.replace('<h1>', '<button>Manage Page</button><h1>')
        self.html = self.html.replace('</h1>', '</h1><h2>Alice Example</h2>')
        self.page.unroute('**/*')
        self.page.route('**/*', lambda route: route.fulfill(
            body=self.html + "<script>history.replaceState(null, '', '/profile.php?id=123')</script>",
            content_type='text/html'))
        result = publish(self.page, 'Page post', timeout_ms=500,
                         page_id='123', page_name='Alice Example')
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(result['profile']['name'], 'Alice Example')
        self.assertEqual(self.page.evaluate('window.clicks'), 1)
        for page_id, code in ((None, 'ambiguous_dom'), ('456', 'page_identity_mismatch')):
            with self.subTest(page_id=page_id), self.assertRaises(AgentError) as error:
                publish(self.page, 'Page post', timeout_ms=200,
                        page_id=page_id, page_name='Alice Example')
            self.assertEqual(error.exception.code, code)
            self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_duplicate_page_labels_do_not_bypass_composer_identity(self):
        self.html = FIXTURE.replace('<h1>', '<button>Manage Page</button><h1>')
        self.html = self.html.replace('</h1>', '</h1><h2>Alice Example</h2>').replace(
            '<h3>Alice Example</h3>', '<h3>Wrong Page</h3>')
        self.page.unroute('**/*')
        self.page.route('**/*', lambda route: route.fulfill(
            body=self.html + "<script>history.replaceState(null, '', '/profile.php?id=123')</script>",
            content_type='text/html'))
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Alice Example', timeout_ms=200,
                    page_id='123', page_name='Alice Example')
        self.assertIn('posting identity', error.exception.message)
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

    def test_profile_name_link_and_alternative_owner_control(self):
        self.html = FIXTURE.replace(
            '<h1>Alice Example</h1><button>Edit profile</button>',
            '<h1>Facebook</h1><h2><a href="/alice.example">Alice Example</a></h2>'
            '<div role="button" aria-label="Edit cover photo">Edit cover photo</div>')
        result = inspect_profile(self.page, timeout_ms=500)
        self.assertEqual(result['name'], 'Alice Example')

    def test_composer_dialog_disambiguated_by_textbox(self):
        self.html = FIXTURE.replace(
            '</body>', '<div role="dialog"><h2>Create post</h2></div></body>')
        result = publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(self.page.evaluate('window.clicks'), 1)

    def test_post_button_in_next_step_dialog(self):
        self.html = FIXTURE.replace(
            '<button id="post" onclick="submitPost()">Post</button>',
            '<button onclick="this.parentElement.hidden=true; '
            'document.getElementById(\'submit-dialog\').hidden=false">Next</button>')
        self.html = self.html.replace(
            '<script>', '<div role="dialog" id="submit-dialog" hidden>'
            '<button onclick="this.parentElement.hidden=true; submitPost()">Post</button>'
            '</div><script>')
        result = publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(self.page.evaluate('window.clicks'), 1)
        self.assertEqual(self.page.evaluate('window.submittedText'), 'Hello')

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

    def test_dismiss_button_handles_composer_popup(self):
        self.html = FIXTURE.replace('<button id="post"', '<button>Not now</button><button id="post"')
        result = publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
