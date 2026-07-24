from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "scripts"
    / "render_repo_configs.py"
)
MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "standards"
    / "repo-config.manifest.json"
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
    def test_python_ci_uses_current_setup_action_revisions(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        expected_revisions = {
            "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
            "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
            "astral-sh/setup-uv": "c771a70e6277c0a99b617c7a806ffedaca235ff9",
            "actions/setup-node": "820762786026740c76f36085b0efc47a31fe5020",
            "actions/setup-java": "03ad4de0992f5dab5e18fcb136590ce7c4a0ac95",
        }

        for repository in manifest["repositories"]:
            for wrapper in repository.get("workflow_wrappers", {}).values():
                for job in wrapper.get("jobs", {}).values():
                    for step in job.get("steps", []):
                        action = step.get("uses", "")
                        for name, revision in expected_revisions.items():
                            if action.startswith(f"{name}@"):
                                self.assertEqual(
                                    action,
                                    f"{name}@{revision}",
                                    f"{repository['name']} uses a stale {name} revision",
                                )

    def test_rust_repositories_expose_foundational_ci_gates(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        repositories = {
            repository["name"]: repository
            for repository in manifest["repositories"]
        }

        for repository_name in (
            "bijux-atlas",
            "bijux-core",
            "bijux-genomics",
            "bijux-gnss",
        ):
            wrapper = repositories[repository_name]["workflow_wrappers"]["ci"]
            self.assertEqual(wrapper["name"], "continuous integration")
            jobs = wrapper["jobs"]
            expected_job_names = {
                "fmt": "format",
                "lint": "lint",
                "audit": "dependency audit",
                "test": "test",
            }
            for gate, expected_job_name in expected_job_names.items():
                self.assertEqual(jobs[gate]["name"], expected_job_name)
                commands = [
                    step.get("run")
                    for step in jobs[gate]["steps"]
                    if step.get("run")
                ]
                self.assertIn(f"make {gate}", commands)

    def test_genomics_ci_uses_governed_fast_rust_lanes(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        repository = next(
            repository
            for repository in manifest["repositories"]
            if repository["name"] == "bijux-genomics"
        )
        wrapper = repository["workflow_wrappers"]["ci"]

        self.assertEqual(wrapper["env"]["RUST_TOOLCHAIN_VERSION"], "1.95.0")
        self.assertEqual(wrapper["on"]["workflow_dispatch"], {})
        self.assertNotIn("slow-tier", wrapper["jobs"])

        rust_toolchain_action = (
            "dtolnay/rust-toolchain@"
            "e97e2d8cc328f1b50210efc529dca0028893a2d9"
        )
        for job in wrapper["jobs"].values():
            for step in job.get("steps", []):
                if step.get("uses") == rust_toolchain_action:
                    self.assertEqual(
                        step["with"]["toolchain"],
                        "${{ env.RUST_TOOLCHAIN_VERSION }}",
                    )

        sccache_action = (
            "mozilla/sccache-action@"
            "7d986dd989559c6ecdb630a3fd2557667be217ad"
        )
        for gate in ("fmt", "lint", "audit", "test"):
            uses = {
                step.get("uses")
                for step in wrapper["jobs"][gate]["steps"]
                if step.get("uses")
            }
            self.assertIn(sccache_action, uses)

    def test_repository_checkout_variable_normalizes_repository_name(self) -> None:
        self.assertEqual(
            MODULE.repository_checkout_variable("bijux.github.io"),
            "BIJUX_REPOSITORY_PATH_BIJUX_GITHUB_IO",
        )

    def test_resolve_repository_checkout_uses_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as checkout:
            with mock.patch.dict(
                os.environ,
                {"BIJUX_REPOSITORY_PATH_BIJUX_GNSS": checkout},
            ):
                self.assertEqual(
                    MODULE.resolve_repository_checkout("bijux-gnss"),
                    Path(checkout).resolve(),
                )

    def test_resolve_repository_checkout_rejects_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            with (
                mock.patch.object(MODULE, "ROOT", Path(workspace)),
                mock.patch.dict(os.environ, {}, clear=True),
            ):
                with self.assertRaisesRegex(
                    FileNotFoundError,
                    "BIJUX_REPOSITORY_PATH_BIJUX_GNSS",
                ):
                    MODULE.resolve_repository_checkout("bijux-gnss")

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
