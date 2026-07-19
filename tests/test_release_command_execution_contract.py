from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = REPO_ROOT / "shared" / "bijux-gh" / "workflows"


class ReleaseCommandExecutionContractTests(unittest.TestCase):
    def test_configured_commands_are_passed_through_step_environments(self) -> None:
        workflows = {
            "release-crates.yml": (
                ("WAIT_FOR_CI_COMMAND", "wait_for_ci_command"),
                ("PLAN_COMMAND", "plan_command"),
                ("VERIFY_TOKEN_COMMAND", "verify_token_command"),
                ("PUBLISH_COMMAND", "publish_command"),
            ),
            "release-github.yml": (
                ("WAIT_FOR_CI_COMMAND", "wait_for_ci_command"),
                ("PLAN_COMMAND", "plan_command"),
                ("PREPARE_COMMAND", "prepare_command"),
            ),
            "release-pypi.yml": (
                ("WAIT_FOR_CI_COMMAND", "wait_for_ci_command"),
                ("PLAN_COMMAND", "plan_command"),
                ("PREPARE_COMMAND", "prepare_command"),
                ("PUBLISH_COMMAND", "publish_command"),
            ),
        }

        for workflow_name, command_variables in workflows.items():
            with self.subTest(workflow=workflow_name):
                workflow = (WORKFLOW_ROOT / workflow_name).read_text(encoding="utf-8")
                self.assertNotIn('eval "${{ needs.resolve.outputs.', workflow)
                for command_variable, output_name in command_variables:
                    self.assertIn(
                        f"{command_variable}: "
                        f"${{{{ needs.resolve.outputs.{output_name} }}}}",
                        workflow,
                    )
                    self.assertIn(f'eval "${{{command_variable}}}"', workflow)


if __name__ == "__main__":
    unittest.main()
