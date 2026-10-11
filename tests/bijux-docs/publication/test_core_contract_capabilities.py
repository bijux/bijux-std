"""Bind Core's actual callbacks to finite contracts and confined source links."""
from __future__ import annotations
import hashlib
import importlib.util
import json
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

CAPABILITIES = load(ROOT/'shared/bijux-docs/security/producer_capabilities.py', 'bijux_core_contract_capabilities')
FIXTURE = Path(__file__).parent/'fixtures/core-contracts/docs/automation/publish_contract_assets.py'

class Configuration(dict):
    __getattr__ = dict.__getitem__

class CoreContracts(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT/'artifacts/qualification/core-contract-capabilities'
        artifacts.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.path = self.root/'docs/automation/publish_contract_assets.py'
        self.path.parent.mkdir(parents=True)
        shutil.copyfile(FIXTURE, self.path)
        for index, name in enumerate(CAPABILITIES.CORE_CONTRACT_ASSETS):
            path = self.root/'contracts'/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'owned_contract': index})+'\n')
        (self.root/'docs/spec').mkdir()
        (self.root/'docs/spec/contract.md').write_text('# Owned contract\n')
        self.hook = load(self.path, 'bijux_reviewed_core_contracts')
        self.config = Configuration(hooks={'contracts': self.hook}, docs_dir=str(self.root/'docs'),
                                    site_dir=str(self.root/'artifacts/site'),
                                    repo_url='https://github.com/bijux/bijux-core',
                                    nav=[{'Home': 'index.md'}, {'Guide': 'guide.md'}])

    def capture(self, publication=False):
        return CAPABILITIES.hooks(self.config, self.root, publication=publication)

    def reject(self):
        with self.assertRaises((ValueError, CAPABILITIES.CapabilityError)):
            self.capture()

    def test_native_callback_copies_exactly_five_bound_contracts(self):
        record, = self.capture()
        self.assertEqual(record['recipe'], 'core-contract-assets')
        self.hook.on_post_build(self.config)
        self.assertEqual(set(record['outputs']), {'contracts/'+name for name in CAPABILITIES.CORE_CONTRACT_ASSETS})
        self.assertEqual({row['path']: row['sha256'] for row in record['inputs']}, record['outputs'])
        CAPABILITIES.verify_outputs(Path(self.config.site_dir), {'hooks': [record]})

    def test_native_source_links_preserve_navigation_and_owned_source_identity(self):
        self.capture()
        page = types.SimpleNamespace(file=types.SimpleNamespace(src_uri='index.md'))
        rendered = self.hook.on_page_markdown('[Owned](spec/contract.md#shape) [Guide](guide.md) <a href="guide.md">Guide</a>', page, self.config)
        self.assertIn('https://github.com/bijux/bijux-core/blob/main/docs/spec/contract.md#shape', rendered)
        self.assertIn('[Guide](guide.md)', rendered)
        self.assertIn('href="guide/"', rendered)

    def test_changed_public_output_cannot_inherit_contract_capture(self):
        record, = self.capture()
        self.hook.on_post_build(self.config)
        target = Path(self.config.site_dir)/next(iter(record['outputs']))
        target.write_text('{}\n')
        with self.assertRaises(CAPABILITIES.CapabilityError):
            CAPABILITIES.verify_outputs(Path(self.config.site_dir), {'hooks': [record]})

    def test_contract_source_moving_after_capture_invalidates_outputs(self):
        record, = self.capture()
        (self.root/'contracts'/CAPABILITIES.CORE_CONTRACT_ASSETS[0]).write_text('{"changed": true}\n')
        self.hook.on_post_build(self.config)
        with self.assertRaises(CAPABILITIES.CapabilityError):
            CAPABILITIES.verify_outputs(Path(self.config.site_dir), {'hooks': [record]})

    def test_extra_contract_cannot_escape_the_finite_population(self):
        self.hook.CONTRACT_ASSETS.append('../outside.json')
        self.reject()

    def test_missing_contract_is_refused(self):
        (self.root/'contracts'/CAPABILITIES.CORE_CONTRACT_ASSETS[0]).unlink()
        self.reject()

    def test_contract_symlink_is_refused(self):
        path = self.root/'contracts'/CAPABILITIES.CORE_CONTRACT_ASSETS[0]
        path.unlink()
        path.symlink_to(self.root/'contracts'/CAPABILITIES.CORE_CONTRACT_ASSETS[1])
        self.reject()

    def test_invalid_json_contract_is_refused(self):
        (self.root/'contracts'/CAPABILITIES.CORE_CONTRACT_ASSETS[0]).write_text('not JSON')
        self.reject()

    def test_foreign_repository_cannot_use_core_source_links(self):
        self.config['repo_url'] = 'https://github.com/foreign/core'
        self.reject()

    def test_replaced_copy_dependency_is_refused(self):
        self.hook.shutil = types.SimpleNamespace(copy2=lambda *_: None)
        self.reject()

    def test_replaced_source_link_helper_is_refused(self):
        self.hook._source_target = lambda *_: ('../../outside.md', '')
        self.reject()

    def test_changed_callback_source_is_refused(self):
        self.path.write_text(self.path.read_text()+'\n# altered producer source\n')
        self.reject()

    def test_untracked_contract_cannot_enter_publication(self):
        subprocess.run(['git', 'init', '--quiet', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', 'docs/automation/publish_contract_assets.py'], check=True)
        with self.assertRaises(subprocess.CalledProcessError):
            self.capture(publication=True)
        subprocess.run(['git', '-C', str(self.root), 'add', 'contracts'], check=True)
        self.assertEqual(len(self.capture(publication=True)), 1)

if __name__ == '__main__':
    unittest.main()
