"""Same-sample timing comparison; no second feed run or invented manual baseline."""

import json
import os
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

from .browser import Browser
from .models import AgentError
from .reel_decisions import judge_file, product_context
from .reels import collect_reels


def run_benchmark(args):
    if not 1 <= args.target_count <= args.max_observations <= 50:
        raise AgentError('invalid_arguments', 'Require 1 <= target count <= max observations <= 50.')
    if not args.approve_api:
        raise AgentError('invalid_arguments', 'Use --approve-api to authorize up to max-observations paid Jev requests.')
    if not os.environ.get('TYPESAFE_API_KEY', '').strip():
        raise AgentError('missing_credentials', 'Set TYPESAFE_API_KEY in tools/.env or the environment; browser was not opened.', True)
    product_context(args.product_dir)
    directory = Path(args.output_dir)
    if directory.exists():
        raise AgentError('invalid_arguments', 'Benchmark output directory must be new.')
    directory.mkdir(parents=True)
    started = perf_counter()
    with Browser(endpoint=args.cdp, timeout_ms=args.timeout_ms or 30000) as browser:
        observations = collect_reels(browser, args.page_id, args.max_observations)
    collection_seconds = perf_counter() - started
    raw = directory / 'observations.json'
    with raw.open('x') as stream:
        json.dump(observations, stream, ensure_ascii=False, indent=2)
    judgment_path = directory / 'jev-judgments.json'
    judgment_started = perf_counter()
    summary = judge_file(SimpleNamespace(
        input=str(raw), product_dir=args.product_dir, output=str(judgment_path),
        limit=args.max_observations, threshold=0.9, model='jev-latest', dry_run=False,
        approve_api=True, vietnamese_audience=True, target_count=args.target_count))
    judgment_seconds = perf_counter() - judgment_started
    judgments = json.loads(judgment_path.read_text())
    by_order = {record['order']: record for record in observations['records']}
    selected = [{**by_order[r['order']], 'jev': r} for r in judgments['records'] if r['selected']]
    with (directory / 'selected-reels.json').open('x') as stream:
        json.dump({'profile': observations['profile'], 'target_count': args.target_count,
                   'selected_count': len(selected), 'records': selected}, stream, ensure_ascii=False, indent=2)
    timing = {
        'comparison': 'Same raw sample. Without Jev is collection only, NOT equivalent manual semantic filtering.',
        'without_jev_collection_seconds': round(collection_seconds, 4),
        'jev_stage_seconds': round(judgment_seconds, 4),
        'with_jev_collection_plus_judgment_seconds': round(collection_seconds + judgment_seconds, 4),
        'pipeline_elapsed_seconds': round(perf_counter() - started, 4),
        'scope': 'Monotonic wall time; excludes code changes, setup diagnostics, and agent explanation/report drafting.',
        'observations': len(observations['records']), 'jev_requests': summary['judged'],
        'selected': len(selected), 'target': args.target_count,
        'target_met': len(selected) >= args.target_count,
        'promotion_excluded': summary['excluded'],
        'api_request_seconds': round(sum(r['request_seconds'] for r in judgments['records']), 4),
        'tokens': {key: sum(r['usage'].get(key, 0) or 0 for r in judgments['records'])
                   for key in ('input_tokens', 'output_tokens')},
        'models': sorted({r['model'] for r in judgments['records']}),
        'limitations': 'Text-only audience inference; thresholds provisional; no measured model accuracy or dollar cost.',
    }
    with (directory / 'timing.json').open('x') as stream:
        json.dump(timing, stream, ensure_ascii=False, indent=2)
    return {'output_directory': str(directory), **timing}
