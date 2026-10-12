"""Refuse altered npm bytes, package topology and platform identities before reuse."""
import copy
import gzip
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(path, key):
    module = ModuleType(key)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


ARCHIVE = load(ROOT / 'tests/bijux-docs/execution/runtime_transport/archive.py', 'bijux_runtime_transport_controls')
GATE = load(ROOT / 'tests/bijux-docs/execution/browser_gate.py', 'bijux_runtime_gate_controls')


class RuntimeTransportTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(dir=ROOT / 'artifacts')
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.source, self.runtime = self.root / 'source', self.root / 'runtime'
        self.source.mkdir(); self.runtime.mkdir()
        self.inputs = {'node_version': 'v24.21.0', 'node_sha256': 'a' * 64,
                       'npm_version': '11.11.0', 'npm_tree_sha256': 'b' * 64,
                       'npm_cli_sha256': 'c' * 64, 'platform': {'system': 'Linux', 'machine': 'x86_64'}}
        package = {'name': 'owned-browser-suite', 'devDependencies': {'playwright': '1.58.2'}}
        lock = {'lockfileVersion': 3, 'packages': {'': package, 'node_modules/playwright': {'version': '1.58.2'}}}
        for name, value in [('package.json', package), ('package-lock.json', lock)]:
            data = json.dumps(value).encode()
            (self.source / name).write_bytes(data)
            (self.runtime / name).write_bytes(data)
        package_dir = self.runtime / 'node_modules/playwright'
        package_dir.mkdir(parents=True)
        (package_dir / 'package.json').write_text(json.dumps({'name': 'playwright', 'version': '1.58.2', 'bin': {'playwright': 'cli.js'}}))
        (package_dir / 'cli.js').write_text('#!/usr/bin/env node\nconsole.log("native transport control")\n')
        (package_dir / 'cli.js').chmod(0o755)
        (package_dir / 'lib').mkdir()
        (package_dir / 'lib/runtime.js').write_text('module.exports = "exact producer bytes";\n')
        (self.runtime / 'node_modules/.bin').mkdir()
        (self.runtime / 'node_modules/.bin/playwright').symlink_to('../playwright/cli.js')
        self.archive = self.root / 'packages.tar.gz'
        self.receipt = ARCHIVE.pack(self.runtime, self.source, self.archive, self.inputs)

    def unpack(self, declaration=None, inputs=None, output=None):
        return ARCHIVE.unpack(self.archive, declaration or self.receipt, self.source,
                              output or self.root / 'consumer', inputs or self.inputs)

    def mutate(self, change):
        with tarfile.open(self.archive) as stream:
            members = [(member.name, stream.extractfile(member).read(), member.type) for member in stream]
        change(members)
        with tarfile.open(self.archive, 'w:gz', format=tarfile.USTAR_FORMAT) as stream:
            for name, body, kind in members:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = '../../outside' if kind != tarfile.REGTYPE else ''
                member.size = len(body) if kind == tarfile.REGTYPE else 0
                stream.addfile(member, io.BytesIO(body) if member.size else None)
        self.receipt['archive_sha256'] = ARCHIVE.IDENTITY.digest(self.archive.read_bytes())

    def test_exact_package_files_executable_modes_and_links_are_reconstructed_and_reobserved(self):
        self.assertEqual(self.unpack(), self.receipt)
        original = ARCHIVE.IDENTITY.inventory(self.runtime)
        actual = ARCHIVE.IDENTITY.inventory(self.root / 'consumer')
        self.assertEqual(actual, original)
        self.assertEqual(os.readlink(self.root / 'consumer/node_modules/.bin/playwright'), '../playwright/cli.js')
        second = self.root / 'second.tar.gz'
        self.assertEqual(ARCHIVE.pack(self.runtime, self.source, second, self.inputs), self.receipt)
        self.assertEqual(second.read_bytes(), self.archive.read_bytes())

    def test_platform_node_npm_and_lock_change_each_refuses_before_output_creation(self):
        for field in self.inputs:
            changed = copy.deepcopy(self.inputs)
            changed[field] = {'system': 'Darwin', 'machine': 'arm64'} if field == 'platform' else 'altered'
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'platform, toolchain or source lock'):
                self.unpack(inputs=changed)
            self.assertFalse((self.root / 'consumer').exists())
        (self.source / 'package-lock.json').write_text('{"lockfileVersion":3,"packages":{}}')
        with self.assertRaises(ValueError): self.unpack()
        self.assertFalse((self.root / 'consumer').exists())

    def test_changed_package_object_and_receipt_refuse(self):
        self.mutate(lambda members: members.__setitem__(1, (members[1][0], b'forged bytes', tarfile.REGTYPE)))
        with self.assertRaises(ValueError): self.unpack()
        self.assertFalse((self.root / 'consumer').exists())
        altered = {**self.receipt, 'members_sha256': 'f' * 64}
        with self.assertRaises(ValueError): self.unpack(declaration=altered)

    def test_archive_alias_links_duplicate_members_and_trailing_data_refuse(self):
        original = self.archive.read_bytes()
        declaration = copy.deepcopy(self.receipt)
        controls = [lambda members: members.append(('../outside', b'owned', tarfile.REGTYPE)),
                    lambda members: members.append(('objects/' + 'a' * 64, b'', tarfile.SYMTYPE)),
                    lambda members: members.append(('objects/' + 'a' * 64, b'', tarfile.LNKTYPE)),
                    lambda members: members.append(members[1])]
        for change in controls:
            self.archive.write_bytes(original); self.receipt = copy.deepcopy(declaration)
            self.mutate(change)
            with self.assertRaises(ValueError): self.unpack()
            self.assertFalse((self.root / 'consumer').exists())
        self.archive.write_bytes(original + gzip.compress(b'foreign trailing bytes'))
        self.receipt['archive_sha256'] = ARCHIVE.IDENTITY.digest(self.archive.read_bytes())
        with self.assertRaises(ValueError): self.unpack()

    def test_installed_foreign_bin_link_version_missing_executable_and_hardlink_refuse(self):
        link = self.runtime / 'node_modules/.bin/playwright'
        link.unlink(); link.symlink_to('../../outside')
        with self.assertRaisesRegex(ValueError, 'escapes'): ARCHIVE.pack(self.runtime, self.source, self.root / 'bad.tar.gz', self.inputs)
        link.unlink(); link.symlink_to('../playwright/cli.js')
        package = self.runtime / 'node_modules/playwright/package.json'
        package.write_text('{"name":"playwright","version":"1.59.0"}')
        with self.assertRaisesRegex(ValueError, 'version'): ARCHIVE.pack(self.runtime, self.source, self.root / 'bad.tar.gz', self.inputs)
        package.write_text('{"name":"playwright","version":"1.58.2","bin":{"playwright":"cli.js"}}')
        executable = self.runtime / 'node_modules/playwright/cli.js'
        executable.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'not executable'): ARCHIVE.pack(self.runtime, self.source, self.root / 'bad.tar.gz', self.inputs)
        executable.chmod(0o755)
        os.link(executable, self.runtime / 'node_modules/playwright/alias.js')
        with self.assertRaisesRegex(ValueError, 'Hard-linked'): ARCHIVE.pack(self.runtime, self.source, self.root / 'bad.tar.gz', self.inputs)

    def test_index_cannot_authorize_foreign_links_missing_parents_modes_or_excess_bytes(self):
        original = self.archive.read_bytes()
        declaration = copy.deepcopy(self.receipt)
        controls = [lambda index: index['members']['node_modules/.bin/playwright'].update(target='../../outside'),
                    lambda index: index['members'].pop('node_modules/playwright'),
                    lambda index: index['members']['node_modules/playwright/cli.js'].update(mode=0o4755),
                    lambda index: index['members']['node_modules/playwright/cli.js'].update(bytes=ARCHIVE.IDENTITY.MAX_FILE_BYTES + 1),
                    lambda index: index['members'].__setitem__('../outside', {'kind': 'directory'}),
                    lambda index: index['inputs'].update(lock_sha256='f' * 64)]
        for change in controls:
            self.archive.write_bytes(original); self.receipt = copy.deepcopy(declaration)
            def mutate(members):
                index = json.loads(members[0][1]); change(index)
                members[0] = ('index.json', json.dumps(index).encode(), tarfile.REGTYPE)
            self.mutate(mutate)
            with self.assertRaises(ValueError): self.unpack()
            self.assertFalse((self.root / 'consumer').exists())

    def test_existing_destination_and_linked_ancestors_preserve_user_files(self):
        output = self.root / 'consumer'; output.mkdir()
        (output / 'authored').write_text('preserved')
        with self.assertRaisesRegex(ValueError, 'Preserve'): self.unpack()
        self.assertEqual((output / 'authored').read_text(), 'preserved')
        alias = self.root / 'alias'; alias.symlink_to(output, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Linked'): self.unpack(output=alias / 'nested')
        self.assertFalse((output / 'nested').exists())

    def gate(self, applicable=True, missing=False):
        artifacts = self.root / ('gate-applicable' if applicable else 'gate-refused')
        artifacts.mkdir()
        if not missing:
            (artifacts / 'browser-packages.tar.gz').write_bytes(self.archive.read_bytes())
            (artifacts / 'browser-packages.json').write_text(json.dumps(self.receipt))
        with patch.object(GATE, 'ARTIFACTS', artifacts), patch.object(GATE, 'TESTS', self.source), \
             patch.object(GATE, 'runtime_transport', return_value=ARCHIVE), \
             patch.object(ARCHIVE.IDENTITY, 'toolchain', return_value=self.inputs if applicable else {**self.inputs, 'node_sha256': 'altered'}), \
             patch.object(GATE.COSTS, 'ROOT', self.root), patch.object(GATE.subprocess, 'run') as install:
            GATE.install_browser_runtime()
            decision = json.loads((artifacts / 'runtime-transport.json').read_text())
        return artifacts, decision, install

    def test_gate_uses_verified_tree_without_npm_install_and_keeps_execution_required(self):
        artifacts, decision, install = self.gate()
        install.assert_not_called()
        self.assertEqual(decision['status'], 'transported')
        self.assertIs(decision['browser_execution_required'], True)
        self.assertTrue((artifacts / 'node-runtime/node_modules/.bin/playwright').is_file())

    def test_inapplicable_and_missing_transport_perform_fresh_install(self):
        for missing in (False, True):
            if missing:
                (self.source / 'node_modules').unlink()
                # Each gate has its own artifacts owner.
                (self.root / 'gate-refused').rename(self.root / 'retained-refusal')
            artifacts, decision, install = self.gate(applicable=False, missing=missing)
            self.assertEqual(decision['status'], 'fresh_install')
            self.assertTrue(decision['reason'])
            self.assertEqual(install.call_args.args[0], ['npm', '--prefix', str(artifacts / 'node-runtime'), 'ci'])
            self.assertFalse((artifacts / 'node-runtime/node_modules').exists())


if __name__ == '__main__':
    unittest.main()
