"""Prove the required report cannot succeed on incomplete rendered execution."""
from pathlib import Path
import os
import re
import subprocess
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
    def run_gate(self, repository, checks='success', navigation='success'):
        env = {**os.environ, 'GITHUB_REPOSITORY': repository,
               'CHECK_RESULT': checks, 'NAVIGATION_RESULT': navigation}
        return subprocess.run(['bash', '--noprofile', '--norc', '-c', gate()],
                              env=env, capture_output=True, text=True)

    def test_complete_shared_source_and_rendered_execution_passes(self):
        self.assertEqual(self.run_gate('bijux/bijux-std').returncode, 0)

    def test_shared_failure_cancellation_skip_or_absent_result_cannot_green_report(self):
        for prerequisite in ('checks', 'navigation'):
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
        self.assertIn('needs: [checks, navigation]', report)
        self.assertIn('if: ${{ always() &&', report)
        self.assertIn('CHECK_RESULT: ${{ needs.checks.result }}', report)
        self.assertIn('NAVIGATION_RESULT: ${{ needs.navigation.result }}', report)
        self.assertLess(report.index('Require applicable source and rendered checks'), report.index('Run standards report'))

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

    def test_every_shared_pull_request_author_receives_full_rendered_qualification(self):
        for name in ('navigation-fixtures', 'publication-commands', 'navigation'):
            with self.subTest(job=name):
                source = job(name)
                self.assertIn("github.repository == 'bijux/bijux-std'", source)
                self.assertNotIn('dependabot', source)
        aggregate = job('navigation')
        self.assertIn('needs: [navigation-fixtures, navigation-browsers, publication-commands, frontend-browser-faults, frontend-public-faults]', aggregate)
        for variable in ('FIXTURE_RESULT', 'BROWSER_RESULT', 'COMMAND_RESULT'):
            self.assertIn('test "$' + variable + '" = success', aggregate)


if __name__ == '__main__':
    unittest.main()
