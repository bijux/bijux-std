"""Actual selected/reference renderer and committed interactive capability failures."""
from pathlib import Path
import copy
import hashlib
import importlib
import importlib.util
import json
import os
import py_compile
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tests'))
spec = importlib.util.spec_from_file_location('bijux_interactive_fixture', ROOT/'tests/bijux-docs/generated/commands/test_publication_renderer_commands.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class InteractiveReportRendererTests(unittest.TestCase):
    setUp_source = fixture.PublicationRendererCommandTests.setUp
    git = staticmethod(fixture.PublicationRendererCommandTests.git)

    @classmethod
    def setUpClass(cls):
        profiles = load('bijux_interactive_observed_runtime', ROOT/'shared/bijux-docs/security/renderer_profiles.py')
        cls.observed_environment = profiles.environment_snapshot()

    def setUp(self):
        self.setUp_source()
        output_root = Path(os.environ.get('BIJUX_INTERACTIVE_TEST_ARTIFACTS_ROOT', ROOT/'artifacts/qualification/interactive-report-renderer'))
        self.output = output_root/self._testMethodName
        self.output.mkdir(parents=True, exist_ok=True)
        self.identity = load('bijux_interactive_identity', self.shared/'security/build_identity.py')
        profiles = load('bijux_interactive_profiles', self.shared/'security/renderer_profiles.py')
        environment = copy.deepcopy(self.observed_environment)
        admission = self.shared/'security/renderer-producer-admission.json'
        table = json.loads(admission.read_text())
        profile = {'id':'interactive-report-test-runtime','usage':'verification-only','environment':environment}
        external = [x for x in environment['startup_inputs'] if x['path'].startswith('stdlib/')
                    and not Path(x['resolved_target']).is_relative_to(Path(sys.base_prefix).resolve())]
        if external:
            profile['external_startup_review'] = {x['path']:{'sha256':x['sha256'],'resolved_target':x['resolved_target'],
                'recipe':'distro-apport-import-unavailable','purpose':'Retain guarded inactive distro startup in the isolated renderer fixture.'} for x in external}
        table['profiles'] = [p for p in table['profiles'] if p.get('environment') != environment]
        table['profiles'].append(profile); admission.write_text(json.dumps(table,indent=2)+'\n')
        self.profiles = profiles
        self.owner_name = 'ops/website/report-owner.json'
        self.repo.joinpath('.gitignore').write_text('artifacts/\n')
        self.repo.joinpath('docs/index.md').write_text('# Frozen records\n\nRead the frozen records and their documented limits.\n')
        config = {'INHERIT':'mkdocs.shared.yml','site_name':'Frozen records fixture','site_url':self.url,'docs_dir':'docs',
                  'site_dir':'artifacts/docs/site','strict':True,'theme':{'name':'material','custom_dir':'docs/overrides','font':False},
                  'plugins':['search'],'extra':{'bijux':{'repository':'bijux-core','nav_mode':'default','theme_key':'bijux:theme',
                  'interactive_report_owner':self.owner_name}},'extra_css':['assets/styles/extra.css'],'nav':[{'Home':'index.md'}]}
        import yaml
        self.repo.joinpath('mkdocs.yml').write_text(yaml.safe_dump(config,sort_keys=False))
        self.repo.joinpath('mkdocs.shared.yml').write_text('extra:\n  bijux:\n    repository: fixture\n')
        command=[sys.executable,str(self.shared/'tooling/scripts/sync_mkdocs_hub.py'),str(self.repo),str(self.shared)]
        result=subprocess.run(command,capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        self.assertEqual(result.returncode,0,result.stderr)
        for name in ('navigation-sync.js','external-links.js'):
            path=self.repo/'docs/assets/javascripts'/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('/* Authored fixture script, without application execution. */\n')
        self.body='window.frozenRecords=__DATA__;'
        self.report_body='window.frozenRecords={"records":[{"name":"frozen evidence"}]};'
        self.raw='<html><head><meta charset="utf-8"><link rel="icon" href="data:,"></head><body><h1>Frozen records</h1><script id="report-bootstrap" type="application/json">{"dataset":"records"}</script><script src="records.js"></script><script>'+self.report_body+'</script></body></html>'
        self.write('producer/report.html','<html><script>'+self.body+'</script></html>')
        self.write('docs/report/records.html',self.raw)
        self.write('docs/report/records.js','window.reportLabels=["frozen evidence"];\n')
        self.write('ops/website/report-readers.json',json.dumps({'schema':1,'readers':[{'output':'report/records.html','title':'Frozen record evidence',
            'purpose':'Read the frozen records and documented evidence limitations.','return_route':'index.html','search_route':'index.html','query':'Frozen'}]}))
        from mkdocs.config import load_config
        actual=load_config(config_file=str(self.repo/'mkdocs.yml'),site_dir=str(self.site))
        bootstrap=json.dumps({'dataset':'records'},sort_keys=True,separators=(',',':')).encode()
        self.owner={'schema':'owned-embedded-reports.v1','site_url':self.url,'config':self.record('mkdocs.yml'),
            'resolved_config_sha256':self.identity.configuration_identity(actual,self.repo),'producer_inputs':[self.record('producer/report.html')],
            'reports':[{'report_class':'interactive','output':'report/records.html','source':self.record('docs/report/records.html'),
                'resources':{'report/records.js':{'source':'docs/report/records.js','sha256':self.record('docs/report/records.js')['sha256'],
                'bytes':len((self.repo/'docs/report/records.js').read_bytes()),'kind':'reviewed-script'}},
                'reviewed_scripts':[hashlib.sha256(self.report_body.encode()).hexdigest()],
                'bootstrap_id':'report-bootstrap','bootstrap_sha256':hashlib.sha256(bootstrap).hexdigest(),
                'recipe':{'template':'producer/report.html','expansions':[],'slots':{'__DATA__':{'kind':'json'}}},
                'providers':{},'reviewed_provider_origins':[],'provider_calls':[]}],'parents':[],
            'reader_purpose':self.record('ops/website/report-readers.json')}
        self.save_owner();self.commit()
        policy=load('bijux_interactive_policy',self.shared/'security/csp.py')
        self.adapter=importlib.import_module(policy.embedded_module().__package__+'.interactive_rendering')
        self.passive=importlib.import_module(policy.embedded_module().__package__+'.rendering')
        self.command=[sys.executable,str(self.shared/'security/render_publication.py'),'--config','mkdocs.yml','--site-dir','artifacts/docs/site']
        self.env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
        self.env.pop('DOCS_SOURCE_IDENTITY',None);self.env.pop('BIJUX_DOCS_READER_OWNER',None)

    def write(self,name,value):
        path=self.repo/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value)

    def record(self,name):
        return {'path':name,'sha256':hashlib.sha256((self.repo/name).read_bytes()).hexdigest()}

    def save_owner(self):
        self.write(self.owner_name,json.dumps(self.owner,indent=2)+'\n')

    def commit(self):
        self.git(self.repo,'add','.bijux','docs','ops','producer','mkdocs.yml','mkdocs.shared.yml','.gitignore')
        self.git(self.repo,'-c','commit.gpgsign=false','commit','-qm','test(docs): own frozen interactive renderer inputs')

    def source(self,owner=None):
        return self.adapter.InteractiveReportSource(self.repo,owner or self.owner_name,'mkdocs.yml',self.owner['config']['sha256'],
                                                   self.owner['resolved_config_sha256'],self.url)

    def test_passive_boundary_still_rejects_interactive_source(self):
        with self.assertRaisesRegex(ValueError,'finite zero-executable') as failure:
            self.passive.ReaderSource(self.repo,self.owner_name,'mkdocs.yml',self.owner['config']['sha256'],self.owner['resolved_config_sha256'],self.url)
        (self.output/'failure-before.json').write_text(json.dumps({'boundary':'unchanged canonical passive ReaderSource',
            'source_sha':self.git(self.repo,'rev-parse','HEAD').stdout.strip(),'error':str(failure.exception)})+'\n')

    def test_selected_and_independent_reference_render_exact_interactive_bytes(self):
        result=subprocess.run(self.command+['--interactive-report-owner',self.owner_name],cwd=self.repo,env=self.env,capture_output=True,text=True)
        (self.output/'renderer.log').write_text(result.stdout+result.stderr)
        self.assertEqual(result.returncode,0,result.stderr)
        report_root=self.repo/'artifacts/website-security'
        reports={name:json.loads((report_root/(name+'.json')).read_text()) for name in ['build-identity','csp','producer-reconstruction','site-verification']}
        for name,value in reports.items():(self.output/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
        self.assertTrue(all(reports[n]['verification_only'] for n in ['build-identity','producer-reconstruction','site-verification']))
        self.assertTrue(reports['site-verification']['passed'])
        self.assertEqual(set(reports['site-verification']['standalone_readers']),{'report/records.html'})
        self.assertEqual(len({reports[n]['bundle_sha256'] for n in ['build-identity','csp','site-verification']}),1)
        page=next(p for p in reports['producer-reconstruction']['pages'] if p['path']=='report/records.html')
        self.assertEqual(page['class'],'source-owned-interactive-report');self.assertEqual(page['executables'],['report/records.js'])
        content=(self.site/'report/records.html').read_text();self.assertIn(self.report_body,content)
        self.assertIn('Return to documentation',content);self.assertIn('Search documentation',content)
        source=self.source();scope=source.verify(self.site,reports['csp'],reports['build-identity'])
        scope.unchanged(self.site,reports['csp']);self.assertEqual(scope.classes['report/records.html'],'interactive')
        classes, bodies = copy.deepcopy(scope.classes), copy.deepcopy(scope.bodies)
        scope.classes['report/records.html']='static-reader'
        with self.assertRaisesRegex(ValueError,'class or executable source changed'):scope.unchanged(self.site,reports['csp'])
        scope.classes=classes;scope.bodies['report/records.html'].append('window.injected=true;')
        with self.assertRaisesRegex(ValueError,'class or executable source changed'):scope.unchanged(self.site,reports['csp'])
        scope.bodies=bodies
        before=(self.site/'report/records.html').read_bytes();(self.site/'report/records.html').write_bytes(before+b'changed')
        with self.assertRaises(ValueError):scope.unchanged(self.site,reports['csp'])
        (self.site/'report/records.html').write_bytes(before)
        forged=copy.deepcopy(reports['csp']);forged['embedded']['descriptor_path']=str(self.repo/'ops/forged.json')
        with self.assertRaisesRegex(ValueError,'cannot select another'):source.verify(self.site,forged,reports['build-identity'])
        with self.assertRaisesRegex(ValueError,'not approved for publication'):self.profiles.select(self.shared,self.repo,publication=True)
        # Retain exact source/public bytes as historical evidence. Receipt owner
        # paths remain the actual runtime paths, without pretending this copy ran.
        retained=self.output/'consumer'
        if retained.exists():shutil.rmtree(retained)
        shutil.copytree(self.repo,retained,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        (self.output/'retained-fixture.json').write_text(json.dumps({'repository':str(self.repo),
            'source_sha':self.git(self.repo,'rev-parse','HEAD').stdout.strip(),
            'retained_exact_byte_copy':str(retained),'bundle_sha256':reports['build-identity']['bundle_sha256'],
            'scope':'committed verification-only source fixture; copy is evidence, not a new execution'},indent=2)+'\n')

    def test_selector_cannot_be_granted_by_another_committed_descriptor(self):
        other='ops/website/other-owner.json';self.write(other,(self.repo/self.owner_name).read_text());self.commit()
        with self.assertRaisesRegex(ValueError,'selector differs'):self.source(other)

    def test_untracked_descriptor_and_changed_source_cannot_select_scope(self):
        descriptor=self.repo/self.owner_name;descriptor.write_text(descriptor.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'untracked or differs'):self.source()

    def test_recipe_cannot_grant_unreviewed_executable_expression(self):
        self.owner['reports'][0]['recipe']['slots']['__DATA__']={'kind':'literal','values':['null']}
        self.save_owner();self.commit()
        with self.assertRaisesRegex(ValueError,'unreviewed executable'):self.source()

    def test_missing_committed_producer_cannot_be_receipt_authority(self):
        self.owner['producer_inputs']=[];self.save_owner();self.commit()
        with self.assertRaisesRegex(ValueError,'finite explicitly classified'):self.source()

    def test_unreviewed_provider_cannot_be_selected_from_complete_recipe(self):
        report=self.owner['reports'][0];provider='https://tiles.example.invalid'
        original=self.report_body;self.report_body+='L.tileLayer("'+provider+'/tiles/{z}");'
        self.raw=self.raw.replace(original,self.report_body);self.write('docs/report/records.html',self.raw)
        self.write('producer/report.html','<html><script>'+self.body+'L.tileLayer("'+provider+'/tiles/{z}");</script></html>')
        report['source']=self.record('docs/report/records.html');report['reviewed_scripts']=[hashlib.sha256(self.report_body.encode()).hexdigest()]
        report['providers']={provider:{'purpose':'Frozen geographic evidence','activation':None,'attribution':None,'terms':None}}
        report['provider_calls']=[{'callee':'L.tileLayer'}];self.owner['producer_inputs']=[self.record('producer/report.html')]
        self.save_owner();self.commit()
        with self.assertRaisesRegex(ValueError,'not owner-reviewed'):self.source()

    def test_provider_origin_without_actual_finite_call_cannot_gain_capability(self):
        report=self.owner['reports'][0];provider='https://tiles.example.invalid'
        report['providers']={provider:{'purpose':'Owner fixture','activation':'Explicit fixture control',
                                     'attribution':'Fixture attribution','terms':'Fixture local policy'}}
        report['reviewed_provider_origins']=[provider];report['provider_calls']=[{'callee':'L.tileLayer'}]
        self.save_owner();self.commit()
        with self.assertRaisesRegex(ValueError,'differ from actual reviewed executable calls'):self.source()

    def test_malformed_recipe_and_resource_fields_cannot_expand_authority(self):
        original=copy.deepcopy(self.owner)
        for mutation in ('slot','resource','report'):
            self.owner=copy.deepcopy(original)
            if mutation=='slot':self.owner['reports'][0]['recipe']['slots']['__DATA__']={'kind':'eval'}
            if mutation=='resource':self.owner['reports'][0]['resources']['report/records.js']['unreviewed']=True
            if mutation=='report':self.owner['reports'].append(None)
            self.save_owner();self.commit()
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.source()

    def test_actual_report_bootstrap_must_match_committed_registration_identity(self):
        self.owner['reports'][0]['bootstrap_sha256']='0'*64;self.save_owner();self.commit()
        with self.assertRaisesRegex(ValueError,'bootstrap differs'):self.source()

    def test_forged_publication_selection_cannot_replace_committed_configuration(self):
        other='ops/website/other-owner.json';self.write(other,(self.repo/self.owner_name).read_text());self.commit()
        source=self.source();checkpoint={'repository_source':{'sha':source.source_sha},'config':self.owner['config']}
        class VerifiedSource:
            configuration_identity=staticmethod(self.identity.configuration_identity)
            def verify_source(self,repository,selected):
                # Model only the already verified source checkpoint. The real
                # publisher additionally verifies GitHub source and profile.
                if selected!=checkpoint:raise ValueError('different checkpoint')
        forged={'embedded':{'descriptor_path':str(self.repo/other),'source_sha':source.source_sha}}
        with self.assertRaisesRegex(ValueError,'cannot select another'):
            self.adapter.verify_publication(self.site,forged,{},repository=self.repo,identity=VerifiedSource(),checkpoint=checkpoint)

    def test_report_resource_changed_after_source_selection_rejects(self):
        source=self.source();path=self.repo/'docs/report/records.js';path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'fingerprint differs'):source._descriptor()

    def test_resource_metadata_cannot_claim_different_committed_bytes(self):
        self.owner['reports'][0]['resources']['report/records.js']['bytes']+=1
        self.save_owner();self.commit()
        with self.assertRaisesRegex(ValueError,'reviewed byte count'):self.source()

    def test_serialized_scope_cannot_grant_interactive_executable_authority(self):
        with self.assertRaisesRegex(ValueError,'independently prepared in-process'):
            self.adapter.VerifiedInteractiveReports({'reports':['report/records.html']},self.site,{}, {},{})

    def test_distinct_standard_roots_have_separate_repeatable_processor_authority(self):
        first_policy=load('bijux_owned_root_policy',self.shared/'security/csp.py')
        first_publication=load('bijux_owned_root_publication',self.shared/'security/publication.py')
        other=self.base/'independent-standard'
        shutil.copytree(self.shared,other,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        second_policy=load('bijux_other_root_policy',other/'security/csp.py')
        second_publication=load('bijux_other_root_publication',other/'security/publication.py')
        for first_loader,second_loader in ((first_policy,second_policy),(first_publication,second_publication)):
            first,second=first_loader.embedded_module(),second_loader.embedded_module()
            self.assertIsNot(first,second)
            self.assertIs(first,first_loader.embedded_module())
            self.assertIs(second,second_loader.embedded_module())
            self.assertEqual(Path(first.__file__).resolve().parent,self.shared/'security/embedded_reports')
            self.assertEqual(Path(second.__file__).resolve().parent,other/'security/embedded_reports')
            self.assertEqual(first.processor_inputs(),second.processor_inputs())
            self.assertTrue(all(not Path(x['path']).is_absolute() for x in first.processor_inputs()))

    def test_changed_owned_processor_source_cannot_reuse_cached_module_authority(self):
        for filename in ('csp.py','publication.py'):
            policy=load('bijux_changing_root_'+filename,self.shared/'security'/filename)
            previous=policy.embedded_module()
            processor=self.shared/'security/embedded_reports/contract.py'
            before=processor.read_bytes();processor.write_bytes(before+b'\n# Owned source version under test.\n')
            current=policy.embedded_module()
            self.assertIsNot(current,previous)
            self.assertNotEqual(current.__package__,previous.__package__)
            self.assertIs(current,policy.embedded_module())
            processor.write_bytes(before)
            self.assertIs(previous,policy.embedded_module())

    def cached_processor_probe(self, filename):
        processor = self.shared/'security/embedded_reports/contract.py'
        processor.write_bytes(processor.read_bytes() + b'\nREVIEWED_CACHE_MARKER = "cached"\n')
        before, captured_stat = processor.read_bytes(), processor.stat()
        py_compile.compile(str(processor), doraise=True)
        fresh = before.replace(b'REVIEWED_CACHE_MARKER = "cached"', b'REVIEWED_CACHE_MARKER = "source"')
        self.assertEqual(len(before), len(fresh))
        processor.write_bytes(fresh)
        os.utime(processor, ns=(captured_stat.st_atime_ns, captured_stat.st_mtime_ns))
        policy = load('bijux_captured_processor_' + filename, self.shared/'security'/filename)
        admitted = policy.embedded_module()
        contract = importlib.import_module(admitted.__package__ + '.contract')
        observation = {'loader': filename, 'source_sha256': hashlib.sha256(fresh).hexdigest(),
                       'expected_marker': 'source', 'executed_marker': contract.REVIEWED_CACHE_MARKER,
                       'timestamp_valid_cached_bytecode_present': True,
                       'bytecode_writes_disabled': sys.dont_write_bytecode}
        (self.output/'processor-observation.json').write_text(json.dumps(observation, indent=2)+'\n')
        self.assertEqual(contract.REVIEWED_CACHE_MARKER, 'source')
        self.assertIs(admitted, policy.embedded_module())
        self.assertEqual(Path(contract.__file__).resolve(), processor.resolve())
        helper = processor.with_name('processor_loading.py')
        loader_input = next(item for item in admitted.processor_inputs()
                            if item['path'] == 'security/embedded_reports/processor_loading.py')
        self.assertEqual(loader_input['sha256'], hashlib.sha256(helper.read_bytes()).hexdigest())
        importlib.invalidate_caches()
        adapter = importlib.import_module(admitted.__package__ + '.interactive_rendering')
        self.assertEqual(Path(adapter.__file__).resolve(), processor.with_name('interactive_rendering.py').resolve())
        self.assertIs(admitted, policy.embedded_module())

    def test_csp_loader_executes_captured_source_despite_timestamp_valid_bytecode(self):
        self.cached_processor_probe('csp.py')

    def test_publication_loader_executes_captured_source_despite_timestamp_valid_bytecode(self):
        self.cached_processor_probe('publication.py')

    def test_passive_and_interactive_cli_selections_cannot_be_mixed(self):
        result=subprocess.run(self.command+['--reader-owner',self.owner_name,'--interactive-report-owner',self.owner_name],
                              cwd=self.repo,env=self.env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('cannot be mixed',result.stderr)


if __name__=='__main__':unittest.main()
