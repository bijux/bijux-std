"""Publication documentation authority stays independent of application standards."""
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bijux_publication_pin_fixture", ROOT / "tests/test_docs_publication_security.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
identity = fixture.identity


class PublicationPin(unittest.TestCase):
    setUp = fixture.QualifiedPublicationTests.setUp
    git = staticmethod(fixture.QualifiedPublicationTests.git)
    write_records = fixture.QualifiedPublicationTests.write_records

    def publication_source(self):
        pin = self.root / ".github/standards/bijux-docs.sha"
        pin.write_text(self.standard_sha + "\n")
        (self.root / ".github/standards/bijux-std.sha").write_text("a" * 40 + "\n")
        self.git(self.root, "add", ".github/standards/bijux-docs.sha", ".github/standards/bijux-std.sha")
        self.git(self.root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "independent publication source")
        self.source_sha = self.git(self.root, "rev-parse", "HEAD").strip()
        actual_git = identity.git

        def fetched(root, *args):
            if args and args[0] == "fetch":
                self.assertEqual(args, ("fetch", "--quiet", "--depth", "1", "origin", self.standard_sha))
                return ""
            return actual_git(root, *args)

        with patch.object(identity, "git", side_effect=fetched):
            return identity.source_checkpoint(self.root, self.source_sha, "artifacts/accepted-standard", self.url,
                                              "artifacts/docs/site", "make gh-docs-build", "make gh-docs-verify",
                                              standard_pin="publication")

    def test_publication_selects_its_tracked_exact_pointer_independently(self):
        checkpoint = self.publication_source()
        self.assertEqual(checkpoint["standard"]["sha"], self.standard_sha)
        self.assertEqual(checkpoint["standard_pin"], {"selector": "publication", "path": ".github/standards/bijux-docs.sha"})
        identity.verify_source(self.root, checkpoint)

    def test_pin_path_cannot_be_rewritten_to_arbitrary_tracked_file(self):
        checkpoint = self.publication_source()
        checkpoint["standard_pin"]["path"] = "docs/index.md"
        with self.assertRaisesRegex(ValueError, "finite source-owned selector"):
            identity.verify_source(self.root, checkpoint)

    def test_missing_publication_pointer_cannot_fall_back_to_runtime(self):
        with self.assertRaises(ValueError):
            identity.source_checkpoint(self.root, self.source_sha, "artifacts/accepted-standard", self.url,
                                       "artifacts/docs/site", "make docs", "make gh-docs-verify", standard_pin="publication")

    def test_unknown_pointer_selector_cannot_supply_a_path_or_commit(self):
        for selector in (".github/standards/bijux-std.sha", "a" * 40, "preview", None, []):
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                identity.standard_pin_path(selector)

    def test_legacy_runtime_checkpoint_retains_exact_authority(self):
        self.assertEqual(identity.checkpoint_pin(self.source), ".github/standards/bijux-std.sha")
        legacy = dict(self.source)
        legacy.pop("standard_pin")
        identity.verify_source(self.root, legacy)


if __name__ == "__main__":
    unittest.main()
