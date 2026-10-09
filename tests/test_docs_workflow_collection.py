"""Keep collection ownership, lineage and filesystem admission exact."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COLLECTION = load('workflow_collection_controls', ROOT / 'tests/bijux-docs/execution/workflow_collection.py')
FIXTURES = load('collection_artifact_fixtures', ROOT / 'tests/test_docs_workflow_artifacts.py')


class WorkflowCollectionTests(unittest.TestCase):
    def setUp(self):
        fixture = FIXTURES.WorkflowArtifactOwnershipTests()
        fixture.setUp()
        for name in ('identity', 'job', 'artifact', 'paths', 'responses', 'api', 'now'):
            setattr(self, name, getattr(fixture, name))
        self.roles = {'producer': COLLECTION.registry()['producer']}
        self.job['steps'][-1]['name'] = self.roles['producer']['upload_step']
        partitions = json.loads((ROOT / 'tests/bijux-docs/execution/browser_partitions.json').read_text())
        suites = {entry['suite'] for entries in partitions['groups'].values() for entry in entries} | {'persisted-reader-history'}
        self.producer_files = {f'inventories/{suite}{suffix}': b'{}' for suite in suites
                               for suffix in ('.json', '.json.contract.json')}
        self.producer_files.update({'browser-fixtures.tar.gz': b'archive', 'browser-fixtures.sha256': b'hash\n',
                                    'renderer-source-observation.json': b'{}'})
        self.envelope = {'source_head': self.identity['checkout_sha'], 'workflow_run_id': '123', 'workflow_attempt': '2',
                         'artifact_digests': {name: hashlib.sha256(data).hexdigest() for name, data in self.producer_files.items()
                                             if not name.endswith('.contract.json') and name != 'browser-fixtures.sha256'}}
        self.producer_files['producer-envelope.json'] = json.dumps(self.envelope, sort_keys=True).encode()
        self.bodies = {}
        self.set_body(33, self.artifact, self.producer_files)
        self.artifact['expires_at'] = '2030-01-01T00:00:00Z'
        self.api.archive = lambda artifact_id: self.bodies[artifact_id]
        # API/source fixtures are controlled; actual checkout refusal is tested
        # separately without editing tracked files during a live qualification.
        source = patch.object(COLLECTION, 'checkout_state', return_value={key: self.identity[key] for key in ('checkout_sha', 'source_tree')})
        source.start(); self.addCleanup(source.stop)

    def set_body(self, artifact_id, metadata, files):
        body = FIXTURES.archive(list(files.items()))
        self.bodies[artifact_id] = body
        metadata.update(size_in_bytes=len(body), digest='sha256:' + hashlib.sha256(body).hexdigest())

    def collection(self):
        source = COLLECTION.LINEAGE.observe_source(self.api, self.identity)
        specs = {role: {key: spec[key] for key in ('job_name', 'artifact_prefix', 'upload_step')}
                 for role, spec in self.roles.items()}
        inputs = source.admit(specs, now=self.now)
        return COLLECTION.Collection(source, inputs, self.roles, _created=COLLECTION._CREATED)

    def add_browser(self, role=None):
        role = role or next(role for role in COLLECTION.registry() if role.startswith('browser-'))
        spec = COLLECTION.registry()[role]
        self.roles[role] = spec
        job = copy.deepcopy(self.job)
        job.update(id=44, name=spec['job_name'])
        job['steps'][-1]['name'] = spec['upload_step']
        artifact = copy.deepcopy(self.artifact)
        artifact.update(id=55, name=spec['artifact_prefix'] + '-' + self.identity['checkout_sha'] + '-2')
        prefix = spec['subtree'] + '/'
        files = {prefix + 'qualification.json': b'{"native":"passed"}'}
        record = {'schema': 1, 'executor': {'role': role, 'source_head': self.identity['checkout_sha'],
                  'workflow_run_id': '123', 'workflow_attempt': '2'},
                  'producer': {**{key: self.envelope[key] for key in ('source_head', 'workflow_run_id', 'workflow_attempt', 'artifact_digests')},
                               'envelope_sha256': hashlib.sha256(self.producer_files['producer-envelope.json']).hexdigest()},
                  'files_sha256': {'qualification.json': hashlib.sha256(files[prefix + 'qualification.json']).hexdigest()}}
        files[prefix + 'execution.json'] = json.dumps(record, sort_keys=True).encode()
        self.set_body(55, artifact, files)
        self.responses[self.paths['run'] + '/jobs?filter=latest&per_page=100&page=1'] = {'total_count': 2, 'jobs': [self.job, job]}
        self.responses[self.paths['run'] + '/jobs?filter=all&per_page=100&page=1'] = {'total_count': 2, 'jobs': [self.job, job]}
        self.responses[self.paths['run'] + '/artifacts?per_page=100&page=1'] = {'total_count': 2, 'artifacts': [self.artifact, artifact]}
        self.responses['repos/bijux/bijux-std/actions/jobs/44'] = job
        self.responses['repos/bijux/bijux-std/actions/artifacts/55'] = artifact
        return role, job, artifact, files, record

    def test_registry_derives_exact_all_browser_renderer_and_fixed_roles(self):
        roles = COLLECTION.registry()
        source = (ROOT / '.github/workflows/bijux-std.yml').read_text()
        partitions = json.loads((ROOT / 'tests/bijux-docs/execution/browser_partitions.json').read_text())
        expected = {'browser-' + group + '-' + engine for group in partitions['groups'] for engine in partitions['engines']}
        self.assertEqual({role for role in roles if role.startswith('browser-')}, expected)
        renderers = load('collection_renderer_groups', ROOT / 'tests/bijux-docs/execution/renderer_controls.py')
        self.assertEqual({role for role in roles if role.startswith('renderer-')}, {'renderer-' + group for group in renderers.GROUPS})
        self.assertEqual({role for role in roles if not role.startswith(('browser-', 'renderer-'))},
                         {'producer', 'commands', 'persisted', 'fault-public'} | {'fault-' + engine for engine in partitions['engines']})
        self.assertEqual(len({spec['job_name'] for spec in roles.values()}), len(roles))
        for spec in roles.values():
            self.assertIn(spec['upload_step'], source)

    def test_complete_producer_body_materializes_and_identical_producer_reuse_is_explicit(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as folder:
            output = Path(folder) / 'collected'
            collection = COLLECTION.collect(self.api, self.identity, 'producer', output)
            self.assertEqual({str(path.relative_to(output)): path.read_bytes() for path in output.rglob('*') if path.is_file()}, self.producer_files)
            collection.materialize(output)
            self.assertEqual(collection.producer.pointer()['artifact']['id'], 33)
            self.assertEqual(collection.export_record()['collector']['attempt'], 2)

    def test_exact_actual_owner_and_producer_and_native_body_declarations_are_verified(self):
        role, _, _, _, record = self.add_browser()
        collection = self.collection()
        collection.verify_execution(role, record)
        self.assertEqual(collection.paths[role], 'shards')
        for field, value in [('schema', True), ('executor', {**record['executor'], 'workflow_attempt': '1'}),
                             ('producer', {**record['producer'], 'envelope_sha256': 'f' * 64}), ('files_sha256', {})]:
            changed = {**record, field: value}
            with self.subTest(field=field):
                with self.assertRaises(ValueError): collection.verify_execution(role, changed)

    def test_owned_forged_executor_producer_and_missing_extra_body_records_refuse(self):
        role, _, artifact, files, record = self.add_browser()
        original = copy.deepcopy(record)
        for change in ('executor', 'producer', 'missing', 'extra'):
            record = copy.deepcopy(original)
            if change == 'executor': record['executor']['workflow_attempt'] = '1'
            if change == 'producer': record['producer']['artifact_digests'] = {}
            if change == 'missing': record['files_sha256'] = {}
            if change == 'extra': record['files_sha256']['unowned.json'] = 'f' * 64
            files[self.roles[role]['subtree'] + '/execution.json'] = json.dumps(record).encode()
            self.set_body(55, artifact, files)
            collection = self.collection()
            with self.subTest(change=change):
                with self.assertRaises(ValueError): collection.verify_execution(role, record)

    def test_retained_producer_attempt_is_preserved_in_actual_native_input_declaration(self):
        role, _, artifact, files, record = self.add_browser()
        self.job['run_attempt'] = 1
        self.artifact['name'] = self.artifact['name'][:-1] + '1'
        self.envelope['workflow_attempt'] = '1'
        self.producer_files['producer-envelope.json'] = json.dumps(self.envelope, sort_keys=True).encode()
        self.set_body(33, self.artifact, self.producer_files)
        record['producer']['workflow_attempt'] = '1'
        record['producer']['envelope_sha256'] = hashlib.sha256(self.producer_files['producer-envelope.json']).hexdigest()
        files[self.roles[role]['subtree'] + '/execution.json'] = json.dumps(record).encode()
        self.set_body(55, artifact, files)
        collection = self.collection()
        collection.verify_execution(role, record)
        self.assertEqual(collection.producer.workflow_identity()['workflow_attempt'], '1')
        self.assertEqual(collection.inputs[role].workflow_identity()['workflow_attempt'], '2')

    def test_wrong_namespace_and_same_bytes_cross_owner_collision_refuse_before_writes(self):
        role, _, artifact, files, _ = self.add_browser()
        wrong = dict(files)
        wrong['another-role/index.html'] = b'unchanged'
        self.set_body(55, artifact, wrong)
        collection = self.collection()
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as folder:
            output = Path(folder)
            sentinel = output / 'previous.html'; sentinel.write_bytes(b'previous')
            with self.assertRaisesRegex(ValueError, 'namespace'): collection.materialize(output)
            self.assertEqual(list(output.iterdir()), [sentinel])
        collection = self.collection()
        collection._roles[role]['subtree'] = None
        collection._roles[role]['destination'] = ''
        collection.inputs[role]._files = {'producer-envelope.json': self.producer_files['producer-envelope.json']}
        collection.inputs[role]._hashes = {'producer-envelope.json': hashlib.sha256(self.producer_files['producer-envelope.json']).hexdigest()}
        with self.assertRaisesRegex(ValueError, 'collision'): collection.plan()

    def test_missing_or_unowned_producer_inventory_refuses_complete_output_plan(self):
        for change in ('missing', 'extra'):
            files = dict(self.producer_files)
            inventory = next(name for name in files if name.startswith('inventories/'))
            if change == 'missing': del files[inventory]
            else: files['inventories/unowned.json'] = b'{}'
            self.set_body(33, self.artifact, files)
            with self.subTest(change=change):
                with self.assertRaises(ValueError): self.collection().plan()

    def test_existing_output_collision_symlink_or_changed_producer_preserves_previous_bytes(self):
        collection = self.collection()
        for mode in ('changed', 'symlink', 'ancestor'):
            with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as folder:
                output = Path(folder) / 'collected'; output.mkdir()
                previous = Path(folder) / 'previous'; previous.write_bytes(b'previous')
                target = output / 'producer-envelope.json'
                if mode == 'changed': target.write_bytes(b'previous')
                elif mode == 'symlink': target.symlink_to(previous)
                else: (output / 'inventories').symlink_to(previous)
                with self.subTest(mode=mode):
                    with self.assertRaises(ValueError): collection.materialize(output)
                    self.assertEqual(previous.read_bytes(), b'previous')
                    self.assertEqual(len(list(output.iterdir())), 1)

    def test_complete_source_registry_collects_disjoint_body_union_and_retains_original_attempts(self):
        registry = COLLECTION.registry()
        jobs, artifacts = [self.job], [self.artifact]
        producer = {**{key: self.envelope[key] for key in ('source_head', 'workflow_run_id', 'workflow_attempt', 'artifact_digests')},
                    'envelope_sha256': hashlib.sha256(self.producer_files['producer-envelope.json']).hexdigest()}
        for index, (role, spec) in enumerate(registry.items()):
            if role == 'producer': continue
            job = copy.deepcopy(self.job)
            job.update(id=100 + index, name=spec['job_name'])
            job['steps'][-1]['name'] = spec['upload_step']
            artifact = copy.deepcopy(self.artifact)
            artifact.update(id=200 + index, name=spec['artifact_prefix'] + '-' + self.identity['checkout_sha'] + '-2')
            prefix = (spec['subtree'] + '/') if spec['subtree'] else ''
            files = {prefix + 'native.json': b'{}'}
            if role.startswith('browser-') or role == 'persisted' or (role.startswith('fault-') and role != 'fault-public'):
                record = {'schema': 1, 'executor': {'role': role, 'source_head': self.identity['checkout_sha'],
                          'workflow_run_id': '123', 'workflow_attempt': '2'}, 'producer': producer,
                          'files_sha256': {'native.json': hashlib.sha256(b'{}').hexdigest()}}
                files[prefix + 'execution.json'] = json.dumps(record).encode()
            self.set_body(artifact['id'], artifact, files)
            self.responses['repos/bijux/bijux-std/actions/jobs/' + str(job['id'])] = job
            self.responses['repos/bijux/bijux-std/actions/artifacts/' + str(artifact['id'])] = artifact
            jobs.append(job); artifacts.append(artifact)
        for query in ('latest', 'all'):
            self.responses[self.paths['run'] + '/jobs?filter=' + query + '&per_page=100&page=1'] = {'total_count': len(jobs), 'jobs': jobs}
        self.responses[self.paths['run'] + '/artifacts?per_page=100&page=1'] = {'total_count': len(artifacts), 'artifacts': artifacts}
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as folder:
            collection = COLLECTION.collect(self.api, self.identity, 'navigation', Path(folder) / 'collected')
            self.assertEqual(set(collection.inputs), set(registry))
            self.assertEqual({pointer['owner_attempt'] for pointer in collection.export_record()['admission']['inputs'].values()}, {2})
            self.assertEqual(len([call for call in self.api.calls if isinstance(call, str) and '/actions/jobs/' in call]), len(jobs))
            self.assertEqual(len([call for call in self.api.calls if isinstance(call, str) and '/actions/artifacts/' in call]), len(artifacts))
            self.assertEqual(sum('/actions/runs/' in call for call in self.api.calls if isinstance(call, str)), 12)

    def test_dirty_wrong_root_or_untracked_source_closure_cannot_consume_git_authority(self):
        # Compile the exact function independently of this class's controlled
        # source fixture patch, while retaining its real globals and subprocess.
        module = load('collection_checkout_controls', ROOT / 'tests/bijux-docs/execution/workflow_collection.py')
        def git(command, **kwargs):
            if command[1:] == ['rev-parse', '--show-toplevel']: return str(ROOT)
            if command[1:] == ['status', '--porcelain', '--untracked-files=no']: return ''
            if command[1:] == ['rev-parse', 'HEAD']: return 'b' * 40
            if command[1:] == ['rev-parse', 'HEAD^{tree}']: return 'c' * 40
            if command[1] == 'ls-files': return 'owned closure'
            raise AssertionError(command)
        with patch.object(module.subprocess, 'check_output', side_effect=git):
            self.assertEqual(module.checkout_state(), {'checkout_sha': 'b' * 40, 'source_tree': 'c' * 40})
        for mode in ('root', 'dirty', 'untracked'):
            def refused(command, **kwargs):
                if mode == 'root' and command[1:] == ['rev-parse', '--show-toplevel']: return str(ROOT.parent)
                if mode == 'dirty' and command[1] == 'status': return ' M source.py'
                if mode == 'untracked' and command[1] == 'ls-files': raise COLLECTION.subprocess.CalledProcessError(1, command)
                return git(command, **kwargs)
            with self.subTest(mode=mode), patch.object(module.subprocess, 'check_output', side_effect=refused):
                with self.assertRaises((ValueError, COLLECTION.subprocess.CalledProcessError)): module.checkout_state()

    def test_changed_source_before_materialization_refuses_without_output_writes(self):
        before = {key: self.identity[key] for key in ('checkout_sha', 'source_tree')}
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as folder:
            output = Path(folder) / 'refused'
            with patch.object(COLLECTION, 'checkout_state', side_effect=[before, {**before, 'source_tree': 'e' * 40}]):
                with self.assertRaisesRegex(ValueError, 'changed during collection'):
                    COLLECTION.collect(self.api, self.identity, 'producer', output)
            self.assertFalse(output.exists())

    def test_parallel_workflow_cannot_adopt_canonical_roles_or_context(self):
        with patch.dict(COLLECTION.os.environ, {'GITHUB_REPOSITORY': self.api.repository, 'GITHUB_RUN_ID': '123',
                        'GITHUB_RUN_ATTEMPT': '2', 'GITHUB_SHA': self.identity['checkout_sha']}):
            self.assertEqual(COLLECTION.context_from_environment(self.api, self.identity['head']), self.identity)
            self.responses[self.paths['run']]['path'] = '.github/workflows/parallel.yml'
            with self.assertRaisesRegex(ValueError, 'source-owned frontend workflow'):
                COLLECTION.context_from_environment(self.api, self.identity['head'])
        with self.assertRaisesRegex(ValueError, 'source-owned frontend workflow'):
            COLLECTION.collect(self.api, {**self.identity, 'workflow_path': '.github/workflows/parallel.yml'}, 'producer', ROOT / 'artifacts')

    def test_failed_refresh_retains_actual_superseding_api_frame_without_admission(self):
        audits = []
        original = self.api.archive
        def changed(artifact_id):
            data = original(artifact_id)
            self.responses[self.paths['run']]['run_attempt'] = 3
            return data
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as folder, patch.object(self.api, 'archive', side_effect=changed):
            output = Path(folder) / 'refused'
            with self.assertRaisesRegex(ValueError, 'superseded'):
                COLLECTION.collect(self.api, self.identity, 'producer', output, audit=audits.append)
            self.assertFalse(output.exists())
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0]['status'], 'failed')
        self.assertIsNone(audits[0]['collection'])
        frames = audits[0]['admission']['refresh_observations']
        self.assertEqual(frames[-1]['run']['run_attempt'], 3)
        self.assertNotEqual(frames[-1]['status'], 'passed')

    def test_successful_collection_audit_retains_original_executor_and_physical_plan(self):
        audits = []
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as folder:
            collected = COLLECTION.collect(self.api, self.identity, 'producer', Path(folder) / 'collected', audit=audits.append)
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0]['status'], 'admitted')
        self.assertEqual(audits[0]['collection'], collected.export_record())
        self.assertIsNotNone(audits[0]['admission']['inputs']['producer'])

    def test_unknown_stage_and_serialized_capability_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'stage'): COLLECTION.collect(self.api, self.identity, 'unknown', ROOT / 'artifacts')
        with self.assertRaisesRegex(ValueError, 'live API'): COLLECTION.Collection({}, {}, {})

    def test_executor_requires_canonical_current_authoritative_inprogress_owner(self):
        role, job, _, _, _ = self.add_browser()
        # Producer-only admission captures, but never admits, a running executor.
        job.update(status='in_progress', conclusion=None, completed_at=None)
        del self.roles[role]
        collection = self.collection()
        self.assertEqual(collection.executor_pointer(role)['workflow_attempt'], '2')
        with self.assertRaisesRegex(ValueError, 'Unknown'): collection.executor_pointer('arbitrary-environment-job')
        job['run_attempt'] = 1
        with self.assertRaises(ValueError): self.collection().executor_pointer(role)


if __name__ == '__main__':
    unittest.main()
