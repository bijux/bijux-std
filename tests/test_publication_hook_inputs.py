"""Bind declared publication callback inputs to physical committed Git bytes."""
from pathlib import Path
import importlib.util
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('bijux_hook_source_authority', ROOT / 'shared/bijux-docs/security/producer_authority.py')
authority = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(authority)


class CommittedHookInputs(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT / 'artifacts/qualification/publication-hook-inputs'
        artifacts.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.git('init', '-q')
        (self.root / '.gitignore').write_text('artifacts/\ndocs/assets/\n')
        (self.root / 'docs/hooks').mkdir(parents=True)
        (self.root / 'docs/hooks/site_assets.py').write_text('def on_post_build(config):\n    return None\n')
        (self.root / 'reader-docs').mkdir()
        (self.root / 'reader-docs/index.md').write_text('# Reader source\n')
        (self.root / 'owned-assets').mkdir()
        (self.root / 'owned-assets/icon.png').write_bytes(b'committed icon bytes')
        self.git('add', '.gitignore', 'docs/hooks/site_assets.py', 'reader-docs/index.md', 'owned-assets/icon.png')
        self.git('-c', 'user.name=Bijux', '-c', 'user.email=tests@bijux.invalid', 'commit', '-qm', 'test: define callback source ownership')
        self.inputs = authority.files(self.root, source=True, publication_source=True)
        self.hook = {
            'source': 'docs/hooks/site_assets.py',
            'source_sha256': authority.digest(self.inputs['docs/hooks/site_assets.py']),
            'inputs': [{'path': 'owned-assets/icon.png', 'sha256': authority.digest(self.inputs['owned-assets/icon.png'])}],
        }

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True)

    def verify(self, *, publication=True):
        return authority.require_committed_hook_inputs({'hooks': [self.hook]}, self.inputs, publication=publication)

    def test_clean_committed_hook_source_and_input_are_accepted(self):
        self.assertIsNone(self.verify())

    def test_ignored_fallback_input_is_rejected_despite_clean_git_status(self):
        assets = self.root / 'docs/assets'
        assets.mkdir()
        (assets / 'owner-extra.js').write_bytes(b'ignored executable source')
        self.assertEqual(self.git('status', '--porcelain').strip(), '')
        self.inputs = authority.files(self.root, source=True, publication_source=True)
        self.hook['inputs'] = [{'path': 'docs/assets/owner-extra.js', 'sha256': authority.digest((assets / 'owner-extra.js').read_bytes())}]
        with self.assertRaisesRegex(authority.ProducerError, 'not committed source: docs/assets/owner-extra.js'):
            self.verify()

    def test_missing_hook_source_is_rejected(self):
        self.hook['source'] = 'docs/hooks/unowned.py'
        with self.assertRaisesRegex(authority.ProducerError, 'not committed source: docs/hooks/unowned.py'):
            self.verify()

    def test_hook_source_digest_must_match_captured_committed_bytes(self):
        self.hook['source_sha256'] = '0' * 64
        with self.assertRaisesRegex(authority.ProducerError, 'digest differs.*docs/hooks/site_assets.py'):
            self.verify()

    def test_asset_digest_must_match_captured_committed_bytes(self):
        self.hook['inputs'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(authority.ProducerError, 'digest differs.*owned-assets/icon.png'):
            self.verify()

    def test_noncanonical_declared_paths_cannot_alias_committed_inputs(self):
        for path in ('../owned-assets/icon.png', '/owned-assets/icon.png', './owned-assets/icon.png'):
            with self.subTest(path=path):
                self.hook['inputs'][0]['path'] = path
                with self.assertRaisesRegex(authority.ProducerError, 'not committed source'):
                    self.verify()

    def test_empty_hook_set_requires_no_extra_owner_input(self):
        self.assertIsNone(authority.require_committed_hook_inputs({'hooks': []}, self.inputs, publication=True))

    def test_verification_fixture_keeps_existing_uncommitted_input_behavior(self):
        self.hook['source'] = 'fixture/hook.py'
        self.hook['inputs'][0]['path'] = 'fixture/untracked.png'
        self.assertIsNone(self.verify(publication=False))


if __name__ == '__main__':
    unittest.main(verbosity=2)
