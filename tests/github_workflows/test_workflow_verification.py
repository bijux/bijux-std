from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .policy_fixtures import source_fixture, projection_fixture, byte_tree, refresh_snapshots


class CanonicalWorkflowVerificationTests(unittest.TestCase):
    def owning_writer_fixture(self, workspace):
        source, initial = source_fixture(workspace)
        root = Path(workspace) / 'bijux-std'
        source.rename(root)
        sync, renderer = initial.canonical_sources.owning_scripts(root)
        owned = sync.WORKFLOW_EXECUTION
        manifest = sync.load_manifest()
        sync.resolve_repository_checkout = lambda name: root
        renderer.resolve_repository_checkout = lambda name: root
        sync.copy_repo_files('bijux-std', sync.find_repo_config(manifest, 'bijux-std'), manifest)
        renderer.render_repo('bijux-std', manifest)
        return root, owned, manifest

    def test_owning_writer_all_inventory_mirrors_and_canonical_sources_are_read_only(self):
        with tempfile.TemporaryDirectory() as workspace:
            root, owned, manifest = self.owning_writer_fixture(workspace)
            inventory = manifest['workflow_inventory']['managed_workflows']
            self.assertEqual(len(inventory), 10)
            before = byte_tree(root)
            first = owned.verify_projection(root, root, 'bijux-std')
            self.assertEqual(first, owned.verify_projection(root, root, 'bijux-std'))
            self.assertEqual(before, byte_tree(root))
            self.assertFalse(first['mutated_product'])
            for entry in inventory:
                for relative in [entry['source'], '.bijux/' + entry['source']]:
                    self.assertIn(relative, first['verified_files'])
                    self.assertNotIn(relative, first['absent_paths'])

    def test_owning_writer_each_raw_mirror_drift_refuses_without_mutation(self):
        with tempfile.TemporaryDirectory() as workspace:
            root, owned, manifest = self.owning_writer_fixture(workspace)
            for entry in manifest['workflow_inventory']['managed_workflows']:
                relative = '.bijux/' + entry['source']
                with self.subTest(relative=relative):
                    path = root / relative
                    original = path.read_bytes()
                    path.write_bytes(original + b'\n# raw mirror drift\n')
                    before = byte_tree(root)
                    with self.assertRaisesRegex(ValueError, 'noncanonical managed projection: ' + relative):
                        owned.verify_projection(root, root, 'bijux-std')
                    self.assertEqual(before, byte_tree(root))
                    path.write_bytes(original)

    def test_owning_writer_enabled_pr_approval_runtime_drift_refuses(self):
        with tempfile.TemporaryDirectory() as workspace:
            root, owned, _ = self.owning_writer_fixture(workspace)
            relative = '.github/workflows/pr-approval-policy.yml'
            path = root / relative
            original = path.read_bytes()
            self.assertIn(b'timeout-minutes: 10', original)
            path.write_bytes(original.replace(b'timeout-minutes: 10', b'timeout-minutes: 11'))
            before = byte_tree(root)
            with self.assertRaisesRegex(ValueError, 'noncanonical managed projection: ' + relative):
                owned.verify_projection(root, root, 'bijux-std')
            self.assertEqual(before, byte_tree(root))

    def test_separate_owning_projection_canonical_raw_source_drift_refuses(self):
        with tempfile.TemporaryDirectory() as workspace:
            source, owned = source_fixture(workspace)
            target = Path(workspace) / 'bijux-std'
            projection_fixture(source, owned, target, repository='bijux-std')
            relative = 'shared/bijux-gh/workflows/release-artifacts.yml'
            path = target / relative
            path.write_bytes(path.read_bytes() + b'\n# canonical raw source drift\n')
            before = byte_tree(target)
            with self.assertRaisesRegex(ValueError, 'noncanonical managed projection: ' + relative):
                owned.verify_projection(source, target, 'bijux-std')
            self.assertEqual(before, byte_tree(target))

    def test_default_and_selected_repeated_projection_are_read_only(self):
        for selected in [False, True]:
            with self.subTest(selected=selected), tempfile.TemporaryDirectory() as workspace:
                source, owned = source_fixture(workspace, selected=selected)
                target = Path(workspace) / 'projected-repository'
                expected = projection_fixture(source, owned, target)
                before = byte_tree(target)
                first = owned.verify_projection(source, target, 'bijux-atlas')
                self.assertEqual(first, owned.verify_projection(source, target, 'bijux-atlas'))
                self.assertEqual(before, byte_tree(target))
                self.assertFalse(first['mutated_product'])
                self.assertEqual(owned.requires_parser(source, 'bijux-atlas'), selected)
                self.assertEqual(expected, owned.verification.expected_projection(source, target, 'bijux-atlas')[0])

    def test_checksum_consistent_managed_runtime_drift_refuses(self):
        with tempfile.TemporaryDirectory() as workspace:
            source, owned = source_fixture(workspace)
            target = Path(workspace) / 'projected-repository'
            projection_fixture(source, owned, target)
            path = target / '.github/workflows/automerge-pr.yml'
            original = path.read_bytes();changed = original.replace(b'  enable:\n', b'  enable:\n    if: false\n', 1)
            self.assertNotEqual(original, changed);path.write_bytes(changed)
            (target / '.github/bijux-std-shared.sha256').write_text(hashlib.sha256(changed).hexdigest()+'  .github/workflows/automerge-pr.yml\n')
            before = byte_tree(target)
            with self.assertRaisesRegex(ValueError, 'noncanonical managed projection: .github/workflows/automerge-pr.yml'):
                owned.verify_projection(source, target, 'bijux-atlas')
            self.assertEqual(before, byte_tree(target))

    def test_rebound_governance_inputs_never_select_expected_runtime(self):
        for relative in ['.github/standards/repo-config.manifest.json',
                         '.github/scripts/workflow_execution/schema.py',
                         '.github/scripts/workflow_execution/verification.py',
                         '.github/standards/workflow-sources/source-manifest.json',
                         '.bijux/shared/bijux-gh/workflows/github-policy.yml']:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as workspace:
                source, owned = source_fixture(workspace)
                target = Path(workspace) / 'projected-repository';projection_fixture(source, owned, target)
                path = target / relative;path.write_bytes(path.read_bytes()+b'\n')
                before = byte_tree(target)
                with self.assertRaisesRegex(ValueError, 'noncanonical managed projection'):
                    owned.verify_projection(source, target, 'bijux-atlas')
                self.assertEqual(before, byte_tree(target))

    def test_disabled_runtime_presence_refuses(self):
        with tempfile.TemporaryDirectory() as workspace:
            source, owned = source_fixture(workspace)
            manifest_path = source / '.github/standards/repo-config.manifest.json'
            manifest = json.loads(manifest_path.read_text())
            repo = next(entry for entry in manifest['repositories'] if entry['name'] == 'bijux-atlas')
            repo['workflow_allowlist'].remove('release-ghcr')
            manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
            refresh_snapshots(source, owned)
            target = Path(workspace) / 'projected-repository';projection_fixture(source, owned, target)
            (target / '.github/workflows/release-ghcr.yml').write_text('owned-looking but disabled\n')
            with self.assertRaisesRegex(ValueError, 'disabled managed destination'):
                owned.verify_projection(source, target, 'bijux-atlas')

    def test_missing_and_symlinked_projection_refuse(self):
        for variant in ['missing', 'symlink']:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as workspace:
                source, owned = source_fixture(workspace)
                target = Path(workspace) / 'projected-repository';projection_fixture(source, owned, target)
                path = target / '.github/scripts/render_repo_configs.py';path.unlink()
                if variant == 'symlink':
                    path.symlink_to(source / '.github/scripts/render_repo_configs.py')
                with self.assertRaisesRegex(ValueError, 'unreadable managed projection'):
                    owned.verify_projection(source, target, 'bijux-atlas')

    def test_missing_executable_dependency_is_not_hidden_by_incomplete_copy_mapping(self):
        with tempfile.TemporaryDirectory() as workspace:
            source, owned = source_fixture(workspace)
            target = Path(workspace) / 'projected-repository';projection_fixture(source, owned, target)
            relative = '.github/scripts/workflow_execution/verification.py'
            (target / relative).unlink()
            with self.assertRaisesRegex(ValueError, 'unreadable managed projection'):
                owned.verify_projection(source, target, 'bijux-atlas')

    def test_source_change_during_verification_refuses(self):
        with tempfile.TemporaryDirectory() as workspace:
            source, owned = source_fixture(workspace)
            target = Path(workspace) / 'projected-repository';projection_fixture(source, owned, target)
            real = owned.verification.read_owned
            changed = False
            def source_change(root, relative):
                nonlocal changed
                result = real(root, relative)
                if root == target.resolve() and not changed:
                    changed = True
                    path = source / '.github/CODEOWNERS'
                    path.write_bytes(path.read_bytes()+b'\n# changed source during comparison\n')
                return result
            before = byte_tree(target)
            with mock.patch.object(owned.verification, 'read_owned', side_effect=source_change):
                with self.assertRaisesRegex(ValueError, 'source changed during'):
                    owned.verify_projection(source, target, 'bijux-atlas')
            self.assertTrue(changed)
            self.assertEqual(before, byte_tree(target))

    def test_authored_manual_publisher_call_refuses_before_any_write(self):
        with tempfile.TemporaryDirectory() as workspace:
            source, owned = source_fixture(workspace, selected=True)
            target = Path(workspace) / 'projected-repository';projection_fixture(source, owned, target)
            (target / '.github/workflows/owned-release.yml').write_text('on: workflow_dispatch\njobs:\n  publish:\n    uses: ./.github/workflows/release-github.yml\n')
            before = byte_tree(target)
            with self.assertRaisesRegex(ValueError, 'manual-only publication'):
                owned.verify_projection(source, target, 'bijux-atlas')
            self.assertEqual(before, byte_tree(target))


if __name__ == '__main__':
    unittest.main()
