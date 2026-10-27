from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bijux_release_source_renderer", ROOT / ".github/scripts/render_repo_configs.py")
RENDERER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RENDERER)
WORKFLOW = RENDERER.WORKFLOW_EXECUTION.parse_workflow(
    (ROOT / "shared/bijux-gh/workflows/release-artifacts.yml").read_bytes(), "release artifacts"
)


class ReleaseSourceAdmissionContractTests(unittest.TestCase):
    def test_source_admission_precedes_installation_build_and_artifact_upload(self):
        steps = WORKFLOW["jobs"]["build"]["steps"]
        names = [step.get("name") for step in steps]
        source = names.index("Verify release source and repository admission")
        self.assertLess(names.index("Setup Python"), source)
        for name in ("Install package toolchain", "Build release artifacts", "Stage publish artifacts", "Upload publish artifacts"):
            self.assertLess(source, names.index(name))
        self.assertIn("Verify release revision and repository artifact policy", names)
        self.assertEqual(WORKFLOW["permissions"], {"contents": "read", "actions": "read"})
        self.assertEqual(steps[source]["env"]["GITHUB_TOKEN"], "${{ github.token }}")
        self.assertNotIn("continue-on-error", steps[source])

    def test_source_hook_native_refusal_and_revision_failures_stop_build_admission(self):
        step = next(step for step in WORKFLOW["jobs"]["build"]["steps"]
                    if step.get("name") == "Verify release source and repository admission")
        scenarios = [("admitted", 0, "v0.2.0", "a" * 40, 0, True),
                     ("source-refusal", 37, "v0.2.0", "a" * 40, 37, True),
                     ("wrong-tag", 0, "v0.2.0", "b" * 40, 1, False),
                     ("empty-tag", 0, "", "a" * 40, 1, False)]
        for name, status, tag, tag_sha, expected, called in scenarios:
            with self.subTest(scenario=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / ".github").mkdir()
                (root / "bin").mkdir()
                marker = root / "source-consumed"
                (root / ".github/release.env").write_text(
                    "BIJUX_RELEASE_SOURCE_VERIFICATION_COMMAND='touch source-consumed; exit " + str(status) + "'\n"
                )
                git = root / "bin/git"
                git.write_text("#!/bin/sh\nif [ \"$3\" = HEAD ]; then printf '%s\\n' \"$GITHUB_SHA\"; else printf '%s\\n' \"$TAG_SHA\"; fi\n")
                git.chmod(0o755)
                result = subprocess.run(["bash", "-c", step["run"]], cwd=root,
                                        env={**os.environ, "PATH": str(root / "bin") + os.pathsep + os.environ["PATH"],
                                             "RELEASE_TAG": tag, "GITHUB_SHA": "a" * 40, "TAG_SHA": tag_sha},
                                        capture_output=True, timeout=10)
                self.assertEqual(result.returncode, expected)
                self.assertEqual(marker.exists(), called)

    def test_pollenomics_source_command_requires_current_lra_receipt_only_for_engine(self):
        manifest = json.loads((ROOT / ".github/standards/repo-config.manifest.json").read_text())
        repository = RENDERER.find_repo_config(manifest, "bijux-pollenomics")
        command = next(entry["value"] for entry in repository["release_env"]
                       if entry["key"] == "BIJUX_RELEASE_SOURCE_VERIFICATION_COMMAND")
        for package, status, expected, called in [("bijux-pollenomics-lra", 0, 0, True),
                                                  ("bijux-pollenomics-lra", 29, 29, True),
                                                  ("bijux-pollenomics", 29, 0, False),
                                                  ("pollenomics", 29, 0, False)]:
            with self.subTest(package=package, gate_status=status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "bin").mkdir()
                marker = root / "arguments"
                python = root / "bin/python3"
                python.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$ARGUMENTS\"\nexit \"$GATE_STATUS\"\n")
                python.chmod(0o755)
                env = {**os.environ, "PATH": str(root / "bin") + os.pathsep + os.environ["PATH"],
                       "PACKAGE_SLUG": package, "GITHUB_WORKSPACE": str(root), "GITHUB_SHA": "a" * 40,
                       "RELEASE_TAG": "v0.2.0", "GITHUB_REPOSITORY": "bijux/bijux-pollenomics",
                       "ARTIFACTS_DIR": "artifacts/engine", "ARGUMENTS": str(marker), "GATE_STATUS": str(status)}
                result = subprocess.run(["bash", "-c", command], env=env, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, expected)
                self.assertEqual(marker.exists(), called)
                if called:
                    arguments = marker.read_text().splitlines()
                    self.assertEqual(arguments[:3], ["-B", "-m", "bijux_pollenomics_dev.ci.lra_reference.release_gate"])
                    for flag, value in {"--target-sha": "a" * 40, "--release-tag": "v0.2.0",
                                        "--repository": "bijux/bijux-pollenomics", "--repository-root": str(root),
                                        "--output": str(root / "artifacts/engine/lra-source-evidence")}.items():
                        self.assertEqual(arguments[arguments.index(flag) + 1], value)
                    self.assertNotIn("--allow-prerelease", arguments)


if __name__ == "__main__":
    unittest.main()
