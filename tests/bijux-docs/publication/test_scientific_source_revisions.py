"""Refuse substituted source resolvers before scientific download execution."""
from __future__ import annotations

import functools
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SECURITY = ROOT / 'shared/bijux-docs/security'
with patch.object(sys, 'path', [str(SECURITY), *sys.path]):
    SPEC = importlib.util.spec_from_file_location('bijux_scientific_source_revisions', SECURITY / 'scientific_source_revisions.py')
    revisions = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(revisions)
    NATIVE_SPEC = importlib.util.spec_from_file_location('bijux_scientific_revisions_native_git', SECURITY / 'retained_scientific_downloads.py')
    native = importlib.util.module_from_spec(NATIVE_SPEC)
    NATIVE_SPEC.loader.exec_module(native)

CONTRACTS = '''class ReportRebuildError(RuntimeError):
    pass
def require_string(value, label):
    if not isinstance(value, str) or not value:
        raise ReportRebuildError(label)
    return value
def require_relative_path(value, label):
    value = require_string(value, label)
    if value.startswith('/') or any(part in {'', '.', '..'} for part in value.split('/')):
        raise ReportRebuildError(label)
    return value
'''
OBJECTS = '''from pathlib import Path
from ..contracts import ReportRebuildError
def require(value, reason):
    if not value:
        raise ReportRebuildError(reason)
def hexadecimal(value, width):
    return type(value) is str and len(value) == width and all(c in '0123456789abcdef' for c in value)
def physical(path):
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)), 'physical source required')
'''
DESCRIPTOR = '''import hashlib
import json
from pathlib import Path
from ..contracts import require_relative_path
from . import objects
from .objects import require, physical, hexadecimal
def object_fields(value, keys):
    require(type(value) is dict and set(value) == keys, 'fields differ')
    return value
def json_object(raw):
    return json.loads(raw)
def pinned_bytes(path, checksum, size, cap):
    physical(path)
    raw = path.read_bytes()
    require(0 < size <= cap and len(raw) == size and hashlib.sha256(raw).hexdigest() == checksum, 'registry differs')
    return raw
'''
INDEX = '''from functools import lru_cache
from pathlib import Path
from ..contracts import require_relative_path
from .descriptor import object_fields, json_object, pinned_bytes
from .objects import physical, require, hexadecimal
INDEX_PATH = {path!r}
INDEX_SHA256 = {sha!r}
INDEX_BYTES = {size}
MAX_DESCRIPTOR_BYTES = 8 * 1024**2
def _seal(path):
    physical(path)
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
@lru_cache(maxsize=8)
def _index_buffer(path, checksum, size, seal):
    return object_fields(json_object(pinned_bytes(path, checksum, size, 4 * 1024**2)), {{'schema_version', 'capsules', 'source_revisions'}})
def configured_index(repository):
    path = repository / INDEX_PATH
    return _index_buffer(path, INDEX_SHA256, INDEX_BYTES, _seal(path))
def source_revision(repository, historical):
    require(hexadecimal(historical, 40), 'literal epoch required')
    return str(configured_index(repository)['source_revisions'].get(historical, historical))
'''


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def require(value, reason):
    if not value:
        raise ValueError(reason)


def regular(root, path):
    require(path.is_relative_to(root) and path.is_file()
            and not any(part.is_symlink() for part in (path, *path.parents)), 'regular owner required')
    return path.read_bytes()


class ScientificSourceRevisions(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT / 'artifacts/qualification/scientific-source-revisions'
        artifacts.mkdir(parents=True, exist_ok=True)
        scratch = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.registry = {'schema_version': 'retained-source-index.v1', 'capsules': {},
                         'source_revisions': dict(revisions.PAPER_STORAGE)}
        raw = json.dumps(self.registry).encode()
        self.write(revisions.INDEX, raw)
        fixture = {'contracts': CONTRACTS, 'retained_source': 'from .index import source_revision\n',
                   'retained_source.objects': OBJECTS, 'retained_source.descriptor': DESCRIPTOR,
                   'retained_source.index': INDEX.format(path=revisions.INDEX, sha=digest(raw), size=len(raw))}
        sources = {}
        for suffix, body in fixture.items():
            relative = revisions.SOURCES[suffix][0]
            self.write(revisions.SOURCE_ROOT + relative, body.encode())
            sources[suffix] = relative, digest(body.encode())
        for name, value in {'SOURCES': sources, 'INDEX_BYTES': len(raw), 'INDEX_SHA256': digest(raw)}.items():
            manager = patch.object(revisions, name, value)
            manager.start()
            self.addCleanup(manager.stop)
        self.identity = 'a' * 40
        self.manifest = {'repository_revision': self.identity, 'producer_revision': self.identity,
                         'papers': [{'source_revision': old} for old in revisions.PAPER_STORAGE]}
        self.write_manifest()
        self.git('init', '-q')
        self.commit()
        self.modules = {}
        names = ['bijux_pollenomics_dev', 'bijux_pollenomics_dev.ci', revisions.PACKAGE]
        injected = {}
        for name in names:
            module = types.ModuleType(name)
            module.__path__ = []
            injected[name] = module
        for suffix, (relative, _) in sources.items():
            name = revisions.PACKAGE + '.' + suffix
            module = types.ModuleType(name)
            module.__file__ = str(self.root / (revisions.SOURCE_ROOT + relative))
            module.__package__ = name if suffix == 'retained_source' else name.rpartition('.')[0]
            if suffix == 'retained_source':
                module.__path__ = []
            injected[name] = self.modules[suffix] = module
        manager = patch.dict(sys.modules, injected)
        manager.start()
        self.addCleanup(manager.stop)
        for suffix in ('contracts', 'retained_source.objects', 'retained_source.descriptor',
                       'retained_source.index', 'retained_source'):
            module = self.modules[suffix]
            exec(compile(fixture[suffix], module.__file__, 'exec', dont_inherit=True), vars(module))
        self.hook = types.SimpleNamespace(source_revision=self.modules['retained_source'].source_revision)

    def write(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def write_manifest(self):
        self.write('reports/exports/papers/manifest.json', json.dumps(self.manifest).encode())

    def git(self, *arguments):
        return subprocess.run(['git', '--no-replace-objects', '-C', str(self.root), *arguments],
                              check=True, capture_output=True, timeout=30).stdout

    def commit(self):
        paths = [revisions.SOURCE_ROOT + relative for relative, _ in revisions.SOURCES.values()]
        self.git('add', '--', *paths, revisions.INDEX, 'reports/exports/papers/manifest.json')
        self.git('-c', 'user.name=Bijux fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'record source resolver fixture')

    def capture(self):
        return revisions.capture(self.hook, self.root, regular, require, digest, native._blobs, native._git)

    def refused(self, message):
        with self.assertRaisesRegex(ValueError, message):
            self.capture()

    def test_exact_epochs_preserve_storage_mapping_and_identity(self):
        result = self.capture()
        self.assertEqual(len(result['inputs']), 6)
        actual = {row['historical_revision']: row['storage_revision'] for row in result['paper_source_revisions']}
        self.assertEqual(actual, {**revisions.PAPER_STORAGE, self.identity: self.identity})

    def test_foreign_imported_resolver_is_refused_without_execution(self):
        calls = []
        self.hook.source_revision = lambda *args: calls.append(args)
        self.refused('imported source resolver differs')
        self.assertEqual(calls, [])

    def test_replaced_public_export_is_refused_before_execution(self):
        self.modules['retained_source'].source_revision = lambda *args: self.identity
        self.refused('imported source resolver differs')

    def test_same_code_with_foreign_globals_cannot_supply_resolver(self):
        index = self.modules['retained_source.index']
        index.source_revision = types.FunctionType(index.source_revision.__code__, dict(vars(index)))
        self.hook.source_revision = self.modules['retained_source'].source_revision = index.source_revision
        self.refused('loaded resolver callable differs')

    def test_replaced_transitive_index_reader_is_refused(self):
        self.modules['retained_source.index'].configured_index = lambda root: self.registry
        self.refused('loaded resolver callable differs')

    def test_forged_cache_wrapped_attribute_cannot_hide_other_callable(self):
        index = self.modules['retained_source.index']
        original = index._index_buffer.__wrapped__
        index._index_buffer = functools.lru_cache(maxsize=8)(lambda *args: self.registry)
        index._index_buffer.__wrapped__ = original
        self.refused('cache wraps another callable')

    def test_poisoned_native_cache_cannot_change_mapping(self):
        index = self.modules['retained_source.index']
        index.configured_index(self.root)['source_revisions'][self.identity] = 'b' * 40
        self.refused('loaded registry differs')

    def test_replaced_native_dependency_is_refused(self):
        self.modules['retained_source.descriptor'].json = types.SimpleNamespace(loads=lambda raw: self.registry)
        self.refused('dependency binding differs')

    def test_changed_index_or_committed_source_refuses(self):
        self.write(revisions.INDEX, json.dumps({**self.registry, 'capsules': {'forged': {}}}).encode())
        self.refused('fixed source registry differs')

    def test_changed_resolver_file_cannot_gain_authority_by_commit(self):
        name = revisions.SOURCE_ROOT + revisions.SOURCES['retained_source.index'][0]
        self.write(name, (self.root / name).read_bytes() + b'\n# Different reviewed source.\n')
        self.commit()
        self.refused('reviewed committed resolver source required')

    def test_changed_fixed_registry_constant_is_refused(self):
        self.modules['retained_source.index'].INDEX_SHA256 = '0' * 64
        self.refused('fixed registry identity differs')

    def test_foreign_loaded_module_origin_is_refused(self):
        self.modules['retained_source.index'].__file__ = str(self.root / 'foreign.py')
        self.refused('module must belong')


if __name__ == '__main__':
    unittest.main()
