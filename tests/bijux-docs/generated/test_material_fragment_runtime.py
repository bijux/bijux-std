"""Admitted native fragment restoration cannot enqueue obsolete navigation."""
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
spec = importlib.util.spec_from_file_location('fragment_runtime', OWNED / 'build_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class MaterialFragmentRuntimeTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'artifacts/bijux-docs/fragment-admission-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        distribution = importlib.metadata.distribution('mkdocs-material')
        self.version = distribution.version
        self.templates = Path(distribution.locate_file('material/templates'))

    def test_exact_native_bundle_retains_handlers_and_binds_fragment_source(self):
        admitted = json.loads((OWNED / 'admission.json').read_text())
        upstream = (self.templates / admitted['bundle']).read_text()
        asset, output, record, _ = runtime.compile_runtime(self.templates, self.version)
        boundary = record['fragment_restoration_boundary']
        self.assertEqual(upstream.count(boundary['original']), 1)
        self.assertNotIn(boundary['original'].encode(), output)
        self.assertIn(boundary['replacement'].encode(), output)
        self.assertEqual(record['fragment_restoration_sha256'], hashlib.sha256((OWNED / 'fragment-restoration.js').read_bytes()).hexdigest())
        # Retain the actual link classifier, fragment scroll condition, and native history protocol.
        for unchanged in ['if(r.target||e.metaKey||e.ctrlKey)return y', 'history.state!==null||!a.hash', 'history.replaceState(c,""),history.pushState(null,"",a)', 'h(window,"popstate").pipe(m(we),le())']:
            self.assertIn(unchanged, upstream)
            self.assertIn(unchanged.encode(), output)
        self.assertIn(record['output_sha256'], asset)
        runtime.validate_generated_javascript(output)

    def test_missing_or_duplicate_fragment_boundary_rejects_before_output(self):
        templates = self.root / 'templates'
        owned = self.root / 'owned'
        shutil.copytree(OWNED, owned)
        admitted = json.loads((owned / 'admission.json').read_text())
        for relative in ['base.html', admitted['bundle'], admitted['bundle'] + '.map', admitted['worker']]:
            target = templates / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.templates / relative, target)
        bundle = templates / admitted['bundle']
        original = bundle.read_text()
        for changed in [original.replace(runtime.FRAGMENT_SCROLL_BOUNDARY, ''), original + runtime.FRAGMENT_SCROLL_BOUNDARY]:
            with self.subTest(occurrences=changed.count(runtime.FRAGMENT_SCROLL_BOUNDARY)):
                bundle.write_text(changed)
                current = dict(admitted, bundle_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest())
                (owned / 'admission.json').write_text(json.dumps(current))
                with mock.patch.object(runtime, 'OWNED', owned), self.assertRaisesRegex(ValueError, 'fragment restoration boundary must occur exactly once'):
                    runtime.generate(self.root / 'output', templates, self.version)
                self.assertFalse((self.root / 'output').exists())

    def test_malformed_fragment_helper_preserves_existing_emitted_bundle(self):
        output = self.root / 'output'
        runtime.generate(output, self.templates, self.version)
        before = {str(path.relative_to(output)): path.read_bytes() for path in output.rglob('*') if path.is_file()}
        owned = self.root / 'malformed-owned'
        shutil.copytree(OWNED, owned)
        helper = owned / 'fragment-restoration.js'
        helper.write_bytes(helper.read_bytes() + b'\n(() => {')
        with mock.patch.object(runtime, 'OWNED', owned), self.assertRaisesRegex(ValueError, 'rejected by admitted JavaScript parser'):
            runtime.generate(output, self.templates, self.version)
        self.assertEqual(before, {str(path.relative_to(output)): path.read_bytes() for path in output.rglob('*') if path.is_file()})


if __name__ == '__main__':
    unittest.main(verbosity=2)
