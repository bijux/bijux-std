"""Bind mirror admission to real accepted Git sources and immutable native evidence."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'shared/bijux-gitlab/publication/admission.py'


def zipped(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        for name, value in files.items():
            archive.writestr(name, json.dumps(value))
    return output.getvalue()


class PublicationAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'Native publication needs accepted-parent admission')
        spec = importlib.util.spec_from_file_location('bijux_publication_admission', SOURCE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.scratch = tempfile.TemporaryDirectory(dir=ROOT / 'artifacts')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.git('init', '-q', '--initial-branch=main')
        self.git('config', 'user.name', 'Bijux admission fixture')
        self.git('config', 'user.email', 'admission@example.invalid')
        self.fixture('std')

    def git(self, *arguments):
        return subprocess.check_output(['git', '-C', str(self.root), *arguments], text=True,
                                       stderr=subprocess.PIPE).strip()

    def fixture(self, name):
        self.name = name
        self.project = 88948041 if name == 'std' else 88949971
        self.project_path = 'bijux-oss/bijux-' + name
        package = self.root / 'shared/bijux-gitlab'
        package.mkdir(parents=True, exist_ok=True)
        self.unit_names = ['std / contracts'] + ['std / contracts / partition ' + str(index) for index in range(2, 7)]
        self.names = self.unit_names + ['std / prerequisite ' + str(index) for index in range(6, 82)] + ['std / report'] if name == 'std' else [
            'contracts', 'terraform-format', 'terraform-validate', 'standards', 'governance-plan']
        contracts = {value: {'operation': 'report' if value == 'std / report' else 'standard',
                             'frontend': False, 'paths': ['artifacts/gitlab/acceptance'] if value == 'std / report' else []}
                     for value in self.names}
        if name == 'std':
            for index, unit in enumerate(self.unit_names):
                contracts[unit].update(operation='contracts', args=[index])
        (package / 'pipeline.py').write_text('CONTRACT_PARTITION_COUNT = 6\ndef job_contracts(root):\n    return ' + repr(contracts) + '\n')
        (package / 'contracts.py').write_bytes((ROOT / 'shared/bijux-gitlab/contracts.py').read_bytes())
        (self.root / '.gitlab-ci.yml').write_text('fixture: accepted-parent\n')
        self.git('add', 'shared/bijux-gitlab/pipeline.py', 'shared/bijux-gitlab/contracts.py', '.gitlab-ci.yml')
        self.git('commit', '-qm', 'test(ci): declare native prerequisite ownership')
        self.sha = self.git('rev-parse', 'HEAD')
        self.env = {'GITLAB_CI': 'true', 'CI_SERVER_URL': 'https://gitlab.com',
                    'CI_PROJECT_ID': str(self.project), 'CI_PROJECT_PATH': self.project_path,
                    'CI_PIPELINE_ID': '300', 'CI_JOB_ID': '900', 'CI_JOB_NAME': 'publication / mirrors',
                    'CI_PIPELINE_SOURCE': 'parent_pipeline', 'CI_COMMIT_SHA': self.sha,
                    'CI_COMMIT_BRANCH': 'main', 'CI_COMMIT_REF_NAME': 'main',
                    'CI_COMMIT_REF_PROTECTED': 'true', 'CI_DEFAULT_BRANCH': 'main',
                    'BIJUX_PARENT_PIPELINE_ID': '200'}
        prefix = '/projects/' + str(self.project)
        self.prefix = prefix
        self.jobs = [self.job(1000 + index, value) for index, value in enumerate(self.names)]
        self.report = self.jobs[-1]['id']
        self.child = self.job(900, 'publication / mirrors', pipeline=300, status='running')
        self.mr = {'iid': 7, 'project_id': self.project, 'target_project_id': self.project,
                   'state': 'merged', 'target_branch': 'main', 'merge_commit_sha': self.sha,
                   'sha': 'a' * 40, 'diff_refs': {'head_sha': 'a' * 40}, 'draft': False,
                   'author': {'username': 'bijux'}, 'labels': ['owner-self-signoff']}
        self.responses = {
            prefix: {'id': self.project, 'path_with_namespace': self.project_path, 'default_branch': 'main'},
            prefix + '/repository/branches/main': {'name': 'main', 'protected': True, 'commit': {'id': self.sha}},
            prefix + '/pipelines/300': {'id': 300, 'project_id': self.project, 'sha': self.sha,
                                        'source': 'parent_pipeline', 'ref': 'main', 'status': 'running'},
            prefix + '/pipelines/200': {'id': 200, 'project_id': self.project, 'sha': self.sha,
                                        'source': 'push', 'ref': 'main', 'status': 'running'},
            prefix + '/pipelines/300/jobs?include_retried=true&per_page=100&page=1': [self.child],
            prefix + '/pipelines/200/jobs?include_retried=true&per_page=100&page=1': self.jobs,
            prefix + '/pipelines/200/bridges?include_retried=true&per_page=100&page=1': [
                self.job(800, 'publish / mirrors', status='running', downstream_pipeline={
                    'id': 300, 'project_id': self.project, 'sha': self.sha, 'ref': 'main'})],
            prefix + '/repository/commits/' + self.sha + '/merge_requests?per_page=100': [self.mr],
            prefix + '/merge_requests/7': self.mr,
            prefix + '/merge_requests/7/approvals': {'sha': 'a' * 40, 'approved_by': [{'user': {'username': 'bijux'}}]},
        }
        self.receipt = {'schema_version': 1, 'server_url': 'https://gitlab.com',
                        'project_id': self.project, 'project_path': self.project_path,
                        'commit_sha': self.sha, 'pipeline_id': 200, 'pipeline_source': 'push',
                        'ref': 'main', 'ref_protected': True, 'publication': {'status': 'pending'},
                        'validation': {'status': 'passed', 'jobs': {
                            row['name']: {'job_id': row['id'], 'raw_job': copy.deepcopy(row)}
                            for row in self.jobs[:-1]}}}
        self.files = {'artifacts/gitlab/acceptance/acceptance.json': self.receipt}
        self.unit_files = {}
        self.artifact_requests = []
        self.after_last_unit = None
        if name == 'std':
            universe = ['fixture.UnitCases.test_case_' + str(index) for index in (0, 1, 2, 3, 7, 8)]
            assigned = [universe[index] for index in (2, 0, 3, 5, 4, 1)]
            owners = []
            for index, unit in enumerate(self.unit_names):
                identifier = self.jobs[index]['id']
                relative = f'artifacts/gitlab/jobs/{identifier}/contracts/unit-results.json'
                self.unit_files[identifier] = {relative: {
                    'schema_version': 1, 'status': 'passed', 'source_head': self.sha,
                    'partition_count': 6, 'partition_index': index, 'universe_ids': universe,
                    'universe_sha256': hashlib.sha256(json.dumps(universe, separators=(',', ':')).encode()).hexdigest(),
                    'expected_ids': [assigned[index]], 'executed_ids': [assigned[index]],
                    'case_results': [{'id': assigned[index], 'status': 'passed'}],
                    **{key: [] for key in ('failures', 'errors', 'skips', 'expected_failures',
                                          'unexpected_successes', 'discovery_errors')}}}
                owners.append({'partition_index': index, 'job_name': unit, 'job_id': identifier,
                               'receipt_path': relative,
                               'receipt_sha256': hashlib.sha256(json.dumps(self.unit_files[identifier][relative]).encode()).hexdigest()})
            self.receipt['validation']['contract_coverage'] = {
                'schema_version': 1, 'status': 'passed', 'source_head': self.sha, 'partition_count': 6,
                'universe_ids': universe,
                'universe_sha256': hashlib.sha256(json.dumps(universe, separators=(',', ':')).encode()).hexdigest(),
                'expected_cases': 6, 'executed_cases': 6,
                'partitions': [{'partition_index': index, 'expected_cases': 1, 'executed_cases': 1} for index in range(6)],
                'provider': 'gitlab', 'server_url': 'https://gitlab.com', 'project_id': self.project,
                'project_path': self.project_path, 'pipeline_id': 200, 'native_owners': owners}
        if name == 'iac':
            identity = {'version': 1, 'project_id': str(self.project), 'project_path': self.project_path,
                        'commit': self.sha, 'pipeline_id': '200', 'job_id': str(self.report),
                        'source': 'push', 'ref': 'main', 'protected_ref': True}
            digest = hashlib.sha256((self.root / '.gitlab-ci.yml').read_bytes()).hexdigest()
            self.receipt = {**identity, 'authority': 'read-only-plan', 'status': 'planned',
                            'github_authentication': 'anonymous', 'remote_writes': False, 'application_ready': False,
                            'native_input_digests': {'.gitlab-ci.yml': digest},
                            'plan': {'commit': self.sha, 'status': 'planned', 'privileged': False,
                                     'remote_writes': False, 'input_digests': {'.gitlab-ci.yml': digest},
                                     'plan_digest': 'b' * 64, 'ruleset_plan': []}}
            self.files = {'artifacts/gitlab/context.json': {**identity, 'authority': 'validation-only'},
                          'artifacts/gitlab/governance-plan.json': self.receipt,
                          'artifacts/gitlab/github-public-reads.json': {'version': 1, 'authentication': 'anonymous',
                              'remote_writes': False, 'failures': 0, 'upstream_requests': 39, 'cache_hits': 48,
                              'request_limit': 45, 'max_seconds': 180, 'requests': []}}

    def job(self, identifier, name, *, pipeline=200, status='success', **values):
        return {'id': identifier, 'name': name, 'status': status, 'allow_failure': False,
                'ref': 'main', 'pipeline': {'id': pipeline, 'project_id': self.project, 'sha': self.sha},
                'commit': {'id': self.sha}, 'runner': {'id': 55},
                'created_at': '2026-11-15T10:00:00Z', 'started_at': '2026-11-15T10:00:01Z',
                'finished_at': '2026-11-15T10:01:00Z' if status == 'success' else None, **values}

    def admit(self, *, read=None):
        def artifact(identifier, *, pipeline_id, commit_sha):
            if (pipeline_id, commit_sha) != (200, self.sha) or identifier not in {self.report, *self.unit_files}:
                raise AssertionError('Artifact request is not bound to the actual prerequisite owner')
            self.artifact_requests.append(identifier)
            if identifier == 1005 and self.after_last_unit is not None:
                self.after_last_unit()
            return zipped(self.files if identifier == self.report else self.unit_files[identifier])
        return self.module.admit(self.root, self.env,
            read=read or (lambda path: copy.deepcopy(self.responses[path])), artifact=artifact)

    def test_completed_std_parent_and_actual_bridge_admit_only_accepted_merge_commit(self):
        record = self.admit()
        self.assertEqual(record['name'], 'bijux-std')
        self.assertEqual(record['commit_sha'], self.sha)
        self.assertEqual(record['parent_pipeline_id'], 200)
        self.assertEqual(record['report_job_id'], 1082)
        self.assertEqual(record['mr_iid'], 7)
        self.assertEqual(record['canonical_mr_url'], 'https://gitlab.com/bijux-oss/bijux-std/-/merge_requests/7')
        self.assertEqual(record['route']['github_repository_id'], 1212849789)
        self.assertEqual(record['route']['personal_gitlab_project_id'], 88949531)

    def test_publication_requires_pending_report_and_complete_requalified_unit_coverage(self):
        for key, value in [('publication', {'status': 'published'}), ('publication', None)]:
            original = self.receipt[key]
            self.receipt[key] = value
            with self.subTest(value=value), self.assertRaises(ValueError): self.admit()
            self.receipt[key] = original
        coverage = self.receipt['validation'].pop('contract_coverage')
        with self.assertRaises(ValueError): self.admit()
        self.receipt['validation']['contract_coverage'] = coverage
        self.artifact_requests = []
        self.admit()
        self.assertEqual(self.artifact_requests, [1082, 1000, 1001, 1002, 1003, 1004, 1005])

    def test_unit_case_skips_omissions_overlap_and_wrong_source_cannot_reuse_passed_report(self):
        relative = 'artifacts/gitlab/jobs/1000/contracts/unit-results.json'
        mutations = [lambda row: row['case_results'][0].update(status='skipped'),
                     lambda row: row.update(executed_ids=[], case_results=[]),
                     lambda row: row.update(expected_ids=['fixture.UnitCases.test_case_0'],
                         executed_ids=['fixture.UnitCases.test_case_0'],
                         case_results=[{'id': 'fixture.UnitCases.test_case_0', 'status': 'passed'}]),
                     lambda row: row.update(source_head='c' * 40)]
        for mutate in mutations:
            original = copy.deepcopy(self.unit_files[1000][relative])
            mutate(self.unit_files[1000][relative])
            self.receipt['validation']['contract_coverage']['native_owners'][0]['receipt_sha256'] = hashlib.sha256(
                json.dumps(self.unit_files[1000][relative]).encode()).hexdigest()
            with self.subTest(receipt=self.unit_files[1000][relative]), self.assertRaises(ValueError): self.admit()
            self.unit_files[1000][relative] = original

    def test_unit_owner_hash_path_pipeline_and_report_source_must_match_actual_evidence(self):
        coverage = self.receipt['validation']['contract_coverage']
        mutations = [lambda row: row['native_owners'][0].update(receipt_sha256='c' * 64),
                     lambda row: row['native_owners'][0].update(job_id=999),
                     lambda row: row['native_owners'][0].update(receipt_path='artifacts/unowned.json'),
                     lambda row: row.update(pipeline_id=300), lambda row: row.update(source_head='c' * 40),
                     lambda row: row['native_owners'].pop()]
        for mutate in mutations:
            original = copy.deepcopy(coverage)
            mutate(coverage)
            with self.subTest(coverage=coverage), self.assertRaises(ValueError): self.admit()
            coverage.clear(); coverage.update(original)
        self.unit_files[1000] = {}
        with self.assertRaises(ValueError): self.admit()

    def test_native_freshness_fences_run_after_the_last_unit_archive_download(self):
        endpoint = self.prefix + '/pipelines/200/jobs?include_retried=true&per_page=100&page=1'
        original = copy.deepcopy(self.responses)
        changes = [lambda: self.responses[endpoint].append(self.job(9000, self.unit_names[0])),
                   lambda: self.responses[self.prefix + '/repository/branches/main']['commit'].update(id='c' * 40),
                   lambda: self.responses[self.prefix + '/merge_requests/7'].update(labels=[])]
        for change in changes:
            self.after_last_unit = change
            with self.subTest(change=change), self.assertRaises(ValueError): self.admit()
            self.responses = copy.deepcopy(original)

    def test_iac_requires_actual_five_successes_and_all_three_anonymous_plan_receipts(self):
        self.fixture('iac')
        record = self.admit()
        self.assertEqual(record['name'], 'bijux-iac')
        self.assertEqual(record['report_job_id'], 1004)
        self.assertEqual(record['route']['github_repository_id'], 1223469411)
        self.assertEqual(record['route']['personal_gitlab_project_id'], 88950131)

    def test_noncanonical_environment_unprotected_ref_and_direct_pipeline_cannot_admit(self):
        for key, value in [('GITLAB_CI', 'false'), ('CI_PROJECT_ID', '88949531'),
                           ('CI_PROJECT_PATH', 'bijux/bijux-std'), ('CI_SERVER_URL', 'https://evil.invalid'),
                           ('CI_PIPELINE_SOURCE', 'push'), ('CI_COMMIT_REF_PROTECTED', 'false'),
                           ('CI_COMMIT_BRANCH', 'feature'), ('CI_COMMIT_REF_NAME', 'feature'),
                           ('CI_JOB_NAME', 'std / report'), ('BIJUX_PARENT_PIPELINE_ID', '0'),
                           ('CI_COMMIT_TAG', 'v1.0.0')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                original = self.env
                self.env = {**original, key: value}
                try: self.admit()
                finally: self.env = original

    def test_live_project_parent_child_branch_and_bridge_must_agree(self):
        cases = [('', 'id', 1), ('/repository/branches/main', 'protected', False),
                 ('/repository/branches/main', 'commit', {'id': 'c' * 40}),
                 ('/pipelines/200', 'source', 'merge_request_event'),
                 ('/pipelines/200', 'sha', 'c' * 40), ('/pipelines/300', 'source', 'push'),
                 ('/pipelines/300', 'ref', 'other')]
        for suffix, key, value in cases:
            original = copy.deepcopy(self.responses)
            self.responses[self.prefix + suffix][key] = value
            with self.subTest(suffix=suffix, key=key), self.assertRaises(ValueError): self.admit()
            self.responses = original
        bridge = self.responses[self.prefix + '/pipelines/200/bridges?include_retried=true&per_page=100&page=1'][0]
        bridge['downstream_pipeline']['id'] = 999
        with self.assertRaises(ValueError): self.admit()

    def test_required_job_missing_failed_skipped_or_newer_retry_cannot_reuse_success(self):
        endpoint = self.prefix + '/pipelines/200/jobs?include_retried=true&per_page=100&page=1'
        original = copy.deepcopy(self.jobs)
        for status in ('failed', 'skipped', 'manual', 'running', 'canceled'):
            self.responses[endpoint] = original + [self.job(9000, self.names[0], status=status)]
            with self.subTest(status=status), self.assertRaises(ValueError): self.admit()
        self.responses[endpoint] = original[1:]
        with self.assertRaises(ValueError): self.admit()

    def test_child_must_be_the_latest_running_physical_publication_job(self):
        endpoint = self.prefix + '/pipelines/300/jobs?include_retried=true&per_page=100&page=1'
        for changes in ({'status': 'success'}, {'id': 901}, {'name': 'unrelated'}):
            self.responses[endpoint] = [{**self.child, **changes}]
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.admit()
        self.responses[endpoint] = [self.child, self.job(901, 'publication / mirrors', pipeline=300, status='running')]
        with self.assertRaises(ValueError): self.admit()

    def test_std_acceptance_receipt_cannot_substitute_ids_source_or_protection(self):
        for key, value in [('commit_sha', 'c' * 40), ('pipeline_id', 300),
                           ('ref_protected', False), ('pipeline_source', 'merge_request_event')]:
            original = copy.deepcopy(self.receipt)
            self.receipt[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.admit()
            self.receipt.clear(); self.receipt.update(original)
        self.receipt['validation']['jobs'][self.names[0]]['job_id'] = 999
        with self.assertRaises(ValueError): self.admit()

    def test_malformed_std_validation_and_boolean_schema_cannot_admit(self):
        for value in ([], None, {'status': 'passed', 'jobs': {}}, {'status': 'failed', 'jobs': {}}):
            original = self.receipt['validation']
            self.receipt['validation'] = value
            with self.subTest(validation=value), self.assertRaises(ValueError): self.admit()
            self.receipt['validation'] = original
        self.receipt['schema_version'] = True
        with self.assertRaises(ValueError): self.admit()

    def test_std_artifact_cannot_substitute_missing_acceptance_or_unowned_files(self):
        self.files['artifacts/terraform/terraform.tfstate'] = {'sensitive': True}
        with self.assertRaises(ValueError): self.admit()
        self.files = {'artifacts/gitlab/acceptance/other.json': self.receipt}
        with self.assertRaises(ValueError): self.admit()

    def test_accepted_merge_requires_exact_merge_commit_and_owner_review(self):
        for key, value in [('merge_commit_sha', 'c' * 40), ('state', 'opened'),
                           ('labels', []), ('target_branch', 'feature'), ('draft', True)]:
            original = copy.deepcopy(self.mr)
            self.mr[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.admit()
            self.mr.clear(); self.mr.update(original)
        self.mr['author'] = {'username': 'contributor'}
        self.assertEqual(self.admit()['review'], 'owner-approved')
        self.responses[self.prefix + '/merge_requests/7/approvals']['approved_by'] = []
        with self.assertRaises(ValueError): self.admit()

    def test_dirty_tracked_source_and_wrong_checkout_fail_before_evidence_admission(self):
        (self.root / '.gitlab-ci.yml').write_text('unreviewed\n')
        with self.assertRaises(ValueError): self.admit()
        self.git('checkout', '--', '.gitlab-ci.yml')
        self.env['CI_COMMIT_SHA'] = 'c' * 40
        with self.assertRaises(ValueError): self.admit()

    def test_retry_or_branch_move_during_artifact_admission_invalidates_result(self):
        endpoint = self.prefix + '/pipelines/200/jobs?include_retried=true&per_page=100&page=1'
        count = 0
        def read(path):
            nonlocal count
            data = copy.deepcopy(self.responses[path])
            if path == endpoint:
                count += 1
                if count > 1: data.append(self.job(9000, self.names[0], status='failed'))
            return data
        with self.assertRaises(ValueError): self.admit(read=read)

    def test_successful_new_retry_branch_move_or_review_removal_invalidates_admission(self):
        for kind in ('retry', 'branch', 'review'):
            endpoint = self.prefix + {'retry': '/pipelines/200/jobs?include_retried=true&per_page=100&page=1',
                'branch': '/repository/branches/main', 'review': '/merge_requests/7'}[kind]
            count = 0
            def read(path):
                nonlocal count
                data = copy.deepcopy(self.responses[path])
                if path == endpoint:
                    count += 1
                    if count > 1:
                        if kind == 'retry': data.append(self.job(9000, self.names[0]))
                        elif kind == 'branch': data['commit']['id'] = 'c' * 40
                        else: data['labels'] = []
                return data
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.admit(read=read)

    def test_iac_receipt_missing_privileged_writing_or_wrong_source_is_refused(self):
        self.fixture('iac')
        for key, value in [('remote_writes', True), ('application_ready', True), ('status', 'failed')]:
            original = self.receipt[key]
            self.receipt[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.admit()
            self.receipt[key] = original
        self.receipt['plan']['privileged'] = True
        with self.assertRaises(ValueError): self.admit()
        self.receipt['plan']['privileged'] = False
        self.files.pop('artifacts/gitlab/context.json')
        with self.assertRaises(ValueError): self.admit()

    def test_iac_gateway_failure_or_changed_source_digest_is_not_publication_evidence(self):
        self.fixture('iac')
        self.files['artifacts/gitlab/github-public-reads.json']['failures'] = 1
        with self.assertRaises(ValueError): self.admit()
        self.files['artifacts/gitlab/github-public-reads.json']['failures'] = 0
        self.receipt['native_input_digests']['.gitlab-ci.yml'] = 'c' * 64
        with self.assertRaises(ValueError): self.admit()

    def test_iac_incomplete_native_digest_and_boolean_version_are_refused(self):
        self.fixture('iac')
        for value in (None, [], {}, {'untracked.json': 'c' * 64}):
            original = self.receipt['native_input_digests']
            self.receipt['native_input_digests'] = value
            with self.subTest(digests=value), self.assertRaises(ValueError): self.admit()
            self.receipt['native_input_digests'] = original
        self.receipt['version'] = True
        with self.assertRaises(ValueError): self.admit()

    def test_default_public_transport_rejects_unapproved_paths_without_network(self):
        reader = self.module.PublicRead()
        for path in ('https://evil.invalid', '/projects/1', '/projects/88948041/jobs/1/trace',
                     '/projects/88948041/repository/branches/feature', '/projects/88948041?token=secret'):
            with self.subTest(path=path), self.assertRaises(ValueError): reader(path)

    def test_public_metadata_rejects_truncated_inventory_even_when_a_next_page_is_declared(self):
        reader = self.module.PublicRead()
        class Response(io.BytesIO):
            status = 200
            headers = {'X-Page': '1', 'X-Next-Page': '2'}
        class Opener:
            def open(self, request, timeout): return Response(b'[]')
        reader.opener = Opener()
        with self.assertRaises(ValueError):
            reader('/projects/88948041/pipelines/200/jobs?include_retried=true&per_page=100&page=1')

    def test_public_metadata_uses_only_get_and_rejects_ambiguous_json(self):
        reader = self.module.PublicRead()
        requests = []
        class Response(io.BytesIO):
            status = 200
            headers = {}
        class Opener:
            body = b'{"id":88948041}'
            def open(self, request, timeout):
                requests.append(request)
                return Response(self.body)
        opener = Opener()
        reader.opener = opener
        self.assertEqual(reader('/projects/88948041'), {'id': 88948041})
        self.assertEqual(requests[0].full_url, 'https://gitlab.com/api/v4/projects/88948041')
        self.assertEqual(requests[0].method, 'GET')
        self.assertFalse({key.lower() for key in dict(requests[0].header_items())}
                         & {'authorization', 'private-token', 'job-token', 'cookie'})
        opener.body = b'{"id":88948041,"id":1}'
        with self.assertRaises(ValueError): reader('/projects/88948041')
