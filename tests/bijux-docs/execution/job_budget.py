"""Check completed frontend job budgets from retained GitHub jobs metadata."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

BASELINE_JOBS = {'std / standard', 'std / contracts', 'std / report'}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def expected_job_names(groups: dict, engines: tuple | list) -> set[str]:
    require(bool(groups) and bool(engines), 'Canonical browser groups and engines are required')
    require(len(set(engines)) == len(engines), 'Duplicate canonical engine')
    require(all(isinstance(x, str) and x and '/' not in x for x in [*groups, *engines]), 'Invalid canonical group or engine')
    return {'std / navigation fixtures', 'std / navigation', 'std / publication commands',
            'std / frontend public artifact fault controls'} | {
        f'std / frontend fault controls / {engine}' for engine in engines
    } | {
        f'std / navigation {group} / {engine}' for group in groups for engine in engines
    }


def timestamp(value: object) -> datetime:
    require(isinstance(value, str) and bool(value), 'Actual job timestamp is required')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None, 'Timestamp timezone is required')
    return parsed


def current_inventory(payload: dict, *, groups: dict, engines: tuple | list, run_id: int, attempt: int, head: str) -> tuple[list[dict], set[str]]:
    require(type(run_id) is int and run_id > 0 and type(attempt) is int and attempt > 0, 'Invalid requested run or attempt')
    require(isinstance(head, str) and re.fullmatch(r'[a-f0-9]{40}', head), 'Full workflow source SHA is required')
    jobs = payload.get('jobs')
    require(isinstance(jobs, list) and bool(jobs), 'Actual job metadata is required')
    names = expected_job_names(groups, engines)
    require(payload.get('total_count') == len(jobs), 'Incomplete jobs API page')
    require(len({j.get('name') for j in jobs}) == len(jobs), 'Duplicate job name')
    require({j.get('name') for j in jobs} == names | BASELINE_JOBS, 'Missing or unexpected current job name')
    require(all(type(j.get('id')) is int and j['id'] > 0 for j in jobs), 'Actual unique job IDs are required')
    require(len({j['id'] for j in jobs}) == len(jobs), 'Duplicate job ID')
    require(all(j.get('run_id') == run_id and j.get('run_attempt') == attempt and j.get('head_sha') == head for j in jobs), 'Job run, attempt or source mismatch')
    return jobs, names


def refresh_nonterminal(payload: dict, *, fetch, groups: dict, engines: tuple | list,
                        run_id: int, attempt: int, head: str) -> dict:
    """Reobserve only incomplete API rows without inferring success from completed steps."""
    jobs, names = current_inventory(payload, groups=groups, engines=engines,
                                    run_id=run_id, attempt=attempt, head=head)
    updated = []
    identity = ('id', 'name', 'run_id', 'run_attempt', 'head_sha')
    for job in jobs:
        if job['name'] in names and job.get('status') != 'completed':
            observed = fetch(job['id'])
            require(isinstance(observed, dict) and
                    all(observed.get(key) == job.get(key) for key in identity),
                    'Refreshed job identity differs from exact source, attempt or inventory')
            updated.append(observed)
        else:
            updated.append(job)
    return {**payload, 'jobs': updated}


def qualify(payload: dict, *, groups: dict, engines: tuple | list, run_id: int, attempt: int, head: str) -> dict:
    jobs, names = current_inventory(payload, groups=groups, engines=engines,
                                    run_id=run_id, attempt=attempt, head=head)
    records = []
    for job in jobs:
        if job['name'] not in names:
            continue
        require(job.get('status') == 'completed' and job.get('conclusion') == 'success', 'Required frontend job is not terminal-success')
        created, started, ended = (timestamp(job.get(key)) for key in ('created_at', 'started_at', 'completed_at'))
        require(created <= started <= ended, 'Job timestamps are out of order')
        duration = (ended - started).total_seconds()
        require(duration < 180, 'Frontend job reached the strict 180-second limit')
        steps = job.get('steps')
        require(isinstance(steps, list) and bool(steps), 'Actual job steps are required')
        step_records = []
        for step in steps:
            require(step.get('status') == 'completed' and step.get('conclusion') in {'success', 'skipped'}, 'Job step is not terminal-success or intentionally skipped')
            before, after = step.get('started_at'), step.get('completed_at')
            if before is None or after is None:
                require(before is None and after is None and step['conclusion'] == 'skipped', 'Actual step timestamps are missing')
                seconds = None
            else:
                before, after = timestamp(before), timestamp(after)
                require(started <= before <= after <= ended, 'Step timestamps are outside the actual job interval')
                seconds = (after - before).total_seconds()
            step_records.append({'name': step.get('name'), 'result': step['conclusion'], 'seconds': seconds})
        records.append({'id': job['id'], 'name': job['name'], 'created_at': job['created_at'], 'started_at': job['started_at'],
                        'completed_at': job['completed_at'], 'seconds': duration, 'queue_seconds': (started - created).total_seconds(), 'steps': step_records})
    require({j['name'] for j in records} == names, 'Frontend budget coverage is incomplete')
    return {'schema': 1, 'status': 'passed', 'workflow_run_id': run_id, 'workflow_attempt': attempt, 'workflow_head': head,
            'strict_limit_seconds': 180, 'expected_jobs': len(names), 'executed_jobs': len(records), 'jobs': records,
            'maximum_seconds': max(j['seconds'] for j in records), 'maximum_queue_seconds': max(j['queue_seconds'] for j in records),
            'limits': ['Queue is reported separately. Provider performance is observed, not guaranteed. No browser case or release acceptance is inferred.']}


def registry_digests(registry_path: Path) -> dict[str, str]:
    names = ('browser_gate.py', 'browser_partitions.py', 'browser_partitions.json')
    return {name: hashlib.sha256(registry_path.with_name(name).read_bytes()).hexdigest() for name in names}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs-json', type=Path, required=True)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--attempt', type=int, required=True)
    parser.add_argument('--workflow-head', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        registry_path = Path(__file__).with_name('browser_gate.py')
        registry = {'__name__': 'budget_registry', '__file__': str(registry_path)}
        exec(compile(registry_path.read_text(), str(registry_path), 'exec'), registry)
        receipt = qualify(json.loads(args.jobs_json.read_text()), groups=registry['GROUPS'], engines=registry['ENGINES'],
                          run_id=args.run_id, attempt=args.attempt, head=args.workflow_head)
        receipt['input_sha256'] = hashlib.sha256(args.jobs_json.read_bytes()).hexdigest()
        receipt['registry_sha256'] = hashlib.sha256(registry_path.read_bytes()).hexdigest()
        receipt['registry_files_sha256'] = registry_digests(registry_path)
    except (ValueError, KeyError, TypeError, OSError) as error:
        receipt = {'schema': 1, 'status': 'failed', 'error': str(error)}
    receipt['requested_workflow_run_id'] = args.run_id
    receipt['requested_workflow_attempt'] = args.attempt
    receipt['requested_workflow_head'] = args.workflow_head
    if args.jobs_json.is_file():
        receipt['input_sha256'] = hashlib.sha256(args.jobs_json.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print('Frontend job budget:', receipt['status'])
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
