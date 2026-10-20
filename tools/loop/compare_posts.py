"""Stage 6a: compare different posts' content outcomes.

Retains uncertainty; unmatched distribution is not creative causation.
"""


def compare_content(selected, hypotheses=None, actions=None):
    """Compare eligible original Page placements across creative hypotheses."""
    eligible = selected.get('eligible', [])
    page_obs = [obs for obs in eligible if obs.get('source') == 'facebook_insights_dashboard']

    actions = actions or []
    actions_by_pub = {}
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
