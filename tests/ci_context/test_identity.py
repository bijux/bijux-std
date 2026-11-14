"""Keep native provider executions distinct without fabricating workflow attempts."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
EXECUTION = ROOT / 'tests/bijux-docs/execution'
GITLAB = {'GITLAB_CI': 'true', 'CI_SERVER_URL': 'https://gitlab.example.com',
          'CI_PROJECT_ID': '17', 'CI_PROJECT_PATH': 'bijux/bijux-std',
          'CI_PIPELINE_ID': '123', 'CI_JOB_ID': '456', 'CI_COMMIT_SHA': 'a' * 40,
          'CI_PIPELINE_SOURCE': 'merge_request_event'}
IDENTITY = {'provider': 'gitlab', 'server_url': 'https://gitlab.example.com',
            'project_id': '17', 'project_path': 'bijux/bijux-std',
            'pipeline_id': '123', 'job_id': '456', 'commit_sha': 'a' * 40}


def load(name):
    path = EXECUTION / (name + '.py')
    spec = importlib.util.spec_from_file_location('bijux_ci_test_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProviderIdentityTests(unittest.TestCase):
    def context(self):
        self.assertTrue((EXECUTION / 'ci_context.py').is_file(), 'Native CI identity boundary is missing')
        return load('ci_context')

    def test_gitlab_retains_actual_job_and_pipeline_as_distinct_identities(self):
        with patch.dict(os.environ, GITLAB, clear=True):
            context = self.context()
            self.assertEqual(context.workflow_identity(), IDENTITY)
            self.assertEqual(context.pipeline_identity(), {key: value for key, value in IDENTITY.items() if key != 'job_id'})
            self.assertNotIn('workflow_attempt', context.execution_identity())

    def test_incomplete_or_ambiguous_provider_environment_is_rejected(self):
        for key in ('CI_SERVER_URL', 'CI_PROJECT_ID', 'CI_PROJECT_PATH', 'CI_PIPELINE_ID', 'CI_JOB_ID', 'CI_COMMIT_SHA'):
            env = dict(GITLAB); env.pop(key)
            with self.subTest(key=key), patch.dict(os.environ, env, clear=True):
                with self.assertRaises(ValueError):
                    self.context().workflow_identity()
        for changes in ({'CI_JOB_ID': '0'}, {'CI_PROJECT_PATH': '../bijux-std'},
                        {'CI_SERVER_URL': 'https://token@gitlab.example.com'},
                        {'GITHUB_RUN_ID': '99'}, {'CI_COMMIT_SHA': 'branch'}):
            with self.subTest(changes=changes), patch.dict(os.environ, {**GITLAB, **changes}, clear=True):
                with self.assertRaises(ValueError):
                    self.context().workflow_identity()

    def test_fresh_aggregate_retains_each_executor_but_rejects_foreign_pipeline(self):
        with patch.dict(os.environ, GITLAB, clear=True):
            context = self.context()
            producer = {**IDENTITY, 'job_id': '111'}
            self.assertEqual(context.verify_workflow(producer), producer)
            with self.assertRaises(ValueError):
                context.verify_workflow({**producer, 'pipeline_id': '124'})
            with self.assertRaises(ValueError):
                context.verify_workflow({**producer, 'job_id': None})
            with self.assertRaises(ValueError):
                context.verify_workflow(producer, IDENTITY)

    def test_github_and_local_workflow_schema_remains_unchanged(self):
        for env, expected in (({}, {'workflow_run_id': None, 'workflow_attempt': None}),
                              ({'GITHUB_RUN_ID': '12', 'GITHUB_RUN_ATTEMPT': '3'},
                               {'workflow_run_id': '12', 'workflow_attempt': '3'})):
            with patch.dict(os.environ, env, clear=True):
                context = self.context()
                self.assertEqual(context.workflow_identity(), expected)
                self.assertEqual(load('publication_gate').workflow_identity(), expected)
                with self.assertRaises(ValueError):
                    context.verify_workflow({'workflow_run_id': 'different', 'workflow_attempt': '3'})

    def test_publication_commands_record_native_gitlab_execution(self):
        with patch.dict(os.environ, GITLAB, clear=True):
            self.assertEqual(load('publication_gate').workflow_identity(), IDENTITY)

    def test_gitlab_recovery_is_explicitly_unsupported(self):
        with patch.dict(os.environ, GITLAB, clear=True):
            controllers = load('workflow_controllers')
            with self.assertRaisesRegex(ValueError, 'gitlab retained-proof recovery'):
                controllers.collect('producer')


class GitLabPlannerTests(unittest.TestCase):
    def test_plan_select_verify_runs_full_fresh_and_emits_dotenv(self):
        artifacts = ROOT / 'artifacts/qualification/ci-context'
        artifacts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=artifacts) as folder:
            folder = Path(folder)
            head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
            env = {key: value for key, value in os.environ.items() if not key.startswith(('GITHUB_', 'CI_'))}
            env.update(GITLAB, CI_COMMIT_SHA=head, BIJUX_CI_OUTPUT=str(folder / 'selection.env'),
                       EXPECTED_BASELINE=head, VERIFICATION_MODE='full', EXPECTED_FRONTEND='true', PLAN_RESULT='success')
            for name in ('FIXTURE', 'BROWSER', 'COMMAND', 'RENDERER', 'CATALOGUE', 'PERSISTED', 'FAULT_BROWSER', 'FAULT_PUBLIC'):
                env[name + '_RESULT'] = 'success'
            common = ['--plan', str(folder / 'plan.json'), '--selection', str(folder / 'selection.json'),
                      '--output', str(folder / 'qualification.json')]
            for operation in ('plan', 'select', 'verify'):
                result = subprocess.run(['python3', '-B', str(EXECUTION / 'input_planning/cli.py'), operation, *common],
                                        cwd=ROOT, env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((folder / 'selection.env').read_text(), 'frontend=true\nfrontend=true\n')
            receipt = json.loads((folder / 'qualification.json').read_text())
            self.assertTrue(receipt['frontend_executed'])
            self.assertIsNone(receipt['original_proof'])

    def test_gitlab_accepted_proof_mode_is_refused_before_outputs(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith(('GITHUB_', 'CI_'))}
        env.update(GITLAB, VERIFICATION_MODE='accepted-proof-qualification')
        result = subprocess.run(['python3', '-B', str(EXECUTION / 'input_planning/cli.py'), 'plan'],
                                cwd=ROOT, env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('gitlab retained-proof recovery', result.stderr)

    def test_gitlab_retained_proof_flags_are_refused_even_with_full_mode(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith(('GITHUB_', 'CI_'))}
        env.update(GITLAB, VERIFICATION_MODE='full')
        for flag in ('--accepted-proof', '--consumer-platform', '--selection-only'):
            with self.subTest(flag=flag):
                result = subprocess.run(['python3', '-B', str(EXECUTION / 'input_planning/cli.py'), 'verify', flag],
                                        cwd=ROOT, env=env, text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('gitlab retained-proof recovery', result.stderr)


if __name__ == '__main__':
    unittest.main()
