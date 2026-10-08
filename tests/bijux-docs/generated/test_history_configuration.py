"""Qualify default history features and deliberate authored tracking overrides."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml
import test_shell_configuration as configuration

ROOT = Path(__file__).resolve().parents[3]


class ReaderHistoryConfigurationTests(unittest.TestCase):
    def fixture(self, directory):
        return configuration.ShellConfigurationLoaderTests().cli_fixture(directory)

    def run_validator(self, repo):
        return subprocess.run([sys.executable, str(configuration.PATH), str(repo)], capture_output=True, text=True, timeout=15)

    def test_default_features_validate_without_automatic_fragment_tracking(self):
        parent = ROOT / "artifacts/bijux-docs/history-configuration"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            repo, effective, _ = self.fixture(directory)
            self.assertNotIn("navigation.tracking", effective["theme"]["features"])
            result = self.run_validator(repo)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_explicit_authored_tracking_remains_admitted_and_unchanged(self):
        parent = ROOT / "artifacts/bijux-docs/history-configuration"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            repo, effective, root = self.fixture(directory)
            root["theme"] = {"features": [*effective["theme"]["features"], "navigation.tracking"]}
            path = repo / "mkdocs.yml"
            path.write_text(yaml.safe_dump(root, sort_keys=False))
            before = path.read_bytes()
            result = self.run_validator(repo)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(before, path.read_bytes())

    def test_history_policy_retains_instant_navigation_and_toc_follow(self):
        parent = ROOT / "artifacts/bijux-docs/history-configuration"
        parent.mkdir(parents=True, exist_ok=True)
        for feature in ("navigation.instant", "toc.follow"):
            with self.subTest(feature=feature), tempfile.TemporaryDirectory(dir=parent) as directory:
                repo, effective, root = self.fixture(directory)
                root["theme"] = {"features": [value for value in effective["theme"]["features"] if value != feature]}
                (repo / "mkdocs.yml").write_text(yaml.safe_dump(root, sort_keys=False))
                result = self.run_validator(repo)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("theme.features must include " + feature, result.stdout + result.stderr)
