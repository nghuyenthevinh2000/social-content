"""Stage 8: record explicit human approval of selected proposals.

Approval does not publish, leave groups, delete posts or change allocation.
"""

import json
from pathlib import Path

from tools.loop import storage


def approve_run_review(root, run_id, proposal_ids=None):
    """Record explicit human approval for selected proposals in a run."""
    root = Path(root).resolve()
    run_dir, manifest = storage.load_run(root, run_id)
    review_path = run_dir / 'review.json'
    if not review_path.exists():
        raise ValueError(f"No review found for run {run_id}.")

    review_data = json.loads(review_path.read_text())
    review_data['status'] = 'approved'
    review_data['approved_at'] = storage.now().isoformat()
    review_data['approved_proposals'] = proposal_ids or [s.get('id') for s in review_data.get('suggestions', [])]
    storage.save(review_path, review_data)

    manifest['status'] = 'review_approved'
    manifest['review_status'] = 'approved'
    manifest['approved_at'] = review_data['approved_at']
    storage.save(run_dir / 'manifest.json', manifest)

    return review_data
