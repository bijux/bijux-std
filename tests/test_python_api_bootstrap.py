from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


CONTRACT = Path(__file__).resolve().parents[1] / "shared/bijux-makes-py/api-contract.mk"


class PythonApiBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = self.root / "configs"
        self.config.mkdir()
        self.manifest = self.config / "package.json"
        self.lock = self.config / "package-lock.json"
        self.manifest.write_text('{"private":true,"engines":{"node":">=22.12.0"}}\n')
        self.lock.write_text('{"lockfileVersion":3,"packages":{}}\n')
        self.node = self.root / "artifacts/api/node"
        self.marker = self.node / ".deps-ok"
        self.trace = self.root / "npm-trace.jsonl"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        npm = self.bin / "npm"
        npm.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            "with open(os.environ['API_NPM_TRACE'], 'a') as output:\n"
            " output.write(json.dumps({'args':sys.argv[1:], 'cwd':os.getcwd()})+'\\n')\n"
            "if os.environ.get('API_NPM_FAIL') == '1': sys.exit(19)\n"
            "if sys.argv[1] == 'init': pathlib.Path('package.json').write_text('{}')\n"
        )
        npm.chmod(0o755)
        self.makefile = self.root / "Makefile"
        self.makefile.write_text(
            f"MONOREPO_ROOT := {self.root}\n"
            f"API_ARTIFACTS_DIR := {self.root}/artifacts/api\n"
            f"include {CONTRACT}\n"
        )
        self.environment = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "API_NPM_TRACE": str(self.trace),
        }

    def run_make(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["make", "--no-print-directory", "-f", str(self.makefile), "node_deps", *arguments],
            cwd=self.root,
            env=self.environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def calls(self) -> list[dict]:
        return [json.loads(line) for line in self.trace.read_text().splitlines()] if self.trace.exists() else []

    def test_default_installs_reviewed_lock_with_strict_engines(self) -> None:
        result = self.run_make()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.node / "package.json").read_bytes(), self.manifest.read_bytes())
        self.assertEqual((self.node / "package-lock.json").read_bytes(), self.lock.read_bytes())
        self.assertTrue(self.marker.is_file())
        self.assertEqual(self.calls(), [{"args": ["ci", "--engine-strict", "--no-fund", "--no-audit", "--loglevel=info"], "cwd": str(self.node)}])
        self.assertEqual(self.run_make().returncode, 0)
        self.assertEqual(len(self.calls()), 1)

    def test_missing_lock_rejects_without_installation_or_marker(self) -> None:
        self.lock.unlink()
        self.assertNotEqual(self.run_make().returncode, 0)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.marker.exists())

    def test_failed_locked_installation_never_admits_marker(self) -> None:
        self.environment["API_NPM_FAIL"] = "1"
        self.assertNotEqual(self.run_make().returncode, 0)
        self.assertEqual(len(self.calls()), 1)
        self.assertFalse(self.marker.exists())

    def test_failed_refresh_revokes_previous_ready_marker(self) -> None:
        self.assertEqual(self.run_make().returncode, 0)
        self.lock.write_text(self.lock.read_text() + " ")
        future = max(time.time(), self.marker.stat().st_mtime) + 2
        os.utime(self.lock, (future, future))
        self.environment["API_NPM_FAIL"] = "1"
        self.assertNotEqual(self.run_make().returncode, 0)
        self.assertFalse(self.marker.exists())
        self.assertEqual(len(self.calls()), 2)

    def test_manifest_and_lock_changes_rebuild_sandbox(self) -> None:
        self.assertEqual(self.run_make().returncode, 0)
        for path in (self.manifest, self.lock):
            path.write_text(path.read_text() + " ")
            future = max(time.time(), self.marker.stat().st_mtime) + 2
            os.utime(path, (future, future))
            self.assertEqual(self.run_make().returncode, 0)
            self.assertEqual((self.node / path.name).read_bytes(), path.read_bytes())
            os.utime(path, (time.time() - 2, time.time() - 2))
        self.assertEqual(len(self.calls()), 3)

    def test_unreviewed_fallback_mode_rejects_without_npm(self) -> None:
        self.assertNotEqual(self.run_make("API_NODE_BOOTSTRAP_MODE=npm-install-fallback").returncode, 0)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.marker.exists())

    def test_disabled_node_tools_need_no_package_inputs_or_installation(self) -> None:
        self.manifest.unlink()
        self.lock.unlink()
        self.assertEqual(self.run_make("API_ENABLE_NODE_TOOLS=0").returncode, 0)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.marker.exists())

    def test_failed_explicit_pinned_install_never_falls_back(self) -> None:
        self.node.mkdir(parents=True)
        (self.node / "package.json").write_text('{}')
        self.environment["API_NPM_FAIL"] = "1"
        self.assertNotEqual(self.run_make("API_NODE_BOOTSTRAP_MODE=npm-install-pinned").returncode, 0)
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["args"][0], "install")
        self.assertIn("@openapitools/openapi-generator-cli@2.41.0", calls[0]["args"])
        self.assertIn("@redocly/cli@2.58.1", calls[0]["args"])
        self.assertFalse(self.marker.exists())


if __name__ == "__main__":
    unittest.main()
