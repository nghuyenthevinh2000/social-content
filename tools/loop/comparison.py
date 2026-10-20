"""Pure comparison and review functions: no network, no file mutation, no LLM.

Implements rules from:
- tools/loop/content-comparison.md
- tools/loop/group-comparison.md
- tools/loop/metrics-learning-plan.md
"""

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional
import uuid


def gap_key(gap: Dict[str, Any]) -> tuple:
    """Stable identity for duplicate clean-up; keeps distinct placements separate."""
    return (gap.get('kind'), gap.get('placement_id'), gap.get('detail'))


def dedupe_gaps(gaps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    unique = []
    for gap in gaps:
        key = gap_key(gap)
        if key in seen:
            continue
        seen.add(key)
        unique.append(gap)
    return unique


DEFAULT_POLICY: Dict[str, Any] = {
    'matched_age_max_over_hours': 2.0,
    'matched_age_max_diff_hours': 2.0,
    'group_review_min_rounds': 3,
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_observations(
    manifest: Dict[str, Any],
    raw_inputs: Dict[str, Any],
    placements: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Normalize raw collector outputs into scoped observations and gap tasks."""
    observations = []
    gaps = list(manifest.get('gaps', []))
    placement_by_post = {
        str(item.get('copy_post_id')): item
        for item in placements or []
        if item.get('copy_post_id')
    }

    # 1. Dashboard captures
    for cap in raw_inputs.get('insights_captures', []):
        observed_at = cap.get('observed_at') or cap.get('records', [{}])[0].get('observed_at')
        records = cap.get('records', [])
        if not records:
            gaps.append({
                'kind': 'empty_capture',
                'placement_id': cap.get('placement_id'),
                'detail': 'Insights capture contains no records.'
            })
            continue

        primary = records[0]
        metrics = primary.get('post_metrics') or {}
        placement_id = cap.get('placement_id')
        checkpoint = cap.get('checkpoint', '24h')
        actual_age = cap.get('actual_age_hours')

        # Check if tabs were captured
        stages = {r.get('stage') for r in records}
        panel_status = {
            'traffic_captured': 'initial' in stages,
            'source_captured': 'Source' in stages or any(r.get('how_people_find_content') for r in records),
            'demographics_captured': bool(primary.get('age_gender_segments') or primary.get('reported_age_percentages')),
        }
        if not panel_status['source_captured']:
            gaps.append({
                'kind': 'partial_capture',
                'placement_id': placement_id,
                'detail': 'Source panel was not explicitly opened; discovery breakdown incomplete.'
            })

        evidence_str = str(cap.get('evidence_file', ''))
        evidence_hash = cap.get('evidence_hash') or (hashlib.sha256(evidence_str.encode('utf-8')).hexdigest() if evidence_str else None)

        observations.append({
            'id': f"obs-{placement_id}-{checkpoint}-{len(observations)}",
            'placement_id': placement_id,
            'publication_id': cap.get('publication_id'),
            'checkpoint': checkpoint,
            'observed_at': observed_at,
            'actual_age_hours': actual_age,
            'scope': 'cumulative',
            'source': 'facebook_insights_dashboard',
            'metrics': {
                'views': metrics.get('views'),
                'viewers': metrics.get('viewers'),
                'three_second_views': metrics.get('three_second_views'),
                'average_watch_time_seconds': metrics.get('average_watch_time_seconds'),
                'average_percentage_watched': metrics.get('average_percentage_watched'),
                'reactions': metrics.get('reactions'),
                'comments': metrics.get('comments'),
                'shares': metrics.get('shares'),
                'clicks': metrics.get('clicks'),
                'watch_time_seconds': metrics.get('watch_time_seconds'),
                'largest_dropoff_seconds': metrics.get('largest_dropoff_seconds'),
                'qualified_inquiries': None,
            },
            'panel_status': panel_status,
            'evidence_file': cap.get('evidence_file'),
            'evidence_hash': evidence_hash,
        })

    # 2. Content library group rows
    for row in raw_inputs.get('content_library_rows', []):
        row_id = row.get('id') or row.get('post_id') or row.get('row_id')
        if not row_id:
            row_text = row.get('raw_text', '')
            row_id = hashlib.sha256(row_text.encode('utf-8')).hexdigest()[:10] if row_text else uuid.uuid4().hex[:8]

        # A verified Page post ID is the only safe join. Titles are never merged.
        matched = placement_by_post.get(str(row.get('post_id'))) if row.get('post_id') else None
        placement_id = matched.get('id') if matched else row.get('placement_id')
        publication_id = matched.get('publication_id') if matched else row.get('publication_id')

        group_id = row.get('group_id')
        placement_kind = row.get('kind') or row.get('placement_kind')
        if (not group_id and placement_kind == 'group_copy') or row.get('unresolved_group_identity'):
            gaps.append({
                'kind': 'unresolved_group_identity',
                'placement_id': placement_id or row_id,
                'group_name': row.get('group_name'),
                'detail': f"Group copy '{row.get('group_name') or row.get('permalink') or row_id}' lacks a stable numeric group ID; distribution is descriptive only."
            })

        evidence_str = str(row.get('evidence_file', ''))
        row_hash = row.get('evidence_hash') or (hashlib.sha256(evidence_str.encode('utf-8')).hexdigest() if evidence_str else None)

        observations.append({
            'id': f"obs-lib-{row_id}",
            'placement_id': placement_id,
            'publication_id': publication_id,
            'identity_source': 'page_post_id' if matched else ('group_id' if group_id else 'unresolved'),
            'copy_post_id': row.get('post_id'),
            'checkpoint': 'observation',
            'observed_at': row.get('observed_at') or _iso_now(),
            'actual_age_hours': row.get('age_hours'),
            'scope': 'period_summary',
            'source': 'content_library',
            'metrics': {
                'views': row.get('views'),
                'viewers': row.get('viewers'),
                'three_second_views': row.get('three_second_views'),
                'average_watch_time_seconds': None,
                'average_percentage_watched': None,
                'reactions': row.get('reactions'),
                'comments': row.get('comments'),
                'shares': row.get('shares'),
                'clicks': None,
                'watch_time_seconds': None,
                'largest_dropoff_seconds': None,
                'qualified_inquiries': None,
            },
            'panel_status': {'library_row': True},
            'evidence_file': row.get('evidence_file'),
            'evidence_hash': row_hash,
        })

    # 3. CSV imports
    csv_hash = raw_inputs.get('csv_evidence_hash')
    for post in raw_inputs.get('csv_posts', []):
        post_id = post.get('post_id')
        summary = post.get('export_period_totals') or post.get('summary_metrics') or {}
        observations.append({
            'id': f"obs-csv-{post_id}",
            'placement_id': post.get('placement_id'),
            'publication_id': post.get('publication_id'),
            'checkpoint': 'period_summary',
            'observed_at': _iso_now(),
            'actual_age_hours': None,
            'scope': 'period_summary',
            'source': 'csv_export',
            'metrics': {
                'views': None,
                'viewers': None,
                'three_second_views': None,
                'average_watch_time_seconds': None,
                'average_percentage_watched': None,
                'reactions': summary.get('reactions'),
                'comments': summary.get('comments'),
                'shares': summary.get('shares'),
                'clicks': None,
                'watch_time_seconds': summary.get('seconds_viewed'),
                'largest_dropoff_seconds': None,
                'qualified_inquiries': None,
            },
            'panel_status': {'csv_period': True},
            'evidence_file': raw_inputs.get('csv_source_file'),
            'evidence_hash': csv_hash,
        })

    return {
        'manifest_id': manifest.get('run_id'),
        'observations': observations,
        'gaps': dedupe_gaps(gaps),
    }


def select_comparable(
    observations: List[Dict[str, Any]],
    placements: List[Dict[str, Any]],
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Partition eligible and descriptive-only observations under the policy."""
    pol = dict(DEFAULT_POLICY)
    if policy:
        pol.update(policy)

    placement_by_id = {p['id']: p for p in placements}
    eligible = []
    descriptive = []
    gaps = []

    for obs in observations:
        placement_id = obs.get('placement_id')
        placement = placement_by_id.get(placement_id)

        if not placement:
            descriptive.append({**obs, 'exclusion_reason': 'unmatched_placement'})
            continue

        visibility = placement.get('visibility', 'unknown')
        if visibility != 'visible':
            descriptive.append({
                **obs,
                'exclusion_reason': f"placement_{visibility}",
                'detail': f"Placement status is {visibility}, not visible."
            })
            if visibility == 'pending':
                gaps.append({
                    'kind': 'pending_approval',
                    'placement_id': placement_id,
                    'detail': 'Group post is pending moderation; cannot evaluate performance.'
                })
            continue

        checkpoint = obs.get('checkpoint')
        age_hours = obs.get('actual_age_hours')

        if checkpoint in ('24h', '7d'):
            target_hours = 24.0 if checkpoint == '24h' else 168.0
            max_over = pol.get('matched_age_max_over_hours', 2.0)

            if age_hours is None:
                descriptive.append({
                    **obs,
                    'exclusion_reason': 'unknown_age',
                    'detail': 'Snapshot lacks calculated age_hours.'
                })
            elif age_hours < target_hours:
                descriptive.append({
                    **obs,
                    'exclusion_reason': 'premature_capture',
                    'detail': f"Observed at {age_hours}h; checkpoint requires at least {target_hours}h."
                })
            elif age_hours > target_hours + max_over:
                descriptive.append({
                    **obs,
                    'exclusion_reason': 'mismatched_age',
                    'detail': f"Observed at {age_hours}h; exceeds {target_hours}h + {max_over}h tolerance window."
                })
            else:
                eligible.append(obs)
        else:
            # Observation without standard checkpoint is descriptive
            descriptive.append({
                **obs,
                'exclusion_reason': 'non_standard_checkpoint',
                'detail': f"Checkpoint '{checkpoint}' is descriptive."
            })

    return {
        'eligible': eligible,
        'descriptive': descriptive,
        'gaps': dedupe_gaps(gaps),
    }


def compare_content(
    selected: Dict[str, Any],
    hypotheses: Optional[Dict[str, Any]] = None,
    actions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compare eligible original Page placements across creative hypotheses."""
    eligible = selected.get('eligible', [])
    page_obs = [obs for obs in eligible if obs.get('source') == 'facebook_insights_dashboard']

    actions = actions or []
    actions_by_pub: Dict[str, List[Dict[str, Any]]] = {}
    for act in actions:
        pub_id = act.get('publication_id')
        if pub_id:
            actions_by_pub.setdefault(pub_id, []).append(act)

    comparisons = []
    flags = []

    for obs in page_obs:
        pub_id = obs.get('publication_id')
        pub_actions = actions_by_pub.get(pub_id, [])
        qualified = [a for a in pub_actions if a.get('status') == 'qualified']
        has_action_coverage = len(pub_actions) > 0

        m = obs.get('metrics', {})
        avg_pct = m.get('average_percentage_watched')
        avg_seconds = m.get('average_watch_time_seconds')

        row = {
            'publication_id': pub_id,
            'placement_id': obs.get('placement_id'),
            'checkpoint': obs.get('checkpoint'),
            'actual_age_hours': obs.get('actual_age_hours'),
            'views': m.get('views'),
            'viewers': m.get('viewers'),
            'three_second_views': m.get('three_second_views'),
            'average_watch_time_seconds': avg_seconds,
            'average_percentage_watched': avg_pct,
            'reactions': m.get('reactions'),
            'comments': m.get('comments'),
            'shares': m.get('shares'),
            'qualified_inquiries': len(qualified) if has_action_coverage else None,
            'action_coverage': has_action_coverage,
        }
        comparisons.append(row)

        if avg_pct is not None:
            flags.append({
                'publication_id': pub_id,
                'type': 'guardrail',
                'message': 'Average percentage watched is not completion rate; do not treat it as full viewers.'
            })

        if not has_action_coverage:
            flags.append({
                'publication_id': pub_id,
                'type': 'missing_outcome',
                'message': 'Buyer actions/qualified inquiries are unknown (null, not zero).'
            })

    return {
        'creative_matrix': comparisons,
        'descriptive_observations': selected.get('descriptive', []),
        'flags': flags,
        'limits': [
            'Duration and distribution must be controlled before declaring an opening winner.',
            'Unknown buyer outcomes prevent sales rankings.',
        ],
    }


def compare_groups(
    selected: Dict[str, Any],
    actions: Optional[List[Dict[str, Any]]] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Rank visible copies of identical creative within common eligible rounds."""
    pol = dict(DEFAULT_POLICY)
    if policy:
        pol.update(policy)

    eligible = selected.get('eligible', [])
    group_obs = [obs for obs in eligible if obs.get('source') == 'content_library']

    actions = actions or []
    actions_by_placement: Dict[str, List[Dict[str, Any]]] = {}
    for act in actions:
        pl_id = act.get('placement_id')
        if pl_id:
            actions_by_placement.setdefault(pl_id, []).append(act)

    by_creative: Dict[str, List[Dict[str, Any]]] = {}
    for obs in group_obs:
        pub_id = obs.get('publication_id', 'unknown')
        by_creative.setdefault(pub_id, []).append(obs)

    group_matrix = []
    diagnostic_flags = []

    for creative_id, placements in by_creative.items():
        rows = []
        has_any_inquiry_data = False

        for obs in placements:
            pl_id = obs.get('placement_id')
            pl_actions = actions_by_placement.get(pl_id, [])
            qualified = [a for a in pl_actions if a.get('status') == 'qualified']
            has_coverage = len(pl_actions) > 0
            if has_coverage:
                has_any_inquiry_data = True

            m = obs.get('metrics', {})
            rows.append({
                'placement_id': pl_id,
                'publication_id': creative_id,
                'views': m.get('views'),
                'viewers': m.get('viewers'),
                'reactions': m.get('reactions'),
                'shares': m.get('shares'),
                'qualified_inquiries': len(qualified) if has_coverage else None,
                'inquiry_coverage': has_coverage,
            })

        # Sorting: inquiries if comparable, else distribution-only (viewers -> views)
        if has_any_inquiry_data:
            rank_basis = 'qualified_inquiries'
            rows.sort(key=lambda r: (r.get('qualified_inquiries') or -1, r.get('viewers') or -1, r.get('views') or -1), reverse=True)
        else:
            rank_basis = 'distribution_only'
            rows.sort(key=lambda r: (r.get('viewers') or -1, r.get('views') or -1), reverse=True)

        for rank, row in enumerate(rows, start=1):
            row['rank'] = rank
            row['rank_basis'] = rank_basis

        group_matrix.extend(rows)

        diagnostic_flags.append({
            'creative_id': creative_id,
            'message': 'Group viewers must never be pooled across groups as unique audience reach.'
        })

    return {
        'group_matrix': group_matrix,
        'exclusions': selected.get('descriptive', []),
        'diagnostic_flags': diagnostic_flags,
    }


def build_review_bundle(
    comparison: Dict[str, Any],
    hypotheses: Optional[Dict[str, Any]] = None,
    policies: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble structured bundle for agent review and proposal generation."""
    pol = policies or DEFAULT_POLICY
    gaps = comparison.get('gaps', [])
    content_matrix = comparison.get('content_comparison', {}).get('creative_matrix', [])
    content_descriptive = comparison.get('content_comparison', {}).get('descriptive_observations', [])
    group_matrix = comparison.get('group_comparison', {}).get('group_matrix', [])
    group_exclusions = comparison.get('group_comparison', {}).get('exclusions', [])
    descriptive_all = content_descriptive or group_exclusions or comparison.get('descriptive', [])

    return {
        'run_id': comparison.get('run_id'),
        'created_at': _iso_now(),
        'policy': pol,
        'summary': {
            'eligible_content_items': len(content_matrix),
            'descriptive_content_items': len(content_descriptive),
            'eligible_group_items': len(group_matrix),
            'open_gap_count': len(gaps),
        },
        'content_comparison': content_matrix,
        'descriptive_observations': descriptive_all,
        'group_comparison': group_matrix,
        'gaps': gaps,
        'hypotheses_reference': hypotheses or {},
        'review_guidelines': [
            'Identify the weakest supported step: distribution, opening attention, relevance, CTA, or follow-up.',
            'Propose one-variable creative tests separately from group allocation adjustments.',
            'Each suggestion must cite specific evidence IDs, expected outcomes, controls, and measurement window.',
            'Do not declare an unsupported conversion winner when inquiries are null.',
        ],
        'pending_agent_review': True,
    }
