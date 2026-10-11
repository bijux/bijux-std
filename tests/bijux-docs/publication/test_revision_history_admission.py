"""Bind native revision pages to real committed Git ownership without per-page logs."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('bijux_committed_revision_pages', ROOT / 'shared/bijux-docs/security/producer_capabilities.py')
capabilities = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capabilities)


class CommittedRevisionPages(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'artifacts/qualification/revision-history-admission'
        parent.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.git('init', '-q', '--initial-branch=main')
        self.git('config', 'user.name', 'Bijux')
        self.git('config', 'user.email', 'bijux@example.invalid')
        (self.root / 'docs').mkdir()
        (self.root / 'docs/index.md').write_text('# Committed source\n')
        self.commit('initial committed documentation')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def commit(self, subject):
        self.git('add', 'docs')
        self.git('commit', '-qm', subject)

    def admit(self, *paths):
        capabilities.committed_document_history(self.root, paths, self.git('rev-parse', 'HEAD'))

    def native_history(self, path):
        return bool(self.git('log', '-1', '--format=%H', 'HEAD', '--', path))

    def test_committed_pages_preserve_native_path_history(self):
        self.admit('docs/index.md')
        self.assertTrue(self.native_history('docs/index.md'))

    def test_native_configuration_retains_receipt_and_callback_contract(self):
        from mkdocs.config import load_config
        owner = self.root / 'mkdocs.yml'
        owner.write_text('site_name: History\ndocs_dir: docs\nplugins:\n'
                         '  - git-revision-date-localized:\n'
                         '      enable_creation_date: false\n'
                         '      fallback_to_build_date: true\n')
        config = load_config(config_file=str(owner))
        retained = capabilities.revision_history(config, self.root)
        with patch.object(capabilities, 'git', wraps=capabilities.git) as operations:
            qualified = capabilities.revision_history(config, self.root, publication=True)
        self.assertEqual(qualified, retained | {'publication_history_verified': True})
        self.assertEqual(len(operations.call_args_list), 4)
        self.assertTrue(qualified['fallback_preserved'])

    def test_rename_keeps_actual_committed_destination_history(self):
        self.git('mv', 'docs/index.md', 'docs/renamed.md')
        self.commit('renamed documentation owner')
        self.admit('docs/renamed.md')
        self.assertTrue(self.native_history('docs/renamed.md'))
        with self.assertRaises(capabilities.CapabilityError):
            self.admit('docs/index.md')

    def test_merge_introduced_page_is_committed_native_source(self):
        self.git('switch', '-qc', 'authored-page')
        (self.root / 'docs/merged.md').write_text('# Merged source\n')
        self.commit('branch-authored documentation')
        self.git('switch', '-q', 'main')
        self.git('merge', '-q', '--no-ff', 'authored-page', '-m', 'accepted documentation merge')
        self.admit('docs/merged.md')
        self.assertTrue(self.native_history('docs/merged.md'))

    def test_unchanged_merge_history_union_cannot_admit_staged_ghost(self):
        self.git('switch', '-qc', 'authored-and-removed')
        (self.root / 'docs/ghost.md').write_text('# Removed branch page\n')
        self.commit('branch-authored page')
        self.git('rm', '-q', 'docs/ghost.md')
        self.commit('branch-removed page')
        self.git('switch', '-q', 'main')
        self.git('merge', '-q', '--no-ff', 'authored-and-removed', '-m', 'unchanged documentation merge')
        names = self.git('log', '--full-history', '-m', '--root', '--format=', '--name-only', 'HEAD')
        self.assertIn('docs/ghost.md', names.splitlines())
        self.assertFalse(self.native_history('docs/ghost.md'))
        (self.root / 'docs/ghost.md').write_text('# Staged page\n')
        self.git('add', 'docs/ghost.md')
        with self.assertRaises(capabilities.CapabilityError):
            self.admit('docs/ghost.md')

    def test_deleted_then_staged_source_requires_new_accepted_commit(self):
        self.git('rm', '-q', 'docs/index.md')
        self.git('commit', '-qm', 'deleted documentation owner')
        (self.root / 'docs').mkdir()
        (self.root / 'docs/index.md').write_text('# Staged resurrection\n')
        self.git('add', 'docs/index.md')
        self.assertTrue(self.native_history('docs/index.md'))
        with self.assertRaises(capabilities.CapabilityError):
            self.admit('docs/index.md')

    def test_staged_new_page_has_no_committed_history(self):
        (self.root / 'docs/new.md').write_text('# New source\n')
        self.git('add', 'docs/new.md')
        with self.assertRaises(capabilities.CapabilityError):
            self.admit('docs/new.md')

    def test_staged_modified_page_differs_from_selected_committed_blob(self):
        (self.root / 'docs/index.md').write_text('# Changed source\n')
        self.git('add', 'docs/index.md')
        with self.assertRaises(capabilities.CapabilityError):
            self.admit('docs/index.md')

    def test_generated_untracked_page_is_refused(self):
        (self.root / 'docs/generated.md').write_text('# Generated source\n')
        with self.assertRaises(capabilities.CapabilityError):
            self.admit('docs/generated.md')

    def test_committed_link_is_not_a_regular_documentation_owner(self):
        (self.root / 'docs/linked.md').symlink_to('index.md')
        self.commit('linked documentation source')
        with self.assertRaises(capabilities.CapabilityError):
            self.admit('docs/linked.md')

    def test_unmerged_index_cannot_claim_committed_page_ownership(self):
        self.git('switch', '-qc', 'conflicting-page')
        (self.root / 'docs/index.md').write_text('# Branch source\n')
        self.commit('branch-modified documentation')
        self.git('switch', '-q', 'main')
        (self.root / 'docs/index.md').write_text('# Main source\n')
        self.commit('main-modified documentation')
        merged = subprocess.run(['git', '-C', str(self.root), 'merge', 'conflicting-page'],
                                capture_output=True, text=True)
        self.assertNotEqual(merged.returncode, 0)
        with self.assertRaisesRegex(capabilities.CapabilityError, 'unmerged'):
            self.admit('docs/index.md')

    def test_catalogue_still_requires_complete_original_native_history(self):
        from mkdocs.config import load_config
        clone = self.root / 'artifacts/shallow'
        clone.parent.mkdir()
        subprocess.run(['git', 'clone', '-q', '--depth=1', self.root.as_uri(), str(clone)], check=True)
        owner = self.root / 'mkdocs.yml'
        owner.write_text('site_name: History\nplugins: [git-revision-date-localized]\n')
        config = load_config(config_file=str(owner), docs_dir=str(clone / 'docs'))
        catalogue = types.SimpleNamespace(sources=types.SimpleNamespace(files=lambda files, _: files))
        with self.assertRaisesRegex(capabilities.CapabilityError, 'complete native original history'):
            capabilities.revision_history(config, clone, publication=True, catalogue=catalogue)

    def test_path_names_with_spaces_and_nonascii_use_exact_nul_records(self):
        (self.root / 'docs/Åland reference.md').write_text('# Exact source path\n')
        self.commit('exact documentation path')
        self.admit('docs/Åland reference.md')
        self.assertTrue(self.native_history('docs/Åland reference.md'))

    def test_git_membership_cost_is_constant_for_many_pages(self):
        for number in range(80):
            (self.root / f'docs/reference-{number}.md').write_text('# Committed reference\n')
        self.commit('committed reference corpus')
        paths = [f'docs/reference-{number}.md' for number in range(80)]
        with patch.object(capabilities, 'git', wraps=capabilities.git) as operations:
            capabilities.committed_document_history(self.root, paths, self.git('rev-parse', 'HEAD'))
        self.assertEqual(len(operations.call_args_list), 2)
        self.assertTrue(all(self.native_history(path) for path in paths))

    def test_shallow_boundary_keeps_existing_native_publication_semantics(self):
        clone = self.root / 'artifacts/shallow'
        clone.parent.mkdir()
        subprocess.run(['git', 'clone', '-q', '--depth=1', self.root.as_uri(), str(clone)], check=True)
        head = subprocess.check_output(['git', '-C', str(clone), 'rev-parse', 'HEAD'], text=True).strip()
        capabilities.committed_document_history(clone, ['docs/index.md'], head)
        self.assertTrue(subprocess.check_output(
            ['git', '-C', str(clone), 'log', '-1', '--format=%H', 'HEAD', '--', 'docs/index.md'], text=True).strip())


if __name__ == '__main__':
    unittest.main()
