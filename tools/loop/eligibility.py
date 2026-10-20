"""Stage 5: decide which observations are comparable.

Ineligible evidence stays visible as descriptive observations with a reason.
"""

from tools.loop import storage


DEFAULT_POLICY = {
    'matched_age_max_over_hours': 2.0,
    'matched_age_max_diff_hours': 2.0,
    'group_review_min_rounds': 3,
}


def select_comparable(observations, placements, policy=None):
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
        'gaps': storage.dedupe_gaps(gaps),
    }
