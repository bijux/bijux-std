"""Qualify installed renderer receipts inside the admitted fixture environment."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
SECURITY = ROOT / "shared/bijux-docs/security"
spec = importlib.util.spec_from_file_location("bijux_publication_receipt_fixture", ROOT / "tests/test_docs_publication_security.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class PublicationRendererReceiptTests(unittest.TestCase):
    setUp = fixture.QualifiedPublicationTests.setUp
    git = staticmethod(fixture.QualifiedPublicationTests.git)
    write_records = fixture.QualifiedPublicationTests.write_records

    def test_actual_renderer_config_environment_is_bound_and_candidate_is_explicit(self):
        runtime = Path(sys.executable)
        self.assertTrue(runtime.exists(), "Prepare the actual docs toolchain: make ui-test-install-docs")
        report = "artifacts/website-security/local-build.json"
        command = [str(runtime), str(SECURITY / "build_identity.py")]
        env = dict(os.environ, SITE_URL=self.url)
        env.pop("DOCS_SOURCE_IDENTITY", None)
        started = subprocess.run(command + ["begin", "--config", "mkdocs.yml", "--site-dir", "artifacts/docs/site",
                                            "--site-url", "", "--output", report], cwd=self.root, env=env, text=True, capture_output=True)
        self.assertEqual(started.returncode, 0, started.stderr)
        data = json.loads((self.root / report).read_text())
        self.assertTrue(data["verification_only"])
        self.assertEqual(data["site_url"], self.url)
        self.assertEqual(data["renderer"]["packages"]["mkdocs-material"], "9.7.7")
        changed = subprocess.run(command + ["finish", "--receipt", report], cwd=self.root,
                                 env=env | {"SITE_URL": "https://bijux.io/changed/"}, text=True, capture_output=True)
        self.assertNotEqual(changed.returncode, 0)
        self.assertIn("resolved renderer configuration/environment changed", changed.stderr)
        finished = subprocess.run(command + ["finish", "--receipt", report], cwd=self.root, env=env, text=True, capture_output=True)
        self.assertEqual(finished.returncode, 0, finished.stderr)

    def test_ignored_renderer_source_rejected_by_actual_builder(self):
        runtime = Path(sys.executable)
        self.assertTrue(runtime.exists(), "Prepare the actual docs toolchain: make ui-test-install-docs")
        (self.root / ".git/info/exclude").write_text("ignored.md\n")
        (self.root / "docs/ignored.md").write_text("unreviewed renderer input")
        command = [str(runtime), str(SECURITY / "build_identity.py"), "begin", "--config", "mkdocs.yml",
                   "--site-dir", "artifacts/docs/site", "--site-url", self.url,
                   "--source-checkpoint", self.paths["source"], "--output", "artifacts/website-security/build.json"]
        result = subprocess.run(command, cwd=self.root, env=dict(os.environ, SITE_URL=self.url),
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ignored renderer source cannot be attributed", result.stderr)
