"""Deletion authority requires exact committed bytes and no remaining workflow caller."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from .policy_fixtures import MODULE, ROOT

OWNER = MODULE.retired_package_workflows


class RetiredPackageWorkflowTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'artifacts').mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=ROOT / 'artifacts')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'verification@bijux.io')
        self.git('config', 'user.name', 'Bijux verification')
        self.paths = sorted(OWNER.ATLAS_PACKAGE_PREIMAGES)
        self.preimages = {}
        for relative in self.paths:
            body = ('name: ' + Path(relative).stem + '\njobs: {}\n').encode()
            self.write(relative, body)
            self.preimages[relative] = hashlib.sha256(body).hexdigest()
        self.write('README.md', b'authored repository documentation\n')
        self.commit()
        replacement = patch.object(OWNER, 'ATLAS_PACKAGE_PREIMAGES', self.preimages)
        replacement.start()
        self.addCleanup(replacement.stop)

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, stderr=subprocess.PIPE)

    def write(self, relative, body):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    def commit(self):
        self.git('add', 'README.md', '.github')
        self.git('commit', '-qm', 'test(github): retain package workflow preimages')

    def plan(self):
        return OWNER.plan_retirement(self.root, 'bijux-atlas')

    def test_exact_unused_committed_pair_retires_and_authored_content_survives(self):
        self.write('.github/workflows/owned.yml', b'jobs: {check: {steps: [{run: echo ordinary}]}}\n')
        plan = self.plan()
        OWNER.apply_retirement(self.root, 'bijux-atlas', plan)
        self.assertEqual(self.plan(), {})
        self.assertEqual((self.root / 'README.md').read_bytes(), b'authored repository documentation\n')
        self.assertTrue((self.root / '.github/workflows/owned.yml').is_file())

    def test_unselected_repository_preserves_every_preimage(self):
        self.assertEqual(OWNER.plan_retirement(self.root, 'bijux-core'), {})
        OWNER.apply_retirement(self.root, 'bijux-core', {})
        self.assertTrue(all((self.root / p).is_file() for p in self.paths))

    def test_changed_committed_and_uncommitted_bytes_refuse(self):
        path = self.root / self.paths[0]
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'differs from admitted preimage'):
            self.plan()
        self.commit()
        with self.assertRaisesRegex(ValueError, 'differs from admitted preimage'):
            self.plan()

    def test_untracked_matching_bytes_do_not_gain_deletion_authority(self):
        original = (self.root / self.paths[0]).read_bytes()
        self.git('rm', self.paths[0])
        self.git('commit', '-qm', 'test(github): remove tracked package workflow')
        self.write(self.paths[0], original)
        with self.assertRaisesRegex(ValueError, 'committed and unchanged'):
            self.plan()

    def test_staged_removal_with_restored_worktree_refuses(self):
        original = (self.root / self.paths[0]).read_bytes()
        self.git('rm', self.paths[0])
        self.write(self.paths[0], original)
        with self.assertRaisesRegex(ValueError, 'staged changes'):
            self.plan()

    def test_same_byte_symlink_cannot_substitute_for_owned_workflow(self):
        path = self.root / self.paths[0]
        self.write('external.yml', path.read_bytes())
        path.unlink()
        path.symlink_to(self.root / 'external.yml')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.plan()

    def test_actual_local_remote_quoted_and_step_callers_refuse(self):
        for reference in ['./' + self.paths[0],
                          'bijux/bijux-atlas/' + self.paths[1] + '@' + 'a' * 40]:
            for owner in ['job', 'step']:
                with self.subTest(reference=reference, owner=owner):
                    uses = 'uses: "' + reference + '"'
                    job = '{' + uses + '}' if owner == 'job' else '{steps: [{' + uses + '}]}'
                    self.write('.github/workflows/caller.yaml', ('jobs: {check: ' + job + '}\n').encode())
                    with self.assertRaisesRegex(ValueError, 'still has a caller'):
                        self.plan()
        self.assertTrue(all((self.root / p).is_file() for p in self.paths))

    def test_second_preimage_change_refuses_before_deleting_first(self):
        plan = self.plan()
        path = self.root / self.paths[1]
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaises(ValueError):
            OWNER.apply_retirement(self.root, 'bijux-atlas', plan)
        self.assertTrue(all((self.root / p).is_file() for p in self.paths))

    def test_new_caller_between_admission_and_deletion_refuses(self):
        plan = self.plan()
        self.write('.github/workflows/caller.yml',
                   ('jobs: {check: {uses: "./' + self.paths[0] + '"}}\n').encode())
        with self.assertRaisesRegex(ValueError, 'still has a caller'):
            OWNER.apply_retirement(self.root, 'bijux-atlas', plan)
        self.assertTrue(all((self.root / p).is_file() for p in self.paths))

    def test_missing_or_malformed_admission_cannot_delete_remaining_files(self):
        plan = self.plan()
        for bad in [{}, {self.paths[0]: '0' * 64}]:
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'changed during projection'):
                OWNER.apply_retirement(self.root, 'bijux-atlas', bad)
        (self.root / self.paths[1]).unlink()
        with self.assertRaisesRegex(ValueError, 'changed during projection'):
            OWNER.apply_retirement(self.root, 'bijux-atlas', plan)
        self.assertTrue((self.root / self.paths[0]).is_file())
