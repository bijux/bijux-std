"""Render actual !ENV production defaults through the documentation Make recipes."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("bijux_public_origin_fixture", ROOT / "tests/test_docs_public_origin.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class DocsPublicOriginMakeTests(unittest.TestCase):
    write_makefile = fixture.DocsPublicOriginTests.write_makefile
    make = fixture.DocsPublicOriginTests.make

    def setUp(self):
        fixture.DocsPublicOriginTests.setUp(self)
        self.url = "https://bijux.io/bijux-core/"
        (self.repo / "docs").mkdir()
        (self.repo / "docs/index.md").write_text("# Public documentation\n\nA real canonical reader page.\n")
        (self.repo / "mkdocs.yml").write_text(
            "site_name: Public origin fixture\nsite_url: !ENV [SITE_URL, '" + self.url + "']\n")
        with (self.repo / "Makefile").open("a") as stream:
            stream.write("DOCS_BUILD_CONFIG_FILE := $(CURDIR)/mkdocs.yml\nDOCS_CHECK_CONFIG_FILE := $(CURDIR)/mkdocs.yml\n")
        # Source/compiler boundaries are controlled fixtures. The actual selected
        # interpreter executes MkDocs; no fixture grants source or runtime approval.
        self.python.write_text("#!" + sys.executable + "\n" + '''import json, os, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
if args and args[0].endswith("validate_production_url.py"):
    raise SystemExit(subprocess.call([sys.executable, *args]))
with Path(os.environ["BIJUX_ORIGIN_EVENTS"]).open("a") as log:
    log.write(json.dumps({"event":"runtime" if args and args[0].endswith("compiler.py") else "renderer", "args":args, "site_url":os.environ.get("SITE_URL")})+"\\n")
if args and args[0].endswith("compiler.py"):
    raise SystemExit(0)
raise SystemExit(subprocess.call([sys.executable, *args]))
''')

    def render(self, goal="docs-check", **variables):
        result, events = self.make(goal, **variables)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return self.seed.read_text(), events

    def test_unset_override_renders_authored_canonical_default(self):
        for goal in ("docs", "docs-check"):
            with self.subTest(goal=goal):
                html, events = self.render(goal)
                self.assertIn('rel="canonical" href="' + self.url + '"', html)
                self.assertIsNone(events[-1]["site_url"])

    def test_inherited_empty_override_is_unset_before_actual_render(self):
        self.env["SITE_URL"] = ""
        html, events = self.render()
        self.assertIn('rel="canonical" href="' + self.url + '"', html)
        self.assertIsNone(events[-1]["site_url"])

    def test_explicit_public_override_renders_exact_canonical_origin(self):
        selected = "https://bijux.io/bijux-atlas/"
        html, events = self.render(DOCS_CHECK_SITE_URL=selected)
        self.assertIn('rel="canonical" href="' + selected + '"', html)
        self.assertEqual(events[-1]["site_url"], selected)

    def test_explicit_invalid_origin_rejects_before_real_render_or_public_mutation(self):
        result, events = self.make("docs-check", DOCS_CHECK_SITE_URL="http://localhost/")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Production site URL", result.stderr)
        self.assertEqual(events, [])
        self.assertEqual(self.seed.read_text(), "Existing qualified documentation")


if __name__ == "__main__":
    unittest.main()
