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
import tempfile
import unittest
from unittest.mock import patch

import test_docs_workflow_artifacts as ARTIFACTS
import test_docs_workflow_lineage as LINEAGE
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
        pull = {'number': 17, 'merged': True, 'state': 'closed', 'merge_commit_sha': self.base,
                'merged_at': '2026-10-12T18:00:00Z', 'base': {'ref': 'main', 'repo': repo},
                'head': {'sha': self.head, 'ref': 'ci/owned-source', 'repo': repo}}
        self.run = {'id': 101, 'run_attempt': 2, 'head_sha': self.head, 'status': 'completed',
                    'conclusion': 'success', 'event': 'pull_request', 'repository': repo,
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

    def test_live_accepted_merge_can_relax_only_its_exact_original_preview_tree(self):
        fixture = ARTIFACTS.WorkflowArtifactOwnershipTests(); fixture.setUp()
        identity, api = fixture.identity, fixture.api
        api.json_array = api.json
        base = 'd' * 40
        run = fixture.responses[fixture.paths['run']]
        run.update(status='completed', conclusion='success', event='pull_request')
        pull = {'number': 17, 'merged': True, 'state': 'closed', 'merge_commit_sha': base,
                'merged_at': '2026-10-12T18:00:00Z', 'base': {'ref': 'main', 'repo': run['repository']},
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


if __name__ == '__main__':
    unittest.main()
