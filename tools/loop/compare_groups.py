"""Stage 6b: compare the same creative across verified group copies.

Groups are ranked at matched visible ages; views ranking and buyer-outcome
ranking stay separate and ties are preserved.
"""

from tools.loop import eligibility


def compare_groups(selected, actions=None, policy=None):
    """Rank visible copies of identical creative within common eligible rounds."""
    pol = dict(eligibility.DEFAULT_POLICY)
    if policy:
        pol.update(policy)

    eligible = selected.get('eligible', [])
    group_obs = [obs for obs in eligible if obs.get('source') == 'content_library']

    actions = actions or []
    actions_by_placement = {}
    for act in actions:
        pl_id = act.get('placement_id')
        if pl_id:
            actions_by_placement.setdefault(pl_id, []).append(act)

    by_creative = {}
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
