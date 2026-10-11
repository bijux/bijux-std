"""Qualify the real media callback without admitting arbitrary inline JavaScript."""
from __future__ import annotations

import importlib.metadata
import importlib.util
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('bijux_media_csp', ROOT / 'shared/bijux-docs/security/csp.py')
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)
HTML = '<!doctype html><html><head><meta charset="utf-8"></head><body><img src="image.png"></body></html>'


def media_available():
    try:
        return importlib.metadata.version('mkdocs-glightbox') == policy.GLIGHTBOX_VERSION
    except importlib.metadata.PackageNotFoundError:
        return False


class MediaDependencyBoundary(unittest.TestCase):
    def test_absent_plugin_grants_no_media_capability(self):
        with patch.object(policy.importlib.metadata, 'distribution', side_effect=importlib.metadata.PackageNotFoundError):
            self.assertEqual(policy.media_inputs(), [])

    def test_different_dependency_version_is_refused(self):
        with patch.object(policy.importlib.metadata, 'distribution', return_value=types.SimpleNamespace(version='0.5.3')):
            with self.assertRaisesRegex(policy.PolicyError, 'version'):
                policy.media_inputs()

    def test_unreviewed_inline_code_remains_refused(self):
        with self.assertRaisesRegex(policy.PolicyError, 'Executable inline'):
            policy.qualify_html(HTML.replace('</body>', '<script>alert(1)</script></body>'), {policy.GLIGHTBOX_SCRIPT}, '')

    def test_similar_callback_with_extra_executable_code_is_refused(self):
        script = policy.GLIGHTBOX_SCRIPT + 'fetch("https://example.invalid/");'
        with self.assertRaisesRegex(policy.PolicyError, 'Executable inline'):
            policy.qualify_html(HTML.replace('</body>', f'<script>{script}</script></body>'), {policy.GLIGHTBOX_SCRIPT}, '')


@unittest.skipUnless(media_available(), 'actual Linux media profile is required')
class NativeMediaCallback(unittest.TestCase):
    def setUp(self):
        from mkdocs_glightbox.plugin import LightboxPlugin
        self.plugin = LightboxPlugin()
        errors, warnings = self.plugin.load_config({'touchNavigation': True, 'loop': False, 'effect': 'zoom'})
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.configuration = {'theme': types.SimpleNamespace(name='material'), 'plugins': {}}
        self.plugin.on_config(self.configuration)
        self.page = types.SimpleNamespace(meta={}, url='guide/index.html')
        self.allowed, self.base = policy.admitted_scripts(ROOT / 'shared/bijux-docs', self.material_templates())

    @staticmethod
    def material_templates():
        import material
        return Path(material.__file__).parent / 'templates'

    def output(self):
        return self.plugin.on_post_page(HTML, page=self.page, config=self.configuration)

    def test_actual_native_material_callback_receives_only_its_exact_hash(self):
        output = self.output()
        updated, hashes = policy.qualify_html(output, self.allowed, self.base)
        self.assertEqual(hashes, [policy.hash_source(policy.GLIGHTBOX_SCRIPT)])
        self.assertIn("script-src 'self' " + hashes[0], updated)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", updated)
        self.assertNotIn('https://', updated.split("script-src ", 1)[1].split(';', 1)[0])

    def test_actual_minifier_preserves_the_reviewed_executable_bytes(self):
        from mkdocs_minify_plugin.plugin import MinifyPlugin
        plugin = MinifyPlugin()
        errors, warnings = plugin.load_config({'minify_html': True, 'minify_js': True, 'minify_css': True})
        self.assertEqual(errors, [])
        output = plugin.on_post_page(self.output(), page=self.page, config=self.configuration)
        _, hashes = policy.qualify_html(output, self.allowed, self.base)
        self.assertEqual(hashes, [policy.hash_source(policy.GLIGHTBOX_SCRIPT)])

    def test_changed_native_loop_option_is_refused(self):
        self.plugin.config['loop'] = True
        with self.assertRaisesRegex(policy.PolicyError, 'Executable inline'):
            policy.qualify_html(self.output(), self.allowed, self.base)

    def test_changed_native_effect_is_refused(self):
        self.plugin.config['effect'] = 'fade'
        with self.assertRaisesRegex(policy.PolicyError, 'Executable inline'):
            policy.qualify_html(self.output(), self.allowed, self.base)

    def test_media_dependency_and_assets_are_bound_in_policy_receipt(self):
        record = policy.policy_inputs(ROOT / 'shared/bijux-docs', self.material_templates())['media_callback']
        self.assertEqual(record['version'], '0.5.2')
        self.assertEqual({item['path']: item['sha256'] for item in record['files']}, policy.GLIGHTBOX_INPUTS)

    def test_changed_native_producer_is_refused(self):
        self.corrupted_dependency('mkdocs_glightbox/plugin.py')

    def test_changed_native_browser_asset_is_refused(self):
        self.corrupted_dependency('mkdocs_glightbox/glightbox/glightbox.min.js')

    def test_changed_native_stylesheet_is_refused(self):
        self.corrupted_dependency('mkdocs_glightbox/glightbox/glightbox.min.css')

    def corrupted_dependency(self, changed):
        artifacts = ROOT / 'artifacts/qualification/media-callback'
        artifacts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=artifacts) as directory:
            root = Path(directory)
            installed = importlib.metadata.distribution('mkdocs-glightbox')
            for name in policy.GLIGHTBOX_INPUTS:
                destination = root/name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(installed.locate_file(name), destination)
            (root/changed).write_bytes((root/changed).read_bytes()+b'\n/* changed */\n')
            selected = types.SimpleNamespace(version='0.5.2', locate_file=lambda name: root/name)
            with patch.object(policy.importlib.metadata, 'distribution', return_value=selected):
                with self.assertRaisesRegex(policy.PolicyError, 'differs'):
                    policy.media_inputs()


if __name__ == '__main__':
    unittest.main()
