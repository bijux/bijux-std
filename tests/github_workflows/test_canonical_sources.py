from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .policy_fixtures import MODULE, source_fixture, byte_tree


class CanonicalSourceCaptureTests(unittest.TestCase):
    def test_actual_finite_capture_repeats_without_writes(self):
        with tempfile.TemporaryDirectory() as workspace:
            root, owned = source_fixture(workspace)
            before = byte_tree(root)
            actual = owned.capture_sources(root)
            self.assertEqual(actual, owned.capture_sources(root))
            self.assertEqual(before, byte_tree(root))
            manifest = json.loads(actual['.github/standards/workflow-sources/source-manifest.json'])
            self.assertIn('.github/scripts/workflow_execution/verification.py', manifest['inputs'])
            self.assertIn('.github/scripts/check_workflow_projection.py', manifest['inputs'])
            self.assertIn('.github/standards/repo-config.manifest.json', manifest['inputs'])
            self.assertEqual(actual['.github/standards/workflow-sources/bijux-std.yml'],
                             (root / '.github/workflows/bijux-std.yml').read_bytes())
            owned.validate_source_snapshots(root)

    def test_stale_or_missing_snapshot_refuses_without_repair(self):
        for variant in ['base', 'manifest', 'missing']:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as workspace:
                root, owned = source_fixture(workspace)
                path = root / '.github/standards/workflow-sources/bijux-std.yml'
                if variant == 'manifest':
                    path = root / '.github/standards/workflow-sources/source-manifest.json'
                if variant == 'missing':
                    path.unlink()
                else:
                    path.write_bytes(path.read_bytes() + b'\n')
                before = byte_tree(root)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    owned.validate_source_snapshots(root)
                self.assertEqual(before, byte_tree(root))

    def test_changed_canonical_input_cannot_reuse_old_snapshots(self):
        with tempfile.TemporaryDirectory() as workspace:
            root, owned = source_fixture(workspace)
            path = root / '.github/scripts/check_pinned_actions.py'
            path.write_bytes(path.read_bytes() + b'\n# changed owning input\n')
            with self.assertRaisesRegex(ValueError, 'stale canonical source snapshot'):
                owned.validate_source_snapshots(root)

    def test_inventory_divergence_refuses_capture(self):
        with tempfile.TemporaryDirectory() as workspace:
            root, owned = source_fixture(workspace)
            path = root / '.github/standards/workflow-inventory.json'
            content = json.loads(path.read_text());content['managed_workflows'].pop()
            path.write_text(json.dumps(content))
            with self.assertRaisesRegex(ValueError, 'inventory differs'):
                owned.capture_sources(root)

    def test_symlink_and_unbounded_source_refuse(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            (root / 'owned').write_text('source')
            (root / 'alias').symlink_to(root / 'owned')
            for relative in ['../owned', '/owned', 'alias']:
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    MODULE.canonical_sources.read_owned(root, relative)


if __name__ == '__main__':
    unittest.main()
