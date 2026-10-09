"""Reject incomplete or relabeled catalogue execution receipts."""
from pathlib import Path
import copy
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('bijux_catalogue_execution_controls',
    ROOT / 'tests/bijux-docs/catalogue/execution.py')
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class CatalogueExecution(unittest.TestCase):
    def setUp(self):
        self.source = {'head': 'a' * 40, 'files': {'owned': 'b' * 64}}
        self.runtime = {'fixture': 'explicit-unit-identity'}
        self.receipt = {'schema': 1, 'group': 'source',
            'expected_ids': gate.expected('source'), 'executed_ids': gate.expected('source'),
            'failed_ids': [], 'skipped_ids': [], 'passed': True,
            'source_before': self.source, 'source_after': self.source,
            'runtime_before': self.runtime, 'runtime_after': self.runtime,
            'publication_approval': False, 'workflow': gate.helpers.workflow_identity()}

    def check(self, receipt):
        gate.verify(receipt, 'source', self.source, self.runtime)

    def test_complete_exact_case_identity_is_accepted(self):
        self.check(self.receipt)

    def test_groups_cover_all_maintained_cases_exactly_once(self):
        complete = [case for group in gate.GROUPS for case in gate.expected(group)]
        self.assertEqual(len(complete), 58)
        self.assertEqual(len(set(complete)), 58)

    def test_missing_executed_case_is_rejected(self):
        self.receipt['executed_ids'].pop()
        with self.assertRaises(ValueError): self.check(self.receipt)

    def test_duplicate_executed_case_is_rejected(self):
        self.receipt['executed_ids'].append(self.receipt['executed_ids'][0])
        with self.assertRaises(ValueError): self.check(self.receipt)

    def test_unexpected_case_is_rejected(self):
        self.receipt['executed_ids'][-1] = 'foreign.Test.case'
        with self.assertRaises(ValueError): self.check(self.receipt)

    def test_failed_or_skipped_case_is_rejected(self):
        for field in ('failed_ids', 'skipped_ids'):
            receipt = copy.deepcopy(self.receipt)
            receipt[field] = [receipt['expected_ids'][0]]
            with self.subTest(field=field), self.assertRaises(ValueError): self.check(receipt)

    def test_source_mutation_is_rejected(self):
        self.receipt['source_after'] = {'head': 'a' * 40, 'files': {'owned': 'c' * 64}}
        with self.assertRaises(ValueError): self.check(self.receipt)

    def test_runtime_mutation_is_rejected(self):
        self.receipt['runtime_after'] = {'fixture': 'changed'}
        with self.assertRaises(ValueError): self.check(self.receipt)

    def test_cross_group_receipt_is_rejected(self):
        self.receipt['group'] = 'renderer'
        with self.assertRaises(ValueError): self.check(self.receipt)

    def test_other_workflow_attempt_is_rejected(self):
        self.receipt['workflow'] = {'workflow_run_id': 'unexpected', 'workflow_attempt': '9'}
        with self.assertRaises(ValueError): self.check(self.receipt)

    def test_publication_approval_is_rejected(self):
        self.receipt['publication_approval'] = True
        with self.assertRaises(ValueError): self.check(self.receipt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
