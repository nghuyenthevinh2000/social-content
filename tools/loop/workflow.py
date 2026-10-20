"""Workflow orchestration, run state and the project-level status projection.

Stages are called in order; this module owns frozen runs, resume, completion and
``<project>/loop/status.json``. Stage logic lives in the stage modules.
"""

import json
from pathlib import Path
import subprocess
import uuid

from tools.loop import (
    approval,
    checkpoints,
    collect,
    compare_groups,
    compare_posts,
    eligibility,
    normalize,
    review,
    storage,
)


STATUS_SCHEMA_VERSION = 3
STAGE_ORDER = [
    'register', 'checkpoints', 'collect', 'normalize', 'eligibility',
    'compare_posts', 'compare_groups', 'review', 'approval',
]
COLLECT_STEPS = ('content_library', 'csv_export', 'csv_import', 'post_insights')


# --------------------------------------------------------------------------- #
# Status projection
# --------------------------------------------------------------------------- #

_UNSET = object()


def _empty_status():
    return {
        'schema_version': STATUS_SCHEMA_VERSION,
        'run_id': None,
        'updated_at': storage.now().isoformat(),
        'current_stage': None,
        'current_step': None,
        'state': 'idle',
        'stages': {},
        'comparison_result': None,
        'reason': None,
        'error': None,
        'next_action': None,
        'artifacts': {},
        'pending_run_ids': [],
    }


def _stage_entry(state, reason=None, *, started_at=_UNSET, ended_at=_UNSET):
    now = storage.now().isoformat()
    if started_at is _UNSET:
        started_at = now
    if ended_at is _UNSET:
        ended_at = None if state in ('running', 'waiting') else now
    return {
        'state': state,
        'started_at': started_at,
        'ended_at': ended_at,
        'reason': reason,
    }


def _saved_stage(history, stage, state, reason=None):
    """Use recorded transition times; leave unknown times null rather than invented."""
    saved = history.get(stage)
    if saved:
        return {
            'state': saved.get('state') or state,
            'started_at': saved.get('started_at'),
            'ended_at': saved.get('ended_at'),
            'reason': saved.get('reason') or reason,
        }
    return _stage_entry(state, reason, started_at=None, ended_at=None)


def run_artifacts(root, run_id):
    """Project-relative links for a run, only for files that exist."""
    if not run_id:
        return {}
    root = Path(root).resolve()
    run_dir = root / 'loop/runs' / run_id
    candidates = {
        'manifest': run_dir / 'manifest.json',
        'raw_evidence': root / 'sources/post-metrics/captures' / run_id,
        'normalized': root / 'sources/post-metrics/normalized' / f"{run_id}.json",
        'comparison': run_dir / 'comparison.json',
        'review_bundle': run_dir / 'review-bundle.json',
        'review': run_dir / 'review.json',
        'review_markdown': run_dir / 'review.md',
    }
    return {key: str(path.relative_to(root)) for key, path in candidates.items()
            if path.exists()}


class StatusWriter:
    """Only writer of ``loop/status.json``.

    Every ``begin``/``step``/``finish`` call is atomic. ``begin`` raises on write
    failure so callers do not start a stage without a persisted transition.
    """

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root / 'loop/status.json'
        self.run_id = None
        self.history = {}

    def read(self):
        if not self.path.is_file():
            return _empty_status()
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return _empty_status()
        status = _empty_status()
        status.update(data)
        if not isinstance(status.get('stages'), dict):
            status['stages'] = {}
        if not isinstance(status.get('pending_run_ids'), list):
            status['pending_run_ids'] = []
        return status

    def _write(self, status):
        status['schema_version'] = STATUS_SCHEMA_VERSION
        status['updated_at'] = storage.now().isoformat()
        storage.save(self.path, status)
        return status

    def _persist_stage(self, stage, entry):
        """Mirror stage transitions into the run manifest so they survive rebuilds."""
        if not stage:
            return
        record = {key: entry.get(key) for key in ('state', 'started_at', 'ended_at', 'reason')}
        self.history[stage] = record
        if not self.run_id:
            return
        manifest_path = self.root / 'loop/runs' / self.run_id / 'manifest.json'
        if not manifest_path.is_file():
            return
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            return
        history = manifest.setdefault('stage_history', {})
        history.update(self.history)
        storage.save(manifest_path, manifest)

    def begin(self, stage, *, run_id=None, step=None):
        """Persist a running stage before doing any of its work."""
        status = self.read()
        if run_id is not None:
            self.run_id = run_id
            status['run_id'] = run_id
        status.update(current_stage=stage, current_step=step, state='running',
                      reason=None, error=None, next_action=None)
        entry = _stage_entry('running')
        status['stages'][stage] = entry
        self._write(status)
        self._persist_stage(stage, entry)
        return status

    def step(self, stage, step):
        """Report a collection substep without restarting the stage."""
        status = self.read()
        status.update(current_stage=stage, current_step=step)
        if status.get('state') == 'idle':
            status['state'] = 'running'
        entry = status['stages'].setdefault(stage, _stage_entry('running'))
        if entry.get('state') != 'running':
            entry.update(_stage_entry('running'))
        self._write(status)
        self._persist_stage(stage, entry)
        return status

    def finish(self, stage, *, state='completed', stage_state=None, step=None, reason=None,
               error=None, next_action=None, run_id=None, artifacts=None, pending_run_ids=None,
               comparison_result=None):
        """Persist a stage outcome; state is the overall projection state."""
        status = self.read()
        if run_id is not None:
            self.run_id = run_id
            status['run_id'] = run_id
        entry = status['stages'].get(stage) or _stage_entry('running')
        entry['state'] = stage_state or state
        entry['ended_at'] = (None if entry['state'] in ('running', 'waiting')
                             else storage.now().isoformat())
        entry['reason'] = reason
        status['stages'][stage] = entry
        status.update(current_stage=stage, current_step=step, state=state,
                      reason=reason, error=error, next_action=next_action)
        if artifacts is not None:
            status['artifacts'] = artifacts
        if pending_run_ids is not None:
            status['pending_run_ids'] = pending_run_ids
        if comparison_result is not None:
            status['comparison_result'] = comparison_result
        self._write(status)
        self._persist_stage(stage, entry)
        return status

    def close_stage(self, stage, state, reason=None):
        """Record a stage outcome without changing the overall projection state."""
        status = self.read()
        entry = status['stages'].get(stage) or _stage_entry('running')
        entry['state'] = state
        entry['ended_at'] = None if state in ('running', 'waiting') else storage.now().isoformat()
        entry['reason'] = reason
        status['stages'][stage] = entry
        self._write(status)
        self._persist_stage(stage, entry)
        return status

    def recover_interrupted(self):
        """Turn a saved running state from an exited invocation into interrupted."""
        status = self.read()
        if status.get('state') != 'running':
            return status
        run_id = status.get('run_id')
        stage = status.get('current_stage')
        entry = status['stages'].get(stage) if stage else None
        if entry and entry.get('state') == 'running':
            entry['state'] = 'failed'
            entry['ended_at'] = storage.now().isoformat()
            entry['reason'] = 'Invocation exited while this stage was running.'
        status['state'] = 'interrupted'
        status['reason'] = (
            f"The previous invocation exited while stage '{stage}' was running; "
            "completion is unknown and the external action must not be retried blindly."
        )
        status['next_action'] = (
            f"Inspect the run, then resume: python -m tools.loop --project <project> "
            f"cycle --resume {run_id}"
            if run_id else "Inspect the project state before running another cycle."
        )
        self._write(status)
        if entry:
            self.run_id = run_id
            self._persist_stage(stage, entry)
        return status


def _failed_collect_step(manifest):
    """Best-effort collector substep from saved gaps and collector status."""
    failed = [key for key, value in manifest.get('collector_status', {}).items()
              if value == 'failed']
    gap_kinds = {gap.get('kind') for gap in manifest.get('gaps', [])}
    if 'content_library' in failed or gap_kinds & {
            'content_library_failed', 'content_library_error',
            'content_library_page_mismatch', 'content_library_empty',
            'content_library_unidentified', 'content_library_traversal_incomplete'}:
        return 'content_library'
    if 'csv_export' in failed or gap_kinds & {
            'csv_export_failed', 'csv_export_error', 'csv_evidence_unusable'}:
        return 'csv_import' if 'csv_import_failed' in gap_kinds else 'csv_export'
    if gap_kinds & {'post_insights_failed', 'post_insights_error', 'post_insights_unusable'}:
        return 'post_insights'
    return None


def _projection_from_manifest(root, run_id, manifest, pending=None):
    """Rebuild a missing/stale status projection from authoritative run state."""
    status = _empty_status()
    status['run_id'] = run_id
    status['artifacts'] = run_artifacts(root, run_id)
    pending = pending or {}
    open_ids = [item['run_id'] for item in pending.get('open_runs', []) if item['run_id'] != run_id]
    status['pending_run_ids'] = open_ids

    history = manifest.get('stage_history', {}) or {}
    run_status = manifest.get('status')
    failed_step = _failed_collect_step(manifest)
    comparison_path = Path(root) / 'loop/runs' / run_id / 'comparison.json'
    if comparison_path.is_file():
        try:
            artifact = json.loads(comparison_path.read_text())
            status['comparison_result'] = review.summarize_comparison(artifact)
        except (OSError, ValueError):
            status['comparison_result'] = None

    def complete(*stages):
        for stage in stages:
            status['stages'][stage] = _saved_stage(
                history, stage, 'completed', 'Rebuilt from saved run state.')

    def waiting(stage, reason):
        status['stages'][stage] = _saved_stage(history, stage, 'waiting', reason)

    def close_comparison():
        outcome = status.get('comparison_result') or {}
        if outcome.get('result') == 'not_comparable':
            status['stages']['compare_groups'] = _saved_stage(
                history, 'compare_groups', 'waiting',
                outcome.get('reason') or 'No eligible observations; no leaderboard is implied.')
        else:
            status['stages']['compare_groups'] = _saved_stage(
                history, 'compare_groups', 'completed', 'Rebuilt from saved run state.')

    if run_status in ('collection_incomplete', 'partial_collection_pending_review'):
        complete('checkpoints')
        status['stages']['collect'] = _saved_stage(
            history, 'collect', 'failed', 'Collection did not complete.')
        status['current_stage'] = 'collect'
        status['current_step'] = failed_step or 'content_library'
        status['state'] = 'failed'
        status['reason'] = 'Collection did not complete; saved evidence is preserved.'
        status['next_action'] = (
            f"Repair the failed {status['current_step']} collector, then resume: "
            f"python -m tools.loop --project <project> cycle --resume {run_id}"
        )
        if status['artifacts'].get('comparison'):
            complete('normalize', 'eligibility', 'compare_posts')
            close_comparison()
        if status['artifacts'].get('review_bundle'):
            waiting('review', 'Review bundle is available.')
    elif run_status == 'pending_agent_review':
        complete('checkpoints', 'collect', 'normalize', 'eligibility', 'compare_posts')
        close_comparison()
        waiting('review', 'Review bundle is available.')
        status['current_stage'] = 'review'
        status['state'] = 'waiting'
        status['reason'] = 'Waiting for agent review.'
        status['next_action'] = (
            f"Record the agent review: python -m tools.loop --project <project> "
            f"review --run {run_id} --file REVIEW.json"
        )
    elif run_status == 'in_progress':
        # A saved in-progress manifest may have stopped anywhere; never infer completion.
        status['state'] = 'interrupted'
        status['reason'] = 'The run was left in progress when its invocation exited.'
        status['next_action'] = (
            f"Inspect the run, then resume: python -m tools.loop --project <project> "
            f"cycle --resume {run_id}"
        )
    elif run_status == 'review_proposed':
        complete('checkpoints', 'collect', 'normalize', 'eligibility',
                 'compare_posts', 'review')
        close_comparison()
        waiting('approval', 'Proposal recorded.')
        status['current_stage'] = 'approval'
        status['state'] = 'waiting'
        status['reason'] = 'A review proposal is recorded and awaits an explicit human decision.'
        status['next_action'] = (
            f"Decide on the proposal: python -m tools.loop --project <project> "
            f"approve-review --run {run_id} [--proposals IDS]"
        )
    elif run_status == 'review_approved':
        complete('checkpoints', 'collect', 'normalize', 'eligibility',
                 'compare_posts', 'review', 'approval')
        close_comparison()
        status['current_stage'] = 'approval'
        status['state'] = 'completed'
        status['reason'] = 'Human approval recorded; execution remains outside this workflow.'
    elif run_status == 'no_work':
        complete('checkpoints')
        if pending.get('open_runs') or pending.get('pending_reviews'):
            status['state'] = 'waiting'
            status['reason'] = 'No due checkpoints, but collection or review work remains.'
        else:
            status['state'] = 'idle'
            status['reason'] = 'No due checkpoints and no pending work.'
    else:
        status['state'] = 'idle'
        status['reason'] = 'No recognized run state; inspect the run manifest.'
        status['next_action'] = 'Inspect the project before another cycle.'
    return status


def rebuild_if_missing(root, state=None):
    """Rebuild a missing or stale projection from the newest actionable run."""
    writer = StatusWriter(root)
    if writer.path.is_file():
        current = writer.read()
        run_id = current.get('run_id')
        up_to_date = current.get('schema_version') == STATUS_SCHEMA_VERSION
        comparison_path = (Path(root) / 'loop/runs' / run_id / 'comparison.json'
                           if run_id else None)
        missing_outcome = (comparison_path is not None and comparison_path.is_file()
                           and current.get('comparison_result') is None)
        if (up_to_date and not missing_outcome
                and (not run_id or (Path(root) / 'loop/runs' / run_id / 'manifest.json').is_file())):
            return current

    runs = sorted((Path(root) / 'loop/runs').glob('*/manifest.json'),
                  key=lambda path: path.stat().st_mtime, reverse=True)
    pending = pending_work(root, state) if state is not None else {}
    for manifest_path in runs:
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            continue
        if manifest.get('status') == 'no_work' and pending.get('open_runs'):
            continue
        projection = _projection_from_manifest(root, manifest_path.parent.name, manifest, pending)
        return writer._write(projection)
    projection = _empty_status()
    projection['stages']['checkpoints'] = _stage_entry('completed')
    projection['reason'] = 'No runs recorded yet.'
    return writer._write(projection)


def report_no_work(writer, pending, run_id=None):
    """Report idle only when no collection or review/approval work remains."""
    open_runs = pending.get('open_runs') or []
    if open_runs:
        # Preserve the selected unfinished run's real stage instead of relabeling it.
        selected = open_runs[-1]
        manifest_path = Path(writer.root) / 'loop/runs' / selected['run_id'] / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        projection = _projection_from_manifest(writer.root, selected['run_id'], manifest, pending)
        projection['pending_run_ids'] = [item['run_id'] for item in open_runs
                                         if item['run_id'] != selected['run_id']]
        projection['reason'] = (
            f"No due checkpoints. Waiting runs remain: {selected['run_id']}"
            + (f" and {len(projection['pending_run_ids'])} other(s)."
               if projection['pending_run_ids'] else '.')
        )
        if not projection.get('next_action') and pending.get('pending_review_count'):
            projection['next_action'] = 'Record or close the pending reviews listed by status.'
        return writer._write(projection)

    if pending.get('pending_review_count'):
        return writer.finish(
            'checkpoints', state='waiting', stage_state='completed', run_id=run_id,
            reason='No due checkpoints, but pending reviews remain.',
            next_action='Record or close the pending reviews listed by status.',
            artifacts=run_artifacts(writer.root, run_id),
            pending_run_ids=[],
        )
    return writer.finish(
        'checkpoints', state='idle', stage_state='completed', run_id=run_id,
        reason='No due checkpoints and no pending work.',
        next_action=None,
        artifacts=run_artifacts(writer.root, run_id),
        pending_run_ids=[],
    )


# --------------------------------------------------------------------------- #
# Pending work
# --------------------------------------------------------------------------- #

def open_runs(root):
    """Describe runs that still need a decision, without changing them."""
    root = Path(root).resolve()
    result = []
    for run_dir in sorted((root / 'loop/runs').glob('*/')):
        manifest_path = run_dir / 'manifest.json'
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            continue
        status = manifest.get('status')
        review_path = run_dir / 'review.json'
        review_status = None
        if review_path.is_file():
            try:
                review_status = json.loads(review_path.read_text()).get('status')
            except (OSError, ValueError):
                review_status = 'unreadable'
        failed = [key for key, value in manifest.get('collector_status', {}).items() if value == 'failed']
        actionable = (
            status in ('in_progress', 'collection_incomplete', 'partial_collection_pending_review', 'pending_agent_review')
            or failed
            or review_status == 'proposed'
        )
        if actionable:
            result.append({
                'run_id': run_dir.name,
                'status': status,
                'review_status': review_status,
                'failed_collectors': failed,
                'gap_count': len(manifest.get('gaps', [])),
            })
    return result


def pending_work(root, state):
    """Surface reviews and failed runs even when no checkpoint is due."""
    root = Path(root).resolve()
    pending_reviews = []
    represented = {str(item.get('publication_id')) for item in state.get('placements', [])}
    for placement in state.get('placements', []):
        for name, checkpoint in placement.get('checkpoints', {}).items():
            if checkpoint.get('review_status') == 'pending':
                pending_reviews.append({
                    'kind': 'placement_checkpoint',
                    'placement_id': placement.get('id'),
                    'publication_id': placement.get('publication_id'),
                    'checkpoint': name,
                    'checkpoint_status': checkpoint.get('status'),
                    'observation_ref': checkpoint.get('selected_observation_ref'),
                })
    for publication in state.get('publications', []):
        if str(publication.get('id')) in represented:
            continue
        if publication.get('review_status') == 'pending':
            pending_reviews.append({
                'kind': 'publication',
                'publication_id': publication.get('id'),
                'checkpoint': '24h',
                'checkpoint_status': publication.get('metrics_status'),
                'observation_ref': publication.get('receipt_file'),
            })
    runs = open_runs(root)
    return {
        'pending_reviews': pending_reviews,
        'open_runs': runs,
        'pending_review_count': len(pending_reviews),
        'open_run_count': len(runs),
    }


# --------------------------------------------------------------------------- #
# Run-level commands
# --------------------------------------------------------------------------- #

def _review_action(run_id):
    return (f"Record the agent review: python -m tools.loop --project <project> "
            f"review --run {run_id} --file REVIEW.json")


def _approval_action(run_id):
    return (f"Decide on the proposal: python -m tools.loop --project <project> "
            f"approve-review --run {run_id} [--proposals IDS]")


def _repair_action(run_id, step):
    return (f"Repair the failed {step} collector, then resume: "
            f"python -m tools.loop --project <project> cycle --resume {run_id}")


def comparison_summary(selected, content, groups):
    """State whether the comparison supports a usable ranked result."""
    eligible = selected.get('eligible', [])
    descriptive = selected.get('descriptive', [])
    reasons = {}
    for item in descriptive:
        reason = item.get('exclusion_reason') or 'unspecified_exclusion'
        reasons[reason] = reasons.get(reason, 0) + 1
    content_count = len(content.get('creative_matrix', []))
    group_count = len(groups.get('group_matrix', []))
    comparable = bool(content_count or group_count)
    if comparable:
        reason = (f"{content_count} content row(s) and {group_count} group row(s) "
                  "are eligible for comparison.")
    elif descriptive:
        detail = ', '.join(f'{key}={count}' for key, count in sorted(reasons.items()))
        reason = (f"No eligible observations; {len(descriptive)} descriptive observation(s) "
                  f"were excluded ({detail}). No leaderboard is implied.")
    else:
        reason = 'No observations were available for comparison.'
    return {
        'result': 'comparable' if comparable else 'not_comparable',
        'reason': reason,
        'eligible_observations': len(eligible),
        'descriptive_observations': len(descriptive),
        'eligible_content_items': content_count,
        'eligible_group_items': group_count,
        'exclusion_reasons': reasons,
    }


def compare_run(root, run_id):
    """Recompute deterministic comparisons for a run; never collects."""
    root = Path(root).resolve()
    run_dir, manifest = storage.load_run(root, run_id)
    normalized_path = root / 'sources/post-metrics/normalized' / f"{run_id}.json"
    if not normalized_path.is_file():
        raise ValueError(f"Run '{run_id}' has no normalized observations; run cycle before compare.")
    normalized = json.loads(normalized_path.read_text())
    state = json.loads((root / 'loop/publications.json').read_text())
    actions = storage.load_actions(root)

    writer = StatusWriter(root)
    stage = 'eligibility'
    writer.begin(stage, run_id=run_id)
    try:
        selected = eligibility.select_comparable(
            normalized.get('observations', []), state.get('placements', []))
        writer.finish('eligibility', state='completed', run_id=run_id,
                      artifacts=run_artifacts(root, run_id))
        stage = 'compare_posts'
        writer.begin(stage, run_id=run_id)
        content = compare_posts.compare_content(selected, actions=actions)
        writer.finish('compare_posts', state='completed', run_id=run_id,
                      artifacts=run_artifacts(root, run_id))
        stage = 'compare_groups'
        writer.begin(stage, run_id=run_id)
        groups = compare_groups.compare_groups(selected, actions=actions)
    except Exception as exc:
        writer.finish(stage, state='failed', run_id=run_id,
                      reason=f'Comparison failed in {stage}.',
                      error={'stage': stage, 'detail': str(exc)},
                      next_action=f"Inspect the failure, then rerun compare --run {run_id}.",
                      artifacts=run_artifacts(root, run_id))
        raise

    summary = comparison_summary(selected, content, groups)
    gaps = storage.dedupe_gaps(
        list(manifest.get('gaps', [])) + list(normalized.get('gaps', [])) + list(selected.get('gaps', []))
    )
    artifact = {
        'run_id': run_id,
        'content_comparison': content,
        'group_comparison': groups,
        'comparison_summary': summary,
        'gaps': gaps,
    }
    storage.save(run_dir / 'comparison.json', artifact)
    writer.finish('compare_groups',
                  state='waiting' if summary['result'] == 'not_comparable' else 'completed',
                  stage_state='waiting' if summary['result'] == 'not_comparable' else 'completed',
                  run_id=run_id,
                  reason=summary['reason'],
                  next_action=(f"Prepare the review bundle: python -m tools.loop "
                               f"--project <project> prepare-review --run {run_id}"),
                  artifacts=run_artifacts(root, run_id),
                  comparison_result=summary)
    return {
        'run_id': run_id,
        'status': 'compared',
        'comparison_result': summary['result'],
        'comparison_file': str((run_dir / 'comparison.json').relative_to(root)),
        'eligible_content_items': summary['eligible_content_items'],
        'eligible_group_items': summary['eligible_group_items'],
        'descriptive_observations': summary['descriptive_observations'],
        'gap_count': len(gaps),
        'exit_code': 0,
    }


def prepare_review_run(root, run_id):
    """Prepare a review bundle and report the human/agent handoff."""
    root = Path(root).resolve()
    writer = StatusWriter(root)
    writer.begin('review', run_id=run_id)
    try:
        result = review.prepare_review(root, run_id)
    except Exception as exc:
        writer.finish('review', state='failed', run_id=run_id,
                      reason='Review bundle preparation failed.',
                      error={'stage': 'review', 'detail': str(exc)},
                      next_action=f"Inspect the failure, then rerun prepare-review --run {run_id}.",
                      artifacts=run_artifacts(root, run_id))
        raise
    if not result.get('pending_agent_review'):
        writer.close_stage('review', 'completed',
                           'Existing review retained; evidence is unchanged.')
        if result.get('review_status') == 'approved':
            writer.finish('approval', state='completed', run_id=run_id,
                          reason='Human approval retained; execution remains outside this workflow.',
                          next_action=None,
                          artifacts=run_artifacts(root, run_id),
                          comparison_result=result.get('comparison_result'))
        else:
            writer.finish('approval', state='waiting', run_id=run_id,
                          reason='Recorded proposal retained; evidence is unchanged.',
                          next_action=_approval_action(run_id),
                          artifacts=run_artifacts(root, run_id),
                          comparison_result=result.get('comparison_result'))
        return result
    reason = ('Review bundle rebuilt after evidence changed; the earlier proposal is superseded.'
              if result.get('review_invalidated')
              else 'Review bundle prepared; waiting for agent review.')
    writer.finish('review', state='waiting', run_id=run_id,
                  reason=reason,
                  next_action=_review_action(run_id),
                  artifacts=run_artifacts(root, run_id),
                  comparison_result=result.get('comparison_result'))
    return result


def record_review_run(root, run_id, review_data):
    """Record a review proposal and report the approval handoff."""
    root = Path(root).resolve()
    writer = StatusWriter(root)
    writer.begin('review', run_id=run_id)
    try:
        result = review.record_run_review(root, run_id, review_data)
    except Exception as exc:
        writer.finish('review', state='failed', run_id=run_id,
                      reason='Recording the review failed.',
                      error={'stage': 'review', 'detail': str(exc)},
                      next_action=f"Inspect the failure, then record review --run {run_id} again.",
                      artifacts=run_artifacts(root, run_id))
        raise
    writer.finish('approval', state='waiting', run_id=run_id,
                  reason='Review proposal recorded; waiting for an explicit human decision.',
                  next_action=_approval_action(run_id),
                  artifacts=run_artifacts(root, run_id))
    status = writer.read()
    if status['stages'].get('review', {}).get('state') == 'running':
        writer.close_stage('review', 'completed', 'Review recorded.')
    return result


def approve_review_run(root, run_id, proposal_ids=None):
    """Record explicit approval and report the completed endpoint."""
    root = Path(root).resolve()
    writer = StatusWriter(root)
    writer.begin('approval', run_id=run_id)
    try:
        result = approval.approve_run_review(root, run_id, proposal_ids)
    except Exception as exc:
        writer.finish('approval', state='failed', run_id=run_id,
                      reason='Recording approval failed.',
                      error={'stage': 'approval', 'detail': str(exc)},
                      next_action=f"Inspect the failure, then approve-review --run {run_id}.",
                      artifacts=run_artifacts(root, run_id))
        raise
    writer.finish('approval', state='completed', run_id=run_id,
                  reason='Human approval recorded; execution remains outside this workflow.',
                  next_action=None,
                  artifacts=run_artifacts(root, run_id))
    return result


# --------------------------------------------------------------------------- #
# Cycle
# --------------------------------------------------------------------------- #

def cycle(root, *, dry_run=False, resume=None, runner=None):
    """Execute collection, normalization, comparison and review staging in order."""
    root = Path(root).resolve()
    config = storage.load_project(root)
    page_id = config['page_id']
    state_path = root / 'loop/publications.json'
    state = json.loads(state_path.read_text())

    at = storage.now()
    runner = runner or subprocess.run

    # 1. Resume validation or new run ID
    if resume:
        run_id = storage.validate_run_id(resume)
        run_dir = storage.run_directory(root, run_id)
        manifest_path = run_dir / 'manifest.json'
        if not manifest_path.exists():
            raise ValueError(f"Run '{resume}' does not exist; cannot resume.")
        manifest = json.loads(manifest_path.read_text())
        if manifest.get('page_id') != page_id:
            raise ValueError(f"Run '{resume}' was recorded for Page {manifest.get('page_id')}, not {page_id}.")
        due_work = manifest.get('due_work', [])
        manifest['status'] = 'in_progress'
        manifest.setdefault('collector_status', {})
        manifest.setdefault('evidence_files', [])
        manifest.setdefault('gaps', [])
        manifest.setdefault('warnings', [])
    else:
        run_id = at.strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        run_dir = storage.run_directory(root, run_id)
        manifest_path = run_dir / 'manifest.json'
        due_work = checkpoints.due_checkpoints(state, at)
        manifest = {
            'run_id': run_id,
            'started_at': at.isoformat(),
            'status': 'in_progress',
            'page_id': page_id,
            'due_work': due_work,
            'evidence_files': [],
            'collector_status': {},
            'warnings': [],
            'gaps': [],
        }

    # 2. Legitimately empty worklist (dry runs never write status or runs)
    if not due_work:
        pending = pending_work(root, state)
        if dry_run:
            return {
                'status': 'no_work',
                'dry_run': True,
                'page_id': page_id,
                'due_work_count': 0,
                'due_work': [],
                **pending,
                'exit_code': 0,
            }
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest['status'] = 'no_work'
        manifest['completed_at'] = storage.now().isoformat()
        manifest['pending_work'] = pending
        manifest['warnings'].append(
            'No placement checkpoints or publications are currently due. '
            f"Pending reviews: {pending['pending_review_count']}; open runs: {pending['open_run_count']}."
        )
        storage.save(manifest_path, manifest)
        writer = StatusWriter(root)
        if not pending.get('open_runs'):
            # Only this no-work run is selected; start its checkpoint transition.
            # Otherwise the older waiting run keeps its recorded history untouched.
            writer.begin('checkpoints', run_id=run_id)
        report_no_work(writer, pending, run_id)
        return {
            'status': 'no_work',
            'run_id': run_id,
            'due_work_count': 0,
            'message': 'No due checkpoints.',
            **pending,
            'exit_code': 0,
        }

    # 3. Dry-run preview
    if dry_run:
        return {
            'status': 'planned',
            'dry_run': True,
            'page_id': page_id,
            'due_work_count': len(due_work),
            'due_work': due_work,
            'planned_steps': [
                'discover_content_library',
                'export_summary_csv',
                'capture_insights',
                'normalize',
                'compare',
                'prepare_review',
            ],
            'exit_code': 0,
        }

    run_dir.mkdir(parents=True, exist_ok=True)
    storage.save(manifest_path, manifest)
    writer = StatusWriter(root)
    writer.begin('checkpoints', run_id=run_id)
    writer.finish('checkpoints', state='completed', run_id=run_id,
                  reason=('Resumed frozen due worklist.' if resume else 'Frozen due worklist.'),
                  artifacts=run_artifacts(root, run_id))

    # 4. Sequential collection
    collector = collect.Collector(
        root, run_id, page_id, state, manifest, manifest_path, runner)
    writer.begin('collect', run_id=run_id, step='content_library')
    collector.content_library()
    needs_csv = any(item.get('placement_kind') == 'original_page'
                    or item.get('kind') == 'publication' for item in due_work)
    if needs_csv:
        writer.step('collect', 'csv_export')
    collector.summary_csv(due_work)
    writer.step('collect', 'post_insights')
    collector.post_insights(due_work)
    raw_inputs = collector.raw_inputs

    # 5. Check for collection incomplete
    manifest['gaps'] = storage.dedupe_gaps(manifest.get('gaps', []))
    total_observations = (
        len(raw_inputs['insights_captures']) +
        len(raw_inputs['content_library_rows']) +
        len(raw_inputs['csv_posts'])
    )
    failure_step = collector.failures[0]['step'] if collector.failures else None
    if collector.failures:
        writer.finish(
            'collect', state='failed', run_id=run_id, step=failure_step,
            reason='One or more collectors failed; saved evidence is preserved.',
            error={'stage': 'collect', 'step': failure_step,
                   'detail': collector.failures[0]['detail']},
            next_action=_repair_action(run_id, failure_step),
            artifacts=run_artifacts(root, run_id),
        )
    else:
        writer.finish('collect', state='completed', run_id=run_id, step='post_insights',
                      artifacts=run_artifacts(root, run_id))

    if total_observations == 0:
        manifest['status'] = 'collection_incomplete'
        manifest['completed_at'] = storage.now().isoformat()
        manifest['warnings'].append('Due work existed but no usable evidence files could be collected or parsed.')
        storage.save(manifest_path, manifest)
        writer.finish(
            'collect', state='failed', run_id=run_id,
            step=failure_step or 'content_library',
            reason='No usable evidence could be collected or parsed.',
            error={'stage': 'collect', 'step': failure_step or 'content_library',
                   'detail': manifest['warnings'][-1]},
            next_action=_repair_action(run_id, failure_step or 'content_library'),
            artifacts=run_artifacts(root, run_id),
        )
        return {
            'status': 'collection_incomplete',
            'run_id': run_id,
            'due_work_count': len(due_work),
            'evidence_files_count': len(manifest.get('evidence_files', [])),
            'gaps': manifest.get('gaps', []),
            'exit_code': 1,
        }

    # 6. Normalize observations
    writer.begin('normalize', run_id=run_id)
    normalized = normalize.normalize_observations(
        manifest, raw_inputs, state.get('placements', []))
    norm_path = root / 'sources/post-metrics/normalized' / f"{run_id}.json"
    norm_path.parent.mkdir(parents=True, exist_ok=True)
    storage.save(norm_path, normalized)
    writer.finish('normalize', state='completed', run_id=run_id,
                  artifacts=run_artifacts(root, run_id))

    # 7. Select comparable observations and compare
    writer.begin('eligibility', run_id=run_id)
    selected = eligibility.select_comparable(
        normalized['observations'], state.get('placements', []))
    writer.finish('eligibility', state='completed', run_id=run_id,
                  artifacts=run_artifacts(root, run_id))

    actions = storage.load_actions(root)
    writer.begin('compare_posts', run_id=run_id)
    content_comp = compare_posts.compare_content(selected, actions=actions)
    writer.finish('compare_posts', state='completed', run_id=run_id,
                  artifacts=run_artifacts(root, run_id))
    writer.begin('compare_groups', run_id=run_id)
    group_comp = compare_groups.compare_groups(selected, actions=actions)

    summary = comparison_summary(selected, content_comp, group_comp)
    all_gaps = storage.dedupe_gaps(
        list(manifest.get('gaps', [])) + list(normalized.get('gaps', [])) + list(selected.get('gaps', []))
    )
    comp_artifact = {
        'run_id': run_id,
        'content_comparison': content_comp,
        'group_comparison': group_comp,
        'comparison_summary': summary,
        'gaps': all_gaps,
    }
    storage.save(run_dir / 'comparison.json', comp_artifact)
    writer.finish('compare_groups',
                  state='waiting' if summary['result'] == 'not_comparable' else 'completed',
                  run_id=run_id, reason=summary['reason'],
                  artifacts=run_artifacts(root, run_id),
                  comparison_result=summary)

    # 8. Checkpoint commit in publications.json; reuse never increments attempts.
    for cap in raw_inputs['insights_captures']:
        p_id = cap.get('placement_id')
        cp_name = cap.get('checkpoint', '24h')
        for pl in state.get('placements', []):
            if pl['id'] == p_id and cp_name in pl.get('checkpoints', {}):
                cp = pl['checkpoints'][cp_name]
                cp['status'] = 'collected'
                if not cap.get('reused'):
                    cp['attempts'] = cp.get('attempts', 0) + 1
                cp['selected_observation_ref'] = cap.get('evidence_file')
                if not cap.get('reused') or not cp.get('review_status'):
                    cp['review_status'] = 'pending'
        for pub in state.get('publications', []):
            if pub['id'] == cap.get('publication_id'):
                pub['metrics_status'] = 'collected'
                if not cap.get('reused') or not pub.get('review_status'):
                    pub['review_status'] = 'pending'
                pub['receipt_file'] = cap.get('evidence_file')
    storage.save(state_path, state)

    failed_collectors = [k for k, v in manifest.get('collector_status', {}).items() if v == 'failed']
    any_insights_failed = any(g.get('kind') in ('post_insights_failed', 'post_insights_error',
                                                'post_insights_unusable')
                              for g in manifest.get('gaps', []))
    is_partial = bool(failed_collectors or any_insights_failed)
    retained_review = (not is_partial
                       and manifest.get('review_status') in ('proposed', 'approved')
                       and not collector.changed)

    # 9. Build review bundle; an unchanged recorded review keeps its handoff stage.
    writer.begin('review', run_id=run_id)
    hypotheses = storage.load_hypotheses(root, config)
    bundle = review.build_review_bundle(
        comp_artifact, hypotheses=hypotheses,
        pending_agent_review=not retained_review,
        review_status=manifest.get('review_status') if retained_review else None)
    storage.save(run_dir / 'review-bundle.json', bundle)
    manifest['review_bundle_pending'] = not retained_review
    if retained_review:
        writer.close_stage('review', 'completed', 'Existing review retained; evidence is unchanged.')
    else:
        writer.close_stage('review', 'waiting', 'Review bundle prepared.')

    if is_partial:
        status_str = 'partial_collection_pending_review'
        exit_code = 1
        manifest['warnings'].append(f"Incomplete collection: collectors {failed_collectors or 'post_insights'} encountered errors; partial review available.")
    elif retained_review:
        # Re-staging identical evidence must not silently invalidate a recorded review.
        status_str = f"review_{manifest['review_status']}"
        exit_code = 0
    else:
        status_str = 'pending_agent_review'
        exit_code = 0

    manifest['status'] = status_str
    manifest['completed_at'] = storage.now().isoformat()
    manifest['gaps'] = all_gaps
    storage.save(manifest_path, manifest)

    pending = pending_work(root, state)
    others = [item['run_id'] for item in pending['open_runs'] if item['run_id'] != run_id]

    if is_partial:
        step = failure_step or ('post_insights' if any_insights_failed else 'content_library')
        writer.finish(
            'collect', state='failed', run_id=run_id, step=step,
            reason='Collection is partial; a review bundle is available but repair is still required.',
            error={'stage': 'collect', 'step': step,
                   'detail': 'One or more collectors failed; see gaps and collector_status.'},
            next_action=_repair_action(run_id, step),
            artifacts=run_artifacts(root, run_id),
            pending_run_ids=others,
        )
    elif status_str == 'review_proposed':
        writer.finish('approval', state='waiting', run_id=run_id,
                      reason='A review proposal is recorded and awaits an explicit human decision.',
                      next_action=_approval_action(run_id),
                      artifacts=run_artifacts(root, run_id),
                      pending_run_ids=others,
                      comparison_result=summary)
    elif status_str == 'review_approved':
        writer.finish('approval', state='completed', run_id=run_id,
                      reason='Human approval recorded; execution remains outside this workflow.',
                      next_action=None,
                      artifacts=run_artifacts(root, run_id),
                      pending_run_ids=others,
                      comparison_result=summary)
    else:
        writer.finish('review', state='waiting', run_id=run_id,
                      reason='Review bundle prepared; waiting for agent review.',
                      next_action=_review_action(run_id),
                      artifacts=run_artifacts(root, run_id),
                      pending_run_ids=others,
                      comparison_result=summary)

    return {
        'run_id': run_id,
        'status': status_str,
        'run_directory': str(run_dir.relative_to(root)),
        'comparison_result': summary['result'],
        'comparison': comp_artifact,
        'review_bundle': str((run_dir / 'review-bundle.json').relative_to(root)),
        'exit_code': exit_code,
    }
