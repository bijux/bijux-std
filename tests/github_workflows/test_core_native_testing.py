"""Core's native test context requires complete bounded worker evidence."""
import json
import unittest
from github_workflows.policy_fixtures import ROOT, RENDERER


class CoreNativeTestingTests(unittest.TestCase):
    def workflow(self):
        manifest = json.loads((ROOT / '.github/standards/repo-config.manifest.json').read_text())
        prepared = RENDERER.prepare_repo_files('bijux-core', manifest)
        return RENDERER.WORKFLOW_EXECUTION.parse_workflow(prepared['.github/workflows/ci.yml'], 'Core CI')

    def test_test_context_requires_every_bounded_producer_and_worker(self):
        jobs = self.workflow()['jobs']
        names = {'test_plan', 'test_libraries', 'test_binaries', 'test_tools', 'test_rust', 'test_python'}
        self.assertEqual(set(jobs['test']['needs']), names)
        self.assertIn('always()', jobs['test']['if'])
        for name in names | {'test'}:
            with self.subTest(job=name):
                self.assertEqual(jobs[name]['timeout-minutes'], 5)
                self.assertNotIn('continue-on-error', jobs[name])
                self.assertIn("github.event.pull_request.user.login != 'dependabot[bot]'", jobs[name]['if'])
        self.assertEqual(jobs['test']['env']['NATIVE_JOB_RESULTS'], '${{ toJSON(needs.*.result) }}')

    def test_rust_partitions_and_python_coverage_execute_independently(self):
        jobs = self.workflow()['jobs']
        self.assertFalse(jobs['test_rust']['strategy']['fail-fast'])
        self.assertEqual(jobs['test_rust']['strategy']['max-parallel'], 16)
        self.assertEqual(jobs['test_rust']['strategy']['matrix'], '${{ fromJSON(needs.test_plan.outputs.matrix) }}')
        self.assertNotIn('test_rust', jobs['test_python']['needs'])
        self.assertNotIn('test_python', jobs['test_rust']['needs'])
        self.assertIn('test_tools', jobs['test_rust']['needs'])
        self.assertIn('test_tools', jobs['test_python']['needs'])
        install = next(step for step in jobs['test_rust']['steps'] if step['name']=='Install the pinned test executor')
        self.assertEqual(install['with']['fallback'], 'none')
        self.assertEqual(install['with']['checksum'], 'true')
        self.assertIn('taiki-e/install-action@', install['uses'])

    def test_current_candidate_inputs_are_bound_to_their_producer(self):
        jobs = self.workflow()['jobs']
        for name in ['test_libraries','test_binaries','test_tools','test_rust','test_python','test']:
            env = jobs[name]['env']
            self.assertEqual(env['NATIVE_MANIFEST_SHA256'], '${{ needs.test_plan.outputs.manifest_sha256 }}')
            self.assertEqual(env['NATIVE_PLAN_SHA256'], '${{ needs.test_plan.outputs.plan_sha256 }}')
        self.assertTrue(any(step.get('with',{}).get('pattern')=='native-*proof*' for step in jobs['test']['steps']))
