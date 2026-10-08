"""Actual Make profiles must admit installed renderer/source before invoking a renderer."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
PROFILE = Path(os.environ.get('DOCS_MAKE_SOURCE', ROOT / 'shared/bijux-makes-py/ci/docs.mk'))


class MaterialMakeAdmissionTests(unittest.TestCase):
    def setUp(self):
        output = ROOT / 'artifacts/bijux-docs/make-material-admission'
        output.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=output)
        self.addCleanup(self.directory.cleanup)
        self.fixture = Path(self.directory.name)
        self.shared = self.fixture / '.bijux/shared/bijux-docs'
        shutil.copytree(ROOT / 'shared/bijux-docs/tooling/material', self.shared / 'tooling/material')
        for relative in ['tooling/quality/validate_production_url.py', 'tooling/scripts/verify_bijux_docs_site.sh', 'tooling/scripts/docs_source_authority.sh', 'partials/main.html', json.loads((self.shared / 'tooling/material/runtime-provenance.json').read_text())['output_asset']]:
            target = self.shared / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / 'shared/bijux-docs' / relative, target)
        subprocess.run(['git', 'init', '-q', str(self.fixture)], check=True, capture_output=True)
        self.retained = self.fixture / 'artifacts/retained-output'
        self.retained.mkdir(parents=True)
        (self.retained / 'reader-proof.txt').write_text('prior reader artifact')
        self.invocations = self.fixture / 'invocations.jsonl'
        self.wrapper = self.fixture / 'renderer-python'
        # Only MkDocs execution is replaced. Admission invokes the real pinned compiler/interpreter.
        self.wrapper.write_text(f'''#!{sys.executable}
import json,os,subprocess,sys
from pathlib import Path
with Path({str(self.invocations)!r}).open('a') as output:
 output.write(json.dumps({{'args':sys.argv[1:],'profile':os.environ.get('READER_PROFILE'),'bytecode':os.environ.get('PYTHONDONTWRITEBYTECODE')}})+'\\n')
if sys.argv[1:3]==['-m','mkdocs']:
 sys.exit(0)
sys.exit(subprocess.call([{sys.executable!r},*sys.argv[1:]]))
''')
        self.wrapper.chmod(0o755)
        self.makefile = self.fixture / 'Makefile'
        self.makefile.write_text(f'''PROJECT_DIR := {self.fixture}
PROJECT_ARTIFACTS_DIR := {self.fixture}/artifacts
MKDOCS_CFG := {self.fixture}/mkdocs.yml
DOCS_PYTHON := {self.wrapper}
DOCS_SITE_URL := https://bijux.io/fixture/
DOCS_BUILD_PREPARE_TARGETS :=
DOCS_CHECK_PREPARE_TARGETS :=
DOCS_SERVE_PREPARE_TARGETS :=
DOCS_BUILD_PRE_CLEAN_PATHS := {self.retained}
DOCS_CHECK_PRE_CLEAN_PATHS := {self.retained}
DOCS_SERVE_PRE_CLEAN_PATHS := {self.retained}
DOCS_BUILD_ENV := READER_PROFILE=build
DOCS_CHECK_ENV := READER_PROFILE=check
DOCS_SERVE_ENV := READER_PROFILE=serve
include {PROFILE}
''')
        (self.fixture / 'mkdocs.yml').write_text('site_name: Reader fixture\n')

    def run_profile(self, target='docs'):
        environment = {**os.environ, 'BIJUX_STD_LOCAL_VERIFY': '1'}
        process = subprocess.run(['make', target], cwd=self.fixture, env=environment, text=True, capture_output=True)
        calls = [json.loads(line) for line in self.invocations.read_text().splitlines()] if self.invocations.exists() else []
        return process, calls

    def assert_preserved_before_render(self, result, calls):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(any(call['args'][:2] == ['-m', 'mkdocs'] for call in calls))
        self.assertEqual((self.retained / 'reader-proof.txt').read_text(), 'prior reader artifact')

    def test_missing_compiler_rejects_before_artifact_cleanup_and_renderer(self):
        (self.shared / 'tooling/material/build_runtime.py').unlink()
        result, calls = self.run_profile()
        self.assert_preserved_before_render(result, calls)
        self.assertIn('missing accepted Material runtime compiler', result.stderr)

    def test_installed_material_outside_admission_cannot_render(self):
        path = self.shared / 'tooling/material/admission.json'
        admitted = json.loads(path.read_text())
        admitted['version'] = '9.7.8'
        path.write_text(json.dumps(admitted))
        result, calls = self.run_profile('docs-check')
        self.assert_preserved_before_render(result, calls)
        self.assertIn('Unsupported Material version', result.stderr)

    def test_generated_runtime_drift_rejects_before_renderer(self):
        record = json.loads((self.shared / 'tooling/material/runtime-provenance.json').read_text())
        (self.shared / record['output_asset']).write_text('incorrect owned asset')
        result, calls = self.run_profile('docs-serve-run')
        self.assert_preserved_before_render(result, calls)
        self.assertIn('compatibility output differs', result.stderr)

    def test_all_profile_entrypoints_admit_with_the_same_interpreter_and_environment(self):
        for target, profile in [('docs', 'build'), ('docs-check', 'check'), ('docs-serve-run', 'serve')]:
            with self.subTest(target=target):
                if self.invocations.exists():
                    self.invocations.unlink()
                result, calls = self.run_profile(target)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                compiler_calls = [call for call in calls if call['args'][:1] == [str(self.shared / 'tooling/material/build_runtime.py')]]
                renderer_calls = [call for call in calls if call['args'][:2] == ['-m', 'mkdocs']]
                self.assertEqual(len(compiler_calls), 1)
                self.assertEqual(len(renderer_calls), 1)
                self.assertIn('Local candidate verification only', result.stdout + result.stderr)
                self.assertEqual(compiler_calls[0]['args'], [str(self.shared / 'tooling/material/build_runtime.py'), '--check'])
                self.assertEqual(compiler_calls[0]['profile'], profile)
                self.assertEqual(compiler_calls[0]['bytecode'], '1')
                self.assertEqual(renderer_calls[0]['args'][:2], ['-m', 'mkdocs'])
                self.assertEqual(renderer_calls[0]['profile'], profile)

    def test_deploy_rejects_before_admission_cleanup_or_render(self):
        result, calls = self.run_profile('docs-deploy')
        self.assert_preserved_before_render(result, calls)
        self.assertEqual(calls, [])
        self.assertIn('publish the exact qualified artifact through the reviewed GitHub Pages workflow', result.stderr)


if __name__ == '__main__':
    unittest.main()
