"""Per-capture distribution ownership remains strict across reused module inventories."""
from pathlib import Path
import importlib.util
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bijux_distribution_origin_controls", ROOT / "shared/bijux-docs/security/renderer_profiles.py")
profiles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profiles)
ARTIFACTS = ROOT / "artifacts/distribution-origin-controls"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


class DistributionMembershipTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(dir=ARTIFACTS)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.installed = self.root / "installed"
        self.stdlib = self.root / "stdlib"
        self.installed.mkdir()
        self.stdlib.mkdir()
        self.modules = {}
        self.owners = {}
        self.distributions = {}
        self.calls = []
        for name, owner in (("mkdocs", "mkdocs"), ("material", "mkdocs-material"), ("jinja2", "Jinja2"), ("yaml", "PyYAML")):
            self.module(name, owner)
        owned_sys = types.SimpleNamespace(path=[], modules=self.modules, stdlib_module_names={"json"})
        for patcher in (
            mock.patch.object(profiles, "sys", owned_sys),
            mock.patch.object(profiles.sysconfig, "get_path", side_effect=lambda name: str(self.stdlib if name == "stdlib" else self.installed)),
            mock.patch.object(profiles.metadata, "packages_distributions", return_value=self.owners),
            mock.patch.object(profiles.metadata, "distribution", side_effect=self.distribution),
            mock.patch.object(profiles, "__import__", side_effect=lambda name: self.modules[name], create=True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def module(self, name, owner):
        relative = Path(name.replace(".", "/") + ".py")
        path = self.installed / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("owned = True\n")
        module = types.ModuleType(name)
        module.__file__ = str(path)
        self.modules[name] = module
        self.owners.setdefault(name.split(".")[0], [owner])
        if owner not in self.distributions:
            self.distributions[owner] = types.SimpleNamespace(files=[], locate_file=lambda item: self.installed / str(item))
        self.distributions[owner].files.append(relative)
        return module

    def distribution(self, owner):
        self.calls.append(owner)
        return self.distributions[owner]

    def capture(self):
        profiles.origins(self.root, self.root / "shared", publication=True)

    def test_many_loaded_modules_resolve_each_distribution_once(self):
        for index in range(12):
            self.module("sample.part" + str(index), "sample")
        self.capture()
        self.assertCountEqual(self.calls, ["mkdocs", "mkdocs-material", "Jinja2", "PyYAML", "sample"])

    def test_later_capture_rechecks_changed_distribution_inventory(self):
        self.capture()
        self.distributions["mkdocs"].files.clear()
        with self.assertRaisesRegex(profiles.ProfileError, "namespace is shadowed"):
            self.capture()
        self.assertEqual(self.calls.count("mkdocs"), 2)

    def test_unlisted_loaded_module_is_rejected(self):
        module = self.module("sample.extra", "sample")
        self.distributions["sample"].files.clear()
        with self.assertRaisesRegex(profiles.ProfileError, "namespace is shadowed"):
            self.capture()
        self.assertTrue(Path(module.__file__).is_file())

    def test_producer_distribution_outside_installed_root_is_rejected(self):
        self.distributions["mkdocs"].locate_file = lambda item: self.root / str(item)
        with self.assertRaisesRegex(profiles.ProfileError, "namespace is shadowed"):
            self.capture()

    def test_standard_library_namespace_shadow_is_rejected(self):
        self.module("json", "sample")
        with self.assertRaisesRegex(profiles.ProfileError, "standard library import is shadowed"):
            self.capture()

    def test_reviewed_requests_alias_keeps_actual_distribution_owner(self):
        module = self.module("urllib3", "urllib3")
        self.modules["requests.packages.urllib3"] = module
        self.capture()
        self.assertEqual(self.calls.count("urllib3"), 1)

    def test_unknown_requests_alias_is_rejected(self):
        module = self.module("sample", "sample")
        self.modules["requests.packages.sample"] = module
        with self.assertRaisesRegex(profiles.ProfileError, "unknown requests dependency alias"):
            self.capture()

    def test_parent_traversal_inventory_cannot_admit_module(self):
        module = self.module("sample", "sample")
        self.distributions["sample"].files[:] = [Path("../installed/sample.py")]
        with self.assertRaisesRegex(profiles.ProfileError, "namespace is shadowed"):
            self.capture()
        self.assertTrue(Path(module.__file__).is_file())

    def test_shared_namespace_retains_all_declared_distribution_owners(self):
        self.module("sample.first", "first")
        self.module("sample.second", "second")
        self.owners["sample"] = ["first", "second"]
        self.capture()
        self.assertEqual(self.calls.count("first"), 1)
        self.assertEqual(self.calls.count("second"), 1)

    def test_later_capture_rechecks_rebound_module_path(self):
        module = self.module("sample", "sample")
        self.capture()
        module.__file__ = str(self.root / "unowned.py")
        with self.assertRaisesRegex(profiles.ProfileError, "namespace is shadowed"):
            self.capture()
