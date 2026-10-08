"""Exercise execution-order projection and all-config validation before writes."""
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
from configuration.ordered_assets import ordered_list, project_required_lists, validate_effective_assets

SPEC = importlib.util.spec_from_file_location('configuration_projection', SHARED / 'tooling/scripts/sync_mkdocs_hub.py')
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)
SOURCE = Path('mkdocs.yml')


class OrderedAssetsTests(unittest.TestCase):
    def merge(self, text, required=('first.js', 'recovery.js', 'bootstrap.js'), **kwargs):
        return ordered_list(text, 'extra_javascript', list(required), SOURCE, create=True, **kwargs)

    def test_missing_dependency_inserted_before_bootstrap_preserves_author_position(self):
        before = '# author header\nextra_javascript: # assets\n  - first.js\n  - author-before.js # custom hook\n  - bootstrap.js\n  - author-after.js\nnav:\n  - Home: index.md\n'
        after = self.merge(before)
        self.assertEqual(after, before.replace('  - bootstrap.js', '  - recovery.js\n  - bootstrap.js'))
        self.assertEqual(self.merge(after), after)

    def test_missing_tail_inserted_after_predecessor_before_author_tail(self):
        before = 'extra_javascript:\n  - first.js\n  - author.js\n'
        self.assertEqual(self.merge(before), 'extra_javascript:\n  - first.js\n  - recovery.js\n  - bootstrap.js\n  - author.js\n')

    def test_unanchored_required_prefix_preserves_author_styles_override_order(self):
        original = 'extra_css:\n  - author.css\n  - further-author.css\n'
        result = ordered_list(original, 'extra_css', ['shared.css'], SOURCE, create=True)
        self.assertEqual(result, original.replace('extra_css:\n', 'extra_css:\n  - shared.css\n'))

    def test_authored_mapping_and_tags_preserved_exactly(self):
        author = '  - path: author.js # authored\n    type: module\n    defer: !ENV [DEFER_MODULE, true]\n'
        text = 'extra_javascript:\n  - first.js\n' + author + '  - bootstrap.js\n'
        self.assertIn(author, self.merge(text))

    def test_single_and_double_quoted_paths_are_preserved(self):
        text = 'extra_javascript:\n  - "first.js" # first\n  - \'bootstrap.js\'\n'
        self.assertEqual(self.merge(text), text.replace("  - 'bootstrap.js'", "  - recovery.js\n  - 'bootstrap.js'"))

    def test_indentless_list_is_supported(self):
        text = 'extra_javascript:\n- first.js\n- bootstrap.js\nnav: []\n'
        self.assertEqual(self.merge(text), text.replace('- bootstrap.js', '- recovery.js\n- bootstrap.js'))

    def test_empty_override_is_populated(self):
        text = 'extra_javascript: [] # override\nnav: []\n'
        result = self.merge(text)
        self.assertIn('extra_javascript:  # override\n  - first.js\n', result)
        self.assertTrue(result.endswith('nav: []\n'))

    def test_absent_root_override_remains_absent(self):
        self.assertEqual(ordered_list('site_name: Product\n', 'extra_javascript', ['first.js'], SOURCE, create=False), 'site_name: Product\n')

    def test_final_line_without_newline_is_not_concatenated(self):
        result = self.merge('extra_javascript:\n  - first.js')
        self.assertIn('  - first.js\n  - recovery.js\n', result)

    def test_canonical_order_drift_requires_explicit_review(self):
        with self.assertRaisesRegex(RuntimeError, 'canonical order conflicts'):
            self.merge('extra_javascript:\n  - bootstrap.js\n  - author.js\n  - first.js\n')

    def test_duplicate_owned_entry_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'duplicate canonical'):
            self.merge('extra_javascript:\n  - first.js\n  - first.js\n')

    def test_owned_async_attribute_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'authored attributes'):
            self.merge('extra_javascript:\n  - path: first.js\n    async: true\n')

    def test_owned_path_only_mapping_is_preserved(self):
        text = 'extra_javascript:\n  - path: first.js # owned\n  - bootstrap.js\n'
        self.assertIn('  - path: first.js # owned\n', self.merge(text))

    def test_retirement_is_exact_and_preserves_comments(self):
        text = 'extra_javascript:\n  - retired.js\n  # author explanation\n  - vendor/mermaid-99.0.0.js\n  - first.js\n'
        after = self.merge(text, retired=('retired.js',))
        self.assertNotIn('  - retired.js\n', after)
        self.assertIn('  # author explanation\n  - vendor/mermaid-99.0.0.js\n', after)

    def test_owned_retired_mapping_attributes_are_not_silently_deleted(self):
        with self.assertRaisesRegex(RuntimeError, 'authored attributes'):
            self.merge('extra_javascript:\n  - path: retired.js\n    defer: true\n', retired=('retired.js',))

    def test_scalar_alias_flow_and_tagged_shapes_fail(self):
        for shape in ['asset.js', '*scripts', '&scripts', '[first.js]', '{path: first.js}', '!ENV SCRIPTS', 'null']:
            with self.subTest(shape=shape), self.assertRaisesRegex(RuntimeError, 'block list'):
                self.merge('extra_javascript: ' + shape + '\n')

    def test_duplicate_and_quoted_fields_fail(self):
        for text in ['extra_javascript: []\nextra_javascript: []\n', '"extra_javascript": []\n']:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                self.merge(text)

    def test_yaml_merge_keys_and_explicit_keys_require_review(self):
        for text in ['<<: *authored\nextra_javascript: []\n', '? extra_javascript\n: []\n', 'extra_javascript:[]\n']:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                self.merge(text)

    def test_malformed_continuation_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'unsupported list item'):
            self.merge('extra_javascript:\n  - author.js\n    unexpectedly: mapping\n')

    def test_inconsistent_empty_list_with_children_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'cannot also contain'):
            self.merge('extra_javascript: []\n  - first.js\n')

    def test_css_and_plugins_preserve_authored_options_and_tags(self):
        plugin = '  - social:\n      enabled: !ENV [ENABLE_SOCIAL_CARDS, false]\n      cache_dir: artifacts/social\n  - redirects:\n      redirect_maps:\n        old.md: index.md\n'
        baseline = {'extra_css': ['shared.css'], 'extra_javascript': ['shared.js'], 'required_plugins': ['search', 'autorefs']}
        original = 'extra_css:\n  - author.css\nplugins:\n' + plugin + 'hooks:\n  - docs/hooks/author.py\n'
        merged = project_required_lists(original, baseline, SOURCE, shared=True)
        self.assertIn(plugin, merged)
        self.assertIn('hooks:\n  - docs/hooks/author.py\n', merged)
        self.assertIn('  - search\n  - autorefs\n', merged)
        self.assertLess(merged.index('  - autorefs\n'), merged.index('  - social:\n'))
        self.assertEqual(project_required_lists(merged, baseline, SOURCE, shared=True), merged)

    def test_existing_search_plugin_options_remain_unchanged(self):
        original = 'plugins:\n  - search:\n      lang: [en, de]\n  - autorefs\n'
        self.assertEqual(ordered_list(original, 'plugins', ['search', 'autorefs'], SOURCE, create=True), original)

    def test_plugin_mapping_overrides_require_explicit_migration(self):
        with self.assertRaisesRegex(RuntimeError, 'block list'):
            ordered_list('plugins: {search: {}}\n', 'plugins', ['search'], SOURCE, create=True)

    def test_asset_validator_accepts_author_modules_rejects_owned_drift(self):
        baseline = {'extra_css': ['shared.css'], 'extra_javascript': ['first.js', 'bootstrap.js'], 'retired_extra_javascript': ['retired.js']}
        good = {'extra_css': ['author.css', 'shared.css'], 'extra_javascript': ['first.js', {'path': 'author.js', 'type': 'module'}, 'bootstrap.js']}
        validate_effective_assets(good, baseline, 'fixture')
        for bad in [['bootstrap.js', 'first.js'], ['first.js', 'first.js', 'bootstrap.js'], ['first.js', 'bootstrap.js', 'retired.js'], [{'path': 'first.js', 'async': True}, 'bootstrap.js']]:
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                validate_effective_assets({**good, 'extra_javascript': bad}, baseline, 'fixture')


class ConfigurationPreflightTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'artifacts/configuration-contract'
        parent.mkdir(parents=True, exist_ok=True)
        self.repo = Path(tempfile.mkdtemp(prefix='config-', dir=parent))
        self.addCleanup(shutil.rmtree, self.repo)
        self.shared = self.repo / '.bijux/shared/bijux-docs'
        (self.shared / 'config').mkdir(parents=True)
        for name in ['mkdocs-baseline.json', 'hub-links.json']:
            shutil.copy2(SHARED / 'config' / name, self.shared / 'config' / name)
        self.text = 'extra:\n  bijux:\n    repository: fixture\n    theme_key: bijux:theme\n'
        (self.repo / 'mkdocs.yml').write_text('INHERIT: mkdocs.shared.yml\n' + self.text)
        (self.repo / 'mkdocs.shared.yml').write_text(self.text)

    def run_sync(self, *args):
        return subprocess.run([sys.executable, str(SHARED / 'tooling/scripts/sync_mkdocs_hub.py'), str(self.repo), str(self.shared), *args], capture_output=True, text=True)

    def test_root_error_preserves_both_files_before_write(self):
        root = self.repo / 'mkdocs.yml'
        for shape in ['extra_javascript: wrong.js\n', 'extra_css: *author\n', 'plugins: {social: {}}\n', 'exclude_docs: [bad]\n']:
            with self.subTest(shape=shape):
                root.write_text('INHERIT: mkdocs.shared.yml\n' + self.text + shape)
                before = {path: path.read_bytes() for path in [root, self.repo / 'mkdocs.shared.yml']}
                result = self.run_sync()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_missing_root_mapping_preserves_shared(self):
        (self.repo / 'mkdocs.yml').write_text('site_name: Missing bijux\n')
        before = (self.repo / 'mkdocs.shared.yml').read_bytes()
        self.assertNotEqual(self.run_sync().returncode, 0)
        self.assertEqual(before, (self.repo / 'mkdocs.shared.yml').read_bytes())

    def test_unsupported_inheritance_leaves_both_configs_unchanged(self):
        root = self.repo / 'mkdocs.yml'
        for inherit in ['other.yml', '!ENV INHERIT_FILE', '*custom']:
            with self.subTest(inherit=inherit):
                root.write_text('INHERIT: ' + inherit + '\n' + self.text)
                before = {path: path.read_bytes() for path in [root, self.repo / 'mkdocs.shared.yml']}
                self.assertNotEqual(self.run_sync().returncode, 0)
                self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_shared_symlink_is_rejected_without_target_write(self):
        target = self.repo / 'author.yml'
        target.write_text(self.text)
        path = self.repo / 'mkdocs.shared.yml'
        path.unlink()
        path.symlink_to(target)
        self.assertNotEqual(self.run_sync().returncode, 0)
        self.assertEqual(target.read_text(), self.text)

    def test_check_is_read_only_and_repeated_sync_is_identical(self):
        before = {name: (self.repo / name).read_bytes() for name in ['mkdocs.yml', 'mkdocs.shared.yml']}
        result = self.run_sync('--check')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('configuration drift', result.stderr)
        self.assertEqual(before, {name: (self.repo / name).read_bytes() for name in before})
        self.assertEqual(self.run_sync().returncode, 0)
        after = {name: (self.repo / name).read_bytes() for name in before}
        self.assertEqual(self.run_sync('--check').returncode, 0)
        self.assertEqual(self.run_sync().returncode, 0)
        self.assertEqual(after, {name: (self.repo / name).read_bytes() for name in before})

    def test_feature_is_admitted_only_when_actual_baseline_requires_it(self):
        self.assertEqual(self.run_sync().returncode, 0)
        path = self.repo / 'mkdocs.shared.yml'
        self.assertNotIn('search-recovery.js', path.read_text())
        policy = self.shared / 'config/mkdocs-baseline.json'
        baseline = json.loads(policy.read_text())
        index = baseline['extra_javascript'].index('assets/javascripts/shell/bootstrap.js')
        baseline['extra_javascript'].insert(index, 'assets/javascripts/shell/search-recovery.js')
        policy.write_text(json.dumps(baseline))
        self.assertEqual(self.run_sync().returncode, 0)
        text = path.read_text()
        self.assertEqual(text.count('assets/javascripts/shell/search-recovery.js'), 1)
        self.assertLess(text.index('search-recovery.js'), text.index('bootstrap.js'))


if __name__ == '__main__':
    unittest.main()
