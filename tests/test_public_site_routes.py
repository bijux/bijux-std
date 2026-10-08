"""Exercise production route/search gates against deliberately broken artifacts."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT/'shared/bijux-docs/tooling/quality'
sys.path.insert(0,str(QUALITY))
from validate_site_routes import qualify


class PublicSiteRouteTests(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT/'artifacts/website-delivery'
        artifacts.mkdir(parents=True,exist_ok=True)
        self.sandbox = tempfile.TemporaryDirectory(prefix='public-routes-',dir=artifacts)
        self.addCleanup(self.sandbox.cleanup)
        self.site = Path(self.sandbox.name)/'site'
        self.url = 'https://bijux.io/bijux-core/'
        self.site.mkdir()
        self.write('index.html',self.html(self.url,'intro','<a href="guide/#use">Read guide</a><a href="https://bijux.io/">Hub</a>','assets/search.js'))
        self.write('guide/index.html',self.html(self.url+'guide/','use','<a href="../#intro">Home</a>','../assets/search.js'))
        self.write('assets/search.js','self.onmessage = () => {};')
        self.write('assets/site.css','body { color: teal; }')
        self.write('sitemap.xml','<urlset><url><loc>'+self.url+'</loc></url><url><loc>'+self.url+'guide/</loc></url></urlset>')
        self.write('search/search_index.json',json.dumps(dict(docs=[dict(location='',title='Home',text='Intro'),dict(location='guide/#use',title='Use',text='Instructions')],config={})))

    @staticmethod
    def html(canonical,anchor,content,worker):
        return '<html><head><link rel="canonical" href="'+canonical+'"></head><body><h1 id="'+anchor+'">Title</h1>'+content+'<script id="__config" type="application/json">'+json.dumps(dict(search=worker))+'</script></body></html>'

    def write(self,name,content):
        path=self.site/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(content)

    def report(self, network=None):
        return qualify(self.site,self.url,network or ['https://bijux.io/',self.url,'https://bijux.io/bijux-canon/'])

    def assert_rejected(self,text):
        report=self.report()
        self.assertEqual(report['result'],'fail')
        self.assertTrue(any(text in e for e in report['errors']),report['errors'])

    def test_complete_route_anchor_index_worker_artifact_passes(self):
        report=self.report()
        self.assertEqual(report['errors'],[])
        self.assertEqual(report['result'],'pass')
        self.assertEqual(report['route_count'],2)
        self.assertEqual(report['search_entries'],2)
        self.assertEqual(len(report['artifact_inventory_sha256']),64)

    def test_deep_route_cannot_reuse_root_canonical(self):
        path=self.site/'guide/index.html'
        path.write_text(path.read_text().replace(self.url+'guide/',self.url))
        self.assert_rejected('canonical must identify this production route')

    def test_loopback_canonical_is_rejected(self):
        path=self.site/'index.html'
        path.write_text(path.read_text().replace(self.url,'http://127.0.0.1:8000/'))
        self.assert_rejected('canonical must identify this production route')

    def test_missing_deep_destination_and_anchor_are_rejected(self):
        path=self.site/'index.html'
        path.write_text(path.read_text().replace('guide/#use','guide/#missing'))
        self.assert_rejected('missing anchor')
        path.write_text(path.read_text().replace('guide/#missing','not-published/'))
        self.assert_rejected('missing link destination')

    def test_redirect_route_requires_built_production_target_without_full_search_ui(self):
        self.write('old/index.html','<html><head><link rel="canonical" href="'+self.url+
                   'guide/"><meta http-equiv="refresh" content="0; url=../guide/"></head></html>')
        self.assertEqual(self.report()['errors'],[])
        path=self.site/'old/index.html'
        path.write_text(path.read_text().replace(self.url,'http://bijux.io/bijux-core/'))
        self.assert_rejected('redirect canonical does not reach a built route')

    def test_encoded_hostname_and_browser_backslash_cannot_bypass_public_url_check(self):
        original=(self.site/'index.html').read_text()
        for url in ('https://%31%32%37.0.0.1/', 'https://example.com:wrong/', 'https:\\\\127.0.0.1\\example'):
            with self.subTest(url=url):
                self.write('index.html',original.replace('</body>','<a href="'+url+'">Target</a></body>'))
                self.assert_rejected('malformed')

    def test_duplicate_ids_are_not_hidden_by_a_valid_target(self):
        path=self.site/'index.html'
        path.write_text(path.read_text().replace('</body>','<p id="intro">Duplicate</p></body>'))
        self.assert_rejected('duplicate document IDs')

    def test_missing_download_and_css_import_are_rejected(self):
        path=self.site/'index.html'
        path.write_text(path.read_text().replace('</body>','<a href="evidence.pdf">Evidence</a></body>'))
        self.write('assets/site.css','@import "missing.css";')
        self.assert_rejected('missing link destination evidence.pdf')
        self.assert_rejected('missing CSS asset missing.css')

    def test_search_index_404_fails_before_browser_promotion(self):
        (self.site/'search/search_index.json').unlink()
        self.assert_rejected('Search index is absent')

    def test_search_worker_404_fails_even_if_index_exists(self):
        (self.site/'assets/search.js').unlink()
        self.assert_rejected('configured search worker is absent')

    def test_wrong_cross_product_search_scope_is_rejected(self):
        self.write('search/search_index.json',json.dumps(dict(docs=[dict(location='https://bijux.io/bijux-canon/',title='Canon',text='Wrong scope')])))
        self.assert_rejected('destination escapes this product')

    def test_indexed_missing_heading_is_rejected(self):
        self.write('search/search_index.json',json.dumps(dict(docs=[dict(location='guide/#missing',title='Guide',text='Wrong anchor')])))
        self.assert_rejected('destination anchor is missing')

    def test_empty_index_cannot_be_reported_as_working_search(self):
        self.write('search/search_index.json',json.dumps(dict(docs=[])))
        self.assert_rejected('Search index is invalid')

    def test_invalid_or_loopback_sitemap_destination_is_rejected(self):
        self.write('sitemap.xml','<urlset><url><loc>http://localhost:8000/</loc></url></urlset>')
        self.assert_rejected('noncanonical/nonproduction/excluded routes')
        self.assert_rejected('missing eligible canonical routes')

    def test_root_hub_registry_links_do_not_require_other_products_inside_its_artifact(self):
        old=self.url
        self.url='https://bijux.io/'
        for name in ('index.html','guide/index.html','sitemap.xml'):
            path=self.site/name
            path.write_text(path.read_text().replace(old,self.url))
        path=self.site/'index.html'
        path.write_text(path.read_text().replace('</body>','<a href="bijux-canon/reference/">Canon reference</a></body>'))
        self.assertEqual(self.report()['errors'],[])

    def test_unicode_route_uses_encoded_canonical_and_resolved_anchor(self):
        from urllib.parse import quote
        encoded = quote('μέθοδος')
        self.write('μέθοδος/index.html',self.html(self.url+encoded+'/','science','', '../assets/search.js'))
        path=self.site/'index.html'
        path.write_text(path.read_text().replace('</body>','<a href="'+encoded+'/#science">Science</a></body>'))
        sitemap=self.site/'sitemap.xml'
        sitemap.write_text(sitemap.read_text().replace('</urlset>','<url><loc>'+self.url+encoded+'/</loc></url></urlset>'))
        self.assertEqual(self.report()['errors'],[])

    def test_symlink_asset_cannot_qualify_another_filesystem_source(self):
        (self.site/'assets/external.js').symlink_to(self.site/'assets/search.js')
        with self.assertRaisesRegex(ValueError,'symlink'):
            self.report()

    def test_public_external_development_links_cannot_hide_from_local_resolver(self):
        original = (self.site/'index.html').read_text()
        for url in ('http://localhost:8000/', 'https://127.0.0.1/', 'http://127.1:8000/',
                    'https://2130706433/', 'https://192.168.1.4/', 'https://[::1]/',
                    'http://api.internal/', 'https://portal.localhost./', 'http://100.64.0.1/'):
            with self.subTest(url=url):
                self.write('index.html',original.replace('</body>','<a href="'+url+'">Target</a></body>'))
                self.assert_rejected('development/private host')

    def test_development_link_exception_is_exact_documented_and_never_admits_resources(self):
        url = 'http://localhost:8000/'
        original = (self.site/'index.html').read_text()
        self.write('index.html',original.replace('</body>','<a href="'+url+'">Local tutorial</a></body>'))
        exception = dict(route='index.html',url=url,purpose='Open the local tutorial server after starting it')
        report = qualify(self.site,self.url,[self.url],[exception])
        self.assertEqual(report['result'],'pass')
        self.assertTrue(report['development_links'][0]['exempted'])
        self.write('index.html',original.replace('</body>','<script src="'+url+'"></script></body>'))
        report = qualify(self.site,self.url,[self.url],[exception])
        self.assertEqual(report['result'],'fail')
        self.assertFalse(report['development_links'][0]['exempted'])

    def test_css_and_forms_are_checked_for_development_and_insecure_urls(self):
        self.write('assets/site.css','@import "http://127.0.0.1:8000/local.css";')
        self.assert_rejected('development/private host')
        self.write('assets/site.css','body { color: teal; }')
        path = self.site/'index.html'
        path.write_text(path.read_text().replace('</body>','<form action="http://192.168.1.2/submit"></form></body>'))
        self.assert_rejected('development/private host')
        path.write_text(path.read_text().replace('http://192.168.1.2/submit','http://cdn.example.com/submit'))
        self.assert_rejected('insecure active resource')

    def test_ordinary_public_https_external_links_remain_external(self):
        path = self.site/'index.html'
        path.write_text(path.read_text().replace('</body>','<a href="https://github.com/bijux/bijux-std">Source</a></body>'))
        self.assertEqual(self.report()['result'],'pass')

    def test_malformed_placeholder_url_is_rejected_even_when_external(self):
        path = self.site/'index.html'
        path.write_text(path.read_text().replace('</body>','<a href="{{ source_url }}">Source</a></body>'))
        self.assert_rejected('malformed/unrendered public URL')

    def test_bundle_digest_matches_publication_inventory_and_records_mechanical_scope(self):
        from validate_site_routes import bundle_identity, SCOPES
        report = self.report()
        files, digest = bundle_identity(self.site)
        self.assertEqual(report['bundle_sha256'],digest)
        self.assertEqual(report['files'],files)
        self.assertEqual(report['scope'],SCOPES)
        self.assertTrue(report['passed'])
        self.assertTrue(report['verification_only'])

    def test_cli_requires_one_explicit_artifact_and_keeps_report_outside_public_bytes(self):
        relative=self.site.relative_to(ROOT)
        output=self.site.parent/'route-report.json'
        command=[sys.executable,str(QUALITY/'validate_site_routes.py'),'--repo-root',str(ROOT),'--site-dir',str(relative),'--site-url',self.url,'--output',str(output)]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(output.read_text())['result'],'pass')
        command[-1]=str(self.site/'route-report.json')
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.site/'route-report.json').exists())


if __name__=='__main__':
    unittest.main()
