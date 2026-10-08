"""Exact-distribution admission and reproduction for the owned Material index boundary."""
from __future__ import annotations
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
OWNED = ROOT / 'shared/bijux-docs/tooling/material'
spec = importlib.util.spec_from_file_location('material_runtime', OWNED / 'build_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class MaterialRuntimeTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'artifacts/bijux-docs/material-admission-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        distribution = importlib.metadata.distribution('mkdocs-material')
        self.version = distribution.version
        self.templates = Path(distribution.locate_file('material/templates'))

    def copied_templates(self):
        target = self.root / 'templates'
        admitted = json.loads((OWNED / 'admission.json').read_text())
        for relative in ['base.html', admitted['bundle'], admitted['bundle'] + '.map', admitted['worker']]:
            dest = target / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.templates / relative, dest)
        return target

    def test_exact_admission_reproduces_identical_asset_and_truthful_provenance(self):
        first = runtime.compile_runtime(self.templates, self.version)
        self.assertEqual(first, runtime.compile_runtime(self.templates, self.version))
        asset, output, record, template = first
        self.assertEqual(hashlib.sha256(output).hexdigest(), record['output_sha256'])
        self.assertIn(record['output_sha256'], asset)
        self.assertEqual(record['boundary']['occurrences'], 1)
        self.assertIn(b'window.bijuxSearchIndex.observe(ks,Z)', output)
        self.assertIn(b'window.bijuxSearchWorker.channel(e,T)', output)
        self.assertEqual(record['worker_boundary']['occurrences'], 1)
        self.assertEqual(record['upstream_worker_sha256'], hashlib.sha256((self.templates / record['upstream_worker']).read_bytes()).hexdigest())
        self.assertNotIn(b'//# sourceMappingURL=', output)
        self.assertIn(b'Permission is hereby granted', output)
        self.assertIn(asset.encode(), template)
        self.assertIn(b'config.extra_javascript', template)

    def test_character_only_global_subscription_is_removed_without_changing_focused_keyboard(self):
        admitted = json.loads((OWNED / 'admission.json').read_text())
        upstream = (self.templates / admitted['bundle']).read_text()
        asset, output, record, _ = runtime.compile_runtime(self.templates, self.version)
        policy = record['global_character_shortcuts']
        self.assertEqual(policy['disabled_keys'], ['/', 'f', 's'])
        self.assertEqual(policy['occurrences'], 1)
        self.assertEqual(policy['replacement'], ';')
        self.assertEqual(upstream.count(policy['original']), 1)
        self.assertNotIn(policy['original'].encode(), output)
        # The entire adjacent native search keyboard subscription stays byte-identical.
        start = upstream.rfind('r.pipe(', 0, upstream.index(policy['original']))
        focused = upstream[start:upstream.index(policy['original'])]
        self.assertIn('ArrowUp', focused)
        self.assertIn('ArrowDown', focused)
        self.assertIn('Escape', focused)
        self.assertIn(focused.encode(), output)
        self.assertIn(record['output_sha256'], asset)

    def test_character_shortcut_boundary_rejects_missing_or_duplicate_reviewed_source(self):
        templates = self.copied_templates()
        owned = self.root / 'character-shortcut-owned'
        shutil.copytree(OWNED, owned)
        admitted = json.loads((owned / 'admission.json').read_text())
        bundle = templates / admitted['bundle']
        original = bundle.read_text()
        needle = runtime.GLOBAL_CHARACTER_SHORTCUTS
        self.assertEqual(original.count(needle), 1)
        for changed in (original.replace(needle, ''), original + needle):
            with self.subTest(occurrences=changed.count(needle)):
                bundle.write_text(changed)
                current = dict(admitted, bundle_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest())
                (owned / 'admission.json').write_text(json.dumps(current))
                with mock.patch.object(runtime, 'OWNED', owned), self.assertRaisesRegex(ValueError, 'character-only search shortcut boundary must occur exactly once'):
                    runtime.generate(self.root / 'shared', templates, self.version)
                self.assertFalse((self.root / 'shared').exists())

    def test_complete_generated_script_is_parsed_by_the_actual_admitted_node(self):
        _, output, record, _ = runtime.compile_runtime(self.templates, self.version)
        runtime.validate_generated_javascript(output)
        self.assertEqual(record['syntax_validation']['parser'], 'Node.js vm.Script')
        self.assertEqual(record['syntax_validation']['required_version'], 'v24.21.0')

    def test_malformed_final_adapter_rejects_before_changing_existing_output(self):
        shared = self.root / 'shared'
        runtime.generate(shared, self.templates, self.version)
        before = {str(path.relative_to(shared)): path.read_bytes() for path in shared.rglob('*') if path.is_file()}
        owned = self.root / 'malformed-final-owned'
        shutil.copytree(OWNED, owned)
        adapter = owned / 'search-worker-adapter.js'
        adapter.write_bytes(adapter.read_bytes() + b'\n(() => {')
        with mock.patch.object(runtime, 'OWNED', owned), self.assertRaisesRegex(ValueError, 'rejected by admitted JavaScript parser'):
            runtime.generate(shared, self.templates, self.version)
        self.assertEqual(before, {str(path.relative_to(shared)): path.read_bytes() for path in shared.rglob('*') if path.is_file()})

    def test_malformed_final_native_separator_cannot_replace_a_valid_existing_bundle(self):
        shared = self.root / 'shared'
        runtime.generate(shared, self.templates, self.version)
        before = {str(path.relative_to(shared)): path.read_bytes() for path in shared.rglob('*') if path.is_file()}
        malformed = lambda source: source.replace(runtime.GLOBAL_CHARACTER_SHORTCUTS, '')
        with mock.patch.object(runtime, 'without_global_character_shortcuts', side_effect=malformed), self.assertRaisesRegex(ValueError, 'rejected by admitted JavaScript parser'):
            runtime.generate(shared, self.templates, self.version)
        self.assertEqual(before, {str(path.relative_to(shared)): path.read_bytes() for path in shared.rglob('*') if path.is_file()})

    def test_exact_check_does_not_require_an_output_emission_parser(self):
        shared = self.root / 'shared'
        runtime.generate(shared, self.templates, self.version)
        with mock.patch.object(runtime.subprocess, 'run', side_effect=AssertionError('check must compare exact prequalified output')):
            runtime.generate(shared, self.templates, self.version, check=True)

    def test_head_extension_changes_template_only_and_remains_optional_consumer_content(self):
        asset, output, record, template = runtime.compile_runtime(self.templates, self.version)
        self.assertEqual(record["template_extension"], {
            "block": "extrahead", "include": "partials/site-head.html", "owner": "consumer",
            "optional": True, "managed_default": False,
        })
        self.assertEqual(template.count(b'{% include "partials/site-head.html" ignore missing %}'), 1)
        self.assertIn(b'{{ super() }}', template)
        self.assertFalse((OWNED.parents[1] / "partials/site-head.html").exists())
        self.assertEqual(template.count(b'{% block scripts %}'), 1)
        self.assertEqual(template.count(asset.encode()), 1)

    def test_unsupported_version_rejects_before_output(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported Material version'):
            runtime.generate(self.root / 'shared', self.templates, '9.7.8')
        self.assertFalse((self.root / 'shared').exists())

    def test_altered_native_bundle_base_or_map_rejects_before_output(self):
        admitted = json.loads((OWNED / 'admission.json').read_text())
        templates = self.copied_templates()
        for relative in [admitted['bundle'], 'base.html', admitted['bundle'] + '.map']:
            path = templates / relative
            original = path.read_bytes()
            path.write_bytes(original + b'\nchanged')
            with self.assertRaisesRegex(ValueError, 'differs from admitted bytes'):
                runtime.generate(self.root / 'shared', templates, self.version)
            self.assertFalse((self.root / 'shared').exists())
            path.write_bytes(original)

    def test_ambiguous_boundary_rejects_even_when_distribution_hash_is_explicitly_admitted(self):
        templates = self.copied_templates()
        owned = self.root / 'owned'
        shutil.copytree(OWNED, owned)
        original_admission = json.loads((owned / 'admission.json').read_text())
        bundle = templates / original_admission['bundle']
        original = bundle.read_text()
        for changed in [original.replace(original_admission['needle'], ''), original + original_admission['needle']]:
            bundle.write_text(changed)
            admission = dict(original_admission)
            admission['bundle_sha256'] = hashlib.sha256(bundle.read_bytes()).hexdigest()
            (owned / 'admission.json').write_text(json.dumps(admission))
            with mock.patch.object(runtime, 'OWNED', owned):
                with self.assertRaisesRegex(ValueError, 'exactly once'):
                    runtime.generate(self.root / 'shared', templates, self.version)
            self.assertFalse((self.root / 'shared').exists())

    def test_changed_native_worker_rejects_before_output(self):
        templates = self.copied_templates()
        admitted = json.loads((OWNED / 'admission.json').read_text())
        worker = templates / admitted['worker']
        worker.write_bytes(worker.read_bytes() + b'\nchanged worker')
        with self.assertRaisesRegex(ValueError, 'worker differs from admitted bytes'):
            runtime.generate(self.root / 'shared', templates, self.version)
        self.assertFalse((self.root / 'shared').exists())

    def test_missing_or_ambiguous_worker_boundary_rejects_even_with_reviewed_bundle_hash(self):
        templates = self.copied_templates()
        owned = self.root / 'worker-owned'
        shutil.copytree(OWNED, owned)
        original_admission = json.loads((owned / 'admission.json').read_text())
        bundle = templates / original_admission['bundle']
        original = bundle.read_text()
        for changed in [original.replace(original_admission['worker_boundary'], ''), original + original_admission['worker_boundary']]:
            bundle.write_text(changed)
            admission = dict(original_admission)
            admission['bundle_sha256'] = hashlib.sha256(bundle.read_bytes()).hexdigest()
            (owned / 'admission.json').write_text(json.dumps(admission))
            with mock.patch.object(runtime, 'OWNED', owned):
                with self.assertRaisesRegex(ValueError, 'Search-worker boundary must occur exactly once'):
                    runtime.generate(self.root / 'shared', templates, self.version)
            self.assertFalse((self.root / 'shared').exists())

    def assert_owned_context_rejected(self, needle, declaration, message):
        templates = self.copied_templates()
        owned = self.root / 'owned-context'
        shutil.copytree(OWNED, owned)
        admitted = json.loads((owned / 'admission.json').read_text())
        bundle = templates / admitted['bundle']
        original = bundle.read_text()
        self.assertEqual(original.count(needle), 1)
        for changed in (original.replace(needle, ''), original + needle, original + declaration):
            with self.subTest(owned_context=needle, declaration=declaration):
                bundle.write_text(changed)
                current = dict(admitted, bundle_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest())
                (owned / 'admission.json').write_text(json.dumps(current))
                with mock.patch.object(runtime, 'OWNED', owned), self.assertRaisesRegex(ValueError, message):
                    runtime.generate(self.root / 'shared', templates, self.version)
                self.assertFalse((self.root / 'shared').exists())

    def test_search_result_context_rejects_missing_duplicate_or_predeclared_owned_helper(self):
        self.assert_owned_context_rejected(
            'href:`${s}`,class:"md-search-result__link",tabIndex:-1',
            '__bijuxSearchCapabilityTarget', 'Native search renderer boundary')

    def test_native_iife_rejects_missing_or_duplicate_owned_lexical_scope(self):
        self.assert_owned_context_rejected(
            '"use strict";(()=>{', '__bijuxSearchCapabilityTarget', 'Native search renderer boundary')

    def test_native_resize_context_rejects_missing_duplicate_or_predeclared_owned_helper(self):
        self.assert_owned_context_rejected(
            'new ResizeObserver(e=>e.forEach(t=>cn.next(t)))',
            '__bijuxElementResizeObserver', 'Native resize delivery')

    def test_altered_upstream_license_rejects_before_output(self):
        owned = self.root / 'owned'
        shutil.copytree(OWNED, owned)
        (owned / 'UPSTREAM-LICENSE.txt').write_text('missing license')
        with mock.patch.object(runtime, 'OWNED', owned):
            with self.assertRaisesRegex(ValueError, 'license differs'):
                runtime.generate(self.root / 'shared', self.templates, self.version)
        self.assertFalse((self.root / 'shared').exists())

    def test_check_rejects_altered_generated_asset_or_template(self):
        shared = self.root / 'shared'
        record = runtime.generate(shared, self.templates, self.version)
        runtime.generate(shared, self.templates, self.version, check=True)
        for relative in [record['output_asset'], 'partials/main.html']:
            path = shared / relative
            original = path.read_bytes()
            path.write_bytes(original + b'\nchanged')
            with self.assertRaisesRegex(ValueError, 'output differs'):
                runtime.generate(shared, self.templates, self.version, check=True)
            path.write_bytes(original)

    def test_unknown_previous_runtime_is_preserved_and_rejected(self):
        shared = self.root / 'shared'
        existing = shared / 'assets/javascripts/material-search.unreviewed.js'
        existing.parent.mkdir(parents=True)
        existing.write_text('preserve user edits')
        with self.assertRaisesRegex(ValueError, 'Preserve previous'):
            runtime.generate(shared, self.templates, self.version)
        self.assertEqual(existing.read_text(), 'preserve user edits')
        self.assertFalse((shared / 'partials/main.html').exists())


if __name__ == '__main__':
    unittest.main()
