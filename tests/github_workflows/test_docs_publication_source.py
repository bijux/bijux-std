from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from .policy_fixtures import MODULE, ROOT


class DocumentationPublicationSourceTests(unittest.TestCase):
    def workflow(self):
        return MODULE.parse_workflow((ROOT / "shared/bijux-gh/workflows/deploy-docs.yml").read_bytes(), "deploy-docs")

    def test_source_admission_precedes_dependency_setup_and_build(self):
        steps = self.workflow()["jobs"]["build"]["steps"]
        names = [step.get("name", "") for step in steps]
        admission = names.index("Admit accepted documentation standards")
        self.assertGreater(admission, names.index("Checkout repository"))
        self.assertLess(admission, names.index("Resolve docs deploy configuration"))
        command = steps[admission]["run"]
        self.assertIn("https://github.com/bijux/bijux-std.git", command)
        self.assertIn("BIJUX_STD_ROOT=%s", command)
        self.assertIn("BIJUX_STD_REF=%s", command)
        self.assertNotIn("secrets.", command)

    def test_missing_or_malformed_pins_fail_before_any_source_preparation(self):
        command = next(step["run"] for step in self.workflow()["jobs"]["build"]["steps"] if step.get("name") == "Admit accepted documentation standards")
        root = ROOT / "artifacts" / "docs-publication-controls"
        root.mkdir(parents=True, exist_ok=True)
        for pin in [None, "main", "a" * 39, "a" * 41, "../untrusted", "A" * 40]:
            with self.subTest(pin=pin), tempfile.TemporaryDirectory(dir=root) as directory:
                target = Path(directory)
                (target / ".github/standards").mkdir(parents=True)
                if pin is not None:
                    (target / ".github/standards/bijux-std.sha").write_text(pin + "\n")
                result = subprocess.run(["bash", "-c", command], cwd=target, env={**os.environ, "GITHUB_ENV": str(target / "env")}, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((target / "artifacts/accepted-standard").exists())
                self.assertFalse((target / "env").exists())
