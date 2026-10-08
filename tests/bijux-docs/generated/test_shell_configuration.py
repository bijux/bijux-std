"""Exercise diagnostics through the actual YAML loader and validator boundary."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "shared/bijux-docs/tooling/quality/validate_bijux_docs_contract.py"
SPEC = importlib.util.spec_from_file_location("bijux_typed_shell_validator", PATH)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class ShellConfigurationLoaderTests(unittest.TestCase):
    def parse(self, content):
        parent = ROOT / "artifacts/bijux-docs/shell-configuration"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            path = Path(directory) / "authored.yml"
            path.write_text(content)
            return validator.load_yaml(path)

    def test_duplicate_top_level_and_nested_keys_reject_even_valid_last_values(self):
        for content in ("extra: {}\nextra: {}\n", "extra:\n  bijux:\n    repository: other\n    repository: bijux-core\n"):
            with self.subTest(content=content), self.assertRaisesRegex(RuntimeError, r"authored.yml: duplicate configuration key .* at line"):
                self.parse(content)

    def test_scalar_and_sequence_documents_have_mapping_diagnostics(self):
        for content in ("true\n", "- extra\n", "'site'\n"):
            with self.subTest(content=content), self.assertRaisesRegex(RuntimeError, "authored.yml: configuration must be a mapping"):
                self.parse(content)

    def test_author_yaml_merge_and_python_name_tag_survive_without_execution(self):
        config = self.parse("defaults: &defaults\n  repository: bijux-core\nextra:\n  bijux:\n    <<: *defaults\n    repository: bijux-atlas\nhooks: [docs/hooks/content.py]\nformatter: !!python/name:pymdownx.superfences.fence_code_format\n")
        validator.validate_root_contract(config, "authored.yml")
        self.assertEqual(config["extra"]["bijux"]["repository"], "bijux-atlas")
        self.assertEqual(config["formatter"], "")

    def test_invalid_hook_shape_reports_file_and_hook_index(self):
        config = self.parse("extra:\n  bijux:\n    repository: bijux-core\nhooks:\n  - true\n")
        with self.assertRaisesRegex(RuntimeError, r"authored.yml: hooks\[1\] must be a non-empty string"):
            validator.validate_root_contract(config, "authored.yml")

    def test_invalid_tagged_owned_field_is_not_silently_resolved_or_defaulted(self):
        config = self.parse("extra:\n  bijux:\n    repository: bijux-core\n    repository_facts: !ENV [SHOW_FACTS, false]\n")
        with self.assertRaisesRegex(RuntimeError, "repository_facts must be a Boolean"):
            validator.validate_root_contract(config, "authored.yml")

    def cli_fixture(self, directory):
        repo = Path(directory)
        canonical = ROOT / "shared/bijux-docs/config"
        baseline = json.loads((canonical / "mkdocs-baseline.json").read_text())
        registry = json.loads((canonical / "hub-links.json").read_text())
        shared = repo / ".bijux/shared/bijux-docs/config"
        shared.mkdir(parents=True)
        for name in ("mkdocs-baseline.json", "hub-links.json"):
            (shared / name).write_bytes((canonical / name).read_bytes())
        config = {key: baseline[key] for key in ("strict", "use_directory_urls", "dev_addr", "copyright")}
        theme = baseline["theme"]
        config.update(theme={key: theme[key] for key in ("name", "language", "logo", "favicon", "font")},
                      plugins=baseline["required_plugins"], markdown_extensions=list(baseline["required_markdown_extensions"]),
                      extra_css=baseline["extra_css"], extra_javascript=baseline["extra_javascript"],
                      exclude_docs="\n".join(baseline["required_exclude_docs"]),
                      extra={"bijux": {"nav_mode": "default", "theme_key": "bijux:theme", "hub_links": registry}})
        config["theme"].update(icon={"repo": theme["repository_icon"]}, features=theme["required_features"])
        config["markdown_extensions"] = [{"pymdownx.superfences": {"custom_fences": [{"name": "mermaid", "class": baseline["diagram"]["fence_class"]}]}} if value == "pymdownx.superfences" else value for value in config["markdown_extensions"]]
        vendor = repo / "docs" / baseline["diagram"]["vendor"]
        vendor.parent.mkdir(parents=True)
        vendor.symlink_to(ROOT / "shared/bijux-docs" / baseline["diagram"]["vendor"])
        root = {"INHERIT": "mkdocs.shared.yml", "site_name": "Authored identity", "extra": {"bijux": {"repository": "bijux-core"}}}
        (repo / "mkdocs.shared.yml").write_text(yaml.safe_dump(config, sort_keys=False))
        (repo / "mkdocs.yml").write_text(yaml.safe_dump(root, sort_keys=False))
        return repo, config, root

    def test_real_cli_retains_valid_effective_configuration_without_writes(self):
        parent = ROOT / "artifacts/bijux-docs/shell-configuration"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            repo, _, _ = self.cli_fixture(directory)
            before = {name: (repo / name).read_bytes() for name in ("mkdocs.yml", "mkdocs.shared.yml")}
            result = subprocess.run([sys.executable, str(PATH), str(repo)], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("validation passed", result.stdout)
            self.assertEqual(before, {name: (repo / name).read_bytes() for name in before})

    def test_real_cli_names_root_mode_and_missing_shared_destination_without_writes(self):
        parent = ROOT / "artifacts/bijux-docs/shell-configuration"
        parent.mkdir(parents=True, exist_ok=True)
        for fault in ("mode", "destination"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(dir=parent) as directory:
                repo, shared, root = self.cli_fixture(directory)
                if fault == "mode":
                    root["extra"]["bijux"]["nav_mode"] = "phone"
                    (repo / "mkdocs.yml").write_text(yaml.safe_dump(root, sort_keys=False))
                else:
                    removed = shared["extra"]["bijux"]["hub_links"].pop()
                    (repo / "mkdocs.shared.yml").write_text(yaml.safe_dump(shared, sort_keys=False))
                before = {name: (repo / name).read_bytes() for name in ("mkdocs.yml", "mkdocs.shared.yml")}
                result = subprocess.run([sys.executable, str(PATH), str(repo)], capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                expected = "mkdocs.yml: extra.bijux.nav_mode" if fault == "mode" else "missing required keys: " + removed["key"]
                self.assertIn(expected, result.stderr)
                self.assertEqual(before, {name: (repo / name).read_bytes() for name in before})


if __name__ == "__main__":
    unittest.main()
