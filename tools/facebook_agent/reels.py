"""Capture visible recommendations without interacting with engagement controls."""

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from . import selectors


def reel_url(url):
    parsed = urlsplit(url)
    match = re.fullmatch(r'/reel/(\d+)/?', parsed.path)
    if parsed.hostname not in ('www.facebook.com', 'facebook.com') or not match:
        return None
    return f'https://www.facebook.com/reel/{match[1]}'


SNAPSHOT = """() => {
    const visible = el => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight
            && r.right > 0 && r.left < innerWidth && s.visibility !== 'hidden'
            && s.display !== 'none';
    };
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const text = [];
    while (walker.nextNode()) {
        const node = walker.currentNode;
        if (!node.textContent.trim() || !visible(node.parentElement)) continue;
        const range = document.createRange();
        range.selectNodeContents(node);
        const r = range.getBoundingClientRect();
        if (r.width && r.height && r.bottom > 0 && r.top < innerHeight)
            text.push(node.textContent.trim());
    }
    return {
        text: text.join('\\n'),
        links: [...document.querySelectorAll('a[href]')].filter(visible)
            .map(a => ({text: a.innerText, url: a.href})),
        buttons: [...document.querySelectorAll('[role="button"],button')]
            .filter(visible).map(a => ({text: a.innerText, label: a.getAttribute('aria-label')}))
    };
}"""


def collect_reels(browser, page_id, limit=15):
    profile = browser.check_authenticated(page_id=page_id)
    page = browser.page
    browser.keep_page = True
    page.goto('https://www.facebook.com/reel/', wait_until='domcontentloaded',
              timeout=browser.timeout_ms)
    page.wait_for_timeout(4000)
    records = []
    seen = set()
    for _ in range(limit):
        selectors.check_block(page)
        snapshot = page.evaluate(SNAPSHOT)
        url = reel_url(page.url)
        key = url or snapshot['text']
        if key not in seen:
            seen.add(key)
            records.append({'order': len(records) + 1, 'url': url,
                            'browser_url': page.url,
                            'observed_at': datetime.now(timezone.utc).isoformat(),
                            **snapshot})
        # Scroll only: no likes, follows, shares, or recommendation controls.
        page.mouse.move(page.viewport_size['width'] // 2 if page.viewport_size else 600, 400)
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(2500)
    return {'profile': profile, 'records': records,
            'scope': 'Personalized feed observations; language and individual reel identity require review.'}
