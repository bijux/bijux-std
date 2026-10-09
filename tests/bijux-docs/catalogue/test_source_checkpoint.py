"""Typed owner selection controls; provider acceptance is an explicit unit fixture."""
from pathlib import Path
import copy
import importlib.util
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from fixture_source import create_fixture

HERE = Path(__file__).resolve()
REPO = next(parent for parent in HERE.parents
            if (parent / 'shared/bijux-docs/security/catalogue_recipe.py').is_file())
OUTPUT = REPO / 'artifacts/catalogue-checkpoint-tests'
OUTPUT.mkdir(parents=True, exist_ok=True)


def load(path):
    spec = importlib.util.spec_from_file_location('bijux_catalogue_checkpoint_identity', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceCheckpoint(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(dir=OUTPUT)
        self.addCleanup(directory.cleanup)
        self.root = create_fixture(REPO, Path(directory.name) / 'source')
        self.shared = self.root / '.bijux/shared/bijux-docs'
        pin = self.root / '.github/standards/bijux-std.sha'
        pin.parent.mkdir(parents=True)
        pin.write_text('a' * 40 + '\n')
        self.git('add', '.github/standards/bijux-std.sha')
        self.git('commit', '-qm', 'test(docs): bind controlled standard pointer')
        self.identity = load(self.shared / 'security/build_identity.py')
        self.authority = {'sha': 'a' * 40,
                          'shared_tree_sha256': self.identity.tree_identity(self.shared)}
        provider = patch.object(self.identity, 'fetched_standard', return_value=self.authority)
        provider.start()
        self.addCleanup(provider.stop)

    def git(self, *arguments):
        return subprocess.run(['git', '-C', str(self.root), *arguments], check=True,
                              capture_output=True, text=True).stdout.strip()

    def checkpoint(self, **selection):
        return self.identity.source_checkpoint(
            self.root, self.git('rev-parse', 'HEAD'), 'artifacts/provider-fixture',
            'https://bijux.io/bijux-masterclass/', 'artifacts/site',
            'build-catalogue', 'verify-catalogue', **selection)

    def test_tracked_owner_and_derived_configuration_are_distinct(self):
        record = self.checkpoint(source_recipe='masterclass-catalogue')
        self.assertEqual(record['config']['path'], 'mkdocs.yml')
        self.assertEqual(record['derivation']['configuration']['path'], 'artifacts/mkdocs.root.yml')
        self.identity.verify_source(self.root, record)

    def test_generic_tracked_checkpoint_has_no_derived_scope(self):
        record = self.checkpoint()
        self.assertNotIn('derivation', record)
        self.identity.verify_source(self.root, record)

    def test_ignored_configuration_cannot_become_tracked_owner(self):
        with self.assertRaises(ValueError):
            self.checkpoint(config='artifacts/mkdocs.root.yml', source_recipe='masterclass-catalogue')

    def test_unknown_recipe_cannot_be_checkpointed(self):
        with self.assertRaisesRegex(ValueError, 'unknown recipe'):
            self.checkpoint(source_recipe='unreviewed-recipe')

    def test_forged_derived_map_cannot_pass_source_verification(self):
        record = self.checkpoint(source_recipe='masterclass-catalogue')
        record['derivation']['document_map_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'record differs'):
            self.identity.verify_source(self.root, record)

    def test_owner_cannot_be_relabelled_as_effective_configuration(self):
        record = self.checkpoint(source_recipe='masterclass-catalogue')
        record['derivation']['owner'] = record['derivation']['configuration']
        with self.assertRaisesRegex(ValueError, 'tracked owner checkpoint'):
            self.identity.verify_source(self.root, record)

    def test_malformed_derivation_record_fails_closed(self):
        record = self.checkpoint(source_recipe='masterclass-catalogue')
        record['derivation'] = ['untyped']
        with self.assertRaisesRegex(ValueError, 'tracked owner checkpoint'):
            self.identity.verify_source(self.root, record)

    def test_changed_committed_owner_does_not_reuse_prior_checkpoint(self):
        record = self.checkpoint(source_recipe='masterclass-catalogue')
        path = self.root / 'mkdocs.yml'
        path.write_text(path.read_text() + '\nsite_description: changed\n')
        with self.assertRaises(ValueError):
            self.identity.verify_source(self.root, record)


if __name__ == '__main__':
    unittest.main(verbosity=2)
