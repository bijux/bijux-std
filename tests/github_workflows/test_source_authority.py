from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .policy_fixtures import source_fixture


def committed_fixture(directory):
    root, owned = source_fixture(directory)
    def git(*args):
        result = subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True)
        return result.stdout.strip()
    git('init', '--quiet');git('config', 'user.name', 'Bijux verification')
    git('config', 'user.email', 'verification@example.invalid')
    git('add', '.github', 'shared');git('commit', '--quiet', '-m', 'test(github): establish owned source fixture')
    git('remote', 'add', 'origin', 'https://github.com/bijux/bijux-std.git')
    return root, owned, git('rev-parse', 'HEAD'), git


def tracked_product_pin(target, sha):
    pin = target / '.github/standards/bijux-std.sha'
    pin.parent.mkdir(parents=True, exist_ok=True);pin.write_text(sha+'\n')
    (target / '.gitignore').write_text('artifacts/\n')
    def git(*args):
        return subprocess.run(['git','-C',str(target),*args],check=True,capture_output=True,text=True)
    git('init','--quiet');git('config','user.name','Bijux verification')
    git('config','user.email','verification@example.invalid')
    git('add','.github/standards/bijux-std.sha','.gitignore')
    git('commit','--quiet','-m','test(github): bind tracked product source pin')
    return pin


class WorkflowSourceAuthorityTests(unittest.TestCase):
    def test_explicit_candidate_qualifies_only_owning_standard(self):
        with tempfile.TemporaryDirectory() as workspace:
            root, owned, sha, _ = committed_fixture(workspace)
            actual = owned.admit_source(root, root, 'bijux-std', sha, candidate=True)
            self.assertEqual(actual, {'mode': 'candidate-only', 'sha': sha, 'dirty': False})
            for repository, target in [('bijux-atlas', root), ('bijux-std', root.parent)]:
                with self.subTest(repository=repository), self.assertRaisesRegex(ValueError, 'restricted'):
                    owned.admit_source(root, target, repository, sha, candidate=True)
            path = root / '.github/CODEOWNERS';path.write_bytes(path.read_bytes()+b'\n')
            self.assertTrue(owned.admit_source(root, root, 'bijux-std', sha, candidate=True)['dirty'])

    def test_full_sha_and_explicit_verifier_root_are_mandatory(self):
        with tempfile.TemporaryDirectory() as workspace:
            root, owned, sha, _ = committed_fixture(workspace)
            for invalid in [sha[:12], sha.upper(), 'main', '0'*40]:
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    owned.admit_source(root, root, 'bijux-std', invalid, candidate=True)
            with self.assertRaisesRegex(ValueError, 'source.*own verifier'):
                owned.admit_source(root.parent, root.parent, 'bijux-std', sha, candidate=True)

    def test_accepted_source_refuses_product_checkout_or_incidental_sibling(self):
        with tempfile.TemporaryDirectory() as workspace:
            root, owned, sha, _ = committed_fixture(workspace)
            target = root.parent / 'other-product'
            tracked_product_pin(target, sha)
            for destination in [root, target]:
                with self.subTest(target=destination), self.assertRaisesRegex(ValueError, 'artifacts cache'):
                    owned.admit_source(root, destination, 'bijux-atlas', sha)

    def test_accepted_source_refuses_wrong_origin_dirty_inputs_and_pin(self):
        for variant in ['origin', 'dirty', 'pin', 'untracked']:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as workspace:
                target = Path(workspace) / 'product'
                root, owned, sha, git = committed_fixture(target / 'artifacts/cache')
                pin = tracked_product_pin(target, sha)
                if variant == 'origin':git('remote', 'set-url', 'origin', 'https://example.invalid/bijux-std.git')
                if variant == 'dirty':(root / '.github/CODEOWNERS').write_text('changed')
                if variant == 'untracked':(root / 'untracked-input').write_text('changed')
                if variant == 'pin':pin.write_text('0'*40+'\n')
                with self.assertRaises(ValueError):owned.admit_source(root, target, 'bijux-atlas', sha)

    def test_guard_is_independent_and_local_source_override_cannot_admit_acceptance(self):
        with tempfile.TemporaryDirectory() as workspace:
            target = Path(workspace) / 'product'
            root, owned, sha, _ = committed_fixture(target / 'artifacts/cache')
            pin = tracked_product_pin(target, sha)
            real = subprocess.run;guards=[]
            def execute(command, **kwargs):
                if command[0] == 'bash':
                    guards.append((command, kwargs))
                    return subprocess.CompletedProcess(command, 0, '', '')
                return real(command, **kwargs)
            with mock.patch.dict(os.environ, {'BIJUX_STD_ALLOW_LOCAL_SOURCE':'1', 'BIJUX_STD_GIT_URL':'https://example.invalid/source'}):
                with mock.patch('subprocess.run', side_effect=execute):
                    result = owned.admit_source(root, target, 'bijux-atlas', sha)
            self.assertEqual(result['mode'], 'accepted-GitHub-source')
            self.assertEqual(len(guards), 1)
            command, options = guards[0]
            self.assertEqual(command, ['bash', str(root/'shared/bijux-checks/scripts/verify-accepted-source.sh'), str(root), sha])
            self.assertNotIn('BIJUX_STD_ALLOW_LOCAL_SOURCE', options['env'])
            self.assertEqual(options['env']['BIJUX_STD_GIT_URL'], 'https://github.com/bijux/bijux-std.git')
            # This is a boundary unit with the existing fetch guard mocked, not a GitHub acceptance receipt.

    def test_untracked_pin_and_artifact_alias_cannot_grant_authority(self):
        for variant in ['untracked-pin', 'artifact-alias']:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as workspace:
                target = Path(workspace) / 'product'
                if variant == 'artifact-alias':
                    external = Path(workspace) / 'external-cache';external.mkdir()
                    target.mkdir();(target/'artifacts').symlink_to(external, target_is_directory=True)
                root, owned, sha, _ = committed_fixture(target/'artifacts/cache')
                pin = tracked_product_pin(target, sha)
                if variant == 'untracked-pin':
                    subprocess.run(['git','-C',str(target),'rm','--cached',str(pin.relative_to(target))],check=True,capture_output=True)
                with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                    owned.admit_source(root,target,'bijux-atlas',sha)

    def test_guard_fetch_failure_never_returns_accepted_authority(self):
        with tempfile.TemporaryDirectory() as workspace:
            target = Path(workspace) / 'product'
            root, owned, sha, _ = committed_fixture(target / 'artifacts/cache')
            pin = tracked_product_pin(target, sha)
            real = subprocess.run
            def execute(command, **kwargs):
                if command[0] == 'bash':raise subprocess.CalledProcessError(1, command, stderr='missing exact source')
                return real(command, **kwargs)
            with mock.patch('subprocess.run', side_effect=execute), self.assertRaisesRegex(RuntimeError, 'missing exact source'):
                owned.admit_source(root, target, 'bijux-atlas', sha)


if __name__ == '__main__':
    unittest.main()
