"""Complete typed and ordinary tracked renderer paths in isolated test fixtures."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

from entrypoint_fixture import execute

HERE = Path(__file__).resolve()
REPO = next(parent for parent in HERE.parents
            if (parent / 'shared/bijux-docs/security/catalogue_recipe.py').is_file())
OUTPUT = REPO / 'artifacts/catalogue-entrypoint-tests'
OUTPUT.mkdir(parents=True, exist_ok=True)


class CatalogueEntrypoints(unittest.TestCase):
    def test_actual_typed_renderer_reconstructs_originals_without_publication_approval(self):
        with tempfile.TemporaryDirectory(dir=OUTPUT) as directory:
            receipt = execute(REPO, Path(directory) / 'source', catalogue=True, retained=OUTPUT)
            self.assertTrue(receipt['reconstruction']['verification_only'])
            self.assertEqual(receipt['identity']['state'], 'complete')
            self.assertTrue(receipt['routes']['passed'])
            self.assertEqual(receipt['routes']['route_count'], 5)
            self.assertEqual(receipt['routes']['search_entries'], 4)
            self.assertEqual(receipt['identity']['derivation']['documents'], 4)
            self.assertFalse(receipt['publication_approval'])
            (OUTPUT / 'typed-entrypoint.json').write_text(json.dumps(receipt, indent=2) + '\n')

    def test_actual_tracked_renderer_uses_the_unchanged_default_dependency_lock(self):
        python = os.environ.get('BIJUX_CATALOGUE_DEFAULT_PYTHON')
        self.assertTrue(python, 'Select the independent default 32-package renderer explicitly')
        with tempfile.TemporaryDirectory(dir=OUTPUT) as directory:
            receipt = Path(directory) / 'tracked-entrypoint.json'
            code = ('from pathlib import Path; import json; from publication_gate import runtime_identity; '
                    'default_runtime=runtime_identity(); '
                    'from entrypoint_fixture import execute; '
                    f'out=execute(Path({str(REPO)!r}), Path({str(Path(directory) / "source")!r}), catalogue=False, retained=Path({str(OUTPUT)!r})); '
                    'out["default_runtime"]=default_runtime; '
                    f'Path({str(receipt)!r}).write_text(json.dumps(out, indent=2)+chr(10))')
            result = subprocess.run([python, '-B', '-c', code], cwd=REPO,
                                    env={**os.environ, 'PYTHONPATH': str(HERE.parent) + os.pathsep + str(REPO / 'tests/bijux-docs/execution')}, capture_output=True, text=True)
            (OUTPUT / 'tracked-entrypoint.log').write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            actual = json.loads(receipt.read_text())
            self.assertTrue(actual['reconstruction']['verification_only'])
            self.assertEqual(actual['identity']['state'], 'complete')
            self.assertTrue(actual['routes']['passed'])
            self.assertEqual(actual['routes']['route_count'], 2)
            self.assertEqual(actual['routes']['search_entries'], 1)
            self.assertNotIn('derivation', actual['identity'])
            self.assertEqual(len(actual['default_runtime']['distributions']), 32)
            self.assertFalse(actual['default_runtime']['publication_approval'])
            self.assertFalse(actual['publication_approval'])
            (OUTPUT / 'tracked-entrypoint.json').write_text(json.dumps(actual, indent=2) + '\n')
