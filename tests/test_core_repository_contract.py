from __future__ import annotations

import json
import unittest
from pathlib import Path


MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "standards"
    / "repo-config.manifest.json"
)

RUST_TOOLCHAIN = "1.86.0"
CRATES_IO_PACKAGES = (
    "bijux-dag-core",
    "bijux-dag-artifacts",
    "bijux-dag-runtime",
    "bijux-dag-app",
    "bijux-dag-cli",
    "bijux-cli",
)


class CoreRepositoryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.repository = next(
            repository
            for repository in manifest["repositories"]
            if repository["name"] == "bijux-core"
        )
        cls.release_env = {
            entry["key"]: entry["value"]
            for entry in cls.repository["release_env"]
        }

    def test_release_toolchains_match_core_workspace(self) -> None:
        for key in (
            "BIJUX_RELEASE_RUST_TOOLCHAIN",
            "BIJUX_CRATES_RELEASE_RUST_TOOLCHAIN",
            "BIJUX_PYPI_RUST_TOOLCHAIN",
        ):
            self.assertEqual(self.release_env[key], RUST_TOOLCHAIN)

        self.assertEqual(
            self.repository["workflow_wrappers"]["ci"]["env"][
                "RUST_TOOLCHAIN_VERSION"
            ],
            RUST_TOOLCHAIN,
        )

    def test_binary_release_families_cover_cli_and_dag(self) -> None:
        build_matrix = self.release_env["BIJUX_RELEASE_BUILD_MATRIX_JSON"]
        self.assertEqual(
            [entry["package_slug"] for entry in build_matrix],
            ["bijux-cli", "bijux-dag"],
        )
        dag_entry = next(
            entry
            for entry in build_matrix
            if entry["package_slug"] == "bijux-dag"
        )
        self.assertEqual(dag_entry["artifacts_dir"], "artifacts/rust")
        self.assertEqual(
            dag_entry["build_targets"],
            "build-dag-release-bundle",
        )

        self.assertEqual(
            [
                entry["package_slug"]
                for entry in self.release_env[
                    "BIJUX_GHCR_RELEASE_PACKAGE_MATRIX_JSON"
                ]
            ],
            ["bijux-cli", "bijux-dag"],
        )
        self.assertEqual(
            self.release_env["BIJUX_GHCR_RELEASE_ALLOWED_PACKAGES"],
            "bijux-cli bijux-dag",
        )

    def test_crates_release_order_and_allowlist_match_public_packages(self) -> None:
        expected = " ".join(CRATES_IO_PACKAGES)
        self.assertEqual(
            self.release_env["BIJUX_CRATES_RELEASE_PACKAGES"],
            expected,
        )
        self.assertEqual(
            self.release_env["BIJUX_CRATES_RELEASE_ALLOWED_PACKAGES"],
            expected,
        )


if __name__ == "__main__":
    unittest.main()
