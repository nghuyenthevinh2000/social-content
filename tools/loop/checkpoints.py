"""Stage 2: find due 24h/7d measurements from verified publication times.

Planned posts are never treated as published, and pending reviews stay visible.
"""

from tools.loop import storage


def due(entry, at=None):
    """Legacy publication-level due check."""
    at = at or storage.now()
    return (entry.get('metrics_status') in ('pending', 'fetching')
            and entry.get('due_at') is not None
            and storage.timestamp(entry['due_at']) is not None
            and storage.timestamp(entry['due_at']) <= at)


def due_checkpoints(state, at=None):
    """Find all due checkpoints across placements and legacy publications.

    Prefer v2 checkpoints. Include legacy due work only for publications
    not represented by a placement. Deduplicate the same placement/checkpoint;
    freeze the resulting worklist.
    """
    at = at or storage.now()
    due_items = []
    seen_placements = set()
    represented_pubs = set()

    # 1. Check v2 placements
    for pl in state.get('placements', []):
        represented_pubs.add(pl.get('publication_id'))
        for cp_name, cp in pl.get('checkpoints', {}).items():
            key = (pl['id'], cp_name)
            if key in seen_placements:
                continue
            if cp.get('status') in ('pending', 'fetching') and cp.get('due_at'):
                due_time = storage.timestamp(cp['due_at'])
                if due_time and due_time <= at:
                    seen_placements.add(key)
                    due_items.append({
                        'kind': 'placement_checkpoint',
                        'placement_id': pl['id'],
                        'publication_id': pl.get('publication_id'),
                        'placement_kind': pl.get('kind', 'original_page'),
                        'checkpoint': cp_name,
                        'due_at': cp['due_at'],
                        'permalink': pl.get('permalink'),
                        'insights_url': pl.get('insights_url'),
                        'post_id': pl.get('copy_post_id'),
                    })

    # 2. Check legacy publications only if not already represented by a placement
    for pub in state.get('publications', []):
        if pub['id'] in represented_pubs:
            continue
        if due(pub, at):
            due_items.append({
                'kind': 'publication',
                'id': pub['id'],
                'publication_id': pub['id'],
                'placement_kind': 'original_page',
                'checkpoint': '24h',
                'due_at': pub.get('due_at'),
                'url': pub.get('url'),
                'permalink': pub.get('url'),
                'insights_url': pub.get('insights_url'),
                'post_id': pub.get('post_id'),
            })
    return due_items
