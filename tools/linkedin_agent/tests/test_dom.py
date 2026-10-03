"""Local Chromium fixtures model LinkedIn's scoped composer and media dialogs."""

import base64
import json
import time
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright, Locator

from tools.linkedin_agent.models import AgentError, ImageInput
from tools.linkedin_agent import posts
from tools.linkedin_agent.posts import publish_post


class ComposerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.images = (
            ImageInput('first.png', 'image/png', base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAACklEQVQIHWMAAgAABAABDTukuQAAAABJRU5ErkJggg=='
            )),
            ImageInput('second.jpg', 'image/jpeg', base64.b64decode(
                '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/'
                '2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAABAAEDASIAAhEBAxEB/'
                '8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/'
                '8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD9/KKKKAP/2Q=='
            )),
        )

    def tearDown(self):
        self.page.close()

    def load_fixture(self, **options):
        # Route the production feed URL locally: no LinkedIn requests or live posts.
        self.page.route('**/*', lambda route: route.abort())
        html = """<!doctype html><html><head><style>
        .ql-editor { white-space: pre-wrap; }
        #notifications { position: fixed; top: 0; right: 0; pointer-events: none; }
        </style></head><body>
        <nav id="global-nav"><a href="/feed/">Home</a></nav>
        <button class="share-box-feed-entry__trigger">Start a post</button>
        <div contenteditable="true" role="textbox">Outside editor</div>
        <button>Post</button><a href="https://www.linkedin.com/posts/unrelated">Unrelated post</a>
        <div id="notifications"></div>
        <div role="dialog" aria-label="Create a post" style="display:none" id="composer">
          <div class="share-creation-state__member-info"><a href="/in/person/">Personal author</a></div>
          <div class="share-creation-state__text-editor"><div class="ql-editor" contenteditable="true" role="textbox" aria-label="Text editor for creating content"></div></div>
          <button aria-label="Add media">Add media</button>
          <div class="share-images"></div>
          <button class="share-actions__primary-action">Post</button>
        </div>
        <div role="dialog" aria-label="Media editor" style="display:none" id="media">
          <input type="file" accept="image/*" multiple hidden>
          <div class="share-images"></div><button>Next</button>
        </div>
        <script>
        const options = OPTIONS;
        window.postClicks=0; window.nextClicks=0; window.uploaded=[]; window.submittedText=null;
        const composer=document.querySelector('#composer'), media=document.querySelector('#media');
        const editor=composer.querySelector('[contenteditable]');
        const post=composer.querySelector('.share-actions__primary-action');
        window.appCaptureSubmissions=0;
        if(options.appCapture) document.addEventListener('click', event => {
          if(event.composedPath().includes(post)) window.appCaptureSubmissions++;
        }, true);
        if(options.pointerdownMutation) post.onpointerdown=()=>editor.innerText='changed on pointerdown';
        if(options.prepopulated) {
          const scope=options.prepopulated==='composer'?composer:media;
          for(let i=0;i<2;i++) {
            const img=document.createElement('img'); img.className='share-images__image';
            img.src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAACklEQVQIHWMAAgAABAABDTukuQAAAABJRU5ErkJggg==';
            scope.querySelector('.share-images').append(img);
            if(options.hiddenPreviews) img.style.display='none';
          }
        }
        if(options.preexistingText) editor.innerText='old draft';
        if(options.preexistingFiles) {
          const transfer=new DataTransfer(); transfer.items.add(new File(['old'], 'old.png', {type:'image/png'}));
          media.querySelector('input').files=transfer.files;
        }
        window.activePostCaptureListeners=new Set();
        const addListener=window.addEventListener.bind(window), removeListener=window.removeEventListener.bind(window);
        window.addEventListener=function(type, listener, capture) {
          if(type==='click' && capture===true) window.activePostCaptureListeners.add(listener);
          return addListener(type,listener,capture);
        };
        window.removeEventListener=function(type, listener, capture) {
          if(type==='click' && capture===true) window.activePostCaptureListeners.delete(listener);
          return removeListener(type,listener,capture);
        };
        function toast(text, url) {
          const el=document.createElement('div'); el.className='artdeco-toast-item'; el.setAttribute('role','alert');
          el.innerHTML='<span class="artdeco-toast-item__message"></span>';
          el.firstChild.textContent=text;
          if(url) {const a=document.createElement('a'); a.href=url; a.textContent='View post'; el.append(a);}
          document.querySelector('#notifications').append(el); return el;
        }
        if(options.stale) window.staleToast=toast('Post successful.', 'https://www.linkedin.com/posts/old');
        if(options.hiddenStale) {window.staleToast=toast('Post successful.'); window.staleToast.style.display='none';}
        if(options.persistentComposerInput) composer.insertAdjacentHTML('beforeend','<input type="file" accept="image/*" multiple hidden>');
        if(options.preDispatchToast) post.onpointerdown=()=> {
          window.postClicksAtPreDispatchToast=window.postClicks;
          toast('Post successful.');
        };
        document.querySelector('.share-box-feed-entry__trigger').onclick=()=>composer.style.display='block';
        composer.querySelector('[aria-label="Add media"]').onclick=()=> {
          if(options.inlineMedia) composer.append(media.querySelector('input'));
          else if(options.mediaDelay) setTimeout(()=>media.style.display='block',options.mediaDelay);
          else media.style.display='block';
          if(options.duplicateMedia) {const copy=media.cloneNode(true); copy.style.display='block'; document.body.append(copy);}
        };
        media.querySelector('input').onchange=async function() {
          if(options.uploadDelay) await new Promise(resolve=>setTimeout(resolve,options.uploadDelay));
          window.uploaded=await Promise.all([...this.files].map(async f=>({name:f.name,type:f.type,bytes:[...new Uint8Array(await f.arrayBuffer())]})));
          for(const f of [...this.files].slice(0,options.incomplete?1:undefined)) {
            const img=document.createElement('img'); img.className='share-images__image'; img.alt=f.name;
            img.src=URL.createObjectURL(f);
            (options.inlineMedia?composer:media).querySelector('.share-images').append(img);
          }
          if(options.brokenPreview) media.querySelector('img').src='data:image/png;base64,broken';
          if(options.progress || options.transientProgress) media.insertAdjacentHTML('beforeend','<div role="progressbar">Uploading</div>');
          if(options.transientProgress) setTimeout(()=>media.querySelector('[role="progressbar"]').remove(),100);
          if(options.error) media.insertAdjacentHTML('beforeend','<div role="alert">Image upload failed</div>');
        };
        media.querySelector('button').onclick=()=> {
          window.nextClicks++;
          if(options.stuckNext) return;
          if(options.done && media.querySelector('button').textContent==='Next') {media.querySelector('button').textContent='Done'; return;}
          composer.querySelector('.share-images').replaceChildren(...media.querySelector('.share-images').children);
          media.style.display='none';
          if(options.corruptText) editor.innerText='changed text';
          if(options.lateError) composer.insertAdjacentHTML('beforeend','<div role="alert">Image upload failed</div>');
          if(options.lateProgress) composer.insertAdjacentHTML('beforeend','<div role="progressbar">Uploading</div>');
          if(options.lateIdentity) composer.querySelector('.share-creation-state__member-info a').href='/company/wrong/';
          if(options.latePersonalIdentity) composer.querySelector('.share-creation-state__member-info a').href='/in/other/';
          if(options.delayedPostChangesText) {
            post.style.display='none';
            setTimeout(()=>{editor.innerText='changed while waiting'; post.style.display='block';},100);
          }
        };
        post.onclick=()=> {
          window.postClicks++;
          // Quill-style draft serialization, independent of production's native selection comparison.
          window.submittedText=[...editor.childNodes].map(n =>
            (n.nodeType===1 && ['DIV','P'].includes(n.tagName)?'\\n':'') + n.textContent).join('');
          composer.style.display='none';
          if(options.confirm!==false) {
            if(options.reuseStale) return;
            if(options.modifyStaleLink) {window.staleToast.querySelector('a').href='https://www.linkedin.com/posts/new-link-only'; return;}
            if(options.modifyStaleWhitespace) {window.staleToast.firstChild.textContent=' Post successful. '; return;}
            if(options.hiddenStale) window.staleToast.style.display='block';
            else toast(options.successText || 'Post successful.', options.url);
          }
        };
        if(options.identity==='company') composer.querySelector('.share-creation-state__member-info a').href='/company/example/';
        if(options.identity==='missing') composer.querySelector('.share-creation-state__member-info').remove();
        if(options.identity==='ambiguous') composer.querySelector('.share-creation-state__member-info').insertAdjacentHTML('beforeend','<a href="/in/other/">Other</a>');
        if(options.identity==='mixed') composer.querySelector('.share-creation-state__member-info').insertAdjacentHTML('beforeend','<a href="/company/example/">Company</a>');
        if(options.editor==='missing') editor.remove();
        if(options.editor==='duplicate') editor.parentNode.append(editor.cloneNode(true));
        if(options.post==='missing') post.remove();
        if(options.post==='duplicate') post.parentNode.append(post.cloneNode(true));
        if(options.post==='disabled') post.disabled=true;
        if(options.next==='duplicate') media.append(media.querySelector('button').cloneNode(true));
        if(options.file==='duplicate') media.append(media.querySelector('input').cloneNode(true));
        if(options.hiddenDuplicates) {
          for(const control of [editor,post]) {const copy=control.cloneNode(true); copy.style.display='none'; control.parentNode.append(copy);}
        }
        </script></body></html>""".replace('OPTIONS', json.dumps(options))
        self.page.route('https://www.linkedin.com/feed/', lambda route: route.fulfill(body=html, content_type='text/html'))
        self.page.goto('https://www.linkedin.com/feed/')

    def assert_preparation_failure(self, expected_code, **options):
        self.load_fixture(**options)
        with self.assertRaises(AgentError) as caught:
            publish_post(self.page, 'Approved text', self.images, timeout_ms=350)
        self.assertEqual(caught.exception.code, expected_code)
        self.assertEqual(self.page.evaluate('window.postClicks'), 0)

    def test_single_and_multiple_image_snapshot_order_and_exact_multiline_text(self):
        for images in (self.images[:1], self.images):
            with self.subTest(count=len(images)):
                self.load_fixture()
                text = '  Approved first line\n\nSecond line  '
                self.assertEqual(publish_post(self.page, text, images, timeout_ms=1000), {'status': 'posted', 'url': None})
                self.assertEqual(self.page.evaluate('window.submittedText'), text)
                self.assertEqual(self.page.evaluate('window.uploaded'), [
                    {'name': i.name, 'type': i.mime_type, 'bytes': list(i.buffer)} for i in images
                ])
                self.assertEqual(self.page.evaluate('[window.postClicks,window.nextClicks]'), [1, 1])
                self.page.unroute_all()

    def test_crlf_is_compared_with_browser_line_endings(self):
        self.load_fixture()
        publish_post(self.page, 'First\r\nSecond', self.images, timeout_ms=1000)
        self.assertEqual(self.page.evaluate('window.submittedText'), 'First\nSecond')

    def test_preexisting_media_cannot_satisfy_delayed_upload(self):
        for scope in ('composer', 'media'):
            with self.subTest(scope=scope):
                self.assert_preparation_failure('upload_failed', prepopulated=scope, uploadDelay=2000)
                self.assertEqual(self.page.evaluate('window.uploaded'), [])
                self.page.unroute_all()

    def test_uploaded_payload_association_and_order_are_verified(self):
        real_upload = Locator.set_input_files
        for change in ('order', 'bytes'):
            with self.subTest(change=change):
                self.load_fixture()

                def upload(locator, files, **kwargs):
                    altered = list(reversed(files)) if change == 'order' else [
                        {**files[0], 'buffer': b'X' * len(files[0]['buffer'])}, files[1]]
                    return real_upload(locator, altered, **kwargs)

                with patch.object(Locator, 'set_input_files', upload):
                    with self.assertRaises(AgentError) as caught:
                        publish_post(self.page, 'Approved text', self.images, timeout_ms=1000)
                self.assertEqual(caught.exception.code, 'upload_failed')
                self.assertEqual(self.page.evaluate('window.postClicks'), 0)
                self.page.unroute_all()

    def test_hidden_previews_old_files_and_old_text_are_rejected(self):
        for options, code in (({'prepopulated': 'media', 'hiddenPreviews': True}, 'upload_failed'),
                              ({'preexistingFiles': True}, 'upload_failed'),
                              ({'preexistingText': True}, 'text_mismatch')):
            with self.subTest(options=options):
                self.assert_preparation_failure(code, **options)
                self.assertEqual(self.page.evaluate('window.uploaded'), [])
                self.page.unroute_all()

    def test_delayed_supplied_upload_waits_for_new_decoded_previews(self):
        self.load_fixture(uploadDelay=150)
        self.assertEqual(publish_post(self.page, 'Approved text', self.images, timeout_ms=1500),
                         {'status': 'posted', 'url': None})
        self.assertEqual(self.page.evaluate('window.uploaded.map(file=>file.name)'), ['first.png', 'second.jpg'])
        self.assertEqual(self.page.evaluate('window.postClicks'), 1)

    def test_auto_wait_draft_mutations_cancel_actual_dispatch(self):
        for mutation, code in (
            ("document.querySelector('#composer [contenteditable]').innerText='changed'", 'text_mismatch'),
            ("document.querySelector('#composer .share-creation-state__member-info a').href='/in/other/'", 'unsupported_identity'),
            ("document.querySelector('#composer img').src='data:image/png;base64,broken'", 'upload_failed'),
            ("const scope=document.querySelector('#composer .share-images'); scope.append(scope.firstElementChild)", 'upload_failed'),
            ("const img=document.querySelector('#composer img'); img.replaceWith(img.cloneNode(true))", 'upload_failed'),
            ("document.querySelector('#composer').insertAdjacentHTML('beforeend','<div role=progressbar>Uploading</div>')", 'upload_failed'),
            ("const post=document.querySelector('#composer .share-actions__primary-action'); const replacement=post.cloneNode(true); replacement.onclick=post.onclick; post.replaceWith(replacement)", 'dom_timeout'),
        ):
            with self.subTest(code=code):
                self.load_fixture()
                real_click = Locator.click
                invocations = []

                def click(locator, *args, **kwargs):
                    if locator.get_attribute('class') == 'share-actions__primary-action':
                        invocations.append('post')
                        self.page.evaluate('''mutation => {
                            const cover=document.createElement('div');
                            cover.style='position:fixed;inset:0;z-index:1000;background:white';
                            document.body.append(cover);
                            setTimeout(()=>{eval(mutation); cover.remove();},100);
                        }''', mutation)
                    return real_click(locator, *args, **kwargs)

                with patch.object(Locator, 'click', click):
                    with self.assertRaises(AgentError) as caught:
                        publish_post(self.page, 'Approved text', self.images, timeout_ms=1500)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(invocations, ['post'])
                self.assertEqual(self.page.evaluate('window.postClicks'), 0)
                self.assertEqual(self.page.evaluate('window.activePostCaptureListeners.size'), 0)
                self.page.unroute_all()

    def test_cancellation_precedes_application_document_capture(self):
        self.load_fixture(appCapture=True, pointerdownMutation=True)
        with self.assertRaises(AgentError) as caught:
            publish_post(self.page, 'Approved text', self.images, timeout_ms=1000)
        self.assertEqual(caught.exception.code, 'text_mismatch')
        self.assertEqual(self.page.evaluate('[window.postClicks,window.appCaptureSubmissions]'), [0, 0])

    def test_lost_cancellation_acknowledgement_remains_uncertain(self):
        self.load_fixture(pointerdownMutation=True)
        real_click = Locator.click
        invocations = []

        def click(locator, *args, **kwargs):
            if locator.get_attribute('class') == 'share-actions__primary-action':
                invocations.append('post')
                real_click(locator, *args, **kwargs)
                raise RuntimeError('lost cancellation acknowledgement')
            return real_click(locator, *args, **kwargs)

        with patch.object(Locator, 'click', click):
            with self.assertRaises(AgentError) as caught:
                publish_post(self.page, 'Approved text', self.images, timeout_ms=1000)
        self.assertEqual(caught.exception.code, 'submission_uncertain')
        self.assertTrue(caught.exception.human_action_required)
        self.assertEqual(invocations, ['post'])
        self.assertEqual(self.page.evaluate('window.postClicks'), 0)
        self.assertEqual(self.page.evaluate('window.activePostCaptureListeners.size'), 0)

    def test_cleanup_failure_after_cancellation_remains_uncertain(self):
        self.load_fixture(pointerdownMutation=True)
        real_cleanup = posts._remove_dispatch_capture

        def cleanup(capture):
            real_cleanup(capture)
            raise RuntimeError('cleanup acknowledgement lost')

        with patch.object(posts, '_remove_dispatch_capture', cleanup):
            with self.assertRaises(AgentError) as caught:
                publish_post(self.page, 'Approved text', self.images, timeout_ms=1000)
        self.assertEqual(caught.exception.code, 'submission_uncertain')
        self.assertEqual(self.page.evaluate('window.postClicks'), 0)
        self.assertEqual(self.page.evaluate('window.activePostCaptureListeners.size'), 0)

    def test_rejects_company_missing_and_ambiguous_identity(self):
        for identity in ('company', 'missing', 'ambiguous', 'mixed'):
            with self.subTest(identity=identity):
                self.assert_preparation_failure('unsupported_identity', identity=identity)
                self.page.unroute_all()

    def test_missing_or_duplicate_editor_and_post_and_disabled_post(self):
        for key, values in (('editor', ('missing', 'duplicate')), ('post', ('missing', 'duplicate', 'disabled')), ('next', ('duplicate',)), ('file', ('duplicate',))):
            for value in values:
                with self.subTest(control=key, state=value):
                    code = {'missing': 'dom_timeout', 'duplicate': 'ambiguous_selector', 'disabled': 'submission_disabled'}[value]
                    self.assert_preparation_failure(code, **{key: value})
                    self.page.unroute_all()

    def test_incomplete_previews_progress_upload_errors_and_late_changes(self):
        for option, code in (
            ('incomplete', 'dom_timeout'), ('progress', 'dom_timeout'),
            ('brokenPreview', 'dom_timeout'), ('error', 'upload_failed'),
            ('lateError', 'upload_failed'), ('lateProgress', 'dom_timeout'),
            ('corruptText', 'text_mismatch'), ('lateIdentity', 'unsupported_identity'),
            ('latePersonalIdentity', 'unsupported_identity'), ('stuckNext', 'dom_timeout'),
            ('delayedPostChangesText', 'text_mismatch'),
        ):
            with self.subTest(option=option):
                self.assert_preparation_failure(code, **{option: True})
                self.page.unroute_all()

    def test_uncertain_submission_is_not_retried(self):
        self.load_fixture(confirm=False)
        with self.assertRaises(AgentError) as caught:
            publish_post(self.page, 'Approved text', self.images, timeout_ms=350)
        self.assertEqual(caught.exception.code, 'submission_uncertain')
        self.assertTrue(caught.exception.human_action_required)
        self.assertEqual(self.page.evaluate('window.postClicks'), 1)

    def test_pre_dispatch_toast_is_not_confirmation(self):
        self.load_fixture(preDispatchToast=True, confirm=False)
        with self.assertRaises(AgentError) as caught:
            publish_post(self.page, 'Approved text', self.images, timeout_ms=500)
        self.assertEqual(caught.exception.code, 'submission_uncertain')
        self.assertTrue(caught.exception.human_action_required)
        self.assertEqual(self.page.evaluate('[window.postClicksAtPreDispatchToast, window.postClicks]'), [0, 1])
        self.assertEqual(self.page.evaluate('window.activePostCaptureListeners.size'), 0)

    def test_toast_during_final_click_auto_wait_is_not_confirmation(self):
        self.load_fixture(confirm=False)
        real_click = Locator.click

        def click(locator, *args, **kwargs):
            if locator.get_attribute('class') == 'share-actions__primary-action':
                self.page.evaluate('''() => {
                    const cover=document.createElement('div');
                    cover.style='position:fixed;inset:0;z-index:1000;background:white';
                    document.body.append(cover);
                    setTimeout(()=>{
                        window.postClicksAtPreDispatchToast=window.postClicks;
                        const toast=document.createElement('div');
                        toast.className='artdeco-toast-item'; toast.setAttribute('role','alert');
                        toast.textContent='Post successful.';
                        document.querySelector('#notifications').append(toast);
                    },50);
                    setTimeout(()=>cover.remove(),150);
                }''')
            return real_click(locator, *args, **kwargs)

        with patch.object(Locator, 'click', click):
            with self.assertRaises(AgentError) as caught:
                publish_post(self.page, 'Approved text', self.images, timeout_ms=1000)
        self.assertEqual(caught.exception.code, 'submission_uncertain')
        self.assertEqual(self.page.evaluate('[window.postClicksAtPreDispatchToast, window.postClicks]'), [0, 1])
        self.assertEqual(self.page.evaluate('window.activePostCaptureListeners.size'), 0)

    def test_post_dispatch_toast_confirms_even_with_pre_dispatch_toast(self):
        self.load_fixture(preDispatchToast=True)
        self.assertEqual(publish_post(self.page, 'Approved text', self.images, timeout_ms=1000), {'status': 'posted', 'url': None})
        self.assertEqual(self.page.evaluate('[window.postClicksAtPreDispatchToast, window.postClicks]'), [0, 1])
        self.assertEqual(self.page.evaluate('window.activePostCaptureListeners.size'), 0)

    def test_stale_success_is_not_confirmation(self):
        self.load_fixture(stale=True, reuseStale=True)
        with self.assertRaises(AgentError) as caught:
            publish_post(self.page, 'Approved text', self.images, timeout_ms=350)
        self.assertEqual(caught.exception.code, 'submission_uncertain')
        self.assertEqual(self.page.evaluate('window.postClicks'), 1)

    def test_fresh_notification_and_link_scoping(self):
        for options, expected in (
            ({'stale': True}, None),
            ({'hiddenStale': True}, None),
            ({'url': 'https://www.linkedin.com/feed/update/urn:li:activity:123/'}, 'https://www.linkedin.com/feed/update/urn:li:activity:123/'),
            ({'url': 'https://www.linkedin.com/posts/person_123'}, 'https://www.linkedin.com/posts/person_123'),
            ({'url': 'https://www.linkedin.com.evil.test/posts/fake'}, None),
            ({'url': 'https://www.linkedin.com/in/person'}, None),
        ):
            with self.subTest(options=options):
                self.load_fixture(**options)
                self.assertEqual(publish_post(self.page, 'Approved text', self.images, timeout_ms=1000), {'status': 'posted', 'url': expected})
                self.assertEqual(self.page.evaluate('window.postClicks'), 1)
                self.page.unroute_all()

    def test_non_success_notification_is_not_confirmation(self):
        self.load_fixture(successText='Your changes were saved.')
        with self.assertRaises(AgentError) as caught:
            publish_post(self.page, 'Approved text', self.images, timeout_ms=350)
        self.assertEqual(caught.exception.code, 'submission_uncertain')
        self.assertEqual(self.page.evaluate('window.postClicks'), 1)

    def test_stale_notification_link_change_is_not_fresh_success(self):
        for option in ('modifyStaleLink', 'modifyStaleWhitespace'):
            with self.subTest(option=option):
                self.load_fixture(stale=True, **{option: True})
                with self.assertRaises(AgentError) as caught:
                    publish_post(self.page, 'Approved text', self.images, timeout_ms=350)
                self.assertEqual(caught.exception.code, 'submission_uncertain')
                self.assertEqual(self.page.evaluate('window.postClicks'), 1)
                self.page.unroute_all()

    def test_success_appearing_during_final_validation_is_still_pre_click(self):
        self.load_fixture(confirm=False)
        read_text = posts._editor_text

        def success_before_click(editor):
            self.page.evaluate('''() => {
                const toast=document.createElement('div');
                toast.className='artdeco-toast-item'; toast.setAttribute('role','alert');
                toast.textContent='Post successful.';
                document.querySelector('#notifications').append(toast);
            }''')
            return read_text(editor)

        with patch.object(posts, '_editor_text', success_before_click):
            with self.assertRaises(AgentError) as caught:
                publish_post(self.page, 'Approved text', self.images, timeout_ms=350)
        self.assertEqual(caught.exception.code, 'submission_uncertain')
        self.assertEqual(self.page.evaluate('window.postClicks'), 1)

    def test_confirmation_observed_after_deadline_is_uncertain(self):
        self.load_fixture()
        read_notification = posts._notification_state

        def slow_observation(handle):
            time.sleep(0.4)
            return read_notification(handle)

        with patch.object(posts, '_notification_state', slow_observation):
            with self.assertRaises(AgentError) as caught:
                publish_post(self.page, 'Approved text', self.images, timeout_ms=350)
        self.assertEqual(caught.exception.code, 'submission_uncertain')
        self.assertEqual(self.page.evaluate('window.postClicks'), 1)

    def test_media_next_done_and_hidden_duplicates_and_progress_completion(self):
        self.load_fixture(done=True, hiddenDuplicates=True, transientProgress=True)
        self.assertEqual(publish_post(self.page, 'Approved text', self.images, timeout_ms=1500), {'status': 'posted', 'url': None})
        self.assertEqual(self.page.evaluate('[window.postClicks,window.nextClicks]'), [1, 2])

    def test_upload_input_in_composer_does_not_require_media_next(self):
        self.load_fixture(inlineMedia=True)
        self.assertEqual(publish_post(self.page, 'Approved text', self.images, timeout_ms=1000), {'status': 'posted', 'url': None})
        self.assertEqual(self.page.evaluate('[window.postClicks,window.nextClicks]'), [1, 0])

    def test_active_media_dialog_excludes_composer_with_persistent_input(self):
        for delay in (0, 100):
            with self.subTest(media_delay=delay):
                self.load_fixture(persistentComposerInput=True, mediaDelay=delay)
                self.assertEqual(publish_post(self.page, 'Approved text', self.images, timeout_ms=1000), {'status': 'posted', 'url': None})
                self.assertEqual(self.page.evaluate('[window.postClicks,window.nextClicks]'), [1, 1])
                self.assertEqual(self.page.locator('#composer input[type="file"]').evaluate('(input) => input.files.length'), 0)
                self.assertEqual(self.page.evaluate('window.uploaded.map(image=>image.name)'), ['first.png', 'second.jpg'])
                self.page.unroute_all()

    def test_duplicate_active_media_dialogs_remain_ambiguous(self):
        self.assert_preparation_failure('ambiguous_selector', persistentComposerInput=True, duplicateMedia=True)

    def test_final_click_exception_before_dispatch_is_uncertain(self):
        self.load_fixture()
        real_click = Locator.click
        invocations = []

        def click(locator, *args, **kwargs):
            if locator.get_attribute('class') == 'share-actions__primary-action':
                invocations.append('post')
                raise RuntimeError('Connection lost before dispatch acknowledgement')
            return real_click(locator, *args, **kwargs)

        with patch.object(Locator, 'click', click):
            with self.assertRaises(AgentError) as caught:
                publish_post(self.page, 'Approved text', self.images, timeout_ms=1000)
        self.assertEqual(caught.exception.code, 'submission_uncertain')
        self.assertTrue(caught.exception.human_action_required)
        self.assertEqual(invocations, ['post'])
        self.assertEqual(self.page.evaluate('window.postClicks'), 0)
        self.assertEqual(self.page.evaluate('window.activePostCaptureListeners.size'), 0)

    def test_final_click_exception_is_uncertain(self):
        self.load_fixture()
        real_click = Locator.click
        invocations = []

        def click(locator, *args, **kwargs):
            if locator.get_attribute('class') == 'share-actions__primary-action':
                invocations.append('post')
                real_click(locator, *args, **kwargs)
                raise RuntimeError('Connection lost after dispatch')
            return real_click(locator, *args, **kwargs)

        with patch.object(Locator, 'click', click):
            with self.assertRaises(AgentError) as caught:
                publish_post(self.page, 'Approved text', self.images, timeout_ms=1000)
        self.assertEqual(caught.exception.code, 'submission_uncertain')
        self.assertEqual(invocations, ['post'])
        self.assertEqual(self.page.evaluate('window.postClicks'), 1)
        self.assertEqual(self.page.evaluate('window.activePostCaptureListeners.size'), 0)


if __name__ == '__main__':
    unittest.main()
