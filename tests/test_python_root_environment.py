from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = ROOT / 'shared/bijux-makes-py/root/env.mk'


class PythonRootEnvironmentTests(unittest.TestCase):
    def setUp(self) -> None:
        artifacts = ROOT / 'artifacts/tests/python-root-environment'
        artifacts.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.make = shutil.which('make')
        self.assertIsNotNone(self.make)
        (self.root / 'Makefile').write_text(
            f'include {ENVIRONMENT}\n'
            '.PHONY: probe\nprobe:\n\t@$(PYTHON) -c "print(1)"\n'
        )

    def interpreter(self, name: str) -> Path:
        path = self.bin / name
        path.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name}"\n')
        path.chmod(0o755)
        return path

    def probe(self, *arguments: str) -> str:
        environment = os.environ.copy()
        environment.pop('PYTHON', None)
        environment['PATH'] = str(self.bin)
        result = subprocess.run(
            [str(self.make), '--no-print-directory', 'probe', 'SHELL=/bin/bash', *arguments],
            cwd=self.root, env=environment,
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def test_prefers_the_supported_named_interpreter_when_available(self) -> None:
        self.interpreter('python3')
        self.interpreter('python3.11')
        self.assertEqual(self.probe(), 'python3.11')

    def test_uses_ambient_python_when_the_named_interpreter_is_absent(self) -> None:
        self.interpreter('python3')
        self.assertEqual(self.probe(), 'python3')

    def test_preserves_an_explicit_interpreter_override(self) -> None:
        custom = self.interpreter('custom-python')
        self.assertEqual(self.probe(f'PYTHON={custom}'), 'custom-python')


if __name__ == '__main__':
    unittest.main()
