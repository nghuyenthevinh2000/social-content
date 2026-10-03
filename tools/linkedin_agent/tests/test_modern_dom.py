"""Offline native-dialog fixtures; all external requests are blocked."""

import json
import unittest
from unittest.mock import patch

from playwright.sync_api import FileChooser

from tools.linkedin_agent import posts
from tools.linkedin_agent.models import AgentError
from tools.linkedin_agent.tests import test_dom


class ModernTests(unittest.TestCase):
    setUpClass = classmethod(test_dom.ComposerTests.setUpClass.__func__)
    tearDownClass = classmethod(test_dom.ComposerTests.tearDownClass.__func__)
    setUp = test_dom.ComposerTests.setUp
    tearDown = test_dom.ComposerTests.tearDown

    def load(self, **options):
        html = '''<body data-rehydrated="false"><style>[contenteditable]{white-space:pre-wrap}</style>
        <nav><button aria-current="true" aria-label="Home">Home</button></nav>
        <div id="shareboxProfilePictureComponentRef"><a href="/in/member/"><figure><svg id="person-accent-4" aria-label="Member"></svg><img src="data:image/png;base64,PNG"></figure></a></div>
        <div role="button" tabindex="0" id="start"><div aria-label="Start a post">Start a post</div></div>
        <dialog data-testid="dialog" id="composer"><div data-sdui-screen="com.linkedin.sdui.flagshipnav.sharing.ShareCompose">
        <figure><svg id="person-accent-4"></svg><img src="data:image/png;base64,PNG"></figure>
        <div role="button" tabindex="0" aria-expanded="false" id="author"><div aria-label="Member"><p>Member</p><svg id="caret-small"></svg></div></div>
        <div componentkey="ShareBox_textEditor" role="textbox" contenteditable="true"></div>
        <button aria-label="Media" aria-haspopup="dialog">Media</button><div id="attachments"></div><button id="post">Post</button>
        </div></dialog>
        <dialog data-testid="dialog" id="media"><header><h2>Editor</h2></header><div role="region" data-testid="add-media-drop-zone" aria-label="Add media. Drag and drop media files here, or use the button to choose files."><button disabled aria-busy="true">Loading</button></div><div id="previews"></div><button id="next" disabled>Next</button></dialog>
        <input type="file" accept="image/jpeg,image/png,video/*" multiple hidden>
        <script>
        const o=OPTIONS, c=document.querySelector('#composer'),m=document.querySelector('#media'),a=document.querySelector('#author'),f=document.querySelector('input[type=file]');
        window.postClicks=0;window.nextClicks=0;window.pickerClicks=0;window.uploaded=[];
        window.startClicks=0;
        setTimeout(()=>document.body.dataset.rehydrated='true',o.hydrationDelay||0);
        document.querySelector('#start').onclick=()=>{window.startClicks++;if(document.body.dataset.rehydrated==='true')c.showModal();};
        a.onclick=()=>{window.pickerClicks++;if(a.getAttribute('aria-expanded')==='true'){document.querySelector('#picker').remove();a.setAttribute('aria-expanded','false');return;}
        a.setAttribute('aria-expanded','true');const p=document.createElement('div');p.id='picker';p.dataset.testid='lazy-column';p.dataset.componentType='LazyColumn';
        p.innerHTML='<p>Post as</p><div id="row"><div><figure><svg id="'+(o.company?'company-accent-4':'person-accent-4')+'"></svg><img src="data:image/png;base64,PNG"></figure><p>'+(o.wrongName?'Other':'Member')+'</p></div><div><input id="radio" type="radio" checked><label for="radio"></label></div></div>';
        c.append(p);if(o.unchecked)p.querySelector('input').checked=false;if(o.duplicate)p.querySelector('#row').append(p.querySelector('input').cloneNode());};
        c.querySelector('[aria-label=Media]').onclick=()=>{m.showModal();f.click();};
        f.onchange=async()=>{window.uploaded=await Promise.all([...f.files].map(async x=>({name:x.name,bytes:[...new Uint8Array(await x.arrayBuffer())]})));
        document.querySelector('[aria-busy]').remove();
        document.querySelector('[data-testid=add-media-drop-zone]').remove();
        [...f.files].forEach((x,i)=>{const img=document.createElement('img');img.alt='image '+(o.order?f.files.length-i-1:i);img.src=o.broken?'data:image/png;base64,broken':URL.createObjectURL(x);document.querySelector('#previews').append(img);});
        const large=document.querySelector('#previews img').cloneNode();large.alt='Image Preview';document.querySelector('#previews').prepend(large);document.querySelector('#next').disabled=false;};
        document.querySelector('#next').onclick=()=>{window.nextClicks++;const thumbs=[...m.querySelectorAll('img')].filter(x=>/^image \\d+$/.test(x.alt));if(o.reverseNext)thumbs.reverse();thumbs.forEach(x=>{const figure=document.createElement('figure');figure.innerHTML='<svg id="image-medium"></svg>';if(o.regeneratedNext)x.src=URL.createObjectURL(f.files[Number(x.alt.split(' ')[1])]);if(o.nonBlob)x.src='data:image/png;base64,PNG';x.alt='';if(o.changedSource)x.src=URL.createObjectURL(f.files[0]);figure.append(x);document.querySelector('#attachments').append(figure);});m.close();if(o.lateName)a.querySelector('[aria-label]').setAttribute('aria-label','Other');};
        document.querySelector('#post').onpointerdown=()=>{if(o.dispatchName)a.querySelector('[aria-label]').setAttribute('aria-label','Other');if(o.dispatchMarker)c.querySelector('figure svg').id='company-accent-4';};
        document.querySelector('#post').onclick=()=>{window.postClicks++;c.close();if(!o.noSuccess){const s=document.createElement('div');s.setAttribute('role','status');s.textContent='Post successful.';document.body.append(s);}};
        if(o.oldText)c.querySelector('[contenteditable]').textContent='old';
        if(o.oldMedia)document.querySelector('#attachments').innerHTML='<figure><svg id="image-medium"></svg><img hidden src="data:image/png;base64,PNG"></figure>';
        if(o.oldFiles){const dt=new DataTransfer();dt.items.add(new File(['old'],'old.png',{type:'image/png'}));f.files=dt.files;}
        if(o.scopedOldFiles){const old=document.createElement('input');old.type='file';old.hidden=true;const dt=new DataTransfer();dt.items.add(new File(['old'],'old.png',{type:'image/png'}));old.files=dt.files;m.append(old);}
        if(o.oldLarge)m.insertAdjacentHTML('beforeend','<img alt="Image Preview" hidden src="data:image/png;base64,PNG">');
        if(o.oldProgress)m.insertAdjacentHTML('beforeend','<div role="progressbar">Uploading old media</div>');
        if(o.feedName)document.querySelector('#shareboxProfilePictureComponentRef svg').setAttribute('aria-label','Other');
        if(o.hiddenCaptcha)document.body.insertAdjacentHTML('beforeend','<iframe src="https://test/captcha?size=invisible" style="display:none"></iframe>');
        if(o.visibleCaptcha)document.body.insertAdjacentHTML('beforeend','<iframe src="https://test/captcha"></iframe>');
        </script>'''.replace('OPTIONS', json.dumps(options)).replace('PNG', __import__('base64').b64encode(self.images[0].buffer).decode())
        self.page.route('**/*', lambda r: r.abort())
        self.page.route('https://www.linkedin.com/feed/', lambda r: r.fulfill(body=html, content_type='text/html'))

    def test_native_chooser_ordered_previews_and_exact_draft(self):
        self.load(hiddenCaptcha=True)
        self.assertEqual(posts.publish_post(self.page, '  hello\n\nworld  ', self.images, 2500), {'status':'posted','url':None})
        self.assertEqual(self.page.evaluate('[postClicks,nextClicks,pickerClicks]'), [1,1,4])
        self.assertEqual(self.page.evaluate('uploaded'), [{'name':i.name,'bytes':list(i.buffer)} for i in self.images])

    def test_start_waits_for_hydration_without_repeat_click(self):
        self.load(hydrationDelay=300)
        posts.publish_post(self.page,'hello world',self.images[:1],2500)
        self.assertEqual(self.page.evaluate('startClicks'),1)

    def test_scoped_old_filelist_and_transition_reorder_are_rejected(self):
        for option in ('scopedOldFiles','reverseNext','changedSource','nonBlob'):
            with self.subTest(option=option):
                self.load(**{option:True})
                with self.assertRaises(AgentError) as e:
                    posts.publish_post(self.page,'hello world',self.images,2500)
                self.assertEqual(e.exception.code,'upload_failed')
                self.assertEqual(self.page.evaluate('postClicks'),0)
                if option=='scopedOldFiles':
                    self.assertEqual(self.page.evaluate('uploaded'),[])
                self.page.unroute_all()

    def test_regenerated_blob_urls_preserve_verified_byte_order(self):
        self.load(regeneratedNext=True)
        self.assertEqual(posts.publish_post(self.page,'hello world',self.images,2500),{'status':'posted','url':None})
        self.assertEqual(self.page.evaluate('postClicks'),1)

    def test_reorder_after_byte_verification_cannot_be_rebaselined_by_guard(self):
        self.load()
        capture = posts._capture_final_dispatch
        def reordered(*args, **kwargs):
            self.page.evaluate('''() => {const scope=document.querySelector('#attachments');scope.append(scope.firstElementChild);}''')
            return capture(*args, **kwargs)
        with patch.object(posts,'_capture_final_dispatch',reordered), self.assertRaises(AgentError) as e:
            posts.publish_post(self.page,'hello world',self.images,2500)
        self.assertEqual(e.exception.code,'upload_failed')
        self.assertEqual(self.page.evaluate('postClicks'),0)

    def test_personal_picker_and_empty_draft_fail_closed(self):
        for option,code in [('company','unsupported_identity'),('feedName','unsupported_identity'),('wrongName','unsupported_identity'),('unchecked','unsupported_identity'),('duplicate','unsupported_identity'),('lateName','unsupported_identity'),('oldText','text_mismatch'),('oldMedia','upload_failed'),('oldFiles','upload_failed'),('oldLarge','upload_failed'),('oldProgress','upload_failed'),('order','upload_failed'),('broken','dom_timeout'),('visibleCaptcha','browser_challenge')]:
            with self.subTest(option=option):
                self.load(**{option:True})
                with self.assertRaises(AgentError) as e:posts.publish_post(self.page,'hello world',self.images,1200)
                self.assertEqual(e.exception.code,code)
                self.assertEqual(self.page.evaluate('postClicks'),0)
                self.page.unroute_all()

    def test_final_dispatch_rechecks_personal_evidence(self):
        for option in ('dispatchName','dispatchMarker'):
            self.load(**{option:True})
            with self.assertRaises(AgentError) as e:posts.publish_post(self.page,'hello world',self.images,2500)
            self.assertEqual(e.exception.code,'unsupported_identity')
            self.assertEqual(self.page.evaluate('postClicks'),0)
            self.page.unroute_all()

    def test_chooser_payload_is_verified(self):
        self.load()
        original=FileChooser.set_files
        def altered(chooser,files,**kwargs):return original(chooser,list(reversed(files)),**kwargs)
        with patch.object(FileChooser,'set_files',altered), self.assertRaises(AgentError) as e:
            posts.publish_post(self.page,'hello world',self.images,2500)
        self.assertEqual(e.exception.code,'upload_failed')
        self.assertEqual(self.page.evaluate('postClicks'),0)
