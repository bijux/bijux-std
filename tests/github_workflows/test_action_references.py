"""Executable workflow reference admission, independent of YAML spelling."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .policy_fixtures import MODULE, ROOT

CHECKER = ROOT / ".github/scripts/check_pinned_actions.py"
SHA = "0123456789abcdef0123456789abcdef01234567"


class ActionReferenceAdmissionTests(unittest.TestCase):
    def check(self, content: str):
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.yml"
            workflow.write_text(content)
            return subprocess.run([sys.executable, str(CHECKER), str(workflow)], text=True, capture_output=True)

    def test_mutable_references_cannot_hide_behind_yaml_spelling(self):
        sources = {
            "quoted": 'jobs: {verify: {steps: [{"uses": "actions/checkout@main"}]}}',
            "named": "jobs:\n  verify:\n    steps:\n      - name: checkout\n        uses: actions/checkout@v7\n",
            "reusable": "jobs: {verify: {uses: owner/repo/.github/workflows/verify.yml@main}}",
            "nested-action": "jobs: {verify: {steps: [{uses: owner/repo/actions/build@v1}]}}",
            "expression": "jobs: {verify: {steps: [{uses: '${{ inputs.action }}'}]}}",
        }
        for name, content in sources.items():
            with self.subTest(name=name):
                result = self.check(content)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("unpinned action reference", result.stderr)
                self.assertIn("jobs.verify", result.stderr)

    def test_full_sha_references_and_existing_local_container_exceptions_pass(self):
        content = f'''jobs:
  verify:
    steps:
      - name: checkout
        "uses": "actions/checkout@{SHA}"
      - uses: owner/repo/actions/build@{SHA}
      - uses: ./owned/action
      - uses: docker://alpine:3.22
  reusable:
    uses: owner/repo/.github/workflows/verify.yml@{SHA}
  local:
    uses: ./.github/workflows/verify.yml
'''
        result = self.check(content)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_malformed_or_ambiguous_yaml_fails_closed(self):
        sources = [
            "jobs: [", "jobs: {}\n---\njobs: {}", "jobs: {}\njobs: {}",
            "jobs: {verify: {steps: [{uses: actions/checkout@main, uses: './owned'}]}}",
            "jobs: {verify: {steps: [!!python/object/apply:os.system ['false']]}}",
            "jobs: {verify: {steps: &steps [{uses: './owned'}]}, alias: {steps: *steps}}",
        ]
        for content in sources:
            with self.subTest(content=content):
                result = self.check(content)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_reference_and_execution_shapes_require_correct_types(self):
        sources = [
            "jobs: {verify: {uses: null}}", "jobs: {verify: {uses: 123}}",
            "jobs: {verify: {steps: [{uses: [actions/checkout@main]}]}}",
            "jobs: {verify: {steps: [{uses: ''}]}}", "jobs: {verify: 123}",
            "jobs: {verify: {steps: {uses: './owned'}}}", "jobs: {verify: {steps: ['not-a-step']}}",
        ]
        for content in sources:
            with self.subTest(content=content):
                result = self.check(content)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_input_named_uses_is_not_an_action_reference(self):
        result = self.check("jobs: {verify: {steps: [{run: echo, env: {uses: ordinary-input}}]}}")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mutable_manifest_selected_workflow_is_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / "shared.yml"
            workflow.write_text("jobs: {verify: {uses: owner/repo/.github/workflows/verify.yml@main}}")
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({"workflow_inventory": {"managed_workflows": [{"source": str(workflow)}]}}))
            result = subprocess.run([sys.executable, str(CHECKER), "--manifest-managed", str(manifest)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("unpinned action reference", result.stderr)

    def test_absent_parser_cannot_admit_an_unchecked_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.yml"
            workflow.write_text(f"jobs: {{verify: {{steps: [{{uses: actions/checkout@{SHA}}}]}}}}")
            environment = dict(os.environ, PATH=directory)
            result = subprocess.run([sys.executable, str(CHECKER), str(workflow)], env=environment, text=True, capture_output=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("ruby is required", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_each_hosted_caller_explicitly_admits_the_parser_before_validation(self):
        policy = MODULE.parse_workflow((ROOT / "shared/bijux-gh/workflows/github-policy.yml").read_bytes(), "policy")
        standard = MODULE.parse_workflow((ROOT / ".github/workflows/bijux-std.yml").read_bytes(), "standard")
        for name, steps in [("policy", policy["jobs"]["policy"]["steps"]), ("standard", standard["jobs"]["checks"]["steps"])]:
            with self.subTest(name=name):
                checker = next(index for index, step in enumerate(steps) if "check_pinned_actions.py" in step.get("run", ""))
                provision = next(index for index, step in enumerate(steps) if step.get("uses", "").startswith("ruby/setup-ruby@"))
                admission = next(index for index, step in enumerate(steps) if "Ruby 3.3.12 required" in step.get("run", ""))
                self.assertLess(provision, admission)
                self.assertLess(admission, checker)
                self.assertEqual(steps[provision]["with"]["ruby-version"], "3.3.12")
                self.assertIn("YAML.respond_to?(:parse_stream)", steps[admission]["run"])
                if name == "policy":
                    self.assertNotIn("if", steps[provision])
                    self.assertNotIn("if", steps[admission])
                else:
                    self.assertEqual(steps[provision]["if"], "${{ matrix.check == 'standard' }}")
                    self.assertEqual(steps[admission]["if"], "${{ matrix.check == 'standard' }}")
