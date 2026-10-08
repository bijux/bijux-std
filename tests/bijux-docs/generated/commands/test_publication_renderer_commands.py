"""Qualify real renderer command guards inside the admitted fixture environment."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tests"))
spec = importlib.util.spec_from_file_location("bijux_publication_command_fixture", ROOT / "tests/test_docs_site_verification.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class PublicationRendererCommandTests(unittest.TestCase):
    setUp = fixture.DocsSiteVerificationTests.setUp
    git = staticmethod(fixture.DocsSiteVerificationTests.git)
    make_profile = fixture.DocsSiteVerificationTests.make_profile

    def test_runtime_admission_rejects_changed_owned_bundle_before_cleanup(self):
        python=Path(sys.executable)
        self.assertTrue(python.is_file(), 'Run this suite with the admitted generated fixture interpreter')
        self.make_profile(python)
        (self.repo/'mkdocs.yml').write_text('site_name: Fixture\nsite_url: '+self.url+'\n')
        with (self.repo/'Makefile').open('a') as stream:
            stream.write('DOCS_CHECK_PRE_CLEAN_PATHS := artifacts/docs/site\n')
        asset=next((self.shared/'assets/javascripts').glob('material-search.*.js'))
        asset.write_bytes(asset.read_bytes()+b'\nInjected bytes\n')
        before=(self.site/'index.html').read_bytes()
        result=subprocess.run(['make','docs-check'],cwd=self.repo,env=self.env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('differs from exact admitted source',result.stderr)
        self.assertEqual((self.site/'index.html').read_bytes(),before)

    def test_actual_renderer_qualifies_supported_profile_or_rejects_unsupported_before_mutation(self):
        python=Path(sys.executable)
        self.assertTrue(python.is_file(), 'Run this suite with the admitted generated fixture interpreter')
        self.make_profile(python)
        (self.repo/'docs/index.md').write_text('# Fixture\n\nA public documentation page with searchable instructions.\n')
        config={
            'INHERIT':'mkdocs.shared.yml','site_name':'Fixture','site_url':self.url,'docs_dir':'docs','site_dir':'artifacts/docs/site',
            'strict':True,
            'theme':{'name':'material','custom_dir':'docs/overrides','font':False},
            'plugins':['search'],
            'extra':{'bijux':{'repository':'bijux-core','nav_mode':'default','theme_key':'bijux:theme'}},
            'extra_css':['assets/styles/extra.css'],'nav':[{'Home':'index.md'}]}
        encoded=subprocess.run([str(python),'-c','import json,sys,yaml; print(yaml.safe_dump(json.load(sys.stdin),sort_keys=False))'],
            input=json.dumps(config),text=True,capture_output=True,check=True).stdout
        (self.repo/'mkdocs.yml').write_text(encoded)
        (self.repo/'mkdocs.shared.yml').write_text('extra:\n  bijux:\n    repository: fixture\n')
        sync=subprocess.run([sys.executable,str(self.shared/'tooling/scripts/sync_mkdocs_hub.py'),
            str(self.repo),str(self.shared)],capture_output=True,text=True)
        self.assertEqual(sync.returncode,0,sync.stderr)
        # These baseline entries are authored consumer assets, rather than shared mirrors.
        for name in ('navigation-sync.js','external-links.js'):
            asset=self.repo/'docs/assets/javascripts'/name;asset.parent.mkdir(parents=True,exist_ok=True)
            asset.write_text('/* Public fixture-owned script; intentionally no behavior. */\n')
        hooks=self.repo/'docs/hooks/internal.py'
        hooks.parent.mkdir(parents=True,exist_ok=True)
        hooks.write_text('Private build implementation; never a public download')
        render_env=self.env.copy()
        render_env.update(DOCS_PUBLICATION_FRAMEWORK='1',BIJUX_DOCS_SHARED_DIR=str(self.shared),DOCS_CHECK_SITE_URL=self.url)
        render_env.pop('PYTHONDONTWRITEBYTECODE',None)
        before_public={path.relative_to(self.site).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in self.site.rglob('*') if path.is_file()}
        result=subprocess.run(['make','docs-check'],cwd=self.repo,env=render_env,capture_output=True,text=True)
        report_root=ROOT/'artifacts/website-delivery/renderer-command-qualification'/self._testMethodName
        report_root.mkdir(parents=True,exist_ok=True)
        (report_root/'command.log').write_text(result.stdout+result.stderr)
        for name in ('build-identity.json','csp.json','site-verification.json'):
            path=self.repo/'artifacts/website-security'/name
            if path.exists():
                shutil.copy2(path,report_root/name)
        if result.returncode == 0:
            retained=report_root/'consumer'
            if retained.exists():
                shutil.rmtree(retained)
            shutil.copytree(self.repo,retained)
        if result.returncode != 0:
            self.assertIn('Renderer profile: unsupported environment; retain actual hosted fingerprints and review a source-owned profile',
                          result.stderr)
            after_public={path.relative_to(self.site).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in self.site.rglob('*') if path.is_file()}
            self.assertEqual(after_public,before_public)
            for name in ('build-identity.json','csp.json','producer-reconstruction.json','site-verification.json'):
                receipt=json.loads((self.repo/'artifacts/website-security'/name).read_text())
                self.assertFalse(receipt['passed'])
                self.assertTrue(receipt['verification_only'])
            (report_root/'profile-availability.json').write_text(json.dumps({
                'state':'unsupported-profile-rejected-before-public-mutation',
                'known_profile_positive_executed':False,
                'positive_qualification_pending':True,
                'reopening_trigger':'Reviewed exact source-owned runtime profile and fresh committed environment qualification',
            },indent=2)+'\n')
            return
        (report_root/'profile-availability.json').write_text(json.dumps({
            'state':'known-verification-profile-qualified',
            'known_profile_positive_executed':True,
            'publication_approval':False,
        },indent=2)+'\n')
        route=json.loads(self.report.read_text())
        build=json.loads((self.repo/'artifacts/website-security/build-identity.json').read_text())
        csp=json.loads((self.repo/'artifacts/website-security/csp.json').read_text())
        self.assertTrue(route['passed'])
        self.assertTrue(route['verification_only'])
        self.assertEqual(build['state'],'complete')
        self.assertEqual(build['bundle_sha256'],route['bundle_sha256'])
        self.assertEqual(csp['bundle_sha256'],route['bundle_sha256'])
        self.assertGreater(route['search_entries'],0)
        self.assertIn('Content-Security-Policy',(self.site/'index.html').read_text())
        self.assertFalse((self.site/'overrides').exists())
        self.assertFalse((self.site/'hooks').exists())
        self.assertEqual(list(self.shared.rglob('__pycache__')),[])


class UnsupportedPublicationRendererCommandTests(unittest.TestCase):
    setUp = fixture.DocsSiteVerificationTests.setUp
    git = staticmethod(fixture.DocsSiteVerificationTests.git)
    make_profile = fixture.DocsSiteVerificationTests.make_profile

    def test_unreviewed_profile_rejects_before_public_artifact_mutation(self):
        table = self.shared / "security/renderer-producer-admission.json"
        table.write_text(json.dumps({"schema": 2, "profiles": []}) + "\n")
        PublicationRendererCommandTests.test_actual_renderer_qualifies_supported_profile_or_rejects_unsupported_before_mutation(self)
        result = json.loads((ROOT / "artifacts/website-delivery/renderer-command-qualification" / self._testMethodName / "profile-availability.json").read_text())
        self.assertEqual(result["state"], "unsupported-profile-rejected-before-public-mutation")
        self.assertFalse(result["known_profile_positive_executed"])
        self.assertTrue(result["positive_qualification_pending"])
