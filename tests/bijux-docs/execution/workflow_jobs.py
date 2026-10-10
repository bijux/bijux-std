"""Reconcile physical Actions executions without changing provider API rows.

Attempt listings may project earlier completed jobs with new IDs and creation
times. Those rows are audit aliases, never new producers. Live original jobs,
checks, complete step lifecycles and attempt windows establish ownership.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime
import re

MAX_ATTEMPTS = 8
EXECUTION_FIELDS = ('run_id', 'head_sha', 'head_branch', 'workflow_name', 'name',
                    'status', 'conclusion', 'started_at', 'completed_at', 'steps',
                    'runner_id', 'runner_name', 'labels')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def timestamp(value):
    require(isinstance(value, str), 'Physical execution timestamp is required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'Physical execution timestamp needs timezone')
    return result


def fingerprint(row):
    require(all(key in row for key in EXECUTION_FIELDS), 'Complete execution fields are required')
    return {key: copy.deepcopy(row[key]) for key in EXECUTION_FIELDS}


def physical(row, frame, upper, caller):
    """Positive runner/step lifecycle proof; queue reservations have no lifecycle."""
    require(type(row.get('runner_id')) is int and row['runner_id'] > 0
            and isinstance(row.get('runner_name'), str) and row['runner_name']
            and isinstance(row.get('labels'), list) and row['labels'], 'Actual runner ownership is required')
    created, started = timestamp(row.get('created_at')), timestamp(row.get('started_at'))
    require(created <= started and timestamp(frame['run_started_at']) <= started
            and (upper is None or started < upper), 'Job is outside its physical attempt window')
    steps = row.get('steps')
    require(isinstance(steps, list) and steps and len(steps) <= 128, 'Actual finite step lifecycle is required')
    require(len({step.get('number') for step in steps}) == len(steps)
            and all(type(step.get('number')) is int and step['number'] > 0
                    and isinstance(step.get('name'), str) and step['name'] for step in steps), 'Actual unique steps are required')
    active = row.get('status') == 'in_progress'
    if active:
        require(row.get('name') == caller and row.get('conclusion') is None
                and row.get('completed_at') is None
                and any(step.get('status') == 'in_progress' for step in steps), 'Only the source-owned active caller may identify execution')
        ended = None
    else:
        require(row.get('status') == 'completed' and row.get('conclusion') is not None, 'Physical terminal status is required')
        ended = timestamp(row.get('completed_at'))
        require(started <= ended and (upper is None or ended < upper), 'Job cleanup crosses its physical attempt window')
    for step in steps:
        require(step.get('status') in ('completed', 'in_progress', 'queued', 'pending'), 'Unknown step lifecycle')
        before, after = step.get('started_at'), step.get('completed_at')
        if before is not None:
            require(started <= timestamp(before) and (ended is None or timestamp(before) <= ended), 'Step start is outside physical job')
        if after is not None:
            require(before is not None and timestamp(before) <= timestamp(after)
                    and (ended is None or timestamp(after) <= ended), 'Step cleanup is outside physical job')
        if step.get('status') == 'in_progress':
            require(active and before is not None and after is None, 'Incoherent active step')
    return active


def check(fetch, row, repository, frame):
    prefix = 'https://api.github.com/repos/' + repository + '/check-runs/'
    url = row.get('check_run_url')
    require(isinstance(url, str) and re.fullmatch(re.escape(prefix) + r'[1-9][0-9]*', url), 'Job check endpoint is outside its repository')
    result = fetch(url.removeprefix('https://api.github.com/'))
    require(result.get('id') == int(url[len(prefix):]) and result.get('url') == url
            and result.get('name') == row['name'] and result.get('head_sha') == row['head_sha']
            and result.get('check_suite', {}).get('id') == frame.get('check_suite_id')
            and result.get('app', {}).get('id') == 15368
            and result.get('app', {}).get('slug') == 'github-actions', 'Check source or Actions ownership differs')
    require(result.get('status') == row.get('status') and result.get('conclusion') == row.get('conclusion'), 'Job and check lifecycle differ')
    if row.get('status') == 'completed':
        require(all(result.get(key) == row.get(key) for key in ('started_at', 'completed_at')), 'Check physical timestamps differ')
    return result


def capture(api, identity, pages, *, fetch=None, caller=None, names=None):
    """Complete bounded attempt frames, canonical executions and untouched aliases."""
    require(type(identity['attempt']) is int and 1 <= identity['attempt'] <= MAX_ATTEMPTS, 'Physical attempt capture exceeds finite bound')
    require(caller is None or isinstance(caller, str) and caller.startswith('std / '), 'Caller must be a source-owned workflow role')
    if names is not None:
        require(isinstance(names, (list, tuple)) and 0 < len(names) <= 128
                and all(isinstance(name, str) and name for name in names)
                and len(set(names)) == len(names) and (caller is None or caller in names),
                'Finite explicit owner scope must include its active caller')
    def needed(row):
        return names is None or row['name'] in names
    fetch = fetch or api.json
    run_path = 'repos/' + api.repository + '/actions/runs/' + str(identity['run_id'])
    def attempt_frame(attempt):
        endpoint = run_path + '/attempts/' + str(attempt)
        run = api.json(endpoint)
        require(all(run.get(key) == identity[value] for key, value in
                    (('id', 'run_id'), ('head_sha', 'head'), ('workflow_id', 'workflow_id'),
                     ('path', 'workflow_path'), ('head_branch', 'head_branch')))
                and run.get('run_attempt') == attempt
                and run.get('repository', {}).get('full_name') == api.repository
                and run.get('head_repository', {}).get('full_name') == api.repository
                and type(run.get('check_suite_id')) is int and run['check_suite_id'] > 0,
                'Attempt source identity differs')
        inventory = pages(api.json, endpoint + '/jobs', 'jobs')
        return {'attempt': attempt, 'run': run, 'inventory': inventory}
    with ThreadPoolExecutor(max_workers=min(8, identity['attempt'])) as pool:
        frames = list(pool.map(attempt_frame, range(1, identity['attempt'] + 1)))
    starts = [timestamp(frame['run'].get('run_started_at')) for frame in frames]
    require(all(a < b for a, b in zip(starts, starts[1:])), 'Attempt execution windows overlap')
    physical_rows, aliases, reservations, unresolved, nonexecutions = [], [], [], [], []
    by_id = {}
    for index, frame in enumerate(frames):
        for row in frame['inventory']['jobs']:
            require(row.get('run_id') == identity['run_id'] and row.get('head_sha') == identity['head']
                    and row.get('head_branch') == identity['head_branch'] and row.get('run_attempt') == frame['attempt']
                    and isinstance(row.get('name'), str) and row['name'], 'Raw attempt job source differs')
            require(row['id'] not in by_id, 'Raw attempt job ID is repeated')
            by_id[row['id']] = row
            if (row.get('status') == 'queued' and row.get('conclusion') is None
                    and not row.get('runner_id') and not row.get('runner_name') and row.get('completed_at') is None):
                reservations.append((row, frame))
            elif row.get('status') == 'completed' and timestamp(row.get('completed_at')) < starts[index]:
                originals = physical_rows + [item['row'] for item in nonexecutions]
                matches = [original for original in originals if original['run_attempt'] < row['run_attempt']
                           and fingerprint(original) == fingerprint(row)]
                require(len(matches) == 1, 'Copied execution has no unique original physical owner')
                aliases.append({'projection': copy.deepcopy(row), 'original_job_id': matches[0]['id']})
            elif (row.get('status') == 'completed' and row.get('conclusion') == 'cancelled'
                    and type(row.get('runner_id')) is int and row['runner_id'] == 0
                    and row.get('runner_name') == '' and row.get('steps') == []):
                # GitHub gives queue cancellations timestamps without assigning
                # a runner. Retain that terminal observation, never a producer.
                created, started, ended = (timestamp(row.get(key)) for key in
                                           ('created_at', 'started_at', 'completed_at'))
                require(starts[index] <= created <= started <= ended
                        and (index + 1 == len(starts) or ended < starts[index + 1]),
                        'Unassigned cancellation is outside its attempt window')
                nonexecutions.append({'row': copy.deepcopy(row),
                    'reason': 'cancelled before runner assignment'})
            elif row.get('status') == 'in_progress' and row.get('name') != caller:
                unresolved.append({'row': copy.deepcopy(row), 'reason': 'unclaimed active execution'})
            else:
                physical(row, frame['run'], starts[index + 1] if index + 1 < len(starts) else None, caller)
                physical_rows.append(row)
    candidates = {}
    for row in physical_rows:
        candidates.setdefault(row['name'], []).append(row)
    selected = []
    for name, rows in candidates.items():
        newest = max(row['run_attempt'] for row in rows)
        latest = [row for row in rows if row['run_attempt'] == newest]
        require(len(latest) == 1, 'Multiple actual latest executions own one role')
        selected.append(latest[0])
    checks = {}
    def verify(row):
        live = fetch('repos/' + api.repository + '/actions/jobs/' + str(row['id']))
        if row.get('status') == 'in_progress':
            require(all(live.get(key) == row.get(key) for key in
                        ('id', 'name', 'run_id', 'run_attempt', 'head_sha', 'started_at', 'runner_id', 'runner_name')),
                    'Active caller execution identity changed')
            require(live.get('status') == 'in_progress', 'Caller completed during admission')
            physical(live, frames[row['run_attempt'] - 1]['run'], None, caller)
        else:
            require(live == row, 'Live per-ID execution differs from attempt frame')
        return row['id'], check(fetch, live, api.repository, frames[row['run_attempt'] - 1]['run'])
    # Every requested canonical original, including a carried owner, is positively
    # checked. Complete attempt frames remain observations; they cannot extend
    # a scoped worker’s authority to unrelated owners.
    with ThreadPoolExecutor(max_workers=8) as pool:
        checks.update(pool.map(verify, [row for row in physical_rows if needed(row)]))
        def verify_nonexecution(item):
            row = item['row']
            require(fetch('repos/' + api.repository + '/actions/jobs/' + str(row['id'])) == row,
                    'Live unassigned cancellation differs from attempt frame')
            return {**item, 'check': check(fetch, row, api.repository,
                                          frames[row['run_attempt'] - 1]['run'])}
        nonexecutions = [*list(pool.map(verify_nonexecution, [item for item in nonexecutions if needed(item['row'])])),
                         *[item for item in nonexecutions if not needed(item['row'])]]
        def projection(alias):
            row = alias['projection']
            require(fetch('repos/' + api.repository + '/actions/jobs/' + str(row['id'])) == row,
                    'Live projected row changed')
        list(pool.map(projection, [alias for alias in aliases if needed(alias['projection'])]))
    relations = []
    for row, frame in reservations:
        if not needed(row):
            unresolved.append({'row': copy.deepcopy(row), 'reason': 'outside explicit owner scope'})
            continue
        reservation_check = check(api.json, row, api.repository, frame['run'])
        binding = reservation_check.get('external_id')
        matches = [actual for actual in physical_rows if actual['run_attempt'] == frame['attempt']
                   and actual['name'] == row['name'] and binding
                   and checks[actual['id']].get('external_id') == binding
                   and (not row.get('steps') or row['steps'] == actual['steps'])]
        if len(matches) == 1 and (matches[0]['status'] == 'completed' or matches[0]['name'] == caller):
            relations.append({'reservation': copy.deepcopy(row), 'check': reservation_check,
                              'physical_job_id': matches[0]['id']})
        else:
            unresolved.append({'row': copy.deepcopy(row), 'check': reservation_check, 'reason': 'unresolved reservation'})
    # A cancellation may be superseded only by a newer actual execution. A
    # carried older success must not satisfy a role canceled without running.
    for item in nonexecutions:
        row = item['row']
        if not any(actual['name'] == row['name'] and actual['run_attempt'] > row['run_attempt']
                   for actual in selected):
            unresolved.append(copy.deepcopy(item))
    require(caller is None or len([row for row in selected if row['name'] == caller
                                  and row['run_attempt'] == identity['attempt'] and row['status'] == 'in_progress']) == 1,
            'Source-owned active caller is missing or ambiguous')
    require(not any(item['row']['name'] == caller for item in unresolved), 'Caller has unresolved execution rows')
    return {'latest': {'total_count': len(selected), 'jobs': copy.deepcopy(selected)},
            'history': {'total_count': len(physical_rows), 'jobs': copy.deepcopy(physical_rows)},
            'execution_reconciliation': {'frames': frames, 'aliases': aliases, 'reservations': relations,
                'nonexecutions': nonexecutions,
                'unresolved': unresolved, 'checks': checks, 'caller': caller,
                **({'checked_job_names': sorted(names)} if names is not None else {}),
                'raw_rows': sum(frame['inventory']['total_count'] for frame in frames),
                'physical_rows': len(physical_rows), 'physical_names': len(selected)}}
