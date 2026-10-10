from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from .policy_fixtures import ROOT, MODULE, source_fixture, projection_fixture, byte_tree
from .test_source_authority import committed_fixture


class CanonicalVerificationWorkflowTests(unittest.TestCase):
    @staticmethod
    def workflow():
        return MODULE.parse_workflow((ROOT/'shared/bijux-gh/workflows/github-policy.yml').read_bytes(), 'github-policy')

    def test_existing_event_job_and_source_range_semantics_survive(self):
        workflow = self.workflow()
        self.assertEqual(set(workflow['on']), {'push','pull_request','merge_group'})
        self.assertEqual(workflow['on']['push'], {'branches':['main'], 'tags':['v*']})
        self.assertEqual(set(workflow['jobs']), {'policy'})
        job = workflow['jobs']['policy'];self.assertEqual(job['name'], 'policy / github')
        self.assertEqual(job['timeout-minutes'], 10)
        gather = next(s for s in job['steps'] if s.get('name')=='Gather changed files')
        self.assertIn('${PR_BASE_SHA}...${PR_HEAD_SHA}', gather['run'])
        self.assertIn('complete checkout history', gather['run'])

    def test_parser_provision_is_pinned_conditional_and_actual_runtime_checked(self):
        steps = self.workflow()['jobs']['policy']['steps']
        setup = next(s for s in steps if s.get('name')=='Provision selected workflow parser')
        self.assertEqual(setup['uses'], 'ruby/setup-ruby@e81a8fa391b11a595c1b7ed84177cc0fe02faf83')
        self.assertEqual(setup['with']['ruby-version'], '3.3.12')
        self.assertEqual(setup['if'], "steps.workflow_source.outputs.requires_parser == 'true'")
        check = next(s for s in steps if s.get('name')=='Admit selected workflow parser runtime')
        self.assertEqual(check['if'], setup['if'])
        self.assertIn('RUBY_VERSION == "3.3.12"', check['run'])
        self.assertIn('YAML.respond_to?(:parse_stream)', check['run'])
        verify = next(s for s in steps if s.get('name')=='Verify canonical managed workflow projection')
        self.assertLess(steps.index(setup), steps.index(verify))
        self.assertLess(steps.index(verify), next(i for i,s in enumerate(steps) if s.get('name')=='Render generated .github files from manifest'))
        self.assertIn('${BIJUX_WORKFLOW_SOURCE_ROOT}/.github/scripts/check_workflow_projection.py', verify['run'])
        self.assertNotIn('sync_github_standards.py', verify['run'])

    def test_source_bootstrap_has_exact_official_fetch_and_artifact_ownership(self):
        step = next(s for s in self.workflow()['jobs']['policy']['steps'] if s.get('id')=='workflow_source')
        script=step['run']
        self.assertIn('https://github.com/bijux/bijux-std.git', script)
        self.assertIn('fetch --quiet --depth 1 origin "${source_sha}"', script)
        self.assertIn('FETCH_HEAD^{commit}', script)
        self.assertIn('${PWD}/artifacts/workflow-source.', script)
        self.assertIn('[[ ! -L artifacts ]]', script)
        self.assertIn("'bijux/bijux-std'", script)
        self.assertIn('--requires-parser', script)
        self.assertNotIn('BIJUX_STD_ALLOW_LOCAL_SOURCE', script)
        with tempfile.TemporaryDirectory() as workspace:
            file=Path(workspace)/'source-bootstrap.sh';file.write_text(script)
            subprocess.run(['bash','-n',str(file)],check=True,capture_output=True)

    def test_actual_candidate_cli_checks_read_only_and_reports_parser_false(self):
        with tempfile.TemporaryDirectory() as workspace:
            source, owned, sha, _ = committed_fixture(workspace)
            # Prepare governed outputs in this owning source fixture before binding a new source commit.
            expected=projection_fixture(source, owned, source, 'bijux-std')
            from .policy_fixtures import refresh_snapshots
            refresh_snapshots(source, owned)
            subprocess.run(['git','-C',str(source),'add','.github','shared','.bijux'],check=True,capture_output=True)
            subprocess.run(['git','-C',str(source),'commit','--quiet','-m','test(github): bind canonical candidate output'],check=True,capture_output=True)
            sha=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
            before=byte_tree(source)
            command=['python3',str(source/'.github/scripts/check_workflow_projection.py'),'--target',str(source),'--repo','bijux-std','--source-sha',sha,'--candidate']
            env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
            full=subprocess.run(command,env=env,capture_output=True,text=True)
            self.assertEqual(full.returncode,0,full.stderr)
            self.assertIn('candidate-only',full.stdout)
            parser=subprocess.run(command+['--requires-parser'],env=env,capture_output=True,text=True)
            self.assertEqual(parser.returncode,0,parser.stderr)
            self.assertEqual(parser.stdout.strip(),'false')
            self.assertEqual(before,byte_tree(source))
            self.assertEqual(subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True),'')


if __name__ == '__main__':
    unittest.main()
