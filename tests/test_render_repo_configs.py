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
    def test_consumer_renderer_uses_synchronized_github_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            consumer_source = repository_root / ".bijux/shared/bijux-gh"
            consumer_source.mkdir(parents=True)

            self.assertEqual(
                MODULE.shared_github_source_root(repository_root),
                consumer_source,
            )

    def test_canon_ci_covers_supported_package_and_platform_matrix(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        repository = next(
            repository
            for repository in manifest["repositories"]
            if repository["name"] == "bijux-canon"
        )
        verify_jobs = repository["workflow_wrappers"]["verify"]["jobs"]
        package_matrix = verify_jobs["package"]["strategy"]["matrix"]["include"]

        self.assertEqual(len(package_matrix), 6)
        supported_python = verify_jobs["supported_python"]
        self.assertEqual(
            supported_python["strategy"]["matrix"]["python-version"],
            ["3.11", "3.12", "3.13", "3.14"],
        )
        supported_python_command = next(
            step["run"]
            for step in supported_python["steps"]
            if step.get("name")
            == "Test every canonical and compatibility distribution"
        )
        self.assertIn('selected_python="$(command -v python)"', supported_python_command)
        self.assertIn('make PYTHON="${selected_python}" test', supported_python_command)
        for package in (
            "compat-bijux-canon",
            "compat-agentic-flows",
            "compat-bijux-agent",
            "compat-bijux-rag",
            "compat-bijux-rar",
            "compat-bijux-vex",
        ):
            self.assertIn(package, supported_python_command)
        self.assertIn('PACKAGE="${package}" test', supported_python_command)

        installed_family = verify_jobs["installed_family"]
        self.assertEqual(
            installed_family["strategy"]["matrix"],
            {
                "runner": ["ubuntu-latest", "macos-latest"],
                "python-version": ["3.11", "3.12", "3.13", "3.14"],
            },
        )
        installed_command = next(
            step["run"]
            for step in installed_family["steps"]
            if step.get("name") == "Build and install the distribution family"
        )
        self.assertIn("uv build --all-packages --wheel", installed_command)
        self.assertIn("= 13", installed_command)
        self.assertIn("bijux-canon-repository", installed_command)
        self.assertNotIn("bijux_canon_repository", installed_command)
        self.assertIn("uv pip check", installed_command)
        self.assertIn('"${venv_dir}/bin/bijux" --version', installed_command)

        self.assertEqual(
            verify_jobs["verification_ready"]["needs"],
            ["repository", "package", "supported_python", "installed_family"],
        )

    def test_canon_release_and_required_checks_cover_public_delivery(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        repository = next(
            repository
            for repository in manifest["repositories"]
            if repository["name"] == "bijux-canon"
        )
        release_env = {
            entry["key"]: entry["value"] for entry in repository["release_env"]
        }
        expected_public = {
            "agentic-flows",
            "bijux-agent",
            "bijux-canon",
            "bijux-canon-agent",
            "bijux-canon-index",
            "bijux-canon-ingest",
            "bijux-canon-reason",
            "bijux-canon-runtime",
            "bijux-rag",
            "bijux-rar",
            "bijux-vex",
        }
        for key in (
            "BIJUX_RELEASE_BUILD_MATRIX_JSON",
            "BIJUX_PYPI_PACKAGE_MATRIX_JSON",
            "BIJUX_GHCR_RELEASE_PACKAGE_MATRIX_JSON",
        ):
            self.assertEqual(
                {entry["package_slug"] for entry in release_env[key]},
                expected_public,
            )

        ruleset = json.loads(MODULE.render_required_status_ruleset(repository))
        required_rule = next(
            rule
            for rule in ruleset["rules"]
            if rule["type"] == "required_status_checks"
        )
        contexts = {
            check["context"]
            for check in required_rule["parameters"]["required_status_checks"]
        }
        self.assertIn("verification-ready", contexts)
        reference = MODULE.render_required_status_reference(repository)
        self.assertIn(
            "`verification-ready` (from workflow `repo / verify`)", reference
        )

    def test_python_ci_uses_current_setup_action_revisions(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        expected_revisions = {
            "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
            "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
            "astral-sh/setup-uv": "20cfd1bf945f4377ade1205e4dbc17946fc9a30d",
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
            "6c977a6ca4077a0ceb28ffbe03f59d46e9ac8772"
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
