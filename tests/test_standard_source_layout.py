"""Classify authored standards checkouts independently of local directory names."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "shared/bijux-checks/scripts/standard-source-layout.sh"


class StandardSourceLayoutTests(unittest.TestCase):
    def classify(self, remote: str, *, layout: str = "source") -> int:
        owner = ROOT / "artifacts/tests/source-layout"
        owner.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=owner) as directory:
            root = Path(directory) / "owned-checkout"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(
                ["git", "-C", str(root), "remote", "add", "origin", remote],
                check=True,
            )
            if layout != "consumer":
                (root / "shared").mkdir()
                if layout != "missing-checks":
                    (root / "shared/bijux-checks").mkdir()
                if layout != "missing-manifest":
                    (root / "shared/shared-dir-sha256.txt").write_text(
                        "source-owned manifest\n", encoding="utf-8"
                    )
            result = subprocess.run(
                [
                    "bash", "-c",
                    'source "$1"; is_standard_source_checkout "$2"',
                    "fixture", str(HELPER), str(root),
                ],
                text=True,
                capture_output=True,
            )
            return result.returncode

    def test_canonical_gitlab_transports_admit_authored_source(self):
        for remote in (
            "https://gitlab.com/bijux-oss/bijux-std",
            "https://gitlab.com/bijux-oss/bijux-std.git",
            "git@gitlab.com:bijux-oss/bijux-std",
            "git@gitlab.com:bijux-oss/bijux-std.git",
            "ssh://git@gitlab.com/bijux-oss/bijux-std.git",
            "ssh://git@gitlab.com:22/bijux-oss/bijux-std.git",
        ):
            with self.subTest(remote=remote):
                self.assertEqual(self.classify(remote), 0)

    def test_existing_github_source_checkouts_remain_compatible(self):
        for remote in (
            "https://github.com/bijux/bijux-std",
            "https://github.com/bijux/bijux-std.git",
            "git@github.com:bijux/bijux-std",
            "git@github.com:bijux/bijux-std.git",
        ):
            with self.subTest(remote=remote):
                self.assertEqual(self.classify(remote), 0)

    def test_mirrors_unrelated_repositories_and_lookalike_urls_are_not_sources(self):
        for remote in (
            "https://gitlab.com/bijux/bijux-std.git",
            "git@gitlab.com:bijux/bijux-std.git",
            "https://gitlab.com/bijux-edu/bijux-std.git",
            "https://gitlab.com/bijux-oss/bijux-core.git",
            "https://github.com/bijux/bijux-ro-crate-node.git",
            "https://gitlab.com.example.invalid/bijux-oss/bijux-std.git",
            "https://gitlab.com@another.example.invalid/bijux-oss/bijux-std.git",
            "https://gitlab.com/bijux-oss/bijux-std.git?source=canonical",
            "https://gitlab.com/bijux-oss/bijux-std.git/another-project",
        ):
            with self.subTest(remote=remote):
                self.assertNotEqual(self.classify(remote), 0)

    def test_matching_remote_requires_both_authored_layout_markers(self):
        for remote in (
            "https://gitlab.com/bijux-oss/bijux-std.git",
            "git@github.com:bijux/bijux-std.git",
        ):
            for layout in ("consumer", "missing-checks", "missing-manifest"):
                with self.subTest(remote=remote, layout=layout):
                    self.assertNotEqual(self.classify(remote, layout=layout), 0)
