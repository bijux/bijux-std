"""Require disjoint complete browser project ownership and terminal evidence."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('browser_partitions', ROOT / 'tests/bijux-docs/execution/browser_partitions.py')
PARTITIONS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PARTITIONS)
GATE_SPEC = importlib.util.spec_from_file_location('browser_gate', ROOT / 'tests/bijux-docs/execution/browser_gate.py')
GATE = importlib.util.module_from_spec(GATE_SPEC)
GATE_SPEC.loader.exec_module(GATE)


def inventory(profiles: bool, count: int = 1, *, profile_names=None) -> dict:
    selected = profile_names if profile_names is not None else PARTITIONS.REGISTRY['profiles'] if profiles else ['phone']
    projects = [{'name': f'{engine}-{profile}', 'engine': engine, 'count': count}
                for engine in PARTITIONS.ENGINES for profile in selected]
    return {'canonical_projects': projects,
            'cases': [{'id': f"{project['name']}-case-{index}", 'project': project['name']}
                      for project in projects for index in range(count)]}


def inventories() -> dict:
    return {suite: inventory(suite in ('navigation', 'search-scope', 'contrast'),
                             profile_names=['desktop'] if suite == 'registry-overflow' else None)
            for suite in PARTITIONS.SUITES}


class BrowserPartitionTests(unittest.TestCase):
    def test_all_canonical_projects_have_exactly_one_owner(self) -> None:
        assignments = PARTITIONS.plan(inventories())
        self.assertEqual(len(PARTITIONS.GROUPS), 26)
        self.assertEqual(len(PARTITIONS.SUITES), 23)
        self.assertEqual(len(assignments), 87)
        claimed = [(suite, name) for (_, suite), names in assignments.items() for name in names]
        expected = [(suite, project['name']) for suite, data in inventories().items() for project in data['canonical_projects']]
        self.assertCountEqual(claimed, expected)
        self.assertEqual(len(set(claimed)), len(claimed))
        self.assertEqual(assignments[('navigation-compact-webkit', 'navigation')], ['webkit-compact'])
        self.assertEqual(assignments[('search-scope-desktop-firefox', 'search-scope')], ['firefox-desktop'])
        self.assertEqual(assignments[('navigation-controls-chromium', 'drawer')], ['chromium-phone'])
        for engine in PARTITIONS.ENGINES:
            self.assertEqual(assignments[(f'registry-overflow-{engine}', 'registry-overflow')],
                             [f'{engine}-desktop'])
            self.assertEqual(assignments[(f'native-reader-history-{engine}', 'native-reader-history')],
                             [f'{engine}-phone'])

    def test_workflow_jobs_match_registry_and_keep_budget(self) -> None:
        workflow = (ROOT / '.github/workflows/bijux-std.yml').read_text()
        job = workflow.split('  navigation-browsers:', 1)[1].split('\n  navigation:', 1)[0]
        groups = re.search(r'group: \[([^\]]+)\]', job).group(1).split(', ')
        engines = re.search(r'engine: \[([^\]]+)\]', job).group(1).split(', ')
        self.assertEqual(groups, list(PARTITIONS.GROUPS))
        self.assertEqual(engines, list(PARTITIONS.ENGINES))
        self.assertIn('timeout-minutes: 3', job)
        self.assertIn('fail-fast: false', job)
        self.assertEqual(len(groups) * len(engines), 78)

    def test_contrast_profiles_preserve_all_thirty_nine_canonical_cases(self) -> None:
        data = inventories()
        data['contrast'] = inventory(True)
        for project in data['contrast']['canonical_projects']:
            project['count'] = 5 if project['name'].endswith('-phone') else 4
        data['contrast']['cases'] = [
            {'id': f"{project['name']}-contrast-{index}", 'project': project['name']}
            for project in data['contrast']['canonical_projects']
            for index in range(project['count'])
        ]
        assigned = PARTITIONS.plan(data)
        self.assertEqual(len(data['contrast']['cases']), 39)
        for engine in PARTITIONS.ENGINES:
            for profile in PARTITIONS.REGISTRY['profiles']:
                self.assertEqual(assigned[(f'contrast-{profile}-{engine}', 'contrast')],
                                 [f'{engine}-{profile}'])
                self.assertEqual(PARTITIONS.selection(f'contrast-{profile}', 'contrast', engine),
                                 {'BIJUX_UI_BROWSER_ENGINE': engine, 'BIJUX_UI_PROFILE': profile})

    def test_missing_or_overlapping_contrast_profile_cannot_reduce_coverage(self) -> None:
        missing = copy.deepcopy(PARTITIONS.REGISTRY)
        del missing['groups']['contrast-compact']
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            PARTITIONS.plan(inventories(), missing)
        overlap = copy.deepcopy(PARTITIONS.REGISTRY)
        overlap['groups']['contrast'] = [{'suite': 'contrast'}]
        with self.assertRaisesRegex(ValueError, 'Duplicate browser project ownership'):
            PARTITIONS.plan(inventories(), overlap)

    def test_missing_viewport_partition_is_rejected(self) -> None:
        registry = copy.deepcopy(PARTITIONS.REGISTRY)
        del registry['groups']['navigation-compact']
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            PARTITIONS.plan(inventories(), registry)

    def test_duplicate_profile_and_unbounded_overlap_are_rejected(self) -> None:
        for entries in ([{'suite': 'navigation', 'profile': 'phone'}], [{'suite': 'navigation'}]):
            registry = copy.deepcopy(PARTITIONS.REGISTRY)
            registry['groups']['overlapping-navigation'] = entries
            with self.subTest(entries=entries), self.assertRaisesRegex(ValueError, 'Duplicate browser project ownership'):
                PARTITIONS.plan(inventories(), registry)

    def test_empty_unknown_and_wrong_engine_profile_are_rejected(self) -> None:
        for profile in ('', 'tablet', 'desktop'):
            registry = copy.deepcopy(PARTITIONS.REGISTRY)
            registry['groups']['navigation-controls'][0]['profile'] = profile
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, 'Unknown viewport|owns no canonical'):
                PARTITIONS.plan(inventories(), registry)

    def test_missing_extra_or_miscounted_canonical_inventory_is_rejected(self) -> None:
        for mutation in ('missing suite', 'extra suite', 'missing case', 'duplicate case', 'unknown engine', 'duplicate project'):
            data = inventories()
            if mutation == 'missing suite':
                data.pop('drawer')
            elif mutation == 'extra suite':
                data['unowned'] = inventory(False)
            elif mutation == 'missing case':
                data['navigation']['cases'].pop()
            elif mutation == 'duplicate case':
                data['navigation']['cases'].append(data['navigation']['cases'][0])
            elif mutation == 'unknown engine':
                data['navigation']['canonical_projects'][0]['engine'] = 'unknown'
            else:
                data['navigation']['canonical_projects'].append(data['navigation']['canonical_projects'][0])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                PARTITIONS.plan(data)

    def test_exact_terminal_partition_reports_are_accepted(self) -> None:
        assignments = PARTITIONS.plan(inventories())
        reports = [(group, suite, {'assigned_project_names': names, 'status': 'passed',
                                  'qualification_kind': 'assigned_engine_shard'})
                   for (group, suite), names in assignments.items()]
        PARTITIONS.verify_reports(assignments, reports)

    def test_missing_duplicate_or_extra_partition_reports_are_rejected(self) -> None:
        assignments = PARTITIONS.plan(inventories())
        complete = [(group, suite, {'assigned_project_names': names, 'status': 'passed',
                                   'qualification_kind': 'assigned_engine_shard'})
                    for (group, suite), names in assignments.items()]
        for reports in (complete[:-1], complete + [complete[0]], complete[:-1] + [('unknown-chromium', 'drawer', complete[0][2])]):
            with self.subTest(reports=len(reports)), self.assertRaisesRegex(ValueError, 'Missing, duplicate or unexpected'):
                PARTITIONS.verify_reports(assignments, reports)

    def test_complete_coverage_cannot_hide_cross_profile_receipt_swaps(self) -> None:
        assignments = PARTITIONS.plan(inventories())
        reports = [(group, suite, {'assigned_project_names': names, 'status': 'passed',
                                  'qualification_kind': 'assigned_engine_shard'})
                   for (group, suite), names in assignments.items()]
        a = next(index for index, entry in enumerate(reports) if entry[:2] == ('navigation-phone-chromium', 'navigation'))
        b = next(index for index, entry in enumerate(reports) if entry[:2] == ('navigation-desktop-chromium', 'navigation'))
        reports[a] = (*reports[a][:2], reports[b][2])
        reports[b] = (*reports[b][:2], {'assigned_project_names': ['chromium-phone'], 'status': 'passed', 'qualification_kind': 'assigned_engine_shard'})
        with self.assertRaisesRegex(ValueError, 'assigned engine/profile'):
            PARTITIONS.verify_reports(assignments, reports)

    def test_nonterminal_failed_and_diagnostic_receipts_are_rejected(self) -> None:
        assignments = PARTITIONS.plan(inventories())
        for field, value in (('status', 'running'), ('status', 'failed'), ('status', 'cancelled'),
                             ('qualification_kind', 'selected_diagnosis')):
            reports = [(group, suite, {'assigned_project_names': names, 'status': 'passed',
                                      'qualification_kind': 'assigned_engine_shard'})
                       for (group, suite), names in assignments.items()]
            reports[0][2][field] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'nonterminal'):
                PARTITIONS.verify_reports(assignments, reports)

    def test_execution_selector_is_owned_by_registry(self) -> None:
        self.assertEqual(PARTITIONS.selection('navigation-phone', 'navigation', 'firefox'),
                         {'BIJUX_UI_BROWSER_ENGINE': 'firefox', 'BIJUX_UI_PROFILE': 'phone'})
        self.assertEqual(PARTITIONS.selection('navigation-controls', 'repository', 'webkit'),
                         {'BIJUX_UI_BROWSER_ENGINE': 'webkit'})
        for group, suite, engine in (('navigation-phone', 'drawer', 'firefox'), ('unknown', 'navigation', 'webkit'),
                                     ('navigation-phone', 'navigation', 'unknown')):
            with self.subTest(group=group, suite=suite, engine=engine), self.assertRaises(ValueError):
                PARTITIONS.selection(group, suite, engine)

    def test_ambient_selection_is_rejected_before_browser_setup(self) -> None:
        for name in ('BIJUX_UI_BROWSER_ENGINE', 'BIJUX_UI_PROJECTS', 'BIJUX_UI_PROFILE'):
            with self.subTest(name=name), patch.dict(GATE.os.environ, {name: ''}), \
                 patch.object(GATE, 'install_browser_runtime') as install, self.assertRaisesRegex(ValueError, 'assigned group'):
                GATE.run('navigation-phone', 'chromium')
            install.assert_not_called()


if __name__ == '__main__':
    unittest.main()
