"""Reject missing, mismatched, skipped and counterfeit frontend fault receipts."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'tests/bijux-docs/execution/frontend_faults.py'
spec = importlib.util.spec_from_file_location('frontend_faults', path)
GATE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(GATE)


class FrontendFaultReceiptTests(unittest.TestCase):
    def setUp(self):
        output = ROOT / 'artifacts/frontend-fault-controls'
        output.mkdir(parents=True, exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=output)
        self.addCleanup(self.folder.cleanup)
        self.pair = []
        for mode in ('clean', 'fault'):
            file = Path(self.folder.name) / (mode + '.xml')
            failures = 0 if mode == 'clean' else 3
            cases = ''.join('<testcase name="control-'+str(n)+'">'+('<failure/>' if mode == 'fault' and n else '')+'</testcase>' for n in range(4))
            file.write_text('<testsuites tests="4" failures="'+str(failures)+'" skipped="0" errors="0"><testsuite>'+cases+'</testsuite></testsuites>')
            rows = [{'case_id': str(n), 'status': 'failed' if mode == 'fault' and n else 'passed',
                     'retry': 0, 'errors': [GATE.FAULT_ERRORS[n-1]] if mode == 'fault' and n else [],
                     'annotations': [{'type': 'browser-version', 'description': 'controlled-test-version'}]} for n in range(4)]
            self.pair.append({'status': 'passed' if mode == 'clean' else 'failed', 'qualification_kind': 'assigned_engine_shard',
                             'source_identity': {'head': 'unit-controlled-source'}, 'fixture_identity': {'manifest_sha256': 'unit-controlled-bundle'},
                             'canonical_projects': [{'name': 'chromium-phone', 'count': 4}], 'assigned_project_names': ['chromium-phone'],
                             'expected_cases': [{'id': str(n)} for n in range(4)], 'results': rows,
                             'junit': {'path': str(file), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}})

    def test_complete_actual_shape_accepts_only_exact_expected_statuses(self):
        GATE.validate_pair(*self.pair)

    def reject(self, mutate, error):
        pair = copy.deepcopy(self.pair)
        mutate(pair)
        with self.assertRaisesRegex(ValueError, error):
            GATE.validate_pair(*pair)

    def test_source_change_cannot_certify_earlier_faults(self):
        self.reject(lambda pair: pair[1]['source_identity'].update(head='different-source'), 'identity differs')

    def test_bundle_change_cannot_certify_earlier_faults(self):
        self.reject(lambda pair: pair[1]['fixture_identity'].update(manifest_sha256='different-bundle'), 'identity differs')

    def test_omitted_case_rejected(self):
        self.reject(lambda pair: pair[1]['results'].pop(), 'four unique')

    def test_duplicate_case_rejected(self):
        self.reject(lambda pair: pair[1]['results'][2].update(case_id='1'), 'four unique')

    def test_unexpected_case_rejected(self):
        self.reject(lambda pair: pair[1]['results'][2].update(case_id='foreign'), 'expected cases')

    def test_skip_rejected(self):
        self.reject(lambda pair: pair[1]['results'][2].update(status='skipped'), 'nonterminal')

    def test_retry_rejected(self):
        self.reject(lambda pair: pair[1]['results'][2].update(retry=1), 'retried')

    def test_missing_version_rejected(self):
        self.reject(lambda pair: pair[1]['results'][2].update(annotations=[]), 'engine version')

    def test_unrelated_assertion_failure_does_not_prove_fault(self):
        self.reject(lambda pair: pair[1]['results'][2].update(errors=['unrelated timeout']), 'intended real fault')

    def test_clean_failure_rejected(self):
        self.reject(lambda pair: pair[0]['results'][2].update(status='failed', errors=['source failure']), 'Clean controls')

    def test_corrupt_actual_junit_rejected(self):
        Path(self.pair[1]['junit']['path']).write_text('corrupt')
        with self.assertRaisesRegex(ValueError, 'JUnit digest'):
            GATE.validate_pair(*self.pair)


if __name__ == '__main__':
    unittest.main()
