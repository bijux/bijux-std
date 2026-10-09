from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "scripts"
    / "sync_github_standards.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bijux_std_sync_github_standards",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SyncGithubStandardsTests(unittest.TestCase):
    def test_explicit_dependency_selection_gates_actual_managed_PR_jobs(self) -> None:
        manifest = copy.deepcopy(MODULE.load_manifest())
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        repo["workflow_allowlist"] = [entry["id"] for entry in manifest["workflow_inventory"]["managed_workflows"]]
        repo["workflow_execution_policy"] = {"schema": 1, "dependency_pull_requests": "skip-managed-jobs"}
        with tempfile.TemporaryDirectory() as workspace:
            destination = Path(workspace)
            with mock.patch.object(MODULE, "resolve_repository_checkout", return_value=destination):
                MODULE.copy_repo_files("bijux-atlas", repo, manifest)
            qualified = []
            for path in (destination / ".github/workflows").glob("*.yml"):
                actual = MODULE.WORKFLOW_EXECUTION.parse_workflow(path.read_bytes(), path.name)
                events = actual["on"]
                if set(events if isinstance(events, (dict, list)) else [events]) & {"pull_request", "pull_request_target", "pull_request_review"}:
                    for identity, job in actual["jobs"].items():
                        self.assertIn("dependabot[bot]", job["if"])
                        self.assertIn("pull_request_review", job["if"])
                        self.assertIn("pull_request_target", job["if"])
                        qualified.append((path.name, identity))
            self.assertIn(("automerge-pr.yml", "enable"), qualified)
            self.assertIn(("github-policy.yml", "policy"), qualified)
            self.assertIn(("pr-approval-policy.yml", "pr-approval"), qualified)
            self.assertIn(("labeler.yml", "label"), qualified)
            source = MODULE.STD_REPO / "shared/bijux-gh/workflows/labeler.yml"
            self.assertEqual((destination / ".bijux/shared/bijux-gh/workflows/labeler.yml").read_bytes(), source.read_bytes())

    def test_untyped_dependency_job_refuses_before_any_copy(self) -> None:
        manifest = copy.deepcopy(MODULE.load_manifest())
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        repo["workflow_execution_policy"] = {"schema": 1, "dependency_pull_requests": "skip-managed-jobs"}
        with tempfile.TemporaryDirectory() as workspace:
            standard = Path(workspace) / "owning-standard"
            shutil.copytree(MODULE.STD_REPO / ".github", standard / ".github")
            shutil.copytree(MODULE.STD_REPO / "shared/bijux-gh", standard / "shared/bijux-gh")
            source = standard / "shared/bijux-gh/workflows/github-policy.yml"
            original = source.read_text()
            source.write_text(original.replace("  policy:\n", "  policy:\n    if: false\n", 1))
            destination = Path(workspace) / "projection-fixture"
            destination.mkdir()
            sentinel = destination / "owned.txt"
            sentinel.write_text("owned preimage\n")
            with (mock.patch.object(MODULE, "STD_REPO", standard),
                  mock.patch.object(MODULE, "resolve_repository_checkout", return_value=destination),
                  mock.patch.object(MODULE, "copy_file_mapping") as copy_file):
                with self.assertRaisesRegex(ValueError, "nonempty source-owned expression"):
                    MODULE.copy_repo_files("bijux-atlas", repo, manifest)
                copy_file.assert_not_called()
            self.assertEqual(sentinel.read_text(), "owned preimage\n")
            self.assertEqual([p.name for p in destination.iterdir()], ["owned.txt"])

    def test_actual_docs_runtime_restricts_refs_before_preparation(self) -> None:
        manifest = copy.deepcopy(MODULE.load_manifest())
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        repo["workflow_execution_policy"] = {"schema": 1, "publication_entrypoints": {
            "deploy-docs": {"mode": "manual-only", "refs": "main-only"},
        }}
        with tempfile.TemporaryDirectory() as workspace:
            destination = Path(workspace)
            with mock.patch.object(MODULE, "resolve_repository_checkout", return_value=destination):
                MODULE.copy_repo_files("bijux-atlas", repo, manifest)
            source = MODULE.WORKFLOW_EXECUTION.parse_workflow(
                (MODULE.STD_REPO / "shared/bijux-gh/workflows/deploy-docs.yml").read_bytes(), "canonical docs"
            )
            actual = MODULE.WORKFLOW_EXECUTION.parse_workflow(
                (destination / ".github/workflows/deploy-docs.yml").read_bytes(), "projected docs"
            )
            self.assertEqual(actual, MODULE.WORKFLOW_EXECUTION.project_publication_entrypoints(
                "deploy-docs", source, repo["workflow_execution_policy"]
            ))
            self.assertEqual(actual["jobs"]["build"]["steps"][0]["name"], "Validate publication event and ref")
            self.assertIn("github.ref == 'refs/heads/main'", actual["jobs"]["deploy"]["if"])
            self.assertEqual((destination / ".bijux/shared/bijux-gh/workflows/deploy-docs.yml").read_bytes(),
                             (MODULE.STD_REPO / "shared/bijux-gh/workflows/deploy-docs.yml").read_bytes())

    def test_unreviewed_docs_guard_refuses_before_any_destination_write(self) -> None:
        manifest = copy.deepcopy(MODULE.load_manifest())
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        repo["workflow_execution_policy"] = {"schema": 1, "publication_entrypoints": {
            "deploy-docs": {"mode": "manual-only", "refs": "main-only"},
        }}
        for variant in ["boolean-predicate", "missing-guard"]:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as workspace:
                standard = Path(workspace) / "owning-standard"
                shutil.copytree(MODULE.STD_REPO / ".github", standard / ".github")
                shutil.copytree(MODULE.STD_REPO / "shared/bijux-gh", standard / "shared/bijux-gh")
                source = standard / "shared/bijux-gh/workflows/deploy-docs.yml"
                original = source.read_text()
                if variant == "boolean-predicate":
                    predicate = next(line for line in original.splitlines() if line.startswith("    if: "))
                    changed = original.replace(predicate, "    if: false", 1)
                else:
                    changed = original.replace("name: Validate publication event and ref", "name: Unreviewed guard", 1)
                self.assertNotEqual(original, changed)
                source.write_text(changed)
                destination = Path(workspace) / "publication-fixture"
                destination.mkdir()
                sentinel = destination / "owned.txt"
                sentinel.write_text("owned preimage\n")
                with (mock.patch.object(MODULE, "STD_REPO", standard),
                      mock.patch.object(MODULE, "resolve_repository_checkout", return_value=destination),
                      mock.patch.object(MODULE, "copy_file_mapping") as copy_file):
                    with self.assertRaises(ValueError):
                        MODULE.copy_repo_files("bijux-atlas", repo, manifest)
                    copy_file.assert_not_called()
                self.assertEqual(sentinel.read_text(), "owned preimage\n")
                self.assertEqual([p.name for p in destination.iterdir()], ["owned.txt"])

    def test_old_flat_generated_helper_retires_only_with_owned_unchanged_preimage(self) -> None:
        manifest = MODULE.load_manifest()
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        for state in ["owned", "unowned", "modified"]:
            with self.subTest(state=state), tempfile.TemporaryDirectory() as workspace:
                target = Path(workspace)
                helper = target / ".github/scripts/workflow_execution.py"
                helper.parent.mkdir(parents=True)
                helper.write_text("source-owned preimage\n")
                checksum = target / ".github/bijux-std-shared.sha256"
                digest = hashlib.sha256(helper.read_bytes()).hexdigest()
                checksum.write_text(f"{digest}  .github/scripts/{'other.py' if state == 'unowned' else 'workflow_execution.py'}\n")
                if state == "modified":
                    helper.write_text("preserve user change\n")
                before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
                with mock.patch.object(MODULE, "resolve_repository_checkout", return_value=target):
                    if state == "owned":
                        MODULE.copy_repo_files("bijux-atlas", repo, manifest)
                        self.assertFalse(helper.exists())
                        self.assertTrue((target / ".github/scripts/workflow_execution/schema.py").exists())
                    else:
                        with self.assertRaisesRegex(ValueError, "managed preimage"):
                            MODULE.copy_repo_files("bijux-atlas", repo, manifest)
                        self.assertEqual({p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}, before)

    def test_manual_publisher_call_refuses_before_any_destination_write(self) -> None:
        manifest = copy.deepcopy(MODULE.load_manifest())
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        repo["workflow_execution_policy"] = {"schema": 1, "publication_entrypoints": {"release-github": {"mode": "manual-only"}}}
        for suffix in ["yml", "yaml"]:
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as workspace:
                target = Path(workspace) / "bijux-atlas"
                workflow = target / f".github/workflows/authored.{suffix}"
                workflow.parent.mkdir(parents=True)
                workflow.write_text("on: workflow_dispatch\njobs:\n  publish:\n    uses: ./.github/workflows/release-github.yml\n")
                before = workflow.read_bytes()
                with mock.patch.object(MODULE, "resolve_repository_checkout", return_value=target):
                    with self.assertRaisesRegex(ValueError, "manual-only publication"):
                        MODULE.copy_repo_files("bijux-atlas", repo, manifest)
                self.assertEqual(workflow.read_bytes(), before)
                self.assertEqual([p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()], [f".github/workflows/authored.{suffix}"])

    def test_wrapper_call_refuses_before_any_copy(self) -> None:
        manifest = copy.deepcopy(MODULE.load_manifest())
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        repo["workflow_execution_policy"] = {"schema": 1, "publication_entrypoints": {"release-github": {"mode": "manual-only"}}}
        repo["workflow_wrappers"] = {"ci": {"on": "pull_request", "jobs": {"publish": {"uses": "./.github/workflows/release-github.yml"}}}}
        with tempfile.TemporaryDirectory() as workspace, mock.patch.object(MODULE, "resolve_repository_checkout", return_value=Path(workspace)), mock.patch.object(MODULE, "copy_file_mapping") as copy_file:
            with self.assertRaisesRegex(ValueError, "manual-only publication"):
                MODULE.copy_repo_files("bijux-atlas", repo, manifest)
            copy_file.assert_not_called()

    def test_later_invalid_workflow_source_refuses_before_copying(self) -> None:
        manifest = copy.deepcopy(MODULE.load_manifest())
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        repo["workflow_execution_policy"] = {"schema": 1, "automatic_runs": "repository-policy-only"}
        with tempfile.TemporaryDirectory() as workspace:
            standard = Path(workspace) / "standard"
            shutil.copytree(MODULE.STD_REPO / ".github", standard / ".github")
            shutil.copytree(MODULE.STD_REPO / "shared/bijux-gh", standard / "shared/bijux-gh")
            source = standard / "shared/bijux-gh/workflows/github-policy.yml"
            source.write_text("on: push\non: workflow_dispatch\njobs: {}\n")
            destination = Path(workspace) / "bijux-atlas"
            destination.mkdir()
            sentinel = destination / "owned.txt"
            sentinel.write_text("owned preimage\n")
            with (mock.patch.object(MODULE, "STD_REPO", standard),
                  mock.patch.object(MODULE, "resolve_repository_checkout", return_value=destination)):
                with self.assertRaisesRegex(ValueError, "duplicate YAML mapping"):
                    MODULE.copy_repo_files("bijux-atlas", repo, manifest)
            self.assertEqual(sentinel.read_text(), "owned preimage\n")
            self.assertEqual([p.name for p in destination.iterdir()], ["owned.txt"])

    def test_missing_parser_refuses_before_copying(self) -> None:
        manifest = copy.deepcopy(MODULE.load_manifest())
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        repo["workflow_execution_policy"] = {"schema": 1, "automatic_runs": "repository-policy-only"}
        with (mock.patch.object(MODULE.WORKFLOW_EXECUTION, "parse_workflow", side_effect=RuntimeError("ruby is required")),
              mock.patch.object(MODULE, "copy_file_mapping") as copy_file):
            with self.assertRaisesRegex(RuntimeError, "ruby is required"):
                MODULE.copy_repo_files("bijux-atlas", repo, manifest)
            copy_file.assert_not_called()

    def test_explicit_automatic_policy_preserves_only_repository_main_push(self) -> None:
        manifest = copy.deepcopy(MODULE.load_manifest())
        repo = MODULE.find_repo_config(manifest, "bijux-atlas")
        repo["workflow_execution_policy"] = {"schema": 1, "automatic_runs": "repository-policy-only"}
        with tempfile.TemporaryDirectory() as workspace:
            target = Path(workspace) / "bijux-atlas"
            target.mkdir()
            with mock.patch.object(MODULE, "resolve_repository_checkout", return_value=target):
                MODULE.copy_repo_files("bijux-atlas", repo, manifest)
            main_push = []
            tag_push = []
            for path in (target / ".github/workflows").glob("*.yml"):
                parsed = json.loads(subprocess.check_output(["ruby", "-ryaml", "-rjson", "-e", "puts JSON.generate(YAML.safe_load(File.read(ARGV[0]), aliases: false))", str(path)], text=True))
                events = parsed.get("on", parsed.get("true", {}))
                push = events.get("push", {}) or {}
                if "main" in push.get("branches", []):
                    main_push.append(path.name)
                if "tags" in push:
                    tag_push.append(path.name)
            self.assertEqual(sorted(main_push), ["github-policy.yml"])
            self.assertEqual(tag_push, [])

    def test_direct_copy_refuses_invalid_policy_and_inventory_before_write(self) -> None:
        for manifest in [
            {"repositories": [{"name": "bijux-atlas", "workflow_execution_policy": {"schema": True}}]},
            {"repositories": [{"name": "bijux-atlas"}], "workflow_inventory": {"version": True, "managed_workflows": []}},
        ]:
            with self.subTest(manifest=manifest), mock.patch.object(MODULE, "copy_file_mapping") as copy_file:
                with self.assertRaises(ValueError):
                    MODULE.copy_repo_files("bijux-atlas", manifest["repositories"][0], manifest)
                copy_file.assert_not_called()

    def test_batch_preflight_precedes_standard_render_checksum_and_git(self) -> None:
        manifest = {"repositories": [{"name": "bijux-std"}, {"name": "bijux-atlas"}, {"name": "bijux-canon", "workflow_execution_policy": {"schema": True}}]}
        with (mock.patch.object(MODULE, "load_manifest", return_value=manifest),
              mock.patch.object(MODULE, "run") as git_run,
              mock.patch.object(MODULE.subprocess, "run") as process,
              mock.patch.object(MODULE, "refresh_shared_checksums") as checksum,
              mock.patch.object(sys, "argv", ["sync_github_standards.py", "--repo", "bijux-atlas", "--repo", "bijux-canon"])):
            with self.assertRaises(ValueError):
                MODULE.main()
            git_run.assert_not_called()
            process.assert_not_called()
            checksum.assert_not_called()

    def test_policy_package_is_canonical_managed_source(self) -> None:
        for name in ["__init__", "source_loading", "schema", "yaml_io", "events", "refs", "dependency_prs", "publication"]:
            path = f".github/scripts/workflow_execution/{name}.py"
            self.assertIn((path, path), MODULE.BASE_FILE_MAPPINGS)
        self.assertNotIn((".github/scripts/workflow_execution.py", ".github/scripts/workflow_execution.py"), MODULE.BASE_FILE_MAPPINGS)

    def test_observe_merge_reads_status_once(self) -> None:
        payload = '{"number":7,"state":"OPEN","mergeStateStatus":"BLOCKED"}'
        with mock.patch.object(MODULE, "run", return_value=payload) as run:
            observed = MODULE.observe_merge(Path("/workspace"), 7)

        self.assertEqual(observed["status"], "waiting_external")
        run.assert_called_once()

    def test_capability_manifest_is_not_a_github_sync_mapping(self) -> None:
        self.assertNotIn(
            (
                "shared/shared-dir-sha256.txt",
                ".bijux/shared/shared-dir-sha256.txt",
            ),
            MODULE.BASE_FILE_MAPPINGS,
        )

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

    def test_refresh_shared_checksums_binds_repository_rendered_files(self) -> None:
        with tempfile.TemporaryDirectory() as checkout:
            root = Path(checkout)
            managed = root / ".github/required-status-checks.md"
            managed.parent.mkdir(parents=True)
            managed.write_text("repository-specific\n", encoding="utf-8")
            checksum = root / ".github/bijux-std-shared.sha256"
            checksum.write_text(
                "0" * 64 + "  .github/required-status-checks.md\n",
                encoding="utf-8",
            )

            MODULE.refresh_shared_checksums(root)

            expected = hashlib.sha256(managed.read_bytes()).hexdigest()
            self.assertEqual(
                checksum.read_text(encoding="utf-8"),
                f"{expected}  .github/required-status-checks.md\n",
            )
            MODULE.verify_shared_checksums(root)


if __name__ == "__main__":
    unittest.main()
