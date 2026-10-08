"""Exercise shell schema failures while preserving product-owned capabilities."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "shared/bijux-docs/tooling/configuration/shell_contract.py"
SPEC = importlib.util.spec_from_file_location("bijux_shell_contract", SOURCE)
schema = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(schema)
LINKS = [{"key": "bijux-core", "label": "Core", "url": "https://bijux.io/bijux-core/"},
         {"key": "bijux-atlas", "label": "Atlas", "url": "https://bijux.io/bijux-atlas/"}]


class ShellSchemaTests(unittest.TestCase):
    def root(self, **fields):
        return {"extra": {"bijux": {"repository": "bijux-phylogenetics-dev", **fields}}}

    def shared(self, **fields):
        return {"extra": {"bijux": {"nav_mode": "default", "theme_key": "bijux:theme", "hub_links": copy.deepcopy(LINKS), **fields}}}

    def test_product_identity_need_not_be_registry_membership(self):
        self.assertEqual(schema.validate_settings(self.root(), "root.yml", "root")["repository"], "bijux-phylogenetics-dev")

    def test_product_capabilities_and_unknown_options_remain_byte_equivalent_objects(self):
        config = self.root(author_component={"mode": "dense", "labels": ["a", "b"]})
        config.update(hooks=["docs/hooks/content.py"], plugins=[{"redirects": {"redirect_maps": {"old.md": "new.md"}}}], theme={"custom_dir": "docs/overrides"})
        before = copy.deepcopy(config)
        schema.validate_settings(config, "root.yml", "root")
        self.assertEqual(config, before)

    def test_invalid_namespace_shapes_report_source_and_field(self):
        for config, field in ((True, "configuration"), ([], "configuration"), ({"extra": []}, "extra"), ({"extra": {"bijux": "compact"}}, "extra.bijux")):
            with self.subTest(field=field, config=config), self.assertRaisesRegex(RuntimeError, "root.yml: " + field + " must be a mapping"):
                schema.validate_settings(config, "root.yml", "root")

    def test_missing_and_nonstring_repository_are_rejected(self):
        for value in (None, True, 7, [], "", " ", "bad/name"):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "root.yml: extra.bijux.repository"):
                schema.validate_settings(self.root(repository=value), "root.yml", "root")

    def test_unknown_mode_and_storage_key_are_rejected(self):
        for fields, field in (({"nav_mode": "phone"}, "nav_mode"), ({"nav_mode": False}, "nav_mode"), ({"theme_key": "product:theme"}, "theme_key")):
            with self.subTest(fields=fields), self.assertRaisesRegex(RuntimeError, "root.yml: extra.bijux." + field):
                schema.validate_settings(self.root(**fields), "root.yml", "root")

    def test_shared_policy_fields_are_required_without_root_defaults(self):
        for field in ("nav_mode", "theme_key", "hub_links"):
            config = self.shared()
            del config["extra"]["bijux"][field]
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "shared.yml: extra.bijux." + field):
                schema.validate_settings(config, "shared.yml", "shared")

    def test_repository_facts_accepts_only_real_booleans(self):
        for value in (True, False):
            schema.validate_settings(self.root(repository_facts=value), "root.yml", "root")
        for value in ("true", "false", 0, 1, None, []):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "repository_facts must be a Boolean"):
                schema.validate_settings(self.root(repository_facts=value), "root.yml", "root")

    def test_root_registry_duplication_remains_prohibited(self):
        with self.assertRaisesRegex(RuntimeError, "must be inherited"):
            schema.validate_settings(self.root(hub_links=LINKS), "root.yml", "root")

    def test_registry_shape_and_required_fields_are_diagnosed(self):
        for value in (None, {}, [], ["not a mapping"], [{"key": 1}], [{"key": "core", "label": False, "url": "https://bijux.io/"}]):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "shared.yml: extra.bijux.hub_links"):
                schema.registry(value, "shared.yml")

    def test_duplicate_registry_key_has_entry_and_key_diagnostic(self):
        with self.assertRaisesRegex(RuntimeError, r"shared.yml: extra.bijux.hub_links\[2\].key 'bijux-core' is duplicated"):
            schema.registry([LINKS[0], LINKS[0]], "shared.yml")

    def test_absolute_url_requires_actual_network_location(self):
        for value in ("http-garbage", "https://", "javascript:alert(1)", "//bijux.io/", "https://user:secret@bijux.io/", "https://bijux.io:bad/", "https://bijux.io/a b", "https://bijux.io/\n"):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, r"hub_links\[1\].url must be an absolute HTTP"):
                schema.registry([{**LINKS[0], "url": value}], "shared.yml")
        schema.registry([{**LINKS[0], "url": "http://127.0.0.1:4173/"}], "local.yml")

    def test_missing_canonical_destination_identifies_required_key(self):
        with self.assertRaisesRegex(RuntimeError, "missing required keys: bijux-atlas"):
            schema.validate_canonical_registry(LINKS[:1], LINKS, "shared.yml")

    def test_registry_order_and_values_cannot_drift(self):
        for value in (LINKS[::-1], [{**LINKS[0], "label": "Changed"}, LINKS[1]]):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "must exactly match"):
                schema.validate_canonical_registry(value, LINKS, "shared.yml")

    def test_hook_shapes_do_not_execute_or_discard_authored_hooks(self):
        for value in ("docs/hooks/content.py", {"docs/hooks/content.py": {}}, [True], [" "], [None]):
            config = self.root()
            config["hooks"] = value
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "root.yml: hooks"):
                schema.validate_settings(config, "root.yml", "root")
        config = self.root()
        config["hooks"] = ["docs/hooks/does-not-exist-yet.py"]
        schema.validate_settings(config, "root.yml", "root")

    def test_effective_input_cannot_hide_missing_product_identity(self):
        config = self.shared()
        with self.assertRaisesRegex(RuntimeError, "repository must be a non-empty string"):
            schema.validate_settings(config, "effective", "effective")
        config["extra"]["bijux"]["repository"] = "bijux-core"
        schema.validate_settings(config, "effective", "effective")

    def test_unknown_validation_role_is_programmer_error(self):
        with self.assertRaisesRegex(ValueError, "Unsupported shell configuration role"):
            schema.validate_settings(self.root(), "root.yml", "consumer")


if __name__ == "__main__":
    unittest.main()
