"""Locate a successful producer through accepted main, merged PR and Actions APIs."""
from __future__ import annotations

from datetime import datetime, timezone
import copy
import os
import re

_CREATED = object()


def admit_qualification_request(api, plan):
    """An explicit manual request must independently own current accepted main."""
    if plan.get('qualification_mode', 'full') == 'full':
        return
    require(plan.get('qualification_mode') == 'accepted-proof-qualification'
            and plan.get('event') == 'workflow_dispatch'
            and plan['checkout'] == plan['baseline']
            and api.repository == 'bijux/bijux-std'
            and os.environ.get('GITHUB_REPOSITORY') == api.repository
            and os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
            and os.environ.get('GITHUB_REF') == 'refs/heads/main'
            and os.environ.get('GITHUB_SHA') == plan['checkout']
            and os.environ.get('VERIFICATION_MODE') == 'accepted-proof-qualification',
            'Qualification request must own the explicit accepted-main event')
    run_id, attempt = os.environ.get('GITHUB_RUN_ID', ''), os.environ.get('GITHUB_RUN_ATTEMPT', '')
    require(run_id.isdecimal() and attempt.isdecimal() and int(run_id) > 0 and int(attempt) > 0,
            'Qualification requires its actual run and attempt')
    prefix = 'repos/' + api.repository + '/'
    main = api.json(prefix + 'git/ref/heads/main')
    require(main.get('ref') == 'refs/heads/main' and main.get('object', {}).get('type') == 'commit'
            and main['object'].get('sha') == plan['checkout'], 'Qualification checkout is not current official main')
    run = api.json(prefix + 'actions/runs/' + run_id)
    require(run.get('id') == int(run_id) and run.get('run_attempt') == int(attempt)
            and run.get('event') == 'workflow_dispatch' and run.get('head_branch') == 'main'
            and run.get('head_sha') == plan['checkout'] and run.get('path') == '.github/workflows/bijux-std.yml'
            and run.get('repository', {}).get('full_name') == api.repository
            and run.get('head_repository', {}).get('full_name') == api.repository
            and run.get('status') in ('in_progress', 'completed')
            and (run.get('status') != 'completed' or run.get('conclusion') == 'success'),
            'Qualification is not its live owning accepted-main workflow run')


class AcceptedProducer:
    """An independently observed acceptance, never recreated from a supplied record."""
    def __init__(self, value, *, _created=None):
        require(_created is _CREATED, 'Producer acceptance requires live merged-PR admission')
        self._value = copy.deepcopy(value)

    def __getitem__(self, key):
        return copy.deepcopy(self._value[key])


class AcceptedCheckout:
    """Live accepted merge authority; serialized audit data cannot relax defaults."""
    def __init__(self, accepted, checkout, head_commit, checkout_commit, tree, *, _created=None):
        require(_created is _CREATED, 'Accepted checkout requires live merged-PR ancestry admission')
        self._accepted, self._checkout = accepted, checkout
        self._head_commit, self._checkout_commit = head_commit, checkout_commit
        self._tree = copy.deepcopy(tree)

    def verify(self, identity, commits):
        require(identity['head'] == self._accepted['head'] and identity['checkout_sha'] == self._checkout
                and identity['source_tree'] == self._accepted['source_tree']
                and identity['run_id'] == self._accepted['run']['id']
                and identity['attempt'] == self._accepted['run']['run_attempt']
                and commits == {'head': self._head_commit, 'checkout_sha': self._checkout_commit},
                'Original checkout differs from authenticated accepted merge authority')

    def verify_source_objects(self, objects, original):
        require(self._tree.get('sha') == self._accepted['source_tree'] and self._tree.get('truncated') is False
                and isinstance(self._tree.get('tree'), list), 'Authenticated original Git tree is incomplete')
        expected = {row['path']: {'mode': row['mode'], 'kind': 'blob', 'object': row['sha']}
                    for row in self._tree['tree'] if row.get('type') == 'blob'}
        require(len(expected) == sum(row.get('type') == 'blob' for row in self._tree['tree'])
                and objects == expected and original.get('head') == self._checkout,
                'Original Git blobs or modes differ from live accepted checkout authority')


def require(value, message):
    if not value:
        raise ValueError(message)


def locate(api, baseline, *, now=None):
    require(api.repository == 'bijux/bijux-std' and isinstance(baseline, str)
            and re.fullmatch('[a-f0-9]{40}', baseline), 'Owning accepted main identity is required')
    prefix = 'repos/' + api.repository + '/'
    main = api.json(prefix + 'git/ref/heads/main')
    require(main.get('ref') == 'refs/heads/main' and main.get('object', {}).get('type') == 'commit'
            and re.fullmatch('[a-f0-9]{40}', main.get('object', {}).get('sha', '')), 'Actual main Git ref is required')
    comparison = api.json(prefix + 'compare/' + baseline + '...' + main['object']['sha'])
    require(comparison.get('status') in ('ahead', 'identical')
            and comparison.get('merge_base_commit', {}).get('sha') == baseline,
            'Event baseline is not accepted main ancestry')
    associated = api.json_array(prefix + 'commits/' + baseline + '/pulls?per_page=100&page=1')
    require(len(associated) < 100 and all(isinstance(row, dict) for row in associated),
            'Complete bounded accepted pull-request association is required')
    candidates = [row for row in associated if row.get('merge_commit_sha') == baseline
                  and row.get('merged_at') and row.get('base', {}).get('ref') == 'main'
                  and row.get('base', {}).get('repo', {}).get('full_name') == api.repository]
    require(len(candidates) == 1 and type(candidates[0].get('number')) is int,
            'Exactly one independently merged owning-main pull request is required')
    pull = api.json(prefix + 'pulls/' + str(candidates[0]['number']))
    require(pull.get('number') == candidates[0]['number'] and pull.get('merged') is True
            and pull.get('state') == 'closed' and pull.get('merge_commit_sha') == baseline
            and pull.get('base', {}).get('ref') == 'main'
            and pull.get('base', {}).get('repo', {}).get('full_name') == api.repository
            and pull.get('head', {}).get('repo', {}).get('full_name') == api.repository
            and re.fullmatch('[a-f0-9]{40}', pull.get('head', {}).get('sha', '')),
            'Accepted producer must belong to the independently merged owning-repository PR')
    merged_at = datetime.fromisoformat(pull['merged_at'].replace('Z', '+00:00'))
    now = now or datetime.now(timezone.utc)
    require(merged_at.tzinfo is not None and now.tzinfo is not None and 0 <= (now - merged_at).total_seconds() <= 14 * 86400,
            'Accepted proof exceeds its fourteen-day admission lifetime')
    head = pull['head']['sha']
    runs = api.json(prefix + 'actions/workflows/bijux-std.yml/runs?head_sha=' + head + '&event=pull_request&per_page=100&page=1')
    rows = runs.get('workflow_runs')
    require(type(runs.get('total_count')) is int and 0 < runs['total_count'] <= 100
            and isinstance(rows, list) and len(rows) == runs['total_count']
            and all(isinstance(row, dict) and type(row.get('id')) is int for row in rows)
            and len({row['id'] for row in rows}) == len(rows), 'Complete bounded exact-head producer runs are required')
    require(all(row.get('head_sha') == head and row.get('path') == '.github/workflows/bijux-std.yml'
                and row.get('event') == 'pull_request' for row in rows), 'Exact accepted workflow run inventory differs')
    run = max(rows, key=lambda row: row['id'])
    require(run.get('status') == 'completed' and run.get('conclusion') == 'success'
            and run.get('repository', {}).get('full_name') == api.repository
            and run.get('head_repository', {}).get('full_name') == api.repository
            and type(run.get('run_attempt')) is int and run['run_attempt'] > 0,
            'Newest accepted producer is missing failed pending or foreign')
    accepted = api.json(prefix + 'git/commits/' + baseline)
    candidate = api.json(prefix + 'git/commits/' + head)
    tree = accepted.get('tree', {}).get('sha')
    require(accepted.get('sha') == baseline and candidate.get('sha') == head
            and re.fullmatch('[a-f0-9]{40}', tree or '')
            and re.fullmatch('[a-f0-9]{40}', candidate.get('tree', {}).get('sha', '')),
            'Accepted main and tested producer Git objects are missing')
    ancestry = api.json(prefix + 'compare/' + head + '...' + baseline)
    require(ancestry.get('status') in ('ahead', 'identical')
            and ancestry.get('merge_base_commit', {}).get('sha') == head,
            'Accepted merged PR head is not an accepted-main ancestor')
    return AcceptedProducer({'accepted_main': baseline, 'accepted_pr': pull['number'], 'merged_at': pull['merged_at'],
            'observed_main': main['object']['sha'], 'head': head, 'source_tree': tree, 'run': run}, _created=_CREATED)


def admit_checkout(api, accepted, checkout):
    prefix = 'repos/' + api.repository + '/'
    require(type(accepted) is AcceptedProducer and api.repository == 'bijux/bijux-std'
            and re.fullmatch('[a-f0-9]{40}', checkout or ''),
            'Original owning checkout SHA is required')
    head_commit = api.json(prefix + 'git/commits/' + accepted['head'])
    checkout_commit = api.json(prefix + 'git/commits/' + checkout)
    require(head_commit.get('sha') == accepted['head'] and checkout_commit.get('sha') == checkout
            and checkout_commit.get('tree', {}).get('sha') == accepted['source_tree'],
            'Original preview does not bind the exact accepted-main tree')
    if checkout != accepted['head']:
        parents = checkout_commit.get('parents')
        require(isinstance(parents, list) and len(parents) == 2
                and parents[1].get('sha') == accepted['head']
                and re.fullmatch('[a-f0-9]{40}', parents[0].get('sha', '')),
                'Original preview parents differ from the accepted PR head')
        ancestry = api.json(prefix + 'compare/' + parents[0]['sha'] + '...' + accepted['accepted_main'])
        require(ancestry.get('status') in ('ahead', 'identical')
                and ancestry.get('merge_base_commit', {}).get('sha') == parents[0]['sha'],
                'Original preview base is not accepted-main ancestry')
    tree = api.json(prefix + 'git/trees/' + accepted['source_tree'] + '?recursive=1')
    return AcceptedCheckout(accepted, checkout, head_commit, checkout_commit, tree, _created=_CREATED)
