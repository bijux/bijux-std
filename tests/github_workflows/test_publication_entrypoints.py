from __future__ import annotations

import copy
import unittest
from .policy_fixtures import MODULE

POLICY = {"schema": 1, "publication_entrypoints": {
    identity: {"mode": "manual-only"}
    for identity in ["deploy-docs", "release-github", "release-ghcr", "release-crates"]
}}


class PublicationEntrypointTests(unittest.TestCase):
    def test_four_manual_APIs_retain_exact_dispatch_and_owned_jobs(self):
        source = {"name": "publisher", "on": {
            "workflow_dispatch": {"inputs": {"release_tag": {"description": "source help", "type": "string", "default": "", "required": False}}},
            "workflow_call": {"inputs": {"release_tag": {"type": "string"}}, "secrets": {"owned": {"required": True}}},
        }, "permissions": {"contents": "read"}, "jobs": {"artifact": {"uses": "./.github/workflows/release-artifacts.yml"}}}
        before = copy.deepcopy(source)
        for identity in POLICY["publication_entrypoints"]:
            with self.subTest(identity=identity):
                projected = MODULE.project_publication_entrypoints(identity, source, POLICY)
                self.assertEqual(projected["on"], {"workflow_dispatch": source["on"]["workflow_dispatch"]})
                self.assertEqual({k: v for k, v in projected.items() if k != "on"}, {k: v for k, v in source.items() if k != "on"})
                self.assertEqual(source, before)
                self.assertEqual(MODULE.project_publication_entrypoints(identity, projected, POLICY), projected)

    def test_canonical_and_unselected_publication_remain_callable(self):
        source = {"on": {"workflow_call": None, "workflow_dispatch": None}, "jobs": {}}
        for policy in [None, {"schema": 1}, {"schema": 1, "publication_entrypoints": {"release-github": {"mode": "canonical"}}}]:
            self.assertEqual(MODULE.project_publication_entrypoints("release-github", source, policy), source)
        self.assertEqual(MODULE.project_publication_entrypoints("release-artifacts", source, POLICY), source)

    def test_manual_API_requires_canonical_dispatch_without_other_entrypoints(self):
        for events in [{"workflow_call": None}, {"workflow_dispatch": None, "pull_request": None}, {"workflow_dispatch": "untyped"}]:
            with self.subTest(events=events), self.assertRaises(ValueError):
                MODULE.project_publication_entrypoints("release-github", {"on": events, "jobs": {}}, POLICY)

    def test_actual_local_manual_calls_are_rejected_and_internal_calls_admitted(self):
        for identity in POLICY["publication_entrypoints"]:
            for suffix in ["", "@main"]:
                documents = {".github/workflows/authored.yml": {"jobs": {"publish": {"uses": f"./.github/workflows/{identity}.yml{suffix}"}}}}
                with self.subTest(identity=identity, suffix=suffix), self.assertRaisesRegex(ValueError, "manual-only publication"):
                    MODULE.validate_publication_calls(documents, POLICY)
        MODULE.validate_publication_calls({"release.yml": {"jobs": {"artifact": {"uses": "./.github/workflows/release-artifacts.yml"}}}}, POLICY)

    def test_whitespace_cannot_hide_manual_workflow_identity(self):
        documents = {"authored.yml": {"jobs": {"publish": {"uses": " ./.github/workflows/release-github.yml "}}}}
        with self.assertRaisesRegex(ValueError, "manual-only publication"):
            MODULE.validate_publication_calls(documents, POLICY)

    def test_default_call_admission_has_no_manual_owner_inference(self):
        documents = {"authored.yml": {"jobs": {"publish": {"uses": "./.github/workflows/release-github.yml"}}}}
        for policy in [None, {"schema": 1}, {"schema": 1, "publication_entrypoints": {"release-github": {"mode": "canonical"}}}]:
            MODULE.validate_publication_calls(documents, policy)

    def test_call_admission_rejects_unstructured_actual_jobs(self):
        for document in [{"jobs": []}, {"jobs": {"call": None}}, {"jobs": {"call": {"uses": False}}}, {"jobs": {"call": {"uses": ""}}}]:
            with self.subTest(document=document), self.assertRaises(ValueError):
                MODULE.validate_publication_calls({"authored.yml": document}, POLICY)


class ControllerPublicationTests(unittest.TestCase):
    def policy(self):
        return {"schema": 1, "publication_entrypoints": {"release-pypi": {"mode": "manual-only", "controller": "iac"}}}

    def test_pypi_credentials_depend_on_read_only_authenticated_admission(self):
        source = {"on": {"workflow_dispatch": {"inputs": {"release_tag": {"type": "string"}}}, "workflow_call": None},
                  "jobs": {"publish": {"runs-on": "ubuntu-latest", "env": {"PYPI_TOKEN": "${{ secrets.PYPI_TOKEN }}"},
                                       "steps": [{"run": "uv publish"}]}}}
        projected = MODULE.project_publication_entrypoints("release-pypi", source, self.policy())
        guard = projected["jobs"]["publication_admission"]
        self.assertEqual(guard["permissions"], {"contents": "read", "checks": "read"})
        self.assertNotIn("secrets.", str(guard))
        self.assertEqual(projected["jobs"]["publish"]["needs"], ["publication_admission"])
        self.assertIn("needs.publication_admission.result == 'success'", projected["jobs"]["publish"]["if"])
        self.assertTrue(projected["on"]["workflow_dispatch"]["inputs"]["accepted_commit"]["required"])
        self.assertNotIn("workflow_call", projected["on"])
        self.assertEqual(MODULE.project_publication_entrypoints("release-pypi", projected, self.policy()), projected)

    def test_renamed_and_indirect_external_publishers_are_rejected(self):
        for job in [{"steps": [{"run": "uv publish"}]},
                    {"steps": [{"uses": "actions/deploy-pages@immutable"}]},
                    {"uses": "bijux/bijux-canon/.github/workflows/release-pypi.yml@main"}]:
            with self.subTest(job=job), self.assertRaises(ValueError):
                MODULE.validate_publication_calls({".github/workflows/renamed.yml": {"jobs": {"publish": job}}}, self.policy())
        MODULE.validate_publication_calls({".github/workflows/ci.yml": {"jobs": {"evidence": {"steps": [
            {"uses": "actions/upload-artifact@immutable"}, {"run": "cargo publish --dry-run"}]}}}}, self.policy())


if __name__ == "__main__":
    unittest.main()
