"""Source-backed catalogue rendering against native MkDocs and revision events."""
from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mkdocs.config import load_config
from mkdocs.commands.build import build
from mkdocs.structure.files import File, Files
from mkdocs.structure.pages import Page

HERE = Path(__file__).resolve()
REPO = next(parent for parent in HERE.parents
            if (parent / 'shared/bijux-docs/security/catalogue_sources.py').is_file())
ARTIFACTS = REPO / 'artifacts/catalogue-native-sources'
ARTIFACTS.mkdir(parents=True, exist_ok=True)
MODULE = REPO / 'shared/bijux-docs/security/catalogue_sources.py'
spec = importlib.util.spec_from_file_location('bijux_catalogue_native_sources', MODULE)
adapter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = adapter
spec.loader.exec_module(adapter)


def replacement(value, **changes):
    return value._replace(**changes)


class CatalogueNativeSourcesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=ARTIFACTS, prefix='native-catalogue-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = 'originals/course.md'
        self.original = b'# Original course\n\nOriginal relative link.\n'
        self.projected = b'# Projected course\n\nRewritten public link.\n'
        for name, data in {self.source: self.original, 'docs/assets/identity.txt': b'asset',
                           'docs/ignored.md': b'# Unattributed old output\n'}.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Bijux verification')
        self.git('config', 'user.email', 'verification@bijux.invalid')
        self.git('add', 'originals/course.md', 'docs/assets/identity.txt')
        self.git('commit', '-qm', 'docs(catalogue): author original course',
                 environment={'GIT_AUTHOR_DATE': '2020-01-02T03:04:05+00:00',
                              'GIT_COMMITTER_DATE': '2021-02-03T04:05:06+00:00'})
        self.configuration = load_config(config_file=io.BytesIO((
            f'site_name: Native catalogue\ndocs_dir: {self.root}/docs\n'
            f'site_dir: {self.root}/site\ntheme: material\nplugins:\n  - git-revision-date-localized:\n'
            '      enable_creation_date: true\n      enable_parallel_processing: false\n'
            '      fallback_to_build_date: false\n'
            'nav:\n  - Course: course/index.md\n').encode()))
        self.configuration.config_file_path = str(self.root / 'mkdocs.yml')
        self.configuration.plugins.on_startup(command='build', dirty=False)
        self.document = adapter.OriginalDocument(self.source, 'course/index.md', self.projected)
        self.sources = adapter.CatalogueSources(self.root, {self.source: self.original}, [self.document])

    def git(self, *args, environment=None):
        command = subprocess.run(['git', '-C', str(self.root), *args], check=True,
                                 capture_output=True, text=True,
                                 env={**os.environ, **(environment or {})})
        return command.stdout.strip()

    def page(self):
        files = self.sources.files(Files([]), self.configuration)
        return Page(None, files.get_file_from_path('course/index.md'), self.configuration)

    def test_real_file_identity_and_public_content_event(self):
        plugin = adapter.CatalogueSourcePlugin(self.sources)
        self.configuration.plugins['bijux/catalogue-sources'] = plugin
        page = self.page()
        self.assertEqual(page.file.content_bytes, self.original)
        self.assertEqual(page.file.abs_src_path, str(self.root / self.source))
        self.assertIsNone(page.file.generated_by)
        self.assertEqual(page.file.edit_uri, self.source)
        page.read_source(self.configuration)
        self.assertEqual(page.markdown, self.projected.decode())

    def test_native_revision_reads_real_author_date_not_build_or_committer_clock(self):
        plugin = self.configuration.plugins['git-revision-date-localized']
        plugin.on_config(self.configuration)
        page = self.page()
        for first in (True, False):
            actual = plugin._get_commit(page, first)
            expected = plugin.util.get_git_commit_timestamp(str(self.root / self.source), first)
            self.assertEqual(actual, expected)
            self.assertTrue(actual[0])
            self.assertEqual(actual[1], 1577934245)

    def test_native_parallel_history_retains_original_keys(self):
        plugin = self.configuration.plugins['git-revision-date-localized']
        plugin.config['enable_parallel_processing'] = True
        plugin.on_config(self.configuration)
        files = self.sources.files(Files([]), self.configuration)
        plugin.on_files(files, self.configuration)
        page = self.page()
        for first in (True, False):
            self.assertEqual(plugin._get_commit(page, first),
                             plugin.util.get_git_commit_timestamp(str(self.root / self.source), first))
        self.assertEqual(set(plugin.last_revision_commits), {str(self.root / self.source)})
        self.assertEqual(set(plugin.created_commits), {str(self.root / self.source)})

    def test_actual_strict_native_build_renders_projection_and_native_dates(self):
        (self.root / 'docs/ignored.md').unlink()
        self.configuration.plugins['bijux/catalogue-sources'] = adapter.CatalogueSourcePlugin(self.sources)
        self.configuration.plugins['git-revision-date-localized'].config['enable_parallel_processing'] = True
        self.configuration.strict = True
        build(self.configuration)
        html = (self.root / 'site/course/index.html').read_text()
        self.assertIn('Projected course', html)
        self.assertNotIn('Original relative link.', html)
        self.assertIn('2020', html)
        self.assertEqual((self.root / self.source).read_bytes(), self.original)
        (ARTIFACTS / 'native-strict-projected-course.html').write_text(html)
        events = self.configuration.plugins.events['files']
        self.assertIs(events[0].__self__, self.configuration.plugins['bijux/catalogue-sources'])

    def test_assets_preserved_and_unattributed_documentation_rejected(self):
        asset = File('assets/identity.txt', str(self.root / 'docs'), self.configuration.site_dir, True)
        foreign = File('ignored.md', str(self.root / 'docs'), self.configuration.site_dir, True)
        with self.assertRaises(adapter.CatalogueSourceError):
            self.sources.files(Files([asset, foreign]), self.configuration)
        files = self.sources.files(Files([asset]), self.configuration)
        self.assertIs(files.get_file_from_path('assets/identity.txt'), asset)
        self.assertEqual(len(files.documentation_pages()), 1)

    def test_absent_original_rejected(self):
        with self.assertRaises(adapter.CatalogueSourceError):
            adapter.CatalogueSources(self.root, {}, [self.document])

    def test_duplicate_route_rejected(self):
        with self.assertRaises(adapter.CatalogueSourceError):
            adapter.CatalogueSources(self.root, {self.source: self.original}, [self.document, self.document])

    def test_unsafe_source_and_route_rejected(self):
        for field, value in [('source', '../course.md'), ('route', '/index.md'),
                             ('route', 'course//index.md'), ('route', 'course\\index.md')]:
            with self.subTest(field=field, value=value), self.assertRaises(adapter.CatalogueSourceError):
                adapter.CatalogueSources(self.root, {self.source: self.original},
                                        [replacement(self.document, **{field: value})])

    def test_changed_original_rejected_before_render(self):
        (self.root / self.source).write_bytes(b'# Changed\n')
        with self.assertRaises(adapter.CatalogueSourceError):
            self.sources.files(Files([]), self.configuration)

    def test_original_symlink_rejected(self):
        path = self.root / self.source
        path.unlink()
        path.symlink_to(self.root / 'docs/ignored.md')
        with self.assertRaises(adapter.CatalogueSourceError):
            self.sources.files(Files([]), self.configuration)

    def test_foreign_route_cannot_use_reconstructed_content(self):
        page = self.page()
        page.file.src_uri = 'unowned/index.md'
        with self.assertRaises(adapter.CatalogueSourceError):
            self.sources.read(page)

    def test_replaced_original_or_generated_marker_rejected(self):
        for field, value in [('abs_src_path', str(self.root / 'docs/ignored.md')),
                             ('generated_by', 'unreviewed'), ('edit_uri', 'docs/ignored.md')]:
            with self.subTest(field=field):
                page = self.page()
                setattr(page.file, field, value)
                with self.assertRaises(adapter.CatalogueSourceError):
                    self.sources.read(page)


if __name__ == '__main__':
    unittest.main(verbosity=2)
