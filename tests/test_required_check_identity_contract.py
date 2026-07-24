from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GITHUB_STANDARD = ROOT / "shared" / "bijux-gh"


class RequiredCheckIdentityContractTests(unittest.TestCase):
    def test_branch_protection_contexts_match_stable_workflow_jobs(self) -> None:
        expected_contexts = {
            "policy / github",
            "policy / pr approval",
            "std / standard",
            "std / report",
        }
        ruleset = json.loads(
            (
                GITHUB_STANDARD / "rulesets" / "main-branch-protection.json"
            ).read_text(encoding="utf-8")
        )
        required_status_rule = next(
            rule
            for rule in ruleset["rules"]
            if rule["type"] == "required_status_checks"
        )
        configured_contexts = {
            check["context"]
            for check in required_status_rule["parameters"][
                "required_status_checks"
            ]
        }

        self.assertEqual(configured_contexts, expected_contexts)

        workflow_expectations = {
            "workflows/github-policy.yml": "    name: policy / github",
            "workflows/pr-approval-policy.yml": (
                "    name: policy / pr approval"
            ),
        }
        for relative_path, job_name in workflow_expectations.items():
            workflow = (GITHUB_STANDARD / relative_path).read_text(
                encoding="utf-8"
            )
            self.assertIn(job_name, workflow)

        status_reference = (
            GITHUB_STANDARD / "required-status-checks.md"
        ).read_text(encoding="utf-8")
        for context in expected_contexts:
            self.assertIn(f"`{context}`", status_reference)


if __name__ == "__main__":
    unittest.main()
