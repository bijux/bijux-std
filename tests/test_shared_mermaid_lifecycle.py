"""Run the shared Mermaid renderer lifecycle regression contracts."""
from pathlib import Path
import shutil
import subprocess
import unittest


class SharedMermaidLifecycleTests(unittest.TestCase):
    def test_mermaid_render_lifecycle(self) -> None:
        node = shutil.which("node")
        self.assertIsNotNone(node, "node is required for shared docs runtime contracts")
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [node, "--test", "--test-reporter=tap", str(root / "tests/bijux-docs/unit/mermaid-init.test.cjs")],
            cwd=root, capture_output=True, text=True, timeout=20, check=False,
        )
        report = root / "artifacts/bijux-docs/unit/mermaid-lifecycle.log"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"(?m)^# tests [1-9][0-9]*$")
        self.assertRegex(result.stdout, r"(?m)^# skipped 0$")
        self.assertRegex(result.stdout, r"(?m)^# cancelled 0$")
