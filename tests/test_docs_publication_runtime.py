"""Publication bootstrap rejects ambient runtimes and unsafe artifact ownership."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared/bijux-docs"


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, SHARED / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load("bijux_install_publication_test", "tooling/security/install_publication_renderer.py")
builder = load("bijux_publication_builder_test", "tooling/security/publication_builder.py")


class PublicationRuntime(unittest.TestCase):
    def setUp(self):
        directory = ROOT / "artifacts/publication-runtime-tests"
        directory.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=directory)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)

    def test_artifact_paths_reject_escape_normalization_and_absolute_owners(self):
        for name in ("source/venv", "artifacts/../venv", "/artifacts/venv", "artifacts//venv", "artifacts/./venv"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                installer.owned_directory(self.root, name)

    def test_absolute_standard_outside_owner_is_rejected(self):
        options = argparse.Namespace(standard_root="/outside/accepted-standard")
        with self.assertRaisesRegex(ValueError, "consumer artifacts"):
            builder.arguments("capture", options, "a" * 40)

    def test_existing_renderer_is_preserved(self):
        path = self.root / "artifacts/renderer"
        path.mkdir(parents=True)
        (path / "retained").write_text("last qualified producer")
        with self.assertRaises(ValueError):
            installer.owned_directory(self.root, "artifacts/renderer")
        self.assertEqual((path / "retained").read_text(), "last qualified producer")

    def test_symlink_artifact_owner_is_rejected(self):
        (self.root / "other").mkdir()
        (self.root / "artifacts").symlink_to(self.root / "other", target_is_directory=True)
        with self.assertRaises(ValueError):
            installer.owned_directory(self.root, "artifacts/renderer")

    def test_wrong_interpreter_refuses_before_creating_destination(self):
        for probe in ('["Darwin","arm64","3.11.17","cpython"]',
                      '["Linux","x86_64","3.11.18","cpython"]',
                      '["Linux","x86_64","3.11.17","pypy"]'):
            with self.subTest(probe=probe), patch.object(installer.subprocess, "check_output", return_value=probe):
                with self.assertRaises(ValueError):
                    installer.install(self.root, "history", "python", "artifacts/renderer")
            self.assertFalse((self.root / "artifacts/renderer").exists())

    def test_pinned_installer_accepts_its_observed_platform_build_metadata(self):
        class HaltBeforeEnvironment(Exception):
            pass
        with patch.object(installer.subprocess, "check_output", side_effect=[
                '["Linux","x86_64","3.11.17","cpython"]', "uv 0.11.17 (x86_64-unknown-linux-gnu)"]), \
                patch.object(installer.subprocess, "run", side_effect=HaltBeforeEnvironment):
            with self.assertRaises(HaltBeforeEnvironment):
                installer.install(self.root, "history", "python", "artifacts/renderer")

    def test_wrong_installer_refuses_before_creating_destination(self):
        with patch.object(installer.subprocess, "check_output", side_effect=[
                '["Linux","x86_64","3.11.17","cpython"]', "uv 0.11.18"]):
            with self.assertRaises(ValueError):
                installer.install(self.root, "history", "python", "artifacts/renderer")
        self.assertFalse((self.root / "artifacts/renderer").exists())

    def local_wheel_cache(self):
        renderer = self.root / "artifacts/renderer/bin/python"
        wheels = self.root / "artifacts/wheels"
        wheels.mkdir(parents=True)
        site = renderer.parent.parent / "lib/python3.11/site-packages"
        for distribution, version in (("csscompressor", "0.9.5"), ("jsmin", "3.0.1")):
            wheel = wheels / f"{distribution}-{version}-py3-none-any.whl"
            wheel.write_bytes(b"reviewed fixture archive")
            metadata = site / f"{distribution}-{version}.dist-info"
            metadata.mkdir(parents=True)
            stamp = wheel.stat().st_mtime_ns
            cache = metadata / "uv_cache.json"
            cache.write_text(json.dumps({"timestamp": {"secs_since_epoch": stamp // 1_000_000_000,
                "nanos_since_epoch": stamp % 1_000_000_000}, "commit": None, "tags": None, "env": {}, "directories": {}}))
            (metadata / "METADATA").write_text("retained reviewed package source")
            data = cache.read_bytes()
            digest = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
            with (metadata / "RECORD").open("w", newline="") as output:
                csv.writer(output).writerows([[cache.relative_to(site).as_posix(), digest, str(len(data))],
                    [(metadata / "METADATA").relative_to(site).as_posix(), "retained", "32"]])
        return renderer, wheels, site

    def test_local_wheel_clock_bookkeeping_is_removed_without_changing_package_bytes(self):
        renderer, wheels, site = self.local_wheel_cache()
        installer.normalize_local_wheel_metadata(renderer, wheels)
        self.assertEqual(list(site.glob("*.dist-info/uv_cache.json")), [])
        for path in site.glob("*.dist-info/METADATA"):
            self.assertEqual(path.read_text(), "retained reviewed package source")
            self.assertNotIn("uv_cache.json", (path.parent / "RECORD").read_text())

    def test_unknown_local_cache_fields_refuse_normalization(self):
        renderer, wheels, site = self.local_wheel_cache()
        cache = site / "csscompressor-0.9.5.dist-info/uv_cache.json"
        data = json.loads(cache.read_text()); data["callback"] = "unreviewed"
        cache.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "bookkeeping"):
            installer.normalize_local_wheel_metadata(renderer, wheels)
        self.assertTrue(cache.exists())

    def test_local_cache_record_tampering_refuses_normalization(self):
        renderer, wheels, site = self.local_wheel_cache()
        record = site / "csscompressor-0.9.5.dist-info/RECORD"
        record.write_text(record.read_text().replace("sha256=", "unknown="))
        with self.assertRaisesRegex(ValueError, "RECORD identity"):
            installer.normalize_local_wheel_metadata(renderer, wheels)
        self.assertTrue((record.parent / "uv_cache.json").exists())

    def test_linked_local_cache_refuses_normalization(self):
        renderer, wheels, site = self.local_wheel_cache()
        cache = site / "csscompressor-0.9.5.dist-info/uv_cache.json"
        moved = cache.with_name("retained.json"); cache.rename(moved); cache.symlink_to(moved)
        with self.assertRaisesRegex(ValueError, "regular owned"):
            installer.normalize_local_wheel_metadata(renderer, wheels)
        self.assertTrue(moved.is_file())

    def test_capture_requires_independent_accepted_source(self):
        options = argparse.Namespace(standard_root=None)
        with patch.dict(builder.os.environ, {}, clear=True), self.assertRaises(ValueError):
            builder.arguments("capture", options, "a" * 40)

    def test_capture_retains_exact_commands_as_data_and_source_recipe(self):
        options = argparse.Namespace(standard_root="artifacts/accepted-standard", config="mkdocs.yml",
            site_dir="artifacts/docs/site", site_url="https://bijux.io/bijux-core/", build_command="make gh-docs-build",
            verify_command="make gh-docs-verify", source_recipe="masterclass-catalogue")
        result = builder.arguments("capture", options, "a" * 40)
        self.assertEqual(result[0], str(SHARED / "security/build_identity.py"))
        for flag, value in (("--source-sha", "a" * 40), ("--standard-root", options.standard_root),
                            ("--build-command", options.build_command), ("--verify-command", options.verify_command),
                            ("--source-recipe", options.source_recipe)):
            self.assertEqual(result[result.index(flag) + 1], value)
        self.assertEqual(result[-2:], ["--source-recipe", "masterclass-catalogue"])

    def test_verification_requires_reconstructed_qualified_manifest(self):
        result = builder.arguments("verify", argparse.Namespace(), "a" * 40)
        self.assertEqual(result, [str(SHARED / "security/publication.py"), "verify", "--manifest",
                                 "artifacts/website-security/publication.json", "--require-qualified"])
        self.assertNotIn("--bytes-only", result)

    def test_unknown_builder_operation_cannot_select_another_executable(self):
        with self.assertRaises(ValueError):
            builder.arguments("arbitrary", argparse.Namespace(), "a" * 40)


if __name__ == "__main__":
    unittest.main()
