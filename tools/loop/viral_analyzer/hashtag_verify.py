"""Plan, collect and review bounded platform hashtag/keyword probes.

Read-only: ``history``. Run-folder writes: ``plan``, ``build-review-prompt``.
Network and history writes: ``collect --execute`` and ``record-review``.
"""

import argparse
from decimal import Decimal
import json
from pathlib import Path
import re
import subprocess
import sys

from tools.loop import storage
from tools.loop.viral_analyzer import hashtag_common as hc


LABEL_TO_GROUP = {
    'direct_application': 'hit',
    'adjacent_process': 'miss',
    'creative_only': 'miss',
    'irrelevant': 'miss',
    'insufficient_evidence': 'unknown',
}
DECISIONS = ('promising', 'mixed', 'deferred_for_context',
             'insufficient_evidence', 'limited_expand')
PLATFORM_PREFIX = {'instagram': 'ig', 'tiktok': 'tt'}
MEDIA_KEYS = ('caption', 'desc', 'title', 'text', 'url', 'share_url',
              'video_url', 'play_url', 'shortcode', 'pk', 'video_id',
              'aweme_id', 'transcript')
REVIEW_TEMPLATE = {
    'schema_version': 1,
    'campaign': '<campaign slug>',
    'run_id': '<campaign run id>',
    'phase': 'probe',
    'reviewer': '<name>',
    'reviewer_type': 'agent',
    'checked_at': '<ISO timestamp with timezone>',
    'prompt_version': hc.PROMPT_VERSION,
    'model': None,
    'evaluations': [{
        'call_id': '<call id>',
        'reason': 'overall sample-level reason',
        'samples': [{
            'sample_id': '<sample id from review-prompt>',
            'label': 'direct_application|adjacent_process|creative_only|irrelevant|insufficient_evidence',
            'reason': 'what the inspected evidence shows',
            'evidence': ['exact caption quote or URL'],
            'observed': {
                'meaning': 'usage observed in this sample',
                'application': 'substrate/application observed',
                'process': 'process observed',
                'role': 'workshop/buyer role evidence',
                'language': 'vi or en',
                'tag_present': True,
            },
        }],
    }],
}


def _result(ok, **payload):
    return {'ok': ok, **payload}


def _generation(root, run_id):
    run_dir = hc.run_directory(root, run_id)
    context = hc.load_json(run_dir / 'context.json', 'generation context')
    candidates = hc.load_json(run_dir / 'candidates.json', 'validated candidates')
    if context.get('schema_version') != 1 or candidates.get('schema_version') != 1:
        raise ValueError('generation artifacts require schema_version 1')
    if context.get('campaign') != root.name or candidates.get('campaign') != root.name:
        raise ValueError('generation artifacts belong to another campaign')
    if candidates.get('context_sha256') != context.get('context_sha256'):
        raise ValueError('candidates were generated from a stale context hash')
    if candidates.get('run_id') != run_id:
        raise ValueError('candidates belong to another run')
    return run_dir, context, candidates


def _decimal(value, label, problems):
    result = hc.decimal_string(value)
    if result is None:
        problems.error(f'{label} must be a nonnegative decimal')
    return result


def load_schema(path, problems):
    data = hc.read_json_file(path, 'provider schema')
    if not isinstance(data, dict):
        problems.error('provider schema must be an object')
        return None
    provider = data.get('provider')
    if not isinstance(provider, str) or not provider.strip():
        problems.error('provider schema requires a provider name')
    currency = data.get('currency', 'USD')
    if not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}', currency):
        problems.error('provider schema currency must be a three-letter code')
    endpoints = data.get('endpoints')
    if not isinstance(endpoints, list) or not endpoints:
        problems.error('provider schema requires a nonempty endpoints list')
        return None
    indexed = {}
    for index, item in enumerate(endpoints):
        label = f'endpoints[{index}]'
        if not isinstance(item, dict):
            problems.error(f'{label} must be an object')
            continue
        platform, kind = item.get('platform'), item.get('kind')
        if not isinstance(platform, str) or not platform.strip():
            problems.error(f'{label}.platform must be a nonempty string')
        if kind not in ('hashtag', 'keyword'):
            problems.error(f'{label}.kind must be hashtag or keyword')
        endpoint = item.get('endpoint')
        if not isinstance(endpoint, str) or not endpoint.startswith('/'):
            problems.error(f'{label}.endpoint must be an absolute provider path')
        method_field = item.get('method_field')
        if not isinstance(method_field, str) or not method_field.strip():
            problems.error(f'{label}.method_field must name the query field')
        fixed = item.get('fixed', {})
        if not isinstance(fixed, dict):
            problems.error(f'{label}.fixed must be an object')
        max_results = item.get('max_results', 3)
        if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 50:
            problems.error(f'{label}.max_results must be an integer from 1 to 50')
        price = _decimal(item.get('price_usd'), f'{label}.price_usd', problems)
        ranking = item.get('ranking_filter')
        if ranking is not None and not isinstance(ranking, str):
            problems.error(f'{label}.ranking_filter must be a string or null')
        key = (platform, kind)
        if key in indexed:
            problems.error(f'{label} duplicates {platform}/{kind}')
            continue
        indexed[key] = {
            'platform': platform, 'kind': kind, 'endpoint': endpoint,
            'method_field': method_field, 'fixed': fixed,
            'max_results': max_results, 'price_usd': price,
            'ranking_filter': ranking,
        }
    if not problems.ok:
        return None
    return {'provider': provider, 'currency': currency, 'endpoints': indexed}


def _call_request(endpoint, query):
    request = dict(endpoint.get('fixed') or {})
    request[endpoint['method_field']] = query
    return request


def _plan_hash(provider, context_sha, calls):
    return hc.canonical_hash({'provider': provider, 'context_sha256': context_sha,
                              'calls': calls})


def _web_evidence(path, candidates, problems):
    """Saved public-search snippets; triage evidence only, never native proof."""
    if not path:
        return None
    data = hc.read_json_file(path, 'web evidence')
    items = data.get('queries') if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        problems.error('web evidence requires a nonempty queries list')
        return None
    if len(items) > 20:
        problems.error('web evidence supports at most 20 queries')
        return None
    queries = []
    total = 0
    for index, item in enumerate(items):
        label = f'web_evidence.queries[{index}]'
        if not isinstance(item, dict):
            problems.error(f'{label} must be an object')
            continue
        query = item.get('query')
        if not isinstance(query, str) or not query.strip():
            problems.error(f'{label}.query must be a nonempty string')
            continue
        results = item.get('results', [])
        if not isinstance(results, list) or len(results) > 10:
            problems.error(f'{label}.results must be a list of at most 10 items')
            continue
        clean = []
        for result_index, result in enumerate(results):
            if not isinstance(result, dict):
                problems.error(f'{label}.results[{result_index}] must be an object')
                continue
            url, snippet = result.get('url'), result.get('snippet')
            if not isinstance(url, str) or not url.startswith(('http://', 'https://')):
                problems.error(f'{label}.results[{result_index}].url must be an http(s) URL')
                continue
            if not isinstance(snippet, str) or len(snippet) > 500:
                problems.error(f'{label}.results[{result_index}].snippet must be at most 500 chars')
                continue
            total += len(snippet)
            clean.append({'url': url, 'snippet': snippet})
        queries.append({'query': query, 'platform': item.get('platform'),
                        'results': clean})
    if total > 20_000:
        problems.error('web evidence snippets exceed the 20,000-character limit')
    tags = {hc.normalize_term(item['text']) for item in candidates
            if item.get('kind') == 'hashtag'}
    if tags and not any(hc.normalize_term(item['query']) in tags for item in queries):
        problems.warn('web evidence has no tag-alone query; snippets cannot establish native usage')
    return queries


def plan_probes(args):
    problems = hc.Problems()
    root = hc.campaign_root(args.project)
    run_dir, context, candidates = _generation(root, args.run)
    if context.get('collection_blocked'):
        problems.error('campaign context is missing or conflicting; collection is blocked')
    schema = load_schema(args.schema, problems)
    if schema is None:
        return _result(False, command='plan', errors=problems.errors,
                       warnings=problems.warnings), problems
    items = candidates.get('candidates') or []
    web_evidence = _web_evidence(getattr(args, 'web_evidence', None), items, problems)
    if args.max_calls and len(items) > args.max_calls:
        problems.error(f'{len(items)} candidates exceed --max-calls {args.max_calls}')
    calls = []
    for candidate in items:
        platform = context.get('platform')
        kind = candidate.get('kind')
        endpoint = schema['endpoints'].get((platform, kind))
        if endpoint is None:
            problems.error(f"no provider endpoint for {platform}/{kind}: {candidate.get('text')}")
            continue
        query = hc.normalize_term(candidate.get('text'))
        if kind == 'hashtag':
            if any(char.isspace() for char in query):
                problems.error(f"hashtag must be a single term: {candidate.get('text')}")
                continue
        elif not query:
            problems.error('keyword must be nonempty')
            continue
        request = _call_request(endpoint, query)
        calls.append({
            'call_id': f"call-{platform}-{kind}-{len(calls) + 1:02d}",
            'candidate_id': candidate.get('id'),
            'platform': platform,
            'kind': kind,
            'query': query,
            'original_text': candidate.get('text'),
            'provider': schema['provider'],
            'endpoint': endpoint['endpoint'],
            'ranking_filter': endpoint.get('ranking_filter'),
            'method_field': endpoint['method_field'],
            'request': request,
            'max_results': endpoint['max_results'],
            'expected_price_usd': str(endpoint['price_usd']),
        })
    seen = set()
    for call in calls:
        identity = (call['platform'], call['kind'], hc.normalize_term(call['query']))
        if identity in seen:
            problems.error(f"duplicate planned probe: {call['platform']}/{call['kind']}/{call['query']}")
        seen.add(identity)
    if not calls:
        problems.error('no candidates could be planned')
    total = sum((Decimal(call['expected_price_usd']) for call in calls), Decimal('0'))
    ceiling = None
    if args.ceiling is not None:
        ceiling = _decimal(args.ceiling, '--ceiling', problems)
        if ceiling is not None and total > ceiling:
            problems.error(f'planned calls cost {total} {schema["currency"]}; ceiling is {ceiling}')
    if not problems.ok:
        return _result(False, command='plan', errors=problems.errors,
                       warnings=problems.warnings), problems
    plan_sha = _plan_hash(schema['provider'], context['context_sha256'], calls)
    document = {
        'schema_version': 1,
        'campaign': root.name,
        'run_id': args.run,
        'context_sha256': context['context_sha256'],
        'created_at': hc.utc_now(),
        'provider': schema['provider'],
        'currency': schema['currency'],
        'approved_ceiling': str(ceiling) if ceiling is not None else None,
        'planned_total_usd': str(total),
        'plan_sha256': plan_sha,
        'web_evidence': web_evidence,
        'calls': calls,
    }
    path = run_dir / 'plan.json'
    hc.write_json(path, document)
    return _result(True, command='plan', campaign=root.name, run_id=args.run,
                   plan_path=str(path.relative_to(root)), calls=len(calls),
                   planned_total_usd=str(total), currency=schema['currency'],
                   plan_sha256=plan_sha, errors=[], warnings=problems.warnings), problems


def _load_plan(run_dir, context, path=None):
    document = hc.load_json(Path(path) if path else run_dir / 'plan.json', 'probe plan')
    if document.get('schema_version') != 1:
        raise ValueError('probe plan requires schema_version 1')
    if document.get('context_sha256') != context.get('context_sha256'):
        raise ValueError('probe plan was built from a stale context hash')
    calls = document.get('calls')
    if not isinstance(calls, list) or not calls:
        raise ValueError('probe plan requires a nonempty calls list')
    expected = _plan_hash(document.get('provider'), document.get('context_sha256'), calls)
    if document.get('plan_sha256') != expected:
        raise ValueError('probe plan hash does not match its calls')
    return document


def _idempotency_key(campaign, run_id, plan_sha, call):
    return hc.canonical_hash({
        'campaign': campaign, 'run_id': run_id, 'plan_sha256': plan_sha,
        'call_id': call['call_id'], 'provider': call['provider'],
        'endpoint': call['endpoint'], 'request': call['request'],
    })


def run_provider(call, idempotency_key, timeout=180):
    """Fixed Glasser invocation; never executes AI-supplied commands or URLs."""
    args = ['glasser', 'run', '-p', call['provider'], '-e', call['endpoint'],
            '-i', json.dumps(call['request'], ensure_ascii=False),
            '--idempotency-key', idempotency_key, '-j']
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return {'returncode': result.returncode, 'stdout': result.stdout,
            'stderr': result.stderr}


def _classify_text(text):
    text = text.lower()
    if 'auth' in text or '401' in text or '403' in text or 'unauthorized' in text:
        return 'auth_failed'
    if '404' in text or 'not found' in text:
        return 'not_found'
    if 'unsupported' in text or 'invalid endpoint' in text or '400' in text:
        return 'unsupported'
    return None


def _classify_failure(returncode, stderr):
    if returncode == 0:
        return None
    outcome = _classify_text(stderr or '')
    if outcome:
        return outcome
    return 'provider_error'


def _response_error(response):
    if isinstance(response, dict) and response.get('error'):
        return _classify_text(json.dumps(response['error'])) or 'provider_error'
    return None


def _candidate_lists(value):
    """Yield media-like lists in encounter order; provider shapes vary."""
    if isinstance(value, dict):
        for child in value.values():
            yield from _candidate_lists(child)
    elif isinstance(value, list):
        dicts = [item for item in value if isinstance(item, dict)]
        if dicts and any(any(key in item for key in MEDIA_KEYS) for item in dicts):
            yield dicts
        for item in value:
            yield from _candidate_lists(item)


def _media_score(items):
    strong = ('caption', 'desc', 'url', 'share_url', 'video_url', 'play_url',
              'shortcode', 'pk', 'aweme_id', 'transcript')
    return (sum(2 for item in items if any(key in item for key in strong)),
            len(items))


def _first(item, *keys):
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _nested(item, *keys):
    for key in keys:
        value = item.get(key)
        if isinstance(value, dict):
            for inner in ('username', 'unique_id', 'handle', 'id', 'name'):
                found = value.get(inner)
                if isinstance(found, str) and found.strip():
                    return found.strip()
    return None


def extract_media(response):
    """Tolerant ordered media extraction; no popularity sorting or zero filling."""
    lists = list(_candidate_lists(response))
    if not lists:
        return []
    best = max(lists, key=_media_score)
    media = []
    for item in best:
        caption = _first(item, 'caption', 'desc', 'description', 'title', 'text')
        transcript = _first(item, 'transcript', 'transcript_text')
        url = _first(item, 'url', 'share_url', 'video_url', 'play_url', 'permalink', 'link')
        video_id = _first(item, 'id', 'pk', 'shortcode', 'video_id', 'aweme_id')
        creator = (_nested(item, 'owner', 'author', 'creator', 'user')
                   or _first(item, 'username', 'author_name', 'creator_name'))
        unavailable = item.get('is_available') is False or bool(item.get('unavailable'))
        accessible = bool(url or video_id) and not unavailable
        evidence = []
        if caption:
            evidence.append('caption')
        if transcript:
            evidence.append('transcript')
        if url:
            evidence.append('video')
        media.append({
            'video_id': video_id,
            'url': url,
            'creator_id': creator,
            'caption': caption,
            'transcript': transcript,
            'evidence': evidence,
            'accessible': accessible,
        })
    return media


def _sample_records(call, media, max_results, collected_at):
    encountered, reviewed, skipped = [], [], []
    seen = set()
    for position, item in enumerate(media, start=1):
        identity = item.get('url') or item.get('video_id') or (
            item.get('creator_id'), item.get('caption'))
        encountered.append({
            'position': position, 'video_id': item.get('video_id'),
            'url': item.get('url'), 'creator_id': item.get('creator_id'),
            'accessible': item.get('accessible'),
        })
        if not item.get('accessible'):
            skipped.append({'position': position, 'reason': 'inaccessible',
                            'video_id': item.get('video_id'), 'url': item.get('url')})
            continue
        if identity in seen:
            skipped.append({'position': position, 'reason': 'duplicate',
                            'video_id': item.get('video_id'), 'url': item.get('url')})
            continue
        seen.add(identity)
        if len(reviewed) >= max_results:
            skipped.append({'position': position, 'reason': 'beyond_first_n',
                            'video_id': item.get('video_id'), 'url': item.get('url')})
            continue
        reviewed.append({
            'sample_id': f"{call['call_id']}-s{len(reviewed) + 1:02d}",
            'position': position,
            **item,
        })
    return {
        'call_id': call['call_id'],
        'platform': call['platform'],
        'kind': call['kind'],
        'query': call['query'],
        'source_endpoint': call['endpoint'],
        'ranking_filter': call.get('ranking_filter'),
        'collected_at': collected_at,
        'max_results': max_results,
        'unique_reviewed': len(reviewed),
        'incomplete': len(reviewed) < max_results,
        'encountered': encountered,
        'reviewed': reviewed,
        'skipped': skipped,
    }


def _status_path(run_dir, call):
    return run_dir / 'calls' / f"{call['call_id']}.status.json"


def _read_status(run_dir, call):
    return hc.load_optional_json(_status_path(run_dir, call))


def _write_status(run_dir, call, status):
    hc.write_json(_status_path(run_dir, call), status)


def collect_probes(args):
    problems = hc.Problems()
    root = hc.campaign_root(args.project)
    run_dir, context, _ = _generation(root, args.run)
    if context.get('collection_blocked'):
        problems.error('campaign context is missing or conflicting; collection is blocked')
        return _result(False, command='collect', errors=problems.errors), problems
    plan = _load_plan(run_dir, context, args.plan)
    calls = plan['calls']
    if not args.execute:
        return _result(True, command='collect', mode='dry-run',
                       calls=[{**call, 'action': 'would_run'} for call in calls],
                       planned_total_usd=plan.get('planned_total_usd'),
                       currency=plan.get('currency'), errors=[],
                       warnings=['no network or writes without --execute']), problems
    ceiling = _decimal(args.ceiling, '--ceiling', problems)
    if ceiling is None:
        return _result(False, command='collect', errors=problems.errors), problems
    approved = plan.get('approved_ceiling')
    if approved is not None:
        ceiling = min(ceiling, Decimal(approved))
    committed = Decimal('0')
    for call in calls:
        status = _read_status(run_dir, call)
        if status and status.get('outcome') == 'success':
            committed += Decimal(str(status.get('charge_usd')
                                     or call['expected_price_usd']))
    outcomes = []
    for call in calls:
        price = Decimal(str(call['expected_price_usd']))
        status = _read_status(run_dir, call)
        if status and status.get('plan_sha256') not in (None, plan['plan_sha256']):
            outcomes.append({'call_id': call['call_id'], 'action': 'stale_plan',
                             'outcome': 'stale_plan',
                             'detail': 'call was planned from different request data; use a new run'})
            continue
        if status and status.get('outcome') == 'success':
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
                             'detail': 'previous attempt is not confirmed; inspect receipts and rerun with --resume'})
            continue
        if committed + price > ceiling:
            outcomes.append({'call_id': call['call_id'], 'action': 'budget_stopped',
                             'outcome': 'budget_exceeded',
                             'detail': f'ceiling {ceiling} would be exceeded'})
            committed = ceiling + 1
            continue
        attempts = (status or {}).get('attempts', 0) + 1
        key = _idempotency_key(root.name, args.run, plan['plan_sha256'], call)
        pending = {
            'call_id': call['call_id'], 'idempotency_key': key,
            'plan_sha256': plan['plan_sha256'], 'attempts': attempts,
            'outcome': 'pending', 'started_at': hc.utc_now(), 'ended_at': None,
            'run_id': None, 'run_url': None, 'charge_usd': None,
            'expected_price_usd': call['expected_price_usd'],
        }
        _write_status(run_dir, call, pending)
        request_path = run_dir / 'calls' / f"{call['call_id']}.request.json"
        if not request_path.exists():
            hc.write_json(request_path, {'provider': call['provider'],
                                         'endpoint': call['endpoint'],
                                         'request': call['request'],
                                         'idempotency_key': key})
        committed += price
        try:
            provider = args.run_func(call, key)
        except subprocess.TimeoutExpired as exc:
            provider = {'returncode': -1, 'stdout': '', 'stderr': f'timeout: {exc}'}
        except OSError as exc:
            provider = {'returncode': -1, 'stdout': '', 'stderr': str(exc)}
        response = None
        parse_error = None
        if provider.get('stdout'):
            try:
                response = json.loads(provider['stdout'])
            except ValueError as exc:
                parse_error = str(exc)
        outcome = _classify_failure(provider.get('returncode', 0),
                                    provider.get('stderr', ''))
        media = extract_media(response) if response is not None else []
        if outcome is None and parse_error:
            outcome = 'provider_error'
        if outcome is None and response is not None:
            outcome = _response_error(response)
        if outcome is None and not media:
            outcome = 'empty_response'
        if outcome is None and not any(item['accessible'] for item in media):
            outcome = 'inaccessible'
        if outcome is None:
            outcome = 'success'
        ended_at = hc.utc_now()
        charge = _charge(response, call['expected_price_usd'])
        status = {**pending, 'attempts': attempts, 'outcome': outcome,
                  'ended_at': ended_at, 'charge_usd': charge,
                  'run_id': _run_id(response), 'run_url': _run_url(response)}
        if parse_error:
            status['parse_error'] = parse_error
        _write_status(run_dir, call, status)
        if provider.get('stdout'):
            response_path = run_dir / 'calls' / f"{call['call_id']}.response.json"
            if not response_path.exists():
                response_path.write_text(provider['stdout'])
        if provider.get('stderr'):
            (run_dir / 'calls' / f"{call['call_id']}.stderr.txt").write_text(provider['stderr'])
        if outcome == 'success':
            samples = _sample_records(call, media,
                                      call.get('max_results', 3), ended_at)
            hc.write_json(run_dir / 'calls' / f"{call['call_id']}.samples.json", samples)
        outcomes.append({'call_id': call['call_id'], 'action': 'dispatched',
                         'outcome': outcome, 'charge_usd': charge})
    return _result(True, command='collect', mode='execute',
                   outcomes=outcomes, currency=plan.get('currency'),
                   errors=[], warnings=[]), problems


def _run_id(response):
    if isinstance(response, dict):
        for key in ('run_id', 'runId'):
            if isinstance(response.get(key), str):
                return response[key]
        run = response.get('run')
        if isinstance(run, dict) and isinstance(run.get('id'), str):
            return run['id']
    return None


def _run_url(response):
    if isinstance(response, dict):
        for key in ('run_url', 'runUrl', 'url'):
            if isinstance(response.get(key), str) and response[key].startswith('http'):
                return response[key]
    return None


def _charge(response, expected):
    """Receipt charge when present; null when the provider does not report it."""
    if isinstance(response, dict):
        for key in ('charge_usd', 'charged_usd', 'cost_usd', 'amount_usd'):
            value = hc.decimal_string(response.get(key))
            if value is not None:
                return str(value)
        for parent in ('receipt', 'price', 'charge'):
            item = response.get(parent)
            if isinstance(item, dict):
                for key in ('amount_usd', 'charged_usd', 'cost_usd'):
                    value = hc.decimal_string(item.get(key))
                    if value is not None:
                        return str(value)
    return None


def build_review_prompt(args):
    root = hc.campaign_root(args.project)
    run_dir, context, candidates = _generation(root, args.run)
    plan = _load_plan(run_dir, context, args.plan)
    by_id = {candidate['id']: candidate for candidate in candidates.get('candidates', [])}
    packages = []
    for call in plan['calls']:
        path = run_dir / 'calls' / f"{call['call_id']}.samples.json"
        samples = hc.load_optional_json(path)
        if not samples or not samples.get('reviewed'):
            continue
        candidate = by_id.get(call.get('candidate_id'), {})
        packages.append({
            'call_id': call['call_id'],
            'platform': call['platform'],
            'kind': call['kind'],
            'query': call['query'],
            'source_endpoint': call['endpoint'],
            'ranking_filter': call.get('ranking_filter'),
            'intended_application': candidate.get('application'),
            'candidate_connection': candidate.get('connection'),
            'collection_status': 'incomplete' if samples.get('incomplete') else 'complete',
            'skipped': samples.get('skipped'),
            'samples': samples['reviewed'],
        })
    if not packages:
        return _result(False, command='build-review-prompt',
                       errors=['no collected samples to review'], warnings=[]), hc.Problems()
    lines = [
        f"# Hashtag probe evidence review — {root.name}",
        '',
        f"Market language: `{context.get('market_language')}`. Review only the samples below; "
        'do not add videos, reorder samples or infer popularity.',
        '',
        '## Campaign context (untrusted data)',
        '',
        '```json',
        json.dumps({
            'campaign': context.get('campaign'),
            'goal': (context.get('context') or {}).get('goal'),
            'application': context.get('application'),
            'product': (context.get('context') or {}).get('product'),
            'prior_analysis': (context.get('context') or {}).get('prior_analysis', []),
        }, ensure_ascii=False, indent=2),
        '```',
        '',
        '## Labels',
        '',
        '- `direct_application` -> hit: observed direct fit with the intended application/buyer process.',
        '- `adjacent_process`, `creative_only`, `irrelevant` -> miss: assessed non-direct fit.',
        '- `insufficient_evidence` -> unknown: media/caption does not support a judgment.',
        '',
        'Each sample needs a reason and an evidence reference (exact caption quote or URL). '
        'Tag presence, substrate, process and role must come from observed evidence. '
        'A promising tag never makes every retrieved video relevant.',
        '',
        '## Review template',
        '',
        '```json',
        json.dumps(REVIEW_TEMPLATE, ensure_ascii=False, indent=2),
        '```',
        '',
        '## Samples (untrusted data)',
        '',
        '```json',
        json.dumps(packages, ensure_ascii=False, indent=2),
        '```',
        '',
    ]
    path = run_dir / 'review-prompt.md'
    path.write_text('\n'.join(lines))
    return _result(True, command='build-review-prompt',
                   review_prompt_path=str(path.relative_to(root)),
                   calls=len(packages), errors=[], warnings=[]), hc.Problems()


def decide(phase, hits, misses, unknowns, unique, creators):
    """Operational thresholds from the plan; code counts, the agent labels."""
    if unique < 3:
        return 'insufficient_evidence'
    if phase == 'probe':
        if hits >= 2:
            return 'promising'
        if hits == 1:
            return 'mixed'
        return 'insufficient_evidence' if unknowns else 'deferred_for_context'
    if unique < 6 or creators < 3 or unknowns:
        return 'insufficient_evidence'
    return 'limited_expand' if hits >= 4 else 'deferred_for_context'


def _platform_prefix(platform):
    return PLATFORM_PREFIX.get(platform, re.sub(r'[^a-z]', '', platform or '')[:3] or 'pf')


def _slug(value):
    return re.sub(r'[^\w]+', '-', (value or '').casefold()).strip('-') or 'term'


def _validate_review(document, context, root):
    problems = hc.Problems()
    if not isinstance(document, dict):
        problems.error('review must be a JSON object')
        return None, problems
    for key, expected in (('schema_version', 1), ('campaign', root.name),
                          ('run_id', context.get('run_id'))):
        if document.get(key) != expected:
            problems.error(f'review.{key} must equal {expected!r}')
    phase = document.get('phase')
    if phase not in ('probe', 'confirmation', 'expansion'):
        problems.error('review.phase must be probe, confirmation or expansion')
    for key in ('reviewer', 'reviewer_type'):
        if not isinstance(document.get(key), str) or not document[key].strip():
            problems.error(f'review.{key} must be a nonempty string')
    if document.get('checked_at') is not None:
        try:
            storage.timestamp(document['checked_at'])
        except (ValueError, TypeError):
            problems.error('review.checked_at must be a timezone-aware ISO timestamp')
    evaluations = document.get('evaluations')
    if not isinstance(evaluations, list) or not evaluations:
        problems.error('review.evaluations must be a nonempty list')
        return document, problems
    for index, evaluation in enumerate(evaluations):
        if not isinstance(evaluation, dict):
            problems.error(f'review.evaluations[{index}] must be an object')
            continue
        if not isinstance(evaluation.get('call_id'), str) or not evaluation['call_id'].strip():
            problems.error(f'review.evaluations[{index}].call_id is required')
        if not isinstance(evaluation.get('samples'), list) or not evaluation['samples']:
            problems.error(f'review.evaluations[{index}].samples must be a nonempty list')
    return document, problems


def _evaluation_record(root, context, plan, review, package, candidate, samples,
                       checked_at, human_corrected):
    counts = {'hit': 0, 'miss': 0, 'unknown': 0}
    creators = set()
    evidence = []
    observed = []
    sample_labels = []
    for item in samples:
        counts[LABEL_TO_GROUP[item['label']]] += 1
        sample = next(entry for entry in package['reviewed']
                      if entry['sample_id'] == item['sample_id'])
        if sample.get('creator_id'):
            creators.add(sample['creator_id'])
        evidence.extend(item.get('evidence') or [])
        if isinstance(item.get('observed'), dict):
            observed.append(item['observed'])
        sample_labels.append({
            'sample_id': item['sample_id'],
            'video_id': sample.get('video_id'),
            'url': sample.get('url'),
            'creator_id': sample.get('creator_id'),
            'position': sample.get('position'),
            'label': item['label'],
            'reason': item.get('reason'),
            'evidence': item.get('evidence'),
            'observed': item.get('observed'),
        })
    hits, misses, unknowns = counts['hit'], counts['miss'], counts['unknown']
    unique = len(samples)
    decision = decide(review['phase'], hits, misses, unknowns, unique, len(creators))
    call = next(entry for entry in plan['calls'] if entry['call_id'] == package['call_id'])
    date = re.sub(r'[^0-9]', '', checked_at)[:8]
    platform_short = _platform_prefix(context.get('platform'))
    base_id = f"eval-{platform_short}-{_slug(call['query'])}-{date}-{review['phase']}"
    return {
        'evaluation_id': base_id,
        'campaign': context.get('campaign'),
        'run_id': context.get('run_id'),
        'probe_id': call['call_id'],
        'checked_at': checked_at,
        'platform': call['platform'],
        'application': candidate.get('application'),
        'intended_application': candidate.get('application'),
        'observed_applications': sorted({item.get('application') for item in observed
                                         if item.get('application')}),
        'market_language': context.get('market_language'),
        'source_endpoint': call['endpoint'],
        'ranking_filter': call.get('ranking_filter'),
        'phase': review['phase'],
        'query_kind': call['kind'],
        'query_text': call['query'],
        'candidate_id': call.get('candidate_id'),
        'sample_creator_ids': sorted(creators),
        'sample_labels': sample_labels,
        'hits': hits,
        'misses': misses,
        'unknowns': unknowns,
        'unique_reviewed': unique,
        'decision': decision,
        'reason': next((entry.get('reason') for entry in review['evaluations']
                        if entry.get('call_id') == package['call_id']), None),
        'evidence_references': list(dict.fromkeys(evidence)),
        'collection_status': 'incomplete' if package.get('incomplete') else 'complete',
        'prompt_version': review.get('prompt_version') or context.get('prompt_version'),
        'reviewer': review.get('reviewer'),
        'reviewer_type': review.get('reviewer_type'),
        'model': review.get('model'),
        'human_corrected': bool(human_corrected),
    }


def record_review(args):
    problems = hc.Problems()
    root = hc.campaign_root(args.project)
    run_dir, context, candidates = _generation(root, args.run)
    plan = _load_plan(run_dir, context, args.plan)
    document = hc.read_json_file(args.review, 'review')
    document, review_problems = _validate_review(document, context, root)
    problems.errors.extend(review_problems.errors)
    if document is None or not problems.ok:
        return _result(False, command='record-review', errors=problems.errors,
                       warnings=problems.warnings), problems
    candidates_by_id = {item['id']: item for item in candidates.get('candidates', [])}
    calls_by_id = {call['call_id']: call for call in plan['calls']}
    packages = {}
    for call in plan['calls']:
        samples = hc.load_optional_json(run_dir / 'calls' / f"{call['call_id']}.samples.json")
        if samples and samples.get('reviewed'):
            packages[call['call_id']] = samples
    reviewed_calls = {entry.get('call_id') for entry in document['evaluations']}
    if reviewed_calls != set(packages):
        missing = sorted(set(packages) - reviewed_calls)
        extra = sorted(reviewed_calls - set(packages))
        problems.error(f'review must cover every collected call; missing={missing} extra={extra}')
    checked_at = document.get('checked_at') or hc.utc_now()
    try:
        storage.timestamp(checked_at)
    except (ValueError, TypeError):
        problems.error('review.checked_at must be a timezone-aware ISO timestamp')
        return _result(False, command='record-review', errors=problems.errors), problems
    records = []
    for evaluation in document['evaluations']:
        call_id = evaluation.get('call_id')
        package = packages.get(call_id)
        if package is None:
            continue
        call = calls_by_id[call_id]
        sample_ids = [item.get('sample_id') for item in evaluation.get('samples') or []]
        expected_ids = [item['sample_id'] for item in package['reviewed']]
        if sample_ids != expected_ids:
            problems.error(f'{call_id}: review samples must match the reviewed set in order; '
                           f'expected {expected_ids}, got {sample_ids}')
            continue
        for item in evaluation['samples']:
            if item.get('label') not in hc.LABELS:
                problems.error(f"{call_id}/{item.get('sample_id')}: invalid label {item.get('label')!r}")
            if not isinstance(item.get('reason'), str) or not item['reason'].strip():
                problems.error(f"{call_id}/{item.get('sample_id')}: reason is required")
            evidence = item.get('evidence')
            if not isinstance(evidence, list) or not evidence or not all(
                    isinstance(value, str) and value.strip() for value in evidence):
                problems.error(f"{call_id}/{item.get('sample_id')}: evidence references are required")
            observed = item.get('observed')
            if observed is not None and not isinstance(observed, dict):
                problems.error(f"{call_id}/{item.get('sample_id')}: observed must be an object")
        if problems.errors:
            continue
        candidate = candidates_by_id.get(call.get('candidate_id'), {})
        records.append(_evaluation_record(
            root, context, plan, document, package, candidate,
            evaluation['samples'], checked_at, args.human_corrected))
    if problems.errors:
        return _result(False, command='record-review', errors=problems.errors,
                       warnings=problems.warnings), problems
    hc.write_json(run_dir / 'review.json', document)
    hc.write_json(run_dir / 'evaluations.json', {'schema_version': 1,
                                                 'records': records})
    items = []
    for record, evaluation in zip(records, document['evaluations']):
        call = calls_by_id[evaluation['call_id']]
        items.append({
            'platform': call['platform'],
            'key': hc.history_key(call['kind'], call['query']),
            'record': record,
            'original_term': call.get('original_text') or call['query'],
            'normalized_term': hc.normalize_term(call['query']),
            'correction': args.correction,
        })
    try:
        merges = hc.append_evaluations(root, items)
    except hc.HistoryConflict as exc:
        problems.error(str(exc))
        merges = []
    return _result(not problems.errors, command='record-review', campaign=root.name,
                   run_id=args.run, records=records, merges=merges,
                   errors=problems.errors, warnings=problems.warnings), problems


def history_report(args):
    root = hc.campaign_root(args.project)
    data = hc.load_history(root)
    rows = []
    for platform, entry, evaluations in hc.history_entries(data):
        if args.platform and platform != args.platform:
            continue
        kind = hc.infer_query_kind(entry)
        key = entry.get('normalized_tag') or entry.get('original_tag')
        if args.key and hc.normalize_term(args.key) not in (hc.normalize_term(key), hc.normalize_term(entry.get('original_tag'))):
            continue
        totals = {field: sum(int(item.get(field) or 0) for item in evaluations)
                  for field in ('hits', 'misses', 'unknowns', 'unique_reviewed')}
        latest = evaluations[-1] if evaluations else None
        rows.append({
            'platform': platform,
            'key': key,
            'original_term': entry.get('original_tag'),
            'query_kind': kind,
            'legacy_kind_inferred': 'query_kind' not in entry,
            'legacy_unverified': any('probe_id' not in item or
                                     'collection_status' not in item
                                     for item in evaluations),
            'evaluations': len(evaluations),
            'totals': totals,
            'latest': latest,
        })
    return _result(True, command='history', campaign=root.name,
                   schema_version=data.get('schema_version'), entries=rows,
                   errors=[], warnings=[]), hc.Problems()


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)

    def generation(command, help_text):
        item = commands.add_parser(command, help=help_text)
        item.add_argument('--project', required=True)
        item.add_argument('--run', required=True)
        return item

    plan = generation('plan', 'Write an exact, priced request plan from validated candidates')
    plan.add_argument('--schema', required=True,
                      help='Saved provider schema/price JSON (from glasser inspect)')
    plan.add_argument('--max-calls', type=int, default=hc.MAX_CANDIDATES)
    plan.add_argument('--ceiling', help='Optional decimal ceiling checked against planned calls')
    plan.add_argument('--web-evidence',
                      help='Optional saved public-search evidence JSON (tag-alone and qualified queries)')
    plan.set_defaults(command_func=plan_probes)

    collect = generation('collect', 'Preview planned calls; --execute dispatches with receipts')
    collect.add_argument('--plan', help='Plan path; defaults to the run plan.json')
    collect.add_argument('--execute', action='store_true', help='Dispatch provider calls')
    collect.add_argument('--ceiling', help='Decimal spend ceiling required with --execute')
    collect.add_argument('--resume', action='store_true',
                         help='Reuse the same idempotency key after an unconfirmed attempt')
    collect.set_defaults(command_func=collect_probes, run_func=run_provider)

    review = generation('build-review-prompt', 'Package collected samples for agent evidence review')
    review.add_argument('--plan', help='Plan path; defaults to the run plan.json')
    review.set_defaults(command_func=build_review_prompt)

    record = generation('record-review', 'Validate labels, count, decide and append history')
    record.add_argument('--review', required=True, help='Saved review JSON')
    record.add_argument('--plan', help='Plan path; defaults to the run plan.json')
    record.add_argument('--correction', action='store_true',
                        help='Append a superseding evaluation instead of conflicting')
    record.add_argument('--human-corrected', action='store_true',
                        help='A human corrected the agent labels')
    record.set_defaults(command_func=record_review)

    hist = commands.add_parser('history', help='Read-only campaign hashtag/keyword history summary')
    hist.add_argument('--project', required=True)
    hist.add_argument('--platform')
    hist.add_argument('--key', help='Original or normalized term/key')
    hist.set_defaults(command_func=history_report)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        result, _ = args.command_func(args)
    except (ValueError, OSError) as exc:
        print(json.dumps({'ok': False, 'command': args.command,
                          'errors': [str(exc)]}, ensure_ascii=False))
        return 2
    except Exception as exc:
        print(json.dumps({'ok': False, 'command': args.command,
                          'errors': [f'unexpected failure: {exc}']}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    sys.exit(main())
