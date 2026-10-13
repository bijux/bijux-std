"""Refuse altered acceptance, source closure and original native identities."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_docs_workflow_artifacts as ARTIFACTS
import test_docs_workflow_lineage as LINEAGE
import test_docs_workflow_jobs as JOBS
import test_docs_renderer_controls as RENDERER
from test_docs_input_planning import FRONTEND_CONTEXTS, require_results

ROOT = Path(__file__).resolve().parents[1]
GATE = RENDERER.CONTROLS.load('accepted_proof_controls', ROOT / 'tests/bijux-docs/execution/proof_continuity/gate.py')
AUTHORITY, SOURCE, NATIVE = GATE.AUTHORITY, GATE.SOURCE, GATE.NATIVE
NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)


class ObservedAPI:
    repository = 'bijux/bijux-std'
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def json(self, endpoint):
        self.calls.append(endpoint)
        return copy.deepcopy(self.responses[endpoint])

    json_array = json


class AcceptedBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.base, self.head, self.checkout, self.tree = (value * 40 for value in 'abcd')
        self.prefix = 'repos/bijux/bijux-std/'
        repo = {'full_name': 'bijux/bijux-std'}
        self.actor = {'login': 'bijux', 'id': 222414480, 'type': 'User'}
        pull = {'number': 17, 'merged': True, 'state': 'closed', 'merge_commit_sha': self.base,
                'merged_at': '2026-10-12T18:00:00Z', 'user': self.actor, 'base': {'ref': 'main', 'repo': repo},
                'head': {'sha': self.head, 'ref': 'ci/owned-source', 'repo': repo}}
        self.run = {'id': 101, 'run_attempt': 2, 'head_sha': self.head, 'status': 'completed',
                    'conclusion': 'success', 'event': 'pull_request', 'repository': repo,
                    'actor': self.actor, 'triggering_actor': self.actor,
                    'head_repository': repo, 'head_branch': 'ci/owned-source', 'workflow_id': 9,
                    'path': '.github/workflows/bijux-std.yml'}
        self.responses = {
            self.prefix + 'git/ref/heads/main': {'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': self.base}},
            self.prefix + 'compare/' + self.base + '...' + self.base: {'status': 'identical', 'merge_base_commit': {'sha': self.base}},
            self.prefix + 'compare/' + self.head + '...' + self.base: {'status': 'ahead', 'merge_base_commit': {'sha': self.head}},
            self.prefix + 'commits/' + self.base + '/pulls?per_page=100&page=1': [pull],
            self.prefix + 'pulls/17': pull,
            self.prefix + 'actions/workflows/bijux-std.yml/runs?head_sha=' + self.head + '&event=pull_request&per_page=100&page=1': {
                'total_count': 1, 'workflow_runs': [self.run]},
            self.prefix + 'git/commits/' + self.base: {'sha': self.base, 'tree': {'sha': self.tree}},
            # Normal merged PR ancestry may preserve the tested PR head with a
            # distinct tree. Only the authenticated preview binds accepted main.
            self.prefix + 'git/commits/' + self.head: {'sha': self.head, 'tree': {'sha': 'e' * 40}},
            self.prefix + 'git/commits/' + self.checkout: {'sha': self.checkout, 'tree': {'sha': self.tree},
                'parents': [{'sha': self.base}, {'sha': self.head}]},
            self.prefix + 'git/trees/' + self.tree + '?recursive=1': {'sha': self.tree, 'truncated': False,
                'tree': [{'path': 'tests/unit.cjs', 'mode': '100644', 'type': 'blob', 'sha': 'f' * 40}]},
        }
        self.api = ObservedAPI(self.responses)

    def accepted(self):
        return AUTHORITY.locate(self.api, self.base, now=NOW)

    def test_distinct_accepted_main_pr_head_preview_and_original_attempt_remain_bound(self):
        accepted = self.accepted()
        authority = AUTHORITY.admit_checkout(self.api, accepted, self.checkout)
        identity = {'head': self.head, 'checkout_sha': self.checkout, 'source_tree': self.tree,
                    'run_id': 101, 'attempt': 2}
        commits = {key: self.api.json(self.prefix + 'git/commits/' + identity[key]) for key in ('head', 'checkout_sha')}
        authority.verify(identity, commits)
        self.assertNotEqual(accepted['accepted_main'], accepted['head'])
        self.assertNotEqual(identity['head'], identity['checkout_sha'])
        for key, value in [('head', '0' * 40), ('checkout_sha', '0' * 40), ('source_tree', '0' * 40), ('run_id', 102), ('attempt', 1)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                authority.verify({**identity, key: value}, commits)
        with self.assertRaises(ValueError): AUTHORITY.AcceptedProducer({'accepted_main': self.base})
        with self.assertRaises(ValueError): AUTHORITY.admit_checkout(self.api, {'accepted_main': self.base}, self.checkout)

    def test_foreign_unmerged_expired_failed_latest_and_nonancestral_acceptance_refuse(self):
        original = copy.deepcopy(self.responses)
        scenarios = ('foreign', 'unmerged', 'expired', 'failed-latest', 'main-ancestry', 'head-ancestry', 'incomplete-runs')
        for scenario in scenarios:
            self.responses.clear(); self.responses.update(copy.deepcopy(original))
            pull = self.responses[self.prefix + 'pulls/17']
            if scenario == 'foreign': pull['head']['repo']['full_name'] = 'foreign/bijux-std'
            elif scenario == 'unmerged': pull['merged'] = False
            elif scenario == 'expired': pull['merged_at'] = '2026-09-01T18:00:00Z'
            elif scenario == 'main-ancestry': self.responses[self.prefix + 'compare/' + self.base + '...' + self.base]['status'] = 'diverged'
            elif scenario == 'head-ancestry': self.responses[self.prefix + 'compare/' + self.head + '...' + self.base]['merge_base_commit']['sha'] = '0' * 40
            else:
                runs = self.responses[self.prefix + 'actions/workflows/bijux-std.yml/runs?head_sha=' + self.head + '&event=pull_request&per_page=100&page=1']
                runs['total_count'] = 2
                if scenario == 'failed-latest': runs['workflow_runs'].append({**self.run, 'id': 102, 'conclusion': 'failure'})
            with self.subTest(scenario=scenario), self.assertRaises(ValueError): self.accepted()

        # Independently observed PR authors and both Actions principals must
        # agree; no receipt or Git author can substitute for a missing API ID.
        for owner in ('author', 'actor', 'triggering_actor'):
            for identity in (None, {}, {'login': 'foreign', 'id': self.actor['id']},
                             {'login': self.actor['login'], 'id': 1},
                             {'login': self.actor['login'], 'id': 0},
                             {'login': self.actor['login'], 'id': True},
                             {'login': self.actor['login'], 'id': str(self.actor['id'])},
                             {'login': 'bijux\nforeign', 'id': self.actor['id']}):
                self.responses.clear(); self.responses.update(copy.deepcopy(original))
                if owner == 'author':
                    self.responses[self.prefix + 'pulls/17']['user'] = identity
                else:
                    rows = self.responses[self.prefix + 'actions/workflows/bijux-std.yml/runs?head_sha=' + self.head + '&event=pull_request&per_page=100&page=1']
                    rows['workflow_runs'][0][owner] = identity
                with self.subTest(owner=owner, principal=identity), self.assertRaises(ValueError):
                    self.accepted()
                plan = {'frontend': False, 'full_verification_reasons': [],
                        'checkout': self.head, 'baseline': self.base}
                live_locate = AUTHORITY.locate
                with patch.object(SOURCE, 'unchanged'), patch.object(AUTHORITY, 'locate',
                        side_effect=lambda api, baseline: live_locate(api, baseline, now=NOW)):
                    selected = GATE.select(ROOT, plan, self.api)
                    self.assertTrue(selected['frontend']); self.assertIsNone(selected['proof'])
                    self.assertEqual(selected['selection_kind'], 'accepted_proof_refused_full_execution')
                    supplied = {**GATE.selection_identity(plan), 'frontend': False,
                                'selection_kind': 'accepted_original_proof', 'proof': {'status': 'passed'}}
                    with self.assertRaisesRegex(ValueError, 'independent required aggregate revalidation'):
                        GATE.verify(ROOT, plan, supplied, 'false', self.api)

    def test_preview_parent_or_tree_drift_cannot_relax_ordinary_observation(self):
        accepted = self.accepted()
        path = self.prefix + 'git/commits/' + self.checkout
        original = copy.deepcopy(self.responses[path])
        for mutation in ('parent', 'tree', 'base-ancestry'):
            self.responses[path] = copy.deepcopy(original)
            if mutation == 'parent': self.responses[path]['parents'][1]['sha'] = '0' * 40
            elif mutation == 'tree': self.responses[path]['tree']['sha'] = '0' * 40
            else: self.responses[self.prefix + 'compare/' + self.base + '...' + self.base]['status'] = 'behind'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                AUTHORITY.admit_checkout(self.api, accepted, self.checkout)

    def test_array_api_keeps_object_default_duplicate_keys_and_repository_boundary(self):
        class Opener:
            def __init__(self, body): self.body, self.requests = body, []
            def open(self, request, timeout):
                self.requests.append(request)
                response = io.BytesIO(self.body); response.status = 200; response.headers = {}
                return response
        path = self.prefix + 'commits/' + self.base + '/pulls'
        for body, operation in [(b'[{}]', 'json'), (b'{}', 'json_array'), (b'[{"sha":1,"sha":2}]', 'json_array')]:
            api = ARTIFACTS.ARTIFACTS.GitHubAPI('bijux/bijux-std', 'controlled-token', opener=Opener(body))
            with self.assertRaises(ValueError): getattr(api, operation)(path)
        opener = Opener(b'[{"number":17}]')
        api = ARTIFACTS.ARTIFACTS.GitHubAPI('bijux/bijux-std', 'controlled-token', opener=opener)
        self.assertEqual(api.json_array(path), [{'number': 17}])
        self.assertEqual(opener.requests[0].get_header('Authorization'), 'Bearer controlled-token')
        with self.assertRaises(ValueError): api.json_array('repos/foreign/project/commits/' + self.base + '/pulls')

    def test_manual_qualification_independently_binds_live_main_event_run_and_attempt(self):
        plan = {'qualification_mode': 'accepted-proof-qualification', 'event': 'workflow_dispatch',
                'checkout': self.base, 'baseline': self.base}
        env = {'GITHUB_REPOSITORY': self.api.repository, 'GITHUB_EVENT_NAME': 'workflow_dispatch',
               'GITHUB_REF': 'refs/heads/main', 'GITHUB_SHA': self.base, 'VERIFICATION_MODE': plan['qualification_mode'],
               'GITHUB_RUN_ID': '201', 'GITHUB_RUN_ATTEMPT': '1',
               'GITHUB_ACTOR': self.actor['login'], 'GITHUB_ACTOR_ID': str(self.actor['id'])}
        path = self.prefix + 'actions/runs/201'
        run = {**self.run, 'id': 201, 'run_attempt': 1, 'event': 'workflow_dispatch',
               'head_sha': self.base, 'head_branch': 'main', 'status': 'in_progress', 'conclusion': None}
        self.responses[path] = run
        with patch.dict(os.environ, env, clear=True):
            AUTHORITY.admit_qualification_request(self.api, plan)
            for key, value in [('event', 'pull_request'), ('head_sha', self.head), ('head_branch', 'foreign'),
                               ('run_attempt', 2), ('id', 202), ('path', '.github/workflows/foreign.yml'),
                               ('repository', {'full_name': 'foreign/project'}),
                               ('head_repository', {'full_name': 'foreign/project'}), ('status', 'queued')]:
                self.responses[path] = {**run, key: value}
                with self.subTest(key=key), self.assertRaises(ValueError):
                    AUTHORITY.admit_qualification_request(self.api, plan)
            for key in ('actor', 'triggering_actor'):
                for value in (None, {}, {'login': 'foreign', 'id': self.actor['id']},
                              {'login': self.actor['login'], 'id': 1},
                              {'login': self.actor['login'], 'id': 0},
                              {'login': self.actor['login'], 'id': True}):
                    self.responses[path] = {**run, key: value}
                    with self.subTest(principal=key, value=value), self.assertRaises(ValueError):
                        AUTHORITY.admit_qualification_request(self.api, plan)
            self.responses[path] = {**run, 'status': 'completed', 'conclusion': 'failure'}
            with self.assertRaises(ValueError): AUTHORITY.admit_qualification_request(self.api, plan)
            self.responses[path] = run
            main = self.responses[self.prefix + 'git/ref/heads/main']
            main['object']['sha'] = self.head
            with self.assertRaises(ValueError): AUTHORITY.admit_qualification_request(self.api, plan)
            main['object']['sha'] = self.base
            for key, value in [('GITHUB_REF', 'refs/heads/foreign'), ('GITHUB_SHA', self.head),
                               ('GITHUB_REPOSITORY', 'foreign/project'), ('GITHUB_EVENT_NAME', 'pull_request'),
                               ('GITHUB_RUN_ATTEMPT', '0'), ('GITHUB_RUN_ID', 'invalid'), ('VERIFICATION_MODE', 'full'),
                               ('GITHUB_ACTOR', ''), ('GITHUB_ACTOR', 'foreign'),
                               ('GITHUB_ACTOR_ID', ''), ('GITHUB_ACTOR_ID', '0'),
                               ('GITHUB_ACTOR_ID', '1'), ('GITHUB_ACTOR_ID', 'invalid')]:
                with self.subTest(environment=key), patch.dict(os.environ, {key: value}), self.assertRaises(ValueError):
                    AUTHORITY.admit_qualification_request(self.api, plan)
            AUTHORITY.admit_qualification_request(self.api, {'qualification_mode': 'full'})

    def test_completed_original_reconciles_before_admission_without_granting_active_ownership(self):
        fixture = JOBS.PhysicalWorkflowTests(); fixture.setUp()
        lineage = JOBS.LINEAGE
        browser, budget = GATE.load('browser_gate.py'), GATE.load('job_budget.py')
        names = budget.expected_job_names(browser.BATCHES, browser.ENGINES) | budget.BASELINE_JOBS
        self.run.update(run_attempt=1, run_started_at='2026-10-12T17:39:00Z', check_suite_id=99)
        runpath = self.prefix + 'actions/runs/101'
        self.responses[runpath] = self.run
        self.responses[runpath + '/attempts/1'] = self.run
        self.responses[self.prefix + 'actions/workflows/9'] = {'id': 9, 'path': self.run['path']}
        rows = []
        for identifier, name in enumerate(sorted(names), 1000):
            row = fixture.job(identifier, 1, name, '2026-10-12T17:40:00Z', '2026-10-12T17:41:00Z')
            row.update(run_id=101, head_sha=self.head, head_branch=self.run['head_branch'])
            rows.append(row)
            self.responses[self.prefix + 'actions/jobs/' + str(identifier)] = row
            self.responses[self.prefix + 'check-runs/' + str(identifier)] = fixture.check(row)
        inventory = {'total_count': len(rows), 'jobs': rows}
        self.responses[runpath + '/attempts/1/jobs?per_page=100&page=1'] = inventory
        self.responses[runpath + '/jobs?filter=latest&per_page=100&page=1'] = inventory
        self.responses[runpath + '/artifacts?per_page=100&page=1'] = {'total_count': 1, 'artifacts': [
            {'id': 33, 'name': 'docs-navigation-complete-' + self.checkout + '-1'}]}
        objects = SOURCE.api_tree(self.responses[self.prefix + 'git/trees/' + self.tree + '?recursive=1'], self.tree)
        plan = {'frontend': False, 'full_verification_reasons': [], 'source_objects': objects,
                'baseline': self.base, 'qualification_mode': 'full'}
        load, locate = GATE.load, AUTHORITY.locate

        class ReconciledOriginal(Exception):
            pass

        def admitted(observation, roles):
            snapshot = observation.observation
            self.assertIsNone(snapshot['execution_reconciliation']['caller'])
            self.assertEqual(snapshot['latest']['total_count'], len(names))
            self.assertTrue(all(row['status'] == 'completed' and row['conclusion'] == 'success'
                                for row in snapshot['latest']['jobs']))
            self.assertEqual(roles['complete']['job_name'], 'std / navigation')
            raise ReconciledOriginal

        original = copy.deepcopy(self.responses)
        with patch.object(SOURCE, 'unchanged'), \
                patch.object(AUTHORITY, 'locate', side_effect=lambda api, base: locate(api, base, now=NOW)), \
                patch.object(GATE, 'load', side_effect=lambda name: lineage if name == 'workflow_lineage.py' else load(name)), \
                patch.object(lineage.SourceObservation, 'admit', admitted):
            # Actual merged-PR admission, physical reconciliation, job/check
            # ownership and whole-job qualification reach archive admission.
            with self.assertRaises(ReconciledOriginal): GATE.qualify(self.api, ROOT, plan)
            for variant in ('active', 'missing', 'failed', 'cancelled'):
                self.responses.clear(); self.responses.update(copy.deepcopy(original))
                inventory = self.responses[runpath + '/attempts/1/jobs?per_page=100&page=1']
                row = next(row for row in inventory['jobs'] if row['name'] == 'std / navigation')
                if variant == 'missing':
                    inventory['jobs'].remove(row); inventory['total_count'] -= 1
                elif variant == 'active':
                    row.update(status='in_progress', conclusion=None, completed_at=None)
                    row['steps'][0].update(status='in_progress', conclusion=None, completed_at=None)
                else:
                    row['conclusion'] = 'failure' if variant == 'failed' else 'cancelled'
                self.responses[self.prefix + 'check-runs/' + str(row['id'])] = fixture.check(row)
                with self.subTest(variant=variant), self.assertRaises(ValueError):
                    GATE.qualify(self.api, ROOT, plan)

    def test_live_accepted_merge_can_relax_only_its_exact_original_preview_tree(self):
        fixture = ARTIFACTS.WorkflowArtifactOwnershipTests(); fixture.setUp()
        identity, api = fixture.identity, fixture.api
        api.json_array = api.json
        base = 'd' * 40
        run = fixture.responses[fixture.paths['run']]
        run.update(status='completed', conclusion='success', event='pull_request',
                   actor=self.actor, triggering_actor=self.actor)
        pull = {'number': 17, 'merged': True, 'state': 'closed', 'merge_commit_sha': base,
                'merged_at': '2026-10-12T18:00:00Z', 'user': self.actor, 'base': {'ref': 'main', 'repo': run['repository']},
                'head': {'sha': identity['head'], 'repo': run['head_repository']}}
        fixture.responses.update({
            self.prefix + 'git/ref/heads/main': {'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': base}},
            self.prefix + 'compare/' + base + '...' + base: {'status': 'identical', 'merge_base_commit': {'sha': base}},
            self.prefix + 'compare/' + identity['head'] + '...' + base: {'status': 'ahead', 'merge_base_commit': {'sha': identity['head']}},
            self.prefix + 'commits/' + base + '/pulls?per_page=100&page=1': [pull], self.prefix + 'pulls/17': pull,
            self.prefix + 'actions/workflows/bijux-std.yml/runs?head_sha=' + identity['head'] + '&event=pull_request&per_page=100&page=1': {
                'total_count': 1, 'workflow_runs': [run]},
            self.prefix + 'git/commits/' + base: {'sha': base, 'tree': {'sha': identity['source_tree']}},
            self.prefix + 'git/trees/' + identity['source_tree'] + '?recursive=1': {
                'sha': identity['source_tree'], 'truncated': False, 'tree': []},
        })
        fixture.responses[self.prefix + 'git/commits/' + identity['head']]['tree']['sha'] = 'e' * 40
        preview = fixture.responses[self.prefix + 'git/commits/' + identity['checkout_sha']]
        preview['parents'] = [{'sha': base}, {'sha': identity['head']}]
        authority = AUTHORITY.admit_checkout(api, AUTHORITY.locate(api, base, now=NOW), identity['checkout_sha'])
        with self.assertRaisesRegex(ValueError, 'Checkout source tree mismatch'):
            ARTIFACTS.ARTIFACTS.observe(api, identity)
        observation = ARTIFACTS.ARTIFACTS.observe(api, identity, checkout_authority=authority)
        self.assertEqual(observation['identity'], identity)
        with self.assertRaises(ValueError): ARTIFACTS.ARTIFACTS.observe(api, identity, checkout_authority={'accepted_main': base})
        for variant in ('head-tree', 'preview-parent', 'preview-tree'):
            original = copy.deepcopy(fixture.responses)
            if variant == 'head-tree': fixture.responses[self.prefix + 'git/commits/' + identity['head']]['tree']['sha'] = 'f' * 40
            elif variant == 'preview-parent': preview['parents'][1]['sha'] = 'f' * 40
            else: preview['tree']['sha'] = 'f' * 40
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                ARTIFACTS.ARTIFACTS.observe(api, identity, checkout_authority=authority)
            fixture.responses.clear(); fixture.responses.update(original)
            preview = fixture.responses[self.prefix + 'git/commits/' + identity['checkout_sha']]


class PortableNativeSourceTests(unittest.TestCase):
    def setUp(self):
        AcceptedBoundaryTests.setUp(self)
        owner = ROOT / 'artifacts/qualification/accepted-native-source'; owner.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=owner); self.addCleanup(directory.cleanup)
        self.owner = Path(directory.name)
        self.current, self.original = (self.owner / name for name in ('current-source', 'original-source'))
        self.file = 'tests/unit.cjs'
        body = b"const { test } = require('node:test');\ntest('original owned native case', () => {});\n"
        for root in (self.current, self.original):
            (root / 'tests').mkdir(parents=True)
            (root / self.file).write_bytes(body)
        self.unit = self.current / self.file
        self.events = self.owner / 'original-node-events.jsonl'
        with self.events.open('w') as stream:
            subprocess.run([shutil.which('node'), '--test', '--test-reporter=' + str(ROOT / 'tests/bijux-docs/execution/node_events.cjs'),
                            str(self.original / self.file)], stdout=stream, stderr=subprocess.PIPE, check=True)
        objects = {self.file: {'mode': '100644', 'kind': 'blob',
                              'object': hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()}}
        hashes = {self.file: hashlib.sha256(body).hexdigest()}
        self.source = {'head': self.checkout, 'files': hashes,
                       'tree_sha256': hashlib.sha256(json.dumps(hashes, separators=(',', ':')).encode()).hexdigest()}
        self.objects = objects
        self.plan = {'frontend': False, 'source_objects': copy.deepcopy(objects), 'checkout': '9' * 40,
                     'baseline': self.base, 'families': ['standard', 'contracts'], 'full_verification_reasons': []}
        self.responses[self.prefix + 'git/trees/' + self.tree + '?recursive=1']['tree'][0]['sha'] = objects[self.file]['object']
        self.authority = AUTHORITY.admit_checkout(self.api, AUTHORITY.locate(self.api, self.base, now=NOW), self.checkout)

    def context(self):
        return SOURCE.admit(self.current, self.plan, self.source, self.objects, self.authority)

    def test_actual_original_native_event_bytes_qualify_in_different_current_checkout_without_rewrite(self):
        original_bytes = self.events.read_bytes()
        with patch.object(RENDERER.CONTROLS, 'ROOT', self.current):
            with self.assertRaises(ValueError): RENDERER.CONTROLS.node_cases(self.events, [self.unit], 1)
            cases = RENDERER.CONTROLS.node_cases(self.events, [self.unit], 1, self.context())
        self.assertEqual(cases[0]['id'][0], self.file)
        self.assertEqual(self.events.read_bytes(), original_bytes)
        self.assertIn(str(self.original / self.file).encode(), original_bytes)

    def test_changed_native_blob_mode_missing_unknown_or_serialized_authority_refuse(self):
        original = self.unit.read_bytes()
        for variant in ('bytes', 'mode', 'missing', 'unknown', 'serialized-authority'):
            plan = copy.deepcopy(self.plan)
            if variant == 'bytes': self.unit.write_bytes(original + b'\n')
            elif variant == 'mode': self.unit.chmod(0o755)
            elif variant == 'missing': plan['source_objects'].clear()
            elif variant == 'unknown': plan['source_objects']['unowned/source.js'] = self.objects[self.file]
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                SOURCE.admit(self.current, plan, self.source, self.objects,
                             {} if variant == 'serialized-authority' else self.authority)
            self.unit.write_bytes(original); self.unit.chmod(0o644)
        changed = copy.deepcopy(self.objects); changed[self.file]['mode'] = '100755'
        with self.assertRaises(ValueError): SOURCE.admit(self.current, self.plan, self.source, changed, self.authority)

    def test_truncated_alias_duplicate_link_git_tree_and_native_root_drift_refuse(self):
        payload = copy.deepcopy(self.responses[self.prefix + 'git/trees/' + self.tree + '?recursive=1'])
        for variant in ('truncated', 'alias', 'duplicate', 'link'):
            value = copy.deepcopy(payload)
            if variant == 'truncated': value['truncated'] = True
            elif variant == 'alias': value['tree'][0]['path'] = 'tests/../unit.cjs'
            elif variant == 'duplicate': value['tree'].append(value['tree'][0])
            else: value['tree'][0]['mode'] = '120000'
            with self.subTest(variant=variant), self.assertRaises(ValueError): SOURCE.api_tree(value, self.tree)
        context = self.context()
        context.native_relative(str(self.original / self.file), [self.unit])
        for value in ('/another/' + self.file, str(self.original / 'foreign/unit.cjs'), str(self.original) + '/tests/../tests/unit.cjs'):
            with self.assertRaises(ValueError): context.native_relative(value, [self.unit])

    def test_missing_or_invalid_proof_selects_fresh_before_jobs_and_later_revalidation_fails(self):
        for failure in ('expired original artifact', 'foreign app', 'missing catalogue owner', 'native coverage incomplete'):
            with patch.object(GATE, 'qualify', side_effect=ValueError(failure)):
                selected = GATE.select(self.current, self.plan, self.api)
            self.assertTrue(selected['frontend']); self.assertIsNone(selected['proof'])
            self.assertEqual(selected['selection_kind'], 'accepted_proof_refused_full_execution')
            results = dict.fromkeys(FRONTEND_CONTEXTS, 'success')
            receipt = require_results(self.plan, results, plan_result='success', selected_frontend=selected['frontend'])
            self.assertTrue(receipt['frontend_executed'])
        proof = {'original_workflow': {'head': self.head, 'checkout_sha': self.checkout, 'run_id': 101, 'attempt': 2},
                 'original_counts': {'browser_cases': 1}}
        with patch.object(GATE, 'qualify', return_value=proof): selected = GATE.select(self.current, self.plan, self.api)
        receipt = require_results(self.plan, dict.fromkeys(FRONTEND_CONTEXTS, 'skipped'), plan_result='success',
                                  selected_frontend=False, proof=proof)
        self.assertEqual(receipt['current_frontend_cases'], 0)
        self.assertEqual(receipt['original_proof']['original_workflow'], proof['original_workflow'])
        with patch.object(GATE, 'qualify', side_effect=ValueError('changed source proof')):
            with self.assertRaisesRegex(ValueError, 'independent required aggregate'):
                GATE.verify(self.current, self.plan, selected, 'false', self.api)
        changed = {**self.plan, 'frontend': True}
        with patch.object(GATE, 'qualify') as qualifier:
            self.assertTrue(GATE.select(self.current, changed, self.api)['frontend']); qualifier.assert_not_called()

    def test_original_artifact_materialization_requires_live_input_and_preserves_owned_body(self):
        fixture = LINEAGE.WorkflowInputLineageTests(); fixture.setUp()
        _, item = fixture.admit()
        output = self.owner / 'admitted-evidence'
        NATIVE.materialize({'complete': item}, output)
        self.assertEqual((output / 'producer-envelope.json').read_bytes(), item.read('producer-envelope.json'))
        with self.assertRaises(ValueError): NATIVE.materialize({'complete': item}, output)
        with self.assertRaises(ValueError): NATIVE.materialize({'complete': {'files': item.files}}, self.owner / 'forged-evidence')


class ConsumerPlatformBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.platform = GATE.load('proof_continuity/consumer_platform.py')
        owner = ROOT / 'artifacts/qualification/proof-platform'; owner.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=owner); self.addCleanup(directory.cleanup)
        self.workspace = Path(directory.name)
        self.node = self.workspace / 'node'; self.node.write_bytes(b'admitted Node bytes')
        self.npm = self.workspace / 'npm/bin/npm-cli.js'
        self.npm.parent.mkdir(parents=True); self.npm.write_bytes(b'admitted npm entrypoint')
        self.tools = {'node': str(self.node), 'npm': str(self.npm), 'docker': '/usr/bin/docker'}

    def test_child_runtime_observer_uses_standard_platform_with_real_installed_tools(self):
        # A child starts beside its wrapper. Import the actual package observer
        # there and read installed tool bytes without asserting producer proof.
        program = """
import json
import runpy
import sys
context = runpy.run_path(sys.argv[1])
identity = context['CONTAINER'].archive_module().IDENTITY
observed = identity.toolchain()
import platform
assert observed['platform']['system'] == platform.system()
assert observed['platform']['machine'] == platform.machine()
print(json.dumps(observed, sort_keys=True))
"""
        path = Path(self.platform.__file__)
        child = subprocess.run([sys.executable, '-B', '-c', program, str(path)],
                               cwd=path.parent, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        observed = json.loads(child.stdout.splitlines()[-1])
        node = Path(shutil.which('node')).resolve(strict=True)
        npm = Path(shutil.which('npm')).resolve(strict=True)
        self.assertEqual(observed['node_version'], subprocess.check_output([str(node), '--version'], text=True).strip())
        self.assertEqual(observed['node_sha256'], hashlib.sha256(node.read_bytes()).hexdigest())
        self.assertEqual(observed['npm_cli_sha256'], hashlib.sha256(npm.read_bytes()).hexdigest())
        self.assertEqual(observed['npm_version'], json.loads((npm.parent.parent / 'package.json').read_bytes())['version'])
        self.assertRegex(observed['npm_tree_sha256'], r'^[a-f0-9]{64}$')

    def test_live_platform_mounts_exact_tools_and_forwards_token_name_without_host_image_claim(self):
        commands = []
        def run(command, **kwargs):
            commands.append(command)
            self.assertEqual(kwargs, {'check': True})
            marker = Path(command[command.index('--child') + 1])
            marker.write_bytes(b'live-admission-completed\n')
        env = {'GH_TOKEN': 'never-print-controlled-token', 'ImageOS': 'ubuntu24', 'ImageVersion': 'foreign-host',
               'RUNNER_OS': 'Linux', 'RUNNER_ARCH': 'X64', 'GITHUB_RUN_ID': '201',
               'GITHUB_ACTOR': 'bijux', 'GITHUB_ACTOR_ID': '222414480'}
        with patch.dict(os.environ, env, clear=True), patch.object(self.platform.shutil, 'which', side_effect=self.tools.get), \
                patch.object(self.platform.subprocess, 'run', side_effect=run):
            self.platform.execute(ROOT, ['select'])
        command = commands[0]
        self.assertIn(self.platform.CONTAINER.IMAGE, command)
        self.assertIn('GH_TOKEN', command); self.assertNotIn(env['GH_TOKEN'], ' '.join(command))
        self.assertIn('GITHUB_ACTOR', command); self.assertIn('GITHUB_ACTOR_ID', command)
        self.assertNotIn(env['GITHUB_ACTOR_ID'], ' '.join(command))
        self.assertNotIn('ImageOS', ' '.join(command)); self.assertNotIn('ImageVersion', ' '.join(command))
        mounts = [command[i + 1] for i, value in enumerate(command) if value == '--mount']
        self.assertIn(f'type=bind,src={ROOT},dst={ROOT},readonly', mounts)
        self.assertIn(f'type=bind,src={ROOT / "artifacts"},dst={ROOT / "artifacts"}', mounts)
        self.assertIn(f'type=bind,src={self.node},dst=/bijux-toolchain/node,readonly', mounts)
        self.assertIn(f'type=bind,src={self.npm.parent.parent},dst=/bijux-toolchain/npm,readonly', mounts)
        self.assertIn('GIT_OPTIONAL_LOCKS=0', command)
        self.assertEqual(command[-1], 'select')

    def test_missing_tools_foreign_npm_child_failure_and_uncompleted_operation_refuse(self):
        for missing in ('docker', 'node', 'npm'):
            tools = {**self.tools, missing: None}
            with self.subTest(missing=missing), patch.object(self.platform.shutil, 'which', side_effect=tools.get), \
                    self.assertRaises(ValueError):
                self.platform.execute(ROOT, ['select'])

        self.tools['npm'] = str(self.node)
        with patch.object(self.platform.shutil, 'which', side_effect=self.tools.get), self.assertRaises(ValueError):
            self.platform.execute(ROOT, ['select'])
        self.tools['npm'] = str(self.npm)
        for action in (lambda *args, **kwargs: None,
                       self.platform.subprocess.CalledProcessError(1, ['docker'])):
            with self.subTest(action=type(action).__name__), \
                    patch.object(self.platform.shutil, 'which', side_effect=self.tools.get), \
                    patch.object(self.platform.subprocess, 'run', side_effect=action), \
                    self.assertRaises((ValueError, self.platform.subprocess.SubprocessError)):
                self.platform.execute(ROOT, ['select'])

    def test_actual_cli_launch_failure_selects_full_but_cannot_revalidate_skipped_work(self):
        from test_docs_input_planning import InputPlanningMutationTests, capture
        fixture = InputPlanningMutationTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        shutil.copytree(ROOT / 'tests/bijux-docs/execution', fixture.repo / 'tests/bijux-docs/execution',
                        dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
        fixture.commit('test(ci): own platform qualification source')
        fixture.base = fixture.git('rev-parse', 'HEAD')
        fixture.git('update-ref', 'refs/remotes/origin/main', fixture.base)
        plan = capture(fixture.repo, fixture.base, fixture.base, 'workflow_dispatch', 'accepted-proof-qualification')
        output = fixture.repo / 'artifacts/bijux-docs/input-plan'; output.mkdir(parents=True)
        (output / 'plan.json').write_text(json.dumps(plan))
        docker = self.workspace / 'docker'; docker.write_text('#!/bin/sh\nexit 17\n'); docker.chmod(0o755)
        node = self.workspace / 'bin/node'; node.parent.mkdir(); node.write_text('#!/bin/sh\nexit 0\n'); node.chmod(0o755)
        self.npm.chmod(0o755)
        (node.parent / 'npm').symlink_to(self.npm)
        env = {**os.environ, 'PATH': str(self.workspace) + os.pathsep + str(node.parent) + os.pathsep + os.environ['PATH'],
               'GITHUB_REPOSITORY': 'bijux/bijux-std', 'GITHUB_EVENT_NAME': 'workflow_dispatch',
               'GITHUB_SHA': fixture.base, 'EXPECTED_BASELINE': fixture.base, 'VERIFICATION_MODE': 'accepted-proof-qualification',
               'GITHUB_OUTPUT': str(output / 'outputs')}
        command = [sys.executable, '-B',
                   str(fixture.repo / 'tests/bijux-docs/execution/input_planning/cli.py')]
        selected = subprocess.run([*command, 'select', '--consumer-platform'], env=env, capture_output=True, text=True)
        self.assertEqual(selected.returncode, 0, selected.stderr)
        decision = json.loads((output / 'selection.json').read_bytes())
        self.assertTrue(decision['frontend']); self.assertIsNone(decision['proof'])
        self.assertEqual(decision['selection_kind'], 'accepted_proof_refused_full_execution')
        self.assertEqual((output / 'outputs').read_text(), 'frontend=true\n')
        decision.update(frontend=False, selection_kind='accepted_original_proof', proof={'status': 'passed'})
        (output / 'selection.json').write_text(json.dumps(decision))
        refused = subprocess.run([*command, 'verify', '--consumer-platform', '--accepted-proof'],
                                 env={**env, 'EXPECTED_FRONTEND': 'false'}, capture_output=True, text=True)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('consumer-platform revalidation failed', refused.stderr)
        self.assertFalse((output / 'qualification.json').exists())



if __name__ == '__main__':
    unittest.main()
