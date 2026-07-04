from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "scripts"
    / "build_repo_manifest.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bijux_std_build_repo_manifest",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildRepoManifestTests(unittest.TestCase):
    def test_normalize_release_env_json_entry_drops_legacy_token_publish_auth(self) -> None:
        normalized = MODULE.normalize_release_env_json_entry(
            "BIJUX_PYPI_PACKAGE_MATRIX_JSON",
            [
                {"package_slug": "bijux-phylogenetics"},
                {"package_slug": "phylogenetic", "publish_auth": "token"},
                {"package_slug": "bijux-example", "publish_auth": "trusted"},
            ],
        )

        self.assertEqual(
            normalized,
            [
                {"package_slug": "bijux-phylogenetics"},
                {"package_slug": "phylogenetic"},
                {"package_slug": "bijux-example", "publish_auth": "trusted"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
