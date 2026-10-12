"""Actual retained native bytes and finite admission adversarial controls."""
from pathlib import Path
import copy
import gzip
import importlib
import importlib.util
import json
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / 'shared/bijux-docs'
FIXTURE = ROOT / 'tests/bijux-docs/publication/fixtures/native-presentations'
spec = importlib.util.spec_from_file_location('bijux_native_policy_test', SHARED / 'security/csp.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
package = policy.embedded_module().__package__
native = importlib.import_module(package + '.native_presentations')
html = importlib.import_module(package + '.html')
rendering = importlib.import_module(package + '.interactive_rendering')


class NativePresentations(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT / 'artifacts/native-presentation-controls'
        artifacts.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'remote', 'add', 'origin',
                        'https://github.com/bijux/bijux-pollenomics.git'], check=True)
        for record in json.loads((FIXTURE / 'source-inputs.json').read_text()):
            target = self.root / record['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(gzip.decompress((FIXTURE / record['fixture']).read_bytes()))
        self.nordic, self.sequence = json.loads((FIXTURE / 'reviewed-reports.json').read_text())

    def content(self, report):
        return (self.root / report['source']['path']).read_bytes()

    def test_original_nordic_document_controller_and_resource_closure_pass(self):
        content = self.content(self.nordic)
        self.assertEqual(len(content), 526299)
        native.document_budget(self.root, self.nordic, content, native.SITE)
        document = html.validate_report(content.decode(), self.nordic, native.SITE)
        result = html.report_recipe(self.root, document, self.nordic, native.SITE, self.nordic['output'])
        self.assertGreater(result['slot_count'], 0)
        native.bootstrap(document, self.nordic)

    def test_nearby_oversized_sources_do_not_borrow_the_nordic_cap(self):
        content = self.content(self.nordic)
        for operation in ('bytes', 'path', 'hash', 'output', 'site', 'recipe', 'resources', 'bootstrap', 'script'):
            with self.subTest(operation=operation):
                report = copy.deepcopy(self.nordic); actual = content; site = native.SITE
                if operation == 'bytes': actual = content + b' '
                elif operation == 'path': report['source']['path'] = 'docs/report/other.html'
                elif operation == 'hash': report['source']['sha256'] = 'a' * 64
                elif operation == 'output': report['output'] = 'report/other.html'
                elif operation == 'site': site = 'https://bijux.io/bijux-core/'
                elif operation == 'recipe': report['recipe']['slots']['__TIME_MAX_BP__']['maximum'] += 1
                elif operation == 'resources': next(iter(report['resources'].values()))['bytes'] += 1
                elif operation == 'bootstrap': report['bootstrap_sha256'] = 'a' * 64
                elif operation == 'script': report['reviewed_scripts'] = ['a' * 64]
                with self.assertRaises(ValueError): native.document_budget(self.root, report, actual, site)

    def test_unknown_documents_retain_the_default_size_budget(self):
        report = {'source': {'path': 'docs/report/other.html', 'sha256': 'a' * 64}}
        native.document_budget(self.root, report, b'x' * 524288, native.SITE)
        with self.assertRaisesRegex(ValueError, 'document budget'):
            native.document_budget(self.root, report, b'x' * 524289, native.SITE)

    def test_changed_native_producer_cannot_reuse_original_nordic_output(self):
        for path in native.NORDIC_PRODUCERS:
            with self.subTest(path=path):
                target = self.root / path; original = target.read_bytes()
                target.write_bytes(original + b'\n')
                with self.assertRaisesRegex(ValueError, 'producer differs'):
                    native.document_budget(self.root, self.nordic, self.content(self.nordic), native.SITE)
                target.write_bytes(original)

    def test_another_repository_cannot_borrow_native_presentations(self):
        subprocess.run(['git', '-C', str(self.root), 'remote', 'set-url', 'origin',
                        'https://github.com/bijux/bijux-core.git'], check=True)
        for report in (self.nordic, self.sequence):
            with self.subTest(report=report['output']), self.assertRaisesRegex(ValueError, 'Pollenomics repository'):
                native.document_budget(self.root, report, self.content(report), native.SITE)

    def test_canonical_checkout_origin_spellings_admit_original_presentations(self):
        for origin in ('https://github.com/bijux/bijux-pollenomics',
                       'https://github.com/bijux/bijux-pollenomics.git',
                       'git@github.com:bijux/bijux-pollenomics.git'):
            subprocess.run(['git', '-C', str(self.root), 'remote', 'set-url',
                            'origin', origin], check=True)
            for report in (self.nordic, self.sequence):
                with self.subTest(origin=origin, report=report['output']):
                    native.document_budget(self.root, report, self.content(report), native.SITE)

    def test_nearby_origins_cannot_borrow_original_presentations(self):
        for origin in ('https://github.com/bijux/bijux-core',
                       'https://github.com/another/bijux-pollenomics',
                       'http://github.com/bijux/bijux-pollenomics',
                       'https://github.com:443/bijux/bijux-pollenomics',
                       'https://github.com/bijux/bijux-pollenomics?ref=main',
                       'https://github.com/bijux/bijux-pollenomics.git#main',
                       'https://user@github.com/bijux/bijux-pollenomics',
                       'https://github.com/bijux/../bijux-pollenomics',
                       'https://github.com/bijux/%62ijux-pollenomics',
                       'https://github.com/bijux/bijux-pollenomics/',
                       'git@github.com:another/bijux-pollenomics.git',
                       'git@github.com:bijux/bijux-core.git'):
            subprocess.run(['git', '-C', str(self.root), 'remote', 'set-url',
                            'origin', origin], check=True)
            for report in (self.nordic, self.sequence):
                with self.subTest(origin=origin, report=report['output']), \
                     self.assertRaisesRegex(ValueError, 'Pollenomics repository'):
                    native.document_budget(self.root, report, self.content(report), native.SITE)

    def test_original_swedish_chart_has_an_exact_bootstrap_free_recipe(self):
        document = html.validate_report(self.content(self.sequence).decode(), self.sequence, native.SITE)
        native.document_budget(self.root, self.sequence, self.content(self.sequence), native.SITE)
        native.bootstrap(document, self.sequence)
        recipe = html.report_recipe(self.root, document, self.sequence, native.SITE, self.sequence['output'])
        self.assertEqual(recipe['slot_count'], 0)
        descriptor = {'config': {'path': 'mkdocs.yml', 'sha256': 'a' * 64},
                      'reader_purpose': {'path': 'readers.json', 'sha256': 'a' * 64},
                      'producer_inputs': [], 'reports': [self.sequence], 'parents': []}
        rendering._shape(descriptor)
        for output, resource in self.sequence['resources'].items():
            native.sequence_data(self.root, self.sequence, output, resource,
                                 (self.root / resource['source']).read_bytes(), native.SITE)

    def test_chart_data_changes_and_unowned_json_are_refused(self):
        for output, resource in self.sequence['resources'].items():
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'reviewed bytes'):
                native.sequence_data(self.root, self.sequence, output, resource,
                                     (self.root / resource['source']).read_bytes() + b' ', native.SITE)
        changed = copy.deepcopy(self.sequence)
        changed['resources']['report/extra.json'] = {'kind': 'native-sequence-data', 'source': 'docs/extra.json',
                                                   'sha256': 'a' * 64, 'bytes': 2}
        with self.assertRaisesRegex(ValueError, 'data closure'): native.sequence_recipe(changed)

    def test_chart_source_script_bootstrap_provider_and_recipe_changes_refuse(self):
        for field, value in (('source', {'path': native.SEQUENCE_SOURCE, 'sha256': 'a' * 64}),
                             ('reviewed_scripts', ['a' * 64]), ('bootstrap_id', 'new-bootstrap'),
                             ('providers', {'https://unknown.example': {}}),
                             ('recipe', {'template': native.SEQUENCE_SOURCE, 'expansions': [], 'slots': {'__X__': {'kind': 'json'}}})):
            with self.subTest(field=field), self.assertRaises(ValueError):
                report = copy.deepcopy(self.sequence); report[field] = value
                native.sequence_recipe(report)
        with self.assertRaisesRegex(ValueError, 'document differs'):
            native.document_budget(self.root, self.sequence, self.content(self.sequence) + b' ', native.SITE)

    def test_generic_interactive_reports_still_require_bootstrap_and_slots(self):
        report = copy.deepcopy(self.sequence)
        report['source']['path'] = 'docs/report/ordinary.html'
        with self.assertRaisesRegex(ValueError, 'bootstrap differs'):
            native.bootstrap(html.Document('<html><script>window.ordinary=true;</script></html>'), report)
        descriptor = {'config': {'path': 'mkdocs.yml', 'sha256': 'a' * 64},
                      'reader_purpose': {'path': 'readers.json', 'sha256': 'a' * 64},
                      'producer_inputs': [], 'reports': [report], 'parents': []}
        with self.assertRaises(ValueError): rendering._shape(descriptor)


if __name__ == '__main__': unittest.main()
