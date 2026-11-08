"""Preserve native renderer failure messages without swallowing process exits."""
from __future__ import annotations

from contextlib import redirect_stderr
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from mkdocs.exceptions import Abort, MkDocsException

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'shared/bijux-docs/security/render_publication.py'
SPEC = importlib.util.spec_from_file_location('bijux_renderer_error_controls', SCRIPT)
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


class RendererErrors(unittest.TestCase):
    def invoke(self, error):
        output = io.StringIO()
        with patch.object(sys, 'argv', [str(SCRIPT), '--config', 'mkdocs.yml',
                                      '--site-dir', 'artifacts/docs/site']), \
                patch.object(renderer, 'build_artifact', side_effect=error) as build, \
                redirect_stderr(output):
            result = renderer.main()
        self.assertIs(build.call_args.kwargs['strict'], True)
        return result, output.getvalue()

    def test_native_strict_abort_keeps_warning_count_and_nonzero_result(self):
        error = Abort('Aborted with 13 warnings in strict mode!')
        self.assertIsInstance(error, SystemExit)
        result, output = self.invoke(error)
        self.assertEqual(result, 1)
        self.assertEqual(output, 'Documentation artifact rejected: Aborted with 13 warnings in strict mode!\n')

    def test_native_mkdocs_exception_keeps_its_message(self):
        result, output = self.invoke(MkDocsException('Source-owned renderer refused.'))
        self.assertEqual(result, 1)
        self.assertEqual(output, 'Documentation artifact rejected: Source-owned renderer refused.\n')

    def test_unrelated_system_exit_keeps_original_exit_code(self):
        error = SystemExit(23)
        with self.assertRaises(SystemExit) as caught:
            self.invoke(error)
        self.assertIs(caught.exception, error)
        self.assertEqual(caught.exception.code, 23)

    def test_keyboard_interrupt_is_not_reclassified(self):
        error = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.invoke(error)
        self.assertIs(caught.exception, error)

    def test_help_remains_available_without_site_dependencies(self):
        result = subprocess.run([sys.executable, '-S', str(SCRIPT), '--help'],
                                cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--source-identity', result.stdout)
        self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
