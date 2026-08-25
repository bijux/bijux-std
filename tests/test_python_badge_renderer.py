from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = REPOSITORY_ROOT / "shared/bijux-makes-py/repository/badge_renderer.py"


def load_renderer_module():
    module_name = "badge_renderer"
    spec = importlib.util.spec_from_file_location(module_name, RENDERER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {RENDERER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class PythonBadgeRendererTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_renderer_module()
        self.fixture = Path(tempfile.mkdtemp())
        (self.fixture / "docs").mkdir()
        for package in ("bijux-example-core", "example", "bijux-example-dev"):
            package_dir = self.fixture / "packages" / package
            package_dir.mkdir(parents=True)
            distribution = package
            package_dir.joinpath("pyproject.toml").write_text(
                f"""\
[project]
name = "{distribution}"
version = "0.0.0"
requires-python = ">=3.11,<4"

[project.urls]
Documentation = "https://example.test/{package}/"
""",
                encoding="utf-8",
            )
            package_dir.joinpath("README.md").write_text(
                f"# {package}\n\n[![old](old)](old)\n\nBody\n",
                encoding="utf-8",
            )
        (self.fixture / "README.md").write_text(
            "# Example\n\n[![old](old)](old)\n\nBody\n",
            encoding="utf-8",
        )
        (self.fixture / "docs/index.md").write_text(
            "# Example\n\n[![old](old)](old)\n\nBody\n",
            encoding="utf-8",
        )
        (self.fixture / "pyproject.toml").write_text(
            """\
[project]
name = "fixture"
version = "0.0.0"
requires-python = ">=3.11,<4"

[tool.bijux_example]
repository = "bijux-example"
packages = ["bijux-example-core", "example", "bijux-example-dev"]
docs_package = "bijux-example-dev"
badge_packages = ["bijux-example-core", "example"]
docs_badge_packages = ["bijux-example-core"]
badge_include_current_docs = false
""",
            encoding="utf-8",
        )
        (self.fixture / "docs/badges.md").write_text(
            """\
<!-- bijux-example-badges:repository-summary:start -->
published {{ public_package_count }}
<!-- bijux-example-badges:repository-summary:end -->

<!-- bijux-example-badges:package-summary:start -->
package {{ distribution_name }}
<!-- bijux-example-badges:package-summary:end -->

<!-- bijux-example-badges:maintainer-summary:start -->
maintainer
<!-- bijux-example-badges:maintainer-summary:end -->

<!-- bijux-example-badges:family-pypi-badge:start -->
pypi {{ distribution_name }} {{ package_pypi_url }}
<!-- bijux-example-badges:family-pypi-badge:end -->

<!-- bijux-example-badges:family-ghcr-badge:start -->
ghcr {{ distribution_name }} {{ package_ghcr_url }}
<!-- bijux-example-badges:family-ghcr-badge:end -->

<!-- bijux-example-badges:family-docs-badge:start -->
docs {{ distribution_name }} {{ docs_url }}
<!-- bijux-example-badges:family-docs-badge:end -->
""",
            encoding="utf-8",
        )
        self.renderer = self.module.BadgeRenderer(self.fixture, "bijux_example")

    def test_repository_render_uses_package_catalog_selection(self) -> None:
        rendered = self.renderer.render_badge_block(
            self.module.BadgeTarget(self.fixture / "README.md", "repository")
        )

        self.assertIn("published 2", rendered)
        self.assertEqual(rendered.count("pypi "), 2)
        self.assertEqual(rendered.count("docs "), 1)

    def test_package_render_respects_docs_family_policy(self) -> None:
        rendered = self.renderer.render_badge_block(
            self.module.BadgeTarget(
                self.fixture / "packages/example/README.md",
                "package",
                "example",
            )
        )

        self.assertIn("package example", rendered)
        self.assertIn("pypi example", rendered)
        self.assertNotIn("docs example ", rendered)
        self.assertIn("docs bijux-example-core", rendered)

    def test_sync_and_check_share_idempotent_rendering(self) -> None:
        changed = self.renderer.synchronize_badges(check=False)

        self.assertEqual(len(changed), 5)
        self.assertEqual(self.renderer.synchronize_badges(check=True), [])
        self.assertIn(
            "<!-- bijux-example-badges:generated:start -->",
            (self.fixture / "README.md").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
