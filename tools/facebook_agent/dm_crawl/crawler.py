"""Facebook Page Direct Message (DM) Ingestion Tool via Graph API.

Pure HTTP/REST implementation: no browser, no Playwright, no CDP.
Queries Meta Graph API /{page_id}/conversations to ingest shared Reels and video links.

Supports both:
1. Native Shares: User clicks the native "Share to Messenger" / "Send to Page" button on a Reel/video.
2. Link Shares: User pastes a Reel/video link into the message text (with or without notes).
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

# Ensure project root is in sys.path so direct script invocation works seamlessly
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tools.common.cli_support import JsonArgumentParser, emit_error, emit_success
from tools.common.config import load_environment
from tools.common.errors import AgentError

# Supported Reel, Short-Form, and Video Share URL patterns
REEL_PATTERNS = [
    re.compile(r'https?://(?:www\.)?facebook\.com/reel/(\d+)', re.I),
    re.compile(r'https?://(?:www\.)?facebook\.com/share/[rvp]/([a-zA-Z0-9_-]+)', re.I),
    re.compile(r'https?://(?:www\.)?facebook\.com/watch/\?v=(\d+)', re.I),
    re.compile(r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9_.-]+/videos/(\d+)', re.I),
    re.compile(r'https?://fb\.watch/([a-zA-Z0-9_-]+)', re.I),
    re.compile(r'https?://(?:www\.)?instagram\.com/reel/([a-zA-Z0-9_-]+)', re.I),
    re.compile(r'https?://(?:www\.)?instagram\.com/p/([a-zA-Z0-9_-]+)', re.I),
    re.compile(r'https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/(\d+)', re.I),
    re.compile(r'https?://(?:vm|vt)\.tiktok\.com/([a-zA-Z0-9_-]+)', re.I),
]


def resolve_short_url(url: str, timeout: float = 3.0) -> str:
    """Resolve short share URLs (fb.watch, facebook.com/share/*, vm.tiktok.com) to target URL."""
    if not url or not any(x in url for x in ('facebook.com/share/', 'fb.watch/', 'tiktok.com/')):
        return url
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        )

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(_NoRedirect)
        try:
            resp = opener.open(req, timeout=timeout)
            loc = resp.headers.get("Location")
        except urllib.error.HTTPError as exc:
            loc = exc.headers.get("Location")
        if loc:
            return loc
    except Exception:
        pass
    return url


def canonicalize_reel_url(url: str, resolve_redirects: bool = True) -> Optional[tuple[str, str]]:
    """Clean tracking params from Reel URL and detect platform.

    If resolve_redirects is True and the URL is a short share link (such as
    facebook.com/share/v/*), resolves HTTP 301/302 redirects to find the canonical reel ID.

    Returns:
        tuple of (canonical_url, platform) or None if not recognized.
    """
    if not url:
        return None
    target_url = resolve_short_url(url) if resolve_redirects else url
    for pattern in REEL_PATTERNS:
        match = pattern.search(target_url)
        if match:
            clean = match.group(0).rstrip('/')
            if 'facebook.com' in clean or 'fb.watch' in clean:
                return clean, 'facebook'
            if 'instagram.com' in clean:
                return clean, 'instagram'
            if 'tiktok.com' in clean:
                return clean, 'tiktok'
    return None


def extract_reels_from_text(text: str) -> List[Dict[str, str]]:
    """Extract all valid Reel and video URLs embedded in message text."""
    if not text:
        return []
    found = []
    seen = set()
    for pattern in REEL_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(0)
            canonical = canonicalize_reel_url(raw, resolve_redirects=True)
            if canonical and canonical[0] not in seen:
                seen.add(canonical[0])
                found.append({'url': canonical[0], 'platform': canonical[1]})
    return found


def _normalize_string(val: str) -> str:
    """Normalize unicode and strip whitespace/accents for robust matching."""
    nfkd = unicodedata.normalize('NFKD', val.lower())
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).replace(' ', '').replace('-', '').replace('_', '')


def _resolve_page_token(target: str, token: str, api_version: str) -> Optional[tuple[str, str, str]]:
    """Try to resolve Page ID and Page Access Token from a User Access Token via /me/accounts."""
    url = f'https://graph.facebook.com/{api_version}/me/accounts?fields=id,name,access_token&access_token={token}'
    req = urllib.request.Request(url, headers={'User-Agent': 'SocialContentBot/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None

    target_norm = _normalize_string(target)
    for page in data.get('data', []):
        p_id = str(page.get('id', ''))
        p_name = page.get('name', '')
        p_token = page.get('access_token', '')

        if not p_token:
            continue
        # Exact ID match
        if target == p_id:
            return p_id, p_name, p_token
        # Name match
        if target_norm in _normalize_string(p_name) or _normalize_string(p_name) in target_norm:
            return p_id, p_name, p_token

    accounts = data.get('data', [])
    if len(accounts) == 1 and accounts[0].get('access_token'):
        first = accounts[0]
        return str(first['id']), first['name'], first['access_token']

    return None


def fetch_inbox_via_api(page_id: str, access_token: str, limit: int = 25, api_version: str = 'v27.0') -> Dict[str, Any]:
    """Fetch Facebook Page DMs directly using Meta Graph API.

    # ponytail: seamlessly handles both native shares and text links per message without duplication.
    """
    if not page_id or not page_id.strip():
        raise AgentError('invalid_page_id', 'Provide a valid Facebook Page ID or username.')
    if not access_token or not access_token.strip():
        raise AgentError('missing_token', 'Provide a valid Facebook Page Access Token.')

    target = page_id.strip()
    active_token = access_token.strip()
    page_name = None

    fields = (
        'id,snippet,updated_time,participants,'
        'messages.limit(20){id,message,created_time,from,shares{id,description,link,name},attachments{id,mime_type,name,file_url,video_data,type,payload}}'
    )

    def _query(tgt: str, tok: str):
        query = urllib.parse.urlencode({
            'fields': fields,
            'limit': str(limit),
            'access_token': tok,
        })
        url = f'https://graph.facebook.com/{api_version}/{tgt}/conversations?{query}'
        req = urllib.request.Request(url, headers={'User-Agent': 'SocialContentBot/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))

    try:
        data = _query(target, active_token)
    except urllib.error.HTTPError as exc:
        err_msg = ''
        try:
            err_body = json.loads(exc.read().decode('utf-8'))
            err_msg = err_body.get('error', {}).get('message', '')
            err_code = err_body.get('error', {}).get('code', exc.code)
        except Exception:
            err_code = exc.code

        if err_code in (10, 100, 190) or 'Page Access Token' in err_msg:
            resolved = _resolve_page_token(target, active_token, api_version)
            if resolved:
                target, page_name, active_token = resolved
                try:
                    data = _query(target, active_token)
                except Exception as inner_exc:
                    raise AgentError('api_request_failed', f'Graph API query failed after page token resolution: {inner_exc}') from inner_exc
            else:
                raise AgentError('api_http_error', f'Meta Graph API error ({exc.code}): {err_msg or exc}') from exc
        else:
            raise AgentError('api_http_error', f'Meta Graph API error ({exc.code}): {err_msg or exc}') from exc
    except Exception as exc:
        raise AgentError('api_request_failed', f'Graph API connection failed: {exc}') from exc

    reels_found = []
    seen_message_ids = set()

    for conv in data.get('data', []):
        messages = conv.get('messages', {}).get('data', [])
        for msg in messages:
            msg_id = msg.get('id')
            if msg_id in seen_message_ids:
                continue
            seen_message_ids.add(msg_id)

            sender_name = msg.get('from', {}).get('name')
            sender_id = msg.get('from', {}).get('id')
            created_time = msg.get('created_time')
            msg_text = msg.get('message', '')

            # Extract URLs from shares, attachments, and text
            share_links = []
            for share_item in msg.get('shares', {}).get('data', []):
                canonical = canonicalize_reel_url(share_item.get('link'))
                if canonical:
                    share_links.append((canonical[0], canonical[1]))

            att_links = []
            for att in msg.get('attachments', {}).get('data', []):
                p_url = att.get('payload', {}).get('url') or att.get('file_url') or att.get('video_data', {}).get('url')
                canonical = canonicalize_reel_url(p_url) if p_url else None
                if canonical:
                    att_links.append((canonical[0], canonical[1]))

            text_links = [(item['url'], item['platform']) for item in extract_reels_from_text(msg_text)]

            # Determine share type and primary canonical URL
            # Case A: Native Share (User tapped Share -> Send to Page)
            if share_links and not text_links:
                for s_url, s_plat in share_links:
                    reels_found.append({
                        'reel_url': s_url,
                        'original_url': s_url,
                        'platform': s_plat,
                        'share_type': 'native_share',
                        'sender': sender_name,
                        'sender_id': sender_id,
                        'message_text': msg_text,
                        'created_time': created_time,
                    })
            # Case B: Link Share (User pasted a URL into message text)
            elif text_links:
                for t_url, t_plat in text_links:
                    # If Facebook resolved a canonical /reel/ ID in shares for this text link, prefer it
                    canonical_resolved = share_links[0][0] if share_links else t_url
                    reels_found.append({
                        'reel_url': canonical_resolved,
                        'original_url': t_url,
                        'platform': t_plat,
                        'share_type': 'link_share',
                        'sender': sender_name,
                        'sender_id': sender_id,
                        'message_text': msg_text,
                        'created_time': created_time,
                    })
            # Case C: Direct Attachment without shares or text
            elif att_links:
                for a_url, a_plat in att_links:
                    reels_found.append({
                        'reel_url': a_url,
                        'original_url': a_url,
                        'platform': a_plat,
                        'share_type': 'attachment_share',
                        'sender': sender_name,
                        'sender_id': sender_id,
                        'message_text': msg_text,
                        'created_time': created_time,
                    })

    return {
        'ok': True,
        'mode': 'graph_api',
        'api_version': api_version,
        'page_id': target,
        'page_name': page_name,
        'conversations_count': len(data.get('data', [])),
        'reels_count': len(reels_found),
        'reels': reels_found,
        'fetched_at': datetime.now(timezone.utc).isoformat(),
    }


def main():
    load_environment(include_repository=True)
    _local_env = Path(__file__).parent / '.env'
    if _local_env.exists():
        for line in _local_env.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k not in os.environ or not os.environ[k]:
                    os.environ[k] = v

    default_token = os.getenv('PAGE_ACCESS_TOKEN') or os.getenv('FB_PAGE_ACCESS_TOKEN')
    parser = JsonArgumentParser(
        prog='crawler',
        description='Fetch Facebook Page DMs and extract shared Reels via Graph API.'
    )
    parser.add_argument('--page', default='giupmehocai', help='Facebook Page username or numeric ID (default: giupmehocai)')
    parser.add_argument('--token', default=default_token, help='Page Access Token (default: env PAGE_ACCESS_TOKEN)')
    parser.add_argument('--limit', type=int, default=25, help='Maximum conversations to query (default: 25)')
    parser.add_argument('--output', help='Save output JSON to a file')

    args = parser.parse_args()

    if not args.token:
        emit_error('missing_token', 'Provide a Page Access Token via --token or set PAGE_ACCESS_TOKEN in dm_crawl/.env')
        return 2

    try:
        result = fetch_inbox_via_api(page_id=args.page, access_token=args.token, limit=args.limit)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        emit_success(result)
        return 0
    except AgentError as err:
        emit_error(err.code, err.message)
        return 3
    except Exception as exc:
        emit_error('internal_error', str(exc))
        return 1


if __name__ == '__main__':
    sys.exit(main())
