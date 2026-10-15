"""Run with the existing environment: python projects/hook-validation-loop/screens/test-redesign.py."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Thread

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parent
OUTPUT = Path('/private/var/folders/nm/hp2tb73d0l75gl6jzvy6jfnm0000gn/T/opencode/hook-redesign')
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def check_no_overflow(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Page overflows horizontally'


def main():
    OUTPUT.mkdir(exist_ok=True)
    originals = {name: (ROOT / name).read_bytes() for name in [
        'first-onboarding-screen.html', 'four-stage-loop-dashboard.html', 'screen-ui.css'
    ]}
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as p:
            options = {'headless': True}
            if Path(CHROME).exists():
                options['executable_path'] = CHROME
            browser = p.chromium.launch(**options)
            context = browser.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'{base}/first-onboarding-screen-redesigned.html')
            expect(page.locator('#workspace-entry')).to_be_hidden()
            page.screenshot(path=str(OUTPUT / 'onboarding-desktop.png'))
            page.locator('#sample-product').click()
            expect(page.locator('.message.user')).to_have_count(1)
            page.locator('#workspace-entry').click()
            expect(page.locator('.message.user')).to_have_count(1)
            chat = page.locator('.chat-panel').bounding_box()
            dashboard = page.locator('.dashboard-panel').bounding_box()
            assert abs(chat['width'] / (chat['width'] + dashboard['width']) - .3) < .001
            expect(page.locator('#continue-video')).to_be_disabled()
            expect(page.locator('.hook-mock-video')).to_have_count(4)
            # Mock clip controls must not toggle hook selection.
            page.locator('.hook-mock-video').first.evaluate('(video) => video.play()')
            page.wait_for_function('document.querySelector(".hook-mock-video").currentTime > 0.2')
            assert abs(page.locator('.hook-mock-video').first.evaluate('(video) => video.duration') - 3) < .1
            expect(page.locator('#continue-video')).to_be_disabled()
            page.locator('.hook-mock-video').nth(1).evaluate('(video) => video.play()')
            assert page.locator('.hook-mock-video').first.evaluate('(video) => video.paused')
            page.locator('.hook-mock-video').nth(1).evaluate('(video) => video.pause()')

            # Interview lives in chat and proceeds one question at a time.
            for answer in ['Người có da nhạy cảm', 'Muốn ít bước chăm sóc', 'Gần gũi']:
                page.locator('#chat-input').fill(answer)
                page.locator('#chat-input').press('Enter')
            expect(page.locator('#chat-log')).to_contain_text('chưa dùng AI')
            for index in [0, 1, 3]:
                page.locator('.hook-card input').nth(index).check()
            expect(page.locator('#selection-count')).to_have_text('Đã chọn 3 hook')
            page.screenshot(path=str(OUTPUT / 'hooks-desktop.png'))
            page.locator('#continue-video').click()
            expect(page.locator('.video-card')).to_have_count(3)
            assert page.locator('.video-card').evaluate_all('(cards) => cards.map(c => c.dataset.hook)') == ['H01', 'H02', 'H04']
            for card in page.locator('.video-card').all():
                expect(card.get_by_role('button', name='Edit in chat')).to_be_visible()
                expect(card.get_by_role('button', name='Approve for posting')).to_be_disabled()
            page.screenshot(path=str(OUTPUT / 'videos-desktop.png'))

            # A real, synthetic test asset exercises native playback and reversible approval.
            if shutil.which('ffmpeg'):
                with tempfile.TemporaryDirectory(dir=OUTPUT) as temp:
                    video = Path(temp) / 'test-video.mp4'
                    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                                    '-i', 'color=c=0x63784f:s=180x320:r=12', '-t', '1',
                                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video)], check=True)
                    first = page.locator('.video-card').first
                    first.locator('input[type=file]').set_input_files(str(video))
                    first = page.locator('.video-card').first
                    expect(first.get_by_role('button', name='Approve for posting')).to_be_enabled()
                    first.get_by_role('button', name='Approve for posting').click()
                    expect(page.locator('#approval-count')).to_have_text('Đã duyệt 1/3')
                    first.get_by_role('button', name='Undo approval').click()
                    expect(page.locator('#approval-count')).to_have_text('Đã duyệt 0/3')
                    first.get_by_role('button', name='Approve for posting').click()
                    first.get_by_role('button', name='Edit in chat').click()
                    page.locator('#chat-input').fill('Một câu mở đầu mới do người dùng viết.')
                    page.locator('#chat-input').press('Enter')
                    expect(page.locator('.video-card').first.locator('.video-hook-caption')).to_have_text('Một câu mở đầu mới do người dùng viết.')
                    expect(page.locator('.video-card').first.get_by_role('button', name='Approve for posting')).to_be_disabled()
                    expect(page.locator('#approval-count')).to_have_text('Đã duyệt 0/3')

            page.locator('#tab-metrics').click()
            expect(page.locator('#metrics-body > tr:not(.detail-row)')).to_have_count(4)
            expect(page.locator('#metric-views')).to_have_text('121.900')
            expect(page.locator('#metric-retention')).to_have_text('58,5%')
            expect(page.locator('#metric-watch')).to_have_text('11,7 giây')
            page.locator('#platform-filter').select_option('TikTok')
            expect(page.locator('#filter-description')).to_have_text('TikTok · 24 giờ')
            expect(page.locator('#metric-views')).to_have_text('56.000')
            page.locator('#window-filter').select_option('6 giờ')
            expect(page.locator('#metric-views')).to_have_text('19.040')
            page.locator('#window-filter').select_option('72 giờ')
            page.locator('#platform-filter').select_option('Tất cả nền tảng')
            expect(page.locator('#metric-views')).to_have_text('219.420')
            page.locator('#metrics-body button').first.click()
            expect(page.locator('#detail-H01')).to_be_visible()
            expect(page.locator('#detail-H01 .platform-detail')).to_have_count(3)
            page.screenshot(path=str(OUTPUT / 'metrics-desktop.png'))
            page.locator('#tab-results').click()
            expect(page.locator('#mock-winner')).to_have_text('H01 giữ chân tốt nhất trong vòng mẫu.')
            expect(page.locator('#mock-total-views')).to_have_text('219.420 lượt xem mẫu')
            expect(page.locator('#mock-ranking .ranking-row')).to_have_count(4)
            expect(page.locator('#mock-ranking .ranking-row').first).to_contain_text('67,8%')
            page.locator('#learning').fill('Chỉ so sánh các phần mở đầu.')
            page.locator('#notes-form button').click()
            page.locator('#hypothesis').fill('Thử câu hỏi ngắn hơn.')
            page.locator('#hypothesis-form button').click()
            expect(page.locator('#draft-note')).to_be_visible()
            page.screenshot(path=str(OUTPUT / 'results-desktop.png'))
            page.reload()
            expect(page.locator('#learning')).to_have_value('Chỉ so sánh các phần mở đầu.')
            expect(page.locator('#draft-note')).to_be_visible()
            expect(page.locator('#results-approval-count')).to_have_text('0 đã duyệt')

            # Keyboard-accessible tabs and every responsive state.
            page.locator('#tab-results').focus()
            page.keyboard.press('Home')
            expect(page.locator('#tab-hooks')).to_be_focused()
            for width in [1440, 1024, 768, 390, 320]:
                page.set_viewport_size({'width': width, 'height': 900})
                for stage in ['hooks', 'video', 'metrics', 'results']:
                    page.locator(f'#tab-{stage}').click()
                    check_no_overflow(page)
                if width == 390:
                    page.locator('#tab-video').click()
                    page.screenshot(path=str(OUTPUT / 'videos-mobile.png'))
                    page.locator('.video-card').first.get_by_role('button', name='Edit in chat').click()
                    expect(page.locator('.chat-panel')).to_be_visible()
                    expect(page.locator('#chat-input')).to_be_focused()
                    page.locator('#cancel-edit').click()
                    page.locator('[data-view=dashboard]').click()

            # Full-screen chat is also usable without horizontal overflow on mobile.
            page.goto(f'{base}/first-onboarding-screen-redesigned.html')
            check_no_overflow(page)
            expect(page.locator('.message.user').first).to_contain_text('serum rau má')
            page.screenshot(path=str(OUTPUT / 'onboarding-mobile.png'))
            # The sample metrics/results must also be populated with no hook selections.
            fresh = browser.new_page(viewport={'width': 390, 'height': 900}, reduced_motion='reduce')
            fresh.goto(f'{base}/four-stage-loop-dashboard-redesigned.html#metrics')
            expect(fresh.locator('#metric-views')).to_have_text('121.900')
            check_no_overflow(fresh)
            fresh.screenshot(path=str(OUTPUT / 'metrics-mobile.png'))
            fresh.locator('#tab-results').click()
            expect(fresh.locator('#mock-ranking .ranking-row')).to_have_count(4)
            check_no_overflow(fresh)
            fresh.screenshot(path=str(OUTPUT / 'results-mobile.png'))
            fresh.close()
            assert not errors, errors
            browser.close()
        for name, content in originals.items():
            assert (ROOT / name).read_bytes() == content, f'Original changed: {name}'
        print('PASS: onboarding, interview, 30/70 split, selections, three video cards, playback,')
        print('approval/undo/edit invalidation, four playable mock hooks, filtered mock metrics,')
        print('consistent loop ranking, notes persistence, keyboard tabs and five viewport sizes.')
        print(f'Screenshots: {OUTPUT}')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
