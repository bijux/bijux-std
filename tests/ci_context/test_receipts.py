"""Bind fresh native evidence to separate producer and executor GitLab jobs."""
import hashlib
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests.ci_context.test_identity import EXECUTION, GITLAB, IDENTITY, ROOT, load


class FreshReceiptIdentityTests(unittest.TestCase):
    def setUp(self):
        owner = ROOT / 'artifacts/qualification/ci-context'
        owner.mkdir(parents=True, exist_ok=True)
        scratch = tempfile.TemporaryDirectory(dir=owner)
        self.addCleanup(scratch.cleanup)
        self.output = Path(scratch.name)
        self.head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        self.identity = {**IDENTITY, 'commit_sha': self.head}
        environment = patch.dict(os.environ, {**GITLAB, 'CI_COMMIT_SHA': self.head, 'PATH': os.environ.get('PATH', '')}, clear=True)
        environment.start(); self.addCleanup(environment.stop)

    def producer(self):
        gate = load('browser_gate')
        paths = ['browser-fixtures.tar.gz', 'browser-packages.tar.gz', 'browser-packages.json',
                 'renderer-source-observation.json'] + [f'inventories/{suite}.json' for suite in (*gate.SUITES, gate.PERSISTED_SUITE)]
        for name in paths:
            path = self.output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'source': {'sha': self.head}, 'verification_only': True, 'admission_created': False}))
        envelope = {'source_head': self.head, 'ci_context': {**self.identity, 'job_id': '111'},
                    'partition_registry_sha256': hashlib.sha256(gate.PARTITIONS.REGISTRY_PATH.read_bytes()).hexdigest(),
                    'batch_registry_sha256': hashlib.sha256(gate.OWNERSHIP.REGISTRY_PATH.read_bytes()).hexdigest(),
                    'artifact_digests': {name: hashlib.sha256((self.output / name).read_bytes()).hexdigest() for name in paths}}
        (self.output / 'producer-envelope.json').write_text(json.dumps(envelope))
        return gate, envelope

    def test_fresh_producer_keeps_its_original_job_and_all_physical_input_checks(self):
        gate, producer = self.producer()
        with patch.object(gate, 'ARTIFACTS', self.output):
            self.assertEqual(gate.verify_producer_envelope(), producer)
            (self.output / 'browser-packages.tar.gz').write_bytes(b'corrupt transport')
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                gate.verify_producer_envelope()

    def test_foreign_pipeline_producer_is_refused(self):
        gate, producer = self.producer()
        producer['ci_context']['pipeline_id'] = 'foreign'
        (self.output / 'producer-envelope.json').write_text(json.dumps(producer))
        with patch.object(gate, 'ARTIFACTS', self.output), self.assertRaises(ValueError):
            gate.verify_producer_envelope()

    def test_execution_record_keeps_producer_and_executor_jobs_distinct(self):
        _, producer = self.producer()
        controllers = load('workflow_controllers')
        folder = self.output / 'persisted-reader'
        folder.mkdir()
        (folder / 'receipt.json').write_text('{"status":"passed"}')
        with patch.object(controllers, 'ARTIFACTS', self.output):
            record = controllers.record_execution(folder, 'persisted', producer)
        self.assertIsNotNone(record, 'GitLab successful native execution must write its declaration')
        self.assertEqual(record['executor']['ci_context'], self.identity)
        self.assertEqual(record['producer']['ci_context']['job_id'], '111')
        self.assertEqual(record['files_sha256'], {'receipt.json': hashlib.sha256(b'{"status":"passed"}').hexdigest()})
        self.assertNotIn('workflow_attempt', record['executor'])

    def test_renderer_receipt_verifies_native_body_from_another_job_in_same_pipeline(self):
        from tests.test_docs_renderer_controls import RendererControlReceiptTests, CONTROLS
        fixture = RendererControlReceiptTests()
        self.addCleanup(fixture.doCleanups); fixture.setUp()
        fixture.receipt['workflow'] = {**self.identity, 'job_id': '222'}
        fixture.write()
        self.assertEqual(CONTROLS.verify(fixture.root, fixture.source)['workflow']['job_id'], '222')
        fixture.receipt['python_cases'].pop(); fixture.write()
        with self.assertRaises(ValueError):
            CONTROLS.verify(fixture.root, fixture.source)

    def test_catalogue_keeps_original_executor_and_complete_cases(self):
        from tests.test_catalogue_execution import CatalogueExecution, gate
        fixture = CatalogueExecution(); fixture.setUp()
        fixture.receipt['workflow'] = {**self.identity, 'job_id': '333'}
        gate.verify(fixture.receipt, 'source', fixture.source, fixture.runtime)
        fixture.receipt['executed_ids'].pop()
        with self.assertRaises(ValueError):
            gate.verify(fixture.receipt, 'source', fixture.source, fixture.runtime)

    def test_renderer_group_union_preserves_each_original_job(self):
        from tests.test_docs_renderer_controls import RendererControlReceiptTests, CONTROLS
        fixture = RendererControlReceiptTests()
        self.addCleanup(fixture.doCleanups); fixture.setUp()
        grouped = fixture.grouped_receipts()
        for number, group in enumerate(CONTROLS.GROUPS):
            path = grouped / group / 'renderer-controls.json'
            receipt = json.loads(path.read_text())
            receipt['workflow'] = {**self.identity, 'job_id': str(900 + number)}
            path.write_text(json.dumps(receipt))
        result = CONTROLS.verify_groups(grouped, fixture.source)
        self.assertEqual(len({receipt['workflow']['job_id'] for receipt in result['groups'].values()}), len(CONTROLS.GROUPS))

    def test_fault_aggregate_retains_each_job_and_requalifies_actual_junit(self):
        from tests.test_docs_frontend_faults import FrontendFaultReceiptTests
        fixture = FrontendFaultReceiptTests()
        self.addCleanup(fixture.doCleanups); fixture.setUp()
        faults = load('frontend_faults')
        current = fixture.pair[0]['source_identity']
        projects = [{'name': engine + '-phone', 'engine': engine, 'count': 4} for engine in faults.ENGINES]
        cases = [{'id': engine + '-' + str(index), 'project': engine + '-phone', 'title': title}
                 for engine in faults.ENGINES for index, title in enumerate(faults.FAULT_CONTROLS)]
        inventory = {'qualification_scope': 'fault-controls', 'source_identity': current,
                     'fixture_identity': fixture.pair[0]['fixture_identity'], 'canonical_projects': projects, 'cases': cases}
        for number, engine in enumerate(faults.ENGINES):
            folder = self.output / engine; folder.mkdir()
            (folder / 'inventory.json').write_text(json.dumps(inventory))
            for mode, original in zip(('clean', 'fault'), fixture.pair):
                destination = folder / mode; destination.mkdir()
                report = copy.deepcopy(original)
                report.update(qualification_scope='fault-controls', canonical_projects=projects,
                              assigned_project_names=[engine + '-phone'],
                              expected_cases=[case for case in cases if case['project'] == engine + '-phone'],
                              projects={engine + '-phone': {'expected': 4, 'executed': 4, 'passed': 4, 'failed': 0, 'skipped': 0}})
                for index, row in enumerate(report['results']):
                    row.update(case_id=engine + '-' + str(index), project=engine + '-phone')
                xml = Path(original['junit']['path']).read_text()
                if mode == 'clean':
                    import xml.etree.ElementTree as ET
                    document = ET.fromstring(xml)
                    suite = document.find('testsuite'); suite.set('hostname', engine + '-phone'); suite.set('tests', '4')
                    for case, title in zip(suite.findall('testcase'), faults.FAULT_CONTROLS):
                        case.set('name', title)
                    xml = ET.tostring(document, encoding='unicode')
                (destination / 'junit.xml').write_text(xml)
                report['junit'] = {'path': 'junit.xml', 'sha256': hashlib.sha256(xml.encode()).hexdigest()}
                (destination / 'qualification.json').write_text(json.dumps(report))
            receipt = {'schema': 1, 'source': current, 'status': 'passed',
                       'ci_context': {**self.identity, 'job_id': str(700 + number)}, 'files': faults.hashes(folder)}
            (folder / 'receipt.json').write_text(json.dumps(receipt))
        public = self.output / 'public'; public.mkdir()
        (public / 'receipt.json').write_text(json.dumps({'schema': 1, 'source': current, 'status': 'passed',
            'ci_context': {**self.identity, 'job_id': '800'}, 'files': {}}))
        result = faults.qualify(original_source=current, output=self.output)
        self.assertEqual(result['clean_browser_cases'], 12)
        self.assertEqual(result['aggregate_rejection'], 'Failed or non-shard evidence')
        (self.output / 'chromium/clean/junit.xml').write_text('changed physical evidence')
        with self.assertRaises(ValueError):
            faults.qualify(original_source=current, output=self.output)
