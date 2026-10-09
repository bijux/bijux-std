"""Reject incomplete, stale and over-budget frontend job observations."""
import copy
import tempfile
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('job_budget', ROOT / 'tests/bijux-docs/execution/job_budget.py')
BUDGET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUDGET)


class FrontendJobBudgetTests(unittest.TestCase):
    def setUp(self):
        self.groups, self.engines = {'navigation': [], 'reader': []}, ['chromium', 'firefox', 'webkit']
        self.head = 'a' * 40
        names = sorted(BUDGET.expected_job_names(self.groups, self.engines) | BUDGET.BASELINE_JOBS)
        self.data = {'total_count': len(names), 'jobs': [{'id': i + 1, 'name': name, 'run_id': 123, 'run_attempt': 2,
            'head_sha': self.head, 'status': 'completed', 'conclusion': 'success',
            'created_at': '2026-01-01T00:00:00Z', 'started_at': '2026-01-01T00:05:00Z', 'completed_at': '2026-01-01T00:07:59.999Z',
            'steps': [{'name': 'Ordinary assigned journeys', 'status': 'completed', 'conclusion': 'success',
                       'started_at': '2026-01-01T00:05:00Z', 'completed_at': '2026-01-01T00:07:00Z'}]} for i, name in enumerate(names)]}
        self.target = next(j for j in self.data['jobs'] if j['name'] == 'std / navigation fixtures')

    def verify(self):
        return BUDGET.qualify(self.data, groups=self.groups, engines=self.engines, run_id=123, attempt=2, head=self.head)

    def test_full_observation_separates_queue_and_whole_job_time(self):
        receipt = self.verify()
        self.assertEqual(receipt['maximum_seconds'], 179.999)
        self.assertEqual(receipt['maximum_queue_seconds'], 300)
        self.assertEqual(receipt['executed_jobs'], 13)

    def test_report_can_be_running_while_completed_dependencies_are_checked(self):
        report = next(j for j in self.data['jobs'] if j['name'] == 'std / report')
        report.update(status='in_progress', conclusion=None, completed_at=None)
        self.assertEqual(self.verify()['status'], 'passed')

    def test_strict_boundary_includes_cleanup_not_only_browser_step(self):
        for ended in ['2026-01-01T00:08:00Z', '2026-01-01T00:08:35Z']:
            with self.subTest(ended=ended):
                self.target['completed_at'] = ended
                with self.assertRaisesRegex(ValueError, '180-second'): self.verify()

    def test_missing_and_duplicate_and_unexpected_job_fail(self):
        baseline = copy.deepcopy(self.data)
        for change in ['missing', 'duplicate', 'unexpected']:
            with self.subTest(change=change):
                self.data = copy.deepcopy(baseline)
                if change == 'missing': self.data['jobs'].pop()
                elif change == 'duplicate': self.data['jobs'].append(copy.deepcopy(self.data['jobs'][0]))
                else: self.data['jobs'][0]['name'] = 'std / navigation unregistered'
                self.data['total_count'] = len(self.data['jobs'])
                with self.assertRaises(ValueError): self.verify()

    def test_incomplete_api_page_and_duplicate_ids_fail(self):
        self.data['total_count'] += 1
        with self.assertRaisesRegex(ValueError, 'API page'): self.verify()
        self.data['total_count'] -= 1
        self.data['jobs'][1]['id'] = self.data['jobs'][0]['id']
        with self.assertRaisesRegex(ValueError, 'Duplicate job ID'): self.verify()

    def test_wrong_run_attempt_and_head_fail(self):
        for key, value in [('run_id', 124), ('run_attempt', 1), ('head_sha', 'b' * 40)]:
            with self.subTest(key=key):
                original = self.target[key]; self.target[key] = value
                with self.assertRaisesRegex(ValueError, 'mismatch'): self.verify()
                self.target[key] = original

    def test_queued_running_cancelled_failed_and_skipped_are_not_passes(self):
        for status, conclusion in [('queued', None), ('in_progress', None), ('completed', 'cancelled'), ('completed', 'failure'), ('completed', 'skipped')]:
            with self.subTest(status=status, conclusion=conclusion):
                self.target.update(status=status, conclusion=conclusion)
                with self.assertRaisesRegex(ValueError, 'terminal-success'): self.verify()

    def test_missing_actual_creation_and_timezone_are_not_invented(self):
        for value in [None, '', '2026-01-01T00:00:00']:
            with self.subTest(value=value):
                self.target['created_at'] = value
                with self.assertRaises(ValueError): self.verify()

    def test_out_of_order_job_and_step_times_fail(self):
        self.target['created_at'] = '2026-01-01T00:06:00Z'
        with self.assertRaisesRegex(ValueError, 'out of order'): self.verify()
        self.target['created_at'] = '2026-01-01T00:00:00Z'
        self.target['steps'][0]['started_at'] = '2026-01-01T00:04:59Z'
        with self.assertRaisesRegex(ValueError, 'outside'): self.verify()

    def test_failed_or_unaccounted_step_is_not_qualified(self):
        step = self.target['steps'][0]
        step['conclusion'] = 'failure'
        with self.assertRaisesRegex(ValueError, 'step'): self.verify()
        step['conclusion'] = 'success'; step['started_at'] = None
        with self.assertRaisesRegex(ValueError, 'timestamps'): self.verify()

    def test_explicit_skipped_step_preserves_absent_timestamps(self):
        self.target['steps'].append({'name': 'Inapplicable conditional setup', 'status': 'completed', 'conclusion': 'skipped', 'started_at': None, 'completed_at': None})
        receipt = self.verify()
        row = next(j for j in receipt['jobs'] if j['name'] == self.target['name'])
        self.assertIsNone(row['steps'][-1]['seconds'])

    def test_invalid_canonical_identity_cannot_shrink_expected_coverage(self):
        for groups, engines in [({}, self.engines), (self.groups, []), (self.groups, ['chromium', 'chromium']), ({'navigation / fake': []}, self.engines)]:
            with self.subTest(groups=groups, engines=engines), self.assertRaises(ValueError):
                BUDGET.expected_job_names(groups, engines)


    def test_registry_identity_covers_each_execution_dependency(self):
        artifacts = ROOT / 'artifacts/qualification/browser-partitions-integration'
        artifacts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=artifacts) as directory:
            root = Path(directory)
            for name in ('browser_gate.py', 'browser_partitions.py', 'browser_partitions.json'):
                (root / name).write_text(name)
            before = BUDGET.registry_digests(root / 'browser_gate.py')
            self.assertEqual(set(before), {'browser_gate.py', 'browser_partitions.py', 'browser_partitions.json'})
            (root / 'browser_partitions.json').write_text('changed declaration')
            after = BUDGET.registry_digests(root / 'browser_gate.py')
            self.assertNotEqual(before['browser_partitions.json'], after['browser_partitions.json'])
            self.assertEqual(before['browser_gate.py'], after['browser_gate.py'])
            (root / 'browser_partitions.py').unlink()
            with self.assertRaises(FileNotFoundError):
                BUDGET.registry_digests(root / 'browser_gate.py')


if __name__ == '__main__':
    unittest.main()
