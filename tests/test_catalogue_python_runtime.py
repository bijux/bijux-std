"""Catalogue verification interpreter ownership and exact recipe controls."""

from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "catalogue_python_runtime", ROOT / "tests/bijux-docs/catalogue/python_runtime.py"
)
recipe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recipe)
ARTIFACTS = ROOT / "artifacts/catalogue-interpreter-controls"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


class CataloguePythonRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ARTIFACTS)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.owner = mock.patch.object(recipe, "ROOT", self.root)
        self.owner.start()
        self.addCleanup(self.owner.stop)
        self.destination = self.root / "artifacts/interpreter"

    def test_existing_interpreter_content_is_preserved(self):
        self.destination.mkdir(parents=True)
        witness = self.destination / "user-source"
        witness.write_text("owned")
        with self.assertRaisesRegex(ValueError, "Preserve existing"):
            recipe.destination(self.destination)
        self.assertEqual(witness.read_text(), "owned")

    def test_destination_outside_artifacts_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "repository artifacts"):
            recipe.destination(self.root / "foreign")

    def test_symlink_destination_is_rejected(self):
        real = self.root / "artifacts/real"
        real.mkdir(parents=True)
        self.destination.symlink_to(real, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "ordinary directories"):
            recipe.destination(self.destination)

    def test_alternate_download_authority_is_rejected_even_when_empty(self):
        for name in ("UV_PYTHON_DOWNLOADS_JSON_URL", "UV_PYTHON_INSTALL_MIRROR"):
            with (
                self.subTest(name=name),
                mock.patch.dict(recipe.os.environ, {name: ""}),
            ):
                with self.assertRaisesRegex(ValueError, "download authorities"):
                    recipe.install(self.destination, "uv")
        self.assertFalse(self.destination.exists())

    def test_wrong_installer_version_is_rejected_before_mutation(self):
        with mock.patch.object(
            recipe.subprocess, "run", return_value=mock.Mock(stdout="uv 0.11.18")
        ):
            with self.assertRaisesRegex(ValueError, "uv 0.11.17"):
                recipe.install(self.destination, "uv")
        self.assertFalse(self.destination.exists())

    def interpreter(self):
        self.destination.mkdir(parents=True)
        executable = self.destination / "python"
        executable.write_bytes(b"controlled interpreter identity")
        return executable

    def description(self, executable):
        return {
            "version": [3, 14, 4],
            "implementation": "cpython",
            "prefix": str(self.destination),
            "base_prefix": str(self.destination),
            "executable": str(executable),
        }

    def test_selected_interpreter_escape_is_rejected(self):
        executable = self.root / "foreign-python"
        executable.write_bytes(b"foreign")
        with self.assertRaisesRegex(ValueError, "escaped"):
            recipe.observe(executable, self.destination)

    def test_wrong_runtime_or_prefix_is_rejected(self):
        executable = self.interpreter()
        for key, value, message in (
            ("version", [3, 14, 3], "exact CPython"),
            ("implementation", "pypy", "exact CPython"),
            ("prefix", str(self.root), "standalone recipe"),
            ("base_prefix", str(self.root), "standalone recipe"),
            ("executable", str(self.root / "other-python"), "standalone recipe"),
        ):
            with self.subTest(field=key):
                description = {**self.description(executable), key: value}
                with mock.patch.object(
                    recipe.subprocess,
                    "run",
                    return_value=mock.Mock(stdout=json.dumps(description)),
                ):
                    with self.assertRaisesRegex(ValueError, message):
                        recipe.observe(executable, self.destination)

    def test_owned_exact_descriptor_remains_verification_only(self):
        executable = self.interpreter()
        with mock.patch.object(
            recipe.subprocess,
            "run",
            return_value=mock.Mock(stdout=json.dumps(self.description(executable))),
        ):
            actual = recipe.observe(executable, self.destination)
        self.assertTrue(actual["verification_only"])
        self.assertFalse(actual["publication_approval"])
        self.assertEqual(len(actual["executable_sha256"]), 64)
