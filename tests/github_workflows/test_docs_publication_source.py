from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from .policy_fixtures import MODULE, ROOT
import copy
import json


class DocumentationPublicationSourceTests(unittest.TestCase):
    def workflow(self):
        return MODULE.parse_workflow((ROOT / "shared/bijux-gh/workflows/deploy-docs.yml").read_bytes(), "deploy-docs")

    def test_full_publication_build_budget_preserves_separate_deployment_budget(self):
        workflow = self.workflow()
        self.assertEqual(workflow["jobs"]["build"]["timeout-minutes"], 60)
        self.assertEqual(workflow["jobs"]["deploy"]["timeout-minutes"], 10)
        self.assertEqual(workflow["jobs"]["deploy"]["needs"], "build")
        steps = workflow["jobs"]["build"]["steps"]
        names = [step.get("name", "") for step in steps]
        self.assertLess(names.index("Build docs site"), names.index("Verify docs site"))
        self.assertLess(names.index("Verify docs site"), names.index("Upload Pages artifact"))
        verifier = steps[names.index("Verify docs site")]
        uploader = steps[names.index("Upload Pages artifact")]
        self.assertNotIn("continue-on-error", verifier)
        self.assertNotIn("continue-on-error", uploader)
        self.assertNotIn("always()", uploader.get("if", ""))
        self.assertIn("verify_command", verifier["env"]["DOCS_COMMAND"])

    def test_all_twelve_manual_projections_keep_budget_and_source_admission(self):
        manifest = json.loads((ROOT / ".github/standards/repo-config.manifest.json").read_text())
        self.assertEqual(len(manifest["repositories"]), 12)
        source = self.workflow()
        before = copy.deepcopy(source)
        for repo in manifest["repositories"]:
            with self.subTest(repository=repo["name"]):
                policy = repo["workflow_execution_policy"]
                projected = MODULE.project_publication_entrypoints("deploy-docs", source, policy)
                self.assertEqual(set(projected["on"]), {"workflow_dispatch"})
                self.assertTrue(projected["on"]["workflow_dispatch"]["inputs"]["accepted_commit"]["required"])
                self.assertEqual(projected["jobs"]["build"]["timeout-minutes"], 60)
                self.assertEqual(projected["jobs"]["deploy"]["timeout-minutes"], 10)
                prior_source = copy.deepcopy(source)
                prior_source["jobs"]["build"]["timeout-minutes"] = 30
                prior = MODULE.project_publication_entrypoints("deploy-docs", prior_source, policy)
                prior["jobs"]["build"]["timeout-minutes"] = 60
                self.assertEqual(projected, prior)
                projected_steps = {step.get("name"): step for step in projected["jobs"]["build"]["steps"]}
                for name in ["Admit accepted documentation standards", "Verify docs site", "Upload Pages artifact"]:
                    original = next(step for step in source["jobs"]["build"]["steps"] if step.get("name") == name)
                    self.assertEqual(projected_steps[name], original)
                for identity in ["build", "deploy"]:
                    self.assertIn("publication_admission", projected["jobs"][identity]["needs"])
                    self.assertIn("needs.publication_admission.result == 'success'", projected["jobs"][identity]["if"])
        self.assertEqual(source, before)

    def test_source_admission_precedes_dependency_setup_and_build(self):
        steps = self.workflow()["jobs"]["build"]["steps"]
        names = [step.get("name", "") for step in steps]
        admission = names.index("Admit accepted documentation standards")
        self.assertGreater(admission, names.index("Checkout repository"))
        self.assertLess(admission, names.index("Resolve docs deploy configuration"))
        command = steps[admission]["run"]
        self.assertIn("https://github.com/bijux/bijux-std.git", command)
        self.assertIn("BIJUX_STD_ROOT=%s", command)
        self.assertIn("BIJUX_STD_REF=%s", command)
        self.assertNotIn("secrets.", command)

    def test_missing_or_malformed_pins_fail_before_any_source_preparation(self):
        command = next(step["run"] for step in self.workflow()["jobs"]["build"]["steps"] if step.get("name") == "Admit accepted documentation standards")
        root = ROOT / "artifacts" / "docs-publication-controls"
        root.mkdir(parents=True, exist_ok=True)
        for pin in [None, "main", "a" * 39, "a" * 41, "../untrusted", "A" * 40]:
            with self.subTest(pin=pin), tempfile.TemporaryDirectory(dir=root) as directory:
                target = Path(directory)
                (target / ".github/standards").mkdir(parents=True)
                if pin is not None:
                    (target / ".github/standards/bijux-std.sha").write_text(pin + "\n")
                result = subprocess.run(["bash", "-c", command], cwd=target, env={**os.environ, "GITHUB_ENV": str(target / "env")}, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((target / "artifacts/accepted-standard").exists())
                self.assertFalse((target / "env").exists())
