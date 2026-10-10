from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from github_workflows.policy_fixtures import byte_tree, projection_fixture, source_fixture


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "shared/bijux-makes-py/repository/governance_projection.py"
SPEC = importlib.util.spec_from_file_location("python_governance_projection", HELPER)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PythonGovernanceProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.target = Path(self.temporary.name) / "product"
        self.source, self.policy = source_fixture(self.target / "artifacts/cache", selected=True)
        self.git(self.source, "init", "--quiet")
        self.git(self.source, "config", "user.name", "Bijux verification")
        self.git(self.source, "config", "user.email", "verification@example.invalid")
        self.git(self.source, "add", ".github", "shared")
        self.git(self.source, "commit", "--quiet", "-m", "test(governance): own projection fixture")
        self.git(self.source, "remote", "add", "origin", MODULE.OFFICIAL_ORIGIN)
        self.sha = self.git(self.source, "rev-parse", "HEAD")
        (self.source / ".git/FETCH_HEAD").write_text(self.sha + "\n")
        projection_fixture(self.source, self.policy, self.target)
        self.pin = self.target / MODULE.PIN_PATH
        self.pin.parent.mkdir(parents=True, exist_ok=True)
        self.pin.write_text(self.sha + "\n")
        (self.target / ".gitignore").write_text("artifacts/\n")
        self.git(self.target, "init", "--quiet")
        self.git(self.target, "config", "user.name", "Bijux verification")
        self.git(self.target, "config", "user.email", "verification@example.invalid")
        self.git(self.target, "add", ".github", ".bijux", ".gitignore")
        self.git(self.target, "commit", "--quiet", "-m", "test(governance): bind product source pin")
        self.fetches = []
        self.delegations = []

    @staticmethod
    def git(root: Path, *arguments: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()

    def verify(self) -> None:
        real_git = MODULE.git
        real_run = subprocess.run

        def execute_git(root: Path, *arguments: str) -> str:
            if arguments[0] == "fetch":
                # This boundary fixture substitutes transport, never GitHub acceptance.
                self.fetches.append((root, arguments))
                return ""
            return real_git(root, *arguments)

        def execute_verifier(command, **options):
            if command[:2] != [sys.executable, str(self.source / ".github/scripts/check_workflow_projection.py")]:
                return real_run(command, **options)
            self.delegations.append((command, options))
            self.policy.validate_source_snapshots(self.source)
            self.policy.verify_projection(self.source, self.target, "bijux-atlas")
            return subprocess.CompletedProcess(command, 0)

        with mock.patch.dict(os.environ, {"BIJUX_STD_ROOT": str(self.source), "BIJUX_STD_ALLOW_LOCAL_SOURCE": "1"}):
            with mock.patch.object(MODULE, "git", side_effect=execute_git), mock.patch.object(MODULE.subprocess, "run", side_effect=execute_verifier):
                MODULE.verify(self.target, "bijux-atlas")

    def test_guarded_publication_projection_passes_without_mutation(self) -> None:
        raw = self.source / "shared/bijux-gh/workflows/deploy-docs.yml"
        rendered = self.target / ".github/workflows/deploy-docs.yml"
        self.assertNotEqual(raw.read_bytes(), rendered.read_bytes())
        before = byte_tree(self.target)
        self.verify()
        self.assertEqual(byte_tree(self.target), before)
        self.assertEqual(len(self.fetches), 1)
        command, options = self.delegations[0]
        self.assertEqual(command, [sys.executable, str(self.source / ".github/scripts/check_workflow_projection.py"), "--target", str(self.target), "--repo", "bijux-atlas", "--source-sha", self.sha])
        self.assertNotIn("BIJUX_STD_ALLOW_LOCAL_SOURCE", options["env"])
        self.assertEqual(options["env"]["BIJUX_STD_GIT_URL"], MODULE.OFFICIAL_ORIGIN)

    def test_projected_guard_drift_rejects_without_repair(self) -> None:
        path = self.target / ".github/workflows/deploy-docs.yml"
        path.write_bytes(path.read_bytes() + b"# unreviewed drift\n")
        before = byte_tree(self.target)
        with self.assertRaises(ValueError):
            self.verify()
        self.assertEqual(byte_tree(self.target), before)

    def test_wrong_origin_rejects_before_fetch_or_verifier(self) -> None:
        self.git(self.source, "remote", "set-url", "origin", "https://example.invalid/source")
        with self.assertRaisesRegex(ValueError, "official GitHub origin"):
            self.verify()
        self.assertEqual(self.fetches, [])
        self.assertEqual(self.delegations, [])

    def test_wrong_source_head_rejects_before_fetch_or_verifier(self) -> None:
        self.pin.write_text("0" * 40 + "\n")
        with self.assertRaisesRegex(ValueError, "HEAD differs"):
            self.verify()
        self.assertEqual(self.fetches, [])
        self.assertEqual(self.delegations, [])

    def test_dirty_source_rejects_before_verifier(self) -> None:
        (self.source / ".github/CODEOWNERS").write_text("changed")
        with self.assertRaisesRegex(ValueError, "modified or untracked"):
            self.verify()
        self.assertEqual(self.delegations, [])

    def test_untracked_pin_rejects_before_source_admission(self) -> None:
        self.git(self.target, "rm", "--cached", MODULE.PIN_PATH)
        with self.assertRaises(subprocess.CalledProcessError):
            self.verify()
        self.assertEqual(self.fetches, [])

    def test_incidental_external_source_rejects_before_git(self) -> None:
        with mock.patch.dict(os.environ, {"BIJUX_STD_ROOT": str(ROOT)}):
            with self.assertRaisesRegex(ValueError, "owning artifacts cache"):
                MODULE.accepted_source(self.target, self.sha)

    def test_default_cache_bootstrap_fetches_exact_pin_inside_owning_artifacts(self) -> None:
        real_git = MODULE.git
        fetches = []

        def transport(root: Path, *arguments: str) -> str:
            if arguments[0] == "fetch":
                fetches.append(arguments)
                return real_git(root, "fetch", "--quiet", "--depth", "1", str(self.source), self.sha)
            return real_git(root, *arguments)

        before = byte_tree(self.target / ".github")
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(MODULE, "git", side_effect=transport):
                source = MODULE.accepted_source(self.target, self.sha)
        self.assertEqual(source, self.target / "artifacts/standards/accepted-source" / self.sha)
        self.assertEqual(self.git(source, "rev-parse", "HEAD"), self.sha)
        self.assertEqual(self.git(source, "remote", "get-url", "origin"), MODULE.OFFICIAL_ORIGIN)
        self.assertEqual(len(fetches), 2)
        self.assertTrue(all(arguments[-1] == self.sha for arguments in fetches))
        self.assertEqual(byte_tree(self.target / ".github"), before)

    def test_make_delegates_without_rendering_or_copying_product_files(self) -> None:
        script = self.target / "artifacts/check.py"
        script.write_text("import pathlib,sys\npathlib.Path(__file__).with_suffix('.args').write_text(repr(sys.argv[1:]))\n")
        before = byte_tree(self.target / ".github")
        result = subprocess.run(
            ["make", "--no-print-directory", "-f", str(ROOT / "shared/bijux-makes-py/bijux.mk"), "bijux-standard-check", f"PROJECT_DIR={self.target}", "PROJECT_SLUG=bijux-atlas", f"BIJUX_STANDARD_CHECK_SCRIPT={script}"],
            cwd=self.target, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(script.with_suffix('.args').read_text(), repr(["--target", str(self.target), "--repo", "bijux-atlas"]))
        self.assertEqual(byte_tree(self.target / ".github"), before)


if __name__ == "__main__":
    unittest.main()
