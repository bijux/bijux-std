"""Run shared reader overflow ownership and lifecycle contracts."""

from pathlib import Path
import shutil
import subprocess
import unittest


class ReaderOverflowTests(unittest.TestCase):
    def test_reader_overflow_lifecycle(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "node is required for shared reader contracts")
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                node,
                "--test",
                "--test-reporter=tap",
                str(root / "tests/bijux-docs/unit/content-reflow.test.cjs"),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=20,
        )
        report = root / "artifacts/bijux-docs/unit/content-reflow.log"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"(?m)^# tests [1-9][0-9]*$")
        self.assertRegex(result.stdout, r"(?m)^# skipped 0$")
        self.assertRegex(result.stdout, r"(?m)^# cancelled 0$")
