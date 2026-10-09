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

    def test_nested_relative_redirect_canonical_identifies_the_built_destination(self):
        self.write('retired/nested/index.html', '<html><head><link rel="canonical" '
                   'href="../../guide/"><meta http-equiv="refresh" '
                   'content="0; url=../../guide/"></head></html>')
        self.assertEqual(self.report()['errors'], [])
        self.assertEqual(self.report()['result'], 'pass')

    def test_relative_redirect_canonical_cannot_escape_or_misidentify_the_destination(self):
        for target in ('../../outside/', '../missing/', 'http://127.0.0.1/guide/',
                       'https://other.example/guide/', '../guide/?variant=1', '../guide/#use'):
            with self.subTest(target=target):
                self.write('retired/index.html', '<html><head><link rel="canonical" '
                           'href="' + target + '"><meta http-equiv="refresh" '
                           'content="0; url=' + target + '"></head></html>')
                self.assert_rejected('redirect canonical does not reach a built route')

    def test_relative_canonical_remains_invalid_on_an_ordinary_content_route(self):
        path = self.site/'guide/index.html'
        path.write_text(path.read_text().replace(self.url+'guide/', './'))
        self.assert_rejected('canonical must identify this production route')

    def test_actual_refresh_destination_requires_a_built_product_route(self):
        for destination in ('http://127.0.0.1:8123/missing/', 'https://outside.example/guide/',
                            'https://bijux.io/bijux-canon/', '../missing/'):
            with self.subTest(destination=destination):
                self.write('retired/index.html', '<html><head><link rel="canonical" href="'+self.url+
                           'guide/"><meta http-equiv="refresh" content="0; url='+destination+'"></head></html>')
                self.assert_rejected('redirect refresh')

    def test_actual_refresh_destination_must_agree_with_canonical(self):
        self.write('retired/index.html', '<html><head><link rel="canonical" href="'+self.url+
                   'guide/"><meta http-equiv="refresh" content="0; url=../"></head></html>')
        self.assert_rejected('redirect refresh destination differs from canonical')

    def test_actual_refresh_fragment_requires_the_destination_anchor(self):
        self.write('retired/index.html', '<html><head><link rel="canonical" href="'+self.url+
                   'guide/"><meta http-equiv="refresh" content="0; url=../guide/#missing"></head></html>')
        self.assert_rejected('redirect refresh anchor is missing')

    def test_refresh_declaration_requires_one_unambiguous_destination(self):
        for declaration in ('<meta http-equiv="refresh" content="0">',
                            '<meta http-equiv="refresh" content="0; url=">',
                            '<meta http-equiv="refresh" content="invalid; url=../guide/">',
                            '<meta http-equiv="refresh" content="٠; url=../guide/">',
                            '<meta http-equiv="refresh" content="0; url=\'../guide/">',
                            '<meta http-equiv="refresh" content="0; url=../guide/"><meta http-equiv="refresh" content="0; url=../">',
                            '<meta http-equiv="refresh" content="0; url=http://127.0.0.1/" content="0; url=../guide/">'):
            with self.subTest(declaration=declaration):
                self.write('retired/index.html', '<html><head><link rel="canonical" href="'+self.url+
                           'guide/">'+declaration+'</head></html>')
                self.assert_rejected('redirect refresh requires one unambiguous destination')

    def test_refresh_quotes_case_and_existing_fragment_preserve_valid_redirects(self):
        from html import escape
        for content in ('0; url=../guide/', "0; URL = '../guide/#use'", '0.5; url="../guide/#use"'):
            with self.subTest(content=content):
                self.write('retired/index.html', '<html><head><link rel="canonical" href="'+self.url+
                           'guide/"><meta http-equiv="REFRESH" content="'+escape(content,quote=True)+'"></head></html>')
                self.assertEqual(self.report()['errors'], [])

    def test_redirect_base_cannot_change_the_actual_refresh_destination(self):
        for base in ('http://127.0.0.1/', 'https://outside.example/',
                     'https://bijux.io/bijux-canon/', self.url+'guide/'):
            with self.subTest(base=base):
                self.write('retired/index.html', '<html><head><base href="'+base+'"><link rel="canonical" href="'+self.url+
                           'guide/"><meta http-equiv="refresh" content="0; url=../guide/"></head></html>')
                self.assert_rejected('unsupported redirect base href')
        self.write('retired/index.html', '<html><head><base href=""><link rel="canonical" href="'+self.url+
                   'guide/"><meta http-equiv="refresh" content="0; url=../guide/"></head></html>')
        self.assertEqual(self.report()['errors'], [])
        self.write('retired/index.html', '<html><head><base href="http://127.0.0.1/" href=""><link rel="canonical" href="'+self.url+
                   'guide/"><meta http-equiv="refresh" content="0; url=../guide/"></head></html>')
        self.assert_rejected('unsupported redirect base href')

    def test_self_refresh_and_multi_route_cycle_are_rejected(self):
        self.write('retired/index.html', '<html><head><link rel="canonical" href="'+self.url+
                   'retired/"><meta http-equiv="refresh" content="0; url=./"></head></html>')
        self.write('sitemap.xml', '<urlset>'+''.join('<url><loc>'+self.url+path+'</loc></url>'
                   for path in ('','guide/','retired/'))+'</urlset>')
        self.assert_rejected('redirect refresh cycle')
        for source,destination in (('retired/','another/'),('another/','retired/')):
            self.write(source+'index.html', '<html><head><link rel="canonical" href="'+self.url+
                       destination+'"><meta http-equiv="refresh" content="0; url=../'+destination+'"></head></html>')
        self.write('sitemap.xml', '<urlset>'+''.join('<url><loc>'+self.url+path+'</loc></url>'
                   for path in ('','guide/','retired/','another/'))+'</urlset>')
        self.assert_rejected('redirect refresh cycle')

    def test_finite_refresh_chain_reaches_existing_content(self):
        for source,destination in (('retired/','another/'),('another/','guide/')):
            self.write(source+'index.html', '<html><head><link rel="canonical" href="'+self.url+
                       destination+'"><meta http-equiv="refresh" content="0; url=../'+destination+'"></head></html>')
        self.write('sitemap.xml', '<urlset>'+''.join('<url><loc>'+self.url+path+'</loc></url>'
                   for path in ('','guide/','another/'))+'</urlset>')
        self.assertEqual(self.report()['errors'], [])

    def responsive(self, kind, value):
        from html import escape
        self.write('assets/image.svg','<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>')
        self.write('assets/retina.svg','<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"/>')
        encoded = escape(value,quote=True)
        if kind == 'img':
            markup = '<img src="assets/image.svg" srcset="'+encoded+'" sizes="100vw" alt="Illustration">'
        elif kind == 'source':
            markup = '<picture><source srcset="'+encoded+'" sizes="100vw"><img src="assets/image.svg" alt="Illustration"></picture>'
        else:
            markup = '<link rel="preload" as="image" href="assets/image.svg" imagesrcset="'+encoded+'" imagesizes="100vw">'
        self.write('index.html',self.html(self.url,'intro',markup,'assets/search.js'))

    def test_each_responsive_candidate_requires_its_delivered_asset(self):
        for kind in ('img','source','link'):
            with self.subTest(kind=kind):
                self.responsive(kind,'assets/image.svg 1x, assets/missing.svg 2x')
                self.assert_rejected('missing asset destination assets/missing.svg')

    def test_responsive_private_assets_cannot_inherit_development_link_exceptions(self):
        for kind in ('img','source','link'):
            with self.subTest(kind=kind):
                self.responsive(kind,'assets/image.svg 1x, http://127.0.0.1/private.svg 2x')
                report = qualify(self.site,self.url,[self.url],[dict(route='index.html',
                                 url='http://127.0.0.1/private.svg',purpose='An explicitly described development link.')])
                self.assertEqual(report['result'],'fail')
                self.assertTrue(any('development/private host' in e for e in report['errors']),report['errors'])
                self.assertTrue(all(not item['exempted'] for item in report['development_links']))

    def test_responsive_insecure_public_asset_is_rejected(self):
        for kind in ('img','source','link'):
            with self.subTest(kind=kind):
                self.responsive(kind,'assets/image.svg 1x, http://public.example/retina.svg 2x')
                self.assert_rejected('insecure active resource URL')

    def test_valid_responsive_density_and_width_sets_preserve_all_candidates(self):
        for kind in ('img','source','link'):
            for value in ('assets/image.svg 1x,assets/retina.svg 2x',
                          'assets/image.svg .5x, assets/retina.svg 1.5x',
                          'assets/image.svg 1e0x, assets/retina.svg 2E+0x',
                          'assets/image.svg 320w, assets/retina.svg 640w',
                          'assets/image.svg, assets/retina.svg 2x'):
                with self.subTest(kind=kind,value=value):
                    self.responsive(kind,value)
                    report = self.report()
                    self.assertEqual(report['errors'],[])
                    self.assertEqual(next(r for r in report['routes'] if r['path']=='index.html')['references'],3)

    def test_responsive_local_commas_and_encoded_paths_are_single_urls(self):
        self.write('assets/image,original.svg','<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.write('assets/εικόνα.svg','<svg xmlns="http://www.w3.org/2000/svg"/>')
        for kind in ('img','source','link'):
            with self.subTest(kind=kind):
                self.responsive(kind,'assets/image,original.svg 1x, assets/%CE%B5%CE%B9%CE%BA%CF%8C%CE%BD%CE%B1.svg 2x')
                self.assertEqual(self.report()['errors'],[])

    def test_responsive_data_uri_commas_preserve_the_following_network_boundary(self):
        data = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j5L8AAAAASUVORK5CYII='
        for kind in ('img','source','link'):
            with self.subTest(kind=kind):
                self.responsive(kind,data+' 1x, assets/retina.svg 2x')
                self.assertEqual(self.report()['errors'],[])
                self.responsive(kind,data+' 1x, https://private.internal/retina.svg 2x')
                self.assert_rejected('development/private host')

    def test_malformed_responsive_sets_cannot_hide_candidate_authority(self):
        values = (', assets/image.svg 1x', 'assets/image.svg 1x,, assets/retina.svg 2x',
                  'assets/image.svg,, assets/retina.svg 2x', 'assets/image.svg 0w',
                  'assets/image.svg 0x', 'assets/image.svg -1x', 'assets/image.svg NaNx',
                  'assets/image.svg 1e999x', 'assets/image.svg 1x 2x',
                  'assets/image.svg 1x, assets/retina.svg 1x',
                  'assets/image.svg 320w, assets/retina.svg 2x',
                  'assets/image.svg 1x, http://127.0.0.1/private.svg invalid',
                  'assets/image.svg (private, http://127.0.0.1/private.svg)')
        for kind in ('img','source','link'):
            for value in values:
                with self.subTest(kind=kind,value=value):
                    self.responsive(kind,value)
                    self.assert_rejected('invalid responsive asset candidates')

    def test_duplicate_responsive_attributes_cannot_replace_browser_authority(self):
        for markup in ('<img srcset="http://127.0.0.1/private.svg 1x" srcset="assets/search.js 1x">',
                       '<picture><source srcset="http://127.0.0.1/private.svg 1x" srcset="assets/search.js 1x"></picture>',
                       '<link rel="preload" as="image" imagesrcset="http://127.0.0.1/private.svg 1x" imagesrcset="assets/search.js 1x">'):
            with self.subTest(markup=markup):
                self.write('index.html',self.html(self.url,'intro',markup,'assets/search.js'))
                self.assert_rejected('invalid responsive asset candidates')

    def test_empty_responsive_attribute_retains_ordinary_fallback_validation(self):
        for kind in ('img','source','link'):
            with self.subTest(kind=kind):
                self.responsive(kind,'')
                self.assertEqual(self.report()['errors'],[])
                path = self.site/'index.html'
                path.write_text(path.read_text().replace('assets/image.svg','assets/missing.svg'))
                self.assert_rejected('missing asset destination assets/missing.svg')

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
