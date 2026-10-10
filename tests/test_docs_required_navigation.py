"""Prove the required report cannot succeed on incomplete rendered execution."""
from pathlib import Path
import importlib.util
import os
import re
import subprocess
import tempfile
import unittest

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
    return '\n'.join(line[10:] for line in script.splitlines()) + '\n'


class RequiredNavigationTests(unittest.TestCase):
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

    def run_gate(self, repository, checks='success', navigation='success', catalogue=None, renderer=None):
        env = {**os.environ, 'GITHUB_REPOSITORY': repository,
               'GITHUB_RUN_ATTEMPT': '1', 'CHECK_RESULT': checks, 'NAVIGATION_RESULT': navigation,
               'CATALOGUE_RESULT': catalogue if catalogue is not None else ('success' if repository == 'bijux/bijux-std' else 'skipped'),
               'RENDERER_RESULT': renderer if renderer is not None else ('success' if repository == 'bijux/bijux-std' else 'skipped')}
        return subprocess.run(['bash', '--noprofile', '--norc', '-c', gate()],
                              env=env, capture_output=True, text=True)

    def test_complete_shared_source_and_rendered_execution_passes(self):
        self.assertEqual(self.run_gate('bijux/bijux-std').returncode, 0)

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
        self.assertIn('name: std / report\n', report)
        self.assertIn('needs: [checks, navigation, catalogue-renderer, renderer-controls]', report)
        self.assertIn('if: ${{ always() &&', report)
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

    def test_every_shared_pull_request_author_receives_full_rendered_qualification(self):
        for name in ('navigation-fixtures', 'publication-commands', 'renderer-controls', 'navigation'):
            with self.subTest(job=name):
                source = job(name)
                self.assertIn("github.repository == 'bijux/bijux-std'", source)
                self.assertNotIn('dependabot', source)
        aggregate = job('navigation')
        self.assertIn('needs: [navigation-fixtures, navigation-browsers, publication-commands, renderer-controls, frontend-browser-faults, frontend-public-faults, persisted-native-reader]', aggregate)
        for variable in ('FIXTURE_RESULT', 'BROWSER_RESULT', 'COMMAND_RESULT', 'RENDERER_RESULT', 'PERSISTED_RESULT'):
            self.assertIn('test "$' + variable + '" = success', aggregate)


    def test_native_cached_reader_is_a_required_separate_capability_job(self):
        native = job('persisted-native-reader')
        self.assertIn('name: std / persisted native reader / chromium', native)
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
        script = 'python3() { return 0; }\n' + script
        variables = ('FAULT_BROWSER_RESULT', 'FAULT_PUBLIC_RESULT', 'PERSISTED_RESULT',
                     'FIXTURE_RESULT', 'BROWSER_RESULT', 'COMMAND_RESULT', 'RENDERER_RESULT')
        for variable in variables:
            for outcome in ('success', 'failure', 'cancelled', 'skipped', '', 'pending'):
                env = {**os.environ, 'GITHUB_RUN_ATTEMPT': '1',
                       **{key: 'success' for key in variables}, variable: outcome}
                actual = subprocess.run(['bash', '--noprofile', '--norc', '-c', script], env=env, capture_output=True)
                with self.subTest(variable=variable, outcome=outcome):
                    self.assertEqual(actual.returncode == 0, outcome == 'success')

    def test_recovery_report_invokes_independent_latest_source_observer_and_propagates_failure(self):
        for result in (0, 1):
            script = f'python3() {{ printf "%s\\n" "$@"; return {result}; }}\n' + gate()
            env = {**os.environ, 'GITHUB_REPOSITORY': 'bijux/bijux-std', 'GITHUB_RUN_ATTEMPT': '2',
                   'GITHUB_RUN_ID': '123', 'EXPECTED_WORKFLOW_HEAD': 'a' * 40,
                   'CHECK_RESULT': 'failure', 'NAVIGATION_RESULT': 'failure',
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
