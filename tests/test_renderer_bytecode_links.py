"""Bytecode admission shares physical source ownership without approving a profile."""
import importlib.util
import marshal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "bijux_bytecode_links", ROOT / "shared/bijux-docs/security/renderer_profiles.py"
)
profiles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profiles)


class BytecodeSourceLinkTests(unittest.TestCase):
    def setUp(self):
        artifact = ROOT / "artifacts/qualification/renderer-bytecode-links"
        artifact.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=artifact)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.base = self.root / "interpreter"
        self.stdlib = self.base / "stdlib"
        self.stdlib.mkdir(parents=True)
        self.external = self.root / "distro"
        self.external.mkdir()
        for name, value in [("base_prefix", str(self.base)), ("pycache_prefix", None)]:
            context = patch.object(profiles.sys, name, value)
            context.start()
            self.addCleanup(context.stop)

    def link(self, name="sitecustomize.py", *, internal=False):
        target = (self.base if internal else self.external) / "startup.py"
        target.write_text("def startup():\n    return 1\n")
        source = self.stdlib / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.symlink_to(target)
        return source, target, self.cache(source)

    def cache(self, source, *, code=None):
        cache = Path(importlib.util.cache_from_source(str(source)))
        cache.parent.mkdir(parents=True, exist_ok=True)
        compiled = compile(source.read_bytes() if code is None else code, str(source), "exec")
        cache.write_bytes(importlib.util.MAGIC_NUMBER + bytes(12) + marshal.dumps(compiled))
        return cache

    def physical(self, *, stdlib=True):
        return profiles.physical_files(self.stdlib, stdlib=stdlib)

    def test_external_typed_startup_cache_matches_exact_linked_source(self):
        source, target, cache = self.link()
        records = self.physical()
        self.assertEqual(records, [{"path": source.name, "sha256": profiles.digest(target.read_bytes()),
                                    "external_startup_target": str(target.resolve())}])
        self.assertTrue(cache.is_file())

    def test_base_interpreter_link_cache_matches_exact_owned_source(self):
        source, target, _ = self.link("owned.py", internal=True)
        records = self.physical()
        self.assertEqual(records[0]["base_interpreter_link"], target.relative_to(self.base).as_posix())
        self.assertEqual(records[0]["path"], source.name)

    def test_external_other_module_link_is_rejected(self):
        _, _, cache = self.link("unreviewed.py")
        self.assertRaisesRegex(profiles.ProfileError, "typed startup", self.physical)
        self.assertRaisesRegex(profiles.ProfileError, "typed startup", profiles.validate_bytecode, cache, root=self.stdlib, stdlib=True)

    def test_nested_external_startup_link_is_rejected(self):
        _, _, cache = self.link("nested/sitecustomize.py")
        self.assertRaisesRegex(profiles.ProfileError, "typed startup", self.physical)
        self.assertRaisesRegex(profiles.ProfileError, "typed startup", profiles.validate_bytecode, cache, root=self.stdlib, stdlib=True)

    def test_nonstdlib_startup_source_link_is_rejected(self):
        _, _, cache = self.link()
        self.assertRaisesRegex(profiles.ProfileError, "installed runtime symlink", self.physical, stdlib=False)
        self.assertRaisesRegex(profiles.ProfileError, "installed runtime symlink", profiles.validate_bytecode, cache, root=self.stdlib, stdlib=False)

    def test_unscoped_direct_bytecode_validation_cannot_admit_source_link(self):
        _, _, cache = self.link()
        self.assertRaisesRegex(profiles.ProfileError, "source link.*owned stdlib", profiles.validate_bytecode, cache)

    def test_orphan_bytecode_names_actual_cache_and_source(self):
        source, _, cache = self.link()
        source.unlink()
        with self.assertRaises(profiles.ProfileError) as caught:
            self.physical()
        self.assertIn(str(cache), str(caught.exception))
        self.assertIn(str(source), str(caught.exception))
        self.assertIn("bytecode source missing", str(caught.exception))

    def test_linked_source_change_invalidates_executable_cache(self):
        _, target, _ = self.link()
        target.write_text("def startup():\n    return 2\n")
        self.assertRaisesRegex(profiles.ProfileError, "bytecode differs", self.physical)

    def test_mutated_cache_invalidates_unchanged_linked_source(self):
        source, _, _ = self.link()
        self.cache(source, code="def startup():\n    return 2\n")
        self.assertRaisesRegex(profiles.ProfileError, "bytecode differs", self.physical)

    def test_bytecode_link_remains_forbidden(self):
        _, _, cache = self.link()
        payload = self.external / "executable.pyc"
        cache.rename(payload)
        cache.symlink_to(payload)
        self.assertRaisesRegex(profiles.ProfileError, "unowned bytecode", self.physical)


if __name__ == "__main__":
    unittest.main()
