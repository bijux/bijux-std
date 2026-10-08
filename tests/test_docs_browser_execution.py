"""Reject corrupted and unsafe cross-job browser fixture transfers."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
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
        transport = GATE.fixture_transport()
        producer = root / 'producer'
        body = b'exact rendered bytes'
        for directory in GATE.fixture_roots():
            fixture = producer / directory
            (fixture / 'site').mkdir(parents=True)
            (fixture / 'site/index.html').write_bytes(body)
            manifest = {'site_files': {'index.html': hashlib.sha256(body).hexdigest()},
                        'source_files': {'source.css': hashlib.sha256(b'source').hexdigest()}}
            (fixture / 'manifest.json').write_text(json.dumps(manifest))
        archive = root / 'browser-fixtures.tar.gz'
        transport.pack(producer, GATE.fixture_roots(), archive)
        if name != 'generated/site/index.html' or kind != tarfile.REGTYPE:
            with tarfile.open(archive) as bundle:
                members = [(entry.name, bundle.extractfile(entry).read(), entry.type) for entry in bundle]
            if kind == tarfile.REGTYPE:
                index = json.loads(members[0][1])
                index['files'][name] = index['files'].pop('generated/site/index.html')
                members[0] = ('index.json', json.dumps(index).encode(), tarfile.REGTYPE)
            else:
                members[1] = (members[1][0], b'', kind)
            with tarfile.open(archive, 'w:gz', format=tarfile.USTAR_FORMAT) as bundle:
                for path, data, entry_kind in members:
                    entry = tarfile.TarInfo(path)
                    entry.type = entry_kind
                    entry.linkname = '../../outside' if entry_kind == tarfile.SYMTYPE else ''
                    entry.size = len(data) if entry_kind == tarfile.REGTYPE else 0
                    bundle.addfile(entry, io.BytesIO(data) if entry.size else None)
        (root / 'browser-fixtures.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + chr(10))

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
                with patch.object(GATE, 'ARTIFACTS', root), self.assertRaisesRegex(ValueError, 'fixture path|Unexpected'):
                    GATE.unpack()
                self.assertFalse((root / 'generated').exists())

    def test_missing_shard_retains_failed_aggregate(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            root = Path(directory)
            with patch.object(GATE, 'ARTIFACTS', root), self.assertRaisesRegex(ValueError, 'Missing, duplicate'):
                GATE.aggregate()
            self.assertIn('"status": "failed"', (root / 'navigation-qualification.json').read_text())

    def test_failed_job_cannot_leave_passing_final_evidence(self) -> None:
        for name in ('FIXTURE_RESULT', 'BROWSER_RESULT'):
            with self.subTest(job=name), tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
                root = Path(directory)
                with patch.object(GATE, 'ARTIFACTS', root), patch.dict(GATE.os.environ, {name: 'failure'}), self.assertRaisesRegex(ValueError, 'required fixture/browser job'):
                    GATE.aggregate()
                self.assertIn('"status": "failed"', (root / 'navigation-qualification.json').read_text())

    def test_producer_observation_and_workflow_are_bound(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            root = Path(directory)
            observation = {'source': {'sha': 'a' * 40}, 'verification_only': True, 'admission_created': False}
            paths = ['browser-fixtures.tar.gz', 'renderer-source-observation.json'] + [f'inventories/{suite}.json' for suite in GATE.SUITES]
            for name in paths:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(observation) if name == 'renderer-source-observation.json' else 'immutable artifact')
            receipt = {'source_head': 'a' * 40, 'workflow_run_id': None, 'workflow_attempt': None,
                       'artifact_digests': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in paths}}
            (root / 'producer-envelope.json').write_text(json.dumps(receipt))
            with patch.object(GATE, 'ARTIFACTS', root), patch.object(GATE.subprocess, 'check_output', return_value='a' * 40), patch.dict(GATE.os.environ, {}, clear=True):
                self.assertEqual(GATE.verify_producer_envelope(), receipt)
                (root / 'renderer-source-observation.json').write_text('changed observer')
                with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                    GATE.verify_producer_envelope()
                receipt['workflow_attempt'] = 'previous attempt'
                (root / 'producer-envelope.json').write_text(json.dumps(receipt))
                with self.assertRaisesRegex(ValueError, 'workflow/candidate identity mismatch'):
                    GATE.verify_producer_envelope()


if __name__ == '__main__':
    unittest.main()
