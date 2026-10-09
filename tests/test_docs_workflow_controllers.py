"""Keep execution declarations and live retained-input authority separate."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTROLLERS = load('tested_workflow_controllers', ROOT / 'tests/bijux-docs/execution/workflow_controllers.py')
GATE = load('tested_workflow_controller_browser', ROOT / 'tests/bijux-docs/execution/browser_gate.py')
RENDERER_TESTS = load('workflow_renderer_fixtures', ROOT / 'tests/test_docs_renderer_controls.py')
COLLECTION_TESTS = load('workflow_collection_fixtures', ROOT / 'tests/test_docs_workflow_collection.py')


class ExecutionDeclarationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=ROOT / 'artifacts')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.role = 'browser-navigation-phone-chromium'
        self.folder = self.root / 'shards/navigation-phone-chromium'
        self.folder.mkdir(parents=True)
        (self.folder / 'qualification.json').write_text('{"controlled": "terminal-success"}\n')
        self.producer = {'source_head': 'a' * 40, 'workflow_run_id': '123', 'workflow_attempt': '1',
                         'artifact_digests': {'browser-fixtures.tar.gz': 'b' * 64}}
        self.write_producer()
        for context in (patch.object(CONTROLLERS, 'ARTIFACTS', self.root),
                        patch.object(CONTROLLERS.subprocess, 'check_output', return_value='a' * 40),
                        patch.dict(os.environ, {'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2'}, clear=True)):
            context.start()
            self.addCleanup(context.stop)

    def write_producer(self):
        (self.root / 'producer-envelope.json').write_text(json.dumps(self.producer) + '\n')

    def declare(self):
        return CONTROLLERS.record_execution(self.folder, self.role, self.producer)

    def test_original_producer_attempt_and_actual_executor_are_preserved(self):
        record = self.declare()
        self.assertEqual(record['executor'], {'role': self.role, 'source_head': 'a' * 40,
                         'workflow_run_id': '123', 'workflow_attempt': '2'})
        self.assertEqual(record['producer']['workflow_attempt'], '1')
        self.assertEqual(record['producer']['envelope_sha256'],
                         hashlib.sha256((self.root / 'producer-envelope.json').read_bytes()).hexdigest())
        self.assertEqual(record['files_sha256'], {'qualification.json':
                         hashlib.sha256((self.folder / 'qualification.json').read_bytes()).hexdigest()})
        self.assertEqual(json.loads((self.folder / 'execution.json').read_text()), record)

    def test_ordinary_same_attempt_declaration_has_no_network_admission(self):
        os.environ['GITHUB_RUN_ATTEMPT'] = '1'
        with patch.object(CONTROLLERS, 'collect', side_effect=AssertionError('Unexpected live recovery')):
            self.assertEqual(self.declare()['executor']['workflow_attempt'], '1')

    def test_local_nonworkflow_runs_keep_existing_artifact_layout(self):
        os.environ.clear()
        with patch.object(CONTROLLERS, 'load', side_effect=AssertionError('Unexpected admission import')):
            self.assertIsNone(self.declare())
        self.assertFalse((self.folder / 'execution.json').exists())

    def test_invalid_execution_run_or_attempt_refuses_before_output(self):
        for variable in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'):
            for value in ('', '0', '-1', '1.0', '01', 'previous'):
                with self.subTest(variable=variable, value=value), patch.dict(os.environ, {variable: value}):
                    with self.assertRaises(ValueError):
                        self.declare()
                    self.assertFalse((self.folder / 'execution.json').exists())

    def test_foreign_source_run_or_newer_producer_refuses_before_output(self):
        baseline = copy.deepcopy(self.producer)
        for key, value in [('source_head', 'c' * 40), ('workflow_run_id', '124'),
                           ('workflow_attempt', '3'), ('workflow_attempt', None)]:
            self.producer = {**baseline, key: value}
            self.write_producer()
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.declare()
            self.assertFalse((self.folder / 'execution.json').exists())

    def test_changed_physical_producer_cannot_hide_behind_retained_mapping(self):
        (self.root / 'producer-envelope.json').write_text(json.dumps({**self.producer, 'workflow_attempt': '2'}))
        with self.assertRaisesRegex(ValueError, 'Physical producer'):
            self.declare()
        self.assertFalse((self.folder / 'execution.json').exists())

    def test_existing_declaration_is_preserved(self):
        self.declare()
        before = (self.folder / 'execution.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'Preserve existing'):
            self.declare()
        self.assertEqual((self.folder / 'execution.json').read_bytes(), before)

    def test_unknown_role_and_same_count_owner_substitution_refuse(self):
        for role in ('browser-unknown-chromium', 'browser-navigation-phone-firefox', 'producer', 'fault-public'):
            with self.subTest(role=role), self.assertRaises(ValueError):
                CONTROLLERS.record_execution(self.folder, role, self.producer)
        self.assertFalse((self.folder / 'execution.json').exists())

    def test_symlinked_owned_member_is_not_a_physical_execution_body(self):
        (self.folder / 'link').symlink_to(self.root / 'producer-envelope.json')
        with self.assertRaisesRegex(ValueError, 'links'):
            self.declare()
        self.assertFalse((self.folder / 'execution.json').exists())

    def test_role_destination_cannot_traverse_an_ancestor_link(self):
        actual = self.root / 'actual-shards'
        (self.root / 'shards').rename(actual)
        (self.root / 'shards').symlink_to(actual, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'traverse links'):
            self.declare()
        self.assertFalse((actual / self.folder.name / 'execution.json').exists())

    def test_serialized_or_foreign_collection_never_grants_authority(self):
        class Collection:
            pass
        for value in ({'status': 'passed', 'inputs': {}}, Collection(), object()):
            with self.subTest(value=type(value).__name__), self.assertRaisesRegex(ValueError, 'API-created'):
                CONTROLLERS.verify_execution(value, self.role, self.folder)

    def test_serialized_producer_never_grants_retained_input_authority(self):
        with patch.object(GATE, 'ARTIFACTS', self.root), self.assertRaisesRegex(ValueError, 'API-created'):
            GATE.verify_producer_envelope(self.producer)


class RecoverySelectionTests(unittest.TestCase):
    def test_normal_local_and_consumer_paths_do_not_select_recovery(self):
        for repository, attempt in [('bijux/bijux-std', '1'), ('bijux/bijux-core', '2'), ('', '2')]:
            with self.subTest(repository=repository, attempt=attempt), patch.dict(os.environ,
                    {'GITHUB_REPOSITORY': repository, 'GITHUB_RUN_ATTEMPT': attempt}, clear=True):
                self.assertFalse(CONTROLLERS.recovery())

    def test_owning_repository_positive_later_attempt_selects_recovery(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'bijux/bijux-std', 'GITHUB_RUN_ATTEMPT': '2'}, clear=True):
            self.assertTrue(CONTROLLERS.recovery())

    def test_malformed_attempt_cannot_select_a_legacy_bypass(self):
        for attempt in ('0', '-1', '', 'previous', '01'):
            with self.subTest(attempt=attempt), patch.dict(os.environ,
                    {'GITHUB_REPOSITORY': 'bijux/bijux-std', 'GITHUB_RUN_ATTEMPT': attempt}, clear=True):
                with self.assertRaisesRegex(ValueError, 'positive'):
                    CONTROLLERS.recovery()

    def test_recovery_requires_explicit_readonly_token_and_actual_head(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'bijux/bijux-std', 'GITHUB_RUN_ATTEMPT': '2'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'token'):
                CONTROLLERS.collect('producer')
            os.environ['GH_TOKEN'] = 'controlled-token'
            with self.assertRaisesRegex(ValueError, 'source SHA'):
                CONTROLLERS.collect('producer')


class RendererAttemptIdentityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = RENDERER_TESTS.RendererControlReceiptTests('test_grouped_native_results_cover_all_python_and_node_controls')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.controls = RENDERER_TESTS.CONTROLS
        self.output = self.fixture.grouped_receipts()
        self.workflows = {group: dict(self.fixture.workflow) for group in self.controls.GROUPS}

    def test_mixed_original_renderer_attempts_keep_complete_native_union(self):
        selected = self.controls.GROUPS[-1]
        receipt = self.output / selected / 'renderer-controls.json'
        data = json.loads(receipt.read_text())
        data['workflow']['workflow_attempt'] = '2'
        receipt.write_text(json.dumps(data))
        self.workflows[selected]['workflow_attempt'] = '2'
        actual = self.controls.verify_groups(self.output, self.fixture.source, self.fixture.workflow, workflows=self.workflows)
        self.assertEqual(actual['input_workflows'], self.workflows)
        self.assertEqual(actual['groups'][selected]['workflow']['workflow_attempt'], '2')
        self.assertEqual(actual['python_executed'], len(self.controls.expected_python_ids()))

    def test_missing_extra_or_wrong_typed_admitted_workflow_refuses_union(self):
        for change in ('missing', 'extra', 'numeric', 'zero'):
            workflows = copy.deepcopy(self.workflows)
            if change == 'missing':
                workflows.pop(self.controls.GROUPS[0])
            elif change == 'extra':
                workflows['unexpected'] = {'workflow_run_id': '123', 'workflow_attempt': '1'}
            else:
                workflows[self.controls.GROUPS[0]]['workflow_attempt'] = 1 if change == 'numeric' else '0'
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.controls.verify_groups(self.output, self.fixture.source, self.fixture.workflow, workflows=workflows)

    def test_self_consistent_relabelled_renderer_receipt_cannot_choose_its_owner(self):
        selected = self.controls.GROUPS[0]
        receipt = self.output / selected / 'renderer-controls.json'
        data = json.loads(receipt.read_text())
        data['workflow']['workflow_attempt'] = '2'
        receipt.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'source/workflow'):
            self.controls.verify_groups(self.output, self.fixture.source, self.fixture.workflow, workflows=self.workflows)


class AdmittedControllerInputsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = COLLECTION_TESTS.WorkflowCollectionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.role, _, _, _, self.record = self.fixture.add_browser()
        self.collection = self.fixture.collection()
        temporary = tempfile.TemporaryDirectory(dir=ROOT / 'artifacts')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.collection.materialize(self.root)
        spec = self.fixture.roles[self.role]
        self.folder = self.root / spec['destination'] / spec['subtree']

    def test_captured_byte_factory_types_keep_actual_admission_and_physical_checks(self):
        CONTROLLERS.require_collection(self.collection)
        self.assertEqual(CONTROLLERS.verify_execution(self.collection, self.role, self.folder), self.record)
        with patch.object(GATE, 'ARTIFACTS', self.root), patch.object(GATE.subprocess, 'check_output',
                return_value=self.fixture.identity['checkout_sha']), patch.dict(os.environ,
                {'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '3'}, clear=True):
            # This controlled API fixture is intentionally missing the separate
            # browser partition duty. Valid factory classes must reach that
            # duty rather than fail Python module registration introspection.
            with self.assertRaisesRegex(ValueError, 'partition registry mismatch'):
                GATE.verify_producer_envelope(self.collection.producer)

    def test_changed_materialized_native_body_cannot_hide_behind_api_admission(self):
        (self.folder / 'qualification.json').write_text('{"counterfactual":"changed"}')
        with self.assertRaisesRegex(ValueError, 'Materialized execution body'):
            CONTROLLERS.verify_execution(self.collection, self.role, self.folder)

    def test_changed_physical_declaration_cannot_choose_another_execution(self):
        record = copy.deepcopy(self.record)
        record['executor']['workflow_attempt'] = '1'
        (self.folder / 'execution.json').write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, 'differs from admitted'):
            CONTROLLERS.verify_execution(self.collection, self.role, self.folder)

    def test_semantically_identical_whitespace_or_duplicate_key_cannot_change_owned_record_bytes(self):
        original = (self.folder / 'execution.json').read_bytes()
        changed = [original + b'\n', original.replace(b'"schema": 1', b'"schema": 1, "schema": 1')]
        for data in changed:
            with self.subTest(data=data[-30:]):
                self.assertEqual(json.loads(data), json.loads(original))
                (self.folder / 'execution.json').write_bytes(data)
                with self.assertRaisesRegex(ValueError, 'differs from admitted'):
                    CONTROLLERS.verify_execution(self.collection, self.role, self.folder)


if __name__ == '__main__':
    unittest.main()
