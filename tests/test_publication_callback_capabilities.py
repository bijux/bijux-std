"""Reject replaced, foreign and shadowed registered renderer callbacks."""
import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('bijux_callback_capabilities',ROOT/'shared/bijux-docs/security/producer_capabilities.py')
capabilities=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(capabilities)


class RegisteredCallbacks(unittest.TestCase):
    def setUp(self):
        artifact=ROOT/'artifacts/website-security/callback-tests';artifact.mkdir(parents=True,exist_ok=True)
        self.scratch=tempfile.TemporaryDirectory(dir=artifact);self.addCleanup(self.scratch.cleanup)
        self.root=Path(self.scratch.name);self.installed=self.root/'installed';self.installed.mkdir()
        self.source=self.installed/'owned_plugin.py'
        self.source.write_text('class Plugin:\n    def on_page_content(self, value, **kwargs):\n        return value\n')
        spec=importlib.util.spec_from_file_location('owned_plugin',self.source);self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.plugin=self.module.Plugin();self.plugins=types.SimpleNamespace(values=lambda:[self.plugin],events={'page_content':[self.plugin.on_page_content]})
        self.config=types.SimpleNamespace(hooks={},plugins=self.plugins)
        mock=patch.object(capabilities.sysconfig,'get_path',return_value=str(self.installed));mock.start();self.addCleanup(mock.stop)
    def records(self):return capabilities.callback_records(self.config,self.root/'owner')
    def test_actual_bound_method_matches_loaded_owned_source(self):
        records=self.records();self.assertEqual(len(records),1);self.assertEqual(records[0]['class'],'installed-profile');self.assertEqual(records[0]['function'],'Plugin.on_page_content')
    def test_mutated_registered_method_rejected(self):
        replacement=compile('def altered(self, value, **kwargs):\n    return "forged"\n',str(self.source),'exec');namespace={};exec(replacement,namespace)
        self.plugins.events['page_content']=[types.MethodType(namespace['altered'],self.plugin)]
        self.assertRaises(capabilities.CapabilityError,self.records)
    def test_changed_callback_source_rejected(self):
        self.source.write_text(self.source.read_text().replace('return value','return "changed"'));self.assertRaises(capabilities.CapabilityError,self.records)
    def test_foreign_method_owner_rejected(self):
        self.plugins.events['page_content']=[self.module.Plugin().on_page_content];self.assertRaises(capabilities.CapabilityError,self.records)
    def test_unregistered_plain_function_rejected(self):
        self.plugins.events['page_content']=[self.module.Plugin.on_page_content];self.assertRaises(capabilities.CapabilityError,self.records)
    def test_native_or_opaque_callback_rejected(self):
        self.plugins.events['page_content']=[len];self.assertRaises(capabilities.CapabilityError,self.records)
    def test_missing_source_rejected(self):
        self.source.unlink();self.assertRaises(capabilities.CapabilityError,self.records)
    def test_symlink_source_rejected(self):
        real=self.source.with_name('different.py');self.source.rename(real);self.source.symlink_to(real);self.assertRaises(capabilities.CapabilityError,self.records)
    def test_registered_callback_order_is_part_of_identity(self):
        self.plugins.events['page_content']=[self.plugin.on_page_content,self.plugin.on_page_content]
        self.assertEqual([record['index'] for record in self.records()],[0,1])


if __name__=='__main__':unittest.main()
