"""Stage 7: prepare and record the agent's learning review.

Assembles evidence, comparisons, hypotheses and gaps. Recording a review is
not approval and does not repair collection.
"""

import json
from pathlib import Path

from tools.loop import eligibility, storage


def summarize_comparison(comparison):
    """Return the stored outcome, or derive one for artifacts written before it existed."""
    summary = comparison.get('comparison_summary')
    if summary:
        return summary
    content_matrix = comparison.get('content_comparison', {}).get('creative_matrix', [])
    content_descriptive = comparison.get('content_comparison', {}).get(
        'descriptive_observations', [])
    group_matrix = comparison.get('group_comparison', {}).get('group_matrix', [])
    group_exclusions = comparison.get('group_comparison', {}).get('exclusions', [])
    descriptive = content_descriptive or group_exclusions or comparison.get('descriptive', [])
    reasons = {}
    for item in descriptive:
        key = item.get('exclusion_reason') or 'unspecified_exclusion'
        reasons[key] = reasons.get(key, 0) + 1
    comparable = bool(content_matrix or group_matrix)
    if comparable:
        reason = (f"{len(content_matrix)} content row(s) and {len(group_matrix)} "
                  "group row(s) are eligible for comparison.")
    elif descriptive:
        detail = ', '.join(f'{key}={count}' for key, count in sorted(reasons.items()))
        reason = (f"No eligible observations; {len(descriptive)} descriptive "
                  f"observation(s) were excluded ({detail}). No leaderboard is implied.")
    else:
        reason = 'No observations were available for comparison.'
    return {
        'result': 'comparable' if comparable else 'not_comparable',
        'reason': reason,
        'eligible_observations': len(content_matrix) + len(group_matrix),
        'eligible_content_items': len(content_matrix),
        'eligible_group_items': len(group_matrix),
        'descriptive_observations': len(descriptive),
        'exclusion_reasons': reasons,
    }


def build_review_bundle(comparison, hypotheses=None, policies=None, *,
                        pending_agent_review=True, review_status=None):
    """Assemble structured bundle for agent review and proposal generation."""
    pol = policies or eligibility.DEFAULT_POLICY
    gaps = comparison.get('gaps', [])
    content_matrix = comparison.get('content_comparison', {}).get('creative_matrix', [])
    content_descriptive = comparison.get('content_comparison', {}).get('descriptive_observations', [])
    group_matrix = comparison.get('group_comparison', {}).get('group_matrix', [])
    group_exclusions = comparison.get('group_comparison', {}).get('exclusions', [])
    descriptive_all = content_descriptive or group_exclusions or comparison.get('descriptive', [])
    comparison_summary = summarize_comparison(comparison)

    return {
        'run_id': comparison.get('run_id'),
        'created_at': storage.now().isoformat(),
        'policy': pol,
        'comparison_result': comparison_summary.get('result', 'unknown'),
        'comparison_summary': comparison_summary,
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
        'pending_agent_review': pending_agent_review,
        'review_status': review_status,
    }


def _cited_ids(review_data):
    ids = set()
    for key in ('publication_id', 'placement_id'):
        if review_data.get(key):
            ids.add(str(review_data[key]))
    for value in review_data.get('evidence_ids', []) or []:
        ids.add(str(value))
    for value in review_data.get('evidence', []) or []:
        if isinstance(value, str):
            ids.add(value)
    return ids


def invalidate_review(root, manifest, review_record):
    """Supersede a review whose evidence revision no longer matches."""
    ids = _cited_ids(review_record)
    state_path = Path(root) / 'loop/publications.json'
    if state_path.is_file():
        state = json.loads(state_path.read_text())
        changed = False
        for placement in state.get('placements', []):
            if (str(placement.get('id')) in ids
                    or str(placement.get('publication_id')) in ids):
                for checkpoint in placement.get('checkpoints', {}).values():
                    if checkpoint.get('review_status') == 'reviewed':
                        checkpoint['review_status'] = 'pending'
                        changed = True
        for publication in state.get('publications', []):
            if (str(publication.get('id')) in ids
                    or str(publication.get('post_id')) in ids):
                if publication.get('review_status') == 'reviewed':
                    publication['review_status'] = 'pending'
                    changed = True
        if changed:
            storage.save(state_path, state)

    record = dict(review_record)
    record['status'] = 'superseded'
    record['superseded_at'] = storage.now().isoformat()
    record['superseded_reason'] = (
        'Collected evidence changed after the review was recorded; '
        'the earlier proposal is preserved but no longer current.'
    )
    run_dir, _ = storage.load_run(root, manifest['run_id'])
    reviewed_at = (record.get('reviewed_at') or 'unknown').replace(':', '').replace('+', 'Z')
    archive = run_dir / f"review.superseded-{reviewed_at}.json"
    storage.save(archive, record)
    storage.save(run_dir / 'review.json', record)
    return record


def prepare_review(root, run_id):
    """Rebuild the review bundle, retaining a review that still matches evidence."""
    root = Path(root).resolve()
    run_dir, manifest = storage.load_run(root, run_id)
    comparison_path = run_dir / 'comparison.json'
    if not comparison_path.is_file():
        raise ValueError(f"Run '{run_id}' has no comparison; run compare first.")
    artifact = json.loads(comparison_path.read_text())

    revision = storage.evidence_revision(manifest)
    review_path = run_dir / 'review.json'
    record = None
    if review_path.is_file():
        try:
            record = json.loads(review_path.read_text())
        except ValueError:
            record = None

    pending = True
    retained_status = None
    invalidated = False
    if record and record.get('status') in ('proposed', 'approved'):
        recorded_revision = record.get('evidence_revision')
        if recorded_revision is None:
            # Legacy review: adopt the current evidence set as its baseline.
            record['evidence_revision'] = revision
            storage.save(review_path, record)
            recorded_revision = revision
        if recorded_revision == revision:
            pending = False
            retained_status = record['status']
        else:
            record = invalidate_review(root, manifest, record)
            invalidated = True
            manifest['status'] = 'pending_agent_review'
            manifest['review_status'] = 'pending'
            manifest['review_invalidated_at'] = storage.now().isoformat()
            manifest['review_invalidated_reason'] = record['superseded_reason']

    config = storage.load_project(root)
    bundle = build_review_bundle(
        artifact,
        hypotheses=storage.load_hypotheses(root, config),
        pending_agent_review=pending,
        review_status=retained_status,
    )
    storage.save(run_dir / 'review-bundle.json', bundle)
    manifest['review_bundle'] = str((run_dir / 'review-bundle.json').relative_to(root))
    manifest['review_bundle_pending'] = pending
    storage.save(run_dir / 'manifest.json', manifest)
    return {
        'run_id': run_id,
        'status': 'review_prepared',
        'review_bundle': str((run_dir / 'review-bundle.json').relative_to(root)),
        'summary': bundle.get('summary', {}),
        'comparison_result': bundle.get('comparison_result'),
        'pending_agent_review': pending,
        'review_status': retained_status,
        'review_invalidated': invalidated,
        'exit_code': 0,
    }


def review(entry, finding):
    """Legacy review function on a single publication entry."""
    if entry.get('metrics_status') != 'collected':
        raise ValueError('Collect the due snapshot before reviewing.')
    for key in ('observation', 'limitation', 'next_test'):
        if not isinstance(finding.get(key), str) or not finding[key].strip():
            raise ValueError(f'Review needs a nonempty {key}.')
    entry.setdefault('reviews', []).append({
        **finding, 'reviewed_at': storage.now().isoformat(), 'run_url': entry.get('run_url'),
    })
    entry['review_status'] = 'reviewed'


def mark_reviewed(root, review_data):
    """Link a recorded review back to the placement/publication it cites."""
    state_path = Path(root) / 'loop/publications.json'
    if not state_path.is_file():
        return
    state = json.loads(state_path.read_text())
    ids = _cited_ids(review_data)
    changed = False
    for placement in state.get('placements', []):
        if str(placement.get('id')) in ids or str(placement.get('publication_id')) in ids:
            for checkpoint in placement.get('checkpoints', {}).values():
                if checkpoint.get('status') == 'collected':
                    checkpoint['review_status'] = 'reviewed'
                    changed = True
    for publication in state.get('publications', []):
        if str(publication.get('id')) in ids or str(publication.get('post_id')) in ids:
            publication['review_status'] = 'reviewed'
            changed = True
    if changed:
        storage.save(state_path, state)


def record_run_review(root, run_id, review_data):
    """Save structured proposals and human-readable review table for a run."""
    root = Path(root).resolve()
    run_dir, manifest = storage.load_run(root, run_id)

    for field in ('observation', 'limitation'):
        if not review_data.get(field):
            raise ValueError(f"Review requires nonempty '{field}'.")

    review_path = run_dir / 'review.json'
    review_record = {
        'run_id': run_id,
        'reviewed_at': storage.now().isoformat(),
        'status': 'proposed',
        'evidence_revision': storage.evidence_revision(manifest),
        **review_data,
    }
    storage.save(review_path, review_record)

    # A recorded review changes run state but never implies approval or repairs collection.
    manifest['status'] = 'review_proposed'
    manifest['review_status'] = 'proposed'
    manifest['review_file'] = str(review_path.relative_to(root))
    manifest['reviewed_at'] = review_record['reviewed_at']
    storage.save(run_dir / 'manifest.json', manifest)

    mark_reviewed(root, review_data)

    # Human-readable markdown
    md_lines = [
        f"# Review for Run `{run_id}`\n\n",
        f"| Field | Value |\n| --- | --- |\n",
        f"| Observation | {review_data.get('observation')} |\n",
        f"| Limitation | {review_data.get('limitation')} |\n",
        f"| Status | Proposed |\n\n",
        "## Suggestions\n\n",
        "| ID | Target | Change | Expected Outcome | Controls |\n| --- | --- | --- | --- | --- |\n",
    ]
    for s in review_data.get('suggestions', []):
        md_lines.append(f"| {s.get('id', '-')} | {s.get('target', '-')} | {s.get('change', '-')} | {s.get('expected_outcome', '-')} | {s.get('controls', '-')} |\n")

    (run_dir / 'review.md').write_text(''.join(md_lines))
    return review_record
