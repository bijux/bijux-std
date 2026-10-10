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
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
            configuration = b'site_name: Exact reader\n'
            config = fixture / 'inputs/hub/mkdocs.yml'
            config.parent.mkdir(parents=True)
            config.write_bytes(configuration)
            manifest['scenarios'] = [{'identity': 'bijux', 'route': '/', 'kind': 'hub',
                'configuration': {'path': 'inputs/hub/mkdocs.yml',
                    'sha256': transport.digest(configuration), 'bytes': len(configuration)}}]
            manifest['configurations_sha256'] = transport.configurations_digest(manifest['scenarios'])
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
            self.assertFalse((root / 'generated/inputs').exists())

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
        for name in ('FIXTURE_RESULT', 'BROWSER_RESULT', 'COMMAND_RESULT', 'RENDERER_RESULT', 'PERSISTED_RESULT'):
            with self.subTest(job=name), tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
                root = Path(directory)
                with patch.object(GATE, 'ARTIFACTS', root), patch.dict(GATE.os.environ, {name: 'failure'}), self.assertRaisesRegex(ValueError, 'required fixture/browser job'):
                    GATE.aggregate()
                self.assertIn('"status": "failed"', (root / 'navigation-qualification.json').read_text())

    def test_producer_observation_and_workflow_are_bound(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            root = Path(directory)
            observation = {'source': {'sha': 'a' * 40}, 'verification_only': True, 'admission_created': False}
            paths = ['browser-fixtures.tar.gz', 'renderer-source-observation.json'] + [f'inventories/{suite}.json' for suite in (*GATE.SUITES, GATE.PERSISTED_SUITE)]
            for name in paths:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(observation) if name == 'renderer-source-observation.json' else 'immutable artifact')
            receipt = {'source_head': 'a' * 40, 'workflow_run_id': None, 'workflow_attempt': None,
                       'partition_registry_sha256': hashlib.sha256(GATE.PARTITIONS.REGISTRY_PATH.read_bytes()).hexdigest(),
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


class RecoveryProducerOrderTests(unittest.TestCase):
    """Exercise cold entry ordering without claiming API or browser qualification."""

    def materialize(self, root: Path) -> None:
        profiles = {}
        for entries in GATE.PARTITIONS.REGISTRY['groups'].values():
            for entry in entries:
                profiles.setdefault(entry['suite'], set()).add(entry.get('profile', 'phone'))
        for suite, selected in profiles.items():
            projects = [{'name': f'{engine}-{profile}', 'engine': engine, 'count': 1}
                        for engine in GATE.ENGINES for profile in sorted(selected)]
            path = root / 'inventories' / f'{suite}.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'canonical_projects': projects,
                'cases': [{'id': suite + '/' + project['name'], 'project': project['name']}
                          for project in projects]}))
        (root / 'producer-envelope.json').write_text('{"controlled": "producer"}')

    @contextmanager
    def execution(self, *, recovery=True, collection_error=None, verification_error=None):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory, ExitStack() as stack:
            root = Path(directory)
            events = []
            member = object()
            collection = SimpleNamespace(producer=member)
            original_plan = GATE.partition_plan

            def collect(stage, *, caller):
                self.assertTrue(caller.startswith('browser-'))
                events.append('collect')
                self.assertEqual(stage, 'producer')
                self.assertFalse((root / 'inventories').exists())
                if collection_error:
                    raise ValueError(collection_error)
                self.materialize(root)
                return collection

            def verify(admission):
                events.append('verify')
                self.assertIs(admission, member if recovery else None)
                self.assertTrue((root / 'producer-envelope.json').is_file())
                if verification_error:
                    raise ValueError(verification_error)
                return {'controlled': 'verified producer'}

            def plan():
                events.append('partition')
                return original_plan()

            def native(*args, **kwargs):
                events.append('native')
                return SimpleNamespace(returncode=0)

            controllers = SimpleNamespace(recovery=lambda: recovery,
                collect=Mock(side_effect=collect), record_execution=Mock(side_effect=lambda *a: events.append('record')))
            if not recovery:
                self.materialize(root)
            stack.enter_context(patch.dict(GATE.os.environ, {}, clear=True))
            stack.enter_context(patch.object(GATE, 'ARTIFACTS', root))
            loader = stack.enter_context(patch.object(GATE, 'workflow_controllers', return_value=controllers))
            verifier = stack.enter_context(patch.object(GATE, 'verify_producer_envelope', side_effect=verify))
            planner = stack.enter_context(patch.object(GATE, 'partition_plan', side_effect=plan))
            unpack = stack.enter_context(patch.object(GATE, 'unpack', side_effect=lambda: events.append('unpack')))
            install = stack.enter_context(patch.object(GATE, 'install_browser_runtime', side_effect=lambda: events.append('install')))
            runner = stack.enter_context(patch.object(GATE.subprocess, 'run', side_effect=native))
            yield SimpleNamespace(root=root, events=events, controllers=controllers,
                loader=loader, verifier=verifier, planner=planner, unpack=unpack, install=install, runner=runner)

    def test_cold_recovery_materializes_verified_producer_before_actual_partition_reads(self):
        with self.execution() as observed:
            self.assertFalse((observed.root / 'inventories').exists())
            GATE.run('navigation-destinations', 'firefox')
            self.assertEqual(observed.events[:5], ['collect', 'verify', 'partition', 'unpack', 'install'])
            self.assertEqual(observed.events[5:], ['native', 'record'])
            observed.controllers.collect.assert_called_once_with('producer', caller='browser-navigation-destinations-firefox')

    def test_first_attempt_verifies_downloaded_producer_without_api_collection(self):
        with self.execution(recovery=False) as observed:
            GATE.run('navigation-destinations', 'chromium')
            observed.controllers.collect.assert_not_called()
            self.assertEqual(observed.events[:4], ['verify', 'partition', 'unpack', 'install'])
            self.assertEqual(observed.events[4:], ['native', 'record'])

    def test_admission_failure_prevents_inventory_reads_unpack_install_and_native_execution(self):
        with self.execution(collection_error='Controlled producer admission refused') as observed:
            with self.assertRaisesRegex(ValueError, 'producer admission refused'):
                GATE.run('navigation-destinations', 'firefox')
            self.assertEqual(observed.events, ['collect'])
            for operation in (observed.verifier, observed.planner, observed.unpack, observed.install, observed.runner):
                operation.assert_not_called()
            self.assertFalse((observed.root / 'inventories').exists())
            observed.controllers.record_execution.assert_not_called()

    def test_producer_verification_failure_prevents_partition_and_native_execution(self):
        with self.execution(verification_error='Controlled producer digest refused') as observed:
            with self.assertRaisesRegex(ValueError, 'producer digest refused'):
                GATE.run('navigation-destinations', 'webkit')
            self.assertEqual(observed.events, ['collect', 'verify'])
            for operation in (observed.planner, observed.unpack, observed.install, observed.runner):
                operation.assert_not_called()
            observed.controllers.record_execution.assert_not_called()

    def test_invalid_assignment_refuses_before_collection_or_cold_inventory_reads(self):
        for group, engine in [('unknown-group', 'firefox'), ('navigation-destinations', 'unknown-engine')]:
            with self.subTest(group=group, engine=engine), self.execution() as observed:
                with self.assertRaisesRegex(ValueError, 'Unknown assigned'):
                    GATE.run(group, engine)
                self.assertEqual(observed.events, [])
                observed.loader.assert_not_called()
                observed.runner.assert_not_called()

    def test_external_selection_refuses_before_collection_and_native_execution(self):
        for variable in ('BIJUX_UI_BROWSER_ENGINE', 'BIJUX_UI_PROJECTS', 'BIJUX_UI_PROFILE'):
            with self.subTest(variable=variable), self.execution() as observed:
                with patch.dict(GATE.os.environ, {variable: 'external'}), self.assertRaisesRegex(ValueError, 'assigned group/engine'):
                    GATE.run('navigation-destinations', 'firefox')
                self.assertEqual(observed.events, [])
                observed.loader.assert_not_called()
                observed.runner.assert_not_called()

    def test_verified_materialization_still_requires_actual_partition_coverage(self):
        with self.execution() as observed:
            collect = observed.controllers.collect.side_effect
            def incomplete(stage, *, caller):
                result = collect(stage, caller=caller)
                path = observed.root / 'inventories/navigation-destinations.json'
                inventory = json.loads(path.read_text())
                inventory['cases'].pop()
                path.write_text(json.dumps(inventory))
                return result
            observed.controllers.collect.side_effect = incomplete
            with self.assertRaisesRegex(ValueError, 'case/project mismatch|case count mismatch'):
                GATE.run('navigation-destinations', 'firefox')
            self.assertEqual(observed.events, ['collect', 'verify', 'partition'])
            observed.unpack.assert_not_called()
            observed.install.assert_not_called()
            observed.runner.assert_not_called()
            observed.controllers.record_execution.assert_not_called()


if __name__ == '__main__':
    unittest.main()
