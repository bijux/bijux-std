"""Explicit Make selection preserves source ownership and literal argument boundaries."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
MAKE_SOURCE = ROOT/'shared/bijux-makes-py/ci/docs.mk'
spec = importlib.util.spec_from_file_location('bijux_interactive_make_fixture', ROOT/'tests/bijux-docs/generated/test_interactive_report_renderer.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


class InteractiveReportMakeDispatchTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT/'artifacts/qualification/interactive-report-dispatch/argument-fixtures'
        parent.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        self.calls = self.repo/'calls.jsonl'
        self.retained = self.repo/'artifacts/docs/site/retained.txt'
        self.retained.parent.mkdir(parents=True)
        self.retained.write_text('retained evidence')
        self.source = self.repo/'source.sh'
        self.source.write_text('#!/bin/sh\nexit 0\n')
        self.compiler = self.repo/'compiler.py'; self.compiler.write_text('')
        self.python = self.repo/'python'
        self.python.write_text(f'''#!{sys.executable}
import json,os,sys
from pathlib import Path
with Path({str(self.calls)!r}).open('a') as output: output.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1].endswith('compiler.py') and os.environ.get('REJECT_RUNTIME')=='1': sys.exit(1)
''')
        self.python.chmod(0o755)
        (self.repo/'mkdocs.yml').write_text('site_name: Argument boundary fixture\n')
        (self.repo/'Makefile').write_text(f'''PROJECT_DIR := $(CURDIR)
PROJECT_ARTIFACTS_DIR := $(CURDIR)/artifacts
MKDOCS_CFG := $(CURDIR)/mkdocs.yml
DOCS_PYTHON := {self.python}
DOCS_SOURCE_VERIFIER := {self.source}
DOCS_PUBLIC_URL_VALIDATOR := {ROOT}/shared/bijux-docs/tooling/quality/validate_production_url.py
DOCS_MATERIAL_COMPILER := {self.compiler}
BIJUX_DOCS_SHARED_DIR := {ROOT}/shared/bijux-docs
DOCS_BUILD_CONFIG_FILE := $(CURDIR)/mkdocs.yml
DOCS_CHECK_CONFIG_FILE := $(CURDIR)/mkdocs.yml
DOCS_BUILD_PREPARE_TARGETS := prepare-owned-inputs
DOCS_CHECK_PREPARE_TARGETS := prepare-owned-inputs
DOCS_BUILD_PRE_CLEAN_PATHS := artifacts/docs/site
DOCS_CHECK_PRE_CLEAN_PATHS := artifacts/docs/site
DOCS_SERVE_BOOTSTRAP_TARGETS := prepare-owned-inputs
include {MAKE_SOURCE}
.PHONY: prepare-owned-inputs
prepare-owned-inputs:
\t@touch prepared
''')

    def run_make(self, target, framework='1', owner='', command_owner=False, **environment):
        self.calls.unlink(missing_ok=True)
        env = {**os.environ, 'DOCS_PUBLICATION_FRAMEWORK':framework,
               'DOCS_INTERACTIVE_REPORT_OWNER':owner, **environment}
        command=['make','--no-print-directory',target]
        if command_owner:
            env['DOCS_INTERACTIVE_REPORT_OWNER']=''
            command.append('DOCS_INTERACTIVE_REPORT_OWNER='+owner.replace('$','$$'))
        result = subprocess.run(command,cwd=self.repo,env=env,capture_output=True,text=True,timeout=30)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []
        return result, calls

    def test_explicit_owner_is_one_literal_argument_for_both_framework_targets(self):
        owner = 'ops/website/owner-$(touch marker)-`touch marker`;"quoted".json'
        for target in ('docs','docs-check'):
            for command_owner in (False,True):
                with self.subTest(target=target,command_owner=command_owner):
                    result,calls = self.run_make(target,owner=owner,command_owner=command_owner)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    render = next(args for args in calls if args[0].endswith('render_publication.py'))
                    index = render.index('--interactive-report-owner')
                    self.assertEqual(render[index+1],owner)
                    self.assertEqual(render.count('--interactive-report-owner'),1)
                    self.assertFalse((self.repo/'marker').exists())
                    self.assertTrue((self.repo/'prepared').exists())

    def test_owner_requires_exact_framework_before_prepare_or_cleanup(self):
        for framework in ('0','2','invalid',''):
            for target in ('docs','docs-check'):
                with self.subTest(framework=framework,target=target):
                    result,calls = self.run_make(target,framework,owner='ops/website/report-owner.json')
                    self.assertNotEqual(result.returncode,0,result.stdout)
                    self.assertIn('DOCS_PUBLICATION_FRAMEWORK=1',result.stderr)
                    self.assertEqual(calls,[])
                    self.assertFalse((self.repo/'prepared').exists())
                    self.assertEqual(self.retained.read_text(),'retained evidence')

    def test_selected_raw_serve_refuses_before_lock_or_bootstrap(self):
        for target in ('docs-serve','docs-serve-run'):
            with self.subTest(target=target):
                result,calls = self.run_make(target,owner='ops/website/report-owner.json')
                self.assertNotEqual(result.returncode,0,result.stdout)
                self.assertIn('interactive reports require source-owned docs or docs-check',result.stderr)
                self.assertEqual(calls,[])
                self.assertFalse((self.repo/'prepared').exists())
                self.assertFalse((self.repo/'artifacts/docs/.cache').exists())
                self.assertEqual(self.retained.read_text(),'retained evidence')

    def test_empty_selector_preserves_native_and_framework_arguments(self):
        for framework in ('0','1'):
            for target in ('docs','docs-check'):
                with self.subTest(framework=framework,target=target):
                    result,calls = self.run_make(target,framework)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    self.assertFalse(any('--interactive-report-owner' in args for args in calls))
                    self.assertTrue(any(args[:2]==['-m','mkdocs'] for args in calls) if framework=='0'
                                    else any(args[0].endswith('render_publication.py') for args in calls))

    def test_runtime_refusal_preserves_prior_artifact_before_prepare(self):
        result,calls = self.run_make('docs-check',owner='ops/website/report-owner.json',REJECT_RUNTIME='1')
        self.assertNotEqual(result.returncode,0)
        self.assertTrue(any(args[0].endswith('compiler.py') for args in calls))
        self.assertFalse(any(args[0].endswith('render_publication.py') for args in calls))
        self.assertFalse((self.repo/'prepared').exists())
        self.assertEqual(self.retained.read_text(),'retained evidence')


class InteractiveReportMakeOwnershipTests(unittest.TestCase):
    setUp_source = fixture.InteractiveReportRendererTests.setUp_source
    git = staticmethod(fixture.InteractiveReportRendererTests.git)
    write = fixture.InteractiveReportRendererTests.write
    record = fixture.InteractiveReportRendererTests.record
    save_owner = fixture.InteractiveReportRendererTests.save_owner
    commit = fixture.InteractiveReportRendererTests.commit
    source = fixture.InteractiveReportRendererTests.source

    @classmethod
    def setUpClass(cls):
        fixture.InteractiveReportRendererTests.setUpClass.__func__(cls)

    def setUp(self):
        fixture.InteractiveReportRendererTests.setUp(self)
        fixture.fixture.PublicationRendererCommandTests.make_profile(self,sys.executable)
        with (self.repo/'Makefile').open('a') as output:
            output.write(f'BIJUX_DOCS_SHARED_DIR := {self.shared}\nDOCS_PUBLICATION_FRAMEWORK := 1\n')
        self.env.update(BIJUX_STD_LOCAL_VERIFY='1',DOCS_PYTHON=sys.executable)

    def run_make(self, target='docs-check', owner=None, **environment):
        env={**self.env,'DOCS_INTERACTIVE_REPORT_OWNER':self.owner_name if owner is None else owner,**environment}
        result=subprocess.run(['make','--no-print-directory',target],cwd=self.repo,env=env,capture_output=True,text=True,timeout=180)
        (self.output/(target+'.stdout.txt')).write_text(result.stdout)
        (self.output/(target+'.stderr.txt')).write_text(result.stderr)
        return result

    def test_actual_make_selected_and_reference_artifacts_reconstruct_for_both_targets(self):
        source_before=self.git(self.repo,'rev-parse','HEAD').stdout.strip()
        for target in ('docs','docs-check'):
            with self.subTest(target=target):
                result=self.run_make(target)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(self.git(self.repo,'rev-parse','HEAD').stdout.strip(),source_before)
                self.assertEqual((self.repo/'docs/report/records.html').read_text(),self.raw)
                receipt=json.loads((self.repo/'artifacts/website-security/producer-reconstruction.json').read_text())
                self.assertTrue(receipt['verification_only'])
                reports={name:json.loads((self.repo/('artifacts/website-security/'+name+'.json')).read_text())
                         for name in ('build-identity','csp','site-verification')}
                self.assertTrue(reports['site-verification']['passed'])
                self.assertEqual(len({reports[name]['bundle_sha256'] for name in reports}),1)
                owned=self.source();self.assertEqual(owned.source_sha,source_before)
                scope=owned.verify(self.site,reports['csp'],reports['build-identity'])
                scope.unchanged(self.site,reports['csp'])
                retained=self.output/target/'consumer'
                retained.parent.mkdir(parents=True,exist_ok=True)
                shutil.copytree(self.repo,retained,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
                self.assertTrue((self.site/'report/records.html').is_file())
                self.assertTrue((self.site/'search/search_index.json').is_file())

    def test_committed_config_cannot_autoactivate_without_explicit_make_selection(self):
        result=self.run_make(owner='')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('requires explicit renderer selection',result.stderr)

    def test_explicit_make_selector_cannot_replace_committed_configuration(self):
        result=self.run_make(owner='ops/website/unselected-owner.json')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('differs from committed configuration',result.stderr)

    def test_passive_selection_remains_incompatible_with_interactive_make_selection(self):
        result=self.run_make(BIJUX_DOCS_READER_OWNER=self.owner_name)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('cannot be mixed',result.stderr)

    def test_changed_source_cannot_reuse_committed_descriptor(self):
        self.write('docs/report/records.js','window.changedRecords=true;\n')
        result=self.run_make()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('fingerprint',result.stderr.lower())

    def test_unresolved_provider_owner_decisions_remain_refused(self):
        provider='https://tiles.example.invalid'
        self.owner['reports'][0]['providers']={provider:{'purpose':'Frozen fixture','activation':None,'attribution':'Fixture','terms':None}}
        self.owner['reports'][0]['provider_calls']=[{'callee':'L.tileLayer'}]
        self.save_owner();self.commit()
        result=self.run_make()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('provider',result.stderr.lower())


if __name__=='__main__':unittest.main()
