"""Offline tests for composer multi-group sharing, against intercepted HTML."""

import json
import unittest

from playwright.sync_api import sync_playwright

from tools.facebook_agent.models import AgentError
from tools.facebook_agent.posting import publish


FIXTURE = '''<!doctype html><html><body>
<h1>Alice Example</h1><button>Edit profile</button>
<button onclick="document.getElementById('create').hidden=false">What's on your mind, Alice?</button>
<div role="dialog" id="create" hidden>
  <h2>Create post</h2><h3>Alice Example</h3>
  <button id="audience" aria-label="Edit privacy">Public</button>
  <div role="textbox" contenteditable="true" style="white-space: pre-wrap" aria-label="What's on your mind, Alice?"></div>
  <button id="next" onclick="openSettings()">Next</button>
</div>
<div role="dialog" id="settings" hidden>
  <h2>Post settings</h2><div id="preview"></div>
  <button id="share" onclick="document.getElementById('groups').hidden=false">Share to groups Reach more people when you share your post in relevant groups.</button>
  <button id="save">Save</button>
  <button id="post" onclick="submitPost()">Post</button>
</div>
<div role="dialog" id="groups" hidden>
  <h2>Share to groups</h2><div>Post in up to 9 groups that you're in.</div>
  <div role="button" class="row" onclick="toggleRow(this)">Group One<input type="checkbox" aria-checked="false"></div>
  <div role="button" class="row" onclick="toggleRow(this)">Group Two<input type="checkbox" aria-checked="false"></div>
  <div role="button" class="row" onclick="toggleRow(this)">Group Three<input type="checkbox" aria-checked="false"></div>
  <button id="done" onclick="document.getElementById('groups').hidden=true">Done</button>
</div>
<script>
window.clicks = 0;
window.selectedGroups = [];
function openSettings() {
  document.getElementById('create').hidden = true;
  document.getElementById('preview').textContent = document.querySelector('[role=textbox]').innerText;
  document.getElementById('settings').hidden = false;
}
function toggleRow(row) {
  const box = row.querySelector('input[aria-checked]');
  const now = box.getAttribute('aria-checked') !== 'true';
  box.setAttribute('aria-checked', String(now));
  box.checked = now;
}
function submitPost() {
  window.clicks++;
  window.selectedGroups = Array.from(document.querySelectorAll('#groups input[aria-checked="true"]'))
    .map((box) => box.parentElement.innerText.trim());
  document.getElementById('settings').hidden = true;
  let toast = document.createElement('div');
  toast.setAttribute('role', 'status');
  toast.textContent = 'Your post has been shared.';
  document.body.appendChild(toast);
}
</script></body></html>'''


class GroupPostTests(unittest.TestCase):
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

        def route(handler, request):
            handler.fulfill(
                body=self.html + "<script>history.replaceState(null, '', '/alice.example')</script>",
                content_type='text/html')

        self.page.route('**/*', route)

    def tearDown(self):
        self.context.close()

    def test_shares_to_named_groups_and_posts_once(self):
        result = publish(self.page, 'Hello', groups=['Group One', 'Group Three'], timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(result['groups'], ['Group One', 'Group Three'])
        self.assertEqual(self.page.evaluate('window.clicks'), 1)
        self.assertEqual(self.page.evaluate('window.selectedGroups'), ['Group One', 'Group Three'])

    def test_unknown_group_stops_before_post(self):
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Hello', groups=['Missing Group'], timeout_ms=500)
        self.assertEqual(error.exception.code, 'group_not_found')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_duplicate_group_titles_stop_before_post(self):
        self.html = FIXTURE.replace('>Group Two<', '>Group One<')
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Hello', groups=['Group One'], timeout_ms=500)
        self.assertEqual(error.exception.code, 'ambiguous_dom')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_too_many_groups_stops_before_post(self):
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Hello', groups=[f'Group {n}' for n in range(10)], timeout_ms=500)
        self.assertEqual(error.exception.code, 'too_many_groups')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_already_selected_group_is_not_toggled_off(self):
        self.html = FIXTURE.replace('>Group One<input type="checkbox" aria-checked="false">',
                                    '>Group One<input type="checkbox" aria-checked="true" checked>')
        result = publish(self.page, 'Hello', groups=['Group One'], timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(self.page.evaluate('window.selectedGroups'), ['Group One'])
        self.assertEqual(self.page.evaluate('window.clicks'), 1)

    def test_groups_without_next_step_stop(self):
        self.html = FIXTURE.replace('<button id="next" onclick="openSettings()">Next</button>',
                                    '<button id="post-direct" onclick="submitPost()">Post</button>')
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Hello', groups=['Group One'], timeout_ms=500)
        self.assertEqual(error.exception.code, 'groups_unsupported')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_post_without_groups_is_unchanged(self):
        result = publish(self.page, 'Hello', timeout_ms=500)
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(result['groups'], [])
        self.assertEqual(self.page.evaluate('window.selectedGroups'), [])
        self.assertEqual(self.page.evaluate('window.clicks'), 1)


if __name__ == '__main__':
    unittest.main()
