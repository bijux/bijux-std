from __future__ import annotations
import copy
import importlib.util
import json
import tempfile
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock
from .policy_fixtures import ROOT, MODULE, INVENTORY, POLICY, manifest


class ExecutionSchemaTests(unittest.TestCase):
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
            ("deploy-docs", {"mode": "manual-only", "refs": True}),
            ("deploy-docs", {"mode": "manual-only", "refs": None}),
            ("deploy-docs", {"mode": "manual-only", "refs": "${{ github.ref }}"}),
        ]:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                MODULE.validate_manifest(manifest({"schema": 1, "publication_entrypoints": {entrypoint: entry}}), ["bijux-atlas"])

    def test_dependency_policy_rejects_boolean_and_unknown_actor_selectors(self):
        for value in [True, False, None, "dependabot", "${{ github.actor }}"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.validate_manifest(manifest({"schema": 1, "dependency_pull_requests": value}), ["bijux-atlas"])
        with self.assertRaises(ValueError):
            MODULE.validate_manifest(manifest({"schema": 1, "dependency_pull_requests": "skip-managed-jobs", "actor": "dependabot[bot]"}), ["bijux-atlas"])

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
