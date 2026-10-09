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

    def test_policy_helper_is_canonical_managed_script(self) -> None:
        self.assertIn((".github/scripts/workflow_execution.py", ".github/scripts/workflow_execution.py"), MODULE.BASE_FILE_MAPPINGS)

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
