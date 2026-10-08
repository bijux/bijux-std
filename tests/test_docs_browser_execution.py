"""Reject corrupted and unsafe cross-job browser fixture transfers."""
from __future__ import annotations

import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('browser_gate', ROOT / 'tests/bijux-docs/execution/browser_gate.py')
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class FixtureTransferTests(unittest.TestCase):
    def bundle(self, root: Path, name: str, kind: bytes = tarfile.REGTYPE) -> None:
        archive = root / 'browser-fixtures.tar.gz'
        with tarfile.open(archive, 'w:gz') as bundle:
            entry = tarfile.TarInfo(name)
            entry.type = kind
            entry.linkname = '../../outside' if kind == tarfile.SYMTYPE else ''
            body = b'exact rendered bytes'
            entry.size = len(body) if kind == tarfile.REGTYPE else 0
            bundle.addfile(entry, io.BytesIO(body) if entry.size else None)
        (root / 'browser-fixtures.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '\n')

    def test_exact_fixture_bytes_are_portable(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            root = Path(directory)
            self.bundle(root, 'generated/site/index.html')
            with patch.object(GATE, 'ARTIFACTS', root):
                GATE.unpack()
            self.assertEqual((root / 'generated/site/index.html').read_bytes(), b'exact rendered bytes')

    def test_archive_corruption_fails_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            root = Path(directory)
            self.bundle(root, 'generated/site/index.html')
            with (root / 'browser-fixtures.tar.gz').open('ab') as stream:
                stream.write(b'changed')
            with patch.object(GATE, 'ARTIFACTS', root), self.assertRaisesRegex(ValueError, 'digest mismatch'):
                GATE.unpack()
            self.assertFalse((root / 'generated').exists())

    def test_path_escape_and_links_are_rejected(self) -> None:
        for name, kind in [('generated/../../outside', tarfile.REGTYPE), ('/outside', tarfile.REGTYPE), ('generated/site/link', tarfile.SYMTYPE), ('inventories/fabricated.json', tarfile.REGTYPE)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
                root = Path(directory)
                self.bundle(root, name, kind)
                with patch.object(GATE, 'ARTIFACTS', root), self.assertRaisesRegex(ValueError, 'Unexpected'):
                    GATE.unpack()
                self.assertFalse((root / 'generated').exists())

    def test_missing_shard_retains_failed_aggregate(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            root = Path(directory)
            with patch.object(GATE, 'ARTIFACTS', root), self.assertRaisesRegex(ValueError, 'Missing, duplicate'):
                GATE.aggregate()
            self.assertIn('"status": "failed"', (root / 'navigation-qualification.json').read_text())


if __name__ == '__main__':
    unittest.main()
