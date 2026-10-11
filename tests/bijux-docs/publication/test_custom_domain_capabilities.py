"""Keep custom domain ownership inside the source-qualified render lifecycle."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import shutil
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[3]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAPABILITIES = load(ROOT / 'shared/bijux-docs/security/producer_capabilities.py',
                    'bijux_custom_domain_capabilities')
FIXTURE = Path(__file__).parent / 'fixtures/custom-domain/configs/docs/publish_site_assets.py'


class CustomDomain(unittest.TestCase):
    def setUp(self):
        directory = ROOT / 'artifacts/qualification/custom-domain-capabilities'
        directory.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=directory)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.path = self.root / 'configs/docs/publish_site_assets.py'
        self.path.parent.mkdir(parents=True)
        shutil.copyfile(FIXTURE, self.path)
        self.assets = self.root / 'docs/assets/site-icons'
        self.assets.mkdir(parents=True)
        for name in CAPABILITIES.ICONS:
            (self.assets / name).write_bytes(('source icon ' + name).encode())
        (self.root / 'CNAME').write_text('bijux.io\n')
        self.hook = load(self.path, 'bijux_custom_domain_hook')
        self.config = types.SimpleNamespace(
            hooks={'custom-domain': self.hook}, docs_dir=str(self.root / 'docs'),
            site_dir=str(self.root / 'artifacts/site'), site_url='https://bijux.io/')

    def capture(self):
        return CAPABILITIES.hooks(self.config, self.root)

    def reject(self):
        with self.assertRaises((ValueError, CAPABILITIES.CapabilityError)):
            self.capture()

    def test_native_outputs_bind_icons_and_exact_domain(self):
        record, = self.capture()
        self.assertEqual(record['recipe'], 'root-icons-and-custom-domain')
        self.hook.on_post_build(self.config)
        self.assertEqual(set(record['outputs']), {*CAPABILITIES.ICONS, 'CNAME'})
        for name, expected in record['outputs'].items():
            self.assertEqual(hashlib.sha256((Path(self.config.site_dir) / name).read_bytes()).hexdigest(), expected)
        self.assertIn({'path': 'CNAME', 'sha256': record['outputs']['CNAME']}, record['inputs'])

    def test_changed_domain_cannot_use_another_site_url(self):
        (self.root / 'CNAME').write_text('other.example\n')
        self.reject()

    def test_domain_bytes_require_exact_newline(self):
        (self.root / 'CNAME').write_text('bijux.io')
        self.reject()

    def test_domain_symlink_is_refused(self):
        (self.root / 'CNAME').unlink()
        (self.root / 'CNAME').symlink_to(FIXTURE)
        self.reject()

    def test_foreign_owner_is_refused(self):
        self.hook.REPO_ROOT = self.root / 'other'
        self.reject()

    def test_replaced_copy_dependency_is_refused(self):
        self.hook.shutil = types.SimpleNamespace(copyfile=lambda *_: None)
        self.reject()

    def test_replaced_callback_is_refused(self):
        self.hook.on_post_build = lambda *_: None
        self.reject()

    def test_modified_source_is_refused(self):
        self.path.write_text(self.path.read_text() + '\n# another callback authority\n')
        self.reject()


if __name__ == '__main__':
    unittest.main()
