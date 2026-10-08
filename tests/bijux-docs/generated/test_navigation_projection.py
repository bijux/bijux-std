"""Exercise the admitted consumer copier rather than relying on broad fixture copies."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SHARED = ROOT / "shared/bijux-docs"
ARTIFACTS = ROOT / "artifacts/bijux-docs/consumer-projection"


class NavigationProjectionTests(unittest.TestCase):
    def fixture(self):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=ARTIFACTS)
        self.addCleanup(directory.cleanup)
        fixture = Path(directory.name)
        shared = fixture / ".bijux/shared/bijux-docs"
        shared.parent.mkdir(parents=True)
        shutil.copytree(SHARED, shared)
        (fixture / "mkdocs.shared.yml").write_text("extra:\n  bijux:\n    repository: fixture\n    theme_key: bijux:theme\n")
        (fixture / "mkdocs.yml").write_text("INHERIT: mkdocs.shared.yml\nextra:\n  bijux:\n    repository: fixture\nnav:\n  - Home: index.md\n")
        binary = fixture / "bin/git"
        binary.parent.mkdir()
        # The only seam is repository-root discovery. Copy and config behavior
        # execute the actual production script without creating another Git repo.
        binary.write_text('#!/bin/sh\nif [ "$1" = rev-parse ] && [ "$2" = --show-toplevel ]; then\n  printf "%s\\n" "$BIJUX_PROJECTION_ROOT"\nelse\n  exit 1\nfi\n')
        binary.chmod(0o755)
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "BIJUX_PROJECTION_ROOT": str(fixture), "PATH": str(binary.parent) + os.pathsep + os.environ["PATH"]}
        return fixture, shared, env

    def run_projection(self, fixture, shared, env):
        return subprocess.run(["bash", str(shared / "tooling/scripts/sync_bijux_docs.sh")], cwd=fixture, env=env, capture_output=True, text=True)

    def test_production_copier_delivers_every_owned_navigation_dependency(self):
        fixture, shared, env = self.fixture()
        result = self.run_projection(fixture, shared, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        for source in (shared / "partials").rglob("*.html"):
            destination = fixture / "docs/overrides/partials" / source.relative_to(shared / "partials")
            self.assertTrue(destination.is_file(), f"Owned partial is absent from actual consumer projection: {source.name}")
            self.assertEqual(source.read_bytes(), destination.read_bytes())
        for source in (shared / "styles").glob("*.css"):
            self.assertEqual(source.read_bytes(), (fixture / "docs/assets/styles" / source.name).read_bytes())
        for source in (shared / "scripts").glob("*.js"):
            destination = {"nav-sync.js": "docs/assets/javascripts/navigation-sync.js", "mermaid-init.js": "docs/assets/javascripts/mermaid-init.js"}.get(source.name, "docs/assets/javascripts/shell/" + source.name)
            self.assertEqual(source.read_bytes(), (fixture / destination).read_bytes())
        self.assertEqual((shared / "assets/bijux_logo_hq.png").read_bytes(), (fixture / "docs/assets/bijux_logo_hq.png").read_bytes())
        self.assertEqual((shared / "assets/site-icons/favicon.ico").read_bytes(), (fixture / "docs/assets/site-icons/favicon.ico").read_bytes())
        self.assertIn("hub_links:", (fixture / "mkdocs.shared.yml").read_text())
        self.assertIn("INHERIT: mkdocs.shared.yml", (fixture / "mkdocs.yml").read_text())
        repeated = self.run_projection(fixture, shared, env)
        self.assertEqual(repeated.returncode, 0, repeated.stderr)

    def test_missing_required_navigation_source_fails_before_consumer_writes(self):
        fixture, shared, env = self.fixture()
        (shared / "partials/nav-item.html").unlink()
        prior_config = (fixture / "mkdocs.shared.yml").read_bytes()
        result = self.run_projection(fixture, shared, env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nav-item.html", result.stderr)
        self.assertEqual(prior_config, (fixture / "mkdocs.shared.yml").read_bytes())
        self.assertFalse((fixture / "docs").exists())
