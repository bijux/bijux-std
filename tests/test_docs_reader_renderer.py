"""Actual committed reader source governs renderer composition, never receipt lists."""
from pathlib import Path
import copy
import importlib
import importlib.util
import json
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bijux_reader_renderer_fixture', ROOT/'tests/test_docs_reader_publication.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


class ReaderRendererTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.ReaderPublicationComposition()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.case = self.fixture.case
        self.adapter = importlib.import_module(self.case.integration.__package__ + '.rendering')
        self.source = self.prepare()
        self.build = self.fixture.build | {'verification_only': True}

    def prepare(self, owner='docs/report/ownership.json', **kw):
        c = self.case
        args = {'config': c.owner['config']['path'], 'config_digest': c.owner['config']['sha256'],
                'resolved_digest': c.owner['resolved_config_sha256'], 'site_url': c.owner['site_url']}
        args.update(kw)
        return self.adapter.ReaderSource(c.repo, owner, **args)

    def test_actual_source_owned_composition_provides_finite_static_scope(self):
        result = self.source.verify(self.case.site, self.fixture.report, self.build)
        self.assertEqual(result.reports, {'report/map.html'})
        self.assertEqual(result.capabilities['report/map.html']['script_sources'], ["'none'"])
        result.unchanged(self.case.site, self.fixture.report)
        self.assertNotIn('producer_authority', vars(result))

    def test_untracked_owner_never_selects_renderer_scope(self):
        (self.case.repo/'artifacts/untracked.json').write_bytes(self.case.descriptor.read_bytes())
        with self.assertRaisesRegex(ValueError, 'untracked or differs'):
            self.prepare(owner='artifacts/untracked.json')

    def test_actual_configuration_and_origin_are_mandatory(self):
        for kw in ({'config_digest':'0'*64}, {'resolved_digest':'0'*64}, {'site_url':'https://other.invalid/'}):
            with self.subTest(kw=kw), self.assertRaisesRegex(ValueError, 'actual selected configuration'):
                self.prepare(**kw)

    def test_interactive_owner_cannot_select_passive_renderer(self):
        c = self.case; c.owner['reports'][0]['report_class'] = 'interactive'
        c.save_owner(); c.git('add','docs/report/ownership.json'); c.git('-c','commit.gpgsign=false','commit','--quiet','-m','fixture: retain different report class')
        with self.assertRaises(ValueError): self.prepare()

    def test_mutated_committed_owner_invalidates_retained_scope(self):
        self.case.descriptor.write_text(self.case.descriptor.read_text()+' ')
        with self.assertRaisesRegex(ValueError, 'owner source changed'):
            self.source.verify(self.case.site, self.fixture.report, self.build)

    def test_receipt_cannot_change_owner_or_committed_source(self):
        for field, value in (('source_sha','0'*40),('descriptor_path',str(self.case.repo/'artifacts/other.json'))):
            csp = copy.deepcopy(self.fixture.report); csp['embedded'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'different committed owner'):
                self.source.verify(self.case.site, csp, self.build)

    def test_retained_index_sitemap_and_report_mutations_are_not_exemptions(self):
        for name in ('search/search_index.json','sitemap.xml','report/map.html'):
            path = self.case.site/name; before = path.read_bytes()
            path.write_bytes(before+b'changed')
            with self.subTest(path=name), self.assertRaises(ValueError):
                self.source.verify(self.case.site, self.fixture.report, self.build)
            path.write_bytes(before)

    def test_post_verification_changes_cannot_reuse_typed_scope(self):
        scope = self.source.verify(self.case.site, self.fixture.report, self.build)
        path = self.case.site/'report/map.html'; path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaises(ValueError): scope.unchanged(self.case.site, self.fixture.report)

    def test_local_scope_cannot_promote_completed_render_to_publication(self):
        with self.assertRaisesRegex(ValueError,'local scope cannot claim'):
            self.source.verify(self.case.site, self.fixture.report, self.fixture.build)

    def test_publication_scope_needs_actual_independent_source_verifier(self):
        with self.assertRaisesRegex(ValueError,'independently reconstructed producer capability'):
            self.source.verify(self.case.site, self.fixture.report, self.fixture.build, publication=True)

    def test_serialized_owner_object_cannot_construct_typed_scope(self):
        with self.assertRaisesRegex(ValueError,'independently prepared in-process source'):
            self.adapter.VerifiedReaders({'reports':['report/map.html']}, self.case.site, self.fixture.report, self.build, {})

    def test_mutated_typed_capability_cannot_replace_rederived_source(self):
        scope = self.source.verify(self.case.site, self.fixture.report, self.build)
        scope.capabilities['report/map.html']['script_sources'] = ["'self'"]
        with self.assertRaisesRegex(ValueError, 'rederived capability changed'):
            scope.unchanged(self.case.site, self.fixture.report)

    def test_publication_profile_refusal_precedes_reader_and_reference_render(self):
        spec = importlib.util.spec_from_file_location('bijux_reader_profile_order', ROOT/'shared/bijux-docs/security/producer_authority.py')
        producer = importlib.util.module_from_spec(spec); spec.loader.exec_module(producer)
        c = self.case
        reference = c.repo/'artifacts/reader-reference'
        before = {p.relative_to(c.site).as_posix(): p.read_bytes() for p in c.site.rglob('*') if p.is_file()}
        with mock.patch.object(producer, 'dependencies', side_effect=producer.ProducerError('controlled profile refusal')) as profiles:
            with self.assertRaisesRegex(ValueError, 'controlled profile refusal'):
                producer.prepare(c.repo, c.owner['config']['path'], ROOT/'shared/bijux-docs', ROOT/'artifacts/unavailable-templates', reference, c.site, publication_scope=True, reader_owner='docs/report/ownership.json')
        profiles.assert_called_once_with(ROOT/'shared/bijux-docs', c.repo, publication=True)
        self.assertFalse(reference.exists())
        self.assertEqual(before, {p.relative_to(c.site).as_posix(): p.read_bytes() for p in c.site.rglob('*') if p.is_file()})


    def test_catalogue_recipe_cannot_substitute_virtual_config_for_passive_owner(self):
        spec = importlib.util.spec_from_file_location('bijux_reader_catalogue_order', ROOT/'shared/bijux-docs/security/producer_authority.py')
        producer = importlib.util.module_from_spec(spec); spec.loader.exec_module(producer)
        c = self.case
        reference = c.repo/'artifacts/catalogue-reader-reference'
        before = {p.relative_to(c.site).as_posix(): p.read_bytes() for p in c.site.rglob('*') if p.is_file()}
        with mock.patch.object(producer, 'dependencies', return_value={}) as profiles, mock.patch.object(producer, 'module', wraps=producer.module) as modules:
            with self.assertRaisesRegex(ValueError, 'passive readers require a tracked MkDocs config'):
                producer.prepare(c.repo, 'artifacts/mkdocs.root.yml', ROOT/'shared/bijux-docs', ROOT/'artifacts/unavailable-templates', reference, c.site,
                                 publication_scope=True, source_recipe='masterclass-catalogue', reader_owner='docs/report/ownership.json')
        profiles.assert_called_once_with(ROOT/'shared/bijux-docs', c.repo, publication=True)
        self.assertEqual([call.args[0].name for call in modules.call_args_list], ['publication.py'])
        self.assertFalse(reference.exists())
        self.assertEqual(before, {p.relative_to(c.site).as_posix(): p.read_bytes() for p in c.site.rglob('*') if p.is_file()})

if __name__ == '__main__': unittest.main()
