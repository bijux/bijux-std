from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "scripts"
    / "render_repo_configs.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bijux_std_render_repo_configs",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RenderRepoConfigsTests(unittest.TestCase):
    def test_ci_wrapper_skips_dependabot_pull_requests(self) -> None:
        wrapper = {
            "jobs": {
                "fast-tier": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "make ci-fast"}],
                },
                "slow-tier": {
                    "if": "${{ github.event_name == 'workflow_dispatch' }}",
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "make test-all"}],
                },
            }
        }

        rendered = MODULE.inject_dependabot_pull_request_skip("ci", copy.deepcopy(wrapper))

        self.assertEqual(
            rendered["jobs"]["fast-tier"]["if"],
            "${{ github.event_name != 'pull_request' || github.event.pull_request.user.login != 'dependabot[bot]' }}",
        )
        self.assertEqual(
            rendered["jobs"]["slow-tier"]["if"],
            "${{ (github.event_name != 'pull_request' || github.event.pull_request.user.login != 'dependabot[bot]') && (github.event_name == 'workflow_dispatch') }}",
        )

    def test_ci_wrapper_stays_ungated(self) -> None:
        wrapper = {
            "jobs": {
                "fast-tier": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "make ci-fast"}],
                }
            }
        }

        rendered = MODULE.inject_policy_gate("ci", copy.deepcopy(wrapper))

        self.assertEqual(rendered, wrapper)

    def test_verify_wrapper_keeps_policy_gate_and_normalized_paths(self) -> None:
        wrapper = {
            "on": {
                "pull_request": {
                    "paths": ["src/**", ".github/workflows/verify.yml"],
                }
            },
            "jobs": {
                "verify": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "make verify"}],
                }
            },
        }

        rendered = MODULE.inject_policy_gate("verify", copy.deepcopy(wrapper))

        self.assertIn("policy_gate", rendered["jobs"])
        self.assertEqual(rendered["jobs"]["verify"]["needs"], "policy_gate")
        self.assertEqual(
            rendered["on"]["pull_request"]["paths"],
            [".bijux/**", ".github/**", "src/**"],
        )


if __name__ == "__main__":
    unittest.main()
