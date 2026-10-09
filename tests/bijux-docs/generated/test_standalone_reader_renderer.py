"""Qualify finite passive readers using the actual installed MkDocs producer."""
from pathlib import Path
import gzip
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tests'))
spec = importlib.util.spec_from_file_location('bijux_static_renderer_commands', ROOT/'tests/bijux-docs/generated/commands/test_publication_renderer_commands.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


class StandaloneRendererTests(unittest.TestCase):
    setUp = fixture.PublicationRendererCommandTests.setUp
    git = staticmethod(fixture.PublicationRendererCommandTests.git)

    def test_committed_passive_reader_and_native_search_reconstruct_together(self):
        from mkdocs.config import load_config
        spec = importlib.util.spec_from_file_location('bijux_static_actual_identity', self.shared/'security/build_identity.py')
        identity = importlib.util.module_from_spec(spec); spec.loader.exec_module(identity)
        self.output = ROOT/'artifacts/qualification/standalone-reader-renderer'
        self.output.mkdir(parents=True, exist_ok=True)
        self.repo.joinpath('docs/index.md').write_text('# Sweden evidence\n\nRead the frozen unavailable-data notice and documentation.\n')
        config = {'INHERIT':'mkdocs.shared.yml','site_name':'Sweden reader fixture','site_url':self.url,'docs_dir':'docs',
                  'site_dir':'artifacts/docs/site','strict':True,'theme':{'name':'material','custom_dir':'docs/overrides','font':False},
                  'plugins':['search'],'extra':{'bijux':{'repository':'bijux-core','nav_mode':'default','theme_key':'bijux:theme'}},
                  'extra_css':['assets/styles/extra.css'],'nav':[{'Home':'index.md'}]}
        import yaml
        self.repo.joinpath('mkdocs.yml').write_text(yaml.safe_dump(config,sort_keys=False))
        self.repo.joinpath('mkdocs.shared.yml').write_text('extra:\n  bijux:\n    repository: fixture\n')
        synced = subprocess.run([sys.executable,str(self.shared/'tooling/scripts/sync_mkdocs_hub.py'),str(self.repo),str(self.shared)],capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        self.assertEqual(synced.returncode,0,synced.stderr)
        for name in ('navigation-sync.js','external-links.js'):
            path=self.repo/'docs/assets/javascripts'/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('/* Actual fixture-owned authored script. */\n')
        # Frozen passive notice from tracked Pollenomics source; no science executes.
        raw='<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>Sweden lake evidence richness</title>\n  <style>\n    body {\n      margin: 0;\n      font-family: ui-sans-serif, system-ui, sans-serif;\n      background: #f8fafc;\n      color: #0f172a;\n      display: grid;\n      min-height: 100vh;\n      place-items: center;\n    }\n    main {\n      max-width: 42rem;\n      padding: 2rem;\n      background: white;\n      border: 1px solid #cbd5e1;\n      border-radius: 1rem;\n      box-shadow: 0 20px 45px rgba(15, 23, 42, 0.08);\n    }\n    h1 {\n      margin-top: 0;\n    }\n    p {\n      line-height: 1.6;\n    }\n    .meta {\n      color: #475569;\n      font-size: 0.95rem;\n    }\n  </style>\n</head>\n<body>\n  <main>\n    <h1>Sweden lake evidence richness</h1>\n    <p>No Sweden lake candidates were available for this bundle because the required pollen context files were missing or did not produce any lake-basin candidates.</p>\n    <p class="meta">Version v66 · generated 2026-09-08</p>\n  </main>\n</body>\n</html>\n'
        path=self.repo/'docs/report/notice.html';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(raw)
        purpose={'schema':1,'readers':[{'output':'report/notice.html','title':'Sweden unavailable evidence','purpose':'Read the frozen unavailable-data notice and documentation limitations.','return_route':'index.html','search_route':'index.html','query':'Sweden'}]}
        ops=self.repo/'ops';ops.mkdir(exist_ok=True);(ops/'reader-purpose.json').write_text(json.dumps(purpose))
        record=lambda name:{'path':name,'sha256':hashlib.sha256((self.repo/name).read_bytes()).hexdigest()}
        actual=load_config(config_file=str(self.repo/'mkdocs.yml'),site_dir=str(self.site))
        descriptor={'schema':'owned-embedded-reports.v1','site_url':self.url,'config':record('mkdocs.yml'),
                    'resolved_config_sha256':identity.configuration_identity(actual,self.repo),'producer_inputs':[],
                    'reports':[{'report_class':'static-reader','output':'report/notice.html','source':record('docs/report/notice.html'),
                                'resources':{},'reviewed_scripts':[],'providers':{},'reviewed_provider_origins':[],'provider_calls':[]}],
                    'parents':[],'reader_purpose':record('ops/reader-purpose.json')}
        (ops/'reader-owner.json').write_text(json.dumps(descriptor))
        self.git(self.repo,'add','.bijux','docs','ops','mkdocs.yml','mkdocs.shared.yml')
        self.git(self.repo,'-c','commit.gpgsign=false','commit','-qm','test(docs): own actual passive reader and discovery inputs')
        command=[sys.executable,str(self.shared/'security/render_publication.py'),'--config','mkdocs.yml','--site-dir','artifacts/docs/site']
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
        env.pop('DOCS_SOURCE_IDENTITY',None);env.pop('BIJUX_DOCS_READER_OWNER',None)
        result=subprocess.run(command+['--reader-owner','ops/reader-owner.json'],cwd=self.repo,env=env,capture_output=True,text=True)
        (self.output/'actual-reader-renderer.log').write_text(result.stdout+result.stderr)
        for name in ('build-identity.json','csp.json','producer-reconstruction.json','site-verification.json'):
            receipt=self.repo/'artifacts/website-security'/name
            if receipt.exists(): shutil.copyfile(receipt,self.output/name)
        self.assertEqual(result.returncode,0,result.stderr)
        retained=self.output/'consumer'
        if retained.exists(): shutil.rmtree(retained)
        shutil.copytree(self.repo,retained,ignore=shutil.ignore_patterns('__pycache__'))
        build=json.loads((self.repo/'artifacts/website-security/build-identity.json').read_text())
        csp=json.loads((self.repo/'artifacts/website-security/csp.json').read_text())
        producer=json.loads((self.repo/'artifacts/website-security/producer-reconstruction.json').read_text())
        routes=json.loads((self.repo/'artifacts/website-security/site-verification.json').read_text())
        self.assertTrue(build['verification_only']);self.assertTrue(producer['verification_only']);self.assertTrue(routes['verification_only'])
        self.assertTrue(routes['passed']);self.assertEqual(set(routes['standalone_readers']),{'report/notice.html'})
        self.assertEqual(build['bundle_sha256'],csp['bundle_sha256']);self.assertEqual(build['bundle_sha256'],routes['bundle_sha256'])
        output=(self.site/'report/notice.html').read_text()
        self.assertNotIn('__config',output);self.assertNotIn('<script',output)
        self.assertIn('Return to documentation',output);self.assertIn('Search documentation',output)
        integration=identity.publication().embedded_module()
        embedded=importlib.import_module(integration.__package__+'.reader')
        restored=embedded.restore(output,'report/notice.html',purpose['readers'][0])
        self.assertEqual(restored.split('<body>',1)[1],raw.split('<body>',1)[1])
        index=json.loads((self.site/'search/search_index.json').read_text())
        self.assertEqual([doc for doc in index['docs'] if doc['location']=='report/notice.html'],[{'location':'report/notice.html','title':purpose['readers'][0]['title'],'text':purpose['readers'][0]['purpose']}])
        self.assertEqual(gzip.decompress((self.site/'sitemap.xml.gz').read_bytes()),(self.site/'sitemap.xml').read_bytes())
        scope=next(page for page in producer['pages'] if page['path']=='report/notice.html')
        self.assertEqual(scope['class'],'source-owned-static-reader');self.assertEqual(scope['executables'],[])
        (self.output/'observed.json').write_text(json.dumps({'actual_python':sys.version,'publication_approval':False,
            'current_exit':result.returncode,'bundle_sha256':build['bundle_sha256'],
            'dependency_profile':producer['renderer_profile'],'source_sha':self.git(self.repo,'rev-parse','HEAD').stdout.strip()},indent=2)+'\n')


if __name__=='__main__':unittest.main()
