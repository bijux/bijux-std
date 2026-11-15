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
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def module():
    path = ROOT / 'shared/bijux-gitlab/execute.py'
    if not path.is_file():
        raise AssertionError('the generated pipeline requires its source-owned execution harness')
    return runpy.run_path(str(path))


class ExecutionHarnessTests(unittest.TestCase):
    def test_contracts_use_owned_standalone_python_and_hashlocked_catalogue_environment(self):
        from unittest.mock import patch
        execute=module()
        self.assertTrue('bootstrap_contracts_python' in execute,'Contracts need their supported owned Python runtime')
        namespace=execute['bootstrap_contracts_python'].__globals__
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as directory:
            root=Path(directory)
            standalone=root/'artifacts/standalone/bin/python';standalone.parent.mkdir(parents=True)
            standalone.write_bytes(b'owned standalone interpreter fixture')
            lock=root/'tests/bijux-docs/catalogue/requirements.lock.txt';lock.parent.mkdir(parents=True)
            lock.write_bytes(b'owned hash-locked dependency fixture\n')
            selected=root/'artifacts/gitlab/contracts/python/bin/python'
            receipt={'commands':[],'runtimes':{'python':{'version':'3.11.2'},
                'standalone_python':{'prefix':str(standalone.parents[1])}}}
            environment={'PATH':'/existing/node/bin:/usr/bin'}
            def run(argv,working,child,record,*,capture=False):
                if argv[:2]==['make','ui-test-install-catalogue']:
                    self.assertIn('UI_CATALOGUE_BASE_PYTHON='+str(standalone),argv)
                    self.assertIn('UI_CATALOGUE_PYTHON_DIR='+str(selected.parents[1]),argv)
                    selected.parent.mkdir(parents=True);selected.symlink_to(standalone)
                    return None
                self.assertEqual(argv[0],str(selected))
                return json.dumps({'version':[3,14,4],'implementation':'cpython','executable':str(selected),
                    'prefix':str(selected.parents[1]),'base_prefix':str(standalone.parents[1]),
                    'data_filter':True,'yaml_version':'6.0.3','yaml_file':str(selected.parents[1]/'lib/python3.14/site-packages/yaml/__init__.py')})
            with patch.dict(namespace,{'run_command':run}):
                result=execute['bootstrap_contracts_python'](root,environment,receipt,standalone)
            self.assertEqual(result,selected)
            self.assertTrue(environment['PATH'].startswith(str(selected.parent)+os.pathsep))
            self.assertEqual(receipt['runtimes']['python']['version'],'3.11.2')
            child=receipt['runtimes']['contracts_python']
            self.assertEqual(child['version'],[3,14,4])
            self.assertTrue(child['data_filter'])
            self.assertEqual(child['executable_sha256'],hashlib.sha256(b'owned standalone interpreter fixture').hexdigest())
            self.assertEqual(child['lock_sha256'],hashlib.sha256(lock.read_bytes()).hexdigest())

    def test_contract_runtime_rejects_unsupported_python_or_missing_data_filter(self):
        from unittest.mock import patch
        execute=module()
        self.assertTrue('bootstrap_contracts_python' in execute,'Contracts need their supported owned Python runtime')
        namespace=execute['bootstrap_contracts_python'].__globals__
        for change in ({'version':[3,11,2]},{'data_filter':False}):
            with self.subTest(change=change),tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as directory:
                root=Path(directory);standalone=root/'artifacts/standalone/bin/python'
                standalone.parent.mkdir(parents=True);standalone.write_bytes(b'owned interpreter fixture')
                selected=root/'artifacts/gitlab/contracts/python/bin/python'
                def run(argv,*args,**kwargs):
                    if argv[0]=='make':
                        selected.parent.mkdir(parents=True);selected.symlink_to(standalone);return
                    return json.dumps({'version':[3,14,4],'implementation':'cpython','executable':str(selected),
                        'prefix':str(selected.parents[1]),'base_prefix':str(standalone.parents[1]),'data_filter':True,
                        'yaml_version':'6.0.3','yaml_file':str(selected.parents[1]/'lib/python3.14/site-packages/yaml/__init__.py'),**change})
                with patch.dict(namespace,{'run_command':run}),self.assertRaises(ValueError):
                    execute['bootstrap_contracts_python'](root,{'PATH':'/usr/bin'},
                        {'runtimes':{'standalone_python':{'prefix':str(standalone.parents[1])}}},standalone)

    def test_renderer_install_does_not_inherit_external_bytecode_prefix(self):
        execute = module()
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            root = Path(directory)
            original = {'PATH':'/owned/bin','PYTHONPYCACHEPREFIX':str(root/'external-cache'),'PYTHONUNBUFFERED':'0'}
            child = execute['runtime_environment'](root, original)
            self.assertNotIn('PYTHONPYCACHEPREFIX',child)
            self.assertEqual(child['PYTHONDONTWRITEBYTECODE'],'1')
            self.assertEqual(child.get('PYTHONUNBUFFERED'),'1')
            self.assertEqual(original['PYTHONPYCACHEPREFIX'],str(root/'external-cache'))

    def test_actual_offline_pip_install_keeps_bytecode_record_inside_renderer_environment(self):
        execute = module()
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            root = Path(directory)
            wheel = root/'bijux_cache_fixture-1.0-py3-none-any.whl'
            metadata = 'bijux_cache_fixture-1.0.dist-info/'
            records = {'bijux_cache_fixture.py':b'owned = True\n',
                metadata+'METADATA':b'Metadata-Version: 2.1\nName: bijux-cache-fixture\nVersion: 1.0\n',
                metadata+'WHEEL':b'Wheel-Version: 1.0\nGenerator: bijux\nRoot-Is-Purelib: true\nTag: py3-none-any\n'}
            records[metadata+'RECORD'] = ''.join(name+',,\n' for name in (*records,metadata+'RECORD')).encode()
            with zipfile.ZipFile(wheel,'w') as archive:
                for name,body in records.items(): archive.writestr(name,body)
            base = dict(os.environ);base.pop('PYTHONPYCACHEPREFIX',None)
            interpreter = root/'artifacts/renderer/python/bin/python'
            subprocess.run([sys.executable,'-m','venv',str(interpreter.parents[1])],env=base,check=True,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            original = {**base,'PYTHONPYCACHEPREFIX':str(root/'external-cache')}
            child = execute['runtime_environment'](root,original)
            subprocess.run([str(interpreter),'-m','pip','install','--disable-pip-version-check','--no-index','--no-deps',str(wheel)],
                           env=child,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            output = subprocess.check_output([str(interpreter),'-c',
                'import importlib.metadata,json; print(json.dumps([str(path) for path in importlib.metadata.distribution("bijux-cache-fixture").files]))'],
                env=child,text=True)
            installed = json.loads(output)
            self.assertTrue(any(name.endswith('.pyc') for name in installed), 'Exercise pip explicit compilation rather than disabling it')
            self.assertFalse(any('..' in Path(name).parts for name in installed),installed)

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
                        'bootstrap_standalone_python':lambda *args:Path(sys.executable),
                        'bootstrap_contracts_python':lambda *args:Path(sys.executable),
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
            for key in ('TMPDIR','PIP_CACHE_DIR','UV_CACHE_DIR','NPM_CONFIG_CACHE'):
                self.assertTrue(Path(env[key]).is_relative_to(root / 'artifacts'))
            self.assertNotIn('PYTHONPYCACHEPREFIX',env)
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
                        'bootstrap_standalone_python':lambda *args:Path(sys.executable),
                        'bootstrap_contracts_python':lambda *args:Path(sys.executable),
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
