"""Affected-input mutation controls over real immutable Git source changes."""
from __future__ import annotations

import copy
import importlib.util
import os
from pathlib import Path
import json
import py_compile
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'tests/bijux-docs/execution/input_planning'
SPEC = importlib.util.spec_from_file_location('bijux_ci_input_planning', PACKAGE / '__init__.py', submodule_search_locations=[str(PACKAGE)])
import sys
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
from bijux_ci_input_planning.ownership import FRONTEND_FAMILIES, classify, select
from bijux_ci_input_planning.source import capture
from bijux_ci_input_planning.qualification import FRONTEND_CONTEXTS, require_results, selection_observation, verify_plan


class InputPlanningMutationTests(unittest.TestCase):
    def git(self, *arguments):
        return subprocess.check_output(['git', *arguments], cwd=self.repo, stderr=subprocess.PIPE).decode().strip()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name) / 'source'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'verification@bijux.io')
        self.git('config', 'user.name', 'Bijux verification')
        self.git('remote', 'add', 'origin', 'https://github.com/bijux/bijux-std.git')
        self.put('tests/bijux-docs/execution/input_planning/ownership.py', 'source-owned planner')
        self.put('.github/standards/workflow-sources/bijux-std.yml', 'canonical workflow')
        self.put('.gitignore', 'artifacts/\n')
        self.put('README.md', 'repository description')
        self.put('shared/bijux-docs/assets/runtime.js', 'runtime')
        self.commit('test(ci): capture governed source baseline')
        self.base = self.git('rev-parse', 'HEAD')
        self.git('update-ref', 'refs/remotes/origin/main', self.base)

    def put(self, relative, body):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)

    def commit(self, subject):
        self.git('add', '--', '.')
        self.git('commit', '-m', subject)

    def plan(self, baseline=None, event='pull_request'):
        return capture(self.repo, self.git('rev-parse', 'HEAD'), self.base if baseline is None else baseline, event)

    def test_known_governance_change_runs_source_and_security_without_claiming_browser_execution(self):
        self.put('.github/ISSUE_TEMPLATE/bug-report.yml', 'a source-owned repository form')
        self.commit('test(ci): change repository issue form')
        plan = self.plan()
        self.assertFalse(plan['frontend'])
        self.assertEqual(plan['families'], ['standard', 'contracts'])
        self.assertEqual(verify_plan(plan, self.repo, plan['checkout'], self.base, 'pull_request'), plan)
        result = require_results(plan, dict.fromkeys(FRONTEND_CONTEXTS, 'skipped'), plan_result='success', source_results=['success'])
        self.assertFalse(result['frontend_executed'])

    def test_render_test_lock_shell_diagram_native_publication_workflow_inputs_select_full_closure(self):
        paths = ['shared/bijux-docs/templates/main.html', 'shared/bijux-docs/assets/runtime.js',
                 'tests/bijux-docs/generated/content/page.md', 'tests/bijux-docs/tooling/diagrams/input.json',
                 'tests/bijux-docs/unit/browser.test.js', 'tests/bijux-docs/package-lock.json',
                 'shared/bijux-docs/security/renderer.py', 'shared/bijux-gh/workflows/deploy-docs.yml',
                 '.github/standards/workflow-sources/bijux-std.yml', 'makes/bijux-docs.mk']
        for path in paths:
            with self.subTest(path=path):
                plan = select([{'status': 'M', 'paths': [path]}])
                self.assertTrue(plan['frontend'])
                self.assertTrue(set(FRONTEND_FAMILIES).issubset(plan['families']))

    def test_real_unknown_rename_delete_and_planner_changes_cannot_select_less_coverage(self):
        for variant in ('unknown', 'rename', 'delete', 'planner'):
            with self.subTest(variant=variant):
                self.git('reset', '--hard', self.base)
                if variant == 'unknown':
                    self.put('unmapped/source.txt', 'new unowned source')
                elif variant == 'rename':
                    self.git('mv', 'README.md', 'NOTICE')
                elif variant == 'delete':
                    (self.repo / 'README.md').unlink()
                else:
                    self.put('tests/bijux-docs/execution/input_planning/ownership.py', 'altered planner')
                self.commit('test(ci): exercise changed source ownership')
                plan = self.plan()
                self.assertTrue(plan['frontend'])
                self.assertTrue(plan['full_verification_reasons'])

    def test_independent_baseline_and_foreign_remote_missing_plan_or_merge_context_refuse_narrowing(self):
        self.assertTrue(self.plan('0' * 40)['frontend'])
        self.assertTrue(self.plan(event='merge_group')['frontend'] is False)
        self.assertTrue(self.plan(event='workflow_dispatch')['frontend'])
        self.git('remote', 'set-url', 'origin', 'https://github.com/foreign/standard.git')
        self.assertTrue(self.plan()['frontend'])
        with self.assertRaises(ValueError):
            verify_plan(None, self.repo, self.git('rev-parse', 'HEAD'), self.base, 'pull_request')
        wrong_head = capture(self.repo, '0' * 40, self.base, 'pull_request')
        self.assertTrue(wrong_head['frontend'])
        with self.assertRaises(ValueError):
            verify_plan(wrong_head, self.repo, '0' * 40, self.base, 'pull_request')

    def test_explicit_qualification_requires_immutable_official_main_and_unchanged_mode(self):
        mode = 'accepted-proof-qualification'
        plan = capture(self.repo, self.base, self.base, 'workflow_dispatch', mode)
        self.assertFalse(plan['frontend'])
        self.assertEqual(plan['event'], 'workflow_dispatch')
        self.assertEqual(plan['qualification_mode'], mode)
        self.assertEqual(verify_plan(plan, self.repo, self.base, self.base, 'workflow_dispatch', mode), plan)
        for event, requested in [('workflow_dispatch', 'full'), ('workflow_dispatch', 'unknown'),
                                 ('pull_request', mode), ('push', mode)]:
            with self.subTest(event=event, requested=requested):
                self.assertTrue(capture(self.repo, self.base, self.base, event, requested)['frontend'])
        with self.assertRaises(ValueError):
            verify_plan(plan, self.repo, self.base, self.base, 'workflow_dispatch')
        self.put('shared/bijux-docs/assets/runtime.js', 'different source awaiting normal acceptance')
        self.commit('test(ci): change protected qualification input')
        head = self.git('rev-parse', 'HEAD')
        self.assertTrue(capture(self.repo, head, head, 'workflow_dispatch', mode)['frontend'])
        self.assertTrue(capture(self.repo, head, self.base, 'workflow_dispatch', mode)['frontend'])
        self.git('update-ref', 'refs/remotes/origin/main', head)
        self.assertFalse(capture(self.repo, head, head, 'workflow_dispatch', mode)['frontend'])

    def test_tampered_selection_changed_baseline_and_any_missing_or_skipped_selected_context_fail(self):
        self.put('shared/bijux-docs/assets/runtime.js', 'changed executable runtime')
        self.commit('test(ci): change owned browser runtime')
        plan = self.plan()
        altered = copy.deepcopy(plan);altered['frontend'] = False
        for supplied, baseline in [(altered, self.base), (plan, '0' * 40)]:
            with self.assertRaises(ValueError):
                verify_plan(supplied, self.repo, plan['checkout'], baseline, 'pull_request')
        for context in FRONTEND_CONTEXTS:
            for outcome in ('skipped', 'failure', 'cancelled', None):
                with self.subTest(context=context, outcome=outcome):
                    results = dict.fromkeys(FRONTEND_CONTEXTS, 'success');results[context] = outcome
                    with self.assertRaises(ValueError):
                        require_results(plan, results, plan_result='success')
        with self.assertRaises(ValueError):
            require_results(plan, dict.fromkeys(FRONTEND_CONTEXTS, 'success'), plan_result='skipped')
        pending = selection_observation(plan)
        self.assertEqual(pending['status'], 'execution_pending')
        self.assertFalse(pending['frontend_executed'])

    def test_unsafe_ambiguous_or_nonregular_inputs_and_dirty_checkout_force_full_verification(self):
        for name in ('../README.md', '/README.md', 'README.md\x00', 'a\\b', 'a//b'):
            self.assertIsNone(classify(name))
        for record in [{'status': 'M', 'paths': ['README.md', 'NOTICE']}, {'status': 'T', 'paths': ['README.md']}, None]:
            self.assertTrue(select([record])['frontend'])
        self.put('README.md', 'uncommitted source')
        self.assertTrue(self.plan()['frontend'])
        self.git('reset', '--hard', self.base)
        (self.repo / 'alias').symlink_to('README.md')
        self.commit('test(ci): preserve source alias observation')
        self.assertTrue(self.plan()['frontend'])

    def test_actual_cli_uses_current_source_bytes_despite_forged_unchecked_bytecode(self):
        shutil.copytree(PACKAGE, self.repo / 'tests/bijux-docs/execution/input_planning', dirs_exist_ok=True)
        self.put('.gitignore', 'artifacts/\n__pycache__/\n')
        self.commit('test(ci): retain executable source planner')
        self.base = self.git('rev-parse', 'HEAD')
        self.git('update-ref', 'refs/remotes/origin/main', self.base)
        forged = self.repo / 'artifacts/forged-source.py'
        forged.parent.mkdir()
        forged.write_text("raise RuntimeError('retained bytecode acquired source authority')\n")
        owner = self.repo / 'tests/bijux-docs/execution/input_planning/ownership.py'
        cache = Path(importlib.util.cache_from_source(str(owner)))
        cache.parent.mkdir(parents=True, exist_ok=True)
        py_compile.compile(str(forged), cfile=str(cache), invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
        cli = owner.with_name('cli.py')
        result = subprocess.run([sys.executable, '-B', str(cli), 'plan'], cwd=self.repo, capture_output=True, text=True,
            env={**os.environ, 'GITHUB_SHA': self.base, 'EXPECTED_BASELINE': self.base, 'GITHUB_EVENT_NAME': 'pull_request',
                 'GITHUB_OUTPUT': str(forged.parent / 'outputs')})
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads((forged.parent / 'bijux-docs/input-plan/plan.json').read_text())
        self.assertFalse(plan['frontend'])


if __name__ == '__main__':
    unittest.main()
