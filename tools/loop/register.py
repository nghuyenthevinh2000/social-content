"""Stage 1: remember confirmed published posts.

Registration only records facts a human already verified. It never publishes.
"""

from datetime import timedelta
import uuid
from urllib.parse import urlparse

from tools.loop import storage


def register(state, post, url, published_at=None):
    """Record a canonical permalink, hypothesis number and verified publish time."""
    url = url.rstrip('/')
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('facebook.com', 'www.facebook.com'):
        raise ValueError('Use an HTTPS facebook.com permalink.')

    published = storage.timestamp(published_at) if published_at is not None else None
    if published is not None and published > storage.now():
        raise ValueError('A future timestamp is not a confirmed publication.')

    for entry in state.get('publications', []):
        if entry.get('url') and entry['url'].rstrip('/') == url:
            if entry['post'] != post:
                raise ValueError('Existing publication has different details; inspect registry first.')
            if entry.get('published_at') is None:
                if published is not None:
                    entry.update(published_at=published.isoformat(),
                                 due_at=(published + timedelta(hours=24)).isoformat(),
                                 metrics_status='pending', review_status='waiting_for_metrics')
            elif published is not None and storage.timestamp(entry['published_at']) != published:
                raise ValueError('Existing publication has different details; inspect registry first.')
            return entry

    entry = {
        'id': uuid.uuid4().hex,
        'post': post,
        'url': url,
        'published_at': published.isoformat() if published else None,
        'due_at': (published + timedelta(hours=24)).isoformat() if published else None,
        'metrics_status': 'pending' if published else 'missing_publication_details',
        'review_status': 'waiting_for_metrics',
    }
    unresolved = next((item for item in state.get('publications', [])
                       if item['post'] == post
                       and item['metrics_status'] == 'missing_publication_details'), None)
    if unresolved is not None:
        entry['id'] = unresolved.get('id', entry['id'])
        unresolved.update(entry)
        unresolved.pop('note', None)
        return unresolved
    state.setdefault('publications', []).append(entry)
    return entry
