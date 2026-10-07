"""Validate immutable refresh failure boundaries using explicit local repositories."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
UPDATER = Path(os.environ.get('BIJUX_TEST_UPDATER', ROOT / 'shared/bijux-checks/update-bijux-std.sh'))
GUARD = ROOT / 'shared/bijux-checks/scripts/verify-accepted-source.sh'
CONFIG = ROOT / 'shared/bijux-checks/bijux-std-checks.yml'


class ExactSourceRefreshTests(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT / 'artifacts/website-delivery'
        artifacts.mkdir(parents=True, exist_ok=True)
        self.sandbox = tempfile.TemporaryDirectory(prefix='source-refresh-', dir=artifacts)
        self.addCleanup(self.sandbox.cleanup)
        self.base = Path(self.sandbox.name)
        self.source = self.base / 'upstream'
        self.source.mkdir()
        for name in ('bijux-makes', 'bijux-makes-rs', 'bijux-checks', 'bijux-gh'):
            path = self.source / 'shared' / name
            path.mkdir(parents=True)
            (path / 'marker.txt').write_text('accepted bytes\n')
        self.git(self.source, 'init', '-q')
        self.git(self.source, 'config', 'user.email', 'bijux@example.invalid')
        self.git(self.source, 'config', 'user.name', 'Bijux tests')
        self.git(self.source, 'add', 'shared')
        self.git(self.source, 'commit', '-qm', 'test(std): define exact source')
        self.sha = self.git(self.source, 'rev-parse', 'HEAD').stdout.strip()
        self.consumer = self.base / 'consumer'
        managed = self.consumer / '.bijux/shared'
        managed.mkdir(parents=True)
        (managed / 'shared-dir-sha256.txt').write_text('previous manifest\n')
        (managed / 'bijux-makes').mkdir()
        (managed / 'bijux-makes/marker.txt').write_text('previous bytes\n')
        self.git(self.consumer, 'init', '-q')
        self.env = dict(os.environ, BIJUX_STD_CONFIG=str(CONFIG),
                        BIJUX_STD_GIT_URL=str(self.source), BIJUX_STD_REF=self.sha,
                        BIJUX_STD_CAPABILITIES='rust', BIJUX_STD_SELF_REPO_MODE='off',
                        BIJUX_STD_ALLOW_LOCAL_SOURCE='1')

    @staticmethod
    def git(repo, *args):
        return subprocess.run(['git', '-C', str(repo), *args], text=True, capture_output=True, check=True)

    def refresh(self, **env):
        return subprocess.run(['bash', str(UPDATER)], cwd=self.consumer,
                              env=dict(self.env, **env), text=True, capture_output=True)

    def managed_snapshot(self):
        return {p.relative_to(self.consumer).as_posix(): p.read_bytes()
                for tree in (self.consumer / '.bijux/shared', self.consumer / 'shared')
                for p in tree.rglob('*') if p.is_file()}

    def test_unavailable_exact_sha_fails_without_head_substitution_or_mutation(self):
        before = self.managed_snapshot()
        result = self.refresh(BIJUX_STD_REF='f' * 40)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.managed_snapshot(), before)
        self.assertIn('no fallback', result.stderr)

    def test_valid_exact_sha_records_resolved_provenance(self):
        result = self.refresh()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.consumer / '.bijux/shared/bijux-makes/marker.txt').read_text(), 'accepted bytes\n')
        receipt = json.loads((self.consumer / 'artifacts/bijux-std/source-provenance.json').read_text())
        self.assertEqual(receipt['resolved_sha'], self.sha)
        self.assertEqual(receipt['requested_ref'], self.sha)
        self.assertTrue(receipt['verification_only'])
        self.assertEqual(receipt['result'], 'refreshed')
        recovery = Path(receipt['recovery_directory'])
        self.assertEqual((recovery / '.bijux/shared/bijux-makes/marker.txt').read_text(), 'previous bytes\n')
        self.assertEqual((recovery / 'shared-dir-sha256.txt').read_text(), 'previous manifest\n')

    def test_explicit_branch_ref_resolves_to_the_fetched_full_sha(self):
        branch = self.git(self.source, 'symbolic-ref', 'HEAD').stdout.strip()
        result = self.refresh(BIJUX_STD_REF=branch)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.consumer / 'artifacts/bijux-std/source-provenance.json').read_text())
        self.assertEqual(receipt['resolved_sha'], self.sha)
        self.assertEqual(receipt['requested_ref'], branch)

    def test_unavailable_named_ref_fails_before_consumer_mutation(self):
        before = self.managed_snapshot()
        result = self.refresh(BIJUX_STD_REF='missing-accepted-source')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.managed_snapshot(), before)

    def test_local_source_is_never_reported_as_accepted_github_rollout(self):
        before = self.managed_snapshot()
        result = self.refresh(BIJUX_STD_ALLOW_LOCAL_SOURCE='0')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.managed_snapshot(), before)
        self.assertIn('GitHub', result.stderr)

    def test_verified_dry_run_has_no_managed_changes(self):
        before = self.managed_snapshot()
        result = self.refresh(BIJUX_STD_UPDATE_DRY_RUN='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.managed_snapshot(), before)
        self.assertTrue(json.loads((self.consumer / 'artifacts/bijux-std/source-provenance.json').read_text())['dry_run'])

    def commit_consumer(self):
        self.git(self.consumer, 'config', 'user.email', 'bijux@example.invalid')
        self.git(self.consumer, 'config', 'user.name', 'Bijux tests')
        self.git(self.consumer, 'add', '.bijux')
        self.git(self.consumer, 'commit', '-qm', 'test(std): retain previous managed source')

    def test_tracked_managed_user_edit_is_preserved(self):
        self.commit_consumer()
        (self.consumer / '.bijux/shared/bijux-makes/marker.txt').write_text('user work\n')
        before = self.managed_snapshot()
        result = self.refresh()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.managed_snapshot(), before)
        self.assertIn('preserve local managed', result.stderr)

    def test_untracked_managed_user_input_is_preserved(self):
        self.commit_consumer()
        (self.consumer / '.bijux/shared/bijux-makes/user.mk').write_text('user work\n')
        before = self.managed_snapshot()
        result = self.refresh()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.managed_snapshot(), before)
        self.assertIn('preserve untracked', result.stderr)

    def legacy_tree(self):
        legacy = self.consumer / 'shared/bijux-makes'
        legacy.mkdir(parents=True)
        (legacy/'marker.txt').write_text('legacy bytes\n')
        return legacy

    def commit_all_managed(self):
        self.git(self.consumer, 'config', 'user.email', 'bijux@example.invalid')
        self.git(self.consumer, 'config', 'user.name', 'Bijux tests')
        self.git(self.consumer, 'add', '.bijux', 'shared')
        self.git(self.consumer, 'commit', '-qm', 'test(std): retain installed and legacy source')

    def test_tracked_legacy_shared_edit_is_preserved_before_cleanup(self):
        legacy = self.legacy_tree()
        self.commit_all_managed()
        (legacy/'marker.txt').write_text('legacy user work\n')
        before = self.managed_snapshot()
        result = self.refresh()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.managed_snapshot(), before)
        self.assertIn('preserve local managed changes', result.stderr)
        self.assertIn('shared/bijux-makes', result.stderr)

    def test_untracked_legacy_shared_input_is_preserved_before_cleanup(self):
        legacy = self.legacy_tree()
        self.commit_all_managed()
        (legacy/'user.mk').write_text('untracked legacy user work\n')
        before = self.managed_snapshot()
        result = self.refresh()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.managed_snapshot(), before)
        self.assertIn('preserve untracked managed input', result.stderr)

    def test_unavailable_exact_sha_preserves_installed_and_legacy_trees(self):
        self.legacy_tree()
        before = self.managed_snapshot()
        result = self.refresh(BIJUX_STD_REF='f' * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.managed_snapshot(), before)
        self.assertIn('no fallback', result.stderr)

    def test_annotated_tag_resolves_to_commit_not_tag_object(self):
        self.git(self.source, '-c', 'tag.gpgSign=false', 'tag', '-a', '-m', 'Published fixture source', 'v1.0.0')
        result = self.refresh(BIJUX_STD_REF='refs/tags/v1.0.0')
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.consumer/'artifacts/bijux-std/source-provenance.json').read_text())
        self.assertEqual(receipt['resolved_sha'], self.sha)
        self.assertEqual(receipt['requested_ref'], 'refs/tags/v1.0.0')

    def test_ambiguous_branch_and_tag_cannot_choose_incidental_source(self):
        self.git(self.source, 'branch', 'documentation')
        self.git(self.source, 'tag', 'documentation')
        before = self.managed_snapshot()
        result = self.refresh(BIJUX_STD_REF='documentation')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.managed_snapshot(), before)
        self.assertIn('ambiguous', result.stderr)

    def test_dry_run_reports_diff_pruned_and_legacy_trees_without_mutation(self):
        self.legacy_tree()
        docs = self.consumer/'.bijux/shared/bijux-docs'
        docs.mkdir()
        (docs/'marker.txt').write_text('previous docs capability\n')
        before = self.managed_snapshot()
        result = self.refresh(BIJUX_STD_UPDATE_DRY_RUN='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.managed_snapshot(), before)
        self.assertIn('-previous bytes', result.stdout)
        self.assertIn('+accepted bytes', result.stdout)
        self.assertIn('Remove unselected managed directory .bijux/shared/bijux-docs', result.stdout)
        self.assertIn('Remove legacy managed directory shared/bijux-makes', result.stdout)

    def test_recovery_snapshot_retains_pruned_capabilities_and_removed_legacy(self):
        self.legacy_tree()
        docs = self.consumer/'.bijux/shared/bijux-docs'
        docs.mkdir()
        (docs/'marker.txt').write_text('previous docs capability\n')
        result = self.refresh()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.consumer/'artifacts/bijux-std/source-provenance.json').read_text())
        recovery = Path(receipt['recovery_directory'])
        self.assertFalse(docs.exists())
        self.assertFalse((self.consumer/'shared/bijux-makes').exists())
        self.assertEqual((recovery/'.bijux/shared/bijux-docs/marker.txt').read_text(),'previous docs capability\n')
        self.assertEqual((recovery/'shared/bijux-makes/marker.txt').read_text(),'legacy bytes\n')
        self.assertEqual((recovery/'shared-dir-sha256.txt').read_text(),'previous manifest\n')

    def test_source_guard_rejects_dirty_checkout_with_unchanged_head(self):
        checkout = self.base / 'fetched'
        self.git(self.base, 'clone', '-q', str(self.source), str(checkout))
        self.git(checkout, 'checkout', '-q', '--detach', self.sha)
        (checkout / 'shared/bijux-makes/marker.txt').write_text('dirty accepted authority\n')
        result = subprocess.run(['bash', str(GUARD), str(checkout), self.sha],
                                env=self.env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('modified or untracked inputs', result.stderr)
        self.assertEqual(self.git(checkout, 'rev-parse', 'HEAD').stdout.strip(), self.sha)

    def test_older_exact_source_remains_valid_after_upstream_branch_moves(self):
        checkout = self.base / 'fetched'
        self.git(self.base, 'clone', '-q', str(self.source), str(checkout))
        self.git(checkout, 'checkout', '-q', '--detach', self.sha)
        (self.source / 'shared/bijux-makes/marker.txt').write_text('successor bytes\n')
        self.git(self.source, 'add', 'shared')
        self.git(self.source, 'commit', '-qm', 'test(std): define successor source')
        result = subprocess.run(['bash', str(GUARD), str(checkout), self.sha],
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('local-verification-only', result.stdout)
        self.assertEqual((checkout / 'shared/bijux-makes/marker.txt').read_text(), 'accepted bytes\n')


if __name__ == '__main__':
    unittest.main()
