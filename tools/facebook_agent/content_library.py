"""Extract structured Content Library table rows: original posts, group copies, and moderation states."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlsplit

from .models import AgentError


LIBRARY_URL = 'https://www.facebook.com/professional_dashboard/content/content_library/'

TABLE_SNAPSHOT = """() => {
    const table = document.querySelector('[role="grid"], [role="table"], table');
    if (!table) {
        return {has_table: false, headers: [], rows: []};
    }
    const headerEls = [...table.querySelectorAll('[role="columnheader"], th')];
    const headers = headerEls.map(el => el.innerText.trim()).filter(Boolean);

    const rowEls = [...table.querySelectorAll('[role="row"], tr')].filter(r => !r.querySelector('[role="columnheader"], th'));
    const rows = rowEls.map(row => {
        const cells = [...row.querySelectorAll('[role="gridcell"], td')].map(c => c.innerText.trim());
        const links = [...row.querySelectorAll('a[href]')].map(a => ({
            text: a.innerText.trim(),
            href: a.href
        }));
        return {
            row_text: row.innerText,
            cells,
            links,
            dataset: Object.assign({}, row.dataset)
        };
    });

    const scrollContainer = table.closest('[style*="overflow"]') || document.documentElement;
    const isAtBottom = (scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight) <= 50;

    return {
        has_table: true,
        headers,
        rows,
        is_at_bottom: isAtBottom
    };
}"""


def extract_group_id_from_url(url: Optional[str]) -> Optional[str]:
    """Extract numeric Facebook Group ID from URL; never invent or guess from name."""
    if not url:
        return None
    match = re.search(r'/groups/(\d+)', url)
    return match.group(1) if match else None


def extract_post_id_from_url(url: Optional[str]) -> Optional[str]:
    """Extract numeric Facebook Post/Reel ID from URL."""
    if not url:
        return None
    # /reel/12345 or /posts/12345 or /permalink/12345 or id=12345
    match = re.search(r'/(?:posts|reel|videos|permalink)/(\d+)', url)
    if match:
        return match.group(1)
    query = parse_qs(urlsplit(url).query)
    if 'story_fbid' in query:
        return query['story_fbid'][0]
    if 'content_id' in query:
        try:
            import base64
            decoded = base64.b64decode(query['content_id'][0]).decode('utf-8', errors='ignore')
            id_match = re.search(r':(\d{10,20})', decoded)
            if id_match:
                return id_match.group(1)
        except Exception:
            pass
    if 'id' in query and not url.startswith('https://www.facebook.com/profile.php'):
        return query['id'][0]
    return None


def parse_row(raw_row: Dict[str, Any], headers: List[str], page_id: str) -> Optional[Dict[str, Any]]:
    """Parse one table row into structured placement record."""
    row_text = raw_row.get('row_text', '')
    if not row_text or not row_text.strip():
        return None

    links = raw_row.get('links', [])
    cells = raw_row.get('cells', [])

    # Post / Reel permalink or Insights URL
    post_link = next((l['href'] for l in links if any(k in l['href'] for k in ('/reel/', '/posts/', '/videos/'))), None)
    insights_link = next((l['href'] for l in links if '/content/insights/' in l['href']), None)
    post_id = extract_post_id_from_url(post_link) or extract_post_id_from_url(insights_link)
    if not post_link and insights_link:
        post_link = insights_link

    # Group link or label
    group_link = next((l['href'] for l in links if '/groups/' in l['href']), None)
    group_id = extract_group_id_from_url(group_link)
    group_name = next((l['text'] for l in links if '/groups/' in l['href']), None)

    # Determine kind & group identity
    is_group_labeled = bool(group_link or group_id or 'group' in row_text.lower() or 'nhóm' in row_text.lower())
    kind = 'group_copy' if is_group_labeled else 'original_page'

    # Moderation / visibility status
    status_lower = row_text.lower()
    if 'pending' in status_lower or 'đang chờ' in status_lower:
        visibility = 'pending'
    elif 'scheduled' in status_lower or 'đã lên lịch' in status_lower:
        visibility = 'scheduled'
    elif 'rejected' in status_lower or 'từ chối' in status_lower:
        visibility = 'rejected'
    elif 'draft' in status_lower or 'bản nháp' in status_lower:
        visibility = 'draft'
    else:
        visibility = 'visible'

    # Extract metrics by exact/normalized header mapping
    views = None
    viewers = None
    three_second_views = None
    reactions = None
    comments = None
    shares = None

    if cells and len(cells) >= len(headers):
        header_map = {h.lower(): idx for idx, h in enumerate(headers)}
        for h_name, idx in header_map.items():
            if idx < len(cells):
                val_text = cells[idx].replace(',', '').strip()
                num = int(val_text) if val_text.isdigit() else None
                clean_h = re.sub(r'\s+', ' ', h_name.strip().lower())

                if clean_h in ('viewers', 'người xem', 'lượt người xem'):
                    viewers = num
                elif any(k in clean_h for k in ('3-second', '3 giây', 'three-second')):
                    three_second_views = num
                elif clean_h in ('views', 'view', 'lượt xem') or (any(k in clean_h for k in ('view', 'lượt xem')) and not any(k in clean_h for k in ('viewer', 'người', '3-second', '3 giây', '1-minute', 'impression', 'lượt hiển thị'))):
                    views = num
                elif any(k in clean_h for k in ('reaction', 'cảm xúc', 'likes', 'lượt thích')):
                    reactions = num
                elif 'comment' in clean_h or 'bình luận' in clean_h:
                    comments = num
                elif 'share' in clean_h or 'chia sẻ' in clean_h:
                    shares = num
        title = cells[0] if cells else row_text.split('\n')[0]

    if views is None:
        # Fallback when table cells are divs without role="gridcell"
        lines = [l.strip() for l in row_text.split('\n') if l.strip() and l.strip() != '\xa0']
        metric_headers = headers[1:] if len(headers) > 1 else []
        M = len(metric_headers)

        if lines and M > 0 and len(lines) >= M + 1:
            metric_vals = lines[-M:]
            preview_lines = lines[:-M]
            title = preview_lines[0]

            for l in preview_lines[1:]:
                if '•' in l:
                    cand = l.split('•')[0].strip()
                    if cand.lower() in ('published', 'đã đăng', 'scheduled', 'đã lên lịch'):
                        kind = 'original_page'
                        group_name = None
                    else:
                        kind = 'group_copy'
                        group_name = cand
                elif 'pending' in l.lower() or 'đang chờ' in l.lower():
                    visibility = 'pending'

            for h, val in zip(metric_headers, metric_vals):
                v = val.replace(',', '').strip()
                num = int(v) if v.isdigit() else None
                clean_h = re.sub(r'\s+', ' ', h.strip().lower())
                if clean_h in ('viewers', 'người xem', 'lượt người xem'):
                    viewers = num
                elif any(k in clean_h for k in ('3-second', '3 giây', 'three-second')):
                    three_second_views = num
                elif clean_h in ('views', 'view', 'lượt xem') or (any(k in clean_h for k in ('view', 'lượt xem')) and not any(k in clean_h for k in ('viewer', 'người', '3-second', '3 giây', '1-minute', 'impression', 'lượt hiển thị'))):
                    views = num
                elif any(k in clean_h for k in ('reaction', 'cảm xúc', 'likes', 'lượt thích')):
                    reactions = num
                elif 'comment' in clean_h or 'bình luận' in clean_h:
                    comments = num
                elif 'share' in clean_h or 'chia sẻ' in clean_h:
                    shares = num
        else:
            title = lines[0] if lines else row_text.split('\n')[0]

    # Fallback to post_id from row text if not in links
    if not post_id:
        fallback_match = re.search(r'\b(122\d{13,16})\b', row_text)
        if fallback_match:
            post_id = fallback_match.group(1)

    unresolved_group = bool(kind == 'group_copy' and not group_id)
    row_hash = hashlib.sha256(row_text.encode('utf-8')).hexdigest()[:12]
    row_id = f"row-{post_id}" if post_id else f"row-{row_hash}"

    return {
        'id': row_id,
        'row_id': row_id,
        'post_id': post_id,
        'title': title,
        'kind': kind,
        'visibility': visibility,
        'page_id': page_id,
        'group_id': group_id,
        'group_name': group_name,
        'group_url': group_link,
        'unresolved_group_identity': unresolved_group,
        'permalink': post_link,
        'insights_url': insights_link,
        'views': views,
        'viewers': viewers,
        'three_second_views': three_second_views,
        'reactions': reactions,
        'comments': comments,
        'shares': shares,
        'raw_text': row_text,
    }


def deduplicate_rows(parsed_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate rows by (post_id, group_id, permalink) or row identity.

    Never merge different placements merely because they share the same title.
    """
    seen = set()
    result = []
    for r in parsed_rows:
        if not r or not r.get('raw_text', '').strip():
            continue
        key = (r.get('post_id'), r.get('group_id'), r.get('permalink'))
        if not any(key):
            key = (r.get('id') or r.get('row_id') or r.get('raw_text'),)
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result


def scrape_content_library(browser, page_id: str, output: Path, max_scrolls: int = 5) -> Dict[str, Any]:
    """Capture Content Library table with virtualized scrolling and deduplication."""
    from . import selectors
    from .insights import SNAPSHOT

    output = Path(output)
    if output.exists():
        raise AgentError('invalid_arguments', 'Output file already exists; choose a new path.')
    output.parent.mkdir(parents=True, exist_ok=True)

    profile = browser.check_authenticated(page_id=page_id)
    page = browser.page
    browser.keep_page = True

    page.goto(LIBRARY_URL, wait_until='domcontentloaded', timeout=browser.timeout_ms)
    page.wait_for_timeout(4000)
    selectors.check_block(page)

    all_raw_rows = []
    observed_headers = []
    traversal_complete = False

    for scroll_idx in range(max_scrolls + 1):
        snapshot = page.evaluate(TABLE_SNAPSHOT)
        if snapshot.get('headers'):
            observed_headers = snapshot['headers']
        new_rows = snapshot.get('rows', [])
        all_raw_rows.extend(new_rows)

        if snapshot.get('is_at_bottom', False):
            traversal_complete = True
            break

        if scroll_idx < max_scrolls:
            # Scroll table container
            page.mouse.wheel(0, 800)
            page.wait_for_timeout(1500)

    # Parse and deduplicate
    parsed = [parse_row(r, observed_headers, page_id) for r in all_raw_rows]
    valid_parsed = [r for r in parsed if r is not None]
    deduped = deduplicate_rows(valid_parsed)

    result_data = {
        'page_id': page_id,
        'observed_at': datetime.now(timezone.utc).isoformat(),
        'traversal_complete': traversal_complete,
        'headers': observed_headers,
        'total_rows_scanned': len(all_raw_rows),
        'unique_placements_count': len(deduped),
        'placements': deduped,
    }

    output.write_text(json.dumps(result_data, ensure_ascii=False, indent=2) + '\n')
    return {
        'output': str(output),
        'unique_placements': len(deduped),
        'traversal_complete': traversal_complete,
    }
