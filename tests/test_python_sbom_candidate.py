"""Package SBOMs bind a locked closure to their source candidate."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "shared/bijux-makes-py"
TEST_ROOT = ROOT / "artifacts/tests/python-sbom-candidate"


def _run(
    argv: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


class PythonSbomCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)
        TEST_ROOT.mkdir(parents=True)
        self.candidate = TEST_ROOT / "candidate"
        self.candidate.mkdir()
        (self.candidate / "makes/bijux-py/ci").mkdir(parents=True)
        (self.candidate / "makes/bijux-py/repository").mkdir()
        (self.candidate / "packages/demo").mkdir(parents=True)
        (self.candidate / "venv/bin").mkdir(parents=True)
        shutil.copyfile(
            SOURCE / "ci/sbom.mk", self.candidate / "makes/bijux-py/ci/sbom.mk"
        )
        shutil.copyfile(
            SOURCE / "repository/sbom_provenance.py",
            self.candidate / "makes/bijux-py/repository/sbom_provenance.py",
        )
        (self.candidate / "pyproject.toml").write_text(
            "[project]\nname = 'workspace'\n"
        )
        (self.candidate / "uv.lock").write_text("locked dependency closure\n")
        (self.candidate / "packages/demo/pyproject.toml").write_text(
            "[project]\nname = 'demo'\n"
        )
        (self.candidate / "Makefile").write_text(
            "SHELL := bash\n.SHELLFLAGS := -eu -o pipefail -c\n"
            "include makes/bijux-py/ci/sbom.mk\n"
        )
        python = self.candidate / "venv/bin/python"
        python.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = -c ] && [ "$2" = \'import pip_audit\' ]; then exit 0; fi\n'
            f'exec {sys.executable} "$@"\n'
        )
        python.chmod(0o755)
        (self.candidate / "fake_uv.py").write_text(
            "import os,pathlib,sys\n"
            "args=sys.argv[1:]\n"
            "assert args[:2]==['export','--frozen'],args\n"
            "assert '--offline' in args and '--package' in args and '--no-emit-local' in args,args\n"
            "if os.getenv('SKIP_EXPORT'): raise SystemExit(0)\n"
            "path=pathlib.Path(args[args.index('--output-file')+1])\n"
            "path.write_text('' if os.getenv('EMPTY_EXPORT') else 'locked-dependency==1.0\\n')\n"
            "with pathlib.Path('uv-argv.log').open('a') as log: log.write(' '.join(args)+'\\n')\n"
        )
        (self.candidate / "fake_audit.py").write_text(
            "import json,os,pathlib,sys\n"
            "args=sys.argv[1:]\n"
            "assert '-r' in args,args\n"
            "requirements=pathlib.Path(args[args.index('-r')+1])\n"
            "assert requirements.read_text()==('' if os.getenv('EMPTY_EXPORT') else 'locked-dependency==1.0\\n')\n"
            "output=pathlib.Path(args[args.index('--output')+1])\n"
            "output.write_text(json.dumps({'bomFormat':'CycloneDX','components':[]}))\n"
            "with pathlib.Path('audit-argv.log').open('a') as log: log.write(' '.join(args)+'\\n')\n"
            "if os.getenv('MUTATE_SOURCE'): pathlib.Path('uv.lock').write_text('changed during audit\\n')\n"
            "if os.getenv('FAIL_AUDIT'): raise SystemExit(17)\n"
        )
        for args in (
            ("init", "-q"),
            ("config", "user.email", "sbom@example.invalid"),
            ("config", "user.name", "SBOM Fixture"),
            (
                "add",
                "pyproject.toml",
                "uv.lock",
                "packages/demo/pyproject.toml",
                "makes/bijux-py/ci/sbom.mk",
                "makes/bijux-py/repository/sbom_provenance.py",
                "Makefile",
            ),
            ("commit", "-qm", "establish source candidate"),
            ("tag", "v1.2.3"),
        ):
            result = _run(["git", *args], cwd=self.candidate)
            self.assertEqual(result.returncode, 0, result.stderr)
        (self.candidate / "README.md").write_text("Source candidate\n")
        for args in (
            ("add", "README.md"),
            ("commit", "-qm", "retain source candidate"),
        ):
            result = _run(["git", *args], cwd=self.candidate)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.environment = {
            "SBOM_SOURCE_ROOT": str(self.candidate),
            "MONOREPO_ROOT": str(self.candidate),
            "SBOM_PYPROJECT": "packages/demo/pyproject.toml",
            "PROJECT_ARTIFACTS_DIR": str(TEST_ROOT / "products"),
            "PACKAGE_NAME": "demo",
            "VENV_PYTHON": str(python),
            "SBOM_METADATA_PYTHON": sys.executable,
            "SBOM_PIP_AUDIT": f"{sys.executable} fake_audit.py",
            "UV": f"{sys.executable} fake_uv.py",
            "SBOM_REQUIRE_CANDIDATE_PROVENANCE": "1",
        }

    def make(self, target: str, **options: str) -> subprocess.CompletedProcess[str]:
        return _run(
            [
                "make",
                "-f",
                "Makefile",
                target,
                *(f"{key}={value}" for key, value in options.items()),
            ],
            cwd=self.candidate,
            env=self.environment,
        )

    def test_locked_package_closure_has_natural_version_and_exact_summary(self) -> None:
        result = self.make("sbom")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        files = sorted((TEST_ROOT / "products/sbom").glob("*.cdx.json"))
        self.assertEqual(len(files), 2)
        self.assertTrue(all("1.2.4.dev1" in path.name for path in files))
        commit = _run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=self.candidate
        ).stdout.strip()
        self.assertTrue(all(commit in path.name for path in files))
        for path in files:
            component = json.loads(path.read_text())["metadata"]["component"]
            self.assertEqual(
                component, {"type": "library", "name": "demo", "version": "1.2.4.dev1"}
            )
        exports = (self.candidate / "uv-argv.log").read_text().splitlines()
        self.assertEqual(len(exports), 2)
        self.assertEqual(sum("--extra dev" in line for line in exports), 1)
        self.assertEqual(
            len((self.candidate / "audit-argv.log").read_text().splitlines()), 2
        )
        self.assertEqual(
            len((TEST_ROOT / "products/sbom/summary.txt").read_text().splitlines()), 2
        )

    def test_source_change_and_wrong_version_refuse_before_audit(self) -> None:
        self.assertNotEqual(self.make("sbom-prod", SBOM_VERSION="1.2.3").returncode, 0)
        self.assertNotEqual(self.make("sbom-prod", GIT_SHA="deadbee").returncode, 0)
        (self.candidate / "uv.lock").write_text("different closure\n")
        result = self.make("sbom-prod")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tracked changes", result.stderr)
        self.assertFalse((self.candidate / "audit-argv.log").exists())

    def test_audit_failure_preserves_failed_artifact_without_publishing(self) -> None:
        result = _run(
            ["make", "-f", "Makefile", "sbom-prod"],
            cwd=self.candidate,
            env={**self.environment, "FAIL_AUDIT": "1"},
        )
        self.assertNotEqual(result.returncode, 0)
        outputs = TEST_ROOT / "products/sbom"
        self.assertEqual(list(outputs.glob("*.prod.cdx.json")), [])
        failed = list(outputs.glob("*.prod.cdx.json.failed"))
        self.assertEqual(len(failed), 1)
        self.assertEqual(
            json.loads(failed[0].read_text())["metadata"]["component"]["name"], "demo"
        )

    def test_source_change_during_audit_refuses_promotion(self) -> None:
        result = _run(
            ["make", "-f", "Makefile", "sbom-prod"],
            cwd=self.candidate,
            env={**self.environment, "MUTATE_SOURCE": "1"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            list((TEST_ROOT / "products/sbom").glob("*.prod.cdx.json")), []
        )
        self.assertEqual(
            len(list((TEST_ROOT / "products/sbom").glob("*.prod.cdx.json.failed"))), 1
        )

    def test_missing_locked_export_never_falls_back_to_environment(self) -> None:
        result = _run(
            ["make", "-f", "Makefile", "sbom-prod"],
            cwd=self.candidate,
            env={**self.environment, "SKIP_EXPORT": "1"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing package production closure", result.stdout)
        self.assertFalse((self.candidate / "audit-argv.log").exists())

    def test_missing_export_cannot_reuse_an_existing_requirements_file(self) -> None:
        for scope in ("prod", "dev"):
            requirements = TEST_ROOT / f"products/sbom/requirements.{scope}.txt"
            requirements.parent.mkdir(parents=True, exist_ok=True)
            requirements.write_text("locked-dependency==1.0\n")
            result = _run(
                ["make", "-f", "Makefile", f"sbom-{scope}"],
                cwd=self.candidate,
                env={**self.environment, "SKIP_EXPORT": "1"},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(requirements.exists())
            self.assertFalse((self.candidate / "audit-argv.log").exists())

    def test_zero_dependency_export_keeps_an_explicit_empty_closure(self) -> None:
        result = _run(
            ["make", "-f", "Makefile", "sbom"],
            cwd=self.candidate,
            env={**self.environment, "EMPTY_EXPORT": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        products = TEST_ROOT / "products/sbom"
        self.assertEqual((products / "requirements.prod.txt").read_bytes(), b"")
        self.assertEqual((products / "requirements.dev.txt").read_bytes(), b"")
        self.assertEqual(len(list(products.glob("*.cdx.json"))), 2)
        self.assertEqual(
            len((self.candidate / "audit-argv.log").read_text().splitlines()), 2
        )

    def test_configured_requirements_route_remains_available_without_strict_mode(
        self,
    ) -> None:
        (self.candidate / "requirements.txt").write_text("locked-dependency==1.0\n")
        result = self.make(
            "sbom-prod",
            SBOM_REQUIRE_CANDIDATE_PROVENANCE="0",
            SBOM_PROD_REQ_INPUT="requirements.txt",
            PKG_VERSION="2.0.0",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        outputs = list((TEST_ROOT / "products/sbom").glob("*.prod.cdx.json"))
        self.assertEqual(len(outputs), 1)
        self.assertEqual(
            json.loads(outputs[0].read_text())["metadata"]["component"],
            {"type": "library", "name": "demo", "version": "2.0.0"},
        )

    def test_snapshot_requires_every_declared_input_digest(self) -> None:
        snapshot_root = TEST_ROOT / "snapshot"
        snapshot_root.mkdir()
        rels = (
            "pyproject.toml",
            "uv.lock",
            "packages/demo/pyproject.toml",
            "makes/bijux-py/ci/sbom.mk",
            "makes/bijux-py/repository/sbom_provenance.py",
        )
        for relative in rels:
            destination = snapshot_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.candidate / relative, destination)
        commit = _run(["git", "rev-parse", "HEAD"], cwd=self.candidate).stdout.strip()
        describe = _run(
            ["git", "describe", "--tags", "--long", "--match", "v[0-9]*"],
            cwd=self.candidate,
        ).stdout.strip()
        input_hashes: dict[str, str] = {
            relative: hashlib.sha256(
                (snapshot_root / relative).read_bytes()
            ).hexdigest()
            for relative in rels
        }
        payload = {
            "schema": "bijux-sbom-snapshot-v1",
            "source_repository": "fixture/demo",
            "source_commit": commit,
            "source_describe": describe,
            "input_sha256": input_hashes,
        }
        provenance = snapshot_root / ".sbom-snapshot-provenance.json"
        provenance.write_text(json.dumps(payload))
        command = [
            sys.executable,
            str(SOURCE / "repository/sbom_provenance.py"),
            "verify",
            "--root",
            str(snapshot_root),
            "--snapshot",
            str(provenance),
            "--sha",
            commit[:8],
            "--version",
            "1.2.4.dev1",
            "--root-project",
            rels[0],
            "--lockfile",
            rels[1],
            "--package-project",
            rels[2],
            "--make-source",
            rels[3],
            "--helper-source",
            rels[4],
        ]
        accepted = _run(command, cwd=snapshot_root)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        (snapshot_root / "uv.lock").write_text("tampered\n")
        refused = _run(command, cwd=snapshot_root)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("input changed", refused.stderr)
        shutil.copyfile(self.candidate / "uv.lock", snapshot_root / "uv.lock")
        del input_hashes[rels[-1]]
        provenance.write_text(json.dumps(payload))
        incomplete = _run(command, cwd=snapshot_root)
        self.assertNotEqual(incomplete.returncode, 0)
        self.assertIn("omits required candidate inputs", incomplete.stderr)
        input_hashes[rels[-1]] = hashlib.sha256(
            (snapshot_root / rels[-1]).read_bytes()
        ).hexdigest()
        provenance.write_text(json.dumps(payload))
        lock = snapshot_root / "uv.lock"
        lock.rename(snapshot_root / "retained-lock")
        lock.symlink_to("retained-lock")
        symlinked = _run(command, cwd=snapshot_root)
        self.assertNotEqual(symlinked.returncode, 0)
        self.assertIn("cannot use a symlink", symlinked.stderr)

    def test_current_candidate_validation_refuses_stale_only_files(self) -> None:
        outputs = TEST_ROOT / "products/sbom"
        outputs.mkdir(parents=True)
        (outputs / "stale.prod.cdx.json").write_text('{"components":[]}')
        result = self.make("sbom-summary")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((outputs / "summary.txt").exists())


if __name__ == "__main__":
    unittest.main()
