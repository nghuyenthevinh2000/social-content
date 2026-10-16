"""Test File Tree and Right Hover Asset Inspector in hook redesign."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as p:
            options = {'headless': True}
            if Path(CHROME).exists():
                options['executable_path'] = CHROME
            browser = p.chromium.launch(**options)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.goto(f'{base}/four-stage-loop-dashboard-redesigned.html')

            # 1. Open project file tree drawer
            expect(page.locator('#project-sidebar')).to_have_attribute('data-collapsed', 'true')
            page.locator('#project-nav-toggle').click()
            expect(page.locator('#project-sidebar')).to_have_attribute('data-collapsed', 'false')

            # 2. Check File tree has brand assets
            expect(page.locator('#brand-asset-count')).to_contain_text('3 tệp')
            expect(page.locator('#brand-asset-file-list .tree-file')).to_have_count(3)

            # 3. Click first brand asset to open right hover flyout
            page.locator('#brand-asset-file-list .tree-file').first.click()
            expect(page.locator('#asset-inspector-flyout')).to_have_attribute('data-open', 'true')
            expect(page.locator('#inspector-asset-title')).to_have_text('raw-footage-serum-01.mp4')
            expect(page.locator('#inspector-preview-stage video')).to_be_visible()

            # 4. Rename asset in inspector
            page.locator('#btn-rename-asset').click()
            expect(page.locator('#inline-rename-form')).to_be_visible()
            page.locator('#rename-input').fill('broll-rau-ma-chuan.mp4')
            page.locator('#inline-rename-form button[type=submit]').click()
            expect(page.locator('#inspector-asset-title')).to_have_text('broll-rau-ma-chuan.mp4')
            expect(page.locator('#brand-asset-file-list .tree-file').first).to_contain_text('broll-rau-ma-chuan.mp4')

            # 5. Hook assignment in inspector
            page.locator('#btn-assign-asset').click()
            expect(page.locator('#hook-assign-box')).to_be_visible()
            page.locator('.hook-chip[data-hook-id="H02"]').click()
            expect(page.locator('#meta-usage')).to_contain_text('H02')

            # 6. Close inspector and close sidebar drawer
            page.locator('#inspector-close-btn').click()
            expect(page.locator('#asset-inspector-flyout')).to_have_attribute('data-open', 'false')
            page.locator('#sidebar-close-btn').click()
            expect(page.locator('#project-sidebar')).to_have_attribute('data-collapsed', 'true')

            # 7. Test file upload in AI chat box
            test_file = ROOT / 'wireframe_preview.json'
            page.locator('#chat-file-input').set_input_files(str(test_file))
            expect(page.locator('#chat-attachments-staging')).to_be_visible()
            expect(page.locator('.staged-chip')).to_contain_text('wireframe_preview.json')
            page.locator('#chat-input').fill('Đính kèm tài liệu tham khảo này nhé.')
            page.locator('#chat-form button[type=submit]').click()

            # Check that message in chat contains the attachment chip
            expect(page.locator('.msg-attachment-chip')).to_contain_text('wireframe_preview.json')
            # Check that the brand assets tree in sidebar increased
            expect(page.locator('#brand-asset-count')).to_contain_text('4 tệp')
            expect(page.locator('#brand-asset-file-list')).to_contain_text('wireframe_preview.json')

            # Click attachment chip inside chat to open inspector
            page.locator('.msg-attachment-chip').first.click()
            expect(page.locator('#asset-inspector-flyout')).to_have_attribute('data-open', 'true')
            expect(page.locator('#inspector-asset-title')).to_have_text('wireframe_preview.json')
            page.locator('#inspector-close-btn').click()

            # 8. Check no overflow across viewports
            for w in [1440, 1024, 768, 390, 320]:
                page.set_viewport_size({'width': w, 'height': 800})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow at {w}px'

            print('PASS: File Tree navigation, brand assets inspection, renaming, hook assignment, chat file upload, and zero overflow.')
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

if __name__ == '__main__':
    main()
