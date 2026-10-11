"""Qualify the real media callback without admitting arbitrary inline JavaScript."""
from __future__ import annotations

import copy
import importlib.metadata
import importlib.util
from pathlib import Path
import re
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('bijux_media_csp', ROOT / 'shared/bijux-docs/security/csp.py')
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)
AUTHORITY_SPEC = importlib.util.spec_from_file_location('bijux_media_authority', ROOT / 'shared/bijux-docs/security/script_authority.py')
authority = importlib.util.module_from_spec(AUTHORITY_SPEC)
AUTHORITY_SPEC.loader.exec_module(authority)
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

    def test_media_id_without_actual_producer_is_refused(self):
        parser = authority.InlineAttributes()
        with self.assertRaisesRegex(authority.AuthorityError, 'lack reviewed producer'):
            parser.feed(f'<script id="init-glightbox">{policy.GLIGHTBOX_SCRIPT}</script>')

    def test_reviewed_media_id_cannot_label_an_unrelated_body(self):
        parser = authority.InlineAttributes(policy.GLIGHTBOX_SCRIPT)
        with self.assertRaisesRegex(authority.AuthorityError, 'callback body'):
            parser.feed('<script id="init-glightbox">alert(1)</script>')

    def test_media_attribute_admission_does_not_allow_handlers_or_other_ids(self):
        for attributes in ['id="init-glightbox" onload="alert(1)"', 'id="other"',
                           'id="init-glightbox" type="module"', 'id="init-glightbox" id="init-glightbox"']:
            with self.subTest(attributes=attributes), self.assertRaises(authority.AuthorityError):
                authority.InlineAttributes(policy.GLIGHTBOX_SCRIPT).feed(f'<script {attributes}>{policy.GLIGHTBOX_SCRIPT}</script>')

    def test_ordinary_script_attributes_remain_narrow_with_media_present(self):
        with self.assertRaisesRegex(authority.AuthorityError, 'classic snippets'):
            authority.InlineAttributes(policy.GLIGHTBOX_SCRIPT).feed('<script nonce="forged">var value=1;</script>')


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

    def authority_case(self):
        artifacts = ROOT / 'artifacts/qualification/media-authority'
        artifacts.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(directory.cleanup)
        site = Path(directory.name)
        from mkdocs_minify_plugin.plugin import MinifyPlugin
        minifier = MinifyPlugin()
        errors, warnings = minifier.load_config({'minify_html': True, 'minify_js': True, 'minify_css': True})
        self.assertEqual((errors, warnings), ([], []))
        native = minifier.on_post_page(self.output(), page=self.page, config=self.configuration)
        (site / 'index.html').write_text(native)
        report = policy.apply(site, ROOT / 'shared/bijux-docs', self.material_templates())
        renderer = {'packages': {'mkdocs-material': '9.7.7', 'mkdocs-glightbox': '0.5.2'},
                    'material_templates': copy.deepcopy(report['policy_inputs']['material_templates'])}
        return site, renderer, report

    def test_native_media_and_minifier_pass_independent_source_reconstruction(self):
        site, renderer, report = self.authority_case()
        result = authority.verify_ordinary(site, ROOT / 'shared/bijux-docs', renderer, report)
        self.assertEqual(result['script_hashes'], [policy.hash_source(policy.GLIGHTBOX_SCRIPT)])
        self.assertEqual(result['pages'], [{'path': 'index.html', 'inline_hashes': result['script_hashes']}])

    def test_media_receipt_cannot_replace_actual_native_inputs(self):
        site, renderer, report = self.authority_case()
        for field in ['version', 'files', 'script_sha256', 'distribution']:
            changed = copy.deepcopy(report)
            changed['policy_inputs']['media_callback'][field] = 'forged'
            with self.subTest(field=field), self.assertRaisesRegex(authority.AuthorityError, 'media fingerprint'):
                authority.verify_ordinary(site, ROOT / 'shared/bijux-docs', renderer, changed)

    def test_missing_media_receipt_and_changed_renderer_are_refused(self):
        site, renderer, report = self.authority_case()
        changed = copy.deepcopy(report)
        del changed['policy_inputs']['media_callback']
        with self.assertRaisesRegex(authority.AuthorityError, 'media fingerprint'):
            authority.verify_ordinary(site, ROOT / 'shared/bijux-docs', renderer, changed)
        renderer['packages']['mkdocs-glightbox'] = '0.5.3'
        with self.assertRaisesRegex(authority.AuthorityError, 'media renderer'):
            authority.verify_ordinary(site, ROOT / 'shared/bijux-docs', renderer, report)

    def test_unavailable_native_producer_cannot_borrow_media_receipt(self):
        site, renderer, report = self.authority_case()
        with patch.object(importlib.metadata, 'distribution', side_effect=importlib.metadata.PackageNotFoundError):
            with self.assertRaisesRegex(authority.AuthorityError, 'actual installed producer'):
                authority.verify_ordinary(site, ROOT / 'shared/bijux-docs', renderer, report)

    def test_changed_native_id_and_callback_are_refused_after_csp_application(self):
        site, renderer, report = self.authority_case()
        page = site / 'index.html'
        original = page.read_text()
        mutations = [re.sub(r'id=("?)init-glightbox\1', 'id="other"', original),
                     original.replace('"loop": false', '"loop": true'),
                     re.sub(r'id=("?)init-glightbox\1', 'id="init-glightbox" onclick="alert(1)"', original)]
        for changed in mutations:
            self.assertNotEqual(changed, original)
            page.write_text(changed)
            with self.subTest(changed=changed), self.assertRaises(authority.AuthorityError):
                authority.verify_ordinary(site, ROOT / 'shared/bijux-docs', renderer, report)
        page.write_text(original)

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
