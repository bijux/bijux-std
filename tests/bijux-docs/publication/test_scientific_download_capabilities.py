"""Bind the reviewed PDF download hook to source bytes and finite public outputs."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    'bijux_scientific_download_capabilities',
    ROOT / 'shared/bijux-docs/security/producer_capabilities.py',
)
capabilities = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capabilities)
FIXTURE = Path(__file__).parent / 'fixtures/scientific-downloads'


def digest(value):
    return hashlib.sha256(value).hexdigest()


class ScientificDownloads(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT / 'artifacts/qualification/scientific-download-capabilities'
        artifacts.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        for name in ('configs/docs/science_downloads.py', 'reports/exports/papers/verify.py'):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(FIXTURE / name, destination)
        self.write('reports/science/paper-accounts.csv',
                   'paper_id,canonical_report\n' + ''.join(
                       f'paper-{number},reports/science/paper-{number}.md\n' for number in range(9)))
        self.write('reports/exports/papers/visual-review.json', '{}\n')
        self.rows = []
        papers = []
        for number in range(9):
            source = f'reports/science/paper-{number}.md'
            self.write(source, f'# Source {number}\n')
            name = f'reports/exports/papers/paper-{number}.pdf'
            self.write(name, f'%PDF-1.7\nRetained paper {number}\n')
            self.row(name, f'assets/science/papers/paper-{number}.pdf', source)
            papers.append({'canonical_report': source})
        decks = ('big-picture', 'developer', 'scientific-evidence')
        deck_sources = {}
        for name in decks:
            source = f'presentation/{name}.tex'
            self.write(source, f'Reviewed presentation {name}\n')
            deck_sources[source] = digest((self.root/source).read_bytes())
            pdf = f'presentation/{name}.pdf'
            self.write(pdf, f'%PDF-1.7\nRetained deck {name}\n')
            self.row(pdf, f'assets/science/presentations/{name}.pdf', source)
        self.write_json('presentation/source-lock.json', {'decks': list(decks), 'sources': deck_sources})
        self.write('reports/exports/papers/producer.py', '# Reviewed export producer\n')
        self.write_json('reports/exports/papers/manifest.json', {
            'inventory': 'reports/science/paper-accounts.csv', 'papers': papers,
            'producer_sha256': {'reports/exports/papers/producer.py': digest(
                (self.root/'reports/exports/papers/producer.py').read_bytes())},
        })
        inputs = ('reports/science/paper-accounts.csv', 'reports/exports/papers/manifest.json',
                  'reports/exports/papers/visual-review.json', 'presentation/source-lock.json')
        self.manifest = {
            'schema_version': 'scientific-reader-downloads.v1', 'files': self.rows,
            'inputs': {name: digest((self.root/name).read_bytes()) for name in inputs},
        }
        self.write_json('reports/exports/site-downloads.json', self.manifest)
        self.path = self.root/'configs/docs/science_downloads.py'
        spec = importlib.util.spec_from_file_location('bijux_reviewed_scientific_downloads', self.path)
        self.hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.hook)
        self.configuration = types.SimpleNamespace(hooks={'downloads': self.hook})

    def write(self, name, value):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def write_json(self, name, value):
        self.write(name, json.dumps(value, indent=2)+'\n')

    def row(self, name, uri, source):
        content = (self.root/name).read_bytes()
        self.rows.append({'path': name, 'site_uri': uri, 'canonical_source': source,
                          'bytes': len(content), 'sha256': digest(content),
                          'source_sha256': digest((self.root/source).read_bytes())})

    def capture(self):
        return capabilities.hooks(self.configuration, self.root)

    def rejected(self):
        with self.assertRaises((ValueError, capabilities.CapabilityError, FileNotFoundError)):
            self.capture()

    def test_native_reviewed_callback_has_twelve_byte_bound_outputs(self):
        record, = self.capture()
        self.assertEqual(record['recipe'], 'scientific-pdf-downloads')
        self.assertEqual(record['outputs'], {row['site_uri']: row['sha256'] for row in self.rows})
        inputs = {row['path'] for row in record['inputs']}
        self.assertIn('reports/exports/papers/verify.py', inputs)
        self.assertIn('reports/exports/papers/producer.py', inputs)
        self.assertTrue({row['canonical_source'] for row in self.rows} <= inputs)

    def test_changed_pdf_cannot_inherit_retained_receipt(self):
        self.write(self.rows[0]['path'], '%PDF-1.7\nDifferent retained bytes\n')
        self.rejected()

    def test_changed_canonical_source_is_refused(self):
        self.write(self.rows[0]['canonical_source'], '# Different canonical source\n')
        self.rejected()

    def test_missing_retained_pdf_is_refused(self):
        (self.root/self.rows[0]['path']).unlink()
        self.rejected()

    def test_changed_export_verifier_is_refused(self):
        self.write('reports/exports/papers/verify.py', 'raise SystemExit(0)\n')
        self.rejected()

    def test_extra_pdf_population_is_refused(self):
        self.manifest['files'].append(dict(self.rows[0]))
        self.write_json('reports/exports/site-downloads.json', self.manifest)
        self.rejected()

    def test_route_substitution_is_refused(self):
        self.manifest['files'][0]['site_uri'] = 'assets/science/substituted.pdf'
        self.write_json('reports/exports/site-downloads.json', self.manifest)
        self.rejected()

    def test_recipe_never_accepts_an_arbitrary_read_callback(self):
        self.hook._read = lambda *args: b'%PDF-1.7\nforged\n'
        self.rejected()

    def test_reviewed_code_with_foreign_global_namespace_is_refused(self):
        original = self.hook.download_bytes
        self.hook.download_bytes = types.FunctionType(original.__code__, dict(original.__globals__))
        self.rejected()

    def test_changed_hook_constants_are_refused(self):
        self.hook.MANIFEST = 'reports/exports/papers/manifest.json'
        self.rejected()

    def test_changed_dependency_binding_is_refused(self):
        self.hook.runpy = types.SimpleNamespace(run_path=lambda *args, **kwargs: None)
        self.rejected()

    def test_missing_declared_producer_input_is_refused(self):
        (self.root/'reports/exports/papers/producer.py').unlink()
        self.rejected()

    def test_pdf_symlink_cannot_supply_owned_bytes(self):
        pdf = self.root/self.rows[0]['path']
        target = pdf.with_suffix('.retained')
        pdf.rename(target)
        pdf.symlink_to(target)
        self.rejected()

    def test_parent_traversal_in_manifest_cannot_alias_source(self):
        self.manifest['inputs']['reports/../reports/science/paper-accounts.csv'] = digest(
            (self.root/'reports/science/paper-accounts.csv').read_bytes())
        self.write_json('reports/exports/site-downloads.json', self.manifest)
        self.rejected()


class RetainedSourceAdmission(unittest.TestCase):
    """Refuse forged lineage before any historical Git or PDF callback executes."""

    write = ScientificDownloads.write
    write_json = ScientificDownloads.write_json
    row = ScientificDownloads.row
    capture = ScientificDownloads.capture

    def setUp(self):
        ScientificDownloads.setUp(self)
        source = FIXTURE/'retained/configs/docs/science_downloads.py'
        shutil.copyfile(source, self.path)
        spec = importlib.util.spec_from_file_location('bijux_reviewed_retained_downloads', self.path)
        self.hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.hook)
        self.configuration.hooks['downloads'] = self.hook
        self.write_json(capabilities.RETAINED_DECK_CONTEXT_PATH, capabilities.RETAINED_DECK_CONTEXT)

    def test_missing_retained_context_never_falls_back_to_current_source_lock(self):
        (self.root/capabilities.RETAINED_DECK_CONTEXT_PATH).unlink()
        with self.assertRaisesRegex(ValueError, 'source must belong'):
            self.capture()

    def test_unknown_context_fields_cannot_rebind_historical_exports(self):
        context = json.loads((self.root/capabilities.RETAINED_DECK_CONTEXT_PATH).read_bytes())
        context['newly_generated'] = True
        self.write_json(capabilities.RETAINED_DECK_CONTEXT_PATH, context)
        with self.assertRaisesRegex(ValueError, 'differs from reviewed lineage'):
            self.capture()

    def test_other_security_delta_cannot_inherit_reviewed_compatibility(self):
        context = json.loads((self.root/capabilities.RETAINED_DECK_CONTEXT_PATH).read_bytes())
        context['security_metadata']['toml_path'] = ['project', 'dependencies']
        self.write_json(capabilities.RETAINED_DECK_CONTEXT_PATH, context)
        with self.assertRaisesRegex(ValueError, 'differs from reviewed lineage'):
            self.capture()

    def test_mutated_loaded_context_constant_is_refused(self):
        self.hook.RETAINED_CONTEXT['source_revision'] = '0'*40
        with self.assertRaisesRegex(ValueError, 'context or dependency binding changed'):
            self.capture()

    def test_substituted_history_helper_is_refused_before_execution(self):
        self.hook._committed_inputs = lambda *args: {}
        with self.assertRaisesRegex(ValueError, 'loaded callback differs'):
            self.capture()

    def test_retention_dependencies_must_keep_native_bindings(self):
        for name in ('io', 'subprocess', 'tomllib'):
            with self.subTest(dependency=name):
                original = getattr(self.hook, name)
                setattr(self.hook, name, types.SimpleNamespace())
                with self.assertRaisesRegex(ValueError, 'dependency binding changed'):
                    self.capture()
                setattr(self.hook, name, original)


class RetainedBuildSourceAdmission(unittest.TestCase):
    """Actual reviewed hook bytes cannot acquire authority through a forged helper."""

    write = ScientificDownloads.write
    write_json = ScientificDownloads.write_json
    row = ScientificDownloads.row
    capture = ScientificDownloads.capture

    def setUp(self):
        ScientificDownloads.setUp(self)
        shutil.copyfile(FIXTURE/'retained-build/configs/docs/science_downloads.py', self.path)
        spec = importlib.util.spec_from_file_location('bijux_reviewed_retained_build_downloads', self.path)
        self.hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.hook)
        self.configuration.hooks['downloads'] = self.hook

    def test_exact_current_hook_has_a_distinct_source_recipe(self):
        self.assertEqual(capabilities.HOOKS[digest(self.path.read_bytes())],
                         'retained-build-scientific-pdf-downloads')

    def test_loaded_history_helper_cannot_be_replaced(self):
        self.hook._committed_inputs = lambda *args: {}
        with self.assertRaisesRegex(ValueError, 'loaded callback differs'):
            self.capture()

    def test_callback_cannot_keep_code_with_foreign_globals(self):
        original = self.hook.retained_deck_sources
        self.hook.retained_deck_sources = types.FunctionType(original.__code__, dict(original.__globals__))
        with self.assertRaisesRegex(ValueError, 'loaded callback differs'):
            self.capture()

    def test_missing_build_context_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'source must belong'):
            self.capture()

    def test_build_source_constant_cannot_be_substituted(self):
        self.hook.CURRENT_DECK_SOURCE_LOCK_SHA256 = '0'*64
        with self.assertRaisesRegex(ValueError, 'constants or native dependency'):
            self.capture()


if __name__ == '__main__':
    unittest.main(verbosity=2)
