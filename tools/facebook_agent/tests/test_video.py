"""Offline tests for video (Reel) publishing, against intercepted HTML."""

import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.facebook_agent.models import AgentError, validate_video
from tools.facebook_agent.posting import publish


FIXTURE = '''<!doctype html><html><body>
<h1>Alice Example</h1><button>Edit profile</button>
<button onclick="document.getElementById('create').hidden=false">What's on your mind, Alice?</button>
<div role="dialog" id="create" hidden>
  <h2>Create post</h2><h3>Alice Example</h3>
  <button id="audience" aria-label="Edit privacy">Public</button>
  <div role="textbox" contenteditable="true" style="white-space: pre-wrap" aria-label="What's on your mind, Alice?"></div>
  <input type="file" accept="image/*,video/*" multiple onchange="attachVideo()">
  <video id="vid" hidden></video>
  <button aria-label="Remove Post Attachment" id="attachment" hidden>Remove Post Attachment</button>
  <button id="next" onclick="toReel()">Next</button>
</div>
<div role="dialog" id="reel" hidden>
  <h2>Edit reel</h2>
  <button onclick="toSettings()">Next</button>
</div>
<div role="dialog" id="settings" hidden>
  <h2>Reel settings</h2>
  <button id="share" onclick="document.getElementById('groups').hidden=false">Share to groups Reach more people when you share your post in relevant groups.</button>
  <button id="post" onclick="submitPost()">Post</button>
</div>
<div role="dialog" id="groups" hidden>
  <h2>Share to groups</h2><div>Post in up to 9 groups that you're in.</div>
  <div role="button" onclick="toggleRow(this)">Group One<input type="checkbox" aria-checked="false"></div>
  <div role="button" onclick="toggleRow(this)">Group Two<input type="checkbox" aria-checked="false"></div>
  <button id="done" onclick="document.getElementById('groups').hidden=true">Done</button>
</div>
<script>
window.clicks = 0; window.selectedGroups = [];
function attachVideo() { document.getElementById('attachment').hidden = false; document.getElementById('vid').hidden = false; }
function toReel() { document.getElementById('create').hidden = true; document.getElementById('reel').hidden = false; }
function toSettings() { document.getElementById('reel').hidden = true; document.getElementById('settings').hidden = false; }
function toggleRow(row) {
  const box = row.querySelector('input[aria-checked]');
  const now = box.getAttribute('aria-checked') !== 'true';
  box.setAttribute('aria-checked', String(now)); box.checked = now;
}
function submitPost() {
  window.clicks++;
  window.selectedGroups = Array.from(document.querySelectorAll('#groups input[aria-checked="true"]'))
    .map((box) => box.parentElement.innerText.trim());
  document.getElementById('settings').hidden = true;
  let toast = document.createElement('div');
  toast.setAttribute('role', 'status');
  toast.textContent = 'Your reel has been shared.';
  document.body.appendChild(toast);
}
</script></body></html>'''


def make_video(directory):
    path = Path(directory) / 'clip.mp4'
    path.write_bytes(b'\x00\x00\x00\x20ftypisom' + b'0' * 64)
    return path


class VideoValidationTests(unittest.TestCase):
    def test_accepts_common_containers(self):
        signatures = {
            'a.mp4': b'\x00\x00\x00\x20ftypisom',
            'a.mov': b'\x00\x00\x00\x14ftypqt  ',
            'a.webm': b'\x1aE\xdf\xa3',
            'a.avi': b'RIFF\x00\x00\x00\x00AVI ',
            'a.flv': b'FLV\x01',
            'a.ogv': b'OggS',
        }
        with tempfile.TemporaryDirectory() as directory:
            for name, header in signatures.items():
                with self.subTest(name=name):
                    path = Path(directory) / name
                    path.write_bytes(header + b'0' * 32)
                    self.assertEqual(validate_video(path), path.resolve())

    def test_rejects_non_video(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'nope.mp4'
            path.write_bytes(b'not a video at all')
            with self.assertRaises(AgentError) as error:
                validate_video(path)
            self.assertEqual(error.exception.code, 'invalid_video')

    def test_missing_file(self):
        with self.assertRaises(AgentError) as error:
            validate_video('/missing/clip.mp4')
        self.assertEqual(error.exception.code, 'invalid_video')

    def test_none_is_allowed(self):
        self.assertIsNone(validate_video(None))


class VideoPostTests(unittest.TestCase):
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
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.video = make_video(self.directory.name)

    def tearDown(self):
        self.context.close()

    def test_video_posts_after_reel_steps(self):
        result = publish(self.page, 'Reel caption', video=self.video, timeout_ms=800)
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(result['video'], str(self.video.resolve()))
        self.assertEqual(result['image'], None)
        self.assertEqual(self.page.evaluate('window.clicks'), 1)

    def test_video_with_groups_selects_and_posts(self):
        result = publish(self.page, 'Reel caption', video=self.video,
                         groups=['Group One', 'Group Two'], timeout_ms=800)
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(result['groups'], ['Group One', 'Group Two'])
        self.assertEqual(self.page.evaluate('window.selectedGroups'), ['Group One', 'Group Two'])
        self.assertEqual(self.page.evaluate('window.clicks'), 1)

    def test_missing_attachment_preview_stops_before_post(self):
        self.html = FIXTURE.replace('onchange="attachVideo()"', 'onchange="void(0)"')
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Reel caption', video=self.video, timeout_ms=500)
        self.assertEqual(error.exception.code, 'ambiguous_dom')
        self.assertEqual(self.page.evaluate('window.clicks'), 0)

    def test_image_and_video_together_rejected(self):
        with self.assertRaises(AgentError) as error:
            publish(self.page, 'Both', self.video, self.video, timeout_ms=500)
        self.assertEqual(error.exception.code, 'invalid_arguments')


if __name__ == '__main__':
    unittest.main()
