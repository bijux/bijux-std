from __future__ import annotations

import json
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
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
extra:
  bijux:
    repository: fixture
    nav_mode: default
    theme_key: bijux:theme
  social: []
extra_javascript:
  - assets/javascripts/vendor/mermaid-11.6.0.min.js
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
        fixture = Path(tempfile.mkdtemp())
        shared = fixture / ".bijux/shared/bijux-docs"
        (shared / "config").mkdir(parents=True)
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
        self.assertIn("shared hub current", second.stdout)
        self.assertIn("root inherits hub", second.stdout)

    def test_templates_preserve_registry_order_without_secondary_ordering(self) -> None:
        for template in HUB_TEMPLATES:
            with self.subTest(template=template.name):
                content = template.read_text(encoding="utf-8")
                self.assertNotIn("canonical_hub_keys", content)
                self.assertNotIn("ordered_hub_links", content)
                self.assertEqual(content.count("{% for entry in hub_links %}"), 1)

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
                {"pymdownx.superfences": {"custom_fences": [{"name": "mermaid"}]}}
            ],
            "extra_javascript": list(validator.MERMAID_SCRIPTS),
        }

        validator.validate_shared_contract(shared_config, CANONICAL_LINKS, "shared")
        validator.validate_root_contract(
            {"extra": {"bijux": {"repository": "fixture"}}},
            "root",
        )

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


if __name__ == "__main__":
    unittest.main()
