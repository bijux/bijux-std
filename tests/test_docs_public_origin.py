"""Exercise production origin admission before Make can mutate documentation."""
from __future__ import annotations

import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = Path(os.environ.get("BIJUX_PUBLIC_ORIGIN_TEST_ARTIFACTS_ROOT",
                               ROOT / "artifacts/website-delivery/public-origins"))


class DocsPublicOriginTests(unittest.TestCase):
    def setUp(self):
        folder = ARTIFACTS
        folder.mkdir(parents=True, exist_ok=True)
        self.sandbox = tempfile.TemporaryDirectory(prefix="origin-admission-", dir=folder)
        self.addCleanup(self.sandbox.cleanup)
        self.repo = Path(self.sandbox.name)
        self.events = self.repo / "events.jsonl"
        self.seed = self.repo / "artifacts/docs/site/index.html"
        self.seed.parent.mkdir(parents=True)
        self.seed.write_text("Existing qualified documentation")
        self.cache = self.repo / "artifacts/docs/cache"
        self.cache.mkdir()
        (self.repo / "mkdocs.yml").write_text("site_name: Fixture\nsite_url: https://bijux.io/bijux-core/\n")
        self.makes = self.repo / "makes/bijux-py"
        for path in ("ci/docs.mk", "root/docs.mk", "ci/util.mk"):
            target = self.makes / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "shared/bijux-makes-py" / path, target)
        self.validator = self.repo / ".bijux/shared/bijux-docs/tooling/quality/validate_production_url.py"
        self.validator.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "shared/bijux-docs/tooling/quality/validate_production_url.py", self.validator)
        self.compiler = self.repo / "compiler.py"
        self.compiler.write_text("Owned compiler fixture")
        self.verifier = self.repo / "verifier.sh"
        self.verifier.write_text('#!/bin/sh\nprintf \'{"event":"source"}\\n\' >> "$BIJUX_ORIGIN_EVENTS"\nexit "${BIJUX_ORIGIN_SOURCE_EXIT:-0}"\n')
        self.python = self.repo / "python-renderer"
        self.python.write_text("#!" + sys.executable + "\n" + '''import json, os, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
if args and args[0].endswith("validate_production_url.py"):
    raise SystemExit(subprocess.call([sys.executable, *args]))
with Path(os.environ["BIJUX_ORIGIN_EVENTS"]).open("a") as log:
    log.write(json.dumps({"event":"runtime" if args and args[0].endswith("compiler.py") else "renderer", "args":args, "site_url":os.environ.get("SITE_URL")})+"\\n")
''')
        self.python.chmod(0o755)
        self.env = {name: value for name, value in os.environ.items()
                    if name != "SITE_URL" and not name.startswith(("DOCS_", "ROOT_DOCS_", "MAKE"))}
        self.env.update(BIJUX_ORIGIN_EVENTS=str(self.events), PYTHONDONTWRITEBYTECODE="1")
        self.write_makefile()

    def write_makefile(self, *, root=False, source_exit=0):
        self.env["BIJUX_ORIGIN_SOURCE_EXIT"] = str(source_exit)
        lines = ["PROJECT_DIR := $(CURDIR)", "PROJECT_ARTIFACTS_DIR := $(CURDIR)/artifacts",
                 "MKDOCS_CFG := $(CURDIR)/mkdocs.yml", f"DOCS_PYTHON := {self.python}",
                 f"DOCS_SOURCE_VERIFIER := {self.verifier}", f"DOCS_MATERIAL_COMPILER := {self.compiler}",
                 "DOCS_BUILD_PRE_CLEAN_PATHS := $(CURDIR)/artifacts/docs/site",
                 "DOCS_CHECK_PRE_CLEAN_PATHS := $(CURDIR)/artifacts/docs/site",
                 "DOCS_BUILD_BOOTSTRAP_TARGETS := bootstrap", "DOCS_CHECK_BOOTSTRAP_TARGETS := bootstrap",
                 "DOCS_BUILD_PREPARE_TARGETS := prepare", "DOCS_CHECK_PREPARE_TARGETS := prepare",
                 "DOCS_SERVE_PREPARE_TARGETS :=", "DOCS_SERVE_PRE_CLEAN_PATHS :=", "DOCS_HYGIENE_FORBID_ROOT :="]
        if root:
            lines += [f"ROOT_MAKE_DIR := {self.makes.parent}", "ROOT_CHECK_PYTHON := $(DOCS_PYTHON)",
                      "ROOT_DOCS_CACHE_DIR := $(CURDIR)/artifacts/docs/cache", "ROOT_DOCS_BUILD_SITE_DIR := $(CURDIR)/artifacts/docs/site",
                      "ROOT_DOCS_CHECK_SITE_DIR := $(CURDIR)/artifacts/docs/site", "ROOT_DOCS_SERVE_SITE_DIR := $(CURDIR)/artifacts/docs/serve",
                      "ROOT_DOCS_DEV_ADDR := 127.0.0.1:62969", "ROOT_DOCS_SERVE_CFG := $(CURDIR)/artifacts/docs/serve.yml",
                      "DOCS_SERVE_BOOTSTRAP_TARGETS :=", "DOCS_RENDER_SERVE_CONFIG := 0"]
        lines += [f"include {self.makes / ('root/docs.mk' if root else 'ci/docs.mk')}",
                  "bootstrap prepare:", '\t@printf \'{"event":"$@"}\\n\' >> "$(BIJUX_ORIGIN_EVENTS)"']
        (self.repo / "Makefile").write_text("\n".join(lines) + "\n")

    def make(self, goal, **variables):
        result = subprocess.run(["make", "--no-print-directory", goal,
                                 *(f"{name}={value}" for name, value in variables.items())],
                                cwd=self.repo, env=self.env, text=True, capture_output=True, timeout=15)
        events = [json.loads(line) for line in self.events.read_text().splitlines()] if self.events.exists() else []
        receipts = ARTIFACTS / "receipts"
        receipts.mkdir(exist_ok=True)
        existing = list(receipts.glob(self._testMethodName + "-*.json"))
        (receipts / f"{self._testMethodName}-{len(existing)}.json").write_text(json.dumps({
            "goal": goal, "variables": variables, "exit": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr, "events": events,
            "existing_public_artifact": self.seed.read_text() if self.seed.exists() else None}, indent=2) + "\n")
        return result, events

    def test_public_site_url_is_default_for_build_and_check(self):
        for goal in ("docs", "docs-check"):
            with self.subTest(goal=goal):
                result, events = self.make(goal, DOCS_SITE_URL="https://bijux.io/bijux-core/")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(events[-1]["site_url"], "https://bijux.io/bijux-core/")
                self.assertEqual([event["event"] for event in events[-5:]], ["bootstrap", "source", "runtime", "prepare", "renderer"])

    def test_root_build_and_check_use_public_default_instead_of_dev_origin(self):
        self.write_makefile(root=True)
        for goal in ("docs", "docs-check"):
            result, events = self.make(goal, DOCS_SITE_URL="https://bijux.io/bijux-core/")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(events[-1]["site_url"], "https://bijux.io/bijux-core/")

    def test_site_url_environment_is_the_generic_public_default(self):
        self.env["SITE_URL"] = "https://bijux.io/"
        result, events = self.make("docs-check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events[-1]["site_url"], "https://bijux.io/")

    def test_empty_override_preserves_authored_config_default(self):
        result, events = self.make("docs-check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(events[-1]["site_url"])
        self.assertIn("site_url: https://bijux.io/bijux-core/", (self.repo / "mkdocs.yml").read_text())

    def test_invalid_origins_reject_before_bootstrap_or_public_mutation(self):
        for goal, variable in (("docs", "DOCS_BUILD_SITE_URL"), ("docs-check", "DOCS_CHECK_SITE_URL")):
            for url in ("http://127.0.0.1:8000/", "https://localhost/", "https://192.168.1.2/", "https://preview.invalid/",
                        "https://bijux.io/path", "https://user@bijux.io/", "https://bijux.io/path/../", "https://bijux.io/?key=value"):
                with self.subTest(goal=goal, url=url):
                    result, events = self.make(goal, **{variable: url})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Production site URL", result.stderr)
                    self.assertEqual(events, [])
                    self.assertEqual(self.seed.read_text(), "Existing qualified documentation")

    def test_missing_validator_rejects_before_any_mutation(self):
        self.validator.unlink()
        result, events = self.make("docs-check", DOCS_SITE_URL="https://bijux.io/")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("validator is unavailable", result.stderr)
        self.assertEqual(events, [])
        self.assertTrue(self.seed.is_file())

    def policy(self):
        spec = importlib.util.spec_from_file_location("owned_origin_policy", self.validator)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_unicode_loopback_origins_reject_before_build_mutation(self):
        for goal, variable in (("docs", "DOCS_BUILD_SITE_URL"), ("docs-check", "DOCS_CHECK_SITE_URL")):
            for host in ("127\u30020.0.1", "127\uff0e0.0.1", "127\uff610.0.1", "\uff10x7f.0.0.1"):
                with self.subTest(goal=goal, host=host):
                    result, events = self.make(goal, **{variable: "https://" + host + "/"})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("local/private/reserved/development hostname", result.stderr)
                    self.assertEqual(events, [])
                    self.assertEqual(self.seed.read_text(), "Existing qualified documentation")

    def test_unicode_public_hosts_preserve_public_origin_admission(self):
        policy = self.policy()
        for host in ("b\u00fccher.de", "caf\u00e9.example.com", "bijux\u3002io", "bijux\uff0eio"):
            with self.subTest(host=host):
                self.assertFalse(policy.development_host(host))
                self.assertEqual(policy.validate("https://" + host + "/docs/"), "https://" + host + "/docs/")

    def test_unicode_private_suffixes_and_compatibility_literals_are_private(self):
        policy = self.policy()
        for host in ("assets.private\u3002internal", "assets.private\uff0einternal", "assets.private\uff61internal",
                     "assets.local\u3002home.arpa", "\uff11\uff12\uff17.0.0.1", "\uff10x7f.0.0.1"):
            with self.subTest(host=host):
                self.assertTrue(policy.development_host(host))

    def test_literal_ip_and_development_boundaries_survive_host_normalization(self):
        policy = self.policy()
        for host in ("localhost.", "127.1", "2130706433", "0177.0.0.1", "0x7f.0.0.1", "192.168.1.2",
                     "10.0.0.1", "169.254.1.2", "::1", "fc00::1", "fe80::1", "224.0.0.1"):
            with self.subTest(host=host):
                self.assertTrue(policy.development_host(host))
        for host in ("bijux.io", "8.8.8.8", "2001:4860:4860::8888"):
            with self.subTest(host=host):
                self.assertFalse(policy.development_host(host))

    def test_unsupported_idna_hosts_fail_closed(self):
        policy = self.policy()
        for host in ("\ud800.example.com", "a..example.com", "a" * 64 + ".example.com"):
            with self.subTest(host=host):
                self.assertTrue(policy.development_host(host))

    def test_source_authority_rejection_still_precedes_cleaning(self):
        self.write_makefile(source_exit=3)
        result, events = self.make("docs-check", DOCS_SITE_URL="https://bijux.io/")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([event["event"] for event in events], ["bootstrap", "source"])
        self.assertTrue(self.seed.is_file())

    def test_framework_receives_public_origin_and_strict_flags(self):
        result, events = self.make("docs-check", DOCS_SITE_URL="https://bijux.io/", DOCS_PUBLICATION_FRAMEWORK="1", BIJUX_DOCS_SHARED_DIR=str(self.validator.parents[2]), DOCS_PUBLICATION_RENDERER="publisher.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("publisher.py", events[-1]["args"])
        self.assertEqual(events[-1]["args"][-2:], ["--site-url", "https://bijux.io/"])

    def test_framework_non_strict_render_remains_rejected(self):
        result, events = self.make("docs-check", DOCS_SITE_URL="https://bijux.io/", DOCS_PUBLICATION_FRAMEWORK="1", BIJUX_DOCS_SHARED_DIR=str(self.validator.parents[2]), DOCS_BUILD_FLAGS="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires exact --strict", result.stderr)
        self.assertNotIn("renderer", [event["event"] for event in events])

    def test_framework_missing_source_still_fails_before_any_mutation(self):
        result, events = self.make("docs-check", DOCS_PUBLICATION_FRAMEWORK="1", DOCS_SITE_URL="https://bijux.io/")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must identify the accepted shared documentation source", result.stderr)
        self.assertEqual(events, [])
        self.assertTrue(self.seed.is_file())

    def test_development_serve_remains_explicit_and_does_not_admit_publication(self):
        result, events = self.make("docs-serve-run", DOCS_DEV_ADDR="127.0.0.1:62969", DOCS_SERVE_SITE_URL="http://127.0.0.1:62969/", DOCS_BUILD_SITE_URL="http://localhost/")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events[-1]["site_url"], "http://127.0.0.1:62969/")
        self.assertEqual(events[-1]["args"][:3], ["-m", "mkdocs", "serve"])
        self.assertIn("127.0.0.1:62969", events[-1]["args"])
        self.assertTrue(self.seed.is_file())

    def test_root_serve_keeps_development_default(self):
        self.write_makefile(root=True)
        result, events = self.make("docs-serve-run", DOCS_SITE_URL="https://bijux.io/")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events[-1]["site_url"], "http://127.0.0.1:62969/")
        self.assertTrue(self.seed.is_file())

    def test_deploy_stays_closed(self):
        result, events = self.make("docs-deploy")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact qualified artifact", result.stderr)
        self.assertEqual(events, [])
        self.assertTrue(self.seed.is_file())


if __name__ == "__main__":
    unittest.main()
