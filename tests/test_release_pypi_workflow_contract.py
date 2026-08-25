from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / "shared" / "bijux-gh" / "workflows" / "release-pypi.yml"


class ReleasePyPiWorkflowContractTests(unittest.TestCase):
    def test_release_pypi_workflow_inherits_release_rust_toolchain(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertNotIn('"1.85.0"', workflow)
        self.assertIn(
            'release_rust_toolchain="$(from_values "" "${BIJUX_RELEASE_RUST_TOOLCHAIN:-}" "${{ vars.BIJUX_RELEASE_RUST_TOOLCHAIN || \'\' }}" "1.86.0")"',
            workflow,
        )
        self.assertIn(
            'rust_toolchain="$(from_values "" "${BIJUX_PYPI_RUST_TOOLCHAIN:-}" "${{ vars.BIJUX_PYPI_RUST_TOOLCHAIN || \'\' }}" "${release_rust_toolchain}")"',
            workflow,
        )

    def test_release_pypi_workflow_uses_trusted_publish_for_maturin_by_default(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn('publish_command="$(from_values "" "${BIJUX_PYPI_PUBLISH_COMMAND:-}" "${{ vars.BIJUX_PYPI_PUBLISH_COMMAND || \'\' }}" "")"', workflow)
        self.assertIn("environment:\n      name: ${{ needs.resolve.outputs.environment_name }}", workflow)
        self.assertIn("permissions:\n      contents: read\n      actions: read\n      id-token: write", workflow)
        self.assertIn("Publish PyPI distributions with custom command", workflow)
        self.assertIn("needs.resolve.outputs.publish_command == ''", workflow)
        self.assertIn("uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # release/v1", workflow)
        self.assertIn("packages-dir: artifacts/python/build", workflow)
        self.assertNotIn('make publish-py PUBLISH_BUILD=0', workflow)


if __name__ == "__main__":
    unittest.main()
