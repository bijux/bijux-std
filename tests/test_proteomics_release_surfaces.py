from __future__ import annotations

import json
from pathlib import Path
import unittest


MANIFEST = Path(__file__).resolve().parents[1] / ".github/standards/repo-config.manifest.json"
PUBLIC_SURFACES = {
    "agentic-proteins", "bijux-proteomics", "bijux-proteomics-core",
    "bijux-proteomics-foundation", "bijux-proteomics-intelligence",
    "bijux-proteomics-knowledge", "bijux-proteomics-lab", "bijux-proteomics-runtime",
    "proteomics", "proteomics-core", "proteomics-foundation", "proteomics-intelligence",
    "proteomics-knowledge", "proteomics-lab", "proteomics-runtime",
}
DOMAIN_LIBRARIES = {
    "bijux-proteomics-core", "bijux-proteomics-foundation", "bijux-proteomics-intelligence",
    "bijux-proteomics-knowledge", "bijux-proteomics-lab",
}


class ProteomicsReleaseSurfacesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text())
        self.repository = next(r for r in self.manifest["repositories"] if r["name"] == "bijux-proteomics")
        self.variables = {entry["key"]: entry["value"] for entry in self.repository["release_env"]}

    def test_all_publication_matrices_admit_exact_public_roster_and_roles(self) -> None:
        for name in ("BIJUX_RELEASE_BUILD_MATRIX_JSON", "BIJUX_PYPI_PACKAGE_MATRIX_JSON", "BIJUX_GHCR_RELEASE_PACKAGE_MATRIX_JSON"):
            rows = self.variables[name]
            self.assertEqual(len(rows), len(PUBLIC_SURFACES))
            self.assertEqual({row["package_slug"] for row in rows}, PUBLIC_SURFACES)
            for row in rows:
                slug = row["package_slug"]
                expected = "runtime" if slug == "bijux-proteomics-runtime" else "library" if slug in DOMAIN_LIBRARIES else "compat"
                self.assertEqual(row["release_role"], expected)

    def test_each_public_surface_has_owned_build_and_sbom_paths(self) -> None:
        for row in self.variables["BIJUX_RELEASE_BUILD_MATRIX_JSON"]:
            slug = row["package_slug"]
            self.assertEqual(row["package_dir"], f"packages/{slug}")
            self.assertEqual(row["artifacts_dir"], f"artifacts/{slug}")
            self.assertEqual(row["build_targets"], "build sbom")

    def test_verification_covers_public_surfaces_and_development_governance(self) -> None:
        rows = self.repository["workflow_wrappers"]["verify"]["jobs"]["package"]["strategy"]["matrix"]["include"]
        expected = PUBLIC_SURFACES | {"bijux-proteomics-dev"}
        self.assertEqual(len(rows), len(expected))
        self.assertEqual({row["package_slug"] for row in rows}, expected)
        for row in rows:
            self.assertEqual(row["package_dir"], f"packages/{row['package_slug']}")
            self.assertEqual(row["artifacts_dir"], f"artifacts/{row['package_slug']}")
            if row["package_slug"].startswith("proteomics") or row["package_slug"] in {"bijux-proteomics", "bijux-proteomics-dev"}:
                self.assertEqual(json.loads(row["check_targets"]), ["quality", "security", "build", "sbom"])
                self.assertEqual(json.loads(row["api_toolchain_targets"]), [])

    def test_shared_python_package_defaults_require_owned_product_targets(self) -> None:
        admitted = set()
        for repository in self.manifest["repositories"]:
            wrappers = repository.get("workflow_wrappers", {})
            inputs = wrappers.get("ci", {}).get("on", {}).get("workflow_call", {}).get("inputs", {})
            if "check_targets" not in inputs:
                continue
            defaults = json.loads(inputs["check_targets"]["default"])
            expected = (["lint", "security"] if repository["name"] == "bijux-pollenomics"
                        else ["quality", "security", "api", "build", "sbom"])
            self.assertEqual(defaults, expected)
            for job in wrappers.get("verify", {}).get("jobs", {}).values():
                fallback = job.get("with", {}).get("check_targets", "")
                if fallback:
                    self.assertNotIn('"docs"', fallback)
            admitted.add(repository["name"])
        self.assertEqual(admitted, {"bijux-canon", "bijux-proteomics", "bijux-phylogenetics", "bijux-pollenomics"})


if __name__ == "__main__":
    unittest.main()
