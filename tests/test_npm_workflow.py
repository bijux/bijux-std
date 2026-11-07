"""Inspect the credential boundary of the source-owned npm publisher."""
from pathlib import Path
import copy
import runpy
import unittest

ROOT=Path(__file__).resolve().parents[1]
POLICY=runpy.run_path(str(ROOT/'.github/scripts/check_workflow_projection.py'))['POLICY']


class NpmWorkflowTests(unittest.TestCase):
    def test_controller_admission_and_inspection_precede_the_only_oidc_job(self):
        source=POLICY.parse_workflow((ROOT/'shared/bijux-gh/workflows/release-npm.yml').read_bytes(),'release-npm')
        original=copy.deepcopy(source)
        policy={'publication_entrypoints':{'release-npm':{'mode':'manual-only','controller':'iac'}}}
        projected=POLICY.project_publication_entrypoints('release-npm',source,policy)
        self.assertEqual(set(projected['on']),{'workflow_dispatch'})
        self.assertEqual(source,original)
        jobs=projected['jobs']
        self.assertEqual(jobs['publication_admission']['permissions'],{'contents':'read','checks':'read'})
        self.assertNotIn('id-token',jobs['inspect'].get('permissions',{}))
        self.assertEqual(jobs['publish']['permissions']['id-token'],'write')
        self.assertEqual(jobs['publish']['environment'],'npm-publication')
        self.assertEqual(set(jobs['publish']['needs']),{'publication_admission','inspect'})
        self.assertIn('publication_admission',jobs['inspect']['needs'])
        self.assertTrue(projected['on']['workflow_dispatch']['inputs']['candidate_run_id']['required'])
        actions=[s.get('uses','') for s in jobs['publish']['steps']]
        self.assertTrue(any(a.startswith('actions/download-artifact@') for a in actions))
        self.assertFalse(any('npm run build' in s.get('run','') or 'npm pack' in s.get('run','') for s in jobs['publish']['steps']))
        self.assertIs(projected['concurrency']['cancel-in-progress'],False)


    def test_documentation_admission_does_not_reference_an_undeclared_release_tag(self):
        for workflow,wanted in [('deploy-docs',''),('release-npm','${{ inputs.release_tag }}')]:
            admission=POLICY.publication.controller_admission_job(workflow)
            self.assertEqual(admission['steps'][1]['env']['PUBLICATION_TAG'],wanted)
