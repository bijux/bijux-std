from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = ROOT / "shared/bijux-docs/tooling/diagrams"
DEPS = Path(os.environ.get("BIJUX_DIAGRAM_DEPENDENCIES", ROOT / "artifacts/website-security/dependencies/build"))


class DiagramDependencyTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "artifacts/website-security/dependencies/tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.scratch.cleanup)
        self.base = Path(self.scratch.name)
        self.deps = self.base / "dependencies"
        self.deps.mkdir()
        for name in ("package.json", "package-lock.json"):
            shutil.copy(DOMAIN / name, self.deps / name)

    def build(self, output=None):
        return subprocess.run(["node", str(DOMAIN / "build.mjs"), "--dependencies", str(self.deps),
                               "--output-dir", str(output or self.base / "output")], cwd=ROOT, text=True, capture_output=True)

    def test_changed_install_manifest_rejected_before_bundle_execution(self):
        path = self.deps / "package.json"
        config = json.loads(path.read_text())
        config["dependencies"]["dompurify"] = "3.4.12"
        path.write_text(json.dumps(config))
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Installed manifest differs", result.stderr)

    def test_changed_install_lock_rejected_before_bundle_execution(self):
        path = self.deps / "package-lock.json"
        lock = json.loads(path.read_text())
        lock["packages"]["node_modules/dompurify"]["resolved"] = "https://foreign.invalid/sanitizer.tgz"
        path.write_text(json.dumps(lock))
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Installed lock differs", result.stderr)

    def test_installed_unpatched_dependency_version_rejected(self):
        manifest = json.loads((DOMAIN / "package.json").read_text())
        for name, version in (manifest["dependencies"] | manifest["devDependencies"]).items():
            path = self.deps / "node_modules" / name
            path.mkdir(parents=True)
            (path / "package.json").write_text(json.dumps({"name": name, "version": "3.4.12" if name == "dompurify" else version}))
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Installed dompurify version differs", result.stderr)

    def test_output_outside_artifacts_rejected(self):
        result = self.build(ROOT / "shared/bijux-docs/tooling/diagrams/generated")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Generated outputs must be under", result.stderr)
        self.assertFalse((DOMAIN / "generated").exists())

    def test_install_outside_artifacts_rejected_before_npm(self):
        result = subprocess.run(["node", str(DOMAIN / "install.mjs"), "--artifact-root", str(DOMAIN / "generated")],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Dependency install must remain under", result.stderr)
        self.assertFalse((DOMAIN / "generated").exists())

    def test_install_manifest_symlink_rejected_before_npm(self):
        artifact = self.base / "install"
        (artifact / "build").mkdir(parents=True)
        destination = artifact / "build/package.json"
        original = self.base / "preserved-manifest.json"
        original.write_text("preserve user data")
        destination.symlink_to(original)
        result = subprocess.run(["node", str(DOMAIN / "install.mjs"), "--artifact-root", str(artifact)],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Dependency manifest destination is not an unlinked regular file", result.stderr)
        self.assertEqual(original.read_text(), "preserve user data")

    def test_build_output_symlink_cannot_overwrite_existing_data(self):
        self.assertTrue((DEPS / "node_modules/esbuild/package.json").exists(),
                        "Prepare required runtime: make -f shared/bijux-docs/tooling/diagrams/Makefile diagrams-install")
        output = self.base / "linked-output"
        output.mkdir()
        original = self.base / "preserved-output.js"
        original.write_text("preserve user data")
        (output / "mermaid-11.17.2.min.js").symlink_to(original)
        result = subprocess.run(["node", str(DOMAIN / "build.mjs"), "--dependencies", str(DEPS),
                                 "--output-dir", str(output)], cwd=ROOT, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Generated output destination must be an unlinked regular file", result.stderr)
        self.assertEqual(original.read_text(), "preserve user data")

    def test_governed_provenance_binds_builder_lock_and_legal_text(self):
        data = json.loads((DOMAIN / "provenance.json").read_text())
        self.assertEqual(data["inputs"]["lock_sha256"], hashlib.sha256((DOMAIN / "package-lock.json").read_bytes()).hexdigest())
        self.assertEqual(data["inputs"]["builder_sha256"], hashlib.sha256((DOMAIN / "build.mjs").read_bytes()).hexdigest())
        self.assertEqual(data["license_sha256"], hashlib.sha256((DOMAIN / "THIRD-PARTY-LICENSES.txt").read_bytes()).hexdigest())
        graph = {p["name"]: p["version"] for p in data["bundled_packages"]}
        self.assertEqual(graph["dompurify"], "3.4.16")
        self.assertEqual(graph["mermaid"], "11.17.2")
        self.assertEqual(graph["katex"], "0.18.2")
        self.assertTrue(data["bundled_inputs"])

    def test_repeated_real_build_produces_identical_artifact_and_provenance(self):
        if not (DEPS / "node_modules/esbuild/package.json").exists():
            self.fail("Pinned diagram runtime missing. Prepare it with: make -f shared/bijux-docs/tooling/diagrams/Makefile diagrams-install; for a read-only qualified runtime set BIJUX_DIAGRAM_DEPENDENCIES to its build directory.")
        outputs = []
        for name in ("first", "repeat"):
            output = self.base / name
            result = subprocess.run(["node", str(DOMAIN / "build.mjs"), "--dependencies", str(DEPS),
                                     "--output-dir", str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(output)
        for file in outputs[0].iterdir():
            self.assertEqual(file.read_bytes(), (outputs[1] / file.name).read_bytes(), file.name)
        self.assertEqual(json.loads((outputs[0] / "provenance.json").read_text()), json.loads((DOMAIN / "provenance.json").read_text()))


if __name__ == "__main__":
    unittest.main()
