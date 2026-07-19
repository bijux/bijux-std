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
