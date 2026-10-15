"""Create four silent 3-second UI demo clips, not AI-generated product footage.

Run with the existing environment: python projects/hook-validation-loop/screens/generate-mock-hooks.py
Requires the already installed Playwright, Chrome and ffmpeg.
"""

from html import escape
from pathlib import Path
import subprocess
import tempfile

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parent
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
HOOKS = [
    ('H01', 'sage', 'Da nhạy cảm? Bắt đầu với một bước chăm sóc đơn giản.'),
    ('H02', 'clay', 'Bạn chọn serum rau má dựa trên điều gì?'),
    ('H03', 'olive', 'Thêm sản phẩm chưa chắc là điều làn da bạn cần.'),
    ('H04', 'sage', 'Đây là cách mình đưa serum rau má vào thói quen hằng ngày.'),
]


def main():
    assets = ROOT / 'assets'
    assets.mkdir(exist_ok=True)
    scratch = Path('/private/var/folders/nm/hp2tb73d0l75gl6jzvy6jfnm0000gn/T/opencode')
    with tempfile.TemporaryDirectory(dir=scratch) as temp, sync_playwright() as p:
        options = {'headless': True}
        if Path(CHROME).exists():
            options['executable_path'] = CHROME
        browser = p.chromium.launch(**options)
        page = browser.new_page(viewport={'width': 540, 'height': 960}, device_scale_factor=1)
        for index, (hook_id, theme, text) in enumerate(HOOKS):
            page.set_content(f'''<html lang="vi"><meta charset="utf-8"><body>
              <div class="video-preview" data-theme="{theme}"><div class="storyboard">
                <span class="storyboard-label">{hook_id} / MOCK VIDEO · 03 GIÂY</span>
                <div class="product-art"><div class="product-shadow"></div><div class="bottle"></div></div>
                <p class="storyboard-hook">{escape(text)}</p>
              </div></div></body></html>''')
            page.add_style_tag(content=(ROOT / 'redesigned-ui.css').read_text())
            page.add_style_tag(content=f'''
              body {{margin:0;font-family:Arial,sans-serif}}
              .video-preview {{width:540px;height:960px;max-height:none;margin:0;border-radius:0}}
              .storyboard {{padding:46px}}
              .storyboard-label {{font-size:17px;letter-spacing:.08em}}
              .storyboard-hook {{font-size:34px;line-height:1.4;letter-spacing:-1px;padding-bottom:35px}}
              .storyboard-hook::before {{width:55px;height:3px;margin-bottom:25px}}
              .product-art {{inset:20% 0 30%;transform:rotate({[-10, 8, -3, 12][index]}deg)}}
              .bottle::after {{font-size:18px;padding-top:25px}}
            ''')
            image = Path(temp) / f'{hook_id}.png'
            page.screenshot(path=str(image))
            # Motion is intentionally limited to a gentle zoom of the labeled demo artwork.
            output = assets / f'mock-hook-{hook_id}.mp4'
            subprocess.run([
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-i', str(image),
                '-vf', "scale=1080:1920,zoompan=z='1+0.025*on/89':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=90:s=360x640:fps=30,format=yuv420p",
                '-t', '3', '-an', '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
                '-movflags', '+faststart', str(output)
            ], check=True)
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(output),
                            '-frames:v', '1', str(assets / f'mock-hook-{hook_id}.jpg')], check=True)
            print(f'{output.name}: {output.stat().st_size:,} bytes')
        browser.close()


if __name__ == '__main__':
    main()
