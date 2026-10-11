"""Whole-tree source custody binds links without promoting them to renderer inputs."""
from pathlib import Path
import importlib.util
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / "shared/bijux-docs/security"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SECURITY / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


producer = load("bijux_link_producer_test", "producer_authority.py")
identity = load("bijux_link_identity_test", "build_identity.py")


class CommittedLinks(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "artifacts/committed-link-tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.git("init", "-q")
        self.git("config", "user.email", "source@example.org")
        self.git("config", "user.name", "Source")
        (self.root / "docs").mkdir()
        (self.root / "docs/index.md").write_text("# Reader\n")
        (self.root / "LICENSE").write_text("authored license")
        (self.root / "SDK").mkdir()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def commit(self, *paths):
        self.git("add", *paths)
        self.git("commit", "-qm", "test source")

    def test_file_alias_is_link_blob_metadata_without_target_bytes(self):
        (self.root / "SDK/LICENSE").symlink_to("../LICENSE")
        self.commit("docs/index.md", "LICENSE", "SDK/LICENSE")
        actual = producer.repository_files(self.root)
        self.assertEqual(actual["SDK/LICENSE"], b"../LICENSE")
        self.assertEqual(actual["LICENSE"], b"authored license")
        with self.assertRaisesRegex(ValueError, "symlink"):
            identity.regular(self.root, "SDK/LICENSE")

    def test_directory_alias_binds_committed_tree_and_still_is_not_renderer_source(self):
        (self.root / "SDK/evidence").symlink_to("../docs", target_is_directory=True)
        self.commit("docs/index.md", "LICENSE", "SDK/evidence")
        self.assertEqual(producer.repository_files(self.root)["SDK/evidence"], b"../docs")
        with self.assertRaisesRegex(ValueError, "symlink"):
            identity.regular(self.root, "SDK/evidence/index.md")

    def test_external_and_uncommitted_targets_are_rejected(self):
        for target in ("/etc/passwd", "../missing", "../../outside"):
            with self.subTest(target=target):
                link = self.root / "SDK/link"
                if link.is_symlink():
                    link.unlink()
                link.symlink_to(target)
                self.commit("docs/index.md", "LICENSE", "SDK/link")
                with self.assertRaises(ValueError):
                    producer.repository_files(self.root)

    def test_hidden_link_blob_mutation_is_rejected(self):
        link = self.root / "SDK/LICENSE"
        link.symlink_to("../LICENSE")
        self.commit("docs/index.md", "LICENSE", "SDK/LICENSE")
        self.git("update-index", "--assume-unchanged", "SDK/LICENSE")
        link.unlink()
        link.symlink_to("../docs/index.md")
        with self.assertRaisesRegex(ValueError, "blob or mode"):
            producer.repository_files(self.root)

    def test_regular_file_cannot_impersonate_committed_link_mode(self):
        link = self.root / "SDK/LICENSE"
        link.symlink_to("../LICENSE")
        self.commit("docs/index.md", "LICENSE", "SDK/LICENSE")
        self.git("update-index", "--assume-unchanged", "SDK/LICENSE")
        link.unlink()
        link.write_text("../LICENSE")
        with self.assertRaises(ValueError):
            producer.repository_files(self.root)

    def test_link_chains_cannot_borrow_regular_target_ownership(self):
        (self.root / "SDK/LICENSE").symlink_to("../LICENSE")
        (self.root / "SDK/link").symlink_to("LICENSE")
        self.commit("docs/index.md", "LICENSE", "SDK/LICENSE", "SDK/link")
        with self.assertRaises(ValueError):
            producer.repository_files(self.root)


if __name__ == "__main__":
    unittest.main()
