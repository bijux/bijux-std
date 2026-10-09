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
        self.assertEqual(receipt['executed_jobs'], len(BUDGET.expected_job_names(self.groups, self.engines)))

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


    def refresh(self, fetch):
        return BUDGET.refresh_nonterminal(self.data, fetch=fetch, groups=self.groups,
            engines=self.engines, run_id=123, attempt=2, head=self.head)

    def test_incomplete_list_row_requires_fresh_exact_job_before_qualification(self):
        completed = copy.deepcopy(self.target)
        self.target.update(status='in_progress', conclusion=None, completed_at=None)
        original = copy.deepcopy(self.data)
        with self.assertRaisesRegex(ValueError, 'terminal-success'): self.verify()
        requested = []
        refreshed = self.refresh(lambda identifier: requested.append(identifier) or completed)
        self.assertEqual(requested, [self.target['id']])
        self.assertEqual(self.data, original)
        receipt = BUDGET.qualify(refreshed, groups=self.groups, engines=self.engines,
            run_id=123, attempt=2, head=self.head)
        self.assertEqual(receipt['executed_jobs'], len(BUDGET.expected_job_names(self.groups, self.engines)))
        self.assertEqual(receipt['maximum_seconds'], 179.999)

    def test_incomplete_fresh_row_and_completed_steps_cannot_infer_success(self):
        self.target.update(status='in_progress', conclusion=None, completed_at=None)
        refreshed = self.refresh(lambda identifier: copy.deepcopy(self.target))
        with self.assertRaisesRegex(ValueError, 'terminal-success'):
            BUDGET.qualify(refreshed, groups=self.groups, engines=self.engines,
                run_id=123, attempt=2, head=self.head)

    def test_refresh_cannot_change_job_source_attempt_run_name_or_id(self):
        completed = copy.deepcopy(self.target)
        self.target.update(status='in_progress', conclusion=None, completed_at=None)
        for key, value in [('id', 999), ('name', 'std / navigation'), ('run_id', 124),
                           ('run_attempt', 1), ('head_sha', 'b' * 40)]:
            with self.subTest(key=key):
                observed = {**completed, key: value}
                with self.assertRaisesRegex(ValueError, 'Refreshed job identity'):
                    self.refresh(lambda identifier: observed)

    def test_terminal_failure_is_not_replaced_with_another_observation(self):
        self.target['conclusion'] = 'cancelled'
        refreshed = self.refresh(lambda identifier: self.fail('Terminal results must not be refreshed'))
        with self.assertRaisesRegex(ValueError, 'terminal-success'):
            BUDGET.qualify(refreshed, groups=self.groups, engines=self.engines,
                run_id=123, attempt=2, head=self.head)

    def test_running_report_is_not_refreshed_and_complete_inventory_is_reused(self):
        report = next(j for j in self.data['jobs'] if j['name'] == 'std / report')
        report.update(status='in_progress', conclusion=None, completed_at=None)
        refreshed = self.refresh(lambda identifier: self.fail('No frontend row needs refresh'))
        self.assertEqual(refreshed, self.data)

    def test_refresh_cannot_repair_invalid_inventory_or_source(self):
        baseline = copy.deepcopy(self.data)
        for defect in ['missing', 'duplicate', 'source']:
            with self.subTest(defect=defect):
                self.data = copy.deepcopy(baseline)
                if defect == 'missing': self.data['jobs'].pop()
                elif defect == 'duplicate': self.data['jobs'].append(self.data['jobs'][0])
                else: self.data['jobs'][0]['head_sha'] = 'b' * 40
                with self.assertRaises(ValueError):
                    self.refresh(lambda identifier: self.fail('Invalid input must fail before network refresh'))

    def test_fresh_terminal_row_still_obeys_strict_duration_and_step_checks(self):
        completed = copy.deepcopy(self.target)
        self.target.update(status='in_progress', conclusion=None, completed_at=None)
        for defect in ['duration', 'step']:
            with self.subTest(defect=defect):
                observed = copy.deepcopy(completed)
                if defect == 'duration': observed['completed_at'] = '2026-01-01T00:08:00Z'
                else: observed['steps'][0]['conclusion'] = 'failure'
                refreshed = self.refresh(lambda identifier: observed)
                with self.assertRaises(ValueError):
                    BUDGET.qualify(refreshed, groups=self.groups, engines=self.engines,
                        run_id=123, attempt=2, head=self.head)

    def test_registry_identity_covers_each_execution_dependency(self):
        artifacts = ROOT / 'artifacts/qualification/browser-partitions-integration'
        artifacts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=artifacts) as directory:
            owner = Path(directory)
            root = owner / 'execution'
            root.mkdir()
            catalogue = owner / 'catalogue'
            catalogue.mkdir()
            (catalogue / 'execution.py').write_text("GROUPS = {'source': ('test_source',)}\n")
            for name in ('browser_gate.py', 'browser_partitions.py', 'browser_partitions.json', 'renderer_controls.py', 'node_events.cjs'):
                (root / name).write_text(name)
            before = BUDGET.registry_digests(root / 'browser_gate.py')
            self.assertEqual(set(before), {'browser_gate.py', 'browser_partitions.py', 'browser_partitions.json', 'renderer_controls.py', 'node_events.cjs', 'catalogue/execution.py'})
            (root / 'browser_partitions.json').write_text('changed declaration')
            after = BUDGET.registry_digests(root / 'browser_gate.py')
            self.assertNotEqual(before['browser_partitions.json'], after['browser_partitions.json'])
            self.assertEqual(before['browser_gate.py'], after['browser_gate.py'])
            (catalogue / 'execution.py').write_text("GROUPS = {'renderer': ('test_renderer',)}\n")
            changed = BUDGET.registry_digests(root / 'browser_gate.py')
            self.assertNotEqual(before['catalogue/execution.py'], changed['catalogue/execution.py'])
            (root / 'browser_partitions.py').unlink()
            with self.assertRaises(FileNotFoundError):
                BUDGET.registry_digests(root / 'browser_gate.py')


    def test_renderer_controls_are_required_terminal_success_and_under_budget(self):
        target = next(job for job in self.data['jobs'] if job['name'] == 'std / renderer controls / renderer')
        baseline = copy.deepcopy(target)
        for field, value in [('status', 'queued'), ('conclusion', 'failure'),
                             ('conclusion', 'cancelled'), ('conclusion', 'skipped'),
                             ('completed_at', '2026-01-01T00:08:00Z')]:
            with self.subTest(field=field, value=value):
                target.update(baseline)
                target[field] = value
                with self.assertRaises(ValueError):
                    self.verify()


    def test_renderer_group_registry_is_literal_bounded_and_unique(self):
        owner = ROOT / 'artifacts/qualification/renderer-partition-registry-controls'
        owner.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=owner) as directory:
            path = Path(directory) / 'renderer_controls.py'
            path.write_text("GROUPS = ('renderer', 'passive-reader', 'interactive-make')\n")
            self.assertEqual(BUDGET.renderer_job_names(path),
                             {'std / renderer controls / renderer', 'std / renderer controls / passive-reader',
                              'std / renderer controls / interactive-make'})
            for source in ["GROUPS = ()", "GROUPS = ['renderer']", "GROUPS = ('renderer', 'renderer')",
                           "GROUPS = ('renderer/unknown',)", "GROUPS = (1,)", "GROUPS = ([],)",
                           "GROUPS = tuple(['renderer'])", "GROUPS = ('renderer',)\nGROUPS = ('passive-reader',)"]:
                with self.subTest(source=source):
                    path.write_text(source)
                    with self.assertRaises(ValueError): BUDGET.renderer_job_names(path)

    def test_every_renderer_partition_is_independently_required_and_budgeted(self):
        wanted = BUDGET.renderer_job_names()
        self.assertEqual(wanted, {'std / renderer controls / renderer', 'std / renderer controls / passive-reader',
                              'std / renderer controls / interactive-make'})
        self.assertEqual({row['name'] for row in self.verify()['jobs']
                          if row['name'].startswith('std / renderer controls / ')}, wanted)
        baseline = copy.deepcopy(self.data)
        for name in wanted:
            for defect in ('missing', 'duplicate', 'unknown', 'cancelled', 'over-budget'):
                with self.subTest(name=name, defect=defect):
                    self.data = copy.deepcopy(baseline)
                    target = next(row for row in self.data['jobs'] if row['name'] == name)
                    if defect == 'missing': self.data['jobs'].remove(target)
                    elif defect == 'duplicate': self.data['jobs'].append(copy.deepcopy(target))
                    elif defect == 'unknown': target['name'] = 'std / renderer controls / unknown'
                    elif defect == 'cancelled': target['conclusion'] = 'cancelled'
                    else: target['completed_at'] = '2026-01-01T00:08:00Z'
                    self.data['total_count'] = len(self.data['jobs'])
                    with self.assertRaises(ValueError): self.verify()
        self.data = baseline

    def test_every_catalogue_job_is_owned_and_budgeted(self):
        receipt = self.verify()
        wanted = BUDGET.catalogue_job_names()
        self.assertEqual(wanted, {'std / catalogue source', 'std / catalogue renderer',
                                 'std / catalogue typed-entrypoint', 'std / catalogue tracked-entrypoint'})
        self.assertEqual({row['name'] for row in receipt['jobs'] if row['name'].startswith('std / catalogue ')}, wanted)

    def test_missing_duplicate_and_unknown_catalogue_jobs_fail_closed(self):
        baseline = copy.deepcopy(self.data)
        for defect in ('missing', 'duplicate', 'unknown'):
            with self.subTest(defect=defect):
                self.data = copy.deepcopy(baseline)
                target = next(row for row in self.data['jobs'] if row['name'] == 'std / catalogue source')
                if defect == 'missing':
                    self.data['jobs'].remove(target)
                elif defect == 'duplicate':
                    self.data['jobs'].append(copy.deepcopy(target))
                else:
                    target['name'] = 'std / catalogue unknown'
                self.data['total_count'] = len(self.data['jobs'])
                with self.assertRaises(ValueError):
                    self.verify()

    def test_catalogue_setup_upload_and_cleanup_count_toward_strict_budget(self):
        target = next(row for row in self.data['jobs'] if row['name'] == 'std / catalogue source')
        target['steps'] = [{'name': 'Catalogue cases', 'status': 'completed', 'conclusion': 'success',
                           'started_at': '2026-01-01T00:05:30Z', 'completed_at': '2026-01-01T00:05:40Z'}]
        for end in ('2026-01-01T00:08:00Z', '2026-01-01T00:08:20Z'):
            with self.subTest(end=end):
                target['completed_at'] = end
                with self.assertRaisesRegex(ValueError, '180-second'):
                    self.verify()

    def test_nonterminal_and_failed_catalogue_results_are_not_qualified(self):
        target = next(row for row in self.data['jobs'] if row['name'] == 'std / catalogue source')
        for status, conclusion in [('queued', None), ('in_progress', None),
                                   ('completed', 'cancelled'), ('completed', 'failure'), ('completed', 'skipped')]:
            with self.subTest(status=status, conclusion=conclusion):
                target.update(status=status, conclusion=conclusion)
                with self.assertRaisesRegex(ValueError, 'terminal-success'):
                    self.verify()

    def test_catalogue_refresh_retains_actual_source_identity(self):
        target = next(row for row in self.data['jobs'] if row['name'] == 'std / catalogue source')
        completed = copy.deepcopy(target)
        target.update(status='in_progress', conclusion=None, completed_at=None)
        refreshed = self.refresh(lambda identifier: completed)
        self.assertEqual(self.data['jobs'][0]['head_sha'], self.head)
        self.assertEqual(BUDGET.qualify(refreshed, groups=self.groups, engines=self.engines,
                         run_id=123, attempt=2, head=self.head)['executed_jobs'],
                         len(BUDGET.expected_job_names(self.groups, self.engines)))
        with self.assertRaisesRegex(ValueError, 'Refreshed job identity'):
            self.refresh(lambda identifier: {**completed, 'head_sha': 'b' * 40})

    def test_catalogue_registry_cannot_execute_or_admit_malformed_selections(self):
        artifacts = ROOT / 'artifacts/catalogue-budget-registry-controls'
        artifacts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=artifacts) as directory:
            path = Path(directory) / 'execution.py'
            for text in ("GROUPS = dangerous()", "GROUPS = {}", "GROUPS = {'source': ()}",
                         "GROUPS = {'source': ('bad/id',)}", "GROUPS = {'bad/name': ('test_source',)}",
                         "GROUPS = {'source': ['test_source']}", "GROUPS = 3", "broken source!",
                         "GROUPS = {'source': ('test_source',)}\nGROUPS = {'other': ('test_other',)}"):
                with self.subTest(text=text):
                    path.write_text(text)
                    with self.assertRaises(ValueError):
                        BUDGET.catalogue_job_names(path)
            path.write_text("GROUPS = {'source': ('test_source',), 'renderer': ('test_renderer',)}")
            self.assertEqual(BUDGET.catalogue_job_names(path), {'std / catalogue source', 'std / catalogue renderer'})
            other = Path(directory) / 'linked.py'
            other.symlink_to(path)
            with self.assertRaisesRegex(ValueError, 'ordinary source'):
                BUDGET.catalogue_job_names(other)

    def test_workflow_catalogue_matrix_matches_source_owned_selection(self):
        text = (ROOT / '.github/workflows/bijux-std.yml').read_text()
        catalogue = text.split('  catalogue-renderer:', 1)[1].split('  publication-commands:', 1)[0]
        matrix = catalogue.split('group: [', 1)[1].split(']', 1)[0]
        self.assertEqual({'std / catalogue ' + item.strip() for item in matrix.split(',')}, BUDGET.catalogue_job_names())


if __name__ == '__main__':
    unittest.main()
