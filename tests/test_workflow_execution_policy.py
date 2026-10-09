from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import shutil
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "bijux_workflow_execution_policy", ROOT / ".github/scripts/workflow_execution.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
INVENTORY = json.loads((ROOT / ".github/standards/workflow-inventory.json").read_text())
POLICY = {
    "schema": 1,
    "automatic_runs": "repository-policy-only",
    "dependency_pull_requests": "skip-managed-jobs",
    "publication_entrypoints": {
        "deploy-docs": {"mode": "manual-only", "refs": "main-only"},
        "release-github": {"mode": "manual-only"},
    },
}


def manifest(policy=POLICY, name="bijux-atlas"):
    return {
        "workflow_inventory": copy.deepcopy(INVENTORY),
        "repositories": [{"name": name, "workflow_allowlist": ["github-policy", "deploy-docs", "release-github"],
                          "workflow_execution_policy": copy.deepcopy(policy)}],
    }


class WorkflowExecutionPolicyTests(unittest.TestCase):
    def test_workflow_parser_preserves_mapping_key_spelling(self):
        document = MODULE.parse_workflow(b"on: [pull_request, workflow_dispatch]\njobs:\n  owned:\n    env:\n      on: spelling\n      'true': distinct\n", "owned.yml")
        self.assertEqual(document["on"], ["pull_request", "workflow_dispatch"])
        self.assertEqual(document["jobs"]["owned"]["env"], {"on": "spelling", "true": "distinct"})

    def test_workflow_parser_refuses_duplicate_alias_multidocument_and_boolean_collisions(self):
        for source in [
            b"on: push\non: workflow_dispatch\njobs: {}\n",
            b"on: workflow_dispatch\njobs:\n  owned: {}\n  owned: {}\n",
            b"on: &events [pull_request]\njobs: {owned: *events}\n",
            b"on: push\njobs: {}\n---\non: workflow_dispatch\njobs: {}\n",
            b"on: push\ntrue: workflow_dispatch\njobs: {}\n",
            b"on: workflow_dispatch\njobs: []\n",
        ]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                MODULE.parse_workflow(source, "owned.yml")

    def test_missing_parser_has_actionable_prerequisite_failure(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("ruby")):
            with self.assertRaisesRegex(RuntimeError, "ruby is required"):
                MODULE.parse_workflow(b"on: workflow_dispatch\njobs: {}\n", "owned.yml")

    def test_automatic_projection_preserves_all_nontrigger_source_and_required_events(self):
        source = {"name": "standard", "on": ["push", "pull_request", "merge_group", "workflow_dispatch"], "jobs": {"checks": {"name": "std / check", "if": "${{ always() }}"}}, "permissions": {"contents": "read"}}
        before = copy.deepcopy(source)
        projected = MODULE.project_automatic_events("bijux-std", source, {"schema": 1, "automatic_runs": "repository-policy-only"})
        self.assertEqual(set(projected["on"]), {"pull_request", "merge_group", "workflow_dispatch"})
        self.assertEqual({k: v for k, v in projected.items() if k != "on"}, {k: v for k, v in source.items() if k != "on"})
        self.assertEqual(source, before)
        self.assertEqual(MODULE.project_automatic_events("bijux-std", source, None), source)
        self.assertEqual(MODULE.project_automatic_events("bijux-std", source, {"schema": 1, "automatic_runs": "canonical"}), source)

    def test_repository_policy_restricts_main_and_preserves_paths_and_PR_configuration(self):
        source = {"on": {"push": {"branches": ["main", "feature"], "tags": ["v*"], "paths": [".github/**"]}, "pull_request": {"branches": ["main"]}}, "jobs": {}}
        policy = {"schema": 1, "automatic_runs": "repository-policy-only"}
        projected = MODULE.project_automatic_events("github-policy", source, policy)
        self.assertEqual(projected["on"]["push"], {"branches": ["main"], "paths": [".github/**"]})
        self.assertEqual(projected["on"]["pull_request"], source["on"]["pull_request"])
        self.assertEqual(MODULE.project_automatic_events("github-policy", projected, policy), projected)

    def test_automatic_projection_admits_null_map_list_and_string_manual_events(self):
        for events in ["workflow_dispatch", ["workflow_dispatch"], {"workflow_dispatch": None}, {"workflow_dispatch": {}}]:
            with self.subTest(events=events):
                projected = MODULE.project_automatic_events("release-github", {"on": events, "jobs": {}}, {"schema": 1, "automatic_runs": "repository-policy-only"})
                self.assertEqual(set(projected["on"]), {"workflow_dispatch"})

    def test_automatic_projection_refuses_unsupported_ambiguous_and_missing_entrypoints(self):
        for identity, events in [
            ("ci", ["push"]), ("ci", ["pull_request", "pull_request"]),
            ("ci", {"schedule": [{"cron": "0 0 * * *"}]}),
            ("ci", {"pull_request": "branches: main"}),
            ("ci", {"push": {"branches": "main"}, "pull_request": None}),
            ("ci", {"push": {"branches": ["main"], "branches-ignore": ["other"]}, "pull_request": None}),
            ("github-policy", {"push": None}),
            ("github-policy", {"push": {"branches": ["feature"]}}),
            ("bijux-std", {"pull_request": None, "workflow_dispatch": None}),
        ]:
            with self.subTest(events=events), self.assertRaises(ValueError):
                MODULE.project_automatic_events(identity, {"on": events, "jobs": {}}, {"schema": 1, "automatic_runs": "repository-policy-only"})

    def test_adjacent_helper_is_not_reused_from_another_canonical_root(self):
        with tempfile.TemporaryDirectory() as workspace:
            helpers = []
            for name in ["owned-standard", "independent-standard"]:
                root = Path(workspace) / name
                scripts = root / ".github/scripts"
                scripts.mkdir(parents=True)
                for filename in ["render_repo_configs.py", "workflow_execution.py"]:
                    shutil.copyfile(ROOT / ".github/scripts" / filename, scripts / filename)
                (root / "shared/bijux-gh").mkdir(parents=True)
                spec = importlib.util.spec_from_file_location("bijux_independent_renderer", scripts / "render_repo_configs.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.assertEqual(Path(module.WORKFLOW_EXECUTION.__file__).resolve(), (scripts / "workflow_execution.py").resolve())
                helpers.append(module.WORKFLOW_EXECUTION)
            self.assertIsNot(helpers[0], helpers[1])
            helpers[0].PUBLICATION_ENTRYPOINTS = frozenset()
            self.assertEqual(helpers[1].validate_manifest(manifest(), ["bijux-atlas"])["bijux-atlas"], POLICY)

    def test_automatic_policy_requires_enabled_repository_policy(self):
        source = manifest()
        source["repositories"][0]["workflow_allowlist"].remove("github-policy")
        with self.assertRaisesRegex(ValueError, "enabled canonical github-policy"):
            MODULE.validate_manifest(source, ["bijux-atlas"])
        for value in [True, "github-policy", ["github-policy", "github-policy"], ["unknown-workflow"]]:
            source = manifest()
            source["repositories"][0]["workflow_allowlist"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.validate_manifest(source, ["bijux-atlas"])

    def test_explicit_reviewed_policy_returns_independent_typed_value(self):
        source = manifest()
        admitted = MODULE.validate_manifest(source, ["bijux-atlas"])["bijux-atlas"]
        self.assertEqual(admitted, POLICY)
        admitted["publication_entrypoints"]["deploy-docs"]["mode"] = "canonical"
        self.assertEqual(source, manifest())

    def test_absent_policy_has_no_implicit_repository_defaults(self):
        source = manifest()
        del source["repositories"][0]["workflow_execution_policy"]
        self.assertEqual(MODULE.validate_manifest(source, ["bijux-atlas"]), {"bijux-atlas": None})
        self.assertNotIn("workflow_execution_policy", source["repositories"][0])

    def test_schema_refuses_noninteger_boolean_missing_and_unknown_versions(self):
        for value in [True, False, 1.0, "1", 0, 2, None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.validate_manifest(manifest({"schema": value}), ["bijux-atlas"])
        with self.assertRaises(ValueError):
            MODULE.validate_manifest(manifest({}), ["bijux-atlas"])

    def test_policy_refuses_unknown_fields_and_arbitrary_conditions(self):
        for policy in [None, [], "manual", {"schema": 1, "jobs": {}},
                       {"schema": 1, "automatic_runs": "${{ true }}"},
                       {"schema": 1, "dependency_pull_requests": False},
                       {"schema": 1, "publication_entrypoints": {"deploy-docs": {"mode": "manual-only", "if": "true"}}},
                       {"schema": 1, "publication_entrypoints": {"release-artifacts": {"mode": "manual-only"}}}]:
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                MODULE.validate_manifest(manifest(policy), ["bijux-atlas"])

    def test_publication_admission_requires_enabled_canonical_inventory(self):
        for location in ["inventory", "allowlist"]:
            source = manifest()
            if location == "inventory":
                source["workflow_inventory"]["managed_workflows"] = [e for e in source["workflow_inventory"]["managed_workflows"] if e["id"] != "deploy-docs"]
            else:
                source["repositories"][0]["workflow_allowlist"].remove("deploy-docs")
            with self.subTest(location=location), self.assertRaises(ValueError):
                MODULE.validate_manifest(source, ["bijux-atlas"])

    def test_main_docs_refs_require_manual_mode_and_cannot_extend_releases(self):
        for entrypoint, entry in [
            ("deploy-docs", {"mode": "canonical", "refs": "main-only"}),
            ("deploy-docs", {"mode": "manual-only", "refs": "refs/heads/feature"}),
            ("release-github", {"mode": "manual-only", "refs": "main-only"}),
            ("deploy-docs", {"refs": "main-only"}),
        ]:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                MODULE.validate_manifest(manifest({"schema": 1, "publication_entrypoints": {entrypoint: entry}}), ["bijux-atlas"])

    def test_standard_cannot_disable_qualification(self):
        for key, value in [("automatic_runs", "repository-policy-only"),
                           ("dependency_pull_requests", "skip-managed-jobs")]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "mandatory workflow qualification"):
                MODULE.validate_manifest(manifest({"schema": 1, key: value}, "bijux-std"), ["bijux-std"])
        self.assertEqual(MODULE.validate_manifest(manifest({"schema": 1, "automatic_runs": "canonical"}, "bijux-std"), ["bijux-std"])["bijux-std"], {"schema": 1, "automatic_runs": "canonical"})

    def test_selected_batch_is_fully_admitted_and_unselected_policy_stays_unmodified(self):
        source = manifest()
        source["repositories"].append({"name": "bijux-canon", "workflow_execution_policy": {"schema": True}})
        before = copy.deepcopy(source)
        MODULE.validate_manifest(source, ["bijux-atlas"])
        with self.assertRaises(ValueError):
            MODULE.validate_manifest(source, ["bijux-atlas", "bijux-canon"])
        self.assertEqual(source, before)

    def test_inventory_refuses_unknown_boolean_duplicate_and_wrong_paths(self):
        invalid = [None, {"version": True, "managed_workflows": []},
                   {"version": 1, "managed_workflows": [], "shell": "arbitrary"}]
        duplicate = copy.deepcopy(INVENTORY)
        duplicate["managed_workflows"].append(copy.deepcopy(duplicate["managed_workflows"][0]))
        invalid.append(duplicate)
        for field, value in [("source", "../private.yml"), ("consumer_runtime", "/owned.yml"),
                             ("id", "${{ expression }}"), ("source", "shared/bijux-gh/workflows/other.yml")]:
            changed = copy.deepcopy(INVENTORY)
            changed["managed_workflows"][0][field] = value
            invalid.append(changed)
        for value in invalid:
            source = manifest()
            source["workflow_inventory"] = value
            with self.subTest(inventory=value), self.assertRaises(ValueError):
                MODULE.validate_manifest(source, ["bijux-atlas"])

    def test_inventory_is_checked_even_when_policy_is_absent(self):
        source = {"repositories": [{"name": "bijux-atlas"}], "workflow_inventory": None}
        with self.assertRaises(ValueError):
            MODULE.validate_manifest(source, ["bijux-atlas"])
        source.pop("workflow_inventory")
        self.assertEqual(MODULE.validate_manifest(source, ["bijux-atlas"]), {"bijux-atlas": None})

    def test_repository_identity_and_selection_are_unambiguous(self):
        source = manifest()
        source["repositories"].append(copy.deepcopy(source["repositories"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate manifest repository"):
            MODULE.validate_manifest(source, ["bijux-atlas"])
        with self.assertRaises(KeyError):
            MODULE.validate_manifest(manifest(), ["missing-repository"])


if __name__ == "__main__":
    unittest.main()
