"""Prove external-link producer ownership without mutating a Git repository."""
import hashlib
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared/bijux-docs/tooling/scripts/project_bijux_docs.py"
spec = importlib.util.spec_from_file_location("link_projection", SCRIPT)
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)

class ExternalLinkProjectionTests(unittest.TestCase):
    def setUp(self):
        output = ROOT / "artifacts/bijux-docs/link-projection"
        output.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=output)
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        self.shared = self.repo / ".bijux/shared/bijux-docs"
        shutil.copytree(ROOT / "shared/bijux-docs", self.shared)

    def test_required_external_asset_has_exactly_one_canonical_producer(self):
        pairs = projection.projection(self.repo, self.shared)
        external = [(source, target) for source, target in pairs if target.name == "external-links.js"]
        self.assertEqual(external, [(self.shared / "scripts/external-links.js", self.repo / "docs/assets/javascripts/external-links.js")])
        self.assertEqual(projection.source_destination("bijux-docs/scripts/external-links.js"), "docs/assets/javascripts/external-links.js")
        self.assertNotIn("docs/assets/javascripts/external-links.js", projection.LEGACY)

    def test_missing_producer_is_rejected_before_any_projection_write(self):
        (self.shared / "scripts/external-links.js").unlink()
        with self.assertRaisesRegex(RuntimeError, "Missing canonical projection inputs.*external-links"):
            projection.projection(self.repo, self.shared)
        self.assertFalse((self.repo / "docs").exists())

    def test_authored_consumer_file_cannot_be_claimed_as_legacy_generated(self):
        destination = self.repo / "docs/assets/javascripts/external-links.js"
        destination.parent.mkdir(parents=True)
        destination.write_text("authored policy with product intent")
        before = destination.read_bytes()
        with mock.patch.object(projection, "tracked", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "explicit authored extension migration required.*external-links"):
                projection.ownership_plan(self.repo, self.shared, projection.projection(self.repo, self.shared), {"mode":"local-verification", "sha":None, "origin":None})
        self.assertEqual(destination.read_bytes(), before)
        self.assertFalse((self.repo / ".bijux/docs-projection.json").exists())

    def test_generated_fixture_has_no_authored_producer_substitute(self):
        source = (ROOT / "tests/bijux-docs/generated/build.py").read_text()
        self.assertIn('shared / "scripts/external-links.js"', source)
        self.assertNotIn('Path(__file__).parent / "external-links.js"', source)
        self.assertFalse((ROOT / "tests/bijux-docs/generated/external-links.js").exists())

    def test_historical_counterfactual_is_the_exact_reviewed_consumer_source(self):
        source = (ROOT / "tests/bijux-docs/ui/generated-specs/external-link-policy/historical-consumer.js").read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), "b6de6ee9cff0ce2221fef7f3c6c91749ee14813eda1069c281fa16005b706cb1")
