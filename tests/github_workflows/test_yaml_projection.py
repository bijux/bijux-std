from __future__ import annotations
import copy
import importlib.util
import json
import os
import py_compile
import tempfile
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock
from .policy_fixtures import ROOT, MODULE, INVENTORY, POLICY, manifest


class CanonicalYamlProjectionTests(unittest.TestCase):
    def test_same_root_changed_source_and_forged_cache_cannot_select_old_schema(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            scripts = root / ".github/scripts"
            scripts.mkdir(parents=True)
            shutil.copyfile(ROOT / ".github/scripts/render_repo_configs.py", scripts / "render_repo_configs.py")
            shutil.copytree(ROOT / ".github/scripts/workflow_execution", scripts / "workflow_execution")
            (root / "shared/bijux-gh").mkdir(parents=True)
            def load():
                spec = importlib.util.spec_from_file_location("bijux_same_root_renderer", scripts / "render_repo_configs.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module.WORKFLOW_EXECUTION
            first = load()
            sys.modules[first.__name__ + ".schema"].PUBLICATION_ENTRYPOINTS = frozenset()
            refreshed = load()
            self.assertEqual(refreshed.validate_manifest(manifest(), ["bijux-atlas"])["bijux-atlas"], POLICY)
            path = scripts / "workflow_execution/schema.py"
            path.write_text(path.read_text() + "\nPUBLICATION_ENTRYPOINTS = frozenset()\n")
            changed = load()
            self.assertNotEqual(changed.__name__, refreshed.__name__)
            with self.assertRaisesRegex(ValueError, "unknown fields"):
                changed.validate_manifest(manifest(), ["bijux-atlas"])

    def test_changed_schema_executes_exact_bytes_despite_timestamp_valid_bytecode(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            scripts = root / ".github/scripts"
            scripts.mkdir(parents=True)
            shutil.copyfile(ROOT / ".github/scripts/render_repo_configs.py", scripts / "render_repo_configs.py")
            shutil.copytree(ROOT / ".github/scripts/workflow_execution", scripts / "workflow_execution")
            (root / "shared/bijux-gh").mkdir(parents=True)
            schema = scripts / "workflow_execution/schema.py"
            original = schema.read_bytes()
            changed = original.replace(b'"release-github"', b'"release-githux"')
            self.assertNotEqual(changed, original)
            self.assertEqual(len(changed), len(original))
            original_stat = schema.stat()
            cache = Path(py_compile.compile(str(schema), doraise=True))
            bytecode = cache.read_bytes()
            schema.write_bytes(changed)
            os.utime(schema, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            self.assertEqual(schema.stat().st_mtime_ns, original_stat.st_mtime_ns)
            spec = importlib.util.spec_from_file_location("bijux_timestamp_renderer", scripts / "render_repo_configs.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            owned_schema = sys.modules[module.WORKFLOW_EXECUTION.__name__ + ".schema"]
            self.assertIn("release-githux", owned_schema.PUBLICATION_ENTRYPOINTS)
            self.assertNotIn("release-github", owned_schema.PUBLICATION_ENTRYPOINTS)
            self.assertEqual(cache.read_bytes(), bytecode)
            with self.assertRaisesRegex(ValueError, "unknown fields"):
                module.WORKFLOW_EXECUTION.validate_manifest(manifest(), ["bijux-atlas"])

    def test_loader_bootstrap_uses_exact_changed_bytes_and_source_identity(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            scripts = root / ".github/scripts"
            scripts.mkdir(parents=True)
            shutil.copyfile(ROOT / ".github/scripts/render_repo_configs.py", scripts / "render_repo_configs.py")
            shutil.copytree(ROOT / ".github/scripts/workflow_execution", scripts / "workflow_execution")
            (root / "shared/bijux-gh").mkdir(parents=True)
            loader = scripts / "workflow_execution/source_loading.py"
            original = loader.read_bytes()
            changed = original.replace(b'bijux_workflow_execution_', b'bijux_workflow_executiox_')
            self.assertNotEqual(original, changed)
            self.assertEqual(len(original), len(changed))
            original_stat = loader.stat()
            cache = Path(py_compile.compile(str(loader), doraise=True))
            bytecode = cache.read_bytes()
            def load():
                spec = importlib.util.spec_from_file_location("bijux_bootstrap_renderer", scripts / "render_repo_configs.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module.WORKFLOW_EXECUTION
            first = load()
            loader.write_bytes(changed)
            os.utime(loader, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            refreshed = load()
            self.assertTrue(refreshed.__name__.startswith("bijux_workflow_executiox_"))
            self.assertNotEqual(first.__name__.split("_")[-1], refreshed.__name__.split("_")[-1])
            self.assertEqual(cache.read_bytes(), bytecode)
            self.assertEqual(refreshed.validate_manifest(manifest(), ["bijux-atlas"])["bijux-atlas"], POLICY)

    def test_workflow_parser_preserves_mapping_key_spelling(self):
        document = MODULE.parse_workflow(b"on: [pull_request, workflow_dispatch]\njobs:\n  owned:\n    env:\n      on: spelling\n      'true': distinct\n", "owned.yml")
        self.assertEqual(document["on"], ["pull_request", "workflow_dispatch"])
        self.assertEqual(document["jobs"]["owned"]["env"], {"on": "spelling", "true": "distinct"})

    def test_workflow_parser_refuses_duplicate_alias_multidocument_and_boolean_collisions(self):
        for source in [
            b"on: push\non: workflow_dispatch\njobs: {}\n",
            b"on: workflow_dispatch\njobs:\n  owned: {}\n  owned: {}\n",
            b"on: &events [pull_request]\njobs: {owned: *events}\n",
            b"on: push\njobs: {}\n---\non: workflow_dispatch\njobs: {}\n",
            b"on: push\ntrue: workflow_dispatch\njobs: {}\n",
            b"on: workflow_dispatch\njobs: []\n",
        ]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                MODULE.parse_workflow(source, "owned.yml")

    def test_missing_parser_has_actionable_prerequisite_failure(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("ruby")):
            with self.assertRaisesRegex(RuntimeError, "ruby is required"):
                MODULE.parse_workflow(b"on: workflow_dispatch\njobs: {}\n", "owned.yml")

    def test_adjacent_helper_is_not_reused_from_another_canonical_root(self):
        with tempfile.TemporaryDirectory() as workspace:
            helpers = []
            for name in ["owned-standard", "independent-standard"]:
                root = Path(workspace) / name
                scripts = root / ".github/scripts"
                scripts.mkdir(parents=True)
                for filename in ["render_repo_configs.py"]:
                    shutil.copyfile(ROOT / ".github/scripts" / filename, scripts / filename)
                shutil.copytree(ROOT / ".github/scripts/workflow_execution", scripts / "workflow_execution")
                (root / "shared/bijux-gh").mkdir(parents=True)
                spec = importlib.util.spec_from_file_location("bijux_independent_renderer", scripts / "render_repo_configs.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.assertEqual(Path(module.WORKFLOW_EXECUTION.__file__).resolve(), (scripts / "workflow_execution/__init__.py").resolve())
                helpers.append(module.WORKFLOW_EXECUTION)
            self.assertIsNot(helpers[0], helpers[1])
            sys.modules[helpers[0].__name__ + ".schema"].PUBLICATION_ENTRYPOINTS = frozenset()
            self.assertEqual(helpers[1].validate_manifest(manifest(), ["bijux-atlas"])["bijux-atlas"], POLICY)


if __name__ == "__main__":
    unittest.main()
