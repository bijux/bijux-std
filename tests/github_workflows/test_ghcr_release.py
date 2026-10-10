from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from .policy_fixtures import MODULE, RENDERER, ROOT


class GhcrBuildFamilyTests(unittest.TestCase):
    def resolve(self, *, allowed: str | None = None, build_matrix: str = "") -> dict[str, str]:
        manifest = json.loads((ROOT / ".github/standards/repo-config.manifest.json").read_text())
        files = RENDERER.prepare_repo_files("bijux-core", manifest)
        workflow = MODULE.parse_workflow((ROOT / "shared/bijux-gh/workflows/release-ghcr.yml").read_bytes(), "release-ghcr")
        step = next(step for step in workflow["jobs"]["resolve"]["steps"] if "filter_matrix()" in step.get("run", ""))
        command = re.sub(r"\$\{\{.*?\}\}", "", step["run"])
        root = ROOT / "artifacts" / "ghcr-controls"
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            target = Path(directory)
            (target / ".github").mkdir()
            release_env = files[".github/release.env"].decode()
            if allowed is not None:
                release_env += f"\nBIJUX_GHCR_RELEASE_ALLOWED_PACKAGES='{allowed}'\n"
            (target / ".github/release.env").write_text(release_env)
            output = target / "output"
            env = {**os.environ, **{key: "" for key in step["env"]},
                   "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": "bijux/bijux-core",
                   "GITHUB_OUTPUT": str(output), "INPUT_RELEASE_TAG": "v1.0.0",
                   "INPUT_BUILD_MATRIX_JSON": build_matrix, "DISPATCH_ENABLED_RAW": "", "DISPATCH_PUSH_LATEST_RAW": ""}
            result = subprocess.run(["bash", "-c", command], cwd=target, env=env, capture_output=True, text=True)
            if result.returncode:
                raise subprocess.CalledProcessError(result.returncode, "GHCR configuration", result.stdout, result.stderr)
            values = {}
            lines = iter(output.read_text().splitlines())
            for line in lines:
                if line.endswith("<<EOF"):
                    values[line.removesuffix("<<EOF")] = next(lines)
                    self.assertEqual(next(lines), "EOF")
                else:
                    key, value = line.split("=", 1)
                    values[key] = value
            return values

    def test_public_crates_share_their_family_bundle_without_losing_the_build(self):
        result = self.resolve()
        self.assertEqual(result["enabled"], "true")
        builds = json.loads(result["build_matrix_json"])
        self.assertEqual([row["package_slug"] for row in builds], ["bijux-cli", "bijux-dag"])
        packages = json.loads(result["package_matrix_json"])
        self.assertEqual([row["package_slug"] for row in packages], result["allowed_packages"].split())
        self.assertEqual(len(packages), 6)
        self.assertTrue(all(row["artifact_name"] == "bijux-dag-release" for row in packages if row["package_slug"].startswith("bijux-dag-")))

    def test_selecting_one_package_preserves_shared_build_families(self):
        result = self.resolve(allowed="bijux-dag-core")
        self.assertEqual(len(json.loads(result["build_matrix_json"])), 2)
        self.assertEqual(json.loads(result["package_matrix_json"]), [{"package_slug": "bijux-dag-core", "artifact_name": "bijux-dag-release"}])

    def test_malformed_build_matrix_is_still_rejected(self):
        for matrix in ["{}", '[{"missing":"package_slug"}]', "broken"]:
            with self.subTest(matrix=matrix), self.assertRaises(subprocess.CalledProcessError):
                self.resolve(build_matrix=matrix)
