"""Exercise product-source admission and generated website-output rejection."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'bijux_source_layout', ROOT / 'shared/bijux-docs/tooling/quality/validate_source_layout.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


class SourceLayoutTests(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT / 'artifacts/source-layout'
        artifacts.mkdir(parents=True, exist_ok=True)
        sandbox = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(sandbox.cleanup)
        self.root = Path(sandbox.name)

    def write(self, relative):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('owned source')
        return path

    def test_scientific_assets_remain_intact(self):
        source = self.write('assets/reference/primers/16S.fasta')
        self.write('assets/golden/smoke-inputs/reads.fastq')
        self.write('assets/CONTRACT.md')
        layout.validate(self.root)
        self.assertEqual(source.read_text(), 'owned source')

    def test_authored_frontend_sources_remain_allowed(self):
        self.write('assets/javascripts/navigation.js')
        self.write('assets/stylesheets/product.css')
        layout.validate(self.root)

    def test_material_output_is_rejected_without_root_html(self):
        for relative in ('assets/javascripts/bundle.abc123.min.js',
                         'assets/javascripts/workers/search.abc123.min.js',
                         'assets/stylesheets/main.abc123.min.css',
                         'assets/stylesheets/palette.abc123.min.css'):
            with self.subTest(relative=relative):
                path = self.write(relative)
                with self.assertRaisesRegex(ValueError, 'generated website asset'):
                    layout.validate(self.root)
                path.unlink()

    def test_generated_root_paths_remain_rejected(self):
        for relative in ('index.html', '404.html', 'search/search_index.json',
                         'sitemap.xml', 'overrides/main.html'):
            with self.subTest(relative=relative):
                path = self.write(relative)
                with self.assertRaisesRegex(ValueError, 'generated root path'):
                    layout.validate(self.root)
                path.unlink()
                if '/' in relative:
                    path.parent.rmdir()

    def test_broken_output_symlink_is_rejected(self):
        (self.root / 'index.html').symlink_to(self.root / 'absent.html')
        with self.assertRaisesRegex(ValueError, 'generated root path'):
            layout.validate(self.root)
