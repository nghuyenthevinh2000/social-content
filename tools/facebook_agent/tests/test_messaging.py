"""Real Playwright tests for direct messaging against intercepted local HTML."""

import unittest
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from tools.facebook_agent.messaging import run_plan, send_message
from tools.facebook_agent.models import AgentError


MESSAGE_BUTTON = '<button id="message" onclick="document.getElementById(\'chat\').hidden=false">Message</button>'

FIXTURE = '''<!doctype html><html><body>
<h1>Alice Example</h1>
''' + MESSAGE_BUTTON + '''
<div role="dialog" id="chat" hidden>
  <div role="textbox" contenteditable="true" style="white-space: pre-wrap" aria-label="Message"></div>
  <button id="send" aria-label="Send" onclick="sendMessage()">Send</button>
</div>
<script>
window.sends = 0;
window.bubbles = [];
function sendMessage() {
  window.sends++;
  const box = document.querySelector('#chat [role=textbox]');
  const text = box.innerText;
  box.innerHTML = '';
  if (!window.failSend) {
    const bubble = document.createElement('div');
    bubble.textContent = text;
    document.getElementById('chat').appendChild(bubble);
    window.bubbles.push(text);
  }
}
</script></body></html>'''

LOGIN = '<input name="email"><input name="pass"><button>Log in</button>'
NO_BUTTON = FIXTURE.replace(MESSAGE_BUTTON, '')
CANNOT = FIXTURE.replace('<body>', '<body><div>You can\'t message this person right now.</div>')
DISABLED = FIXTURE.replace('<button id="send"', '<button disabled id="send"')
DRAFT = FIXTURE.replace('aria-label="Message"></div>', 'aria-label="Message">Draft</div>')
CHANGED = FIXTURE.replace('contenteditable="true" style',
                          'contenteditable="true" oninput="this.textContent=\'Changed\'" style')

URL = 'https://www.facebook.com/alice.example'


class NoDelay:
    def uniform(self, low, high):
        return 0.0


class FakePacer:
    def __init__(self):
        self.calls = 0

    def after_attempt(self):
        self.calls += 1


class MessagingTests(unittest.TestCase):
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
        self.pages = {}

        def route(handler, request):
            path = urlparse(request.url).path
            handler.fulfill(body=self.pages.get(path, FIXTURE), content_type='text/html')

        self.page.route('**/*', route)

    def tearDown(self):
        self.context.close()

    def send(self, text, url=URL, timeout_ms=500):
        return send_message(self.page, url, text, timeout_ms=timeout_ms, rng=NoDelay())

    def test_sends_exact_custom_text_once(self):
        result = self.send('Hi there 👋\nSecond line')
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(result['text'], 'Hi there 👋\nSecond line')
        self.assertEqual(self.page.evaluate('window.sends'), 1)
        self.assertEqual(self.page.evaluate('window.bubbles'), ['Hi there 👋\nSecond line'])

    def test_missing_confirmation_is_uncertain_not_retried(self):
        self.pages['/alice.example'] = FIXTURE + '<script>window.failSend=true</script>'
        result = self.send('Hello')
        self.assertEqual(result['status'], 'uncertain')
        self.assertEqual(self.page.evaluate('window.sends'), 1)

    def test_prior_identical_bubble_does_not_confirm_new_send(self):
        self.pages['/alice.example'] = FIXTURE + (
            '<script>window.failSend=true;const b=document.createElement("div");'
            'b.textContent="Hello";document.getElementById("chat").appendChild(b);</script>')
        result = self.send('Hello')
        self.assertEqual(result['status'], 'uncertain')

    def test_missing_message_button_fails(self):
        self.pages['/alice.example'] = NO_BUTTON
        with self.assertRaises(AgentError) as error:
            self.send('Hello')
        self.assertEqual(error.exception.code, 'message_button_missing')
        self.assertEqual(self.page.evaluate('window.sends'), 0)

    def test_cannot_message_notice_stops_before_typing(self):
        self.pages['/alice.example'] = CANNOT
        with self.assertRaises(AgentError) as error:
            self.send('Hello')
        self.assertEqual(error.exception.code, 'cannot_message')
        self.assertEqual(self.page.evaluate('window.sends'), 0)

    def test_restored_draft_is_rejected(self):
        self.pages['/alice.example'] = DRAFT
        with self.assertRaises(AgentError) as error:
            self.send('Hello')
        self.assertEqual(error.exception.code, 'unexpected_content')
        self.assertEqual(self.page.evaluate('window.sends'), 0)

    def test_changed_text_stops_before_send(self):
        self.pages['/alice.example'] = CHANGED
        with self.assertRaises(AgentError) as error:
            self.send('Hello')
        self.assertEqual(error.exception.code, 'content_changed')
        self.assertEqual(self.page.evaluate('window.sends'), 0)

    def test_disabled_send_stops_before_click(self):
        self.pages['/alice.example'] = DISABLED
        with self.assertRaises(AgentError) as error:
            self.send('Hello', timeout_ms=300)
        self.assertEqual(error.exception.code, 'submit_disabled')
        self.assertEqual(self.page.evaluate('window.sends'), 0)

    def test_login_page_stops_as_not_authenticated(self):
        self.pages['/alice.example'] = LOGIN
        with self.assertRaises(AgentError) as error:
            self.send('Hello')
        self.assertEqual(error.exception.code, 'not_authenticated')
        self.assertIsNone(self.page.evaluate('window.sends'))

    def test_run_plan_reports_each_recipient_and_paces(self):
        self.pages['/missing'] = NO_BUTTON
        recipients = [
            {'url': 'https://www.facebook.com/one', 'message': 'Hi one', 'label': 'one'},
            {'url': 'https://www.facebook.com/missing', 'message': 'Hi two', 'label': 'two'},
            {'url': 'https://www.facebook.com/three', 'message': 'Hi three', 'label': 'three'},
        ]
        pacer = FakePacer()
        result = run_plan(self.page, recipients, timeout_ms=500, pacer=pacer, max_messages=10)
        self.assertEqual(result['confirmed'], 2)
        self.assertEqual(result['failed'], 1)
        self.assertEqual(result['uncertain'], 0)
        self.assertEqual(result['stopped_reason'], None)
        self.assertEqual([r['status'] for r in result['results']],
                         ['confirmed', 'failed', 'confirmed'])
        self.assertEqual(pacer.calls, 3)

    def test_run_plan_stops_on_safety_block(self):
        self.pages['/login'] = LOGIN
        recipients = [
            {'url': 'https://www.facebook.com/login', 'message': 'Hi', 'label': 'login'},
            {'url': 'https://www.facebook.com/two', 'message': 'Hi two', 'label': 'two'},
        ]
        pacer = FakePacer()
        result = run_plan(self.page, recipients, timeout_ms=300, pacer=pacer, max_messages=10)
        self.assertEqual(result['stopped_reason'], 'not_authenticated')
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['status'], 'aborted')
        self.assertEqual(pacer.calls, 0)

    def test_run_plan_honors_max_messages(self):
        recipients = [{'url': f'https://www.facebook.com/p{i}', 'message': f'Hi {i}', 'label': str(i)}
                      for i in range(5)]
        pacer = FakePacer()
        result = run_plan(self.page, recipients, timeout_ms=500, pacer=pacer, max_messages=2)
        self.assertEqual(result['attempted'], 2)
        self.assertEqual(result['stopped_reason'], 'max_messages_reached')
        self.assertEqual(len(result['results']), 2)


if __name__ == '__main__':
    unittest.main()
