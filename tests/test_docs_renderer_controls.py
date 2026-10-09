"""Reject incomplete, nonpassing or relabeled independent renderer controls."""
import copy
import importlib.util
import json
import hashlib
import os
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
        runtime = self.runtime_fixture()
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

    def runtime_fixture(self):
        # A complete controlled schema fixture grants no physical execution approval.
        packages = [{'name': name, 'version': version, 'files_count': 1, 'files_sha256': 'a' * 64}
                    for name, version in CONTROLS.HELPERS.pins().items()]
        manifests, modules = {}, {'.package-lock.json': {'sha256': 'b' * 64}}
        for name, record in CONTROLS.source_node_packages().items():
            text = json.dumps({'name': name.removeprefix('node_modules/'), 'version': record['version']})
            manifests[name] = text
            modules[name.removeprefix('node_modules/') + '/package.json'] = {
                'sha256': hashlib.sha256(text.encode()).hexdigest()}
        return {'python': {'scope': 'installed-exact-lock-fixture-interpreter',
                           'executable': '/owned/python', 'executable_sha256': 'c' * 64,
                           'version': '3.14.4', 'implementation': 'CPython', 'system': 'Darwin', 'machine': 'arm64',
                           'distributions': CONTROLS.HELPERS.pins(),
                           'lock_sha256': CONTROLS.HELPERS.digest(CONTROLS.HELPERS.LOCK),
                           'verification_only': True, 'publication_approval': False},
                'physical_python': {'platform': {'python': '3.14.4', 'implementation': 'cpython',
                                                  'system': 'Darwin', 'machine': 'arm64', 'cache_tag': 'cpython-314'},
                                    'executable_sha256': 'c' * 64,
                                    'stdlib': {'files_count': 1, 'files_sha256': 'd' * 64},
                                    'physical_roots': [{'root': 'site-packages', 'files_count': len(packages), 'files_sha256': 'e' * 64}],
                                    'packages': packages, 'startup_inputs': []},
                'node': {'version': CONTROLS.NODE_VERSION, 'executable': '/owned/node', 'executable_sha256': 'f' * 64,
                         'package_lock_sha256': CONTROLS.HELPERS.digest(CONTROLS.TESTS / 'package-lock.json'),
                         'modules': modules, 'package_manifests': manifests}}


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
        with self.assertRaises(ValueError):
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

    def test_malformed_and_cross_identity_python_runtime_snapshots_fail(self):
        for runtime in (None, [], {'python': [], 'physical_python': {}, 'node': {}}):
            with self.subTest(runtime=runtime), self.assertRaises(ValueError):
                CONTROLS.validate_runtime(runtime)
        baseline = self.runtime_fixture()
        changes = [('python', 'executable', ''), ('python', 'executable_sha256', 'invalid'),
                   ('python', 'version', 'unknown'), ('python', 'machine', ''), ('python', 'system', ''),
                   ('physical_python', 'platform', {}), ('physical_python', 'executable_sha256', 'd' * 64),
                   ('physical_python', 'stdlib', {'files_count': True, 'files_sha256': 'a' * 64}),
                   ('physical_python', 'physical_roots', []), ('physical_python', 'packages', []),
                   ('physical_python', 'startup_inputs', [{'path': '../escape', 'source': '', 'sha256': 'a' * 64}])]
        for owner, key, value in changes:
            with self.subTest(owner=owner, key=key):
                runtime = copy.deepcopy(baseline)
                runtime[owner][key] = value
                with self.assertRaises(ValueError):
                    CONTROLS.validate_runtime(runtime)

    def test_physical_python_packages_must_match_source_lock_without_duplicate_ownership(self):
        for change in ('missing', 'version', 'duplicate', 'unreviewed-extra', 'digest'):
            with self.subTest(change=change):
                runtime = self.runtime_fixture()
                packages = runtime['physical_python']['packages']
                if change == 'missing':
                    packages.pop()
                elif change == 'version':
                    packages[0]['version'] = '0.0.0'
                elif change == 'duplicate':
                    packages.append(copy.deepcopy(packages[0]))
                elif change == 'unreviewed-extra':
                    packages.append({'name': 'unknown', 'version': '1', 'files_count': 1, 'files_sha256': 'a' * 64})
                else:
                    packages[0]['files_sha256'] = 'invalid'
                with self.assertRaises(ValueError):
                    CONTROLS.validate_runtime(runtime)

    def test_node_physical_manifests_and_links_remain_source_owned(self):
        for change in ('executable', 'digest', 'manifest-version', 'manifest-bytes', 'missing-package',
                       'unknown-payload', 'unsafe-path', 'link-escape', 'missing-lock'):
            with self.subTest(change=change):
                runtime = self.runtime_fixture()
                node = runtime['node']
                first = next(iter(node['package_manifests']))
                if change == 'executable':
                    node['executable'] = ''
                elif change == 'digest':
                    node['executable_sha256'] = 'invalid'
                elif change == 'manifest-version':
                    node['package_manifests'][first] = '{}'
                elif change == 'manifest-bytes':
                    node['modules'][first.removeprefix('node_modules/') + '/package.json']['sha256'] = 'c' * 64
                elif change == 'missing-package':
                    del node['package_manifests'][first]
                elif change == 'unknown-payload':
                    node['modules']['unknown/extra.js'] = {'sha256': 'a' * 64}
                elif change == 'unsafe-path':
                    node['modules']['../escape'] = {'sha256': 'a' * 64}
                elif change == 'link-escape':
                    node['modules']['.bin/escape'] = {'target': '../../escape', 'sha256': 'a' * 64}
                else:
                    del node['modules']['.package-lock.json']
                with self.assertRaises((ValueError, TypeError)):
                    CONTROLS.validate_runtime(runtime)

    def test_selected_node_environment_replaces_inherited_foreign_module_path(self):
        owner = self.root / 'runtime-owner'
        owned = owner / 'artifacts/bijux-docs/node-runtime/node_modules/renderer-owned-probe'
        owned.mkdir(parents=True)
        (owned / 'index.js').write_text("module.exports = 'owned-runtime';\n")
        foreign = self.root / 'foreign-modules/renderer-owned-probe'
        foreign.mkdir(parents=True)
        (foreign / 'index.js').write_text("module.exports = 'foreign-runtime';\n")
        with mock.patch.object(CONTROLS, 'ROOT', owner), mock.patch.dict(os.environ, {'NODE_PATH': str(foreign.parent)}):
            env = CONTROLS.node_environment(Path(shutil.which('node')))
            result = subprocess.run([shutil.which('node'), '-e', "process.stdout.write(require('renderer-owned-probe'))"],
                                    env=env, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, 'owned-runtime')
        self.assertEqual(env['NODE_PATH'], str(owned.parent))


    def test_node_dependency_link_escape_is_rejected(self):
        modules = self.root / 'modules'
        modules.mkdir()
        (modules / 'escape').symlink_to(self.root / 'node-events.jsonl')
        with self.assertRaisesRegex(ValueError, 'escapes'):
            CONTROLS.node_modules_identity(modules)


if __name__ == '__main__':
    unittest.main()
