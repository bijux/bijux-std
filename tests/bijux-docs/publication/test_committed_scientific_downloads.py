"""Qualify changing committed review manifests without changing retained PDF epochs."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import types
from pathlib import Path
import subprocess
import typing
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

base = load('bijux_committed_fixture_sources', Path(__file__).with_name('test_retained_scientific_downloads.py'))
helper = load('bijux_committed_source_helper', ROOT/'shared/bijux-docs/security/retained_scientific_downloads.py')
capabilities = base.capabilities


class CommittedSourceManifest(unittest.TestCase):
    def setUp(self):
        self.fixture = base.RetainedBuildSources(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.context = f.returned['context']
        self.context['retained_build'].update(native_terminal_sha256='a'*64, scope='Toy retained source identity; no scientific execution.')
        self.context['previous_deck_epoch']['scope'] = 'Toy original epoch; source identity only.'
        self.fixed_build = copy.deepcopy(self.context['retained_build'])
        self.fixed_previous = copy.deepcopy(self.context['previous_deck_epoch'])
        f.hook.CURRENT_DECK_BUILD = copy.deepcopy(self.fixed_build)
        f.hook.CURRENT_DECK_PREVIOUS_EPOCH = copy.deepcopy(self.fixed_previous)
        f.hook.CURRENT_DECK_CONTEXT_SCHEMA = 'retained-deck-current-source-correspondence.v1'
        f.hook.cast, f.hook.Any = typing.cast, typing.Any
        del f.hook.CURRENT_DECK_CONTEXT_SHA256
        self.commit_context()

    def commit_context(self):
        f = self.fixture
        f.write_json(f.rule['context_path'], self.context)
        f.commit('record reviewed source manifest')

    def capture(self):
        f = self.fixture
        with patch.object(helper, 'ADMISSION', f.rule), patch.object(helper, 'COMMITTED_BUILD', self.fixed_build), patch.object(helper, 'COMMITTED_PREVIOUS_EPOCH', self.fixed_previous):
            return helper.capture_committed(f.hook, f.root, capabilities.regular, capabilities.require, base.digest, f.previous)

    def refused(self, expression):
        with self.assertRaisesRegex((ValueError, subprocess.CalledProcessError), expression):
            self.capture()

    def test_committed_manifest_preserves_both_retained_epochs(self):
        self.assertEqual(self.capture(), self.fixture.returned)
        self.assertEqual(len(self.capture()['current_inputs']), 121)
        self.assertFalse(hasattr(self.fixture.hook, 'CURRENT_DECK_CONTEXT_SHA256'))

    def test_later_committed_source_review_needs_no_new_callback_or_digest(self):
        f = self.fixture
        name = f.paths[15]
        original = dict((r['path'], r['sha256']) for r in f.returned['historical_inputs'])[name]
        f.write(name, 'Another individually reviewed finite source.\n')
        current = f.hash(name)
        self.context['current_source_sha256'][name] = current
        self.context['reviewed_deltas'].append({'path': name, 'retained_sha256': original, 'current_sha256': current, 'review': 'A later source-owned review of this exact source change.'})
        self.context['reviewed_deltas'].sort(key=lambda row: row['path'])
        f.returned['current_inputs'] = [{'path': p, 'sha256': f.hash(p)} for p in f.paths]
        self.commit_context()
        self.assertEqual(self.capture(), f.returned)
        self.assertEqual(len(self.capture()['context']['reviewed_deltas']), 16)

    def test_uncommitted_context_cannot_acquire_authority(self):
        self.context['qualification'] += ' Uncommitted review.'
        self.fixture.write_json(self.fixture.rule['context_path'], self.context)
        self.refused('manifest differs from current committed')

    def test_context_physical_mode_must_match_commit(self):
        path = self.fixture.root/self.fixture.rule['context_path']
        path.chmod(path.stat().st_mode ^ 0o100)
        self.refused('manifest differs from current committed')

    def test_uncommitted_source_cannot_acquire_review_authority(self):
        self.fixture.write(self.fixture.paths[0], 'Unreviewed source\n')
        self.refused('current input differs')

    def test_context_parent_symlink_is_refused(self):
        root = self.fixture.root
        (root/'presentation').rename(root/'actual-presentation')
        (root/'presentation').symlink_to(root/'actual-presentation', target_is_directory=True)
        self.refused('source symlink')

    def test_duplicate_committed_json_keys_refuse(self):
        path = self.fixture.root/self.fixture.rule['context_path']
        path.write_bytes(path.read_bytes().replace(b'{', b'{"qualification":"duplicated",', 1))
        self.fixture.commit('retain malformed source fixture')
        self.refused('duplicate manifest key')

    def test_fixed_epoch_globals_cannot_be_mutated(self):
        self.fixture.hook.CURRENT_DECK_BUILD['native_terminal_sha256'] = '0'*64
        self.refused('fixed source epochs')

    def test_native_typing_binding_cannot_be_replaced(self):
        self.fixture.hook.cast = lambda *args: self.context
        self.refused('native typing bindings')

    def test_committed_unknown_or_malformed_fields_refuse(self):
        for mutation in ['unknown', 'build', 'previous', 'coerced_integer', 'source_hash', 'source_path', 'review_field', 'review_type', 'review_hash', 'missing_delta', 'duplicate_delta', 'reordered_delta', 'retained_hash', 'qualification']:
            with self.subTest(mutation=mutation):
                original = copy.deepcopy(self.context)
                if mutation == 'unknown': self.context['unknown'] = True
                elif mutation == 'build': self.context['retained_build']['unknown'] = True
                elif mutation == 'previous': self.context['previous_deck_epoch']['unknown'] = True
                elif mutation == 'coerced_integer': self.context['retained_build']['source_count'] = 121.0
                elif mutation == 'source_hash': self.context['current_source_sha256'][self.fixture.paths[0]] = True
                elif mutation == 'source_path':
                    value = self.context['current_source_sha256'].pop(self.fixture.paths[-1]); self.context['current_source_sha256']['../outside'] = value
                elif mutation == 'review_field': self.context['reviewed_deltas'][0]['unknown'] = True
                elif mutation == 'review_type': self.context['reviewed_deltas'][0]['review'] = False
                elif mutation == 'review_hash': self.context['reviewed_deltas'][0]['current_sha256'] = '0'*64
                elif mutation == 'missing_delta': self.context['reviewed_deltas'].pop()
                elif mutation == 'duplicate_delta': self.context['reviewed_deltas'].append(self.context['reviewed_deltas'][0])
                elif mutation == 'reordered_delta': self.context['reviewed_deltas'].reverse()
                elif mutation == 'retained_hash': self.context['reviewed_deltas'][0]['retained_sha256'] = '0'*64
                else: self.context['qualification'] = False
                self.commit_context()
                self.refused('Committed retained build|Retained build: reviewed source delta|Retained build: reviewed delta|Retained build: source path')
                self.context.clear(); self.context.update(original)
                self.commit_context()


pdf = load('bijux_committed_fixture_downloads', Path(__file__).with_name('test_scientific_download_capabilities.py'))


class CommittedHookAdmission(unittest.TestCase):
    write = pdf.ScientificDownloads.write
    write_json = pdf.ScientificDownloads.write_json
    row = pdf.ScientificDownloads.row
    capture = pdf.ScientificDownloads.capture

    def setUp(self):
        pdf.ScientificDownloads.setUp(self)
        fixture = Path(__file__).parent/'fixtures/scientific-downloads/committed-manifest/configs/docs/science_downloads.py'
        shutil.copyfile(fixture, self.path)
        self.hook = load('bijux_committed_fixture_hook', self.path)
        self.configuration.hooks['downloads'] = self.hook

    def test_exact_stable_hook_recipe_preserves_old_recipes(self):
        self.assertEqual(pdf.capabilities.HOOKS[base.digest(self.path.read_bytes())], 'committed-retained-scientific-pdf-downloads')
        self.assertEqual(pdf.capabilities.HOOKS['f21163129fc42a4a3cc2e5d4d09c6b9fd1cd9096d14b5c7340a8dd6d8487fa26'], 'retained-build-scientific-pdf-downloads')
        self.assertEqual(pdf.capabilities.HOOKS['6007e8ae8a101b74102df0385dd0a9bb93efe85bf0edc9962ee3cff346a0b5bf'], 'retained-scientific-pdf-downloads')

    def test_foreign_loaded_helper_cannot_acquire_authority(self):
        self.hook._validated_current_deck_context = lambda *args: {}
        with self.assertRaisesRegex(ValueError, 'loaded callback differs'):
            self.capture()

    def test_callback_with_foreign_globals_is_refused(self):
        function = self.hook.retained_deck_sources
        self.hook.retained_deck_sources = types.FunctionType(function.__code__, dict(function.__globals__))
        with self.assertRaisesRegex(ValueError, 'loaded callback differs'):
            self.capture()

    def test_missing_committed_manifest_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'source must belong'):
            self.capture()

    def test_original_lock_identity_cannot_change(self):
        self.hook.CURRENT_DECK_SOURCE_LOCK_SHA256 = '0'*64
        with self.assertRaisesRegex(ValueError, 'fixed source epochs'):
            self.capture()

    def test_typing_dependency_cannot_be_replaced(self):
        self.hook.cast = lambda *args: {}
        with self.assertRaisesRegex(ValueError, 'native typing bindings'):
            self.capture()


if __name__ == '__main__':
    unittest.main(verbosity=2)
