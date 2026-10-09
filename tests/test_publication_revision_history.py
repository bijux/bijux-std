"""Preserve reviewed revision callbacks and require actual publication history."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('bijux_revision_capabilities', ROOT / 'shared/bijux-docs/security/producer_capabilities.py')
capabilities = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capabilities)


class RevisionHistory(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT / 'artifacts/website-security/revision-tests'
        artifacts.mkdir(parents=True, exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.owner = self.root / 'owner'
        self.docs = self.owner / 'docs'
        self.docs.mkdir(parents=True)
        self.installed = self.root / 'installed'
        source = self.installed / 'mkdocs_git_revision_date_localized_plugin/controlled.py'
        source.parent.mkdir(parents=True)
        source.write_text('class Plugin:\n    config = {"fallback_to_build_date": True, "enable_creation_date": False}\n')
        name = 'mkdocs_git_revision_date_localized_plugin.controlled'
        spec = importlib.util.spec_from_file_location(name, source)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.plugin = self.module.Plugin()
        self.config = types.SimpleNamespace(plugins={'git-revision-date-localized': self.plugin}, docs_dir=str(self.docs))
        files = types.ModuleType('mkdocs.structure.files')
        self.pages = [types.SimpleNamespace(abs_src_path=str(self.docs / 'index.md'))]
        files.get_files = lambda _: types.SimpleNamespace(documentation_pages=lambda: self.pages)
        self.start(patch.dict(sys.modules, {name: self.module, 'mkdocs': types.ModuleType('mkdocs'), 'mkdocs.structure': types.ModuleType('mkdocs.structure'), 'mkdocs.structure.files': files}))
        self.version = self.start(patch('importlib.metadata.version', return_value='1.5.1'))
        self.start(patch('importlib.metadata.distribution', return_value=types.SimpleNamespace(locate_file=lambda _: self.installed)))
        self.git = self.start(patch.object(capabilities, 'git', side_effect=self.history))

    def start(self, mock):
        result = mock.start()
        self.addCleanup(mock.stop)
        return result

    def history(self, root, *args):
        if args == ('rev-parse', 'HEAD'):
            return 'c' * 40
        if args[0] == 'ls-files':
            return 'docs/index.md'
        return 'c' * 40 + ':1700000000:'

    def test_reviewed_versions_preserve_source_and_authored_configuration(self):
        for version in ('1.5.1', '1.5.3', '1.6.0'):
            with self.subTest(version=version):
                self.version.return_value = version
                receipt = capabilities.revision_history(self.config, self.owner)
                self.assertEqual(receipt['head'], 'c' * 40)
                self.assertEqual(receipt['source_config'], self.plugin.config)
                self.assertTrue(receipt['fallback_preserved'])
                self.assertFalse(receipt['publication_history_verified'])
                self.assertEqual(len(receipt['plugin_source_sha256']), 64)

    def test_unreviewed_versions_fail_before_history(self):
        for version in ('1.5.2', '1.5.1+local', '0.1.0'):
            with self.subTest(version=version):
                self.version.return_value = version
                self.assertRaisesRegex(capabilities.CapabilityError, 'reviewed revision date', capabilities.revision_history, self.config, self.owner)
        self.git.assert_not_called()

    def test_absent_revision_plugin_has_no_fictional_history(self):
        self.config.plugins.clear()
        self.assertIsNone(capabilities.revision_history(self.config, self.owner))
        self.git.assert_not_called()

    def test_foreign_plugin_class_cannot_use_installed_version(self):
        self.config.plugins['git-revision-date-localized'] = types.SimpleNamespace(config={})
        self.assertRaisesRegex(capabilities.CapabilityError, 'actual revision plugin source', capabilities.revision_history, self.config, self.owner)

    def test_shadowed_module_cannot_use_distribution_identity(self):
        self.module.__file__ = str(self.owner / 'foreign.py')
        self.assertRaisesRegex(capabilities.CapabilityError, 'import shadowed', capabilities.revision_history, self.config, self.owner)

    def test_empty_docs_history_cannot_claim_freshness(self):
        self.git.side_effect = lambda root, *args: 'c' * 40 if args[0] == 'rev-parse' else ''
        self.assertRaisesRegex(capabilities.CapabilityError, 'actual source revision history', capabilities.revision_history, self.config, self.owner)

    def test_publication_requires_each_tracked_source_and_history(self):
        receipt = capabilities.revision_history(self.config, self.owner, publication=True)
        self.assertTrue(receipt['publication_history_verified'])
        self.git.assert_any_call(self.owner, 'ls-files', '--error-unmatch', 'docs/index.md')
        self.git.assert_any_call(self.owner, 'log', '-1', '--format=%H', 'HEAD', '--', 'docs/index.md')

    def test_untracked_publication_page_cannot_use_build_date_fallback(self):
        def missing(root, *args):
            if args[0] == 'ls-files':
                raise subprocess.CalledProcessError(1, ['git', *args])
            return self.history(root, *args)
        self.git.side_effect = missing
        self.assertRaises(subprocess.CalledProcessError, capabilities.revision_history, self.config, self.owner, publication=True)

    def test_tracked_page_without_history_cannot_use_build_date_fallback(self):
        def missing(root, *args):
            if args[:2] == ('log', '-1'):
                return ''
            return self.history(root, *args)
        self.git.side_effect = missing
        self.assertRaisesRegex(capabilities.CapabilityError, 'missing source history', capabilities.revision_history, self.config, self.owner, publication=True)


if __name__ == '__main__':
    unittest.main()
