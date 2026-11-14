"""Keep source-owned artifact paths and receipt executors bound to physical jobs."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch

from tests.gitlab_evidence.test_jobs import EVIDENCE, HEAD, ROOT, job, load
from tests.gitlab_evidence.test_transport import archive
import stat

CONTEXT = {'provider': 'gitlab', 'server_url': 'https://gitlab.com', 'project_id': '17',
           'project_path': 'bijux/bijux-std', 'pipeline_id': '30', 'job_id': '99', 'commit_sha': HEAD}


class SourceOwnedCollectionTests(unittest.TestCase):
    def module(self):
        self.assertTrue((EVIDENCE / 'collect.py').is_file(), 'Native artifact collection is missing')
        return load('collect')

    def qualify(self, files, *, operation='fixtures', args=(), paths=None):
        contract = {'operation': operation, 'args': list(args), 'paths': paths or ['artifacts/bijux-docs/producer-envelope.json']}
        return self.module().qualify_members(ROOT, contract=contract, owner_job=job(), files=files,
            selected_jobs={'std / navigation fixtures': {'job_id': 11}, 'other': {'job_id': 12}}, context=CONTEXT)

    def test_source_owned_member_and_actual_executor_pass(self):
        identity = {**CONTEXT, 'job_id': '11'}
        data = json.dumps({'source_head': HEAD, 'ci_context': identity}).encode()
        result = self.qualify({'artifacts/bijux-docs/producer-envelope.json': data,
                               'artifacts/gitlab/jobs/11/job.json': b'{}'})
        self.assertEqual(result['artifacts/bijux-docs/producer-envelope.json'], hashlib.sha256(data).hexdigest())

    def test_unowned_path_traversal_and_another_job_folder_are_refused(self):
        for name in ('../README.md', 'shared/owned.py', 'artifacts/bijux-docs/foreign.json',
                     'artifacts/gitlab/jobs/12/job.json', 'artifacts/bijux-docs/../foreign'):
            with self.subTest(name=name), self.assertRaises(ValueError): self.qualify({name: b'{}'})

    def test_cross_job_or_pipeline_receipt_cannot_claim_uploading_job(self):
        for changes in ({'job_id': '12'}, {'pipeline_id': '31'}, {'commit_sha': 'b' * 40}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.qualify({'artifacts/bijux-docs/producer-envelope.json':
                              json.dumps({'ci_context': {**CONTEXT, 'job_id': '11', **changes}}).encode()})

    def test_browser_job_cannot_upload_another_group_or_engine_receipt(self):
        own = 'artifacts/bijux-docs/shards/navigation-phone-chromium/receipt.json'
        self.qualify({own: b'{}'}, operation='browser', args=['navigation-phone', 'chromium'], paths=['artifacts/bijux-docs/shards'])
        for name in ('artifacts/bijux-docs/shards/navigation-phone-firefox/receipt.json',
                     'artifacts/bijux-docs/shards/history-chromium/receipt.json'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.qualify({name: b'{}'}, operation='browser', args=['navigation-phone', 'chromium'], paths=['artifacts/bijux-docs/shards'])

    def test_catalogue_job_cannot_upload_another_entrypoint_owners_material(self):
        module = self.module()
        pipeline = module.load_path(ROOT / 'shared/bijux-gitlab/pipeline.py', 'catalogue_ownership_contract')
        contract = pipeline.job_contracts(ROOT)['std / catalogue typed-entrypoint']
        self.qualify({'artifacts/catalogue-entrypoint-tests/typed-entrypoint.json': b'{}'},
                     operation='catalogue', args=['typed-entrypoint'], paths=contract['paths'])
        for name in ('artifacts/catalogue-entrypoint-tests/tracked-entrypoint.json',
                     'artifacts/catalogue-native-sources/unowned.json'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.qualify({name:b'{}'}, operation='catalogue', args=['typed-entrypoint'], paths=contract['paths'])

    def test_merging_only_reuses_identical_bytes_and_preserves_existing_files(self):
        module = self.module()
        owner = ROOT / 'artifacts/qualification/gitlab-evidence'; owner.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=owner) as folder:
            root = Path(folder); seen = {}
            module.merge_files(root, {'artifacts/result.json': b'original'}, seen=seen)
            module.merge_files(root, {'artifacts/result.json': b'original'}, seen=seen)
            with self.assertRaises(ValueError): module.merge_files(root, {'artifacts/result.json': b'other'}, seen=seen)
            self.assertEqual((root / 'artifacts/result.json').read_bytes(), b'original')

    def test_report_collects_only_source_owned_successful_jobs_and_requires_frontend_script_section(self):
        module = self.module()
        owner = ROOT / 'artifacts/qualification/gitlab-evidence'; owner.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=owner) as folder:
            root = Path(folder)
            package = root / 'shared/bijux-gitlab'; package.mkdir(parents=True)
            (root / '.gitignore').write_text('artifacts/\n')
            (package / 'pipeline.py').write_text("def job_contracts(root):\n    return {'producer': {'operation':'fixtures','frontend':True,'args':[],'paths':['artifacts/result.json']}, 'commands': {'operation':'commands','frontend':True,'args':[],'paths':['artifacts/commands.json']}, 'report': {'operation':'report','frontend':False,'args':[],'paths':[]}}\n")
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            subprocess.run(['git', '-C', str(root), 'add', '.gitignore', 'shared/bijux-gitlab/pipeline.py'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=bijux', '-c', 'user.email=tests@example.invalid', 'commit', '-qm', 'test(ci): retain source job ownership'], check=True)
            head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
            producer = job(name='producer', pipeline={'id':30,'project_id':17,'sha':head}, commit={'id':head})
            caller = job(99, 'report', status='running', pipeline={'id':30,'project_id':17,'sha':head}, commit={'id':head})
            commands = job(12, 'commands', pipeline={'id':30,'project_id':17,'sha':head}, commit={'id':head})
            class API:
                observations = []
                marker = True
                parallel_required = False
                barrier = Barrier(2)
                inventories = 0
                retry_during_admission = False
                def pipeline_jobs(self, pipeline_id):
                    self.inventories += 1
                    rows = [copy.deepcopy(producer), copy.deepcopy(commands), copy.deepcopy(caller)]
                    if self.retry_during_admission and self.inventories % 2 == 0:
                        rows.append({**copy.deepcopy(producer), 'id': 111, 'status': 'failed'})
                    return rows
                def job(self, identifier, **kwargs): return copy.deepcopy(caller if identifier == 99 else producer if identifier == 11 else commands)
                def artifact(self, identifier, **kwargs):
                    if self.parallel_required: self.barrier.wait(timeout=2)
                    return archive([('artifacts/result.json' if identifier == 11 else 'artifacts/commands.json', b'{}', stat.S_IFREG | 0o644)])
                def trace(self, identifier, **kwargs):
                    return b'\x1b[0Ksection_start:1794657601:step_script\r\x1b[0K\n\x1b[0Ksection_end:1794657621:step_script\r\x1b[0K' if self.marker else b'plain output'
            api = API()
            env = {'GITLAB_CI':'true','CI_SERVER_URL':'https://gitlab.com','CI_PROJECT_ID':'17',
                   'CI_PROJECT_PATH':'bijux/bijux-std','CI_PIPELINE_ID':'30','CI_JOB_ID':'99','CI_COMMIT_SHA':head}
            with patch.dict(os.environ, env, clear=True), patch.object(module.API, 'GitLabAPI', return_value=api):
                admitted = module.collect(root, exclude_operations={'report'})
                self.assertEqual(admitted['status'], 'passed')
                self.assertEqual((root / 'artifacts/result.json').read_bytes(), b'{}')
                api.marker = False
                with self.assertRaisesRegex(ValueError, 'step_script'):
                    module.collect(root, exclude_operations={'report'})
                api.marker = True
                api.parallel_required = True
                self.assertEqual(module.collect(root, exclude_operations={'report'})['status'], 'passed')
                api.inventories = 0
                api.retry_during_admission = True
                with self.assertRaisesRegex(ValueError, 'Latest required job'):
                    module.collect(root, exclude_operations={'report'})
