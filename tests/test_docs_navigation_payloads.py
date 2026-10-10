"""Qualify serialized navigation ownership and source-bound route coverage."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared/bijux-docs/tooling/quality'))
from performance import navigation as nav

SHA = 'ab' * 20
IDENTITY = {'origin': nav.payloads.ORIGIN, 'sha': SHA, 'tree': '4' * 40,
            'authority': 'selected committed Git objects; remote acceptance is a separate obligation'}


def document(extra='', links='<a href="./">Home</a><a href="read/">Read</a>'):
    return ('<!doctype html><html><head><title>Ångström &amp; docs</title></head><body>'
        '<header data-md-component="header"><nav aria-label="Header">Brand🧬</nav></header>'
        '<nav data-md-component="tabs" aria-label="Tabs">Tabs</nav>'
        '<nav id="bijux-navigation" aria-label="Docs" data-bijux-nav-variant="complete">'+links+'</nav>'
        '<nav class="md-nav md-nav--secondary" aria-label="Contents"><a href="#topic">Topic</a></nav>'
        '<main><article id="topic"><h1>Δocument</h1>'+extra+'</article></main>'
        '<footer class="md-footer"><nav aria-label="Footer">Footer</nav></footer></body></html>').encode()


class NavigationRegions(unittest.TestCase):
    def test_utf8_offsets_exactly_slice_serialized_regions(self):
        raw = document()
        result = nav.Regions(raw)
        expected = '<header data-md-component="header"><nav aria-label="Header">Brand🧬</nav></header>'.encode()
        region = result.regions['header']
        self.assertEqual(raw[region['start_byte']:region['end_byte']], expected)
        self.assertEqual(region['bytes'], len(expected))
        self.assertEqual(region['sha256'], nav.payloads.fingerprint(expected)['sha256'])

    def test_multiline_utf8_offsets_preserve_original_spelling(self):
        raw = document().replace(b'<header', 'α\nβ\n<header'.encode()).replace(b'Brand', b'Brand\r\n')
        parsed = nav.Regions(raw)
        for value in parsed.regions.values():
            self.assertEqual(nav.payloads.fingerprint(raw[value['start_byte']:value['end_byte']])['bytes'], value['bytes'])
        self.assertIn(b'\r\n', raw[parsed.regions['header']['start_byte']:parsed.regions['header']['end_byte']])

    def test_nested_unowned_header_nav_is_counted_once(self):
        parsed = nav.Regions(document())
        self.assertEqual(set(parsed.regions), {'header','tabs','primary-navigation','local-toc','footer'})
        self.assertEqual(len(parsed.regions['header']['links']), 0)
        spans = sorted((item['start_byte'], item['end_byte']) for item in parsed.regions.values())
        self.assertTrue(all(a[1] <= b[0] for a,b in zip(spans,spans[1:])))

    def test_canonical_tabs_inside_header_are_attributed_without_double_counting(self):
        raw=document().replace(b'Brand',b'<nav data-md-component="tabs" aria-label="Site">Site</nav>Brand')
        parsed=nav.Regions(raw)
        child=parsed.regions['header']['contained_landmarks'][0]
        self.assertEqual(child['accounted_by'],'header')
        self.assertEqual(raw[child['start_byte']:child['end_byte']],b'<nav data-md-component="tabs" aria-label="Site">Site</nav>')
        spans=sorted((v['start_byte'],v['end_byte']) for v in parsed.regions.values())
        self.assertTrue(all(a[1]<=b[0] for a,b in zip(spans,spans[1:])))

    def test_duplicate_primary_landmark_is_rejected(self):
        duplicate='<nav id="bijux-navigation" aria-label="Docs" data-bijux-nav-variant="complete"></nav>'
        with self.assertRaisesRegex(ValueError,'Duplicate'): nav.Regions(document(duplicate))

    def test_nested_selected_landmark_is_not_double_counted(self):
        raw = document().replace(b'Brand', b'<nav class="md-nav--secondary" aria-label="Contents"></nav>Brand')
        with self.assertRaisesRegex(ValueError,'Nested owned'): nav.Regions(raw)

    def test_unknown_primary_variant_cannot_claim_complete_graph(self):
        with self.assertRaisesRegex(ValueError,'exact complete'): nav.Regions(document().replace(b'variant="complete"',b'variant="compact"'))

    def test_primary_id_on_other_element_is_refused(self):
        raw=document().replace(b'<nav id="bijux-navigation"',b'<div id="bijux-navigation"')
        with self.assertRaisesRegex(ValueError,'exact complete'): nav.Regions(raw)

    def test_missing_header_cannot_be_zero_bytes(self):
        raw=document().replace(b'data-md-component="header"',b'data-component="other"')
        with self.assertRaisesRegex(ValueError,'Missing required'): nav.Regions(raw)

    def test_duplicate_attributes_are_ambiguous(self):
        with self.assertRaisesRegex(ValueError,'Duplicate HTML attributes'): nav.Regions(document().replace(b'id="topic"',b'id="topic" id="other"'))

    def test_duplicate_ids_are_ambiguous(self):
        with self.assertRaisesRegex(ValueError,'Duplicate document ID'): nav.Regions(document('<span id="topic"></span>'))

    def test_script_and_comment_tag_text_does_not_create_landmarks(self):
        extra='<!-- <nav id="bijux-navigation"></nav> --><script>const text="<nav id=bijux-navigation></nav>";</script>'
        self.assertEqual(len(nav.Regions(document(extra)).regions),5)

    def test_svg_self_closing_and_html_void_tags_preserve_regions(self):
        raw=document('<svg><path d="M0 0"/></svg><img alt="x" src="x.png"><br>')
        self.assertEqual(len(nav.Regions(raw).regions),5)

    def test_malformed_closing_and_unclosed_regions_are_refused(self):
        for raw in [document().replace(b'</header>',b'</div>'),document().replace(b'</html>',b'')]:
            with self.subTest(raw=raw[-40:]), self.assertRaises(ValueError): nav.Regions(raw)

    def test_invalid_utf8_does_not_produce_byte_estimates(self):
        with self.assertRaises(UnicodeError): nav.Regions(document()+b'\xff')


class NavigationInventory(unittest.TestCase):
    def setUp(self):
        parent=Path(os.environ.get('BIJUX_NAVIGATION_TEST_ARTIFACTS',ROOT/'artifacts/qualification/navigation-payload-accounting/controls'))
        parent.mkdir(parents=True,exist_ok=True)
        self.directory=tempfile.TemporaryDirectory(prefix='owned-navigation-',dir=parent)
        self.addCleanup(self.directory.cleanup)
        self.repo=Path(self.directory.name)
        self.site=self.repo/'artifacts/site'
        self.config=self.repo/'artifacts/config.yml'
        self.manifest=self.repo/'artifacts/inventory.json'
        self.standard=self.repo/'standard';self.standard.mkdir()
        self.templates={'partials/header.html':b'owned header producer','partials/nav.html':b'owned navigation producer'}
        self.data={'index.html':document(), 'read/index.html':document(links='<a href="../">Home</a><a href="./">Read</a>'),
                   '404.html':document('<h1>Not found</h1>')}
        self.inventory={'schema':1,'source':IDENTITY,'producer_inputs':{},'retained_generation':{'scope':'controlled unit fixture, not rendered evidence'}}
        self.config.parent.mkdir(parents=True,exist_ok=True)
        self.config.write_text('site_url: https://example.org/docs/\nuse_directory_urls: true\nnav:\n- Home: index.md\n- Read: read.md\n')
        for name,raw in self.data.items():
            path=self.site/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        for name,raw in self.templates.items():
            path=self.repo/'artifacts/producer'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            self.inventory['producer_inputs'][name]={'path':path.relative_to(self.repo).as_posix(),**nav.payloads.fingerprint(raw)}
        self.refresh()
        patches=[mock.patch.object(nav.payloads,'source_identity',return_value=IDENTITY),
                 mock.patch.object(nav.payloads,'committed_file',side_effect=lambda root,sha,name:self.templates[name]),
                 mock.patch.object(nav.payloads,'_git',return_value=('\n'.join('shared/bijux-docs/'+n for n in self.templates)+'\n').encode())]
        for patch in patches: patch.start();self.addCleanup(patch.stop)

    def refresh(self):
        self.inventory['configuration']={'path':self.config.relative_to(self.repo).as_posix(),**nav.payloads.fingerprint(self.config.read_bytes())}
        self.inventory['html_files']={p.relative_to(self.site).as_posix():nav.payloads.fingerprint(p.read_bytes()) for p in sorted(self.site.rglob('*.html'))}
        self.save()

    def save(self): self.manifest.write_text(json.dumps(self.inventory))
    def qualify(self): return nav.qualify(self.repo,self.site,self.config,self.manifest,self.standard,SHA)

    def test_exact_complete_inventory_passes_and_404_is_separate(self):
        report=self.qualify();self.assertEqual(report['result'],'pass')
        self.assertEqual((report['html_files'],report['normal_routes'],report['not_found_routes']),(3,2,1))
        self.assertEqual(report['configured_navigation_routes'],['index.html','read/index.html'])
        self.assertEqual(report['normal_raw_html_bytes'],sum(len(self.data[n]) for n in ['index.html','read/index.html']))

    def test_regions_and_remaining_bytes_partition_each_raw_document(self):
        for page in self.qualify()['pages']:
            self.assertEqual(page['raw_region_bytes']+page['remaining_html_bytes'],page['raw_html']['bytes'])
            self.assertEqual(page['raw_region_bytes'],sum(r['bytes'] for r in page['regions'].values()))

    def test_raw_repetition_never_certifies_encoded_wire_or_reduction(self):
        report=self.qualify()
        self.assertTrue(all(v['value'] is None for v in report['network_quantities'].values()))
        self.assertNotIn('reduction_target',report)

    def test_stale_source_identity_is_rejected(self):
        self.inventory['source']={**IDENTITY,'sha':'5'*40};self.save()
        with self.assertRaisesRegex(ValueError,'stale'):self.qualify()

    def test_stale_template_fingerprint_is_rejected(self):
        self.inventory['producer_inputs']['partials/header.html']['sha256']='0'*64;self.save()
        with self.assertRaisesRegex(ValueError,'Producer input differs'):self.qualify()

    def test_changed_projected_template_is_rejected(self):
        (self.repo/self.inventory['producer_inputs']['partials/nav.html']['path']).write_bytes(b'other nav')
        with self.assertRaisesRegex(ValueError,'Projected template differs'):self.qualify()

    def test_missing_template_owner_is_rejected(self):
        del self.inventory['producer_inputs']['partials/nav.html'];self.save()
        with self.assertRaisesRegex(ValueError,'complete shared template'):self.qualify()

    def test_unknown_template_owner_is_rejected(self):
        self.inventory['producer_inputs']['partials/other.html']=copy.deepcopy(self.inventory['producer_inputs']['partials/nav.html']);self.save()
        with self.assertRaisesRegex(ValueError,'complete shared template'):self.qualify()

    def test_stale_configuration_is_rejected(self):
        self.config.write_text(self.config.read_text()+'# changed inputs\n')
        with self.assertRaisesRegex(ValueError,'Configuration differs'):self.qualify()

    def test_missing_served_route_is_refused_before_graph_accounting(self):
        (self.site/'read/index.html').unlink()
        with self.assertRaisesRegex(ValueError,'served HTML route inventory'):self.qualify()

    def test_additional_served_route_is_not_silently_omitted(self):
        (self.site/'other.html').write_bytes(document())
        with self.assertRaisesRegex(ValueError,'served HTML route inventory'):self.qualify()

    def test_changed_served_route_cannot_reuse_retained_inventory(self):
        (self.site/'index.html').write_bytes(document('<p>Changed</p>'))
        with self.assertRaisesRegex(ValueError,'served HTML route inventory'):self.qualify()

    def test_missing_configured_destination_is_refused(self):
        self.config.write_text(self.config.read_text()+'- Missing: missing.md\n');self.refresh()
        with self.assertRaisesRegex(ValueError,'Configured navigation reaches missing'):self.qualify()

    def test_missing_primary_destination_is_refused(self):
        (self.site/'index.html').write_bytes(document(links='<a href="./">Home</a>'));self.refresh()
        with self.assertRaisesRegex(ValueError,'omits configured'):self.qualify()

    def test_broken_primary_link_is_refused(self):
        (self.site/'index.html').write_bytes(document(links='<a href="./">Home</a><a href="missing/">Missing</a>'));self.refresh()
        with self.assertRaisesRegex(ValueError,'Primary navigation reaches missing'):self.qualify()

    def test_404_destination_is_never_a_normal_graph_target(self):
        (self.site/'index.html').write_bytes(document(links='<a href="404.html">404</a>'));self.refresh()
        with self.assertRaisesRegex(ValueError,'missing or404'):self.qualify()

    def test_normal_unlisted_route_is_measured_and_reported(self):
        (self.site/'unlisted.html').write_bytes(document());self.refresh()
        report=self.qualify();self.assertEqual(report['normal_routes'],3)
        self.assertIn('unlisted.html',report['pages'][0]['normal_routes_outside_primary_navigation'])

    def test_external_product_navigation_is_classified_without_fetch(self):
        (self.site/'index.html').write_bytes(document(links='<a href="./">Home</a><a href="read/">Read</a><a href="https://example.org/other/">Other</a>'));self.refresh()
        page=next(p for p in self.qualify()['pages'] if p['path']=='index.html')
        self.assertEqual(page['primary_external_targets'],['https://example.org/other/'])

    def test_encoded_route_escape_is_refused(self):
        for value in ['%2e%2e/private/', '%2f..%2fprivate/', 'read\\other/', 'https://user:secret@example.org/docs/']:
            with self.subTest(value=value),self.assertRaises(ValueError):nav.destination('https://example.org/docs/','https://example.org/docs/',value)

    def test_symlink_route_is_refused(self):
        (self.site/'index.html').unlink();(self.site/'index.html').symlink_to(self.site/'404.html')
        with self.assertRaisesRegex(ValueError,'symlink'):self.qualify()

    def test_symlink_producer_input_is_refused(self):
        path=self.repo/self.inventory['producer_inputs']['partials/nav.html']['path'];path.unlink();path.symlink_to(self.repo/self.inventory['producer_inputs']['partials/header.html']['path'])
        with self.assertRaisesRegex(ValueError,'symlink'):self.qualify()

    def test_input_outside_owned_artifacts_is_refused(self):
        with self.assertRaisesRegex(ValueError,'owning artifacts'):nav.qualify(self.repo,self.repo/'outside',self.config,self.manifest,self.standard,SHA)

    def test_symlink_site_directory_inside_artifacts_is_refused(self):
        alias=self.repo/'artifacts/alias';alias.symlink_to(self.site,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):nav.qualify(self.repo,alias,self.config,self.manifest,self.standard,SHA)

    def test_symlink_directory_cannot_hide_uninventoried_routes(self):
        outside=self.repo/'other';outside.mkdir();(outside/'hidden.html').write_bytes(document())
        (self.site/'hidden').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):self.qualify()

    def test_producer_path_outside_artifacts_is_refused(self):
        path=self.repo/'header.html';path.write_bytes(self.templates['partials/header.html'])
        self.inventory['producer_inputs']['partials/header.html']['path']='header.html';self.save()
        with self.assertRaisesRegex(ValueError,'owning artifacts'):self.qualify()

    def test_explicit_historical_generation_scope_is_required(self):
        del self.inventory['retained_generation'];self.save()
        with self.assertRaisesRegex(ValueError,'scope must be explicit'):self.qualify()

    def test_duplicate_manifest_keys_are_refused(self):
        self.manifest.write_text('{"schema":1,"schema":1}')
        with self.assertRaisesRegex(ValueError,'Duplicate evidence'):self.qualify()

    def test_duplicate_config_keys_are_refused(self):
        self.config.write_text(self.config.read_text()+'site_url: https://example.org/other/\n');self.refresh()
        with self.assertRaisesRegex(ValueError,'Duplicate configuration'):self.qualify()

    def test_material_function_name_metadata_is_read_without_import(self):
        config=nav.config_data(b'site_url: https://example.org/docs/\nnav: []\nemoji: !!python/name:material.extensions.emoji.twemoji\n')
        self.assertEqual(config['emoji']['configured_function_name'],'material.extensions.emoji.twemoji')

    def test_executable_yaml_object_constructors_are_refused(self):
        with self.assertRaises(nav.yaml.YAMLError):
            nav.config_data(b'site_url: https://example.org/docs/\nnav: []\ncode: !!python/object/apply:os.system [echo unsafe]\n')

    def test_directory_url_false_has_exact_html_destinations(self):
        self.assertEqual(nav.authored_routes({'nav':[{'Home':'index.md'},{'Read':'read.md'}],'use_directory_urls':False}),{'index.html','read.html'})

    def test_ambiguous_navigation_types_are_refused(self):
        for value in [None,True,42]:
            with self.subTest(value=value),self.assertRaises(ValueError):nav.authored_routes({'nav':value})


if __name__ == '__main__': unittest.main()
