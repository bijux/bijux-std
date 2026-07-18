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


class GnssRepositoryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.repositories = {
            repository["name"]: repository
            for repository in cls.manifest["repositories"]
        }

    def test_gnss_is_the_only_managed_repository_with_gnss_packages(self) -> None:
        self.assertIn("bijux-gnss", self.repositories)

        repositories_with_gnss_packages = {
            name
            for name, repository in self.repositories.items()
            if "bijux-gnss-" in json.dumps(repository.get("release_env", []))
        }
        self.assertEqual(repositories_with_gnss_packages, {"bijux-gnss"})

    def test_gnss_release_channels_match_package_contract(self) -> None:
        repository = self.repositories["bijux-gnss"]
        release_env = {
            entry["key"]: entry["value"]
            for entry in repository["release_env"]
        }

        self.assertTrue(release_env["BIJUX_RELEASE_ENABLED"])
        self.assertTrue(release_env["BIJUX_CRATES_RELEASE_ENABLED"])
        self.assertTrue(release_env["BIJUX_GHCR_RELEASE_ENABLED"])
        self.assertFalse(release_env["BIJUX_PYPI_ENABLED"])
        self.assertEqual(
            {
                package["package_slug"]
                for package in release_env["BIJUX_RELEASE_BUILD_MATRIX_JSON"]
            },
            {
                "bijux-gnss",
                "bijux-gnss-core",
                "bijux-gnss-infra",
                "bijux-gnss-nav",
                "bijux-gnss-receiver",
                "bijux-gnss-signal",
            },
        )
        self.assertTrue(
            {
                "release-artifacts",
                "release-crates",
                "release-ghcr",
                "release-github",
            }.issubset(repository["workflow_allowlist"])
        )


if __name__ == "__main__":
    unittest.main()
