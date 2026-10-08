"""Adversarial physical/runtime and source-owned profile admission cases."""
import importlib.util
import json
import marshal
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('bijux_profiles_test',ROOT/'shared/bijux-docs/security/renderer_profiles.py')
profiles=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(profiles)


REAL_SNAPSHOT=profiles.environment_snapshot
REAL_ORIGINS=profiles.origins


class ProfileTests(unittest.TestCase):
    def setUp(self):
        # Explicit cache fixtures stay beside their owned source under artifacts.
        cache_prefix = patch.object(profiles.sys, "pycache_prefix", None)
        cache_prefix.start(); self.addCleanup(cache_prefix.stop)
        artifact=ROOT/'artifacts/website-security/renderer-profile-tests';artifact.mkdir(parents=True,exist_ok=True)
        self.scratch=tempfile.TemporaryDirectory(dir=artifact);self.root=Path(self.scratch.name)
        self.shared=self.root/'shared';(self.shared/'security').mkdir(parents=True)
        self.table=self.shared/'security/renderer-producer-admission.json'
        self.actual={'startup_inputs':[],'platform':{'python':'owned'}}
        self.rows=[{'id':'owned','usage':'verification-only','environment':self.actual}]
        self.write()
        self.snapshot=patch.object(profiles,'environment_snapshot',return_value=self.actual);self.snapshot.start()
        self.origins=patch.object(profiles,'origins');self.origins.start()
    def tearDown(self):
        self.origins.stop();self.snapshot.stop();self.scratch.cleanup()
    def write(self,schema=2):self.table.write_text(json.dumps({'schema':schema,'profiles':self.rows}))
    def select(self,publication=False):return profiles.select(self.shared,self.root,publication=publication)
    def rejected(self,publication=False):
        with self.assertRaises(profiles.ProfileError):self.select(publication)
    def external(self):
        path=self.root/'outside/sitecustomize.py';path.parent.mkdir();path.write_text('reviewed')
        self.actual['startup_inputs']=[{'path':'stdlib/sitecustomize.py','sha256':profiles.DISTRO_STARTUP_SHA256,
                                       'resolved_target':str(path),'source':'exact observed source'}]
        self.rows[0]['external_startup_review']={'stdlib/sitecustomize.py':{
            'sha256':profiles.DISTRO_STARTUP_SHA256,'resolved_target':str(path),
            'recipe':'distro-apport-import-unavailable','purpose':'Reviewed distro import is absent; interpreter exception hook remains default.'}}
        module=types.ModuleType('sitecustomize');module.__file__=str(path)
        self.module_patch=patch.dict(sys.modules,{'sitecustomize':module});self.module_patch.start();self.addCleanup(self.module_patch.stop)
        self.write();return module
    def test_reviewed_external_distro_startup_retains_verification_scope(self):
        self.external();self.assertEqual(self.select()['usage'],'verification-only');self.rejected(True)
    def test_unreviewed_external_startup_requires_owned_mitigation(self):
        self.external();self.rows[0].pop('external_startup_review');self.write();self.rejected()
    def test_changed_external_startup_source_or_target_is_rejected(self):
        self.external();self.actual['startup_inputs'][0]['sha256']='changed';self.rejected()
    def test_unqualified_exception_callback_is_rejected(self):
        self.external()
        with patch.object(sys,'excepthook',lambda *args:None):self.rejected()
    def test_changed_default_hook_pointer_cannot_authorize_python_callback(self):
        self.external();callback=lambda *args:None
        with patch.object(sys,'excepthook',callback), patch.object(sys,'__excepthook__',callback):self.rejected()
    def test_loaded_apport_import_cannot_be_admitted_by_absent_import_recipe(self):
        self.external()
        with patch.dict(sys.modules,{'apport_python_hook':types.ModuleType('apport_python_hook')}):self.rejected()
    def test_reviewed_external_target_path_changes_are_rejected(self):
        self.external();self.rows[0]['external_startup_review']['stdlib/sitecustomize.py']['resolved_target']='different';self.write();self.rejected()
    def test_unreviewed_external_source_recipe_is_rejected(self):
        self.external();self.rows[0]['external_startup_review']['stdlib/sitecustomize.py']['recipe']='accept-any-import';self.write();self.rejected()

    def test_module_name_alone_cannot_open_an_external_publication_origin(self):
        module=types.ModuleType('sitecustomize');module.__file__=str(self.root.parent/'unowned/sitecustomize.py')
        with patch.object(profiles.sys,'path',[str(self.root)]), patch.dict(profiles.sys.modules,{'sitecustomize':module},clear=True):
            with self.assertRaisesRegex(profiles.ProfileError,'loaded module outside reviewed'):
                REAL_ORIGINS(self.root,self.shared,publication=True)

    def test_external_startup_namespace_shadow_is_rejected(self):
        module=self.external();module.__file__=str(self.root/'different.py');self.rejected()

    def test_actual_local_candidate_passes(self):self.assertEqual(self.select()['usage'],'verification-only')
    def test_observation_cannot_authorize_publication(self):self.rejected(True)
    def test_unknown_environment_fails(self):self.actual['platform']['python']='unreviewed';self.rejected()
    def test_duplicate_ids_fail(self):self.rows.append(self.rows[0]);self.write();self.rejected()
    def test_duplicate_matching_environment_fails(self):self.rows.append({**self.rows[0],'id':'other'});self.write();self.rejected()
    def test_unbounded_table_fails(self):self.rows=[{**self.rows[0],'id':str(i)} for i in range(33)];self.write();self.rejected()
    def test_declared_schema_cannot_authorize(self):self.write(schema=1);self.rejected()
    def test_missing_table_fails(self):self.table.unlink();self.rejected()
    def test_symlink_table_fails(self):other=self.root/'table';self.table.rename(other);self.table.symlink_to(other);self.rejected()
    def test_unknown_usage_fails(self):self.rows[0]['usage']='approved-observation';self.write();self.rejected()
    def test_reviewed_source_table_permits_exact_publication(self):self.rows[0]['usage']='publication';self.write();self.assertEqual(self.select(True)['usage'],'publication')
    def startup(self):
        self.actual['startup_inputs']=[{'path':'legitimate.pth','sha256':'owned','source':'import legitimate'}]
        self.rows[0]['usage']='publication';self.rows[0]['environment']=self.actual;self.write()
    def test_unreviewed_startup_fails(self):self.startup();self.rejected(True)
    def test_matching_startup_review_passes(self):self.startup();self.rows[0]['startup_review']={'legitimate.pth':{'sha256':'owned','purpose':'Reviewed runtime startup behavior'}};self.write();self.assertEqual(self.select(True)['usage'],'publication')
    def test_forged_startup_hash_fails(self):self.startup();self.rows[0]['startup_review']={'legitimate.pth':{'sha256':'forged','purpose':'Reviewed runtime startup behavior'}};self.write();self.rejected(True)
    def test_extra_startup_permission_fails(self):self.rows[0]['usage']='publication';self.rows[0]['startup_review']={'other.pth':{}};self.write();self.rejected(True)
    def test_table_race_fails(self):
        profiles.origins.side_effect=lambda *a,**k:self.table.write_text('{}')
        self.rejected()
    def test_profile_changed_after_selection_fails(self):
        selected=self.select();self.rows[0]['usage']='publication';self.write()
        with self.assertRaises(profiles.ProfileError):profiles.unchanged(self.shared,self.root,selected)
    def test_known_namespace_shadow_fails(self):
        self.origins.stop()
        fake=types.ModuleType('mkdocs');fake.__file__=str(self.root/'mkdocs.py')
        owner=types.SimpleNamespace(files=[Path('owned.py')], locate_file=lambda name:self.root/'installed'/name)
        with patch.dict(sys.modules,{'mkdocs':fake}),patch.object(profiles.metadata,'packages_distributions',return_value={'mkdocs':['mkdocs']}),patch.object(profiles.metadata,'distribution',return_value=owner):
            with self.assertRaises(profiles.ProfileError):profiles.origins(self.root,self.shared,publication=False)
        self.origins.start()
    def test_stdlib_namespace_shadow_fails(self):
        self.origins.stop();fake=types.ModuleType('json');fake.__file__=str(self.root/'json.py')
        with patch.dict(sys.modules,{'json':fake}),patch.object(profiles.metadata,'packages_distributions',return_value={}):
            with self.assertRaises(profiles.ProfileError):profiles.origins(self.root,self.shared,publication=False)
        self.origins.start()
    def test_physical_directory_symlink_fails(self):
        (self.root/'other').mkdir();(self.root/'link').symlink_to(self.root/'other',target_is_directory=True)
        with self.assertRaises(profiles.ProfileError):profiles.physical_files(self.root)
    def test_physical_file_symlink_fails(self):
        (self.root/'a.py').write_text('x=1');(self.root/'b.py').symlink_to(self.root/'a.py')
        with self.assertRaises(profiles.ProfileError):profiles.physical_files(self.root)
    def test_legitimate_source_fixture_under_cache_directory_retained(self):
        (self.root/'__pycache__').mkdir();(self.root/'__pycache__/example.py').write_text('x=1')
        self.assertIn('__pycache__/example.py',{item['path'] for item in profiles.physical_files(self.root)})
    def installed_snapshot(self,extra=None,missing=False):
        installed=self.root/'site-packages';installed.mkdir();stdlib=self.root/'stdlib';stdlib.mkdir()
        (stdlib/'owned.py').write_text('value=1')
        (installed/'owned.py').write_text('value=1')
        if missing:(installed/'owned.py').unlink()
        if extra:(installed/extra).write_text('import unreviewed')
        distribution=types.SimpleNamespace(metadata={'Name':'owned'},version='1',files=[Path('owned.py')],locate_file=lambda name:installed/str(name))
        with patch.object(profiles.metadata,'distributions',return_value=[distribution]),patch.object(profiles.sysconfig,'get_path',side_effect=lambda key:str(stdlib if key=='stdlib' else installed)),patch.object(profiles.sys,'prefix',str(self.root)):
            return REAL_SNAPSHOT()
    def test_exact_physical_distribution_source_passes(self):self.assertEqual(self.installed_snapshot()['physical_roots'][0]['files_count'],1)
    def test_unlisted_importable_source_fails(self):self.assertRaises(profiles.ProfileError,self.installed_snapshot,'unknown.py')
    def test_unlisted_startup_pth_fails(self):self.assertRaises(profiles.ProfileError,self.installed_snapshot,'unknown.pth')
    def test_unlisted_native_extension_fails(self):self.assertRaises(profiles.ProfileError,self.installed_snapshot,'unknown.so')
    def test_missing_recorded_dependency_source_fails(self):self.assertRaises(profiles.ProfileError,self.installed_snapshot,None,True)
    def cache(self,source='value=1\n',payload=None):
        path=self.root/'owned.py';path.write_text(source);cache=Path(importlib.util.cache_from_source(str(path)));cache.parent.mkdir()
        data=importlib.util.MAGIC_NUMBER+(0).to_bytes(4,'little')+b'\0'*8+marshal.dumps(compile(source,str(path),'exec'))
        cache.write_bytes(data if payload is None else payload);return path,cache
    def test_actual_cache_matching_owned_source_passes(self):_,cache=self.cache();profiles.validate_bytecode(cache)
    def test_cached_different_executable_fails(self):path,cache=self.cache();path.write_text('value=2\n');self.assertRaises(profiles.ProfileError,profiles.validate_bytecode,cache)
    def test_missing_cache_source_fails(self):path,cache=self.cache();path.unlink();self.assertRaises(profiles.ProfileError,profiles.validate_bytecode,cache)
    def test_invalid_cache_magic_fails(self):_,cache=self.cache(payload=b'wrong');self.assertRaises(profiles.ProfileError,profiles.validate_bytecode,cache)
    def test_invalid_cache_flags_fails(self):_,cache=self.cache();data=cache.read_bytes();cache.write_bytes(data[:4]+(2).to_bytes(4,'little')+data[8:]);self.assertRaises(profiles.ProfileError,profiles.validate_bytecode,cache)
    def test_trailing_cache_payload_fails(self):_,cache=self.cache();cache.write_bytes(cache.read_bytes()+b'junk');self.assertRaises(profiles.ProfileError,profiles.validate_bytecode,cache)
    def test_noncode_cache_payload_fails(self):_,cache=self.cache();cache.write_bytes(cache.read_bytes()[:16]+marshal.dumps('unsafe'));self.assertRaises(profiles.ProfileError,profiles.validate_bytecode,cache)
    def test_malformed_cache_payload_fails(self):_,cache=self.cache();cache.write_bytes(cache.read_bytes()[:16]+b'x');self.assertRaises(profiles.ProfileError,profiles.validate_bytecode,cache)


if __name__=='__main__':unittest.main()
