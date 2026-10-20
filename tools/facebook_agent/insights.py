"""Read-only, evidence-first capture of the active Page's Insights dashboard."""

from datetime import datetime, timezone
import base64
import binascii
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import selectors
from .models import AgentError


READ_ONLY_LABELS = ('Insights', 'Overview', 'Content', 'Audience', 'See insights',
                    'View insights', 'Retention', 'Demographics', 'Reach', 'Engagement',
                    'Views', 'Followers', 'Video', 'Videos', 'Reels', 'See more',
                    'Top countries', 'Source', 'Traffic', 'Age and gender',
                    'Export data', 'Create new data report', 'Report history',
                    'Thông tin chi tiết', 'Tổng quan', 'Nội dung', 'Đối tượng')

SNAPSHOT = """() => ({
    text: document.body.innerText,
    links: [...document.querySelectorAll('a[href]')]
        .filter(el => el.getClientRects().length)
        .map(el => ({text: el.innerText, url: el.href})),
    controls: [...document.querySelectorAll('button,[role="button"],[role="tab"]')]
        .filter(el => el.getClientRects().length)
        .map(el => ({text: el.innerText, label: el.getAttribute('aria-label')})),
    demographic_panel_html: [...document.querySelectorAll('div')]
        .filter(el => el.getClientRects().length && el.innerText.includes('Who viewed your content')
            && el.innerText.includes('Age and gender') && !el.innerText.includes('Link clicks'))
        .sort((a, b) => a.outerHTML.length - b.outerHTML.length)[0]?.outerHTML.slice(0, 60000) || null,
    discovery_panels: [...document.querySelectorAll('div')]
        .filter(el => el.getClientRects().length && el.innerText.includes('How people find your content')
            && el.innerText.includes('Traffic') && !el.innerText.includes('Who viewed your content'))
        .sort((a, b) => a.outerHTML.length - b.outerHTML.length)
        .slice(0, 1).map(el => ({text: el.innerText,
            selected_tab: [...el.querySelectorAll('[aria-pressed="true"], [aria-selected="true"]')]
                .map(tab => tab.innerText.trim()).find(label => ['Traffic', 'Source'].includes(label)) || null})),
    age_gender_segments: [...document.querySelectorAll('[data-metric]')]
        .filter(el => ['MALE', 'FEMALE', 'UNKNOWN'].includes(el.dataset.metric))
        .map(el => {
            let row = el.parentElement;
            while (row && !/^(\\d{2}-\\d{2}|65\\+)\\s/.test(row.innerText)) row = row.parentElement;
            const age = row?.innerText.match(/^(\\d{2}-\\d{2}|65\\+)/)?.[1];
            return {age, gender: el.dataset.metric, bar_width: el.style.width,
                row_text: row?.innerText || null};
        }).filter(row => row.age)
})"""


def validate_url(url, page_id):
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    if (parsed.scheme != 'https' or parsed.hostname != 'www.facebook.com'
            or not (parsed.path == '/professional_dashboard/'
                    or parsed.path.startswith(('/professional_dashboard/', '/insights/', '/content/insights/')))):
        raise AgentError('invalid_arguments', 'Only Facebook professional dashboard/Insights URLs are allowed.')
    for key in ('asset_id', 'page_id'):
        if key in query and query[key] != [page_id]:
            raise AgentError('invalid_arguments', 'Insights URL points to a different Page.')
    if parsed.path.startswith('/content/insights/'):
        try:
            identity = base64.b64decode(query.get('content_id', [''])[0], validate=True).decode()
        except (ValueError, UnicodeError, binascii.Error):
            identity = ''
        if not identity.startswith(f'S:_I{page_id}:'):
            raise AgentError('invalid_arguments', 'Content Insights ID does not belong to the expected Page.')
    return url


def post_metrics(text):
    """Parse labeled English post cards only; never turn chart axes into data."""
    text = text.replace('\ufeff', '')
    if not re.search(r'^Post insights$', text, re.M):
        return None

    def number(pattern):
        match = re.search(pattern, text, re.M)
        if not match:
            return None
        value = match[1].replace(',', '')
        return float(value) if '.' in value else int(value)

    result = {
        'views': number(r'^Views\n([\d,]+)$'),
        'viewers': number(r'^Viewers\n([\d,]+)$'),
        'three_second_views': number(r'^3-second views\n([\d,]+)$'),
        'average_watch_time_seconds': number(r'^Average watch time: (\d+)s$'),
        'average_percentage_watched': number(r'^Average percentage watched\n(\d+(?:\.\d+)?)%$'),
        'reactions': number(r'^(\d+)\nReactions$'),
        'clicks': number(r'^(\d+)\nClicks$'),
        'comments': number(r'^(\d+)\nComments$'),
        'shares': number(r'^(\d+)\nShares$'),
        'follows': number(r'^(\d+)\nFollows$'),
        'player_10_second_view_rate': number(r'^Player 10-second view rate\n(\d+(?:\.\d+)?)%$'),
        'qualified_inquiries': None,
    }
    watch = re.search(r'^Watch time\n(\d+):(\d{2})$', text, re.M)
    result['watch_time_seconds'] = int(watch[1]) * 60 + int(watch[2]) if watch else None
    drop = re.search(r'dropped off at the (\d+):(\d{2}) mark', text)
    result['largest_dropoff_seconds'] = int(drop[1]) * 60 + int(drop[2]) if drop else None
    age = text.split('Who viewed your content', 1)[-1].split('Link clicks', 1)[0]
    result['reported_age_percentages'] = dict(
        (group, float(value)) for group, value in
        re.findall(r'^(\d{2}-\d{2}|65\+)\n(\d+(?:\.\d+)?)%$', age, re.M))
    result['interpretation_note'] = ('Dashboard-reported values, not independently validated. '
                                     'Average percentage watched is not completion rate; '
                                     'age percentages do not establish buyer fit or a unique-person denominator.')
    return result


def capture_insights(browser, page_id, output, url=None, open_labels=(), scrolls=3,
                     hover_demographics=False):
    output = Path(output)
    if output.exists():
        raise AgentError('invalid_arguments', 'Output exists; choose a new evidence path.')
    target = validate_url(url or 'https://www.facebook.com/professional_dashboard/insights/', page_id)
    if not 0 <= scrolls <= 8 or any(label not in READ_ONLY_LABELS for label in open_labels):
        raise AgentError('invalid_arguments', 'Unsupported navigation label or scroll count (0-8).')
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = browser.check_authenticated(page_id=page_id)
    page = browser.page
    browser.keep_page = True
    evidence = {'profile': profile, 'requested_url': target, 'records': [], 'panels': {},
                'scope': 'Rendered dashboard only; chart-only values and unavailable demographics are not inferred.'}

    def capture(stage):
        selectors.check_block(page)
        now_str = datetime.now(timezone.utc).isoformat()
        record = {'stage': stage, 'url': page.url,
                  'observed_at': now_str,
                  **page.evaluate(SNAPSHOT)}
        record['post_metrics'] = post_metrics(record['text'])
        record['chart_tooltips'] = page.get_by_role('tooltip').all_inner_texts()
        if record['post_metrics'] is not None:
            record['post_metrics']['age_gender_segments'] = record['age_gender_segments']
            record['post_metrics']['discovery_panels'] = record['discovery_panels']
        image = output.with_name(output.stem + f'-{len(evidence["records"]):02d}.png')
        page.screenshot(path=str(image), full_page=True)
        record['screenshot'] = image.name
        evidence['records'].append(record)

        # Track panel status
        if stage == 'initial':
            evidence['panels']['traffic'] = {'status': 'captured', 'observed_at': now_str}
            has_demo = bool(record['age_gender_segments'] or (record['post_metrics'] and record['post_metrics'].get('reported_age_percentages')))
            evidence['panels']['demographics'] = {'status': 'captured' if has_demo else 'unavailable', 'observed_at': now_str}
        elif stage == 'Source':
            evidence['panels']['source'] = {'status': 'captured', 'observed_at': now_str}
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')

    page.goto(target, wait_until='domcontentloaded', timeout=browser.timeout_ms)
    page.wait_for_timeout(5000)
    capture('initial')
    for label in open_labels:
        candidates = page.get_by_role('link', name=label, exact=True).or_(
            page.get_by_role('button', name=label, exact=True)).or_(
            page.get_by_role('tab', name=label, exact=True)).or_(
            page.get_by_role('menuitem', name=label, exact=True))
        control = selectors.unique(selectors.visible(candidates), f'Insights navigation: {label}')
        href = control.get_attribute('href')
        if href:
            validate_url(control.evaluate('(el) => el.href'), page_id)
        control.click(timeout=browser.timeout_ms)
        page.wait_for_timeout(3000)
        capture(label)
    if hover_demographics:
        bars = page.locator('[data-metric="MALE"], [data-metric="FEMALE"], [data-metric="UNKNOWN"]')
        for index in range(min(bars.count(), 30)):
            bar = bars.nth(index)
            bar.scroll_into_view_if_needed()
            bar.hover()
            page.wait_for_timeout(700)
            capture(f'demographic-hover-{index + 1}')
    for index in range(scrolls):
        size = page.evaluate('() => ({width: innerWidth, height: innerHeight})')
        page.mouse.move(size['width'] * 0.8, size['height'] * 0.7)
        page.mouse.wheel(0, 650)
        page.wait_for_timeout(1000)
        capture(f'scroll-{index + 1}')
    evidence['capture_complete'] = True
    evidence['panels'].setdefault('source', {'status': 'not_opened', 'observed_at': None})
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    return {'profile': profile, 'records': len(evidence['records']), 'output': str(output)}
