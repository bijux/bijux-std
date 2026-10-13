"""Select full execution unless an independently accepted original proof qualifies."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from types import ModuleType
import xml.etree.ElementTree as ET

_PATH = Path(__file__).with_name('modules.py')
MODULES = ModuleType('bijux_accepted_proof_source_modules')
MODULES.__file__ = str(_PATH)
exec(compile(_PATH.read_bytes(), str(_PATH), 'exec'), MODULES.__dict__)
load = MODULES.load
SOURCE = load('proof_continuity/source.py')
AUTHORITY = load('proof_continuity/authority.py')
NATIVE = load('proof_continuity/native.py')


def qualify(api, root, plan):
    """Only this live read boundary constructs an accepted-proof observation."""
    SOURCE.require(plan['frontend'] is False and not plan['full_verification_reasons'],
                   'Changed unknown or refused inputs require full fresh execution')
    SOURCE.unchanged(root, plan)
    AUTHORITY.admit_qualification_request(api, plan)
    accepted = AUTHORITY.locate(api, plan['baseline'])
    prefix = 'repos/' + api.repository + '/'
    original_tree = SOURCE.api_tree(api.json(prefix + 'git/trees/' + accepted['source_tree'] + '?recursive=1'),
                                    accepted['source_tree'])
    SOURCE.require(SOURCE.frontend(original_tree) == SOURCE.frontend(plan['source_objects']),
                   'Accepted producer frontend source closure differs')
    lineage = load('workflow_lineage.py')
    run = accepted['run']
    artifacts = lineage.ARTIFACTS.pages(api.json, prefix + 'actions/runs/' + str(run['id']) + '/artifacts', 'artifacts')
    latest = lineage.ARTIFACTS.pages(api.json, prefix + 'actions/runs/' + str(run['id']) + '/jobs?filter=latest', 'jobs')
    navigation = [row for row in latest['jobs'] if row.get('name') == 'std / navigation']
    SOURCE.require(len(navigation) == 1 and type(navigation[0].get('run_attempt')) is int,
                   'Original latest aggregate owner is missing or ambiguous')
    matches = [row for row in artifacts['artifacts'] if re.fullmatch(
        'docs-navigation-complete-[a-f0-9]{40}-' + str(navigation[0]['run_attempt']), row.get('name', ''))]
    SOURCE.require(len(matches) == 1, 'Accepted producer lacks exactly one original complete aggregate')
    checkout = matches[0]['name'].removeprefix('docs-navigation-complete-').rsplit('-', 1)[0]
    identity = {'run_id': run['id'], 'attempt': run['run_attempt'], 'head': accepted['head'],
                'checkout_sha': checkout, 'source_tree': accepted['source_tree'],
                'workflow_id': run['workflow_id'], 'workflow_path': run['path'], 'head_branch': run['head_branch']}
    gate = load('browser_gate.py')
    budget = load('job_budget.py')
    names = budget.expected_job_names(gate.BATCHES, gate.ENGINES) | budget.BASELINE_JOBS
    checkout_authority = AUTHORITY.admit_checkout(api, accepted, checkout)
    # The accepted producer has finished; active caller authority belongs only
    # to the current workflow observing its own running execution.
    observation = lineage.observe_source(api, identity, reconcile=True, names=sorted(names),
                                         checkout_authority=checkout_authority)
    budget_receipt = budget.qualify_latest(observation, groups=gate.BATCHES, engines=gate.ENGINES,
        run_id=run['id'], attempt=run['run_attempt'], head=accepted['head'])
    jobs = {row['name']: row for row in observation.observation['latest']['jobs']}
    SOURCE.require(set(jobs) == names and all(row.get('status') == 'completed' and row.get('conclusion') == 'success'
                    for row in jobs.values()), 'Accepted full producer has missing failed or skipped source-owned jobs')
    roles = load('workflow_collection.py').registry()
    wanted = {key: {name: value[name] for name in ('job_name', 'artifact_prefix', 'upload_step')}
              for key, value in roles.items() if key == 'producer' or key.startswith('fault-')}
    wanted['complete'] = {'job_name': 'std / navigation', 'artifact_prefix': 'docs-navigation-complete',
                          'upload_step': 'Retain complete navigation qualification'}
    catalogue = load('../catalogue/execution.py')
    for group in catalogue.GROUPS:
        wanted['catalogue-' + group] = {'job_name': 'std / catalogue ' + group,
            'artifact_prefix': 'docs-catalogue-' + group, 'upload_step': 'Retain catalogue source runtime and test evidence'}
    inputs = observation.admit(wanted)
    complete = NATIVE.decode(inputs['complete'].read('navigation-qualification.json'))
    original = complete['source_identity']
    SOURCE.require(original.get('head') == checkout, 'Original aggregate source differs from its API checkout')
    context = SOURCE.admit(root, plan, original, original_tree, checkout_authority)
    owner = Path(root) / 'artifacts/bijux-docs/proof-continuity'
    owner.mkdir(parents=True, exist_ok=True)
    # The parent is retained, while each verification uses a new physical body.
    # Existing or downloaded observations never populate this capability.
    run_output = Path(tempfile.mkdtemp(prefix='accepted-producer-', dir=owner)) / 'original'
    NATIVE.materialize(inputs, run_output)
    counts = NATIVE.qualify(Path(root), run_output, context, inputs, jobs, load)
    SOURCE.unchanged(root, plan)
    observation.refresh(sorted(names))
    AUTHORITY.admit_qualification_request(api, plan)
    refreshed = AUTHORITY.locate(api, plan['baseline'])
    SOURCE.require(all(refreshed[key] == accepted[key] for key in
                       ('accepted_main', 'accepted_pr', 'merged_at', 'head', 'source_tree', 'run')),
                   'Accepted producer changed during qualification')
    return {'schema': 1, 'status': 'passed', 'qualification_kind': 'accepted_original_execution',
        'accepted_main': accepted['accepted_main'], 'accepted_pr': accepted['accepted_pr'],
        'accepted_at': accepted['merged_at'], 'original_workflow': identity,
        'original_source_identity': original, 'original_counts': counts,
        'original_artifacts': {role: item.pointer() for role, item in sorted(inputs.items())},
        'original_aggregate_sha256': hashlib.sha256(inputs['complete'].read('navigation-qualification.json')).hexdigest(),
        'frontend_objects_sha256': hashlib.sha256(json.dumps(SOURCE.frontend(original_tree), sort_keys=True,
            separators=(',', ':')).encode()).hexdigest(),
        'original_job_budget': budget_receipt,
        'limits': ['Original native receipts retain original source, run and physical attempts.',
                   'No frontend case executed at the current head; current source/security contexts remain required.',
                   'Headless engines do not establish physical devices or human assistive review.']}


def selection_identity(plan):
    return {'schema': 1, 'source_head': plan['checkout'], 'baseline': plan['baseline'],
        'plan_sha256': hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}


def refused(plan, reason):
    return {**selection_identity(plan), 'frontend': True,
            'selection_kind': 'accepted_proof_refused_full_execution', 'refusal': reason, 'proof': None}


def select(root, plan, api=None):
    result = selection_identity(plan)
    if plan['frontend']:
        return {**result, 'frontend': True, 'selection_kind': 'full_current_execution', 'proof': None}
    try:
        if api is None:
            SOURCE.require(os.environ.get('GITHUB_REPOSITORY') == 'bijux/bijux-std', 'Continuity requires its owning repository')
            api = load('workflow_artifacts.py').GitHubAPI('bijux/bijux-std', os.environ.get('GH_TOKEN'))
        # Selection crosses JSON storage before aggregate revalidation. Export
        # the same key representation while internal job/check IDs stay typed.
        proof = json.loads(json.dumps(qualify(api, root, plan)))
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError, ET.ParseError) as error:
        # Transport errors deliberately contain neither credentials nor signed URLs.
        reason = str(error) if isinstance(error, ValueError) else type(error).__name__
        return refused(plan, reason)
    return {**result, 'frontend': False, 'selection_kind': 'accepted_original_proof', 'proof': proof}


def verify(root, plan, supplied, expected_frontend, api=None):
    SOURCE.require(isinstance(supplied, dict) and supplied.get('schema') == 1
        and supplied.get('source_head') == plan['checkout'] and supplied.get('baseline') == plan['baseline']
        and supplied.get('plan_sha256') == hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        and type(supplied.get('frontend')) is bool and str(supplied['frontend']).lower() == expected_frontend,
        'Actual continuity selection differs from current source or workflow outcome')
    if supplied['frontend']:
        SOURCE.require(supplied.get('proof') is None and supplied.get('selection_kind') in
                       ('full_current_execution', 'accepted_proof_refused_full_execution'),
                       'Fresh execution cannot claim an inherited proof')
        return supplied
    SOURCE.require(plan['frontend'] is False and supplied.get('selection_kind') == 'accepted_original_proof',
                   'Changed source cannot omit fresh execution')
    current = select(root, plan, api)
    SOURCE.require(current == supplied and current['frontend'] is False,
                   'Accepted original proof failed independent required aggregate revalidation')
    return current
