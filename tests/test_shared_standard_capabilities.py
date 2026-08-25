from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    REPOSITORY_ROOT / "shared/bijux-checks/bijux-std-checks.yml"
)
RESOLVER_PATH = (
    REPOSITORY_ROOT
    / "shared/bijux-checks/scripts/resolve-shared-directories.sh"
)
UPDATER_PATH = (
    REPOSITORY_ROOT
    / "shared/bijux-checks/update-bijux-std.sh"
)
DIGEST_PATH = (
    REPOSITORY_ROOT
    / "shared/bijux-checks/scripts/directory-tree-sha256.sh"
)
CONTRACT_VALIDATOR_PATH = (
    REPOSITORY_ROOT
    / "shared/bijux-checks/scripts/validate-shared-contracts.sh"
)
STANDARD_WORKFLOW_PATH = (
    REPOSITORY_ROOT / ".github/workflows/bijux-std.yml"
)
TEST_ROOT = (
    REPOSITORY_ROOT
    / "artifacts/tests/shared-standard-capabilities"
)


class SharedStandardCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)
        TEST_ROOT.mkdir(parents=True)

    def resolve(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(RESOLVER_PATH), *arguments],
            check=False,
            text=True,
            capture_output=True,
        )

    def test_all_directories_include_each_shared_make_library(self) -> None:
        result = self.resolve("--all", str(CONFIG_PATH))
        self.assertEqual(result.returncode, 0, result.stderr)
        directories = result.stdout.splitlines()

        self.assertIn("shared/bijux-makes", directories)
        self.assertIn("shared/bijux-makes-py", directories)
        self.assertIn("shared/bijux-makes-rs", directories)
        self.assertEqual(len(directories), len(set(directories)))

    def test_python_parity_roster_covers_all_python_products(self) -> None:
        shared_make = (
            REPOSITORY_ROOT / "shared/bijux-makes-py/bijux.mk"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "BIJUX_PY_REPOS ?= bijux-canon bijux-proteomics "
            "bijux-pollenomics bijux-phylogenetics",
            shared_make,
        )

    def test_repository_specific_status_checks_are_rendered_outputs(self) -> None:
        shared_make = (
            REPOSITORY_ROOT / "shared/bijux-makes-py/bijux.mk"
        ).read_text(encoding="utf-8")
        rendered_block, required_block = shared_make.split(
            "BIJUX_STANDARD_REQUIRED_FILES ?=", maxsplit=1
        )

        for path in (
            ".github/required-status-checks.md",
            ".github/rulesets/main-branch-protection.json",
        ):
            self.assertIn(path, rendered_block)
            self.assertNotIn(path.removeprefix(".github/"), required_block)

    def test_python_security_evidence_fails_closed_without_suppressions(self) -> None:
        shared_root = REPOSITORY_ROOT / "shared/bijux-makes-py"
        security_make = (shared_root / "ci/security.mk").read_text(encoding="utf-8")
        sbom_make = (shared_root / "ci/sbom.mk").read_text(encoding="utf-8")
        package_make = (shared_root / "package.mk").read_text(encoding="utf-8")

        self.assertIn("SECURITY_IGNORE_IDS           ?=\n", security_make)
        self.assertIn(
            "BANDIT_FLAGS                  ?= --severity-level high "
            "--confidence-level high",
            security_make,
        )
        self.assertIn("Bandit is mandatory", security_make)
        self.assertIn("Dependency vulnerability auditing is mandatory", security_make)
        self.assertIn("SBOM_IGNORE_IDS          ?=\n", sbom_make)
        self.assertIn("Ungoverned SBOM vulnerability suppressions", sbom_make)
        self.assertNotIn("PYSEC-", security_make + sbom_make + package_make)
        self.assertNotIn("CVE-", security_make + sbom_make + package_make)
        for line in sbom_make.splitlines():
            if "$(SBOM_PIP_AUDIT)" in line:
                self.assertNotIn("|| true", line)

    def test_python_sibling_parity_is_scoped_to_the_accepted_standard(self) -> None:
        shared_make = (
            REPOSITORY_ROOT / "shared/bijux-makes-py/bijux.mk"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "BIJUX_PY_STD_PIN_REL ?= .github/standards/bijux-std.sha",
            shared_make,
        )
        self.assertIn('cmp -s "$$current_pin_file" "$$other_pin_file"', shared_make)
        self.assertIn("accepted standard pins differ", shared_make)
        self.assertIn("match the local synchronized source", shared_make)

        workspace = TEST_ROOT / "workspace"
        for repository, pin, content in (
            ("current", "a" * 40, "current\n"),
            ("sibling", "b" * 40, "different\n"),
        ):
            root = workspace / repository
            system_root = root / ".bijux/shared/bijux-makes-py"
            local_root = root / "makes/bijux-py"
            pin_path = root / ".github/standards/bijux-std.sha"
            system_root.mkdir(parents=True)
            local_root.mkdir(parents=True)
            pin_path.parent.mkdir(parents=True)
            (system_root / "contract.mk").write_text(content, encoding="utf-8")
            local_content = "current\n" if repository == "current" else content
            (local_root / "contract.mk").write_text(local_content, encoding="utf-8")
            pin_path.write_text(f"{pin}\n", encoding="utf-8")

        command = [
            "make",
            "-f",
            str(REPOSITORY_ROOT / "shared/bijux-makes-py/bijux.mk"),
            "check-bijux-standard",
            f"PROJECT_DIR={workspace / 'current'}",
            "PROJECT_SLUG=current",
            f"BIJUX_PY_WORKSPACE_DIR={workspace}",
            "BIJUX_PY_REPOS=current sibling",
            "BIJUX_PY_SYSTEM_REL=.bijux/shared/bijux-makes-py",
            "BIJUX_PY_REQUIRED_FILES=contract.mk",
        ]
        staggered = subprocess.run(command, check=False, text=True, capture_output=True)
        self.assertEqual(staggered.returncode, 0, staggered.stdout + staggered.stderr)
        self.assertIn("accepted standard pins differ", staggered.stdout)

        sibling_pin = workspace / "sibling/.github/standards/bijux-std.sha"
        sibling_pin.write_text(f"{'a' * 40}\n", encoding="utf-8")
        same_standard = subprocess.run(
            command, check=False, text=True, capture_output=True
        )
        self.assertNotEqual(same_standard.returncode, 0)
        self.assertIn("Shared make drift", same_standard.stdout)

    def test_shared_manifest_matches_complete_directory_trees(self) -> None:
        manifest_path = REPOSITORY_ROOT / "shared/shared-dir-sha256.txt"
        entries = {}
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            digest, directory = line.split(maxsplit=1)
            entries[directory] = digest

        all_directories = self.resolve("--all", str(CONFIG_PATH))
        self.assertEqual(all_directories.returncode, 0, all_directories.stderr)
        self.assertEqual(
            list(entries),
            all_directories.stdout.splitlines(),
        )

        for directory, expected_digest in entries.items():
            directory_path = REPOSITORY_ROOT / directory
            actual_digest = subprocess.run(
                [str(DIGEST_PATH), str(directory_path)],
                check=True,
                text=True,
                capture_output=True,
            ).stdout.strip()
            self.assertEqual(actual_digest, expected_digest, directory)

    def test_digest_ignores_runtime_cache_files(self) -> None:
        source_tree = TEST_ROOT / "digest-source"
        source_tree.mkdir()
        (source_tree / "contract.txt").write_text(
            "managed source\n",
            encoding="utf-8",
        )

        expected_digest = subprocess.run(
            [str(DIGEST_PATH), str(source_tree)],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()

        python_cache = source_tree / "tooling/__pycache__"
        python_cache.mkdir(parents=True)
        (python_cache / "module.cpython-314.pyc").write_bytes(b"cache")
        pytest_cache = source_tree / ".pytest_cache"
        pytest_cache.mkdir()
        (pytest_cache / "state").write_text("cache\n", encoding="utf-8")
        (source_tree / ".DS_Store").write_bytes(b"metadata")

        actual_digest = subprocess.run(
            [str(DIGEST_PATH), str(source_tree)],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()

        self.assertEqual(actual_digest, expected_digest)

    def test_managed_workflow_uses_consumer_contract_validator(self) -> None:
        workflow = STANDARD_WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertTrue(CONTRACT_VALIDATOR_PATH.is_file())
        self.assertIn(
            ".bijux/shared/bijux-checks/scripts/validate-shared-contracts.sh",
            workflow,
        )
        consumer_contract, canonical_contract = workflow.split(
            "elif [[ -x "
            '"shared/bijux-checks/scripts/validate-shared-contracts.sh"',
            maxsplit=1,
        )
        self.assertNotIn("make contract-tests", consumer_contract)
        self.assertIn("make contract-tests", canonical_contract)

    def test_managed_workflow_checks_consumer_against_recorded_standard(
        self,
    ) -> None:
        workflow = STANDARD_WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn(
            'tr -d \'[:space:]\' < .github/standards/bijux-std.sha',
            workflow,
        )
        self.assertIn(
            '[[ ! "${consumer_ref}" =~ ^[0-9a-f]{40}$ ]]',
            workflow,
        )
        self.assertIn(
            'BIJUX_STD_REF="${consumer_ref}" make bijux-std-checks',
            workflow,
        )

    def test_rust_selection_includes_common_without_python_or_docs(self) -> None:
        result = self.resolve("--select", str(CONFIG_PATH), "rust")
        self.assertEqual(result.returncode, 0, result.stderr)
        directories = set(result.stdout.splitlines())

        self.assertEqual(
            directories,
            {
                "shared/bijux-makes",
                "shared/bijux-makes-rs",
                "shared/bijux-checks",
                "shared/bijux-gh",
            },
        )

    def test_docs_python_selection_combines_capabilities_once(self) -> None:
        result = self.resolve(
            "--select",
            str(CONFIG_PATH),
            "docs python common",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        directories = result.stdout.splitlines()

        self.assertIn("shared/bijux-docs", directories)
        self.assertIn("shared/bijux-makes-py", directories)
        self.assertNotIn("shared/bijux-makes-rs", directories)
        self.assertEqual(len(directories), len(set(directories)))

    def test_unknown_capability_fails_closed(self) -> None:
        result = self.resolve("--select", str(CONFIG_PATH), "unknown")

        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "unknown shared standards capability: unknown",
            result.stderr,
        )

    def test_updater_accepts_commit_sha_and_prunes_unselected_libraries(
        self,
    ) -> None:
        standard_source = TEST_ROOT / "standard-source"
        selected_directories = (
            "bijux-makes",
            "bijux-makes-rs",
            "bijux-checks",
            "bijux-gh",
        )
        unselected_directories = ("bijux-docs", "bijux-makes-py")
        for directory in (*selected_directories, *unselected_directories):
            target = standard_source / "shared" / directory
            target.mkdir(parents=True)
            (target / "marker.txt").write_text(
                f"{directory}\n",
                encoding="utf-8",
            )
        subprocess.run(["git", "init", "-q"], cwd=standard_source, check=True)
        subprocess.run(
            ["git", "config", "user.email", "bijux@example.invalid"],
            cwd=standard_source,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Bijux Tests"],
            cwd=standard_source,
            check=True,
        )
        subprocess.run(["git", "add", "shared"], cwd=standard_source, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "test: define shared source"],
            cwd=standard_source,
            check=True,
        )
        source_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=standard_source,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()

        consumer = TEST_ROOT / "consumer"
        managed_root = consumer / ".bijux/shared"
        managed_root.mkdir(parents=True)
        (managed_root / "shared-dir-sha256.txt").write_text(
            "",
            encoding="utf-8",
        )
        stale_docs = managed_root / "bijux-docs"
        stale_docs.mkdir()
        (stale_docs / "stale.txt").write_text("stale\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=consumer, check=True)

        result = subprocess.run(
            [str(UPDATER_PATH)],
            cwd=consumer,
            check=False,
            text=True,
            capture_output=True,
            env={
                **os.environ,
                "BIJUX_STD_CAPABILITIES": "rust",
                "BIJUX_STD_CONFIG": str(CONFIG_PATH),
                "BIJUX_STD_GIT_URL": str(standard_source),
                "BIJUX_STD_REF": source_sha,
                "BIJUX_STD_SELF_REPO_MODE": "off",
                "TMPDIR": str(consumer / "artifacts/process"),
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        for directory in selected_directories:
            self.assertTrue(
                (managed_root / directory / "marker.txt").is_file(),
                directory,
            )
        for directory in unselected_directories:
            self.assertFalse((managed_root / directory).exists(), directory)

        manifest_lines = (
            managed_root / "shared-dir-sha256.txt"
        ).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(manifest_lines), len(selected_directories))
        self.assertTrue(
            all(not line.startswith("e3b0c44298fc") for line in manifest_lines)
        )


if __name__ == "__main__":
    unittest.main()
