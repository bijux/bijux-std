"""Reject incomplete, nonpassing or relabeled independent renderer controls."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('renderer_controls', ROOT / 'tests/bijux-docs/execution/renderer_controls.py')
CONTROLS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLS)


class RendererControlReceiptTests(unittest.TestCase):
    def setUp(self):
        owner = ROOT / 'artifacts/qualification/renderer-control-receipt-tests'
        owner.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=owner)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.unit = self.root / 'unit.test.cjs'
        self.unit.write_text("const { test } = require('node:test');\ntest('first owned result', () => {});\ntest('second owned result', () => {});\n")
        self.events = self.root / 'node-events.jsonl'
        reporter = ROOT / 'tests/bijux-docs/execution/node_events.cjs'
        with self.events.open('w') as stream:
            subprocess.run([shutil.which('node') or 'node', '--test', '--test-reporter=' + str(reporter),
                            str(self.unit)], stdout=stream, stderr=subprocess.PIPE, check=True)
        self.patches = [mock.patch.object(CONTROLS, 'NODE_TEST_COUNT', 2),
                        mock.patch.object(CONTROLS, 'node_files', return_value=[self.unit])]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.source = {'head': 'a' * 40, 'tree_sha256': 'b' * 64, 'files': {'source.py': 'c' * 64}}
        self.workflow = {'workflow_run_id': '123', 'workflow_attempt': '1'}
        expected = CONTROLS.expected_python_ids()
        runtime = {'python': {'distributions': CONTROLS.HELPERS.pins(),
                              'lock_sha256': CONTROLS.HELPERS.digest(CONTROLS.HELPERS.LOCK),
                              'verification_only': True, 'publication_approval': False},
                   'physical_python': {'source': 'controlled-validator-fixture'},
                   'node': {'version': CONTROLS.NODE_VERSION, 'modules': {'owned': 'fixture'},
                            'package_lock_sha256': CONTROLS.HELPERS.digest(CONTROLS.TESTS / 'package-lock.json')}}
        self.receipt = {'schema': 1, 'status': 'passed', 'verification_only': True, 'publication_approval': False,
                        'workflow': self.workflow, 'source_before': self.source, 'source_after': self.source,
                        'child_exit': 0, 'node_exit': 0, 'expected_python_ids': expected,
                        'python_executed': len(expected),
                        'python_cases': [{'id': name, 'status': 'passed', 'errors': []} for name in expected],
                        'node_cases': CONTROLS.node_cases(self.events, [self.unit]), 'node_executed': 2,
                        'runtime_before': runtime, 'runtime_after': copy.deepcopy(runtime)}
        # The actual unit source is an input, not a transported result artifact.
        self.unit.unlink()
        self.write()

    def write(self):
        self.receipt['artifact_digests'] = CONTROLS.HELPERS.inventory(self.root)
        self.receipt['artifact_digests'].pop('renderer-controls.json', None)
        CONTROLS.HELPERS.write_json(self.root / 'renderer-controls.json', self.receipt)

    def verify(self):
        return CONTROLS.verify(self.root, self.source, self.workflow)

    def test_real_native_events_and_complete_controlled_accounting_pass(self):
        self.assertEqual(self.verify()['status'], 'passed')

    def test_wrong_source_and_workflow_cannot_relabel_execution(self):
        original = copy.deepcopy(self.receipt)
        for key in ('source_before', 'source_after', 'workflow'):
            with self.subTest(key=key):
                self.receipt = copy.deepcopy(original)
                self.receipt[key] = {}
                self.write()
                with self.assertRaisesRegex(ValueError, 'source/workflow'):
                    self.verify()

    def test_nonzero_child_or_node_exit_is_not_success(self):
        for key in ('child_exit', 'node_exit'):
            with self.subTest(key=key):
                self.receipt[key] = 1
                self.write()
                with self.assertRaises(ValueError):
                    self.verify()
                self.receipt[key] = 0

    def test_missing_duplicate_unexpected_and_skipped_python_case_fail(self):
        original = copy.deepcopy(self.receipt)
        for change in ('missing', 'duplicate', 'unexpected', 'skipped', 'failed-subtest'):
            with self.subTest(change=change):
                self.receipt = copy.deepcopy(original)
                cases = self.receipt['python_cases']
                if change == 'missing':
                    cases.pop()
                elif change == 'duplicate':
                    cases.append(copy.deepcopy(cases[0]))
                elif change == 'unexpected':
                    cases[0]['id'] = 'unowned.test'
                elif change == 'skipped':
                    cases[0]['status'] = 'skipped'
                else:
                    cases[0]['errors'] = ['actual failed subtest']
                self.write()
                with self.assertRaisesRegex(ValueError, 'Python execution'):
                    self.verify()

    def test_runtime_mutation_or_missing_physical_identity_fails(self):
        self.receipt['runtime_after']['node']['modules']['changed'] = 'mutated'
        self.write()
        with self.assertRaisesRegex(ValueError, 'physical bytes changed'):
            self.verify()
        self.receipt['runtime_before'] = self.receipt['runtime_after'] = {}
        self.write()
        with self.assertRaisesRegex(ValueError, 'installed lock'):
            self.verify()

    def test_missing_extra_and_corrupt_transported_artifacts_fail(self):
        original = self.events.read_bytes()
        self.events.write_bytes(original + b'\n')
        with self.assertRaises(ValueError):
            self.verify()
        self.events.write_bytes(original)
        (self.root / 'unexpected.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'artifacts'):
            self.verify()
        (self.root / 'unexpected.json').unlink()
        self.events.unlink()
        with self.assertRaises(OSError):
            self.verify()

    def test_native_skip_cancel_and_failure_summary_fail(self):
        original = [json.loads(line) for line in self.events.read_text().splitlines()]
        for failure in ('failed', 'skipped', 'cancelled', 'todo'):
            with self.subTest(failure=failure):
                events = copy.deepcopy(original)
                summary = next(event['data'] for event in events if event['type'] == 'test:summary' and 'file' not in event['data'])
                summary['counts'][failure] = 1
                self.events.write_text(''.join(json.dumps(event) + '\n' for event in events))
                with self.assertRaisesRegex(ValueError, 'native Node execution'):
                    CONTROLS.node_cases(self.events, [self.unit], 2)

    def test_missing_duplicate_and_unowned_native_results_fail(self):
        original = [json.loads(line) for line in self.events.read_text().splitlines()]
        for change in ('missing', 'duplicate', 'unowned', 'missing-summary'):
            with self.subTest(change=change):
                events = copy.deepcopy(original)
                row = next(event for event in events if event['type'] == 'test:pass')
                if change == 'missing':
                    events.remove(row)
                elif change == 'duplicate':
                    events.append(copy.deepcopy(row))
                elif change == 'unowned':
                    row['data']['file'] = '/unowned/source.test.cjs'
                else:
                    events = [event for event in events if not (event['type'] == 'test:summary' and 'file' not in event['data'])]
                self.events.write_text(''.join(json.dumps(event) + '\n' for event in events))
                with self.assertRaises(ValueError):
                    CONTROLS.node_cases(self.events, [self.unit], 2)

    def test_unknown_publication_approval_is_not_unit_qualification(self):
        self.receipt['publication_approval'] = True
        self.write()
        with self.assertRaises(ValueError):
            self.verify()

    def test_node_dependency_link_escape_is_rejected(self):
        modules = self.root / 'modules'
        modules.mkdir()
        (modules / 'escape').symlink_to(self.root / 'node-events.jsonl')
        with self.assertRaisesRegex(ValueError, 'escapes'):
            CONTROLS.node_modules_identity(modules)


if __name__ == '__main__':
    unittest.main()
