"""Native render dates require actual committed-source clock authority."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('bijux_render_clock', ROOT / 'shared/bijux-docs/security/build_identity.py')
IDENTITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IDENTITY)


class CommittedRenderClockTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'artifacts/render-clock-controls'
        parent.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / 'document.md').write_text('# Clock owner\n')
        subprocess.run(['git', '-C', str(self.root), 'add', 'document.md'], check=True)
        env = os.environ | {'GIT_AUTHOR_DATE': '2026-10-11T22:43:14Z', 'GIT_COMMITTER_DATE': '2026-10-11T22:43:14Z'}
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                        'commit', '-qm', 'owned render input'], env=env, check=True)
        self.sha = IDENTITY.git(self.root, 'rev-parse', 'HEAD')

    def test_epoch_comes_from_actual_selected_commit_not_ambient_clock(self):
        expected = {'source_sha': self.sha, 'seconds': 1791758594}
        with mock.patch.dict(os.environ, {'SOURCE_DATE_EPOCH': '1791763200'}):
            self.assertEqual(IDENTITY.source_render_epoch(self.root, self.sha), expected)
            with self.assertRaisesRegex(ValueError, 'ambient SOURCE_DATE_EPOCH'):
                with IDENTITY.publication_clock(self.root, self.sha):
                    self.fail('unbound clock reached renderer')

    def test_repeated_invocations_preserve_epoch_and_restore_environment(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            for invocation in range(2):
                with self.subTest(invocation=invocation), IDENTITY.publication_clock(self.root, self.sha) as epoch:
                    self.assertEqual(epoch['seconds'], 1791758594)
                    self.assertEqual(os.environ['SOURCE_DATE_EPOCH'], '1791758594')
                self.assertNotIn('SOURCE_DATE_EPOCH', os.environ)

    def test_render_exception_restores_absent_or_matching_environment(self):
        for previous in (None, '1791758594'):
            with mock.patch.dict(os.environ, {}, clear=True):
                if previous is not None:
                    os.environ['SOURCE_DATE_EPOCH'] = previous
                with self.assertRaisesRegex(RuntimeError, 'renderer failed'):
                    with IDENTITY.publication_clock(self.root, self.sha):
                        raise RuntimeError('renderer failed')
                self.assertEqual(os.environ.get('SOURCE_DATE_EPOCH'), previous)

    def test_native_clock_mutation_is_refused_and_environment_restored(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'changed the committed epoch'):
                with IDENTITY.publication_clock(self.root, self.sha):
                    os.environ['SOURCE_DATE_EPOCH'] = '1791763200'
            self.assertNotIn('SOURCE_DATE_EPOCH', os.environ)

    def test_another_revision_cannot_select_its_timestamp(self):
        with self.assertRaisesRegex(ValueError, 'differs from HEAD'):
            IDENTITY.source_render_epoch(self.root, '0' * 40)
        with self.assertRaisesRegex(ValueError, 'exact source SHA'):
            IDENTITY.source_render_epoch(self.root, 'HEAD')

    def test_epoch_receipt_requires_the_exact_native_integer_schema(self):
        expected = IDENTITY.source_render_epoch(self.root, self.sha)
        for malformed in (None, {}, expected | {'seconds': float(expected['seconds'])},
                          expected | {'seconds': True}, expected | {'ambient': True}):
            with self.subTest(malformed=malformed):
                self.assertFalse(IDENTITY.render_epoch_matches(malformed, expected))
        self.assertTrue(IDENTITY.render_epoch_matches(expected, expected))


if __name__ == '__main__':
    unittest.main()
