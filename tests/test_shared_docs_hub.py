from __future__ import annotations

import json
import shutil
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SHARED_DOCS = REPOSITORY_ROOT / "shared/bijux-docs"
SYNC_SCRIPT = SHARED_DOCS / "tooling/scripts/sync_mkdocs_hub.py"
VALIDATOR = SHARED_DOCS / "tooling/quality/validate_bijux_docs_contract.py"
CANONICAL_LINKS = json.loads((SHARED_DOCS / "config/hub-links.json").read_text(encoding="utf-8"))
HUB_TEMPLATES = (
    SHARED_DOCS / "partials/header.html",
    SHARED_DOCS / "partials/nav.html",
)


SHARED_CONFIG = """\
markdown_extensions:
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: bijux-diagram
          format: !!python/name:pymdownx.superfences.fence_code_format
extra:
  bijux:
    repository: fixture
    nav_mode: default
    theme_key: bijux:theme
  social: []
extra_javascript:
  - assets/javascripts/mermaid-init.js
"""

ROOT_CONFIG = """\
INHERIT: mkdocs.shared.yml
site_name: Fixture
extra:
  bijux:
    repository: fixture
    hub_links:
      - key: stale
        label: Stale
        url: https://example.invalid/
nav:
  - Home: index.md
"""


def load_validator():
    yaml_stub = types.ModuleType("yaml")

    class Node:
        pass

    class SafeLoader:
        @classmethod
        def add_multi_constructor(cls, tag: str, constructor) -> None:
            return None

    yaml_stub.Node = Node
    yaml_stub.ScalarNode = Node
    yaml_stub.SequenceNode = Node
    yaml_stub.MappingNode = Node
    yaml_stub.SafeLoader = SafeLoader
    sys.modules["yaml"] = yaml_stub

    spec = importlib.util.spec_from_file_location("bijux_docs_validator", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {VALIDATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SharedDocsHubTests(unittest.TestCase):
    def fixture(self) -> Path:
        artifact_root = REPOSITORY_ROOT / "artifacts/website-delivery"
        artifact_root.mkdir(parents=True, exist_ok=True)
        fixture = Path(tempfile.mkdtemp(prefix="hub-projection-", dir=artifact_root))
        self.addCleanup(shutil.rmtree, fixture)
        shared = fixture / ".bijux/shared/bijux-docs"
        (shared / "config").mkdir(parents=True)
        shutil.copy2(SHARED_DOCS / "config/mkdocs-baseline.json", shared / "config/mkdocs-baseline.json")
        (shared / "config/hub-links.json").write_text(
            json.dumps(CANONICAL_LINKS, indent=2) + "\n",
            encoding="utf-8",
        )
        (fixture / "mkdocs.shared.yml").write_text(SHARED_CONFIG, encoding="utf-8")
        (fixture / "mkdocs.yml").write_text(ROOT_CONFIG, encoding="utf-8")
        return fixture

    def run_sync(self, fixture: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SYNC_SCRIPT), str(fixture), str(fixture / ".bijux/shared/bijux-docs")],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_sync_writes_canonical_shared_hub_idempotently(self) -> None:
        fixture = self.fixture()

        first = self.run_sync(fixture)
        self.assertEqual(first.returncode, 0, first.stderr)
        first_content = (fixture / "mkdocs.shared.yml").read_text(encoding="utf-8")
        second = self.run_sync(fixture)
        self.assertEqual(second.returncode, 0, second.stderr)

        self.assertEqual(first_content, (fixture / "mkdocs.shared.yml").read_text(encoding="utf-8"))
        self.assertEqual(first_content.count("    hub_links:\n"), 1)
        positions = [first_content.index(f"      - key: {link['key']}\n") for link in CANONICAL_LINKS]
        self.assertEqual(positions, sorted(positions))
        root_content = (fixture / "mkdocs.yml").read_text(encoding="utf-8")
        self.assertNotIn("hub_links:", root_content)
        self.assertIn("repository: fixture", root_content)
        self.assertIn("nav:", root_content)
        self.assertIn("configuration current: " + str(fixture / "mkdocs.shared.yml"), second.stdout)
        self.assertIn("configuration current: " + str(fixture / "mkdocs.yml"), second.stdout)

    def test_templates_preserve_registry_order_without_secondary_ordering(self) -> None:
        for template in HUB_TEMPLATES:
            with self.subTest(template=template.name):
                content = template.read_text(encoding="utf-8")
                self.assertNotIn("canonical_hub_keys", content)
                self.assertNotIn("ordered_hub_links", content)
                self.assertEqual(content.count("{% for entry in hub_links %}"), 1)

    def test_sync_preserves_authored_exclusions_and_closes_root_reinclusion(self) -> None:
        fixture = self.fixture()
        path = fixture / 'mkdocs.yml'
        original = path.read_text() + 'exclude_docs: |\n  /private/\n  !/private/public.md\n  !/overrides/**\n'
        path.write_text(original)
        result = self.run_sync(fixture)
        self.assertEqual(result.returncode, 0, result.stderr)
        updated = path.read_text()
        self.assertIn('/private/\n  !/private/public.md\n  !/overrides/**', updated)
        self.assertGreater(updated.index('  /overrides/'), updated.index('  !/overrides/**'))
        self.assertIn('nav:\n  - Home: index.md', updated)
        for name in ('mkdocs.yml', 'mkdocs.shared.yml'):
            self.assertIn('  /hooks/\n', (fixture / name).read_text())
        before = updated
        self.assertEqual(self.run_sync(fixture).returncode, 0)
        self.assertEqual(path.read_text(), before)

    def test_invalid_root_exclusion_fails_before_shared_or_root_mutation(self) -> None:
        fixture = self.fixture()
        root = fixture / 'mkdocs.yml'
        root.write_text(root.read_text() + 'exclude_docs: [/private/]\n')
        before = {name:(fixture / name).read_bytes() for name in ('mkdocs.yml','mkdocs.shared.yml')}
        result = self.run_sync(fixture)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('exclude_docs must be', result.stderr)
        self.assertEqual(before, {name:(fixture / name).read_bytes() for name in before})

    def test_contract_rejects_authored_reinclusion_after_implementation_boundary(self) -> None:
        validator = load_validator()
        baseline = json.loads((SHARED_DOCS / 'config/mkdocs-baseline.json').read_text())
        config = {'exclude_docs':'\n'.join([*baseline['required_exclude_docs'], '!/overrides/**'])}
        with self.assertRaisesRegex(RuntimeError, 'canonical implementation exclusions'):
            validator.validate_mkdocs_baseline(config, baseline, 'effective')

    def test_validator_accepts_shared_hub_and_root_identity(self) -> None:
        validator = load_validator()
        shared_config = {
            "extra": {
                "bijux": {
                    "nav_mode": "default",
                    "theme_key": "bijux:theme",
                    "hub_links": CANONICAL_LINKS,
                }
            },
            "markdown_extensions": [
                {"pymdownx.superfences": {"custom_fences": [{"name": "mermaid", "class": "bijux-diagram"}]}}
            ],
            "extra_javascript": list(validator.MERMAID_SCRIPTS),
        }

        validator.validate_shared_contract(shared_config, CANONICAL_LINKS, "shared")
        validator.validate_root_contract(
            {"extra": {"bijux": {"repository": "fixture"}}},
            "root",
        )

    def test_validator_rejects_material_intercepted_diagram_fence(self) -> None:
        validator = load_validator()
        config = {"markdown_extensions": [{"pymdownx.superfences": {"custom_fences": [{"name": "mermaid", "class": "mermaid"}]}}], "extra_javascript": list(validator.MERMAID_SCRIPTS)}
        with self.assertRaisesRegex(RuntimeError, "avoid Material external renderer"):
            validator.validate_mermaid_contract(config, "effective")

    def test_validator_rejects_eager_diagram_vendor(self) -> None:
        validator = load_validator()
        config = {"markdown_extensions": [{"pymdownx.superfences": {"custom_fences": [{"name": "mermaid", "class": "bijux-diagram"}]}}], "extra_javascript": [*validator.MERMAID_SCRIPTS, validator.MERMAID_VENDOR]}
        with self.assertRaisesRegex(RuntimeError, "lazy-loaded"):
            validator.validate_mermaid_contract(config, "effective")

    def test_sync_projects_single_owner_diagram_contract_from_legacy_configuration(self) -> None:
        fixture = self.fixture()
        config = fixture / "mkdocs.shared.yml"
        config.write_text(config.read_text().replace("class: bijux-diagram", "class: mermaid") + "  - assets/javascripts/vendor/mermaid-11.6.0.min.js\n")
        result = self.run_sync(fixture)
        self.assertEqual(result.returncode, 0, result.stderr)
        content = config.read_text()
        self.assertIn("name: mermaid", content)
        self.assertIn("class: bijux-diagram", content)
        self.assertNotIn("vendor/mermaid-11.6.0.min.js", content)
        self.assertIn("fence_code_format", content)

    def test_configuration_projection_keeps_diagram_and_branding_ownership_separate(self) -> None:
        fixture = self.fixture()
        config = fixture / "mkdocs.shared.yml"
        authored = '\ntheme:\n  logo: assets/bijux_logo_hq.png\nplugins:\n  - search\n  - authored-plugin\n'
        before = config.read_text().replace("class: bijux-diagram", "class: mermaid") + authored
        config.write_text(before)
        spec = importlib.util.spec_from_file_location("bijux_configuration_projection", SYNC_SCRIPT)
        sync = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sync)
        self.assertIn(authored, sync.diagram_content(before))
        root = fixture / "mkdocs.yml"
        custom = '\ntheme:\n  logo: assets/product-wordmark.svg # authored\n'
        root.write_text(root.read_text() + custom)
        result = self.run_sync(fixture)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = config.read_text()
        expected = authored.replace("  - search\n", "  - search\n  - autorefs\n").replace("assets/bijux_logo_hq.png", "assets/bijux_logo.png")
        self.assertIn(expected, after)
        self.assertIn(custom, root.read_text())
        self.assertIn("class: bijux-diagram", after)
        self.assertIn("fence_code_format", after)
        baseline = json.loads((SHARED_DOCS / "config/mkdocs-baseline.json").read_text())
        self.assertEqual(baseline["theme"]["logo"], "assets/bijux_logo.png")
        self.assertEqual(baseline["retired_theme_logos"], ["assets/bijux_logo_hq.png"])
        self.assertIn(authored, sync.diagram_content(before))
        self.assertNotIn("search-recovery", sync.diagram_content(authored))

    def test_validator_rejects_second_material_owned_mermaid_fence(self) -> None:
        validator = load_validator()
        config = {"markdown_extensions": [{"pymdownx.superfences": {"custom_fences": [
            {"name": "mermaid", "class": "bijux-diagram"},
            {"name": "mermaid", "class": "mermaid"},
        ]}}], "extra_javascript": list(validator.MERMAID_SCRIPTS)}
        with self.assertRaisesRegex(RuntimeError, "avoid Material external renderer"):
            validator.validate_mermaid_contract(config, "effective")

    def test_validator_rejects_mapping_form_eager_vendor(self) -> None:
        validator = load_validator()
        config = {"markdown_extensions": [{"pymdownx.superfences": {"custom_fences": [
            {"name": "mermaid", "class": "bijux-diagram"}
        ]}}], "extra_javascript": [*validator.MERMAID_SCRIPTS, {"path": validator.MERMAID_VENDOR, "defer": True}]}
        with self.assertRaisesRegex(RuntimeError, "lazy-loaded"):
            validator.validate_mermaid_contract(config, "effective")

    def test_projected_vendor_digest_rejects_altered_renderer(self) -> None:
        validator = load_validator()
        fixture = self.fixture()
        baseline = json.loads((SHARED_DOCS / "config/mkdocs-baseline.json").read_text())
        source = SHARED_DOCS / "assets" / baseline["diagram"]["vendor"].removeprefix("assets/")
        destination = fixture / "docs" / baseline["diagram"]["vendor"]
        destination.parent.mkdir(parents=True)
        shutil.copy2(source, destination)
        validator.validate_diagram_asset(fixture, baseline)
        destination.write_bytes(destination.read_bytes() + b"\n/* altered */\n")
        with self.assertRaisesRegex(RuntimeError, "digest differs"):
            validator.validate_diagram_asset(fixture, baseline)

    def test_validator_rejects_root_hub_duplication(self) -> None:
        validator = load_validator()
        config = {
            "extra": {
                "bijux": {
                    "repository": "fixture",
                    "hub_links": CANONICAL_LINKS,
                }
            }
        }

        with self.assertRaisesRegex(RuntimeError, "must be inherited"):
            validator.validate_root_contract(config, "root")

    def test_validator_rejects_shared_hub_drift(self) -> None:
        validator = load_validator()
        changed_links = [dict(link) for link in CANONICAL_LINKS]
        changed_links[-2]["url"] = "https://example.invalid/gnss/"
        config = {
            "extra": {
                "bijux": {
                    "nav_mode": "default",
                    "theme_key": "bijux:theme",
                    "hub_links": changed_links,
                }
            }
        }

        with self.assertRaisesRegex(RuntimeError, "must exactly match"):
            validator.validate_shared_contract(config, CANONICAL_LINKS, "shared")

    def test_validator_accepts_product_extensions_to_mkdocs_baseline(self) -> None:
        validator = load_validator()
        baseline = json.loads(
            (SHARED_DOCS / "config/mkdocs-baseline.json").read_text(encoding="utf-8")
        )
        theme = dict(baseline["theme"])
        repository_icon = theme.pop("repository_icon")
        required_features = theme.pop("required_features")
        theme["icon"] = {"repo": repository_icon}
        theme["features"] = [*required_features, "product.feature"]
        config = {
            "exclude_docs": "\n".join(["/product-private/", *baseline["required_exclude_docs"]]),
            "strict": baseline["strict"],
            "use_directory_urls": baseline["use_directory_urls"],
            "dev_addr": baseline["dev_addr"],
            "copyright": baseline["copyright"],
            "theme": theme,
            "plugins": [*baseline["required_plugins"], {"redirects": {}}],
            "markdown_extensions": [
                *baseline["required_markdown_extensions"],
                "product.extension",
            ],
            "extra_css": [*baseline["extra_css"], "product.css"],
            "extra_javascript": [*baseline["extra_javascript"], "product.js"],
        }

        validator.validate_mkdocs_baseline(config, baseline, "shared")

    def test_validator_rejects_missing_common_mkdocs_feature(self) -> None:
        validator = load_validator()
        baseline = json.loads(
            (SHARED_DOCS / "config/mkdocs-baseline.json").read_text(encoding="utf-8")
        )
        theme = dict(baseline["theme"])
        repository_icon = theme.pop("repository_icon")
        required_features = theme.pop("required_features")
        theme["icon"] = {"repo": repository_icon}
        theme["features"] = required_features[1:]
        config = {
            "exclude_docs": "\n".join(["/product-private/", *baseline["required_exclude_docs"]]),
            "strict": baseline["strict"],
            "use_directory_urls": baseline["use_directory_urls"],
            "dev_addr": baseline["dev_addr"],
            "copyright": baseline["copyright"],
            "theme": theme,
            "plugins": baseline["required_plugins"],
            "markdown_extensions": baseline["required_markdown_extensions"],
            "extra_css": baseline["extra_css"],
            "extra_javascript": baseline["extra_javascript"],
        }

        with self.assertRaisesRegex(RuntimeError, "navigation.tabs"):
            validator.validate_mkdocs_baseline(config, baseline, "shared")

    def test_effective_configuration_can_own_plugins_in_root_config(self) -> None:
        validator = load_validator()
        baseline = json.loads(
            (SHARED_DOCS / "config/mkdocs-baseline.json").read_text(encoding="utf-8")
        )
        theme = dict(baseline["theme"])
        repository_icon = theme.pop("repository_icon")
        required_features = theme.pop("required_features")
        theme["icon"] = {"repo": repository_icon}
        theme["features"] = required_features
        shared = {
            "exclude_docs": "\n".join(["/product-private/", *baseline["required_exclude_docs"]]),
            "strict": baseline["strict"],
            "use_directory_urls": baseline["use_directory_urls"],
            "dev_addr": baseline["dev_addr"],
            "copyright": baseline["copyright"],
            "theme": theme,
            "markdown_extensions": baseline["required_markdown_extensions"],
            "extra_css": baseline["extra_css"],
            "extra_javascript": baseline["extra_javascript"],
        }
        root = {
            "theme": {"custom_dir": "docs/overrides"},
            "plugins": baseline["required_plugins"],
            "nav": [{"Home": "index.md"}],
        }

        validator.validate_mkdocs_baseline(
            validator.merge_mappings(shared, root),
            baseline,
            "effective",
        )


if __name__ == "__main__":
    unittest.main()
