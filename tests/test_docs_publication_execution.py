"""Reject incomplete command execution and corrupted publication evidence."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('publication_gate', ROOT / 'tests/bijux-docs/execution/publication_gate.py')
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class PublicationExecutionTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'artifacts').mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=ROOT / 'artifacts')
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)
        self.source = {'head': 'a' * 40, 'tree_sha256': 'b' * 64, 'files': {'test.py': 'c' * 64}}
        self.workflow = {'workflow_run_id': '123', 'workflow_attempt': '1'}
        self.receipt = self.fixture()

    def fixture(self):
        records = []
        for identifier in GATE.EXPECTED_IDS:
            root = self.output / 'cases' / hashlib.sha256(identifier.encode()).hexdigest()
            root.mkdir(parents=True)
            runtime = 'test_runtime_admission_rejects' in identifier
            command = {'argv': ['make', 'docs-check'], 'cwd': '/fixture/consumer', 'returncode': 2,
                       'stdout': '', 'stderr': 'differs from exact admitted source' if runtime else GATE.UNSUPPORTED}
            if not runtime:
                GATE.write_json(root / 'renderer-evidence/profile-availability.json', {
                    'state': 'unsupported-profile-rejected-before-public-mutation',
                    'positive_qualification_pending': True, 'known_profile_positive_executed': False})
                for name in ('build-identity', 'csp', 'producer-reconstruction', 'site-verification'):
                    GATE.write_json(root / f'fixture-artifacts/website-security/{name}.json', {'passed': False, 'verification_only': True})
            else:
                (root / 'public.html').write_text('Preserved fixture bytes')
            data = {'id': identifier, 'status': 'passed', 'errors': [], 'commands': [command],
                    'public_before': {'index.html': 'd' * 64}, 'public_after': {'index.html': 'd' * 64},
                    'artifacts': GATE.inventory(root)}
            GATE.write_json(root / 'case.json', data)
            records.append({'id': identifier, 'status': 'passed', 'errors': [],
                'receipt': str((root / 'case.json').relative_to(self.output)), 'receipt_sha256': GATE.digest(root / 'case.json')})
        runtime = {'scope': 'installed-exact-lock-fixture-interpreter', 'verification_only': True, 'publication_approval': False,
                   'distributions': GATE.pins(), 'lock_sha256': GATE.digest(GATE.LOCK), 'version': '3.13.8', 'executable': '/fixture/python', 'implementation': 'CPython', 'system': 'Fixture', 'machine': 'fixture-machine', 'executable_sha256': 'e' * 64}
        (self.output / 'unittest.log').write_text('Parser fixture; not a renderer execution receipt')
        receipt = {'schema': 1, 'status': 'passed', 'verification_only': True, 'publication_approval': False,
            'workflow': self.workflow, 'source_before': self.source, 'source_after': self.source, 'child_exit': 0,
            'expected_ids': list(GATE.EXPECTED_IDS), 'executed': 3, 'failed': 0, 'errors': 0, 'skipped': 0,
            'selected_python': '/fixture/python', 'cases': records, 'runtime_before': runtime, 'runtime_after': copy.deepcopy(runtime),
            'artifact_digests': GATE.inventory(self.output)}
        GATE.write_json(self.output / 'command-receipt.json', receipt)
        return receipt

    def verify(self):
        return GATE.verify(self.output, self.source, self.workflow)

    def save(self):
        GATE.write_json(self.output / 'command-receipt.json', self.receipt)

    def rewrite_case(self, change):
        record = self.receipt['cases'][0]
        path = self.output / record['receipt']
        data = json.loads(path.read_text())
        change(data, path.parent)
        data['artifacts'] = GATE.inventory(path.parent)
        data['artifacts'].pop('case.json', None)
        GATE.write_json(path, data)
        record['receipt_sha256'] = GATE.digest(path)
        self.receipt['artifact_digests'] = GATE.inventory(self.output)
        self.receipt['artifact_digests'].pop('command-receipt.json', None)
        self.save()

    def test_exact_parser_fixture_qualifies_only_verification_scope(self):
        self.assertTrue(self.verify()['verification_only'])
        self.assertFalse(self.verify()['publication_approval'])

    def test_missing_case_and_duplicate_identity_are_rejected(self):
        for change in ('missing', 'duplicate', 'unexpected'):
            with self.subTest(change=change):
                original = copy.deepcopy(self.receipt)
                if change == 'missing': self.receipt['cases'].pop()
                elif change == 'duplicate': self.receipt['cases'][1] = copy.deepcopy(self.receipt['cases'][0])
                else: self.receipt['cases'][0]['id'] = 'unrequested.case'
                self.save()
                with self.assertRaisesRegex(ValueError, 'Missing, duplicate'): self.verify()
                self.receipt = original

    def test_incomplete_accounting_failed_child_and_skips_are_rejected(self):
        for field, value in [('executed', 2), ('child_exit', 1), ('skipped', 1), ('failed', 1), ('errors', 1)]:
            with self.subTest(field=field):
                self.receipt[field] = value; self.save()
                with self.assertRaisesRegex(ValueError, 'accounting'): self.verify()
                self.receipt[field] = 3 if field == 'executed' else 0

    def test_changed_current_source_and_workflow_cannot_reuse_passing_receipt(self):
        for field in ('source_before', 'source_after', 'workflow'):
            with self.subTest(field=field):
                original = self.receipt[field]
                self.receipt[field] = {}; self.save()
                with self.assertRaisesRegex(ValueError, 'identity mismatch'): self.verify()
                self.receipt[field] = original

    def test_missing_corrupt_and_unexpected_artifacts_are_rejected(self):
        path = self.output / 'unittest.log'
        for action in ('corrupt', 'missing', 'unexpected'):
            with self.subTest(action=action):
                if action == 'corrupt': path.write_text('Changed log')
                elif action == 'missing': path.unlink()
                else: (self.output / 'unrequested.log').write_text('Extra evidence')
                with self.assertRaisesRegex(ValueError, 'run artifacts'): self.verify()
                path.write_text('Parser fixture; not a renderer execution receipt')
                (self.output / 'unrequested.log').unlink(missing_ok=True)

    def test_corrupt_case_receipt_and_escaping_receipt_path_are_rejected(self):
        row = self.receipt['cases'][0]; path = self.output / row['receipt']; original = path.read_bytes()
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'receipt digest'): self.verify()
        path.write_bytes(original)
        row['receipt'] = '../outside.json'; self.save()
        with self.assertRaisesRegex(ValueError, 'Unsafe'): self.verify()

    def test_rehashed_unsupported_public_mutation_is_still_rejected(self):
        self.rewrite_case(lambda data, root: data['public_after'].update({'index.html': 'Changed public bytes'}))
        with self.assertRaisesRegex(ValueError, 'before mutation'): self.verify()

    def test_rehashed_other_renderer_failure_is_not_accepted_as_unsupported(self):
        self.rewrite_case(lambda data, root: data['commands'][0].update({'stderr': 'Ordinary broken renderer'}))
        with self.assertRaisesRegex(ValueError, 'exactly rejected'): self.verify()

    def test_rehashed_false_publication_success_on_unsupported_profile_is_rejected(self):
        def alter(data, root):
            GATE.write_json(root / 'fixture-artifacts/website-security/csp.json', {'passed': True, 'verification_only': True})
        self.rewrite_case(alter)
        with self.assertRaisesRegex(ValueError, 'passing publication receipt'): self.verify()

    def test_runtime_drift_and_false_approval_are_rejected(self):
        self.receipt['runtime_after']['version'] = 'changed'; self.save()
        with self.assertRaisesRegex(ValueError, 'runtime identity'): self.verify()
        self.receipt['runtime_after'] = copy.deepcopy(self.receipt['runtime_before'])
        self.receipt['publication_approval'] = True; self.save()
        with self.assertRaisesRegex(ValueError, 'verification evidence'): self.verify()

    def test_evidence_symlinks_are_rejected(self):
        (self.output / 'link').symlink_to(self.output / 'unittest.log')
        with self.assertRaisesRegex(ValueError, 'symlinks'): self.verify()

    def test_existing_run_evidence_is_preserved(self):
        with self.assertRaisesRegex(ValueError, 'Preserve existing'):
            GATE.run(Path('/unused/python'), self.output)

    def test_unittest_expected_failure_skip_and_subtest_failure_remain_nonpassing(self):
        class Controls(unittest.TestCase):
            @unittest.expectedFailure
            def test_expected_failure(self): self.fail('Expected failure is not qualification')
            @unittest.skip('Control skip')
            def test_skip(self): pass
            def test_subtest(self):
                with self.subTest(control=True): self.fail('Subtest failed')
        result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=GATE.CommandResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
        self.assertEqual(result.testsRun, 3)
        self.assertEqual([row['status'] for row in result.records], ['failed', 'skipped', 'failed'])


if __name__ == '__main__':
    unittest.main()
