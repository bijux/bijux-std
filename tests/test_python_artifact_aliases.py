from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ALIAS_SCRIPT = (
    REPOSITORY_ROOT
    / "shared"
    / "bijux-makes-py"
    / "repository"
    / "artifact_aliases.py"
)
TEST_ROOT = REPOSITORY_ROOT / "artifacts" / "tests" / "python-artifact-aliases"


class PythonArtifactAliasTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)
        TEST_ROOT.mkdir(parents=True)

    def run_aliases(
        self,
        repo_root: Path,
        command: str,
        *arguments: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        process_dir = TEST_ROOT / "process"
        process_dir.mkdir(exist_ok=True)
        return subprocess.run(
            [
                sys.executable,
                str(ALIAS_SCRIPT),
                command,
                "--repo-root",
                str(repo_root),
                *arguments,
            ],
            check=check,
            capture_output=True,
            text=True,
            env={**os.environ, "TMPDIR": str(process_dir)},
        )

    def test_setup_preserves_legacy_directory(self) -> None:
        repo_root = TEST_ROOT / "preserve"
        legacy_venv = repo_root / ".venv"
        legacy_venv.mkdir(parents=True)
        sentinel = legacy_venv / "environment.txt"
        sentinel.write_text("preserve me\n", encoding="utf-8")

        self.run_aliases(repo_root, "root")

        self.assertTrue(legacy_venv.is_dir())
        self.assertFalse(legacy_venv.is_symlink())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve me\n")

    def test_migration_is_inspection_only_without_apply(self) -> None:
        repo_root = TEST_ROOT / "inspection"
        legacy_venv = repo_root / ".venv"
        legacy_venv.mkdir(parents=True)
        (legacy_venv / "environment.txt").write_text("data\n", encoding="utf-8")

        result = self.run_aliases(repo_root, "migrate")

        self.assertIn("legacy-directory\t.venv", result.stdout)
        self.assertIn("size=", result.stdout)
        self.assertIn("bytes=", result.stdout)
        self.assertIn("inspection-only", result.stdout)
        self.assertTrue(legacy_venv.is_dir())
        self.assertFalse(legacy_venv.is_symlink())

    def test_migration_moves_content_and_materializes_alias(self) -> None:
        repo_root = TEST_ROOT / "migration"
        legacy_venv = repo_root / ".venv"
        legacy_venv.mkdir(parents=True)
        (legacy_venv / "environment.txt").write_text("data\n", encoding="utf-8")
        canonical_venv = repo_root / "artifacts/root/check-venv"
        canonical_venv.mkdir(parents=True)

        result = self.run_aliases(repo_root, "migrate", "--apply")

        self.assertIn("migrated\t.venv", result.stdout)
        self.assertTrue(legacy_venv.is_symlink())
        self.assertEqual(
            os.readlink(legacy_venv),
            "artifacts/root/check-venv",
        )
        self.assertEqual(
            (canonical_venv / "environment.txt").read_text(encoding="utf-8"),
            "data\n",
        )

    def test_migration_preserves_occupied_destination_for_recovery(self) -> None:
        repo_root = TEST_ROOT / "collision"
        alias_path = repo_root / ".tox"
        alias_path.mkdir(parents=True)
        (alias_path / "legacy.txt").write_text("legacy\n", encoding="utf-8")
        blocked_target = repo_root / "artifacts/root/tox"
        blocked_target.mkdir(parents=True)
        (blocked_target / "existing.txt").write_text("occupied\n", encoding="utf-8")

        result = self.run_aliases(repo_root, "migrate", "--apply")

        recovery_path = repo_root / "artifacts/recovery/artifact-aliases/root/tox"
        self.assertIn("preserved\tartifacts/root/tox", result.stdout)
        self.assertTrue(alias_path.is_symlink())
        self.assertEqual(
            (blocked_target / "legacy.txt").read_text(encoding="utf-8"),
            "legacy\n",
        )
        self.assertEqual(
            (recovery_path / "existing.txt").read_text(encoding="utf-8"),
            "occupied\n",
        )

    def test_migration_preflights_recovery_collisions_before_moving(self) -> None:
        repo_root = TEST_ROOT / "recovery-collision"
        alias_path = repo_root / ".tox"
        alias_path.mkdir(parents=True)
        (alias_path / "legacy.txt").write_text("legacy\n", encoding="utf-8")
        target_path = repo_root / "artifacts/root/tox"
        target_path.mkdir(parents=True)
        (target_path / "existing.txt").write_text("occupied\n", encoding="utf-8")
        recovery_path = repo_root / "artifacts/recovery/artifact-aliases/root/tox"
        recovery_path.mkdir(parents=True)

        result = self.run_aliases(repo_root, "migrate", "--apply", check=False)

        self.assertEqual(result.returncode, 2)
        self.assertIn("recovery destinations already exist", result.stderr)
        self.assertTrue(alias_path.is_dir())
        self.assertFalse(alias_path.is_symlink())
        self.assertTrue(target_path.is_dir())

    def test_shared_make_contract_exposes_explicit_migration(self) -> None:
        root_make = (
            REPOSITORY_ROOT
            / "shared"
            / "bijux-makes-py"
            / "repository"
            / "root.mk"
        ).read_text(encoding="utf-8")
        api_make = (
            REPOSITORY_ROOT / "shared" / "bijux-makes-py" / "api-contract.mk"
        ).read_text(encoding="utf-8")

        self.assertIn("artifact-aliases-inspect:", root_make)
        self.assertIn("artifact-aliases-migrate:", root_make)
        self.assertIn("migrate --apply", root_make)
        self.assertNotIn("rm -rf .hypothesis", api_make)
        self.assertIn("Refusing to delete legacy .hypothesis", api_make)

    def test_shared_make_environment_routes_tool_state_under_artifacts(self) -> None:
        root_env = (
            REPOSITORY_ROOT
            / "shared"
            / "bijux-makes-py"
            / "root"
            / "env.mk"
        ).read_text(encoding="utf-8")
        package_env = (
            REPOSITORY_ROOT
            / "shared"
            / "bijux-makes-py"
            / "repository"
            / "env.mk"
        ).read_text(encoding="utf-8")
        dispatch = (
            REPOSITORY_ROOT
            / "shared"
            / "bijux-makes-py"
            / "root"
            / "package-dispatch.mk"
        ).read_text(encoding="utf-8")

        for variable in (
            "PYTHONPYCACHEPREFIX",
            "XDG_CACHE_HOME",
            "HYPOTHESIS_STORAGE_DIRECTORY",
            "UV_CACHE_DIR",
            "PIP_CACHE_DIR",
            "NPM_CONFIG_CACHE",
            "TMPDIR",
        ):
            self.assertIn(f"export {variable} :=", root_env)
            self.assertIn(f"export {variable} :=", package_env)
            expected_dispatch = (
                f'{variable}="$(abspath $(MONOREPO_ROOT))/artifacts/'
            )
            self.assertIn(expected_dispatch, dispatch)
        self.assertIn("export TOX_WORK_DIR :=", root_env)
        self.assertIn("export COVERAGE_FILE :=", package_env)

    def test_artifact_contract_documents_recoverable_migration(self) -> None:
        contract = (
            REPOSITORY_ROOT / "shared" / "bijux-makes-py" / "CONTRACT.md"
        ).read_text(encoding="utf-8")

        self.assertIn("`make artifact-aliases-inspect`", contract)
        self.assertIn("`make artifact-aliases-migrate`", contract)
        self.assertIn("inspection is read-only", contract.lower())
        self.assertIn("artifacts/recovery/artifact-aliases/", contract)
        self.assertIn("never\ndeletes or replaces a real", contract)


if __name__ == "__main__":
    unittest.main()
