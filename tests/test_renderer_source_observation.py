"""Exercise observation boundaries without inventing hosted renderer admission."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "shared/bijux-docs/tooling/security/renderer_fingerprints.py"
spec = importlib.util.spec_from_file_location("bijux_renderer_observation", SOURCE)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


class Distribution:
    def __init__(self, root, *, version="1.0", name="sample"):
        self.root = root
        self.version = version
        self.metadata = {"Name": name}
        self.files = [PurePosixPath("sample/__init__.py"), PurePosixPath("sample/native.so"),
                      PurePosixPath("sample-1.0.dist-info/METADATA"),
                      PurePosixPath("sample-1.0.dist-info/RECORD"),
                      PurePosixPath("../../../bin/sample")]
        for name, value in (("sample/__init__.py", b"value = 1\n"), ("sample/native.so", b"native-code"),
                            ("sample-1.0.dist-info/METADATA", b"Name: sample\nVersion: 1.0\n"),
                            ("sample-1.0.dist-info/RECORD", b"install-state")):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)

    def locate_file(self, file):
        return self.root / str(file)


class RendererObservationTests(unittest.TestCase):
    def setUp(self):
        artifact = Path(os.environ.get("BIJUX_TEST_ARTIFACTS", ROOT / "artifacts/qualification/renderer-source-observation"))
        artifact.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix="source-observation-", dir=artifact)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.distribution = Distribution(self.root / "installed")

    def packages(self):
        return observer.observe_packages(b"sample==1.0\n", lambda _: self.distribution)

    def test_source_and_native_code_are_observed_but_install_records_are_excluded(self):
        records = self.packages()[0]["files"]
        self.assertEqual({r["path"] for r in records}, {
            "sample/__init__.py", "sample/native.so", "sample-1.0.dist-info/METADATA"})
        self.assertTrue(all(len(record["sha256"]) == 64 for record in records))

    def test_changed_code_and_native_payload_change_the_observed_profile(self):
        before = self.packages()
        (self.distribution.root / "sample/native.so").write_bytes(b"different-native")
        self.assertNotEqual(before, self.packages())
        (self.distribution.root / "sample/__init__.py").write_bytes(b"different-source")
        self.assertNotEqual(before, self.packages())

    def test_lock_rejects_ranges_urls_duplicates_and_empty_inventory(self):
        for lock in (b"sample>=1\n", b"sample @ https://example.org/pkg\n",
                     b"foo-bar==1\nFOO_bar==1\n", b"# empty\n", b"sample==1 --hash=sha256:abc\n"):
            with self.subTest(lock=lock), self.assertRaises(observer.ObservationError):
                observer.locked_packages(lock)

    def test_locked_version_and_package_identity_are_required(self):
        for field, value in (("version", "1.1"), ("metadata", {"Name": "foreign"})):
            original = getattr(self.distribution, field)
            setattr(self.distribution, field, value)
            with self.subTest(field=field), self.assertRaises(observer.ObservationError):
                self.packages()
            setattr(self.distribution, field, original)

    def test_missing_record_and_symlink_inputs_fail(self):
        path = self.distribution.root / "sample/native.so"
        path.unlink()
        with self.assertRaises(observer.ObservationError):
            self.packages()
        path.symlink_to(self.distribution.root / "sample/__init__.py")
        with self.assertRaises(observer.ObservationError):
            self.packages()

    def test_missing_distribution_inventory_and_package_fail(self):
        self.distribution.files = None
        with self.assertRaises(observer.ObservationError):
            self.packages()
        def missing(name):
            raise observer.importlib.metadata.PackageNotFoundError(name)
        with self.assertRaisesRegex(observer.ObservationError, "not installed"):
            observer.observe_packages(b"sample==1.0\n", missing)

    def test_duplicate_and_unknown_escape_paths_fail(self):
        original = list(self.distribution.files)
        for record in ("sample/native.so", "../../../etc/passwd", "/outside.py", "sample//unknown.py"):
            self.distribution.files = original + [PurePosixPath(record) if "//" not in record else record]
            with self.subTest(record=record), self.assertRaises(observer.ObservationError):
                self.packages()

    def test_output_confinement_and_existing_observation_preservation(self):
        for value in ("docs/site/report.json", "artifacts/../outside.json", "/outside.json", "artifacts", "artifacts//report.json"):
            with self.subTest(value=value), self.assertRaises(observer.ObservationError):
                observer.output_path(self.root, value)
        output = observer.output_path(self.root, "artifacts/report.json")
        output.parent.mkdir()
        output.write_text("existing")
        with self.assertRaises(observer.ObservationError):
            observer.output_path(self.root, "artifacts/report.json")
        self.assertEqual(output.read_text(), "existing")
        (output.parent / "link").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(observer.ObservationError):
            observer.output_path(self.root, "artifacts/link/report.json")

    def test_source_checkpoint_rejects_dirty_or_changed_committed_input(self):
        def git(root, *arguments):
            if arguments[:2] == ("rev-parse", "--show-toplevel"):
                return str(root)
            if arguments[0] == "status":
                return " M makes/bijux-docs.mk"
            return "a" * 40
        with patch.object(observer, "git", git), self.assertRaisesRegex(observer.ObservationError, "clean"):
            observer.source_snapshot(self.root)
        for name in observer.SOURCE_PATHS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"committed")
        with patch.object(observer, "git", lambda root, *args: str(root) if args[-1] == "--show-toplevel" else ""), \
             patch.object(observer.subprocess, "check_output", return_value=b"different"), \
             self.assertRaisesRegex(observer.ObservationError, "committed"):
            observer.source_snapshot(self.root)

    def observe_fixture(self, package_captures=None, sources=None, runtimes=None):
        path = self.root / observer.SOURCE_PATHS[1]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"sample==1.0\n")
        captures = package_captures or [self.packages(), self.packages()]
        snapshots = sources or [{"sha": "a" * 40}, {"sha": "a" * 40}]
        with patch.object(observer, "__file__", str(self.root / observer.SOURCE_PATHS[0])), \
             patch.object(observer, "source_snapshot", side_effect=snapshots), \
             patch.object(observer, "observe_packages", side_effect=captures), \
             patch.object(observer, "runtime_snapshot", side_effect=runtimes or [{"verification_only": True}, {"verification_only": True}]):
            return observer.observe(self.root)

    def test_source_and_dependency_races_fail_before_report_creation(self):
        altered = self.packages()
        altered[0]["files_sha256"] = "b" * 64
        with self.assertRaisesRegex(observer.ObservationError, "Installed renderer changed"):
            self.observe_fixture([self.packages(), altered])
        with self.assertRaisesRegex(observer.ObservationError, "Source changed"):
            self.observe_fixture(sources=[{"sha": "a" * 40}, {"sha": "b" * 40}])
        self.assertFalse((self.root / "artifacts").exists())

    def test_runtime_race_is_rejected_before_report_creation(self):
        with self.assertRaisesRegex(observer.ObservationError, "Physical renderer runtime changed"):
            self.observe_fixture(runtimes=[{"sha256": "a" * 64}, {"sha256": "b" * 64}])
        self.assertFalse((self.root / "artifacts").exists())

    def test_genuine_observation_never_admits_profile_or_uses_receipt_authority(self):
        report = self.observe_fixture()
        self.assertFalse(report["admission_created"])
        self.assertTrue(report["verification_only"])
        self.assertEqual(report["packages"][0]["version"], "1.0")
        self.assertEqual(report["source"]["sha"], "a" * 40)
        self.assertNotIn("accepted", report)
        json.dumps(report)


if __name__ == "__main__":
    unittest.main()
