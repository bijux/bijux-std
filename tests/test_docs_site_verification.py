"""Exercise exact production artifact verification and source rejection boundaries."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_public_site_routes as route_tests

ROOT=Path(__file__).resolve().parents[1]
SHARED=ROOT/'shared/bijux-docs'
PROJECTOR=SHARED/'tooling/scripts/project_bijux_docs.py'
spec=importlib.util.spec_from_file_location('bijux_site_projection',PROJECTOR)
projector=importlib.util.module_from_spec(spec)
spec.loader.exec_module(projector)


class DocsSiteVerificationTests(unittest.TestCase):
    def setUp(self):
        folder=ROOT/'artifacts/website-delivery'
        folder.mkdir(parents=True,exist_ok=True)
        self.sandbox=tempfile.TemporaryDirectory(prefix='site-verification-',dir=folder)
        self.addCleanup(self.sandbox.cleanup)
        self.base=Path(self.sandbox.name)
        self.repo=self.base/'consumer'
        self.shared=self.repo/'.bijux/shared/bijux-docs'
        shutil.copytree(SHARED,self.shared,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        checks=self.shared.parent/'bijux-checks/scripts'
        checks.mkdir(parents=True)
        for name in ('verify-accepted-source.sh','directory-tree-sha256.sh'):
            shutil.copy2(ROOT/'shared/bijux-checks/scripts'/name,checks/name)
        self.git(self.repo,'init','-q')
        self.git(self.repo,'config','user.email','bijux@example.invalid')
        self.git(self.repo,'config','user.name','Bijux verifier tests')
        projector.apply(self.repo,self.shared)
        fixture=route_tests.PublicSiteRouteTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.site=self.repo/'artifacts/docs/site'
        shutil.copytree(fixture.site,self.site)
        self.url=fixture.url
        self.command=['bash',str(self.shared/'tooling/scripts/verify_bijux_docs_site.sh')]
        self.env={**os.environ,'BIJUX_STD_LOCAL_VERIFY':'1','DOCS_PYTHON':sys.executable,
                  'DOCS_SITE_DIR':'artifacts/docs/site','SITE_URL':self.url,
                  'PYTHONDONTWRITEBYTECODE':'1'}
        self.report=self.repo/'artifacts/website-security/site-verification.json'
        self.git(self.repo,'add','.bijux','docs')
        self.git(self.repo,'commit','-qm','test(docs): define projected source')

    @staticmethod
    def git(root,*args):
        return subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,check=True)

    def verify(self,**env):
        return subprocess.run(self.command,cwd=self.repo,env={**self.env,**env},capture_output=True,text=True)

    def authority(self):
        upstream=self.base/'upstream'
        shutil.copytree(self.shared.parent,upstream/'shared')
        self.git(upstream,'init','-q')
        self.git(upstream,'config','user.email','bijux@example.invalid')
        self.git(upstream,'config','user.name','Bijux source tests')
        self.git(upstream,'add','shared')
        self.git(upstream,'commit','-qm','test(std): define exact local source')
        sha=self.git(upstream,'rev-parse','HEAD').stdout.strip()
        fetched=self.base/'fetched'
        self.git(self.base,'clone','-q',str(upstream),str(fetched))
        return dict(BIJUX_STD_LOCAL_VERIFY='0',BIJUX_STD_ALLOW_LOCAL_SOURCE='1',
                    BIJUX_STD_ROOT=str(fetched),BIJUX_STD_REF=sha,BIJUX_STD_GIT_URL=str(upstream))

    def test_candidate_verifies_exact_artifact_and_remains_candidate_only(self):
        result=self.verify()
        self.assertEqual(result.returncode,0,result.stderr)
        body=json.loads(self.report.read_text())
        self.assertTrue(body['passed'])
        self.assertTrue(body['verification_only'])
        self.assertEqual(body['site_dir'],'artifacts/docs/site')
        self.assertEqual(body['scope'],['PUBLIC-ROUTES','SEARCH-DELIVERY','PRODUCTION-URLS'])
        self.assertEqual(len(body['bundle_sha256']),64)
        self.assertEqual(body['source_checks']['mode'],'local_candidate')

    def test_missing_exact_artifact_never_discovers_another_successful_output(self):
        result=self.verify(DOCS_SITE_DIR='artifacts/docs/missing')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(json.loads(self.report.read_text())['passed'])
        self.assertTrue((self.site/'index.html').is_file())

    def test_missing_worker_replaces_previous_success_receipt_with_rejection(self):
        self.assertEqual(self.verify().returncode,0)
        (self.site/'assets/search.js').unlink()
        result=self.verify()
        self.assertNotEqual(result.returncode,0)
        body=json.loads(self.report.read_text())
        self.assertFalse(body['passed'])
        self.assertEqual(body['failure_stage'],'artifact_routes_search')
        self.assertTrue(any('search worker' in error for error in body['errors']))

    def test_exact_authority_is_mandatory_outside_explicit_local_verification(self):
        self.assertEqual(self.verify().returncode,0)
        result=self.verify(BIJUX_STD_LOCAL_VERIFY='0',BIJUX_STD_ROOT='',BIJUX_STD_REF='')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('BIJUX_STD_ROOT',result.stderr)
        self.assertFalse(json.loads(self.report.read_text())['passed'])
        self.assertEqual(json.loads(self.report.read_text())['failure_stage'],'source_before')

    def test_modified_projected_source_cannot_pass_a_valid_built_artifact(self):
        (self.repo/'docs/overrides/partials/nav.html').write_text('Changed generated navigation')
        result=self.verify()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Preserve authored changes to previously generated destination: docs/overrides/partials/nav.html',result.stderr)
        self.assertEqual(json.loads(self.report.read_text())['failure_stage'],'source_projection')

    def test_clean_locally_fetched_source_is_not_reported_as_github_acceptance(self):
        result=self.verify(**self.authority())
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(self.report.read_text())['verification_only'])
        self.assertIn('local-verification-only',result.stdout)

    def test_late_authority_drift_invalidates_already_passing_route_receipt(self):
        authority=self.authority()
        wrapper=self.base/'python-wrapper'
        wrapper.write_text('#!/usr/bin/env python3\nimport subprocess,sys\nfrom pathlib import Path\n'
            'result=subprocess.run(['+repr(sys.executable)+',*sys.argv[1:]])\n'
            'if sys.argv[1].endswith("validate_site_routes.py"):\n'
            ' Path('+repr(str(self.shared/'styles/extra.css'))+').write_text("Late source drift")\n'
            'raise SystemExit(result.returncode)\n')
        wrapper.chmod(0o755)
        result=self.verify(**authority,DOCS_PYTHON=str(wrapper))
        self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertIn('local shared docs differ',result.stderr)
        body=json.loads(self.report.read_text())
        self.assertFalse(body['passed'])
        self.assertEqual(body['failure_stage'],'source_after')







if __name__=='__main__':
    unittest.main()
