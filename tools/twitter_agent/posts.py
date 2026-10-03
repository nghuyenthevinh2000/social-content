"""Post extraction and bounded read operations for timeline, search, and thread."""

import math
import re
import time
import urllib.parse
from datetime import datetime
from typing import Optional

from .models import AgentError, Target, normalize_target
from .pacing import get_pacer
from . import dom, selectors


EXTRACT_ARTICLES_JS = r"""
selectors => {
    const articles = Array.from(document.querySelectorAll(selectors.ARTICLE));
    const results = [];
    
    function isInsideQuote(el, article) {
        let parent = el.parentElement;
        while (parent && parent !== article) {
            if (parent.matches(selectors.QUOTE_TWEET)) {
                return true;
            }
            if (parent.getAttribute('role') === 'link' && parent.tagName !== 'A') {
                return true;
            }
            parent = parent.parentElement;
        }
        return false;
    }

    for (const article of articles) {
        // Status link / time / id
        const timeElements = Array.from(article.querySelectorAll(selectors.TIMESTAMP));
        let topTime = null;
        let topLink = null;
        for (const timeEl of timeElements) {
            if (!isInsideQuote(timeEl, article)) {
                const link = timeEl.closest(selectors.TIMESTAMP_LINK);
                if (link && !isInsideQuote(link, article)) {
                    topTime = timeEl;
                    topLink = link;
                    break;
                }
            }
        }
        if (!topLink) {
            const links = Array.from(article.querySelectorAll(selectors.TIMESTAMP_LINK));
            for (const link of links) {
                if (!isInsideQuote(link, article)) {
                    topLink = link;
                    break;
                }
            }
        }
        if (!topLink) continue;

        const href = topLink.getAttribute('href') || '';
        const match = href.match(/\/status\/([0-9]+)/);
        if (!match) continue;
        const id = match[1].replace(/^0+/, '');
        if (!id) continue;

        // Author
        let authorObj = { name: '', handle: '', raw: '' };
        const userNames = Array.from(article.querySelectorAll(selectors.AUTHOR));
        for (const un of userNames) {
            if (!isInsideQuote(un, article)) {
                const raw = un.innerText || '';
                const handleMatch = raw.match(/@([A-Za-z0-9_]+)/);
                authorObj = {
                    name: handleMatch ? raw.substring(0, handleMatch.index).trim() : raw.trim(),
                    handle: handleMatch ? '@' + handleMatch[1] : '',
                    raw: raw.trim()
                };
                break;
            }
        }

        // Text
        let text = '';
        const tweetTexts = Array.from(article.querySelectorAll(selectors.TWEET_TEXT));
        for (const tt of tweetTexts) {
            if (!isInsideQuote(tt, article)) {
                text = tt.innerText || '';
                break;
            }
        }

        function parseMetric(val) {
            if (!val) return 0;
            val = val.trim().replace(/,/g, '');
            let multiplier = 1;
            if (val.endsWith('K') || val.endsWith('k')) {
                multiplier = 1000;
                val = val.slice(0, -1);
            } else if (val.endsWith('M') || val.endsWith('m')) {
                multiplier = 1000000;
                val = val.slice(0, -1);
            } else if (val.endsWith('B') || val.endsWith('b')) {
                multiplier = 1000000000;
                val = val.slice(0, -1);
            }
            const num = parseFloat(val);
            return isNaN(num) ? 0 : Math.round(num * multiplier);
        }

        const replyEl = article.querySelector(selectors.REPLY_BUTTON);
        const retweetEl = article.querySelector(selectors.RETWEET_BUTTON);
        const likeEl = article.querySelector(selectors.LIKE_BUTTON);
        const analyticsEl = article.querySelector(selectors.ANALYTICS_LINK);

        const repliesCount = parseMetric(replyEl ? replyEl.innerText : '0');
        const retweetsCount = parseMetric(retweetEl ? retweetEl.innerText : '0');
        const likesCount = parseMetric(likeEl ? likeEl.innerText : '0');
        const viewsCount = parseMetric(analyticsEl ? analyticsEl.innerText : '0');

        const isAd = Array.from(article.querySelectorAll(selectors.AD_LABEL)).some(el => el.textContent === 'Ad' || el.textContent === 'Promoted');

        const timestamp = topTime ? (topTime.getAttribute('datetime') || topTime.textContent || null) : null;

        results.push({
            id: id,
            url: `https://x.com/i/status/${id}`,
            author: authorObj,
            text: text,
            timestamp: timestamp,
            is_ad: isAd,
            metrics: {
                replies: repliesCount,
                retweets: retweetsCount,
                likes: likesCount,
                views: viewsCount,
                total: repliesCount + retweetsCount + likesCount,
            }
        });
    }
    return results;
}
"""


def score_tweet(post: dict, now: Optional[float] = None, post_timestamp_override: Optional[float] = None) -> float:
    if post.get('is_ad'):
        return 0.0

    now_time = now if now is not None else time.time()
    
    # 1. Age factor (weight 40)
    post_time = post_timestamp_override
    if post_time is None and post.get('timestamp'):
        ts_str = str(post['timestamp']).strip()
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            post_time = dt.timestamp()
        except Exception:
            import re
            m = re.fullmatch(r'([0-9]+)\s*([smhd])', ts_str)
            if m:
                val, unit = int(m.group(1)), m.group(2)
                multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
                post_time = now_time - (val * multipliers[unit])
            else:
                post_time = None

    if post_time is not None:
        age_minutes = max(0.0, (now_time - post_time) / 60.0)
        if age_minutes <= 5.0:
            age_factor = 1.0
        elif age_minutes <= 15.0:
            age_factor = 0.7
        elif age_minutes <= 30.0:
            age_factor = 0.4
        else:
            age_factor = 0.1
    else:
        age_factor = 0.5

    # 2. Competition factor (weight 30)
    metrics = post.get('metrics') or {}
    replies = metrics.get('replies', 0)
    if replies < 10:
        comp_factor = 1.0
    elif replies <= 20:
        comp_factor = 0.7
    elif replies <= 50:
        comp_factor = 0.3
    else:
        comp_factor = 0.05

    # 3. Velocity / engagement factor (weight 30)
    total = metrics.get('total', 0)
    # Log-scaled engagement
    velocity_factor = min(1.0, math.log10(max(1, total) + 1) / 3.0)

    total_score = (age_factor * 40.0) + (comp_factor * 30.0) + (velocity_factor * 30.0)
    return round(total_score, 1)


def read_posts(page, mode: str, value: Optional[str] = None, limit: int = 10, *, search_mode: str = 'latest') -> dict:
    """Read posts with bounded scrolling, deduplication, and safe extraction."""
    if not isinstance(limit, int) or limit < 1 or limit > 100:
        raise AgentError('invalid_limit', 'Limit must be between 1 and 100.')

    if search_mode not in ('latest', 'top'):
        raise AgentError('invalid_search_mode', 'search-mode must be latest or top.')

    if mode not in ('timeline', 'search', 'thread'):
        raise AgentError('invalid_mode', f'Unsupported read mode: {mode}.')

    # In unit tests, fixtures are pre-loaded with set_content() on about:blank.
    # If the page already has articles in DOM, skip navigation to preserve fixture.
    current_url = getattr(page, 'url', '') or ''
    has_fixture = False
    if current_url == 'about:blank' or current_url.startswith('data:'):
        try:
            has_fixture = page.locator(dom.ARTICLE).count() > 0 or page.locator(dom.PRIMARY_COLUMN).count() > 0
        except Exception:
            pass

    if not has_fixture:
        block = selectors.detect_block(page)
        if block:
            raise block

        if mode == 'timeline':
            get_pacer().wait('navigation')
            page.goto('https://x.com/home', wait_until='domcontentloaded')
        elif mode == 'search':
            if not value or not value.strip():
                raise AgentError('invalid_search_query', 'Search query cannot be empty.')
            encoded = urllib.parse.quote_plus(value.strip())
            feed = 'live' if search_mode == 'latest' else 'top'
            action = 'profile' if re.fullmatch(r'from:[A-Za-z0-9_]+', value.strip()) else 'search'
            get_pacer().wait(action)
            page.goto(f'https://x.com/search?q={encoded}&f={feed}', wait_until='domcontentloaded')
        elif mode == 'thread':
            if not value:
                raise AgentError('invalid_target', 'Thread target is required.')
            target = normalize_target(value)
            get_pacer().wait('navigation')
            page.goto(target.url, wait_until='domcontentloaded')

        try:
            page.wait_for_selector(dom.ARTICLE, timeout=5000)
        except Exception:
            pass
        block = selectors.detect_block(page)
        if block:
            raise block

    start_time = time.time()
    posts_by_id = {}
    scrolls = 0
    no_progress_rounds = 0
    stop_reason = 'no_progress'

    while True:
        # Check blocks
        block = selectors.detect_block(page)
        if block:
            raise block

        # Extract articles currently in DOM
        current_batch = page.evaluate(EXTRACT_ARTICLES_JS, {
            'ARTICLE': dom.ARTICLE,
            'QUOTE_TWEET': dom.QUOTE_TWEET,
            'TIMESTAMP': dom.TIMESTAMP,
            'TIMESTAMP_LINK': dom.TIMESTAMP_LINK,
            'AUTHOR': dom.AUTHOR,
            'TWEET_TEXT': dom.TWEET_TEXT,
            'REPLY_BUTTON': dom.REPLY_BUTTON,
            'RETWEET_BUTTON': dom.RETWEET_BUTTON,
            'LIKE_BUTTON': dom.LIKE_BUTTON,
            'ANALYTICS_LINK': dom.ANALYTICS_LINK,
            'AD_LABEL': dom.AD_LABEL,
        })
        new_in_batch = 0
        for post in current_batch:
            if post['id'] not in posts_by_id:
                posts_by_id[post['id']] = post
                new_in_batch += 1
                if len(posts_by_id) >= limit:
                    break

        if len(posts_by_id) >= limit:
            stop_reason = 'limit_reached'
            break

        if new_in_batch == 0:
            no_progress_rounds += 1
            if no_progress_rounds >= 3:
                stop_reason = 'no_progress'
                break
        else:
            no_progress_rounds = 0

        if scrolls >= 10:
            stop_reason = 'scroll_limit_reached'
            break

        if time.time() - start_time >= 30.0:
            stop_reason = 'timeout'
            break

        # Scroll
        if not has_fixture:
            # Intentional pacing does not consume the active collection budget.
            start_time += get_pacer().wait('scroll')
        page.evaluate('window.scrollBy(0, window.innerHeight * 1.5)')
        scrolls += 1
        page.wait_for_timeout(500)

    post_list = list(posts_by_id.values())
    for post in post_list:
        post['score'] = score_tweet(post)

    # Build result
    result = {
        'posts': post_list,
        'scrolls': scrolls,
        'reason': stop_reason,
    }

    if mode == 'thread':
        result['partial'] = True
        target_id = normalize_target(value).id if value else None
        target_post = posts_by_id.get(target_id)
        if target_post is None and post_list:
            # Fallback if first post is the target
            target_post = post_list[0]
        result['target'] = target_post
    else:
        if stop_reason == 'limit_reached':
            result['partial'] = False
        else:
            result['partial'] = len(post_list) > 0 and len(post_list) < limit

    return result
