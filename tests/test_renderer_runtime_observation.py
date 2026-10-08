"""Exercise observed runtime closure without approving startup or a profile."""

import importlib.util
from pathlib import Path
import tempfile
import types
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "bijux_runtime_observation_tests",
    ROOT / "shared/bijux-docs/tooling/security/runtime_fingerprints.py",
)
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class RuntimeObservationTests(unittest.TestCase):
    def setUp(self):
        artifact = ROOT / "artifacts/qualification/runtime-observation"
        artifact.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=artifact)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.installed = self.root / "installed"
        self.installed.mkdir()
        self.stdlib = self.root / "stdlib"
        self.stdlib.mkdir()
        self.executable = self.root / "python"
        self.executable.write_bytes(b"actual-interpreter")
        (self.installed / "owned.py").write_text("value=1\n")
        (self.stdlib / "owned_stdlib.py").write_text("value=1\n")
        self.packages = [{"name": "owned", "files": [{"path": "owned.py"}]}]

    def snapshot(self):
        return runtime.snapshot(
            self.packages,
            roots=[self.installed],
            stdlib=self.stdlib,
            executable=self.executable,
        )

    def test_interpreter_stdlib_physical_sources_and_import_origins_are_observed(self):
        result = self.snapshot()
        self.assertTrue(result["verification_only"])
        self.assertFalse(result["admission_created"])
        self.assertEqual(result["stdlib"]["files_count"], 1)
        self.assertEqual(result["physical_roots"][0]["files_count"], 1)
        self.assertTrue(result["loaded_modules"])
        self.assertEqual(result["physical_roots"][0]["outside_locked_inventory"], [])

    def test_unlisted_importable_code_is_retained_as_an_explicit_review_gap(self):
        (self.installed / "unknown.py").write_text("import unknown")
        result = self.snapshot()
        self.assertEqual(
            result["physical_roots"][0]["outside_locked_inventory"], ["unknown.py"]
        )
        self.assertFalse(result["admission_created"])

    def test_missing_locked_code_is_retained_as_an_explicit_review_gap(self):
        (self.installed / "owned.py").unlink()
        self.assertEqual(
            self.snapshot()["physical_roots"][0]["missing_locked_inventory"],
            ["owned.py"],
        )

    def test_startup_pth_and_customization_are_retained_without_execution(self):
        for name in ("unknown.pth", "sitecustomize.py", "usercustomize.py"):
            (self.installed / name).write_text(
                'raise RuntimeError("never execute startup fixture")'
            )
        result = self.snapshot()
        self.assertEqual(
            {item["path"] for item in result["startup_inputs"]},
            {"unknown.pth", "sitecustomize.py", "usercustomize.py"},
        )
        self.assertFalse(result["admission_created"])

    def test_native_and_stdlib_modifications_change_runtime_fingerprints(self):
        before = self.snapshot()
        (self.installed / "owned.so").write_bytes(b"actual-native")
        after = self.snapshot()
        self.assertNotEqual(before["physical_roots"], after["physical_roots"])
        (self.stdlib / "owned_stdlib.py").write_text("value=2")
        self.assertNotEqual(after["stdlib"], self.snapshot()["stdlib"])

    def test_interpreter_change_is_attributable(self):
        before = self.snapshot()
        self.executable.write_bytes(b"other-interpreter")
        self.assertNotEqual(before["executable"], self.snapshot()["executable"])

    def test_cache_bytes_are_observed_separately_without_source_matching_claim(self):
        cache = self.installed / "__pycache__"
        cache.mkdir()
        (cache / "owned.cpython-test.pyc").write_bytes(b"opaque-cache")
        result = self.snapshot()["physical_roots"][0]
        self.assertEqual(result["files_count"], 1)
        self.assertEqual(result["bytecode_count"], 1)
        self.assertIn("bytecode", result)

    def test_source_fixture_inside_cache_directory_is_not_silently_dropped(self):
        cache = self.installed / "__pycache__"
        cache.mkdir()
        (cache / "example.py").write_text("source=True")
        self.assertIn(
            "__pycache__/example.py",
            {item["path"] for item in self.snapshot()["physical_roots"][0]["files"]},
        )

    def test_directory_symlink_is_visible_as_unresolved_closure(self):
        other = self.root / "other"
        other.mkdir()
        (other / "unowned.py").write_text("value=True")
        (self.installed / "link").symlink_to(other, target_is_directory=True)
        result = self.snapshot()["physical_roots"][0]
        self.assertEqual(result["links"][0]["kind"], "directory")
        self.assertNotIn("link/unowned.py", {item["path"] for item in result["files"]})

    def test_regular_and_broken_file_links_remain_explicit(self):
        (self.installed / "link.py").symlink_to(self.installed / "owned.py")
        (self.installed / "missing.py").symlink_to(self.installed / "absent.py")
        result = self.snapshot()["physical_roots"][0]
        self.assertEqual(len(result["links"]), 2)
        self.assertIn("link.py", {item["path"] for item in result["files"]})
        self.assertNotIn("missing.py", {item["path"] for item in result["files"]})

    def test_external_stdlib_startup_target_is_observed_without_execution(self):
        target = self.root / "external-startup.py"
        target.write_text('raise RuntimeError("never run observed fixture")')
        (self.stdlib / "sitecustomize.py").symlink_to(target)
        result = self.snapshot()
        record = next(item for item in result["startup_inputs"] if item["root"] == "stdlib")
        self.assertEqual(record["resolved_target"], str(target))
        self.assertEqual(record["sha256"], runtime.digest(target.read_bytes()))
        self.assertFalse(result["admission_created"])
        self.assertIn("customization_modules", result["startup_runtime"])

    def test_loaded_external_startup_and_exception_callback_origins_are_retained(self):
        target = self.root / "external-startup.py"
        target.write_text("value=1")
        module = types.ModuleType("sitecustomize")
        module.__file__ = str(target)
        def external_callback(kind, value, trace):
            return None
        apport = types.ModuleType("apport_python_hook")
        apport_target = self.root / "apport-hook.py"
        apport_target.write_text("value=2")
        apport.__file__ = str(apport_target)
        with patch.dict(sys.modules, {"sitecustomize": module, "apport_python_hook": apport}), patch.object(sys, "excepthook", external_callback):
            observed = self.snapshot()["startup_runtime"]
        customizations = {item["module"]: item for item in observed["customization_modules"]}
        self.assertEqual(customizations["sitecustomize"]["origin"],
                         {"root": "outside-observed-runtime", "path": str(target)})
        self.assertEqual(customizations["apport_python_hook"]["origin"],
                         {"root": "outside-observed-runtime", "path": str(apport_target)})
        self.assertFalse(observed["exception_hook_is_interpreter_default"])
        self.assertEqual(observed["exception_hook"]["origin"]["root"], "outside-observed-runtime")

    def test_changed_default_hook_pointer_is_not_reported_as_native_default(self):
        callback=lambda *args:None
        with patch.object(sys,"excepthook",callback), patch.object(sys,"__excepthook__",callback):
            self.assertFalse(self.snapshot()["startup_runtime"]["exception_hook_is_interpreter_default"])

    def test_external_target_content_change_changes_startup_identity(self):
        target = self.root / "external-startup.py"
        target.write_text("value=1")
        (self.stdlib / "sitecustomize.py").symlink_to(target)
        before = self.snapshot()["startup_inputs"]
        target.write_text("value=2")
        self.assertNotEqual(before, self.snapshot()["startup_inputs"])

    def test_target_swap_during_open_is_rejected(self):
        first = self.root / "first.py"
        second = self.root / "second.py"
        first.write_text("value=1")
        second.write_text("value=2")
        link = self.root / "selected.py"
        link.symlink_to(first)
        original = runtime.os.open
        def changed(path, flags):
            link.unlink()
            link.symlink_to(second)
            return original(path, flags)
        with patch.object(runtime.os, "open", side_effect=changed):
            with self.assertRaises(runtime.RuntimeObservationError):
                runtime.file_record(link, "selected.py")

    def test_target_change_after_open_is_rejected(self):
        target = self.root / "external.py"
        target.write_text("value=1")
        original = runtime.os.open
        def changed(path, flags):
            descriptor = original(path, flags)
            target.write_text("value=2")
            return descriptor
        with patch.object(runtime.os, "open", side_effect=changed):
            with self.assertRaises(runtime.RuntimeObservationError):
                runtime.file_record(target, "external.py")

    def test_missing_nonregular_and_oversize_targets_are_rejected(self):
        missing = self.root / "missing.py"
        missing.symlink_to(self.root / "absent.py")
        with self.assertRaises(runtime.RuntimeObservationError):
            runtime.file_record(missing, "missing.py")
        fifo = self.root / "fifo"
        runtime.os.mkfifo(fifo)
        with self.assertRaises(runtime.RuntimeObservationError):
            runtime.file_record(fifo, "fifo")
        large = self.root / "large.py"
        large.write_text("value=1")
        with patch.object(runtime, "MAXIMUM_FILE_BYTES", 2):
            with self.assertRaises(runtime.RuntimeObservationError):
                runtime.file_record(large, "large.py")

    def test_volatile_install_metadata_is_not_executable_source_identity(self):
        folder = self.installed / "owned.dist-info"
        folder.mkdir()
        (folder / "RECORD").write_text("volatile")
        (folder / "METADATA").write_text("owned")
        self.assertEqual(self.snapshot()["physical_roots"][0]["files_count"], 2)

    def test_stdlib_does_not_duplicate_site_packages(self):
        nested = self.stdlib / "site-packages"
        nested.mkdir()
        (nested / "foreign.py").write_text("unused")
        self.assertEqual(self.snapshot()["stdlib"]["files_count"], 1)

    def test_file_and_inventory_bounds_fail_with_actionable_evidence(self):
        with (
            patch.object(runtime, "MAXIMUM_FILE_BYTES", 2),
            self.assertRaises(runtime.RuntimeObservationError),
        ):
            self.snapshot()
        with (
            patch.object(runtime, "MAXIMUM_FILES", 0),
            self.assertRaises(runtime.RuntimeObservationError),
        ):
            self.snapshot()

    def test_missing_or_symlink_root_is_rejected(self):
        with self.assertRaises(runtime.RuntimeObservationError):
            runtime.inventory(self.root / "absent")
        link = self.root / "link"
        link.symlink_to(self.installed, target_is_directory=True)
        with self.assertRaises(runtime.RuntimeObservationError):
            runtime.inventory(link)


if __name__ == "__main__":
    unittest.main()
