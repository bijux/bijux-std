"""Physical batches cannot omit, duplicate or exchange canonical group evidence."""
import ast
import copy
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest

import test_docs_browser_execution as EXECUTION
import test_docs_job_budget as BUDGET_CONTROLS
import test_docs_workflow_collection as COLLECTION

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'tests/bijux-docs/execution/browser_ownership/batches.py'
OWNERSHIP = ModuleType('bijux_browser_ownership_controls')
OWNERSHIP.__file__ = str(PATH)
exec(compile(PATH.read_bytes(), str(PATH), 'exec'), OWNERSHIP.__dict__)


class BrowserOwnershipTests(unittest.TestCase):
    def test_missing_duplicate_unknown_and_changed_schema_mapping_refuse(self):
        original = json.loads(OWNERSHIP.REGISTRY_PATH.read_bytes())
        changes = [lambda record: record['batches'].pop('history'),
                   lambda record: record['batches']['history'].append('reader'),
                   lambda record: record['batches']['history'].__setitem__(0, 'foreign-group'),
                   lambda record: record['batches'].__setitem__('history', []),
                   lambda record: record.update(schema=True),
                   lambda record: record.update(unknown=True)]
        for change in changes:
            record = copy.deepcopy(original); change(record)
            with self.assertRaises(ValueError): OWNERSHIP.validate(record, EXECUTION.GATE.GROUPS)
        with self.assertRaisesRegex(ValueError, 'Duplicate'): OWNERSHIP.unique([('batch', 1), ('batch', 2)])
        batches = OWNERSHIP.registry(EXECUTION.GATE.GROUPS)
        self.assertEqual(OWNERSHIP.owner(batches, 'contrast-phone'), 'contrast-responsive')
        with self.assertRaises(ValueError): OWNERSHIP.owner(batches, 'foreign')

    def test_report_refresh_admits_the_source_owned_physical_job_inventory(self):
        workflow = (ROOT / ".github/standards/workflow-sources/bijux-std.yml").read_text()
        lines = workflow.splitlines()
        start = next(index for index, line in enumerate(lines)
                     if "jobs = budget.refresh_nonterminal(" in line)
        statement = []
        for line in lines[start:]:
            statement.append(line.strip())
            if line.rstrip().endswith(")"):
                break
        call = ast.parse("\n".join(statement)).body[0].value
        self.assertIsInstance(call, ast.Call)
        groups = next(keyword.value for keyword in call.keywords if keyword.arg == "groups")
        self.assertIsInstance(groups, ast.Attribute)
        self.assertEqual(ast.unparse(groups.value), "registry")
        registry = EXECUTION.GATE
        supplied = getattr(registry, groups.attr)
        budget = BUDGET_CONTROLS.BUDGET
        names = sorted(budget.expected_job_names(registry.BATCHES, registry.ENGINES)
                       | budget.BASELINE_JOBS)
        head = "a" * 40
        payload = {"total_count": len(names), "jobs": [
            {"id": index + 1, "name": name, "run_id": 123, "run_attempt": 1,
             "head_sha": head, "status": "completed", "conclusion": "success"}
            for index, name in enumerate(names)]}
        def unexpected_refresh(identifier):
            self.fail("Complete physical job inventory must not request another API row")
        observed = budget.refresh_nonterminal(payload, fetch=unexpected_refresh,
            groups=supplied, engines=registry.ENGINES, run_id=123, attempt=1, head=head)
        self.assertEqual(observed, payload)
        self.assertEqual(set(supplied), set(registry.BATCHES))
        self.assertNotEqual(set(registry.GROUPS), set(registry.BATCHES))
        with self.assertRaisesRegex(ValueError, "Missing or unexpected current job name"):
            budget.refresh_nonterminal(payload, fetch=unexpected_refresh,
                groups=registry.GROUPS, engines=registry.ENGINES,
                run_id=123, attempt=1, head=head)

    def test_two_viewports_share_one_setup_and_keep_two_original_native_owners(self):
        controls = EXECUTION.RecoveryProducerOrderTests()
        with controls.execution(recovery=False) as observed:
            EXECUTION.GATE.run('contrast-responsive', 'chromium')
            observed.unpack.assert_called_once(); observed.install.assert_called_once()
            calls = observed.runner.call_args_list
            self.assertEqual(len(calls), 2)
            self.assertEqual([call.kwargs['env']['BIJUX_UI_PROFILE'] for call in calls], ['phone', 'compact'])
            self.assertEqual([call.kwargs['env']['BIJUX_UI_BROWSER_ENGINE'] for call in calls], ['chromium', 'chromium'])
            self.assertEqual([call.args[1] for call in observed.controllers.record_execution.call_args_list],
                             ['browser-contrast-phone-chromium', 'browser-contrast-compact-chromium'])

    def test_one_failed_group_cannot_pass_batch_while_other_groups_still_execute(self):
        controls = EXECUTION.RecoveryProducerOrderTests()
        with controls.execution(recovery=False) as observed:
            observed.runner.side_effect = [SimpleNamespace(returncode=1), SimpleNamespace(returncode=0)]
            with self.assertRaisesRegex(ValueError, 'contrast-phone/contrast'):
                EXECUTION.GATE.run('contrast-responsive', 'webkit')
            self.assertEqual(observed.runner.call_count, 2)
            self.assertEqual(observed.controllers.record_execution.call_count, 1)
            self.assertEqual(observed.controllers.record_execution.call_args.args[1], 'browser-contrast-compact-webkit')

    def fixture(self):
        controls = COLLECTION.WorkflowCollectionTests()
        controls.setUp(); self.addCleanup(controls.doCleanups)
        return controls

    def test_one_api_owner_admits_both_original_group_execution_declarations(self):
        fixture = self.fixture()
        role, job, _, _, record = fixture.add_browser('browser-navigation-links-chromium')
        collection = fixture.collection()
        collection.verify_execution(role, record, 'navigation-destinations')
        self.assertEqual(collection.browser_role('navigation-destinations', 'chromium'), role)
        self.assertEqual(collection.browser_role('links', 'chromium'), role)
        self.assertEqual(collection.inputs[role]._pin['owner_job']['id'], job['id'])
        plan = collection.plan()
        for group in ('navigation-destinations', 'links'):
            self.assertIn('shards/' + group + '-chromium/execution.json', plan)
        self.assertEqual(len([key for key in collection.inputs if key.startswith('browser-')]), 1)

    def test_missing_group_swapped_declaration_and_foreign_namespace_refuse_before_output_plan(self):
        for change in ('missing', 'swapped', 'foreign'):
            fixture = self.fixture()
            role, _, artifact, files, _ = fixture.add_browser('browser-navigation-links-chromium')
            changed = dict(files)
            if change == 'missing':
                changed.pop('links-chromium/execution.json')
            elif change == 'swapped':
                changed['links-chromium/execution.json'] = changed['navigation-destinations-chromium/execution.json']
            else:
                changed['history-chromium/qualification.json'] = b'foreign browser owner'
            fixture.set_body(55, artifact, changed)
            with self.assertRaises(ValueError): fixture.collection().plan()


if __name__ == '__main__':
    unittest.main()
