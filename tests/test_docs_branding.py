"""Prove exact logo retirement and transaction-wide configuration preflight."""
from pathlib import Path
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / 'shared/bijux-docs'
sys.path.insert(0, str(SHARED / 'tooling'))
from configuration.branding import project_theme_logo

SOURCE = Path('mkdocs.yml')
BASELINE = json.loads((SHARED / 'config/mkdocs-baseline.json').read_text())
OLD = 'assets/bijux_logo_hq.png'
NEW = 'assets/bijux_logo.png'


class BrandingTests(unittest.TestCase):
    def apply(self, text, baseline=BASELINE):
        return project_theme_logo(text, baseline, SOURCE)

    def test_literal_migration_preserves_each_quote_comments_and_newlines(self):
        for quote in ['', "'", '"']:
            for newline in ['\n', '\r\n', '\r']:
                with self.subTest(quote=quote, newline=repr(newline)):
                    before = newline.join(['# brand', 'theme: # options', '    name: material', f'    logo :  {quote}{OLD}{quote}   # license', '    icon:', '      logo: material/book', '    palette: !ENV PALETTE']) + newline
                    self.assertEqual(self.apply(before), before.replace(OLD, NEW))
                    self.assertEqual(self.apply(self.apply(before)), self.apply(before))

    def test_missing_final_newline_is_preserved(self):
        before = 'theme:\n  logo: ' + OLD
        self.assertEqual(self.apply(before), 'theme:\n  logo: ' + NEW)

    def test_only_exact_decoded_literal_is_retired(self):
        before = 'theme:\n  logo: "assets/bijux_logo_hq\\u002epng" # encoded literal\n'
        self.assertEqual(self.apply(before), 'theme:\n  logo: "' + NEW + '" # encoded literal\n')

    def test_custom_paths_icons_options_and_unrelated_text_remain_exact(self):
        for value in ['assets/custom.svg', NEW, OLD + '?cache=1', './' + OLD, 'https://example.org/' + OLD, OLD + '.bak']:
            before = f'theme:\n  name: material\n  logo: "{value}" # authored\n  icon:\n    logo: material/library\n    repo: material/git\n  custom_dir: docs/overrides\n# {OLD}\nextra:\n  author_logo: {OLD}\n'
            with self.subTest(value=value):
                self.assertEqual(self.apply(before), before)

    def test_dynamic_and_multiline_custom_logos_remain_authored(self):
        for value in ['null', '~ # icon branding', '!ENV [BRAND_LOGO, assets/custom.svg]', '*authored_logo', '&brand assets/custom.svg', '|\n    authored.svg', '{path: assets/custom.svg}', '[assets/custom.svg]']:
            text = 'theme:\n  logo: ' + value + '\n  icon:\n    logo: material/library\n'
            with self.subTest(value=value):
                self.assertEqual(self.apply(text), text)

    def test_absent_theme_logo_and_minimal_inherit_remain_absent(self):
        for text in ['INHERIT: mkdocs.shared.yml\n', 'theme:\n  name: material\n  icon:\n    logo: material/library\n', 'theme: # empty\n', '# theme:\n# logo: ' + OLD + '\n']:
            self.assertEqual(self.apply(text), text)

    def test_duplicate_theme_or_logo_quoted_keys_and_merge_fail_closed(self):
        for text in ['theme:\n  logo: ' + OLD + '\ntheme:\n  logo: assets/custom.svg\n', 'theme:\n  logo: ' + OLD + '\n  logo: assets/custom.svg\n', '"theme":\n  logo: ' + OLD + '\n', 'theme:\n  "logo": ' + OLD + '\n', 'theme:\n  <<: *options\n  logo: ' + OLD + '\n', '<<: *options\ntheme:\n  logo: ' + OLD + '\n']:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                self.apply(text)

    def test_ambiguous_theme_shapes_and_literal_children_require_review(self):
        for text in ['theme: {logo: ' + OLD + '}\n', 'theme: *theme\n', 'theme:\n  logo:' + OLD + '\n', 'theme:\n  - logo: ' + OLD + '\n', 'theme:\n\tlogo: ' + OLD + '\n', 'theme:\n  logo: ' + OLD + '\n    nested: value\n']:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                self.apply(text)

    def test_invalid_retirement_policies_fail_before_projection(self):
        for retired in [[OLD, OLD], [NEW], ['assets/*.png'], ['assets/../logo.png'], [None], OLD]:
            with self.subTest(retired=retired), self.assertRaises(RuntimeError):
                self.apply('INHERIT: mkdocs.shared.yml\n', {**BASELINE, 'retired_theme_logos': retired})

    def test_nested_icon_logo_is_never_migrated(self):
        before = 'theme:\n  icon:\n    logo: ' + OLD + '\n'
        self.assertEqual(self.apply(before), before)


class BrandingPreflightTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'artifacts/branding-contract'
        parent.mkdir(parents=True, exist_ok=True)
        self.repo = Path(tempfile.mkdtemp(prefix='branding-', dir=parent))
        self.addCleanup(shutil.rmtree, self.repo)
        self.identity = 'extra:\n  bijux:\n    repository: fixture\n    theme_key: bijux:theme\n'
        self.root = self.repo / 'mkdocs.yml'
        self.common = self.repo / 'mkdocs.shared.yml'
        self.root.write_text('INHERIT: mkdocs.shared.yml\n' + self.identity)
        self.common.write_text('theme:\n  logo: ' + OLD + '\n' + self.identity)

    def run_sync(self, *args):
        return subprocess.run([sys.executable, str(SHARED / 'tooling/scripts/sync_mkdocs_hub.py'), str(self.repo), str(SHARED), *args], capture_output=True, text=True)

    def test_real_pipeline_migrates_shared_and_preserves_absent_root_branding(self):
        self.assertEqual(self.run_sync().returncode, 0)
        self.assertIn('  logo: ' + NEW, self.common.read_text())
        self.assertNotIn('theme:', self.root.read_text())
        after = {path: path.read_bytes() for path in [self.root, self.common]}
        self.assertEqual(self.run_sync('--check').returncode, 0)
        self.assertEqual(self.run_sync().returncode, 0)
        self.assertEqual(after, {path: path.read_bytes() for path in after})

    def test_authored_root_logo_override_is_migrated_with_identity_present(self):
        self.root.write_text('INHERIT: mkdocs.shared.yml\n' + self.identity + 'theme:\n  logo: "' + OLD + '" # root brand\n')
        self.assertEqual(self.run_sync().returncode, 0)
        self.assertIn('  logo: "' + NEW + '" # root brand\n', self.root.read_text())

    def test_custom_shared_and_root_branding_is_preserved(self):
        for path in [self.root, self.common]:
            path.write_text(path.read_text() + 'theme:\n  logo: assets/custom.svg\n' if path == self.root else self.identity + 'theme:\n  logo: assets/custom.svg\n')
        self.assertEqual(self.run_sync().returncode, 0)
        for path in [self.root, self.common]:
            self.assertIn('  logo: assets/custom.svg\n', path.read_text())

    def test_late_duplicate_root_leaves_all_configurations_unchanged(self):
        self.root.write_text(self.root.read_text() + 'theme:\n  logo: ' + OLD + '\n  logo: assets/custom.svg\n')
        before = {path: path.read_bytes() for path in [self.root, self.common]}
        result = self.run_sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('duplicate logo', result.stderr)
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_check_only_detects_retirement_without_writes(self):
        before = {path: path.read_bytes() for path in [self.root, self.common]}
        result = self.run_sync('--check')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_minimal_root_identity_limitation_is_retained(self):
        self.root.write_text('INHERIT: mkdocs.shared.yml\n')
        before = {path: path.read_bytes() for path in [self.root, self.common]}
        result = self.run_sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing top-level extra mapping', result.stderr)
        self.assertEqual(before, {path: path.read_bytes() for path in before})


if __name__ == '__main__':
    unittest.main()
