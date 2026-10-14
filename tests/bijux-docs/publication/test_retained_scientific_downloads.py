"""Exercise source-custody boundaries with toy Git epochs, never scientific results."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

capabilities = load('bijux_retained_test_capabilities', ROOT/'shared/bijux-docs/security/producer_capabilities.py')
helper = load('bijux_retained_test_sources', ROOT/'shared/bijux-docs/security/retained_scientific_downloads.py')

def digest(value):
    return hashlib.sha256(value).hexdigest()


class RetainedBuildSources(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT/'artifacts/qualification/retained-scientific-downloads'
        artifacts.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.decks = ('big-picture', 'developer', 'scientific-evidence')
        self.git('init', '-q')
        self.paths = [f'inputs/source-{number:03}.txt' for number in range(121)]
        for name in self.paths[:98]:
            self.write(name, 'Historical source '+name+'\n')
        old_lock = {'decks': list(self.decks), 'sources': self.hashes(self.paths[:98])}
        self.write_json('presentation/source-lock.json', old_lock)
        old_lock_hash = self.hash('presentation/source-lock.json')
        previous_revision = self.commit('retain original source epoch')
        previous = {'schema': 'retained-deck-source-context.v1', 'source_revision': previous_revision,
                    'source_lock_sha256': old_lock_hash, 'security_metadata': {'scope': 'toy fixture'}}
        self.write_json('presentation/retained-source-context.json', previous)
        for name in self.paths[98:]:
            self.write(name, 'Historical source '+name+'\n')
        lock = {'decks': list(self.decks), 'sources': self.hashes(self.paths)}
        self.write_json('presentation/source-lock.json', lock)
        for name in self.decks:
            self.write(f'presentation/{name}.pdf', '%PDF-1.7\nFixture source-custody bytes only\n')
        accepted = self.commit('retain later source epoch')
        historical_hashes = dict(lock['sources'])
        for name in self.paths[:15]:
            self.write(name, 'Individually reviewed current source '+name+'\n')
        current_hashes = self.hashes(self.paths)
        pdfs = self.hashes([f'presentation/{name}.pdf' for name in self.decks])
        context = {
            'schema_version': 'retained-deck-current-source-correspondence.v1',
            'retained_build': {'accepted_revision': accepted, 'source_revision': accepted,
                'source_lock_path': 'presentation/source-lock.json',
                'source_lock_sha256': self.hash('presentation/source-lock.json'), 'source_count': 121,
                'pdf_sha256': pdfs},
            'previous_deck_epoch': {'context_path': 'presentation/retained-source-context.json',
                'context_sha256': self.hash('presentation/retained-source-context.json'),
                'source_revision': previous_revision, 'source_lock_sha256': old_lock_hash, 'source_count': 98},
            'current_source_sha256': current_hashes,
            'reviewed_deltas': [{'path': name, 'retained_sha256': historical_hashes[name],
                'current_sha256': current_hashes[name], 'review': 'Source-specific toy fixture custody review.'}
                for name in self.paths[:15]],
            'qualification': 'Fixture source correspondence; no scientific execution or publication.',
        }
        self.write_json('presentation/retained-build-source-context.json', context)
        self.commit('retain reviewed current source correspondence')
        self.rule = {**helper.ADMISSION, 'context_sha256': self.hash('presentation/retained-build-source-context.json'),
            'source_lock_sha256': self.hash('presentation/source-lock.json'), 'accepted_revision': accepted,
            'source_revision': accepted, 'previous_context_sha256': self.hash('presentation/retained-source-context.json'),
            'previous_revision': previous_revision, 'previous_source_lock_sha256': old_lock_hash, 'pdf_sha256': pdfs}
        self.previous = previous
        self.returned = {'context': context,
            'historical_inputs': [{'path': name, 'sha256': historical_hashes[name]} for name in self.paths],
            'current_inputs': [{'path': name, 'sha256': current_hashes[name]} for name in self.paths]}
        self.hook = types.SimpleNamespace(
            CURRENT_DECK_CONTEXT_PATH=self.rule['context_path'], CURRENT_DECK_CONTEXT_SHA256=self.rule['context_sha256'],
            CURRENT_DECK_SOURCE_LOCK_SHA256=self.rule['source_lock_sha256'], CURRENT_DECK_ACCEPTED_REVISION=accepted,
            RETAINED_CONTEXT_PATH=self.rule['previous_context_path'], RETAINED_CONTEXT_SHA256=self.rule['previous_context_sha256'],
            RETAINED_CONTEXT=previous, DECKS=self.decks, subprocess=subprocess, tomllib=tomllib, io=io,
            retained_deck_sources=lambda root: self.returned)

    def git(self, *arguments):
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_AUTHOR_NAME='Bijux', GIT_AUTHOR_EMAIL='fixture@example.invalid',
                   GIT_COMMITTER_NAME='Bijux', GIT_COMMITTER_EMAIL='fixture@example.invalid')
        return subprocess.check_output(['git', '-C', str(self.root), *arguments], env=env, stderr=subprocess.PIPE).decode().strip()

    def commit(self, subject):
        self.git('add', '--all')
        self.git('commit', '-qm', subject)
        return self.git('rev-parse', 'HEAD')

    def write(self, name, content):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def write_json(self, name, value):
        self.write(name, json.dumps(value, indent=2)+'\n')

    def hash(self, name):
        return digest((self.root/name).read_bytes())

    def hashes(self, names):
        return {name: self.hash(name) for name in names}

    def capture(self):
        with patch.object(helper, 'ADMISSION', self.rule):
            return helper.capture(self.hook, self.root, capabilities.regular, capabilities.require, digest, self.previous)

    def refused(self, pattern):
        with self.assertRaisesRegex((ValueError, subprocess.CalledProcessError), pattern):
            self.capture()

    def test_distinct_98_and_121_epochs_and_15_reviewed_deltas(self):
        captured = self.capture()
        self.assertEqual(captured, self.returned)
        self.assertEqual(len(captured['historical_inputs']), 121)
        self.assertEqual(captured['context']['previous_deck_epoch']['source_count'], 98)
        self.assertEqual(len(captured['context']['reviewed_deltas']), 15)

    def test_changed_raw_context_is_refused(self):
        with (self.root/self.rule['context_path']).open('a') as stream:
            stream.write(' ')
        self.refused('raw source context differs')

    def test_changed_loaded_context_constant_is_refused(self):
        self.hook.CURRENT_DECK_CONTEXT_SHA256 = '0'*64
        self.refused('constants or native dependency')

    def test_changed_native_dependency_binding_is_refused(self):
        self.hook.subprocess = types.SimpleNamespace()
        self.refused('constants or native dependency')

    def test_previous_epoch_cannot_be_replaced_by_later_lock(self):
        self.rule['previous_source_lock_sha256'] = self.rule['source_lock_sha256']
        self.refused('previous source epoch differs')

    def test_changed_current_file_is_refused(self):
        self.write(self.paths[-1], 'Unreviewed source bytes\n')
        self.refused('reviewed committed source')

    def test_reviewed_physical_file_must_also_match_current_git(self):
        self.write(self.paths[-1], 'Another committed source\n')
        self.commit('retain unreviewed source')
        self.write(self.paths[-1], 'Historical source '+self.paths[-1]+'\n')
        self.refused('reviewed committed source')

    def test_current_mode_is_source_owned(self):
        (self.root/self.paths[0]).chmod(0o755)
        self.refused('current source mode differs')

    def test_missing_source_is_refused(self):
        (self.root/self.paths[0]).unlink()
        self.refused('source must belong')

    def test_symlink_source_is_refused(self):
        source = self.root/self.paths[0]
        source.unlink()
        source.symlink_to(self.root/self.paths[1])
        self.refused('source symlink forbidden')

    def test_changed_retained_pdf_is_refused(self):
        self.write('presentation/big-picture.pdf', '%PDF-1.7\nChanged bytes\n')
        self.refused('original retained PDF differs')

    def test_forged_callback_correspondence_is_refused(self):
        self.returned = copy.deepcopy(self.returned)
        self.returned['historical_inputs'][0]['sha256'] = '0'*64
        self.refused('callback source correspondence differs')

    def test_delta_identity_is_independently_checked(self):
        value = self.returned['context']
        value['reviewed_deltas'][0]['retained_sha256'] = '0'*64
        self.write_json(self.rule['context_path'], value)
        self.rule['context_sha256'] = self.hash(self.rule['context_path'])
        self.hook.CURRENT_DECK_CONTEXT_SHA256 = self.rule['context_sha256']
        self.refused('reviewed source delta identity differs')

    def test_delta_population_is_independently_checked(self):
        value = self.returned['context']
        value['reviewed_deltas'].reverse()
        self.write_json(self.rule['context_path'], value)
        self.rule['context_sha256'] = self.hash(self.rule['context_path'])
        self.hook.CURRENT_DECK_CONTEXT_SHA256 = self.rule['context_sha256']
        self.refused('reviewed delta population differs')

    def test_historical_population_is_regular_git_source(self):
        with self.assertRaisesRegex(ValueError, 'historical source population differs'):
            helper._blobs(self.root, self.rule['accepted_revision'], ['missing-source'], capabilities.require)

    def test_history_selector_refuses_traversal_and_duplicate_sources(self):
        for paths in [['inputs/../outside'], [self.paths[0], self.paths[0]]]:
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                helper._blobs(self.root, self.rule['accepted_revision'], paths, capabilities.require)


if __name__ == '__main__':
    unittest.main(verbosity=2)
