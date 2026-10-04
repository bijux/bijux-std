"""Run the shared theme's dependency-free Material state regression contracts."""
from pathlib import Path
import shutil
import subprocess
import unittest


class SharedThemePersistenceTests(unittest.TestCase):
    def test_material_palette_state_contract(self) -> None:
        node = shutil.which("node")
        self.assertIsNotNone(node, "node is required for shared docs runtime contracts")
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [node, "--test", str(root / "tests/bijux-docs/unit/theme-persistence.test.cjs")],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
