from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def module():
    path = ROOT / 'shared/bijux-gitlab/execute.py'
    if not path.is_file():
        raise AssertionError('the generated pipeline requires its source-owned execution harness')
    return runpy.run_path(str(path))


class ExecutionHarnessTests(unittest.TestCase):
    def test_contract_test_child_runs_legacy_receipt_fixtures_without_inherited_ci_identity(self):
        from unittest.mock import patch
        execute = module()
        namespace = execute['execute_job'].__globals__
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            root = Path(directory)
            subprocess.run(['git','init','--quiet',str(root)],check=True)
            subprocess.run(['git','-C',str(root),'remote','add','origin','https://gitlab.com/bijux-oss/bijux-std.git'],check=True)
            identity = {'provider':'gitlab','server_url':'https://gitlab.com','project_id':'88948041',
                        'project_path':'bijux-oss/bijux-std','commit_sha':'a'*40,'pipeline_id':'123','job_id':'456'}
            native = {'GITLAB_CI':'true','CI_SERVER_URL':'https://gitlab.com','CI_PROJECT_ID':'88948041',
                      'CI_PROJECT_PATH':'bijux-oss/bijux-std','CI_PIPELINE_ID':'123','CI_JOB_ID':'456',
                      'CI_COMMIT_SHA':'a'*40,'PYTHONPATH':str(ROOT),'PATH':os.environ.get('PATH','')}
            representative = [sys.executable,'-B','-m','unittest',
                'tests.test_docs_publication_execution.PublicationExecutionTests.test_exact_parser_fixture_qualifies_only_verification_scope',
                'tests.test_docs_renderer_controls.RendererControlReceiptTests.test_real_native_events_and_complete_controlled_accounting_pass']
            with patch.dict(os.environ,native,clear=True), \
                    patch.object(execute['PIPELINE'],'job_contracts',return_value={'std / contracts':{'operation':'contracts','args':[]}}), \
                    patch.dict(namespace,{'validate_context':lambda *args:identity,'bootstrap_node':lambda *args:None,
                        'operation_commands':lambda *args,**kwargs:[representative]}), contextlib.redirect_stdout(io.StringIO()):
                result = execute['execute_job'](root,'std / contracts')
                self.assertEqual(os.environ['CI_JOB_ID'],'456')
            self.assertEqual(result['status'],'passed')
            self.assertEqual(result['ci_context'],identity)

    def test_contract_child_removes_provider_identity_and_read_tokens_only_from_its_copy(self):
        execute = module()
        self.assertTrue('operation_environment' in execute,'Contract tests need an explicit child environment boundary')
        original = {'GITLAB_CI':'true','CI_JOB_ID':'456','GITHUB_RUN_ID':'789',
                    'BIJUX_GITLAB_READ_TOKEN':'fixture-read-token','GH_TOKEN':'fixture-github-token',
                    'PATH':'/owned/bin','TMPDIR':'/owned/artifacts/process','VERIFICATION_MODE':'full'}
        child = execute['operation_environment']('contracts',original)
        self.assertEqual(child,{'PATH':'/owned/bin','TMPDIR':'/owned/artifacts/process','VERIFICATION_MODE':'full'})
        self.assertEqual(original['CI_JOB_ID'],'456')
        self.assertEqual(original['BIJUX_GITLAB_READ_TOKEN'],'fixture-read-token')

    def test_frontend_and_other_native_operations_keep_real_provider_environment(self):
        execute = module()
        self.assertTrue('operation_environment' in execute,'Contract tests need an explicit child environment boundary')
        original = {'GITLAB_CI':'true','CI_JOB_ID':'456','CI_PIPELINE_ID':'123','BIJUX_GITLAB_READ_TOKEN':'fixture-read-token'}
        for operation in ('fixtures','browser','renderer','catalogue','navigation','report','plan','standard','policy'):
            with self.subTest(operation=operation):
                self.assertIs(execute['operation_environment'](operation,original),original)

    def test_every_physical_job_has_a_native_argv_plan(self):
        execute = module()
        jobs = execute['PIPELINE'].job_contracts(ROOT)
        self.assertEqual(len(jobs), 78)
        for name, contract in jobs.items():
            with self.subTest(job=name):
                commands = execute['operation_commands'](ROOT, contract,
                    catalogue_python=ROOT / 'artifacts/catalogue-cpython/bin/python')
                self.assertTrue(commands)
                for command in commands:
                    self.assertIsInstance(command, list)
                    self.assertTrue(all(isinstance(part, str) and part for part in command))
                    self.assertNotEqual(command[:2], ['bash','-c'])
                    self.assertNotEqual(command[:2], ['sh','-c'])
                    self.assertFalse(any(part in {'--accepted-proof', '--selection-only', '--consumer-platform', '--package-container'}
                                         for part in command))

    def test_fixture_producer_preserves_real_native_packaging_without_docker(self):
        commands = module()['operation_commands'](ROOT, {'operation':'fixtures','args':[]})
        flattened = json.dumps(commands)
        self.assertIn('renderer_fingerprints.py', flattened)
        self.assertIn('contrast-generated', flattened)
        self.assertIn(['python3','-B','tests/bijux-docs/execution/browser_gate.py','prepare'], commands)
        self.assertNotIn('--package-container', flattened)
        self.assertNotIn('docker', flattened)

    def test_catalogue_uses_owned_interpreter_and_locked_make_targets(self):
        commands = module()['operation_commands'](ROOT, {'operation':'catalogue','args':['tracked-entrypoint']},
            catalogue_python=ROOT / 'artifacts/catalogue-cpython/bin/python')
        self.assertIn('ui-test-install-catalogue', json.dumps(commands))
        self.assertIn('ui-test-install-catalogue-default', json.dumps(commands))
        self.assertIn('UI_CATALOGUE_GROUP=tracked-entrypoint', json.dumps(commands))
        self.assertIn('UI_CATALOGUE_BASE_PYTHON=' + str(ROOT / 'artifacts/catalogue-cpython/bin/python'), json.dumps(commands))

    def test_unknown_operation_is_blocked(self):
        for operation in ('release', 'observe', 'retained-proof', 'unknown'):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'Unsupported'):
                module()['operation_commands'](ROOT, {'operation':operation,'args':[]})

    def test_node_archive_must_match_the_exact_official_manifest_member(self):
        verify = module()['verify_archive']
        data = b'actual archive bytes'
        name = 'node-v24.21.0-linux-x64.tar.xz'
        digest = hashlib.sha256(data).hexdigest()
        self.assertEqual(verify(data, (digest + '  ' + name + '\n').encode(), name), digest)
        for manifest in ((digest + '  another.tar.xz\n').encode(),
                         ('0' * 64 + '  ' + name + '\n').encode(),
                         ((digest + '  ' + name + '\n') * 2).encode()):
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                verify(data, manifest, name)

    def test_command_failure_retains_real_exit_and_closes_native_section(self):
        execute = module()
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as name:
            root = Path(name)
            receipt = {'commands': []}
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(subprocess.CalledProcessError):
                execute['run_command']([sys.executable, '-c', 'raise SystemExit(7)'], root, dict(os.environ), receipt)
            self.assertEqual(receipt['commands'][0]['exit_code'], 7)
            self.assertIn('section_start:', output.getvalue())
            self.assertIn('section_end:', output.getvalue())

    def test_result_flags_require_actual_success_for_every_required_physical_owner(self):
        execute = module()
        contracts = execute['PIPELINE'].job_contracts(ROOT)
        selected = {name:{'job_id':index,'raw_job':{'id':index,'status':'success','allow_failure':False}}
                    for index,(name,row) in enumerate(contracts.items(), 1)
                    if row['operation'] not in {'navigation','report'}}
        flags = execute['result_flags'](ROOT, {'status':'passed','selected_jobs':selected}, {'navigation','report'})
        self.assertEqual(flags['PLAN_RESULT'], 'success')
        self.assertEqual(flags['CHECK_RESULT'], 'success')
        self.assertEqual(flags['FAULT_BROWSER_RESULT'], 'success')
        self.assertEqual(flags['EXPECTED_FRONTEND'], 'true')
        for mutate in (lambda rows: rows.pop('std / standard'),
                       lambda rows: rows['std / standard']['raw_job'].update(status='failed'),
                       lambda rows: rows['std / standard']['raw_job'].update(allow_failure=True)):
            changed = json.loads(json.dumps(selected)); mutate(changed)
            with self.subTest(selected=changed.get('std / standard')), self.assertRaises(ValueError):
                execute['result_flags'](ROOT, {'status':'passed','selected_jobs':changed}, {'navigation','report'})

    def test_environment_creates_scratch_before_exporting_it_and_uses_artifact_caches(self):
        execute = module()
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as name:
            root = Path(name)
            env = execute['runtime_environment'](root, {'PATH':'/usr/bin'})
            self.assertTrue(Path(env['TMPDIR']).is_dir())
            for key in ('TMPDIR','PIP_CACHE_DIR','UV_CACHE_DIR','NPM_CONFIG_CACHE','PYTHONPYCACHEPREFIX'):
                self.assertTrue(Path(env[key]).is_relative_to(root / 'artifacts'))
            self.assertFalse(any(key.startswith('GITHUB_') for key in env))

    def test_context_rejects_mirror_stale_checkout_and_retained_modes_before_remote_changes(self):
        from unittest.mock import patch
        execute = module()
        sha = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        original = {'GITLAB_CI':'true','CI_SERVER_URL':'https://gitlab.com',
                    'CI_PROJECT_ID':'88948041','CI_PROJECT_PATH':'bijux-oss/bijux-std',
                    'CI_PROJECT_DIR':str(ROOT),'CI_COMMIT_SHA':sha,'CI_PIPELINE_ID':'123','CI_JOB_ID':'456',
                    'CI_JOB_NAME':'std / contracts','CI_PIPELINE_SOURCE':'push',
                    'CI_COMMIT_REF_NAME':'feature','CI_COMMIT_REF_PROTECTED':'false','VERIFICATION_MODE':'full'}
        with patch.dict(os.environ,original,clear=True):
            self.assertEqual(execute['validate_context'](ROOT,'std / contracts',original)['commit_sha'],sha)
        for key,value in [('CI_PROJECT_ID','1'), ('CI_COMMIT_SHA','a'*40),
                          ('CI_JOB_NAME','another job'), ('CI_PROJECT_DIR','/unrelated/checkout'),
                          ('VERIFICATION_MODE','retained'), ('CI_COMMIT_REF_PROTECTED','yes')]:
            environment = {**original,key:value}
            with self.subTest(key=key), patch.dict(os.environ,environment,clear=True), self.assertRaises(ValueError):
                execute['validate_context'](ROOT,'std / contracts',environment)

    def test_acceptance_records_only_admitted_actual_jobs_and_never_publication_success(self):
        execute = module()
        identity = {'provider':'gitlab','server_url':'https://gitlab.com',
                    'project_id':'88948041','project_path':'bijux-oss/bijux-std',
                    'commit_sha':'a'*40,'pipeline_id':'123','job_id':'999'}
        selected = {name:{'job_id':index,'raw_job':{'id':index,'name':name,'status':'success','allow_failure':False,
                     'pipeline':{'id':123,'project_id':88948041,'sha':'a'*40},'commit':{'id':'a'*40}}}
                    for index,(name,row) in enumerate(execute['PIPELINE'].job_contracts(ROOT).items(),1)
                    if row['operation'] != 'report'}
        admission = {'status':'passed','project_id':88948041,'pipeline_id':123,'commit_sha':'a'*40,'selected_jobs':selected}
        env={'CI_PIPELINE_SOURCE':'push','CI_COMMIT_REF_NAME':'main','CI_COMMIT_REF_PROTECTED':'true'}
        result = execute['acceptance_record'](ROOT,identity,env,admission)
        self.assertEqual(result['project_id'],88948041)
        self.assertEqual(result['validation']['jobs'],selected)
        self.assertEqual(result['publication'],{'status':'pending'})
        self.assertIs(result['ref_protected'],True)
        for changes in ({'commit_sha':'b'*40},{'pipeline_id':124},{'project_id':1},{'status':'failed'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                execute['acceptance_record'](ROOT,identity,env,{**admission,**changes})

    def test_failed_job_preserves_real_command_exit_and_never_logs_checkout_credentials(self):
        from unittest.mock import patch
        execute = module()
        namespace = execute['execute_job'].__globals__
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as name:
            root = Path(name)
            subprocess.run(['git','init','--quiet',str(root)],check=True)
            subprocess.run(['git','-C',str(root),'remote','add','origin',
                            'https://oauth2:inert-checkout-credential@gitlab.com/bijux-oss/bijux-std.git'],check=True)
            identity={'provider':'gitlab','server_url':'https://gitlab.com','project_id':'88948041',
                      'project_path':'bijux-oss/bijux-std','commit_sha':'a'*40,'pipeline_id':'123','job_id':'456'}
            jobs={'std / contracts':{'operation':'contracts','args':[]}}
            output=io.StringIO()
            with patch.object(execute['PIPELINE'],'job_contracts',return_value=jobs), \
                    patch.dict(namespace,{'validate_context':lambda *args:identity,
                        'bootstrap_node':lambda *args:None,
                        'operation_commands':lambda *args,**kwargs:[[sys.executable,'-c','raise SystemExit(7)']]}), \
                    contextlib.redirect_stdout(output), self.assertRaises(subprocess.CalledProcessError):
                execute['execute_job'](root,'std / contracts')
            receipt=json.loads((root/'artifacts/gitlab/jobs/456/runtime.json').read_text())
            self.assertEqual(receipt['status'],'failed')
            self.assertEqual(receipt['commands'][-1]['exit_code'],7)
            self.assertNotIn('inert-checkout-credential',output.getvalue())
            self.assertNotIn('inert-checkout-credential',json.dumps(receipt))
            origin=subprocess.check_output(['git','-C',str(root),'remote','get-url','origin'],text=True).strip()
            self.assertEqual(origin,'https://gitlab.com/bijux-oss/bijux-std.git')

    def test_aggregate_refuses_unadmitted_inputs_before_any_controller_command(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        execute=module(); namespace=execute['execute_job'].__globals__
        real_contracts=execute['PIPELINE'].job_contracts(ROOT)
        identity={'provider':'gitlab','server_url':'https://gitlab.com','project_id':'88948041',
                  'project_path':'bijux-oss/bijux-std','commit_sha':'a'*40,'pipeline_id':'123','job_id':'456'}
        def refused(*args,**kwargs):
            raise ValueError('native proof is unavailable')
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as name:
            root=Path(name)
            subprocess.run(['git','init','--quiet',str(root)],check=True)
            subprocess.run(['git','-C',str(root),'remote','add','origin','https://gitlab.com/bijux-oss/bijux-std.git'],check=True)
            with patch.object(execute['PIPELINE'],'job_contracts',return_value=real_contracts), \
                    patch.dict(namespace,{'validate_context':lambda *args:identity,
                        'bootstrap_node':lambda *args:None,
                        'source_module':lambda *args:SimpleNamespace(collect=refused)}), \
                    patch.dict(os.environ,{'CI_PIPELINE_SOURCE':'push','CI_COMMIT_REF_NAME':'feature',
                        'CI_COMMIT_REF_PROTECTED':'false'}), \
                    contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError,'native proof'):
                execute['execute_job'](root,'std / navigation')
            receipt=json.loads((root/'artifacts/gitlab/jobs/456/runtime.json').read_text())
            self.assertEqual(receipt['status'],'failed')
            self.assertEqual(len(receipt['commands']),1)
            self.assertEqual(receipt['commands'][0]['argv'][:3],['git','remote','set-url'])
            self.assertFalse((root/'artifacts/gitlab/acceptance/acceptance.json').exists())

    def test_report_preserves_the_native_required_registry_suite(self):
        commands=module()['operation_commands'](ROOT,{'operation':'report','args':[]})
        self.assertIn(['bash','shared/bijux-checks/scripts/run-bijux-check-suite.sh',
                       '--consumer','.bijux/checks.consumer.json',
                       '--artifacts-dir','artifacts/bijux-checks'],commands)
