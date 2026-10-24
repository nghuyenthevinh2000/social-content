"""Collect viral candidates for hashtag/keyword targets that were already tested.

Activation gate: a target is scraped only when its latest campaign-history
evaluation decision is ``promising`` or ``limited_expand`` in
``sources/viral/hashtag-performance.json``. Nothing runs before that test.
"""

import argparse
from decimal import Decimal
import json
import subprocess
import sys

from tools.loop.viral_analyzer import hashtag_common as hc
from tools.loop.viral_analyzer import hashtag_verify as hv


ACTIVATED_DECISIONS = ('promising', 'limited_expand')
CONTAINERS = (
    ('output', 'reels'), ('output', 'search_item_list'), ('output', 'item_list'),
    ('output', 'aweme_list'), ('output', 'posts'), ('output', 'items'),
    ('data', 'reels'), ('data', 'items'), ('data', 'search_item_list'),
    ('reels',), ('items',), ('search_item_list',), ('item_list',), ('data',),
)
URL_TEMPLATES = {
    'instagram': 'https://www.instagram.com/reel/{id}/',
    'tiktok': 'https://www.tiktok.com/@{creator}/video/{id}',
}
METRIC_PATHS = {
    'views': ('play_count', 'view_count', 'views', 'playCount', 'viewCount',
              'video_view_count', 'statistics.play_count', 'stats.play_count'),
    'likes': ('like_count', 'digg_count', 'likes', 'likeCount', 'diggCount',
              'statistics.digg_count', 'stats.digg_count'),
    'comments': ('comment_count', 'comments', 'commentCount',
                 'statistics.comment_count', 'stats.comment_count'),
    'shares': ('share_count', 'shares', 'shareCount',
               'statistics.share_count', 'stats.share_count'),
}


def _result(ok, **payload):
    return {'ok': ok, **payload}


def _dig(item, path):
    value = item
    for key in path.split('.'):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _metric(item, name):
    for path in METRIC_PATHS[name]:
        value = _dig(item, path)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                text = value.replace(',', '').strip()
                return int(text) if text.isdigit() else float(text)
            except ValueError:
                continue
    return None


def _unwrap(item):
    for key in ('aweme_info', 'item', 'post', 'reel'):
        inner = item.get(key)
        if isinstance(inner, dict) and inner:
            return inner
    return item


def raw_items(response):
    """Ordered provider items across provider shapes; never popularity-sorted."""
    for path in CONTAINERS:
        value = _dig(response, '.'.join(path))
        if isinstance(value, list) and value:
            return [_unwrap(item) for item in value if isinstance(item, dict)]
    return hv.extract_media(response)


def activated_targets(history, platforms=None):
    """Latest campaign-history decision must be promising/limited_expand."""
    targets = []
    for platform, entry, evaluations in hc.history_entries(history):
        if platforms and platform not in platforms:
            continue
        latest = evaluations[-1] if evaluations else None
        if not latest or latest.get('decision') not in ACTIVATED_DECISIONS:
            continue
        kind = hc.infer_query_kind(entry)
        targets.append({
            'platform': platform,
            'query_kind': kind,
            'query': entry.get('normalized_tag') or hc.normalize_term(entry.get('original_tag')),
            'original_term': entry.get('original_tag'),
            'evaluation_id': latest.get('evaluation_id'),
            'decision': latest.get('decision'),
            'application': latest.get('application'),
            'market_language': latest.get('market_language'),
            'unique_reviewed': latest.get('unique_reviewed'),
            'checked_at': latest.get('checked_at'),
        })
    return targets


def _call(target, endpoint, index):
    request = dict(endpoint.get('fixed') or {})
    request[endpoint['method_field']] = target['query']
    return {
        'call_id': f"scrape-{target['platform']}-{target['query_kind']}-{index:02d}",
        'platform': target['platform'],
        'query_kind': target['query_kind'],
        'query': target['query'],
        'evaluation_id': target['evaluation_id'],
        'decision': target['decision'],
        'provider': endpoint['provider'],
        'endpoint': endpoint['endpoint'],
        'method_field': endpoint['method_field'],
        'ranking_filter': endpoint.get('ranking_filter'),
        'request': request,
        'max_results': endpoint['max_results'],
        'expected_price_usd': str(endpoint['price_usd']),
    }


def _idempotency_key(campaign, run_id, gate_sha, call):
    return hc.canonical_hash({
        'campaign': campaign, 'run_id': run_id, 'gate_sha256': gate_sha,
        'call_id': call['call_id'], 'evaluation_id': call['evaluation_id'],
        'provider': call['provider'], 'endpoint': call['endpoint'],
        'request': call['request'],
    })


def _fallback_url(platform, video_id, creator):
    template = URL_TEMPLATES.get(platform)
    if not template or not video_id:
        return None
    if platform == 'tiktok' and not creator:
        return None
    return template.format(id=video_id, creator=creator or 'unknown')


def _scalar(item, *keys):
    for key in keys:
        value = item.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _candidate(call, item, position, collected_at):
    video_id = _scalar(item, 'id', 'pk', 'shortcode', 'video_id', 'aweme_id')
    creator = (hv._nested(item, 'owner', 'author', 'creator', 'user')
               or _scalar(item, 'username', 'author_name', 'creator_name', 'creator_id'))
    url = (_scalar(item, 'url', 'share_url', 'video_url', 'play_url',
                   'permalink', 'link')
           or _fallback_url(call['platform'], video_id, creator))
    caption = hv._first(item, 'caption', 'desc', 'description', 'title', 'text')
    created_at = _dig(item, 'taken_at') or _dig(item, 'create_time') or _dig(item, 'created_at')
    return {
        'platform': call['platform'],
        'target_query': call['query'],
        'query_kind': call['query_kind'],
        'gate_evaluation_id': call['evaluation_id'],
        'gate_decision': call['decision'],
        'source_call_id': call['call_id'],
        'source_endpoint': call['endpoint'],
        'ranking_filter': call.get('ranking_filter'),
        'position': position,
        'video_id': video_id,
        'url': url,
        'video_url': _scalar(item, 'video_url', 'play_url'),
        'creator_id': creator,
        'caption': caption,
        'created_at': created_at,
        'metrics': {name: _metric(item, name) for name in METRIC_PATHS},
        'evidence': {'medium': 'caption' if caption else 'unknown'},
        'collected_at': collected_at,
    }


def _status_path(run_dir, call):
    return run_dir / 'expansion/calls' / f"{call['call_id']}.status.json"


def _read_status(run_dir, call):
    return hc.load_optional_json(_status_path(run_dir, call))


def _build_calls(targets, schema, problems):
    calls = []
    for target in targets:
        endpoint = schema['endpoints'].get((target['platform'], target['query_kind']))
        if endpoint is None:
            problems.error(
                f"no schema endpoint for {target['platform']}/{target['query_kind']}: "
                f"{target['original_term']}")
            continue
        calls.append(_call(target, {**endpoint, 'provider': schema['provider']},
                           len(calls) + 1))
    return calls


def scrape(args):
    problems = hc.Problems()
    root = hc.campaign_root(args.project)
    try:
        history = hc.load_history(root)
    except ValueError as exc:
        return _result(False, command='viral-scrape', errors=[str(exc)]), problems
    run_dir = hc.artifact_directory(root, args.run)
    context = hc.load_optional_json(run_dir / 'context.json')
    if isinstance(context, dict) and context.get('collection_blocked'):
        problems.error('campaign context is missing or conflicting; collection is blocked')
    schema = hv.load_schema(args.schema, problems)
    if schema is None:
        return _result(False, command='viral-scrape', errors=problems.errors,
                       warnings=problems.warnings), problems
    platforms = {args.platform} if args.platform else None
    targets = activated_targets(history, platforms)
    if not targets:
        problems.error('no tested hashtag targets: latest decisions must be '
                       'promising or limited_expand via hashtag_verify record-review')
    if args.limit is not None and args.limit < 1:
        problems.error('--limit must be a positive integer')
    if args.limit and len(targets) > args.limit:
        problems.error(f'{len(targets)} activated targets exceed --limit {args.limit}')
    calls = _build_calls(targets, schema, problems)
    ceiling = None
    if args.ceiling is not None:
        ceiling = hc.decimal_string(args.ceiling)
        if ceiling is None:
            problems.error('--ceiling must be a nonnegative decimal')
    total = sum((Decimal(call['expected_price_usd']) for call in calls), Decimal('0'))
    if ceiling is not None and total > ceiling:
        problems.error(f'activated calls cost {total} {schema["currency"]}; ceiling is {ceiling}')
    if args.execute and ceiling is None:
        problems.error('--execute requires --ceiling')
    if not problems.ok:
        return _result(False, command='viral-scrape', errors=problems.errors,
                       warnings=problems.warnings), problems
    if not args.execute:
        return _result(True, command='viral-scrape', mode='preview', campaign=root.name,
                       run_id=args.run, targets=len(targets), calls=calls,
                       planned_total_usd=str(total), currency=schema['currency'],
                       errors=[], warnings=problems.warnings), problems
    run_func = getattr(args, 'run_func', None) or hv.run_provider
    gate_sha = hc.canonical_hash(targets)
    capture_dir = run_dir / 'expansion/calls'
    capture_dir.mkdir(parents=True, exist_ok=True)
    committed = Decimal('0')
    for call in calls:
        status = _read_status(run_dir, call)
        if status and status.get('outcome') == 'success':
            committed += Decimal(str(status.get('charge_usd') or call['expected_price_usd']))
    outcomes, candidates, duplicates, seen = [], [], [], set()
    for call in calls:
        price = Decimal(call['expected_price_usd'])
        status = _read_status(run_dir, call)
        if status and status.get('gate_sha256') not in (None, gate_sha):
            outcomes.append({'call_id': call['call_id'], 'action': 'stale_gate',
                             'outcome': 'stale_gate',
                             'detail': 'history changed since this call was planned'})
            continue
        if status and status.get('outcome') == 'success':
            _extend_candidates(capture_dir, call, candidates, duplicates, seen)
            outcomes.append({'call_id': call['call_id'], 'action': 'skipped_completed',
                             'outcome': 'success'})
            continue
        if status and status.get('attempts', 0) >= 2:
            outcomes.append({'call_id': call['call_id'], 'action': 'needs_reconciliation',
                             'outcome': status.get('outcome')})
            continue
        if status and not args.resume:
            outcomes.append({'call_id': call['call_id'], 'action': 'needs_reconciliation',
                             'outcome': status.get('outcome'),
                             'detail': 'inspect the receipt, then rerun with --resume'})
            continue
        if committed + price > ceiling:
            outcomes.append({'call_id': call['call_id'], 'action': 'budget_stopped',
                             'outcome': 'budget_exceeded'})
            committed = ceiling + 1
            continue
        attempts = (status or {}).get('attempts', 0) + 1
        key = _idempotency_key(root.name, args.run, gate_sha, call)
        pending = {
            'call_id': call['call_id'], 'idempotency_key': key, 'gate_sha256': gate_sha,
            'attempts': attempts, 'outcome': 'pending', 'started_at': hc.utc_now(),
            'ended_at': None, 'run_id': None, 'run_url': None, 'charge_usd': None,
            'expected_price_usd': call['expected_price_usd'],
        }
        hc.write_json(_status_path(run_dir, call), pending)
        request_path = capture_dir / f"{call['call_id']}.request.json"
        if not request_path.exists():
            hc.write_json(request_path, {'provider': call['provider'],
                                         'endpoint': call['endpoint'],
                                         'request': call['request'],
                                         'idempotency_key': key})
        committed += price
        try:
            provider = run_func(call, key)
        except subprocess.TimeoutExpired as exc:
            provider = {'returncode': -1, 'stdout': '', 'stderr': f'timeout: {exc}'}
        except OSError as exc:
            provider = {'returncode': -1, 'stdout': '', 'stderr': str(exc)}
        response = None
        if provider.get('stdout'):
            try:
                response = json.loads(provider['stdout'])
            except ValueError:
                response = None
        items = raw_items(response) if response is not None else []
        outcome = hv._classify_failure(provider.get('returncode', 0),
                                       provider.get('stderr', ''))
        if outcome is None and response is not None:
            outcome = hv._response_error(response)
        if outcome is None and not items:
            outcome = 'empty_response'
        if provider.get('stderr'):
            (capture_dir / f"{call['call_id']}.stderr.txt").write_text(provider['stderr'])
        if provider.get('stdout'):
            response_path = capture_dir / f"{call['call_id']}.response.json"
            if not response_path.exists():
                response_path.write_text(provider['stdout'])
        ended_at = hc.utc_now()
        status = {**pending, 'attempts': attempts, 'outcome': outcome or 'success',
                  'ended_at': ended_at, 'charge_usd': hv._charge(response, None),
                  'run_id': hv._run_id(response), 'run_url': hv._run_url(response)}
        hc.write_json(_status_path(run_dir, call), status)
        if outcome is None:
            outcome = 'success'
            call_items = _store_items(capture_dir, call, items, ended_at)
            _extend_candidates(None, call, candidates, duplicates, seen, call_items)
        outcomes.append({'call_id': call['call_id'], 'action': 'dispatched',
                         'outcome': outcome,
                         'charge_usd': status.get('charge_usd'),
                         'count': len(items) if outcome == 'success' else 0})
    document = {
        'schema_version': 1,
        'campaign': root.name,
        'run_id': args.run,
        'created_at': hc.utc_now(),
        'provider': schema['provider'],
        'currency': schema['currency'],
        'gate': {'rule': 'latest campaign-history decision in promising/limited_expand',
                 'gate_sha256': gate_sha, 'targets': targets},
        'calls': [{key: call[key] for key in
                   ('call_id', 'platform', 'query_kind', 'query', 'endpoint',
                    'ranking_filter', 'expected_price_usd', 'evaluation_id', 'decision')}
                  for call in calls],
        'outcomes': outcomes,
        'candidates': candidates,
        'duplicates': duplicates,
    }
    candidates_path = run_dir / 'expansion/viral-candidates.json'
    hc.write_json(candidates_path, document)
    return _result(True, command='viral-scrape', mode='execute', campaign=root.name,
                   run_id=args.run, outcomes=outcomes,
                   candidates_path=str(candidates_path.relative_to(root)),
                   candidates=len(candidates), duplicates=len(duplicates),
                   currency=schema['currency'], errors=[], warnings=[]), problems


def _store_items(capture_dir, call, items, collected_at):
    records = [_candidate(call, item, position, collected_at)
               for position, item in enumerate(items, start=1)]
    hc.write_json(capture_dir / f"{call['call_id']}.items.json",
                  {'call_id': call['call_id'], 'collected_at': collected_at,
                   'items': records})
    return records


def _extend_candidates(capture_dir, call, candidates, duplicates, seen, records=None):
    if records is None:
        saved = hc.load_optional_json(capture_dir / f"{call['call_id']}.items.json")
        records = (saved or {}).get('items') or []
    for record in records:
        identity = (record['platform'],
                    record.get('video_id') or record.get('url')
                    or (record.get('creator_id'), record.get('caption'),
                        record.get('source_call_id'), record.get('position')))
        if identity in seen:
            duplicates.append({**record, 'duplicate_of': identity[1]})
            continue
        seen.add(identity)
        candidates.append(record)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, help='Campaign root, e.g. local/<slug>')
    parser.add_argument('--run', required=True,
                        help='Campaign run ID whose expansion/ folder receives captures')
    parser.add_argument('--schema', required=True,
                        help='Saved provider schema/price JSON (from glasser inspect)')
    parser.add_argument('--platform', help='Only this platform, e.g. instagram')
    parser.add_argument('--limit', type=int, help='Maximum activated targets; more is an error')
    parser.add_argument('--ceiling', help='Decimal spend ceiling; required with --execute')
    parser.add_argument('--execute', action='store_true',
                        help='Dispatch provider calls; without it the command only previews')
    parser.add_argument('--resume', action='store_true',
                        help='Reuse the same idempotency key after an unconfirmed attempt')
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    args.run_func = hv.run_provider
    try:
        result, _ = scrape(args)
    except (ValueError, OSError) as exc:
        print(json.dumps({'ok': False, 'command': 'viral-scrape',
                          'errors': [str(exc)]}, ensure_ascii=False))
        return 2
    except Exception as exc:
        print(json.dumps({'ok': False, 'command': 'viral-scrape',
                          'errors': [f'unexpected failure: {exc}']}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    sys.exit(main())
