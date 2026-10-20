"""Stage 4: standardize captured evidence into scoped metric observations.

Preserves source timestamps, scope, identity references and null values.
Processing time is not observation time.
"""

from datetime import datetime, timezone
import hashlib
import uuid

from tools.loop import storage


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def normalize_observations(manifest, raw_inputs, placements=None):
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
        matched = placement_by_post.get(str(post_id)) if post_id else None
        summary = post.get('export_period_totals') or post.get('summary_metrics') or {}
        observations.append({
            'id': f"obs-csv-{post_id}",
            'placement_id': matched.get('id') if matched else post.get('placement_id'),
            'publication_id': matched.get('publication_id') if matched else post.get('publication_id'),
            'identity_source': ('page_post_id' if matched
                                else ('explicit' if post.get('placement_id') else 'unresolved')),
            'copy_post_id': post_id,
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
        'gaps': storage.dedupe_gaps(gaps),
    }
