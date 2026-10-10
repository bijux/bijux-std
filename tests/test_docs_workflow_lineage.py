"""Keep retained input owners and current executors independently attributable."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from threading import Lock
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LINEAGE = load('workflow_lineage', ROOT / 'tests/bijux-docs/execution/workflow_lineage.py')
FIXTURES = load('artifact_control_fixtures', ROOT / 'tests/test_docs_workflow_artifacts.py')


class WorkflowInputLineageTests(unittest.TestCase):
    def setUp(self):
        fixture = FIXTURES.WorkflowArtifactOwnershipTests()
        fixture.setUp()
        for name in ('identity', 'roles', 'body', 'job', 'old', 'artifact', 'paths', 'responses', 'api', 'now'):
            setattr(self, name, getattr(fixture, name))
        self.bodies = {33: self.body}
        def archive(artifact_id):
            self.api.calls.append(('download', artifact_id))
            return self.bodies[artifact_id]
        self.api.archive = archive
        self.receipt = {'source_head': self.identity['checkout_sha'], 'workflow_run_id': '123', 'workflow_attempt': '2'}
        self.set_body(self.receipt)

    def set_body(self, receipt):
        self.receipt = receipt
        self.bytes = json.dumps(receipt, sort_keys=True).encode()
        self.body = FIXTURES.archive([('producer-envelope.json', self.bytes), ('site/index.html', b'<h1>Current</h1>')])
        self.bodies[33] = self.body
        self.artifact.update(digest='sha256:' + hashlib.sha256(self.body).hexdigest(), size_in_bytes=len(self.body))

    def retained(self):
        self.job['run_attempt'] = 1
        self.artifact['name'] = self.artifact['name'][:-1] + '1'
        self.set_body({**self.receipt, 'workflow_attempt': '1'})
        self.responses[self.paths['run'] + '/jobs?filter=all&per_page=100&page=1'] = {'total_count': 1, 'jobs': [self.job]}

    def observe(self):
        return LINEAGE.observe_source(self.api, self.identity)

    def admit(self):
        source = self.observe()
        return source, source.admit(self.roles, now=self.now)['fixtures']

    def test_same_attempt_metadata_and_complete_body_admission_retains_owner_identity(self):
        source, item = self.admit()
        self.assertEqual(source.identity['attempt'], 2)
        self.assertEqual(item.workflow_identity(), {'workflow_run_id': '123', 'workflow_attempt': '2'})
        self.assertEqual(item.verify_receipt('producer-envelope.json', self.bytes), self.receipt)
        self.assertEqual(item.read('site/index.html'), b'<h1>Current</h1>')
        self.assertEqual(item.pointer()['artifact']['id'], 33)

    def test_explicit_older_latest_producer_is_admitted_without_rewriting_attempt(self):
        self.retained()
        source, item = self.admit()
        self.assertEqual(item.workflow_identity()['workflow_attempt'], '1')
        self.assertEqual(source.export_record()['collector']['attempt'], 2)
        self.assertEqual(source.export_record()['inputs']['fixtures']['owner_attempt'], 1)
        self.assertEqual(item.verify_receipt('producer-envelope.json', self.bytes)['workflow_attempt'], '1')
        self.assertEqual(item.read('producer-envelope.json'), self.bytes)

    def test_ordinary_resolver_still_refuses_retained_input_without_lineage(self):
        self.retained()
        with self.assertRaisesRegex(ValueError, 'Cross-attempt'):
            LINEAGE.ARTIFACTS.select(self.api, LINEAGE.ARTIFACTS.observe(self.api, self.identity), self.roles, now=self.now)

    def test_mixed_owner_attempts_and_failed_history_remain_distinct(self):
        second = copy.deepcopy(self.job)
        second.update(id=44, name='std / native browser', run_attempt=2)
        self.retained()
        historical = {**copy.deepcopy(second), 'id': 11, 'run_attempt': 1, 'conclusion': 'cancelled'}
        self.responses[self.paths['run'] + '/jobs?filter=latest&per_page=100&page=1'] = {'total_count': 2, 'jobs': [self.job, second]}
        self.responses[self.paths['run'] + '/jobs?filter=all&per_page=100&page=1'] = {'total_count': 3, 'jobs': [self.job, historical, second]}
        self.responses['repos/bijux/bijux-std/actions/jobs/44'] = second
        source = self.observe()
        rows = source.verify_jobs([self.job['name'], second['name']])
        self.assertEqual({row['name']: row['run_attempt'] for row in rows}, {self.job['name']: 1, second['name']: 2})
        self.assertEqual(source.observation['history']['jobs'][1]['conclusion'], 'cancelled')
        source.admit(self.roles, now=self.now)
        self.assertEqual(source.export_record()['inputs']['fixtures']['owner_attempt'], 1)

    def test_changed_receipt_attempt_or_source_in_an_owned_artifact_is_not_qualified(self):
        self.retained()
        for key, value in [('workflow_attempt', '2'), ('workflow_run_id', '124'), ('source_head', 'e' * 40)]:
            with self.subTest(key=key):
                self.set_body({'source_head': self.identity['checkout_sha'], 'workflow_run_id': '123',
                               'workflow_attempt': '1', key: value})
                _, item = self.admit()
                with self.assertRaises(ValueError): item.verify_receipt('producer-envelope.json', self.bytes)

    def test_unchanged_renderer_receipt_keeps_nested_workflow_and_both_source_fences(self):
        self.retained()
        receipt = {'workflow': {'workflow_run_id': '123', 'workflow_attempt': '1'},
                   'source_before': {'head': self.identity['checkout_sha']}, 'source_after': {'head': self.identity['checkout_sha']}}
        self.set_body(receipt)
        _, item = self.admit()
        self.assertEqual(item.verify_receipt('producer-envelope.json', self.bytes, workflow_path=('workflow',),
                                            source_paths=(('source_before', 'head'), ('source_after', 'head'))), receipt)

    def test_changed_member_missing_extra_receipt_or_pointer_cannot_be_admitted(self):
        self.retained(); _, item = self.admit()
        for name, data in [('producer-envelope.json', self.bytes + b' '), ('unowned.json', self.bytes)]:
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, 'member differs'): item.verify_file(name, data)
        pointer = item.pointer(); item.verify_pointer(pointer)
        for key, value in [('owner_attempt', 2), ('owner_job_id', 99), ('files_sha256', 'f' * 64),
                           ('source_head', 'e' * 40), ('role', 'unowned'), ('schema', True), ('workflow_run_id', 123.0)]:
            with self.subTest(key=key):
                changed = {**pointer, key: value}
                with self.assertRaisesRegex(ValueError, 'does not name'): item.verify_pointer(changed)
        with self.assertRaisesRegex(ValueError, 'Unowned'): item.read('extra.json')

    def test_one_admission_reuses_verified_body_without_repeated_transport(self):
        source, item = self.admit()
        before = len([call for call in self.api.calls if isinstance(call, tuple) and call[0] == 'download'])
        again = source.admit(self.roles, now=self.now)['fixtures']
        self.assertIs(item, again)
        self.assertEqual(len([call for call in self.api.calls if isinstance(call, tuple) and call[0] == 'download']), before)
        again.verify_file('site/index.html', b'<h1>Current</h1>')

    def test_input_pointer_is_independent_of_later_collector_attempt(self):
        self.retained(); _, prior = self.admit()
        self.identity['attempt'] = 3; self.responses[self.paths['run']]['run_attempt'] = 3
        source, current = self.admit()
        self.assertEqual(source.identity['attempt'], 3)
        current.verify_pointer(prior.pointer())
        self.assertEqual(current.workflow_identity()['workflow_attempt'], '1')

    def test_api_created_capabilities_cannot_be_recreated_from_audit_records(self):
        source, item = self.admit()
        record = source.export_record()
        with self.assertRaisesRegex(ValueError, 'live API'): LINEAGE.SourceObservation(self.api, record)
        with self.assertRaisesRegex(ValueError, 'API source'): LINEAGE.ArtifactInput(item.pointer(), {})
        record['collector']['head'] = 'e' * 40
        self.assertEqual(source.identity['head'], 'a' * 40)
        snapshot = source.observation; snapshot['latest']['jobs'][0]['conclusion'] = 'failure'
        self.assertEqual(source.observation['latest']['jobs'][0]['conclusion'], 'success')

    def test_latest_failed_cancelled_or_pending_owner_never_falls_back_to_old_success(self):
        self.old['conclusion'] = 'success'
        for status, conclusion in [('completed', 'failure'), ('completed', 'cancelled'), ('queued', None), ('in_progress', None)]:
            with self.subTest(status=status, conclusion=conclusion):
                self.job.update(status=status, conclusion=conclusion)
                with self.assertRaisesRegex(ValueError, 'terminal-success'): self.admit()
        self.assertFalse(any(isinstance(call, tuple) and call[0] == 'download' for call in self.api.calls))

    def test_authoritative_per_job_source_change_and_missing_latest_owner_refuse(self):
        source = self.observe()
        self.responses[self.paths['job']] = {**self.job, 'head_sha': 'e' * 40}
        with self.assertRaisesRegex(ValueError, 'Authoritative job differs'): source.verify_jobs([self.job['name']])
        with self.assertRaisesRegex(ValueError, 'Missing source-owned'): source.verify_jobs(['unowned job'])

    def test_new_owner_after_cached_verification_cannot_survive_reuse(self):
        source = self.observe(); source.verify_jobs([self.job['name']])
        self.responses[self.paths['run'] + '/jobs?filter=latest&per_page=100&page=1'] = {'total_count': 1,
             'jobs': [{**self.job, 'id': 44, 'conclusion': 'failure'}]}
        with self.assertRaisesRegex(ValueError, 'latest execution changed'): source.verify_jobs([self.job['name']])
        frame = source.export_record()['refresh_observations'][-1]
        self.assertEqual(frame['run']['id'], 123)
        self.assertEqual(frame['latest']['jobs'][0]['id'], 44)
        self.assertEqual(frame['latest']['jobs'][0]['conclusion'], 'failure')
        self.assertEqual(frame['status'], 'observing')

    def test_new_run_or_latest_owner_during_body_transport_refuses_entire_admission(self):
        source = self.observe()
        original = self.api.archive
        def changed(artifact_id):
            data = original(artifact_id)
            self.responses[self.paths['run']]['run_attempt'] = 3
            return data
        self.api.archive = changed
        with self.assertRaisesRegex(ValueError, 'superseded or changed'): source.admit(self.roles, now=self.now)
        self.assertEqual(source.export_record()['inputs'], {})
        frame = source.export_record()['refresh_observations'][-1]
        self.assertEqual(frame['run']['run_attempt'], 3)
        self.assertIsNone(frame['latest'])

    def test_refresh_history_is_bounded_and_never_discards_failed_frames(self):
        source = self.observe()
        for _ in range(LINEAGE.MAX_REFRESHES): source.refresh([self.job['name']])
        with self.assertRaisesRegex(ValueError, 'observation limit'): source.refresh([self.job['name']])
        self.assertEqual(len(source.export_record()['refresh_observations']), LINEAGE.MAX_REFRESHES)

    def test_changed_zip_digest_expiry_or_strict_job_budget_rejects_before_body_use(self):
        self.retained()
        self.bodies[33] = b'x' + self.body[1:]
        with self.assertRaisesRegex(ValueError, 'digest mismatch'): self.admit()
        self.bodies[33] = self.body
        self.artifact['expired'] = True
        with self.assertRaisesRegex(ValueError, 'expired'): self.admit()
        self.artifact['expired'] = False; self.job['completed_at'] = '2026-01-01T00:04:00Z'
        with self.assertRaisesRegex(ValueError, '180-second'): self.admit()

    def test_wrong_run_head_ref_tree_workflow_and_future_attempt_refuse_at_factory(self):
        baseline = copy.deepcopy(self.responses)
        for key, value in [('id', 124), ('head_sha', 'e' * 40), ('head_branch', 'main'), ('workflow_id', 457)]:
            with self.subTest(key=key):
                self.responses.clear(); self.responses.update(copy.deepcopy(baseline)); self.responses[self.paths['run']][key] = value
                with self.assertRaisesRegex(ValueError, 'identity mismatch'): self.observe()
        self.responses.clear(); self.responses.update(copy.deepcopy(baseline))
        self.responses['repos/bijux/bijux-std/git/commits/' + 'b' * 40]['tree']['sha'] = 'e' * 40
        with self.assertRaisesRegex(ValueError, 'source tree'): self.observe()
        self.responses.clear(); self.responses.update(copy.deepcopy(baseline))
        self.responses[self.paths['run'] + '/jobs?filter=all&per_page=100&page=1']['jobs'][0]['run_attempt'] = 3
        with self.assertRaisesRegex(ValueError, 'History'): self.observe()

    def test_duplicate_role_alias_and_changed_source_owner_cannot_supply_inputs(self):
        source = self.observe()
        source.admit(self.roles, now=self.now)
        with self.assertRaisesRegex(ValueError, 'Duplicate source-owned'):
            source.admit({'alias': dict(self.roles['fixtures'])}, now=self.now)
        with self.assertRaisesRegex(ValueError, 'changed its source ownership'):
            source.admit({'fixtures': {**self.roles['fixtures'], 'artifact_prefix': 'unowned'}}, now=self.now)

    def test_authoritative_jobs_are_bounded_concurrent_cached_and_history_preserving(self):
        jobs = [{**copy.deepcopy(self.job), 'id': 100 + index, 'name': 'source-owned-' + str(index)} for index in range(8)]
        self.responses[self.paths['run'] + '/jobs?filter=latest&per_page=100&page=1'] = {'total_count': 8, 'jobs': jobs}
        self.responses[self.paths['run'] + '/jobs?filter=all&per_page=100&page=1'] = {'total_count': 8, 'jobs': jobs}
        for row in jobs: self.responses['repos/bijux/bijux-std/actions/jobs/' + str(row['id'])] = row
        original = self.api.json; lock = Lock(); active = maximum = 0
        def delayed(endpoint):
            nonlocal active, maximum
            if '/actions/jobs/' not in endpoint: return original(endpoint)
            with lock: active += 1; maximum = max(maximum, active)
            try:
                time.sleep(.025)
                return original(endpoint)
            finally:
                with lock: active -= 1
        self.api.json = delayed
        source = self.observe(); names = [row['name'] for row in jobs]
        observed = source.verify_jobs(names, workers=4)
        self.assertEqual(len(observed), 8)
        self.assertTrue(2 <= maximum <= 4)
        calls = len([call for call in self.api.calls if isinstance(call, str) and '/actions/jobs/' in call])
        source.verify_jobs(names, workers=4)
        self.assertEqual(len([call for call in self.api.calls if isinstance(call, str) and '/actions/jobs/' in call]), calls)
        self.assertEqual(len(source.export_record()['observation']['history']['jobs']), 8)
        with self.assertRaisesRegex(ValueError, 'concurrency'): source.verify_jobs(names, workers=9)


class WorkflowCollectionObservationTests(unittest.TestCase):
    set_body = WorkflowInputLineageTests.set_body
    observe = WorkflowInputLineageTests.observe

    def setUp(self):
        WorkflowInputLineageTests.setUp(self)

    def test_unrelated_lifecycle_transition_preserves_identity_without_qualifying_changed_needed_owner(self):
        unrelated = {**copy.deepcopy(self.job), 'id': 44, 'name': 'independent owner', 'status': 'in_progress',
                     'conclusion': None, 'completed_at': None}
        finished = {**copy.deepcopy(unrelated), 'status': 'completed', 'conclusion': 'success',
                    'completed_at': self.job['completed_at']}
        self.responses[self.paths['run'] + '/jobs?filter=latest&per_page=100&page=1'] = {'total_count': 2, 'jobs': [self.job, unrelated]}
        self.responses[self.paths['run'] + '/jobs?filter=all&per_page=100&page=1'] = {'total_count': 2, 'jobs': [self.job, finished]}
        self.responses['repos/bijux/bijux-std/actions/jobs/44'] = finished
        source = self.observe()
        source.admit(self.roles, now=self.now)
        self.assertEqual(source.observation['latest']['jobs'][1]['status'], 'in_progress')
        self.assertEqual(source.observation['history']['jobs'][1]['conclusion'], 'success')
        with self.assertRaisesRegex(ValueError, 'Authoritative job differs'): source.verify_jobs([unrelated['name']])
        unrelated['head_sha'] = 'e' * 40
        with self.assertRaisesRegex(ValueError, 'differs from complete history'): self.observe()

    def test_current_report_lifecycle_can_evolve_but_new_owner_and_artifact_roles_cannot(self):
        latest = {**copy.deepcopy(self.job), 'id': 44, 'name': 'std / report', 'status': 'in_progress',
                  'conclusion': None, 'completed_at': None}
        authoritative = {**copy.deepcopy(latest), 'steps': [*latest['steps'], {'name': 'Observe budgets', 'status': 'in_progress', 'conclusion': None}]}
        self.responses[self.paths['run'] + '/jobs?filter=latest&per_page=100&page=1'] = {'total_count': 2, 'jobs': [self.job, latest]}
        self.responses[self.paths['run'] + '/jobs?filter=all&per_page=100&page=1'] = {'total_count': 2, 'jobs': [self.job, authoritative]}
        self.responses['repos/bijux/bijux-std/actions/jobs/44'] = authoritative
        source = self.observe()
        self.assertEqual(source.verify_jobs(['std / report'])[0], authoritative)
        authoritative.update(status='completed', conclusion='success', completed_at=self.job['completed_at'])
        self.responses[self.paths['run'] + '/jobs?filter=latest&per_page=100&page=1']['jobs'][1] = authoritative
        self.assertEqual(source.verify_jobs(['std / report'])[0]['conclusion'], 'success')
        self.assertEqual(len(source.export_record()['current_report_observations']), 2)
        self.assertEqual(source.observation['latest']['jobs'][1]['status'], 'in_progress')
        for key, value in [('id', 55), ('run_attempt', 1), ('head_sha', 'e' * 40)]:
            with self.subTest(key=key):
                self.responses['repos/bijux/bijux-std/actions/jobs/44'] = {**authoritative, key: value}
                with self.assertRaisesRegex(ValueError, 'report execution identity'): source.verify_jobs(['std / report'])
        self.responses['repos/bijux/bijux-std/actions/jobs/44'] = authoritative
        self.responses[self.paths['job']] = {**self.job, 'steps': []}
        with self.assertRaisesRegex(ValueError, 'Authoritative job differs'): source.verify_jobs([self.job['name']])

    def test_exact_needed_artifact_metadata_is_parallel_and_cached_before_pin_verification(self):
        jobs, artifacts, roles = [], [], {}
        for index in range(8):
            job = {**copy.deepcopy(self.job), 'id': 100 + index, 'name': 'native-' + str(index)}
            artifact = {**copy.deepcopy(self.artifact), 'id': 200 + index,
                        'name': 'native-' + str(index) + '-' + self.identity['checkout_sha'] + '-2'}
            jobs.append(job); artifacts.append(artifact)
            roles['native-' + str(index)] = {**self.roles['fixtures'], 'job_name': job['name'], 'artifact_prefix': 'native-' + str(index)}
            self.responses['repos/bijux/bijux-std/actions/jobs/' + str(job['id'])] = job
            self.responses['repos/bijux/bijux-std/actions/artifacts/' + str(artifact['id'])] = artifact
            self.bodies[artifact['id']] = self.body
        self.responses[self.paths['run'] + '/jobs?filter=latest&per_page=100&page=1'] = {'total_count': 8, 'jobs': jobs}
        self.responses[self.paths['run'] + '/jobs?filter=all&per_page=100&page=1'] = {'total_count': 8, 'jobs': jobs}
        self.responses[self.paths['run'] + '/artifacts?per_page=100&page=1'] = {'total_count': 8, 'artifacts': artifacts}
        original = self.api.json; lock = Lock(); active = maximum = 0
        def delayed(endpoint):
            nonlocal active, maximum
            if '/actions/artifacts/' not in endpoint: return original(endpoint)
            with lock: active += 1; maximum = max(maximum, active)
            try:
                time.sleep(.025)
                return original(endpoint)
            finally:
                with lock: active -= 1
        self.api.json = delayed
        source = self.observe(); admitted = source.admit(roles, workers=4, now=self.now)
        self.assertEqual(len(admitted), 8)
        self.assertTrue(2 <= maximum <= 4)
        self.assertEqual(len([call for call in self.api.calls if isinstance(call, str) and '/actions/artifacts/' in call]), 8)
        source.admit(roles, workers=4, now=self.now)
        self.assertEqual(len([call for call in self.api.calls if isinstance(call, str) and '/actions/artifacts/' in call]), 8)

    def test_compressed_union_and_expanded_union_are_bounded_before_any_input_admission(self):
        source = self.observe()
        from unittest.mock import patch
        with patch.object(LINEAGE, 'MAX_INPUT_ARCHIVE_BYTES', len(self.body) - 1):
            with self.assertRaises(ValueError): source.admit(self.roles, now=self.now)
        self.assertEqual(source.export_record()['inputs'], {})
        source = self.observe()
        with patch.object(LINEAGE.ARTIFACTS, 'MAX_EXPANDED_BYTES', 1):
            with self.assertRaisesRegex(ValueError, 'Expanded'): source.admit(self.roles, now=self.now)
        self.assertEqual(source.export_record()['inputs'], {})


if __name__ == '__main__':
    unittest.main()
