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
AUTOMERGE_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "automerge-pr.yml"
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
    def test_pure_preparation_has_no_destination_selection_or_mutation(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        before = copy.deepcopy(manifest)
        with mock.patch.object(MODULE, "resolve_repository_checkout", side_effect=AssertionError("writer selected")):
            prepared = MODULE.prepare_repo_files("bijux-atlas", manifest)
        self.assertIn(".github/release.env", prepared)
        self.assertIn(".github/workflows/ci.yml", prepared)
        self.assertEqual(manifest, before)

    def test_pure_preparation_and_existing_writer_emit_same_all_repository_bytes(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        for repo in manifest["repositories"]:
            with self.subTest(repository=repo["name"]), tempfile.TemporaryDirectory() as workspace:
                root = Path(workspace)
                expected = MODULE.prepare_repo_files(repo["name"], manifest)
                with mock.patch.object(MODULE, "resolve_repository_checkout", return_value=root):
                    MODULE.render_repo(repo["name"], manifest)
                for relative, body in expected.items():
                    if body is None:
                        self.assertFalse((root / relative).exists())
                    else:
                        self.assertEqual((root / relative).read_bytes(), body)

    def test_selected_dependency_wrapper_preserves_types_and_existing_conditions(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        repo["workflow_execution_policy"] = {"schema": 1, "dependency_pull_requests": "skip-managed-jobs"}
        original_job = {"name": "owned wrapper", "if": "${{ always() && needs.build.result == 'success' }}",
                        "needs": "build", "runs-on": "ubuntu-latest",
                        "env": {"PYTHON_VERSION": "3.11", "OWNED_FLAG": "false"}, "steps": [{"run": "owned command"}]}
        repo["workflow_wrappers"] = {"verify": {"on": {"pull_request_target": None, "pull_request_review": None},
                                                   "jobs": {"owned": original_job}}}
        before = copy.deepcopy(repo)
        with tempfile.TemporaryDirectory() as workspace:
            destination = Path(workspace)
            with mock.patch.object(MODULE, "resolve_repository_checkout", return_value=destination):
                MODULE.render_repo("bijux-atlas", manifest)
            actual = MODULE.WORKFLOW_EXECUTION.parse_workflow(
                (destination / ".github/workflows/verify.yml").read_bytes(), "owned wrapper"
            )
        job = actual["jobs"]["owned"]
        self.assertEqual({k: v for k, v in job.items() if k != "if"},
                         {k: v for k, v in original_job.items() if k != "if"})
        self.assertIn("always() && needs.build.result == 'success'", job["if"])
        self.assertIn("pull_request_review", job["if"])
        self.assertIn("pull_request_target", job["if"])
        self.assertEqual(repo, before)

    def test_selected_dependency_wrapper_refuses_untyped_condition_before_writes(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        repo["workflow_execution_policy"] = {"schema": 1, "dependency_pull_requests": "skip-managed-jobs"}
        repo["workflow_wrappers"] = {"ci": {"on": "pull_request", "jobs": {"owned": {}}},
                                     "verify": {"on": "pull_request_review", "jobs": {"invalid": {"if": False}}}}
        with mock.patch.object(MODULE, "write_if_needed") as write:
            with self.assertRaisesRegex(ValueError, "nonempty source-owned expression"):
                MODULE.render_repo("bijux-atlas", manifest)
            write.assert_not_called()

    def test_consumer_renderer_uses_synchronized_github_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            consumer_source = repository_root / ".bijux/shared/bijux-gh"
            consumer_source.mkdir(parents=True)

            self.assertEqual(
                MODULE.shared_github_source_root(repository_root),
                consumer_source,
            )

    def test_manual_publisher_wrapper_call_refuses_before_render(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        repo["workflow_execution_policy"] = {"schema": 1, "publication_entrypoints": {"release-github": {"mode": "manual-only"}}}
        repo["workflow_wrappers"] = {"ci": {"on": "pull_request", "jobs": {"publisher": {"uses": "./.github/workflows/release-github.yml"}}}}
        with mock.patch.object(MODULE, "write_if_needed") as write:
            with self.assertRaisesRegex(ValueError, "manual-only publication"):
                MODULE.render_repo("bijux-atlas", manifest)
            write.assert_not_called()

    def test_selected_workflow_emitter_preserves_version_boolean_and_empty_types(self) -> None:
        document = {"on": {"workflow_dispatch": {}}, "jobs": {"owned": {"with": {"python-version": "3.11", "flag": "false", "null-string": "null", "number-string": "007", "enabled": True, "arguments": [], "options": {}, "run": "first\nsecond", "trailing": "line\n\n"}}}}
        emitted = MODULE.render_yaml_document(document, preserve_scalar_types=True)
        self.assertEqual(MODULE.WORKFLOW_EXECUTION.parse_workflow(emitted.encode(), "projected.yml"), document)
        self.assertIn('"python-version": "3.11"', emitted)
        self.assertIn("python-version: 3.11", MODULE.render_yaml_document(document))

    def test_explicit_automatic_policy_projects_wrapper_events_before_render(self) -> None:
        repo = {"name": "bijux-atlas", "workflow_wrappers": {"ci": {"on": {"push": {"branches": ["main"]}, "pull_request": None, "workflow_dispatch": None}, "jobs": {"fast": {"name": "owned check"}}}}}
        prepared = MODULE.prepare_workflow_wrappers(repo, {"schema": 1, "automatic_runs": "repository-policy-only"})
        self.assertNotIn("push", prepared["ci"]["on"])
        self.assertEqual(prepared["ci"]["jobs"], repo["workflow_wrappers"]["ci"]["jobs"])
        self.assertIn("push", repo["workflow_wrappers"]["ci"]["on"])

    def test_invalid_later_wrapper_refuses_before_any_governed_render(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        repo["workflow_execution_policy"] = {"schema": 1, "automatic_runs": "repository-policy-only"}
        repo["workflow_wrappers"] = {"ci": {"on": "pull_request", "jobs": {}}, "verify": {"on": "push", "jobs": {}}}
        with tempfile.TemporaryDirectory() as checkout:
            root = Path(checkout)
            sentinel = root / ".github/release.env"
            sentinel.parent.mkdir()
            sentinel.write_text("owned preimage\n")
            with mock.patch.object(MODULE, "resolve_repository_checkout", return_value=root):
                with self.assertRaisesRegex(ValueError, "no workflow entrypoint"):
                    MODULE.render_repo("bijux-atlas", manifest)
            self.assertEqual(sentinel.read_text(), "owned preimage\n")
            self.assertEqual([p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()], [".github/release.env"])

    def test_batch_refuses_invalid_later_policy_before_any_render(self) -> None:
        manifest = {"repositories": [{"name": "bijux-atlas"}, {"name": "bijux-canon", "workflow_execution_policy": {"schema": True}}]}
        with tempfile.TemporaryDirectory() as workspace:
            path = Path(workspace) / "manifest.json"
            path.write_text(json.dumps(manifest))
            with (mock.patch.object(sys, "argv", ["render_repo_configs.py", "--manifest", str(path)]),
                  mock.patch.object(MODULE, "render_repo") as render):
                with self.assertRaises(ValueError):
                    MODULE.main()
                render.assert_not_called()

    def test_invalid_execution_policy_refuses_before_render_writes(self) -> None:
        with tempfile.TemporaryDirectory() as checkout:
            root = Path(checkout)
            sentinel = root / ".github/release.env"
            sentinel.parent.mkdir()
            sentinel.write_text("owned preimage\n", encoding="utf-8")
            manifest = {"repositories": [{"name": "bijux-atlas", "workflow_execution_policy": {"schema": True}}]}
            with mock.patch.object(MODULE, "resolve_repository_checkout", return_value=root):
                with self.assertRaises(ValueError):
                    MODULE.render_repo("bijux-atlas", manifest)
            self.assertEqual(sentinel.read_text(), "owned preimage\n")
            self.assertEqual([p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()], [".github/release.env"])

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
        expected_package_slugs = [
            "bijux-canon-dev",
            "bijux-canon-runtime",
            "bijux-canon-agent",
            "bijux-canon-ingest",
            "bijux-canon-reason",
            "bijux-canon-index",
            "compat-bijux-canon",
            "compat-agentic-flows",
            "compat-bijux-agent",
            "compat-bijux-rag",
            "compat-bijux-rar",
            "compat-bijux-vex",
        ]
        self.assertEqual(
            supported_python["strategy"]["matrix"]["package_slug"],
            expected_package_slugs,
        )
        self.assertEqual(supported_python["strategy"]["max-parallel"], 12)
        supported_python_command = next(
            step["run"]
            for step in supported_python["steps"]
            if step.get("name")
            == "Test one supported package distribution"
        )
        self.assertIn('selected_python="$(command -v python)"', supported_python_command)
        self.assertIn(
            'PACKAGE="${{ matrix.package_slug }}" test', supported_python_command
        )
        self.assertNotIn("for package in", supported_python_command)
        self.assertEqual(
            supported_python["steps"][-1]["with"]["name"],
            "${{ matrix.package_slug }}-test-py${{ matrix.python-version }}",
        )

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
        self.assertIn(
            'UV_CACHE_DIR="${RUNNER_TEMP}/bijux-installed-family-uv-cache"',
            installed_command,
        )
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
            "astral-sh/setup-uv": "c18668ad3cf93ea998bef934396af7bb5c839dc7",
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
            "e2a55d2ffb04f378e9626c28d38b36d230d1e12f"
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

    def test_expensive_wrappers_skip_dependabot_pull_requests(self) -> None:
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

        for wrapper_name in ("ci", "verify"):
            with self.subTest(wrapper_name=wrapper_name):
                rendered = MODULE.inject_dependabot_pull_request_skip(
                    wrapper_name, copy.deepcopy(wrapper)
                )

                self.assertEqual(
                    rendered["jobs"]["fast-tier"]["if"],
                    "${{ github.event_name != 'pull_request' || github.event.pull_request.user.login != 'dependabot[bot]' }}",
                )
                self.assertEqual(
                    rendered["jobs"]["slow-tier"]["if"],
                    "${{ (github.event_name != 'pull_request' || github.event.pull_request.user.login != 'dependabot[bot]') && (github.event_name == 'workflow_dispatch') }}",
                )

    def test_governance_wrapper_keeps_dependabot_verification(self) -> None:
        wrapper = {
            "jobs": {
                "policy": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "make policy"}],
                }
            }
        }

        rendered = MODULE.inject_dependabot_pull_request_skip(
            "github-policy", copy.deepcopy(wrapper)
        )

        self.assertEqual(rendered, wrapper)

    def test_ci_wrapper_stays_unchanged(self) -> None:
        wrapper = {
            "jobs": {
                "fast-tier": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "make ci-fast"}],
                }
            }
        }

        rendered = MODULE.normalize_workflow_wrapper("ci", copy.deepcopy(wrapper))

        self.assertEqual(rendered, wrapper)

    def test_verify_wrapper_runs_independently_with_normalized_paths(self) -> None:
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

        rendered = MODULE.normalize_workflow_wrapper("verify", copy.deepcopy(wrapper))

        self.assertNotIn("policy_gate", rendered["jobs"])
        self.assertNotIn("needs", rendered["jobs"]["verify"])
        self.assertEqual(
            rendered["on"]["pull_request"]["paths"],
            [".bijux/**", ".github/**", "src/**"],
        )

    def test_automerge_defers_to_required_checks_without_preflight_race(self) -> None:
        workflow = AUTOMERGE_WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("  enable:\n", workflow)
        self.assertNotIn("policy-gate", workflow)
        self.assertNotIn("check_workflow_prerequisites.py", workflow)


if __name__ == "__main__":
    unittest.main()
