"""Prove the required report cannot succeed on incomplete rendered execution."""
from pathlib import Path
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from github_workflows.policy_fixtures import MODULE

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/bijux-std.yml'


def job(name):
    source = WORKFLOW.read_text()
    match = re.search(r'^  ' + re.escape(name) + r':\n(.*?)(?=^  [\w-]+:|\Z)', source, re.M | re.S)
    if match is None:
        raise AssertionError('Missing workflow job: ' + name)
    return match.group(1)


def gate():
    section = job('report')
    section = section.split('      - name: Require applicable source and rendered checks\n', 1)[1]
    section = section.split('      - name:', 1)[0]
    script = section.split('        run: |\n', 1)[1]
    return ('\n'.join(line[10:] for line in script.splitlines()) + '\n').replace(
        '${{ needs.input-plan.outputs.frontend }}', '$EXPECTED_FRONTEND')


class RequiredNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_docs_input_planning import InputPlanningMutationTests, capture
        cls.source_fixture = InputPlanningMutationTests()
        cls.source_fixture.setUp()
        cls.addClassCleanup(cls.source_fixture.doCleanups)
        fixture = cls.source_fixture
        shutil.copytree(ROOT / 'tests/bijux-docs/execution',
                        fixture.repo / 'tests/bijux-docs/execution', dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__'))
        fixture.commit('test(ci): retain actual verification source')
        fixture.base = fixture.git('rev-parse', 'HEAD')
        fixture.git('update-ref', 'refs/remotes/origin/main', fixture.base)
        fixture.put('.github/ISSUE_TEMPLATE/question.yml', 'repository question form')
        fixture.commit('test(ci): change source-only governance')
        cls.source_only_plan = capture(fixture.repo, fixture.git('rev-parse', 'HEAD'), fixture.base, 'pull_request')
        fixture.put('shared/bijux-docs/assets/runtime.js', 'changed runtime')
        fixture.commit('test(ci): require frontend execution')
        cls.current_plan = capture(fixture.repo, fixture.git('rev-parse', 'HEAD'), fixture.base, 'pull_request')
        cls.plan_path = fixture.repo / 'artifacts/bijux-docs/input-plan/plan.json'
        cls.plan_path.parent.mkdir(parents=True)
        cls.plan_path.write_text(json.dumps(cls.current_plan))
        cls.selection_path = cls.plan_path.with_name('selection.json')
        cls.select_plan(cls.current_plan)

    @classmethod
    def select_plan(cls, plan):
        env = {**os.environ, 'GITHUB_REPOSITORY': 'bijux/bijux-std', 'GH_TOKEN': '',
               'GITHUB_SHA': plan['checkout'], 'EXPECTED_BASELINE': cls.source_fixture.base,
               'GITHUB_EVENT_NAME': 'pull_request',
               'GITHUB_OUTPUT': str(cls.plan_path.with_name('outputs'))}
        result = subprocess.run([sys.executable, '-B',
            str(cls.source_fixture.repo / 'tests/bijux-docs/execution/input_planning/cli.py'), 'select'],
            cwd=cls.source_fixture.repo, env=env, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    def test_hub_diagram_command_failure_reaches_required_report(self):
        section = job('checks').split('      - name: Run matrix check\n', 1)[1].split('      - name:', 1)[0]
        script = section.split('        run: |\n', 1)[1]
        script = '\n'.join(line[10:] for line in script.splitlines()).replace('${{ matrix.check }}', 'contracts')
        directory = ROOT / 'artifacts/contracts/hub-diagrams'
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=directory) as fixture:
            fixture = Path(fixture)
            validator = fixture / '.bijux/shared/bijux-checks/scripts/validate-shared-contracts.sh'
            validator.parent.mkdir(parents=True)
            validator.write_text('#!/bin/bash\nexit 0\n')
            validator.chmod(0o755)
            make = fixture / 'make'
            make.write_text('#!/bin/bash\ntest "$*" = "docs-reader-ci DOCS_READER_BROWSER_FLAGS=--with-deps" || exit 87\nexit "${READER_EXIT:-0}"\n')
            make.chmod(0o755)
            for reader_exit in ('0', '1', '2', '124'):
                env = {**os.environ, 'GITHUB_REPOSITORY': 'bijux/bijux.github.io',
                       'READER_EXIT': reader_exit, 'PATH': str(fixture) + os.pathsep + os.environ['PATH']}
                completed = subprocess.run(['bash', '-e', '-c', script], cwd=fixture, env=env, capture_output=True, text=True)
                self.assertEqual(completed.returncode, int(reader_exit), completed.stderr)
                checks = 'success' if completed.returncode == 0 else 'failure'
                report = self.run_gate('bijux/bijux.github.io', checks=checks, navigation='skipped')
                self.assertEqual(report.returncode == 0, reader_exit == '0')

    def test_hub_dependency_pull_requests_cannot_skip_reader_contracts(self):
        for name in ('checks', 'report'):
            condition = job(name).split('    if: ', 1)[1].split('\n', 1)[0]
            self.assertIn("github.repository == 'bijux/bijux.github.io' ||", condition)
        checks = job('checks')
        self.assertIn("matrix.check == 'contracts' && (github.repository == 'bijux/bijux-std' || github.repository == 'bijux/bijux.github.io')", checks)
        self.assertIn('node-version: \'24.21.0\'', checks)
        self.assertIn('Retain hub diagram evidence', checks)

    def run_gate(self, repository, checks='success', navigation='success', catalogue=None, renderer=None,
                 frontend='true', frontend_result='success', plan_result='success'):
        env = {**os.environ, 'GITHUB_REPOSITORY': repository, 'GH_TOKEN': '',
               'GITHUB_RUN_ATTEMPT': '1', 'CHECK_RESULT': checks, 'NAVIGATION_RESULT': navigation,
               'CATALOGUE_RESULT': catalogue if catalogue is not None else ('success' if repository == 'bijux/bijux-std' else 'skipped'),
               'RENDERER_RESULT': renderer if renderer is not None else ('success' if repository == 'bijux/bijux-std' else 'skipped'),
               'PLAN_RESULT': plan_result, 'EXPECTED_FRONTEND': frontend,
               'GITHUB_SHA': self.current_plan['checkout'], 'EXPECTED_BASELINE': self.source_fixture.base,
               'GITHUB_EVENT_NAME': 'pull_request',
               **dict.fromkeys(('FIXTURE_RESULT', 'BROWSER_RESULT', 'COMMAND_RESULT', 'PERSISTED_RESULT',
                                'FAULT_BROWSER_RESULT', 'FAULT_PUBLIC_RESULT'), frontend_result)}
        return subprocess.run(['bash', '--noprofile', '--norc', '-c', gate()],
                              cwd=self.source_fixture.repo, env=env, capture_output=True, text=True)

    def test_complete_shared_source_and_rendered_execution_passes(self):
        result = self.run_gate('bijux/bijux-std')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_actual_required_gate_rejects_absent_tampered_or_failed_selection(self):
        original = self.plan_path.read_bytes()
        try:
            self.plan_path.unlink()
            self.assertNotEqual(self.run_gate('bijux/bijux-std').returncode, 0)
            altered = dict(self.current_plan, frontend=False)
            self.plan_path.write_text(json.dumps(altered))
            self.assertNotEqual(self.run_gate('bijux/bijux-std').returncode, 0)
        finally:
            self.plan_path.write_bytes(original)
        original_selection = self.selection_path.read_bytes()
        try:
            self.selection_path.unlink()
            self.assertNotEqual(self.run_gate('bijux/bijux-std').returncode, 0)
            selection = json.loads(original_selection)
            self.selection_path.write_text(json.dumps(dict(selection, frontend=False)))
            self.assertNotEqual(self.run_gate('bijux/bijux-std').returncode, 0)
            self.selection_path.write_text(json.dumps(dict(selection, proof={'status': 'passed'})))
            self.assertNotEqual(self.run_gate('bijux/bijux-std').returncode, 0)
        finally:
            self.selection_path.write_bytes(original_selection)
        self.assertNotEqual(self.run_gate('bijux/bijux-std', frontend='false').returncode, 0)
        self.assertNotEqual(self.run_gate('bijux/bijux-std', plan_result='failure').returncode, 0)
        self.assertNotEqual(self.run_gate('bijux/bijux-std', frontend_result='skipped').returncode, 0)

    def test_source_only_current_head_without_accepted_proof_requires_full_execution(self):
        full_plan = self.current_plan
        original_selection = self.selection_path.read_bytes()
        self.source_fixture.git('checkout', '--detach', self.source_only_plan['checkout'])
        self.current_plan = self.source_only_plan
        self.plan_path.write_text(json.dumps(self.current_plan))
        try:
            self.select_plan(self.current_plan)
            selection = json.loads(self.selection_path.read_text())
            self.assertTrue(selection['frontend'])
            self.assertEqual(selection['selection_kind'], 'accepted_proof_refused_full_execution')
            self.assertEqual(selection['refusal'], 'API token is required')
            self.assertIsNone(selection['proof'])
            self.assertNotEqual(self.run_gate('bijux/bijux-std', frontend='false',
                frontend_result='skipped', renderer='skipped', catalogue='skipped').returncode, 0)
            result = self.run_gate('bijux/bijux-std')
            self.assertEqual(result.returncode, 0, result.stderr)
            for context in ('checks', 'navigation'):
                self.assertNotEqual(self.run_gate('bijux/bijux-std', **{context: 'failure'}).returncode, 0)
            qualification = json.loads((self.plan_path.parent / 'report-qualification.json').read_text())
            self.assertTrue(qualification['frontend_executed'])
        finally:
            self.source_fixture.git('checkout', '--detach', full_plan['checkout'])
            self.current_plan = full_plan
            self.plan_path.write_text(json.dumps(full_plan))
            self.selection_path.write_bytes(original_selection)

    def test_shared_failure_cancellation_skip_or_absent_result_cannot_green_report(self):
        for prerequisite in ('checks', 'navigation', 'renderer'):
            for outcome in ('failure', 'cancelled', 'skipped', '', 'pending', 'SUCCESS'):
                with self.subTest(prerequisite=prerequisite, outcome=outcome):
                    self.assertNotEqual(self.run_gate('bijux/bijux-std', **{prerequisite: outcome}).returncode, 0)

    def test_consumer_requires_successful_checks_and_exact_inapplicable_navigation(self):
        self.assertEqual(self.run_gate('bijux/bijux-core', navigation='skipped').returncode, 0)
        for outcome in ('success', 'failure', 'cancelled', '', 'pending'):
            with self.subTest(navigation=outcome):
                self.assertNotEqual(self.run_gate('bijux/bijux-core', navigation=outcome).returncode, 0)
        for outcome in ('failure', 'cancelled', 'skipped', ''):
            with self.subTest(checks=outcome):
                self.assertNotEqual(self.run_gate('bijux/bijux-core', checks=outcome, navigation='skipped').returncode, 0)

    def test_required_report_materializes_after_failed_prerequisites(self):
        report = job('report')
        self.assertIn('name: ' + MODULE.dependency_prs.UNVERIFIED_JOB_PREFIX + 'std / report\n', report)
        self.assertIn('needs: [input-plan, checks, navigation, catalogue-renderer, renderer-controls,', report)
        self.assertIn('always() &&', report)
        self.assertIn("github.event.pull_request.user.login != 'dependabot[bot]'", report)
        self.assertIn('CHECK_RESULT: ${{ needs.checks.result }}', report)
        self.assertIn('NAVIGATION_RESULT: ${{ needs.navigation.result }}', report)
        self.assertLess(report.index('Require applicable source and rendered checks'), report.index('Run standards report'))

    def test_incomplete_catalogue_execution_cannot_green_required_report(self):
        for result in ('failure', 'cancelled', 'skipped', ''):
            with self.subTest(result=result):
                self.assertNotEqual(self.run_gate('bijux/bijux-std', catalogue=result).returncode, 0)

    def test_catalogue_execution_has_exact_disjoint_groups_and_retained_evidence(self):
        source = job('catalogue-renderer')
        self.assertIn('timeout-minutes: 3', source)
        self.assertIn('group: [source, renderer, typed-entrypoint, tracked-entrypoint]', source)
        self.assertIn('make ui-test-install-catalogue', source)
        self.assertIn('make ui-test-catalogue UI_CATALOGUE_GROUP=', source)
        self.assertIn('if: always()', source)
        self.assertIn('if-no-files-found: error', source)

    def test_renderer_controls_have_a_separate_required_receipt_owner(self):
        controls = job('renderer-controls')
        self.assertIn('timeout-minutes: 3', controls)
        self.assertIn('renderer_controls.py run', controls)
        path = ROOT / 'tests/bijux-docs/execution/renderer_controls.py'
        spec = importlib.util.spec_from_file_location('required_renderer_controls', path)
        registry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(registry)
        matrix = re.search(r'^        group: \[([^\]]+)\]', controls, re.M)
        self.assertIsNotNone(matrix)
        self.assertEqual(tuple(name.strip() for name in matrix.group(1).split(',')),
                         registry.GROUPS)
        self.assertIn('fail-fast: false', controls)
        self.assertIn('--group "${{ matrix.group }}"', controls)
        self.assertIn('name: docs-renderer-controls-${{ matrix.group }}-', controls)
        self.assertIn('path: artifacts/bijux-docs/renderer-controls', controls)
        self.assertIn('if: always()', controls)
        self.assertIn('if-no-files-found: error', controls)
        self.assertNotIn('ui-test-unit', job('navigation-fixtures'))
        aggregate = job('navigation')
        self.assertIn('Download exact renderer unit evidence', aggregate)
        self.assertIn('pattern: docs-renderer-controls-*-${{ github.sha }}-${{ github.run_attempt }}', aggregate)
        self.assertIn("controls.verify_groups(ARTIFACTS / 'renderer-controls')",
                      (ROOT / 'tests/bijux-docs/execution/browser_gate.py').read_text())
        self.assertIn('artifacts/bijux-docs/renderer-controls', aggregate)
        for outcome in ('failure', 'cancelled', 'skipped', ''):
            with self.subTest(outcome=outcome):
                self.assertNotEqual(self.run_gate('bijux/bijux-std', renderer=outcome).returncode, 0)
        self.assertNotEqual(self.run_gate('bijux/bijux-core', navigation='skipped', renderer='success').returncode, 0)


    def test_early_standards_and_contracts_do_not_wait_for_browser_jobs(self):
        checks = job('checks')
        self.assertIn('check: [standard, contracts]', checks)
        self.assertNotIn('    needs:', checks)
        self.assertNotIn('std / report', checks)

    def test_budget_observation_binds_event_head_and_attempt_with_read_only_access(self):
        report = job('report')
        self.assertIn('actions: read', report)
        self.assertNotIn('actions: write', report)
        self.assertIn('github.event.pull_request.head.sha || github.event.merge_group.head_sha || github.sha', report)
        self.assertIn('"run_attempt"] != int(os.environ["GITHUB_RUN_ATTEMPT"])', report)
        self.assertIn('"head_sha"] != os.environ["EXPECTED_WORKFLOW_HEAD"]', report)
        self.assertIn('--workflow-head "$EXPECTED_WORKFLOW_HEAD"', report)
        self.assertIn('artifacts/bijux-docs/job-budget', report)
        self.assertIn('range(2, math.ceil(jobs["total_count"] / 100) + 1)', report)
        self.assertLess(report.index('Verify complete frontend job duration'), report.index('Run standards report'))

    def test_fault_transport_retains_every_owned_receipt_file(self):
        browser = job('frontend-browser-faults')
        transport = browser.split('      - name: Retain intentional failure reports and clean controls\n', 1)[1]
        self.assertIn('          path: artifacts/bijux-docs/frontend-faults\n', transport)
        self.assertIn('          include-hidden-files: true\n', transport)
        self.assertIn('          if-no-files-found: error\n', transport)
        self.assertIn('        if: always()\n', transport)

    def test_public_fault_upload_preserves_complete_evidence_with_bounded_compression(self):
        public = job('frontend-public-faults')
        transport = public.split('      - name: Retain real public fixture and mutated artifact receipts\n', 1)[1]
        self.assertIn('    timeout-minutes: 3\n', public)
        self.assertIn('        if: always()\n', transport)
        self.assertIn('          path: artifacts/bijux-docs/frontend-faults/public\n', transport)
        self.assertIn('          if-no-files-found: error\n', transport)
        self.assertIn('          compression-level: 1\n', transport)
        self.assertNotIn('\n            !', transport)
        aggregate = job('navigation')
        self.assertIn('          path: artifacts/bijux-docs/frontend-faults/public\n', aggregate)
        self.assertIn('          name: docs-frontend-faults-public-${{ github.sha }}-${{ github.run_attempt }}\n', aggregate)

    def test_shared_human_pull_requests_keep_rendered_qualification(self):
        for name in ('navigation-fixtures', 'publication-commands', 'renderer-controls', 'navigation'):
            with self.subTest(job=name):
                source = job(name)
                self.assertIn("github.repository == 'bijux/bijux-std'", source)
                self.assertIn("github.event.pull_request.user.login != 'dependabot[bot]'", source)
                self.assertIn(MODULE.dependency_prs.UNVERIFIED_JOB_PREFIX, source)
        aggregate = job('navigation')
        self.assertIn('needs: [input-plan, navigation-fixtures, navigation-browsers, publication-commands, renderer-controls, frontend-browser-faults, frontend-public-faults, persisted-native-reader, catalogue-renderer]', aggregate)
        for variable in ('FIXTURE_RESULT', 'BROWSER_RESULT', 'COMMAND_RESULT', 'RENDERER_RESULT', 'PERSISTED_RESULT'):
            self.assertIn('test "$' + variable + '" = success', aggregate)


    def test_native_cached_reader_is_a_required_separate_capability_job(self):
        native = job('persisted-native-reader')
        self.assertIn('name: ' + MODULE.dependency_prs.UNVERIFIED_JOB_PREFIX + 'std / persisted native reader / chromium', native)
        self.assertIn('timeout-minutes: 3', native)
        self.assertIn('persisted_reader.py run', native)
        self.assertIn('include-hidden-files: true', native)
        self.assertIn('if-no-files-found: error', native)
        aggregate = job('navigation')
        self.assertIn('PERSISTED_RESULT: ${{ needs.persisted-native-reader.result }}', aggregate)
        self.assertIn('Download exact cached native reader evidence', aggregate)
        self.assertIn('artifacts/bijux-docs/persisted-reader', aggregate)
        execution = aggregate.split('      - name: Require successful jobs and complete unique engine coverage\n', 1)[1]
        execution = execution.split('        run: |\n', 1)[1]
        script = '\n'.join(line[10:] for line in execution.split('      - name:', 1)[0].splitlines())
        # Execute the entire ordinary shell branch; a controlled function replaces
        # native Python only, so every prerequisite remains a real shell refusal.
        script = 'python3() { return 0; }\n' + script.replace('${{ needs.input-plan.outputs.frontend }}', '$EXPECTED_FRONTEND')
        variables = ('FAULT_BROWSER_RESULT', 'FAULT_PUBLIC_RESULT', 'PERSISTED_RESULT',
                     'FIXTURE_RESULT', 'BROWSER_RESULT', 'COMMAND_RESULT', 'RENDERER_RESULT')
        for variable in variables:
            for outcome in ('success', 'failure', 'cancelled', 'skipped', '', 'pending'):
                env = {**os.environ, 'GITHUB_RUN_ATTEMPT': '1', 'EXPECTED_FRONTEND': 'true',
                       **{key: 'success' for key in variables}, variable: outcome}
                actual = subprocess.run(['bash', '--noprofile', '--norc', '-c', script], env=env, capture_output=True)
                with self.subTest(variable=variable, outcome=outcome):
                    self.assertEqual(actual.returncode == 0, outcome == 'success')

    def test_recovery_report_invokes_independent_latest_source_observer_and_propagates_failure(self):
        for result in (0, 1):
            script = f'python3() {{ printf "%s\\n" "$@"; if [[ "$1" == *job_budget.py ]]; then return {result}; fi; return 0; }}\n' + gate()
            env = {**os.environ, 'GITHUB_REPOSITORY': 'bijux/bijux-std', 'GITHUB_RUN_ATTEMPT': '2',
                   'GITHUB_RUN_ID': '123', 'EXPECTED_WORKFLOW_HEAD': 'a' * 40,
                   'EXPECTED_FRONTEND': 'true', 'CHECK_RESULT': 'failure', 'NAVIGATION_RESULT': 'success',
                   'CATALOGUE_RESULT': 'failure', 'RENDERER_RESULT': 'failure'}
            actual = subprocess.run(['bash', '--noprofile', '--norc', '-c', script], env=env, capture_output=True, text=True)
            self.assertEqual(actual.returncode, result)
            self.assertIn('--observe-latest', actual.stdout)
            self.assertIn('a' * 40, actual.stdout)

    def test_browser_execution_declaration_retains_hidden_native_body_members(self):
        transport = job('navigation-browsers').split('      - name: Retain exact shard receipts and failure diagnostics\n', 1)[1]
        self.assertIn('          include-hidden-files: true\n', transport)
        path = ROOT / 'tests/bijux-docs/execution/workflow_controllers.py'
        spec = importlib.util.spec_from_file_location('required_hidden_body', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as folder:
            hidden = Path(folder) / 'test-results/.last-run.json'
            hidden.parent.mkdir(); hidden.write_bytes(b'{"status":"passed"}')
            self.assertIn('test-results/.last-run.json', module.file_hashes(Path(folder)))


if __name__ == '__main__':
    unittest.main()
