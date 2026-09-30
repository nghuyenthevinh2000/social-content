"""Candidate selection, report orchestration, and artifact generation."""

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _parse_iso_timestamp(val: Any) -> Optional[datetime]:
    """Parse ISO timestamp with timezone. Return None if missing, non-string, malformed, or naive."""
    if not isinstance(val, str) or not val.strip():
        return None
    try:
        dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            return None
        return dt
    except Exception:
        return None


def select_candidates(observations: List[Dict[str, Any]], *, start: int, end: int, per_topic: int) -> Dict[str, Any]:
    """Deterministically select top candidates by observed engagement within [start, end)."""
    collected_count = len(observations)

    # 1. Deduplicate observations in insertion order, keeping latest observation and unique source_modes
    by_id: Dict[str, Dict[str, Any]] = {}
    source_modes_by_id: Dict[str, List[str]] = {}

    for obs in observations:
        post = copy.deepcopy(obs.get('post', {}))
        pid = str(post.get('id', ''))
        mode = obs.get('mode', '')
        observed_at = obs.get('observed_at', '')

        if pid not in source_modes_by_id:
            source_modes_by_id[pid] = []
        if mode and mode not in source_modes_by_id[pid]:
            source_modes_by_id[pid].append(mode)

        # Retain latest observation
        post['observed_at'] = observed_at
        by_id[pid] = post

    unique_candidates = list(by_id.values())
    unique_count = len(unique_candidates)
    duplicates_count = collected_count - unique_count

    # 2. Evaluate exclusions in priority order
    excluded_ads = 0
    excluded_invalid_timestamp = 0
    excluded_outside_window = 0

    parsed_timestamps: Dict[str, float] = {}
    eligible: List[Dict[str, Any]] = []

    for cand in unique_candidates:
        pid = cand['id']
        cand['source_modes'] = list(source_modes_by_id.get(pid, []))

        # Check 1: Ad exclusion
        if cand.get('is_ad'):
            cand['exclusion_reason'] = 'ad'
            excluded_ads += 1
            continue

        # Check 2: Invalid/missing/naive timestamp
        raw_ts = cand.get('timestamp')
        dt = _parse_iso_timestamp(raw_ts)
        if dt is None:
            cand['exclusion_reason'] = 'invalid_timestamp'
            excluded_invalid_timestamp += 1
            continue

        ts_epoch = dt.timestamp()
        parsed_timestamps[pid] = ts_epoch

        # Check 3: Outside interval [start, end)
        if not (start <= ts_epoch < end):
            cand['exclusion_reason'] = 'outside_window'
            excluded_outside_window += 1
            continue

        # Eligible
        cand['exclusion_reason'] = None
        eligible.append(cand)

    # 3. Sort eligible candidates:
    # Primary: -metrics.total
    # Secondary: -timestamp (newer first)
    # Tertiary: ascending id
    eligible.sort(key=lambda item: (
        -item.get('metrics', {}).get('total', 0),
        -parsed_timestamps[item['id']],
        item['id']
    ))

    selected_ids = [item['id'] for item in eligible[:per_topic]]

    counts = {
        'collected': collected_count,
        'unique': unique_count,
        'duplicates': duplicates_count,
        'excluded_ads': excluded_ads,
        'excluded_invalid_timestamp': excluded_invalid_timestamp,
        'excluded_outside_window': excluded_outside_window,
        'eligible': len(eligible),
        'selected': len(selected_ids),
    }

    return {
        'candidates': unique_candidates,
        'selected_ids': selected_ids,
        'counts': counts,
    }


from playwright.sync_api import Error as PlaywrightError
from .models import AgentError
from .posts import read_posts
from .topic_config import build_topic_query

FATAL_REPORT_ERRORS = {
    'not_authenticated', 'browser_challenge', 'account_blocked',
    'browser_not_connected', 'browser_connection_failed', 'no_browser_context',
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def collect_report(
    page: Any,
    topics: List[Dict[str, Any]],
    *,
    topics_file: str,
    start: int,
    end: int,
    per_topic: int,
    candidate_limit: int
) -> Dict[str, Any]:
    """Execute all-topic collection with bounded Top/Latest budgets and error handling."""
    top_limit = (candidate_limit + 1) // 2
    latest_limit = candidate_limit // 2
    search_specs = [('top', top_limit), ('latest', latest_limit)]

    topic_entries = []
    session_fatal = False
    any_degraded_search = False

    for topic in topics:
        tid = topic['id']
        tname = topic['name']
        query = build_topic_query(topic, start=start, end=end)

        topic_observations = []
        searches = []
        timeout_occurred = False

        if session_fatal:
            # Entire topic skipped due to prior fatal error
            for mode, limit in search_specs:
                searches.append({
                    'mode': mode,
                    'allocated_limit': limit,
                    'collected': 0,
                    'observed_at': None,
                    'reason': 'skipped',
                    'stop_reason': 'skipped',
                    'scrolls': 0,
                    'error': None,
                })
            any_degraded_search = True
            selection = select_candidates([], start=start, end=end, per_topic=per_topic)
            topic_entries.append({
                **copy.deepcopy(topic),
                'query': query,
                'status': 'skipped',
                'shortfall': True,
                'searches': searches,
                'candidates': selection['candidates'],
                'selected_ids': selection['selected_ids'],
                'counts': selection['counts'],
            })
            continue

        for mode, limit in search_specs:
            if session_fatal:
                searches.append({
                    'mode': mode,
                    'allocated_limit': limit,
                    'collected': 0,
                    'observed_at': None,
                    'reason': 'skipped',
                    'stop_reason': 'skipped',
                    'scrolls': 0,
                    'error': None,
                })
                any_degraded_search = True
                continue

            try:
                res = read_posts(page, 'search', query, limit=limit, search_mode=mode)
                obs_time = _utc_now_iso()
                posts = res.get('posts', [])
                stop_reason = res.get('reason', 'no_progress')
                scrolls = res.get('scrolls', 0)

                for p in posts:
                    topic_observations.append({
                        'post': p,
                        'mode': mode,
                        'observed_at': obs_time,
                    })

                if stop_reason == 'timeout':
                    timeout_occurred = True
                    any_degraded_search = True

                searches.append({
                    'mode': mode,
                    'allocated_limit': limit,
                    'collected': len(posts),
                    'observed_at': obs_time,
                    'reason': stop_reason,
                    'stop_reason': stop_reason,
                    'scrolls': scrolls,
                    'error': None,
                })

            except AgentError as err:
                obs_time = _utc_now_iso()
                any_degraded_search = True
                error_obj = {
                    'code': err.code,
                    'message': err.message,
                    'human_action_required': err.human_action_required,
                }
                searches.append({
                    'mode': mode,
                    'allocated_limit': limit,
                    'collected': 0,
                    'observed_at': obs_time,
                    'reason': 'error',
                    'stop_reason': 'error',
                    'scrolls': 0,
                    'error': error_obj,
                })
                if err.code in FATAL_REPORT_ERRORS:
                    session_fatal = True

            except PlaywrightError as err:
                obs_time = _utc_now_iso()
                any_degraded_search = True
                error_obj = {
                    'code': 'browser_navigation_failed',
                    'message': str(err),
                    'human_action_required': False,
                }
                searches.append({
                    'mode': mode,
                    'allocated_limit': limit,
                    'collected': 0,
                    'observed_at': obs_time,
                    'reason': 'error',
                    'stop_reason': 'error',
                    'scrolls': 0,
                    'error': error_obj,
                })

        selection = select_candidates(topic_observations, start=start, end=end, per_topic=per_topic)

        successful_searches = sum(1 for s in searches if s['error'] is None and s['stop_reason'] != 'skipped')
        failed_searches = sum(1 for s in searches if s['error'] is not None)
        skipped_searches = sum(1 for s in searches if s['stop_reason'] == 'skipped')

        if successful_searches == len(search_specs) and failed_searches == 0:
            if selection['counts']['eligible'] > 0:
                topic_status = 'ok'
            else:
                topic_status = 'empty'
        elif successful_searches > 0 and (failed_searches > 0 or skipped_searches > 0):
            topic_status = 'partial'
        elif successful_searches == 0 and failed_searches > 0:
            topic_status = 'error'
        else:
            topic_status = 'skipped'

        if timeout_occurred and topic_status == 'ok':
            topic_status = 'partial'

        shortfall = len(selection['selected_ids']) < per_topic

        topic_entries.append({
            **copy.deepcopy(topic),
            'query': query,
            'status': topic_status,
            'shortfall': shortfall,
            'searches': searches,
            'candidates': selection['candidates'],
            'selected_ids': selection['selected_ids'],
            'counts': selection['counts'],
        })

    # Summary
    by_status = {'ok': 0, 'empty': 0, 'partial': 0, 'error': 0, 'skipped': 0}
    for t in topic_entries:
        s = t['status']
        by_status[s] = by_status.get(s, 0) + 1

    selected_topic_entries = sum(len(t['selected_ids']) for t in topic_entries)
    unique_selected_posts = len({pid for t in topic_entries for pid in t['selected_ids']})

    summary = {
        'total_topics': len(topic_entries),
        'by_status': by_status,
        'selected_topic_entries': selected_topic_entries,
        'unique_selected_posts': unique_selected_posts,
    }

    start_iso = datetime.fromtimestamp(start, tz=timezone.utc).isoformat().replace('+00:00', 'Z')
    end_iso = datetime.fromtimestamp(end, tz=timezone.utc).isoformat().replace('+00:00', 'Z')

    return {
        'schema_version': 1,
        'generated_at': _utc_now_iso(),
        'window': {
            'start': start,
            'end': end,
            'start_iso': start_iso,
            'end_iso': end_iso,
        },
        'config': {
            'topics_file': topics_file,
            'window_hours': (end - start) // 3600,
            'per_topic': per_topic,
            'candidate_limit': candidate_limit,
            'ranking': 'engagement',
        },
        'coverage': 'bounded_sample',
        'partial': any_degraded_search,
        'topics': topic_entries,
        'summary': summary,
    }


def write_report(report: Dict[str, Any], output_dir: Path) -> Dict[str, str]:
    """Atomically write evidence.json inside a unique run directory under output_dir."""
    out = Path(output_dir)
    if out.is_file():
        raise AgentError('report_write_failed', f"Output directory path '{out}' is an existing file.")

    try:
        out.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise AgentError('report_write_failed', f"Failed to create output directory '{out}': {exc}") from exc

    gen_at = report.get('generated_at')
    dt = _parse_iso_timestamp(gen_at) if gen_at else None
    if not dt:
        dt = datetime.now(timezone.utc)

    timestamp = dt.strftime('%Y%m%d-%H%M%S')
    base_name = f"report-{timestamp}"

    counter = 1
    run_dir = out / base_name
    while True:
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            run_dir = out / f"{base_name}-{counter}"
            counter += 1
        except Exception as exc:
            raise AgentError('report_write_failed', f"Failed to create run directory in '{out}': {exc}") from exc

    evidence_final = run_dir / 'evidence.json'
    temp_evidence = run_dir / 'evidence.json.tmp'

    try:
        evidence_content = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        temp_evidence.write_text(evidence_content, encoding='utf-8')
        temp_evidence.replace(evidence_final)
    except Exception as exc:
        if temp_evidence.exists():
            try:
                temp_evidence.unlink()
            except Exception:
                pass
        raise AgentError('report_write_failed', f"Failed to write report artifacts to '{run_dir}': {exc}") from exc

    return {
        'run_dir': str(run_dir),
        'evidence_json': str(evidence_final),
    }


