"""Refuse forged current deck identities while retaining old PDF recipes."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import types
import tomllib
import typing
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


security = ROOT / 'shared/bijux-docs/security'
compiled = load('bijux_compiled_deck_controls', security / 'compiled_scientific_downloads.py')
native = load('bijux_compiled_native_git', security / 'retained_scientific_downloads.py')
capabilities = load('bijux_compiled_capabilities', security / 'producer_capabilities.py')


class CurrentScientificBindings(unittest.TestCase):
    def test_foreign_loaded_dependencies_refuse_before_helper_loading(self):
        bindings = dict(subprocess=subprocess, io=io, tomllib=tomllib,
                        cast=typing.cast, Any=typing.Any)
        for name in bindings:
            with self.subTest(binding=name):
                hook = types.SimpleNamespace(**{**bindings, name: object()})
                with patch.object(Path, 'read_bytes', side_effect=AssertionError('helper loading must not run')):
                    with self.assertRaisesRegex(ValueError, 'dependency binding changed'):
                        capabilities.current_scientific_context(hook, ROOT)


class CompiledDeckSources(unittest.TestCase):
    def setUp(self):
        owned = ROOT / 'artifacts/qualification/git-compiled-scientific-downloads'
        owned.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=owned)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.git('init', '-q')
        for name in compiled.INPUTS:
            self.write(name, 'Fixed compiled input: ' + name + '\n')
        self.write(compiled.HELPER, 'Reviewed synthetic helper; never executed.\n')
        self.git('add', '--', *compiled.INPUTS, compiled.HELPER)
        self.git('-c', 'user.name=Bijux', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'retain compiled source fixture')
        self.revision = self.git('rev-parse', 'HEAD').decode().strip()
        self.build = {
            'schema_version': 'git-compiled-deck-inputs.v1',
            'source_revision': self.revision,
            'source_date_epoch': int(self.git('show', '-s', '--format=%ct', self.revision)),
            'inputs': list(compiled.INPUTS),
            'compilers': [
                {'deck': name, 'actual_exit': 0, 'argv': [
                    'latexmk', *compiled.FLAGS,
                    f'-outdir=artifacts/jobs/presentation/{name}', f'presentation/{name}.tex',
                ]} for name in compiled.DECKS
            ],
        }
        self.manifest = {'deck_build': self.build, 'inputs': {}, 'files': [
            {'path': f'presentation/{name}.pdf'} for name in compiled.DECKS
        ]}
        self.expected = {'context': self.build, 'current_inputs': [
            {'path': name, 'source_revision': self.revision} for name in compiled.INPUTS
        ]}
        self.hook = types.SimpleNamespace(MANIFEST='reports/exports/site-downloads.json',
                                         retained_deck_sources=lambda root: self.expected)
        self.pinning = patch.object(compiled, 'HELPER_SHA256', capabilities.digest(
            (self.root / compiled.HELPER).read_bytes()))
        self.pinning.start()
        self.addCleanup(self.pinning.stop)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              capture_output=True).stdout

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def capture(self):
        self.write(self.hook.MANIFEST, json.dumps(self.manifest))
        return compiled.capture(self.hook, self.root, capabilities.regular,
                                capabilities.require, capabilities.digest, native._blobs, native._git)

    def refused(self, message):
        with self.assertRaisesRegex(ValueError, message):
            self.capture()

    def test_current_five_inputs_use_git_while_old_recipes_stay_distinct(self):
        self.assertEqual(self.capture(), self.expected)
        self.assertEqual(capabilities.HOOKS['1299643212a65a326e167897ab2951d69503e2ee9b059cf5345c14b521afb6c1'],
                         'git-compiled-scientific-pdf-downloads')
        self.assertEqual(capabilities.HOOKS['1ba76967b9519a4495708ff577694a170dfabb4849449a0381bb3e1512ce632b'],
                         'committed-retained-scientific-pdf-downloads')
        self.assertNotIn('4f76c0fddaccf55d5c4a93fb6bad14cfeb828abfa7058b346c78936380ffd342',
                         capabilities.PDF_VERIFIER_SHA256)

    def test_changed_helper_refuses_before_callback(self):
        self.write(compiled.HELPER, 'Foreign helper\n')
        self.refused('helper differs from reviewed')

    def test_helper_mode_is_committed(self):
        path = self.root / compiled.HELPER
        path.chmod(path.stat().st_mode ^ 0o100)
        self.refused('helper differs from committed')

    def test_changed_compiled_input_refuses(self):
        self.write(compiled.INPUTS[0], 'Different input\n')
        self.refused('input bytes or mode changed')

    def test_compiled_source_mode_refuses(self):
        path = self.root / compiled.INPUTS[0]
        path.chmod(path.stat().st_mode ^ 0o100)
        self.refused('input bytes or mode changed')

    def test_source_date_epoch_refuses(self):
        self.build['source_date_epoch'] += 1
        self.refused('date epoch differs')

    def test_nonancestor_source_refuses(self):
        tree = self.git('rev-parse', 'HEAD^{tree}').decode().strip()
        orphan = self.git('-c', 'user.name=Bijux', '-c', 'user.email=fixture@example.invalid',
                          'commit-tree', tree, '-m', 'independent source fixture').decode().strip()
        self.build['source_revision'] = orphan
        with self.assertRaises(subprocess.CalledProcessError):
            self.capture()

    def test_strict_build_and_compiler_types(self):
        for mutation in ('epoch_bool', 'input_population', 'extra_build', 'compiler_bool', 'compiler_argv', 'compiler_population'):
            with self.subTest(mutation=mutation):
                original = copy.deepcopy(self.build)
                if mutation == 'epoch_bool': self.build['source_date_epoch'] = True
                elif mutation == 'input_population': self.build['inputs'] = self.build['inputs'][:-1]
                elif mutation == 'extra_build': self.build['unknown'] = 1
                elif mutation == 'compiler_bool': self.build['compilers'][0]['actual_exit'] = False
                elif mutation == 'compiler_argv': self.build['compilers'][0]['argv'].append('--shell-escape')
                else: self.build['compilers'].pop()
                self.refused('build identity|compiler completion')
                self.build.clear(); self.build.update(original)

    def test_historical_trigger_is_refused(self):
        self.manifest['inputs']['presentation/source-lock.json'] = '0' * 64
        self.refused('historical inventory')

    def test_wrong_export_population_or_historical_source_hash_refuses(self):
        for mutation in ('duplicate', 'extra', 'historical_hash'):
            with self.subTest(mutation=mutation):
                original = copy.deepcopy(self.manifest['files'])
                if mutation == 'duplicate': self.manifest['files'][0] = self.manifest['files'][1]
                elif mutation == 'extra': self.manifest['files'].append({'path': 'presentation/foreign.pdf'})
                else: self.manifest['files'][0]['source_sha256'] = '0' * 64
                self.refused('current exports')
                self.manifest['files'] = original

    def test_callback_cannot_substitute_its_source_capture(self):
        self.hook.retained_deck_sources = lambda root: {}
        self.refused('callback differs')

    def test_callback_cannot_mutate_consumed_inputs(self):
        def changed(root):
            self.write(compiled.INPUTS[0], 'Changed during capture\n')
            return self.expected
        self.hook.retained_deck_sources = changed
        self.refused('consumed sources changed')


if __name__ == '__main__':
    unittest.main(verbosity=2)
