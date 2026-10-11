"""Keep custom domain ownership inside the source-qualified render lifecycle."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
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
PUBLICATION = load(ROOT / 'shared/bijux-docs/security/publication.py',
                   'bijux_custom_domain_publication')
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


class NativeDomainAdmission(unittest.TestCase):
    """Exercise real MkDocs configuration and the actual native copied output."""

    def setUp(self):
        CustomDomain.setUp(self)
        self.owner = self.root / 'mkdocs.yml'
        self.owner.write_text('site_name: Hub\nsite_url: https://bijux.io/\n'
                              'docs_dir: docs\nplugins: []\n'
                              'hooks: [configs/docs/publish_site_assets.py]\n')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', 'mkdocs.yml', 'CNAME',
                        'configs/docs/publish_site_assets.py', 'docs'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Bijux',
                        '-c', 'user.email=bijux@example.invalid', 'commit', '-qm',
                        'test source-owned domain'], check=True)
        self.owner_record = {'path': 'mkdocs.yml',
                             'sha256': hashlib.sha256(self.owner.read_bytes()).hexdigest()}
        self.site = Path(self.config.site_dir)
        self.hook.on_post_build(self.config)
        (self.site / 'index.html').write_text(
            '<html><head><link rel="canonical" href="https://bijux.io/"></head><body>Hub</body></html>')

    def manifest(self, *, owner=True):
        return PUBLICATION.bundle_manifest(
            self.root, 'artifacts/site', 'https://bijux.io/', 'a' * 40,
            PUBLICATION.load_policy(), owner_config=self.owner_record if owner else None)

    def test_native_copied_root_domain_has_source_owned_admission(self):
        result = self.manifest()
        copied = next(item for item in result['files'] if item['path'] == 'CNAME')
        self.assertEqual(copied['sha256'], hashlib.sha256(b'bijux.io\n').hexdigest())

    def test_unqualified_inventory_cannot_grant_domain_authority(self):
        with self.assertRaisesRegex(PUBLICATION.AdmissionError, 'unadmitted-extension'):
            self.manifest(owner=False)

    def test_unrelated_extensionless_file_is_refused(self):
        (self.site / 'OTHER').write_text('bijux.io\n')
        with self.assertRaisesRegex(PUBLICATION.AdmissionError, 'unadmitted-extension'):
            self.manifest()

    def test_nested_domain_file_is_refused(self):
        (self.site / 'nested').mkdir()
        (self.site / 'nested/CNAME').write_text('bijux.io\n')
        with self.assertRaisesRegex(PUBLICATION.AdmissionError, 'unadmitted-extension'):
            self.manifest()

    def test_changed_copied_domain_is_refused(self):
        (self.site / 'CNAME').write_text('other.example\n')
        with self.assertRaisesRegex(PUBLICATION.AdmissionError, 'public bytes differ'):
            self.manifest()

    def test_changed_domain_source_is_refused(self):
        (self.root / 'CNAME').write_text('other.example\n')
        with self.assertRaisesRegex(ValueError, 'production URL'):
            self.manifest()

    def test_untracked_domain_source_is_refused(self):
        subprocess.run(['git', '-C', str(self.root), 'rm', '--cached', 'CNAME'], check=True,
                       capture_output=True)
        with self.assertRaises(ValueError):
            self.manifest()

    def test_missing_configured_callback_is_refused(self):
        self.owner.write_text(self.owner.read_text().replace(
            'hooks: [configs/docs/publish_site_assets.py]', 'hooks: []'))
        self.owner_record['sha256'] = hashlib.sha256(self.owner.read_bytes()).hexdigest()
        with self.assertRaisesRegex(PUBLICATION.AdmissionError, 'one reviewed'):
            self.manifest()

    def test_changed_owner_configuration_is_refused(self):
        self.owner.write_text(self.owner.read_text() + '# changed owner\n')
        with self.assertRaisesRegex(PUBLICATION.AdmissionError, 'owner configuration changed'):
            self.manifest()

    def test_modified_callback_cannot_self_admit_domain(self):
        self.path.write_text(self.path.read_text() + '\n# unreviewed producer\n')
        with self.assertRaisesRegex(ValueError, 'reviewed source recipe'):
            self.manifest()



if __name__ == '__main__':
    unittest.main()
