from __future__ import annotations

import os
import shutil
import subprocess
import time
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SHARED_ROOT = REPOSITORY_ROOT / "shared"
TEST_ROOT = REPOSITORY_ROOT / "artifacts" / "tests" / "shared-make-common"


class SharedMakeCommonTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)
        TEST_ROOT.mkdir(parents=True)

    def run_make(
        self,
        fixture: Path,
        *targets: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["make", "--no-print-directory", *targets],
            cwd=fixture,
            check=check,
            text=True,
            capture_output=True,
            env={**os.environ, "TMPDIR": str(TEST_ROOT / "process")},
        )

    def write_fixture(self, name: str, makefile: str) -> Path:
        fixture = TEST_ROOT / name
        fixture.mkdir()
        (fixture / "Makefile").write_text(makefile, encoding="utf-8")
        return fixture

    def test_common_contract_omits_unconfigured_language_targets(self) -> None:
        fixture = self.write_fixture(
            "common-only",
            (
                f"BIJUX_MAKES_SHARED_ROOT := {SHARED_ROOT}\n"
                f"include {SHARED_ROOT}/bijux-makes/bijux.mk\n"
            ),
        )

        help_result = self.run_make(fixture, "help")
        self.assertIn("doctor", help_result.stdout)
        self.assertNotIn("fmt ", help_result.stdout)

        fmt_result = self.run_make(fixture, "fmt", check=False)
        self.assertNotEqual(fmt_result.returncode, 0)
        self.assertIn("No rule to make target", fmt_result.stderr)

    def test_doctor_rejects_artifacts_outside_repository_boundary(self) -> None:
        fixture = self.write_fixture(
            "artifact-boundary",
            (
                f"BIJUX_MAKES_SHARED_ROOT := {SHARED_ROOT}\n"
                "ARTIFACT_ROOT := output\n"
                f"include {SHARED_ROOT}/bijux-makes/bijux.mk\n"
            ),
        )

        result = self.run_make(fixture, "doctor", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("artifact root must stay under", result.stderr)

    def test_docs_component_builds_and_checks_under_artifacts(self) -> None:
        fixture = self.write_fixture(
            "docs",
            (
                "BIJUX_MAKE_COMPONENTS := docs\n"
                f"BIJUX_MAKES_SHARED_ROOT := {SHARED_ROOT}\n"
                "DOCS_RUN := ./mkdocs-fixture\n"
                f"include {SHARED_ROOT}/bijux-makes/bijux.mk\n"
            ),
        )
        (fixture / "mkdocs.yml").write_text("site_name: Fixture\n", encoding="utf-8")
        runner = fixture / "mkdocs-fixture"
        runner.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
site_dir=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--site-dir" ]; then
    site_dir="$2"
    shift 2
  else
    shift
  fi
done
if [ -n "${site_dir}" ]; then
  mkdir -p "${site_dir}"
  printf '<html>fixture</html>\\n' >"${site_dir}/index.html"
fi
""",
            encoding="utf-8",
        )
        runner.chmod(0o755)

        self.run_make(fixture, "docs", "docs-check")

        self.assertTrue((fixture / "artifacts/docs/site/index.html").is_file())
        self.assertTrue((fixture / "artifacts/docs/check-site/index.html").is_file())
        self.assertFalse((fixture / "site").exists())

    def test_pinned_gate_runs_from_the_requested_commit(self) -> None:
        fixture = self.write_fixture(
            "pinned",
            """probe:
\t@mkdir -p "$(ARTIFACT_ROOT)/probe"
\t@git rev-parse HEAD >"$(ARTIFACT_ROOT)/probe/commit.txt"
\t@pwd >"$(ARTIFACT_ROOT)/probe/source.txt"
\t@printf '%s\\n' "$(PROJECT_ROOT)" >"$(ARTIFACT_ROOT)/probe/project-root.txt"
""",
        )
        subprocess.run(["git", "init", "-q"], cwd=fixture, check=True)
        subprocess.run(
            ["git", "config", "user.email", "bijux@example.invalid"],
            cwd=fixture,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Bijux Tests"],
            cwd=fixture,
            check=True,
        )
        subprocess.run(["git", "add", "Makefile"], cwd=fixture, check=True)
        subprocess.run(["git", "commit", "-qm", "test: define pinned probe"], cwd=fixture, check=True)
        expected_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=fixture,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        short_sha = expected_sha[:9]
        with (fixture / "Makefile").open("a", encoding="utf-8") as makefile:
            makefile.write("\n# Keep HEAD distinct from the requested frozen commit.\n")
        subprocess.run(["git", "add", "Makefile"], cwd=fixture, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "test: distinguish invoking head"],
            cwd=fixture,
            check=True,
        )

        launcher = SHARED_ROOT / "bijux-makes/scripts/run_pinned_gate.sh"
        result = subprocess.run(
            [str(launcher)],
            cwd=fixture,
            check=True,
            text=True,
            capture_output=True,
            env={
                **os.environ,
                "PINNED_GATE_TARGET": "probe",
                "PINNED_ALLOWED_TARGETS": "probe",
                "TEST_ALL_FROZEN_REF": expected_sha,
                "PROJECT_ROOT": str(fixture / "mutable-source"),
                "RS_ARTIFACT_ROOT": str(fixture / "mutable-artifacts"),
                "NEXTEST_CONFIG_FILE": str(fixture / "mutable-nextest.toml"),
            },
        )
        self.assertIn(f"started probe for {short_sha}", result.stdout)

        status_file = fixture / f"artifacts/{short_sha}/background/probe.exit.status"
        deadline = time.monotonic() + 10
        while not status_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(status_file.is_file())
        self.assertEqual(status_file.read_text(encoding="utf-8").strip(), "0")
        self.assertEqual(
            (fixture / f"artifacts/{short_sha}/probe/commit.txt")
            .read_text(encoding="utf-8")
            .strip(),
            expected_sha,
        )
        frozen_source = fixture / f"artifacts/{short_sha}/frozen-repo"
        self.assertEqual(
            (fixture / f"artifacts/{short_sha}/probe/source.txt")
            .read_text(encoding="utf-8")
            .strip(),
            str(frozen_source),
        )
        self.assertEqual(
            (fixture / f"artifacts/{short_sha}/probe/project-root.txt")
            .read_text(encoding="utf-8")
            .strip(),
            str(frozen_source),
        )
        self.assertFalse((fixture / "mutable-artifacts").exists())


if __name__ == "__main__":
    unittest.main()
