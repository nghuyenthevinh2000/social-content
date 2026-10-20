"""Command-line parsing and dispatch only; stage logic lives in stage modules."""

import argparse
import fcntl
import json
from pathlib import Path
import sys

from tools.loop import (
    checkpoints,
    collect,
    project_init,
    register,
    review,
    storage,
    workflow,
)


def _build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True, help='Project root containing its own loop/config.json and registry')
    commands = parser.add_subparsers(dest='command', required=True)

    init = commands.add_parser('init', help='Initialize project-owned configuration/state without overwriting existing files')
    init.add_argument('--page-id', required=True)
    init.add_argument('--hypotheses-file', help='Optional project-relative JSON with a hypotheses array')
    init.add_argument('--dry-run', action='store_true', help='Validate inputs without writing to disk')

    mig = commands.add_parser('migrate', help='Migrate publications.json to Schema v2 with byte backup')
    mig.add_argument('--dry-run', action='store_true', help='Preview migration without writing to disk')

    cyc = commands.add_parser('cycle', help='Run end-to-end collection, comparison and review bundle generation')
    cyc.add_argument('--dry-run', action='store_true', help='Preview due checkpoints and planned collectors without network calls')
    cyc.add_argument('--resume', help='Resume an unfinished run ID')

    cmp_cmd = commands.add_parser('compare', help='Recompute deterministic comparisons for a run')
    cmp_cmd.add_argument('--run', required=True, dest='run_id')

    prep = commands.add_parser('prepare-review', help='Prepare review bundle for a run')
    prep.add_argument('--run', required=True, dest='run_id')

    act = commands.add_parser('record-action', help='Append manual qualified inquiry or buyer action event')
    act.add_argument('--file', type=Path, required=True)

    apprv = commands.add_parser('approve-review', help='Record human approval for review proposals')
    apprv.add_argument('--run', required=True, dest='run_id')
    apprv.add_argument('--proposals', help='Comma-separated proposal IDs to approve')

    commands.add_parser('status')
    commands.add_parser('due')
    commands.add_parser('collect-insights', help='Read due post dashboards; no Glasser charges')

    add = commands.add_parser('register')
    add.add_argument('--post', type=int, required=True)
    add.add_argument('--url', required=True)
    add.add_argument('--published-at', default=None)

    fetch = commands.add_parser('collect')
    fetch.add_argument('--max-cost-usd', required=True,
                       help='Explicit total spend ceiling for this invocation, not a recurring approval.')

    learn = commands.add_parser('review')
    learn.add_argument('--id', help='Legacy publication ID')
    learn.add_argument('--run', dest='run_id', help='Run ID to attach review to')
    learn.add_argument('--file', type=Path, required=True)
    return parser


def _mark_failed(writer, exc):
    status = writer.read()
    stage = status.get('current_stage')
    if status.get('state') != 'running' or not stage:
        return
    writer.finish(
        stage, state='failed', step=status.get('current_step'),
        reason='Command failed before completing the stage.',
        error={'stage': stage, 'step': status.get('current_step'), 'detail': str(exc)},
        next_action='Inspect the recorded error; retry only when the external action is known to be safe.',
    )


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    root = args.project.expanduser().resolve()
    if args.command != 'init' and not (root / 'loop/config.json').is_file():
        parser.error('Project is not initialized; run --project PATH init --page-id ID first.')

    if args.command == 'init' and getattr(args, 'dry_run', False):
        print(json.dumps(project_init.bootstrap_project(
            root, args.page_id, hypotheses_file=args.hypotheses_file or 'posts/hypothesis.json',
            dry_run=True), indent=2))
        return

    (root / 'loop').mkdir(parents=True, exist_ok=True)
    state_path = root / 'loop/publications.json'

    with (root / 'loop/.engine.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        writer = workflow.StatusWriter(root)
        writer.recover_interrupted()

        if args.command == 'init':
            print(json.dumps(project_init.bootstrap_project(
                root, args.page_id,
                hypotheses_file=args.hypotheses_file or 'posts/hypothesis.json',
                dry_run=args.dry_run), indent=2))
            return
        if args.command == 'migrate':
            print(json.dumps(project_init.migrate(root, dry_run=args.dry_run), indent=2))
            return
        if args.command == 'cycle':
            result = workflow.cycle(root, dry_run=args.dry_run, resume=args.resume)
            print(json.dumps(result, indent=2))
            if result.get('exit_code', 0) != 0 or result.get('status') == 'collection_incomplete':
                sys.exit(1)
            return
        if args.command == 'compare':
            print(json.dumps(workflow.compare_run(root, args.run_id), indent=2))
            return
        if args.command == 'prepare-review':
            print(json.dumps(workflow.prepare_review_run(root, args.run_id), indent=2))
            return
        if args.command == 'record-action':
            event_data = json.loads(args.file.read_text())
            print(json.dumps(collect.record_action(root, event_data), indent=2))
            return
        if args.command == 'approve-review':
            proposals = [p.strip() for p in args.proposals.split(',')] if args.proposals else None
            print(json.dumps(workflow.approve_review_run(root, args.run_id, proposals), indent=2))
            return

        config = storage.load_project(root)
        state = json.loads(state_path.read_text())

        try:
            if args.command == 'register':
                if config.get('hypotheses_file'):
                    valid = {item['post'] for item in json.loads(
                        storage.project_file(root, config['hypotheses_file']).read_text())['hypotheses']}
                    if args.post not in valid:
                        parser.error('Unknown hypothesis post number.')
                writer.begin('register')
                result = register.register(state, args.post, args.url, args.published_at)
                storage.save(state_path, state)
                writer.finish(
                    'register', state='waiting', stage_state='completed',
                    reason='Publication details recorded; no publishing occurred.',
                    next_action='Run cycle when the next checkpoint is due.',
                )
            elif args.command == 'collect':
                writer.begin('collect', step='post_metrics')
                result = collect.collect(state, state_path, args.max_cost_usd,
                                         project_root=root, page_id=config['page_id'])
                writer.finish('collect', state='waiting', stage_state='completed', step='post_metrics',
                              reason=f'Collected {len(result)} publication snapshots.',
                              next_action='Inspect needs_attention entries, then run cycle when due.'
                              if any(item.get('metrics_status') == 'needs_attention' for item in result)
                              else 'Run cycle when the next checkpoint is due.')
            elif args.command == 'collect-insights':
                writer.begin('collect', step='post_insights')
                result = collect.collect_insights(state, state_path,
                                                  project_root=root, page_id=config['page_id'])
                attention = [item for item in result if item.get('metrics_status') == 'needs_attention']
                if attention:
                    writer.finish(
                        'collect', state='failed', step='post_insights',
                        reason='A due dashboard could not be collected.',
                        error={'stage': 'collect', 'step': 'post_insights',
                               'detail': attention[0].get('error')},
                        next_action='Inspect the collector error before another attempt.',
                    )
                else:
                    writer.finish('collect', state='waiting', stage_state='completed', step='post_insights',
                                  reason=f'Collected {len(result)} dashboard snapshots.',
                                  next_action='Run cycle when the next checkpoint is due.')
            elif args.command == 'review':
                review_payload = json.loads(args.file.read_text())
                if args.run_id:
                    result = workflow.record_review_run(root, args.run_id, review_payload)
                elif args.id:
                    writer.begin('review')
                    entry = next(item for item in state['publications'] if item['id'] == args.id)
                    review.review(entry, review_payload)
                    storage.save(state_path, state)
                    writer.finish('review', state='waiting', stage_state='completed',
                                  reason='Legacy publication review recorded.',
                                  next_action='Run cycle when the next checkpoint is due.')
                    result = entry
                else:
                    parser.error('Provide either --run or --id for review.')
            elif args.command == 'due':
                writer.begin('checkpoints')
                result = checkpoints.due_checkpoints(state, storage.now())
                if result:
                    pending = workflow.pending_work(root, state)
                    writer.finish(
                        'checkpoints', state='waiting', stage_state='completed',
                        reason=f'{len(result)} checkpoint(s) are due.',
                        next_action='Run cycle to collect the due checkpoints.',
                        pending_run_ids=[item['run_id'] for item in pending['open_runs']],
                    )
                else:
                    workflow.report_no_work(writer, workflow.pending_work(root, state))
            elif args.command == 'status':
                status = workflow.rebuild_if_missing(root, state)
                result = {**state, 'pending_work': workflow.pending_work(root, state),
                          'status': status}
            else:
                parser.error(f"Unsupported command '{args.command}'.")
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as exc:
            _mark_failed(writer, exc)
            raise

        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
