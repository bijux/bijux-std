"""Exercise canonical source selection through real Git object transfers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / 'shared/bijux-checks'
CANONICAL = 'git@gitlab.com:bijux-oss/bijux-std.git'


class GitLabSourceAcquisitionTests(unittest.TestCase):
    def setUp(self):
        owner = ROOT / 'artifacts/tests/source-acquisition'
        owner.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=owner)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.git(self.source, 'init', '-q')
        self.git(self.source, 'config', 'user.email', 'bijux@example.invalid')
        self.git(self.source, 'config', 'user.name', 'Bijux tests')
        for name in ('bijux-checks', 'bijux-gh', 'bijux-makes'):
            tree = self.source / 'shared' / name
            tree.mkdir(parents=True)
            (tree / 'marker.txt').write_text('fetched source bytes\n')
        self.git(self.source, 'add', 'shared')
        self.git(self.source, 'commit', '-qm', 'test(std): define canonical acquisition fixture')
        self.sha = self.git(self.source, 'rev-parse', 'HEAD').stdout.strip()
        self.checkout = self.root / 'checkout'
        self.git(self.root, 'clone', '-q', str(self.source), str(self.checkout))
        self.git(self.checkout, 'remote', 'set-url', 'origin', CANONICAL)
        self.ssh = self.root / 'source-transport.sh'
        self.ssh.write_text('''#!/usr/bin/env bash
set -eu
[[ ( "$*" == *"git@gitlab.com"* && "$*" == *"bijux-oss/bijux-std.git"* ) || ( "$*" == *"git@github.com"* && "$*" == *"bijux/bijux-std.git"* ) ]] || exit 97
printf 'fetch\\n' >> "$BIJUX_TEST_TRANSPORT_LOG"
exec git-upload-pack "$BIJUX_TEST_SOURCE"
''')
        self.ssh.chmod(0o755)
        self.transport_log = self.root / 'transport.log'
        self.env = dict(os.environ, BIJUX_STD_GIT_URL=CANONICAL,
                        BIJUX_STD_ALLOW_LOCAL_SOURCE='0', GIT_SSH_VARIANT='ssh',
                        GIT_SSH_COMMAND=str(self.ssh), BIJUX_TEST_SOURCE=str(self.source),
                        BIJUX_TEST_TRANSPORT_LOG=str(self.transport_log))

    @staticmethod
    def git(root, *arguments):
        return subprocess.run(['git', '-C', str(root), *arguments], check=True,
                              text=True, capture_output=True)

    def guard(self, sha=None, root=None, **environment):
        return subprocess.run(['bash', str(CHECKS / 'scripts/verify-accepted-source.sh'),
                               str(root or self.checkout), sha or self.sha],
                              env=dict(self.env, **environment), capture_output=True, text=True)

    def test_explicit_canonical_gitlab_fetches_exact_object_and_reports_identity(self):
        result = self.guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('GitLab', result.stdout)
        self.assertIn('88948041', result.stdout)
        self.assertEqual(self.git(self.checkout, 'rev-parse', 'FETCH_HEAD^{commit}').stdout.strip(), self.sha)
        self.assertEqual(self.transport_log.read_text(), 'fetch\n')

    def test_unknown_origins_are_refused_before_fetch_even_with_matching_head(self):
        for origin in (
            'https://gitlab.com/bijux/bijux-std.git',
            'git@gitlab.com:bijux/bijux-std.git',
            'https://gitlab.com/bijux-oss/bijux-core.git',
            'https://gitlab.com/bijux-edu/bijux-std.git',
            'https://gitlab.com.example.invalid/bijux-oss/bijux-std.git',
            'https://gitlab.com@another.invalid/bijux-oss/bijux-std.git',
            'https://gitlab.com/bijux-oss/bijux-std.git?canonical=true',
        ):
            with self.subTest(origin=origin):
                self.git(self.checkout, 'remote', 'set-url', 'origin', origin)
                result = self.guard(BIJUX_STD_GIT_URL=origin)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.transport_log.exists())
                self.assertNotIn('Verified', result.stdout)

    def test_canonical_identity_does_not_bypass_wrong_sha_dirty_input_or_nested_root(self):
        wrong = self.guard(sha='f' * 40)
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn('HEAD differs', wrong.stderr)
        self.assertFalse(self.transport_log.exists())
        tracked = self.checkout / 'shared/bijux-makes/marker.txt'
        tracked.write_text('unverified bytes\n')
        dirty = self.guard()
        self.assertNotEqual(dirty.returncode, 0)
        self.assertIn('modified or untracked', dirty.stderr)
        self.assertFalse(self.transport_log.exists())
        tracked.write_text('fetched source bytes\n')
        nested = self.guard(root=tracked.parent)
        self.assertNotEqual(nested.returncode, 0)
        self.assertIn('explicit repository root', nested.stderr)
        self.assertFalse(self.transport_log.exists())

    def test_canonical_url_requires_matching_requested_origin(self):
        result = self.guard(BIJUX_STD_GIT_URL='https://gitlab.com/bijux-oss/bijux-std.git')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('origin differs', result.stderr)
        self.assertFalse(self.transport_log.exists())

    def consumer(self):
        consumer = self.root / 'consumer'
        managed = consumer / '.bijux/shared'
        managed.mkdir(parents=True)
        (managed / 'shared-dir-sha256.txt').write_text('previous manifest\n')
        self.git(consumer, 'init', '-q')
        return consumer

    def refresh(self, consumer, **environment):
        selected = dict(self.env, BIJUX_STD_REF=self.sha, BIJUX_STD_CAPABILITIES='common',
                        BIJUX_STD_CONFIG=str(CHECKS / 'bijux-std-checks.yml'),
                        BIJUX_STD_SELF_REPO_MODE='off')
        selected.update(environment)
        return subprocess.run(['bash', str(CHECKS / 'update-bijux-std.sh')], cwd=consumer,
                              env=selected, text=True, capture_output=True)

    def test_explicit_gitlab_refresh_records_configured_project_without_claiming_acceptance(self):
        consumer = self.consumer()
        result = self.refresh(consumer)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((consumer / 'artifacts/bijux-std/source-provenance.json').read_text())
        self.assertEqual(receipt['source_project'], {
            'host': 'gitlab.com', 'path': 'bijux-oss/bijux-std', 'id': 88948041,
            'identity_basis': 'configured-canonical-origin'})
        self.assertEqual(receipt['resolved_sha'], self.sha)
        self.assertFalse(receipt['verification_only'])
        self.assertNotIn('accepted', receipt)
        self.assertEqual((consumer / '.bijux/shared/bijux-makes/marker.txt').read_text(), 'fetched source bytes\n')

    def test_explicit_local_verification_retains_its_label_with_canonical_origin(self):
        consumer = self.consumer()
        result = self.refresh(consumer, BIJUX_STD_ALLOW_LOCAL_SOURCE='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((consumer / 'artifacts/bijux-std/source-provenance.json').read_text())
        self.assertTrue(receipt['verification_only'])
        self.assertIn('local-verification-only', result.stdout)

    def test_unavailable_gitlab_sha_refuses_without_fallback_or_managed_changes(self):
        consumer = self.consumer()
        original = (consumer / '.bijux/shared/shared-dir-sha256.txt').read_bytes()
        result = self.refresh(consumer, BIJUX_STD_REF='f' * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no fallback', result.stderr)
        self.assertEqual((consumer / '.bijux/shared/shared-dir-sha256.txt').read_bytes(), original)
        self.assertFalse((consumer / 'artifacts/bijux-std/source-provenance.json').exists())

    def test_gitlab_transports_are_admitted_only_as_exact_canonical_urls(self):
        for origin in (
            'https://gitlab.com/bijux-oss/bijux-std',
            'https://gitlab.com/bijux-oss/bijux-std.git',
            'git@gitlab.com:bijux-oss/bijux-std',
            'git@gitlab.com:bijux-oss/bijux-std.git',
            'ssh://git@gitlab.com/bijux-oss/bijux-std.git',
            'ssh://git@gitlab.com:22/bijux-oss/bijux-std.git',
        ):
            with self.subTest(origin=origin):
                self.git(self.checkout, 'remote', 'set-url', 'origin', origin)
                result = self.guard(sha='f' * 40, BIJUX_STD_GIT_URL=origin)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('HEAD differs', result.stderr)
                self.assertFalse(self.transport_log.exists())

    def test_github_ssh_keeps_legacy_exact_fetch_behavior(self):
        origin = 'git@github.com:bijux/bijux-std.git'
        self.git(self.checkout, 'remote', 'set-url', 'origin', origin)
        result = self.guard(BIJUX_STD_GIT_URL=origin)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Verified GitHub source', result.stdout)
        self.assertNotIn('GitLab', result.stdout)
        self.assertEqual(self.transport_log.read_text(), 'fetch\n')

    def test_gitlab_origin_requires_explicit_opt_in(self):
        environment = dict(self.env)
        environment.pop('BIJUX_STD_GIT_URL')
        result = subprocess.run(['bash', str(CHECKS / 'scripts/verify-accepted-source.sh'),
                                 str(self.checkout), self.sha], env=environment,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('origin differs', result.stderr)
        self.assertFalse(self.transport_log.exists())

    def test_updater_refuses_personal_mirror_before_fetch_or_managed_mutation(self):
        consumer = self.consumer()
        result = self.refresh(consumer, BIJUX_STD_GIT_URL='git@gitlab.com:bijux/bijux-std.git')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.transport_log.exists())
        self.assertEqual((consumer / '.bijux/shared/shared-dir-sha256.txt').read_text(), 'previous manifest\n')

    def test_clean_candidate_commit_is_not_verified_until_canonical_remote_supplies_object(self):
        self.git(self.checkout, 'config', 'user.email', 'bijux@example.invalid')
        self.git(self.checkout, 'config', 'user.name', 'Bijux tests')
        (self.checkout / 'shared/bijux-makes/marker.txt').write_text('candidate-only bytes\n')
        self.git(self.checkout, 'add', 'shared')
        self.git(self.checkout, 'commit', '-qm', 'test(std): define unpublished source candidate')
        candidate = self.git(self.checkout, 'rev-parse', 'HEAD').stdout.strip()
        result = self.guard(sha=candidate)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Verified', result.stdout)
        self.assertEqual(self.git(self.checkout, 'rev-parse', 'HEAD').stdout.strip(), candidate)
        self.assertEqual(self.git(self.checkout, 'status', '--porcelain').stdout, '')
        self.assertEqual(self.transport_log.read_text(), 'fetch\n')
