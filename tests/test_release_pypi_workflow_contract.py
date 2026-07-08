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


if __name__ == "__main__":
    unittest.main()
