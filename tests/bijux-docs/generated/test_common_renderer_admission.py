"""Real neutral/Rust Make entrypoints admit the actual renderer before cleanup."""
from pathlib import Path
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class CommonRendererAdmissionTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'artifacts/bijux-docs/common-renderer-admission'
        parent.mkdir(parents=True, exist_ok=True)
        self.report = parent / 'make-profiles.jsonl'
        self.rendered = parent
        self.directory = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        self.shared = self.repo / '.bijux/shared/bijux-docs'
        shutil.copytree(ROOT / 'shared/bijux-docs/tooling/material', self.shared / 'tooling/material')
        asset = json.loads((self.shared / 'tooling/material/runtime-provenance.json').read_text())['output_asset']
        for relative in ('partials/main.html', asset):
            target = self.shared / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / 'shared/bijux-docs' / relative, target)
        self.record = self.repo / '.bijux/docs-projection.json'
        self.record.write_text(json.dumps({'schema': 1, 'source': {'mode': 'local-verification', 'sha': None, 'origin': None}, 'files': {}}))
        self.prior = self.repo / 'artifacts/docs/site'
        self.prior.mkdir(parents=True)
        (self.prior / 'retained.txt').write_text('previous reader artifact')
        check = self.repo / 'artifacts/docs/check-site'
        check.mkdir(parents=True)
        (check / 'retained.txt').write_text('previous reader artifact')
        self.calls = self.repo / 'artifacts/invocations.jsonl'
        self.prepared = self.repo / 'artifacts/prepared.txt'
        self.wrapper = self.repo / 'renderer-python'
        self.wrapper.write_text(f'''#!{sys.executable}
import json,os,subprocess,sys
from pathlib import Path
with Path({str(self.calls)!r}).open('a') as output:
 output.write(json.dumps({{'args':sys.argv[1:],'provider':os.environ.get('DOCS_PROVIDER'),'cache':os.environ.get('XDG_CACHE_HOME'),'bytecode':os.environ.get('PYTHONDONTWRITEBYTECODE')}})+'\\n')
if sys.argv[1:3]==['-m','mkdocs']:
 if os.environ.get('REAL_DOCS_BUILD')=='1':
  sys.exit(subprocess.call([{sys.executable!r},*sys.argv[1:]]))
 sys.exit(0)
sys.exit(subprocess.call([{sys.executable!r},*sys.argv[1:]]))
''')
        self.wrapper.chmod(0o755)
        (self.repo / 'mkdocs.yml').write_text('site_name: Renderer admission fixture\n')

    def makefile(self, components='docs', fields='', native=False):
        compiler = self.shared / 'tooling/material/build_runtime.py'
        content = f'''BIJUX_MAKE_COMPONENTS := {components}
BIJUX_MAKES_SHARED_ROOT := {ROOT / 'shared'}
DOCS_PYTHON_RUN := env DOCS_PROVIDER=fixture-provider {self.wrapper}
DOCS_MATERIAL_COMPILER := {compiler}
DOCS_PREPARE_TARGETS := prepare-reader
{fields}
include {ROOT / 'shared/bijux-makes/bijux.mk'}
.PHONY: prepare-reader reject-source
prepare-reader:
	@mkdir -p artifacts
	@printf 'prepared\\n' > {self.prepared}
reject-source:
	@echo 'authored source guard refused' >&2; exit 1
'''
        if native:
            self.record.unlink(missing_ok=True)
        (self.repo / 'Makefile').write_text(content)

    def run_make(self, target='docs', *arguments, real=False):
        if self.calls.exists():
            self.calls.unlink()
        argv = ['make', '--no-print-directory', '-j4', target, *arguments]
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result = subprocess.run(argv, cwd=self.repo,
                                env=dict(os.environ, REAL_DOCS_BUILD='1' if real else '0'), capture_output=True, text=True, timeout=30)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []
        with self.report.open('a') as output:
            output.write(json.dumps({'test': self.id(), 'argv': argv, 'cwd': str(self.repo),
                                     'started_utc': started, 'completed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                     'exit_code': result.returncode, 'actual_mkdocs': real, 'calls': calls,
                                     'makefile': (self.repo / 'Makefile').read_text(),
                                     'stdout': result.stdout, 'stderr': result.stderr}) + '\n')
        return result, calls

    def assert_preserved(self, result, calls, prepare=False):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(any(call['args'][:2] == ['-m', 'mkdocs'] for call in calls))
        self.assertEqual((self.prior / 'retained.txt').read_text(), 'previous reader artifact')
        self.assertEqual((self.repo / 'artifacts/docs/check-site/retained.txt').read_text(), 'previous reader artifact')
        self.assertEqual(self.prepared.exists(), prepare)

    def test_managed_default_uses_one_interpreter_and_provider_for_all_neutral_and_rust_entrypoints(self):
        for components in ('docs', 'docs rust'):
            self.makefile(components)
            for target in ('docs', 'docs-check', 'docs-serve'):
                with self.subTest(components=components, target=target):
                    result, calls = self.run_make(target)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(calls[0]['args'], [str(self.shared / 'tooling/material/build_runtime.py'), '--check'])
                    self.assertEqual(calls[0]['bytecode'], '1')
                    self.assertEqual(calls[1]['args'], calls[0]['args'])
                    self.assertEqual(calls[2]['args'][:2], ['-m', 'mkdocs'])
                    self.assertEqual(calls[0]['provider'], 'fixture-provider')
                    self.assertEqual(calls[1]['provider'], 'fixture-provider')
                    self.assertEqual(calls[2]['provider'], 'fixture-provider')
                    self.assertEqual(calls[0]['cache'], calls[2]['cache'])

    def test_missing_compiler_blocks_prepare_and_cleanup_even_under_parallel_make(self):
        (self.shared / 'tooling/material/build_runtime.py').unlink()
        for components in ('docs', 'docs rust'):
            self.makefile(components)
            for target in ('docs', 'docs-check', 'docs-serve'):
                with self.subTest(components=components, target=target):
                    result, calls = self.run_make(target)
                    self.assert_preserved(result, calls)
                    self.assertIn('missing accepted Material runtime compiler', result.stderr)

    def test_installed_version_outside_admission_preserves_prior_output(self):
        path = self.shared / 'tooling/material/admission.json'
        record = json.loads(path.read_text())
        record['version'] = '9.7.8'
        path.write_text(json.dumps(record))
        self.makefile('docs rust')
        result, calls = self.run_make('docs-check')
        self.assert_preserved(result, calls)
        self.assertIn('Unsupported Material version', result.stderr)

    def test_generated_asset_and_template_drift_preserve_prior_output(self):
        asset = json.loads((self.shared / 'tooling/material/runtime-provenance.json').read_text())['output_asset']
        for relative in (asset, 'partials/main.html'):
            with self.subTest(relative=relative):
                path = self.shared / relative
                before = path.read_bytes()
                path.write_bytes(before + b'\nchanged')
                self.makefile()
                result, calls = self.run_make('docs')
                self.assert_preserved(result, calls)
                self.assertIn('compatibility output differs', result.stderr)
                path.write_bytes(before)

    def test_unknown_profile_and_conflicting_runner_fail_before_prepare(self):
        for fields, diagnostic in (('DOCS_RENDERER_PROFILE := guessed', 'must explicitly select'),
                                   ('DOCS_RUN := env mkdocs', 'must equal DOCS_PYTHON_RUN')):
            with self.subTest(fields=fields):
                self.makefile(fields=fields)
                result, calls = self.run_make()
                self.assert_preserved(result, calls)
                self.assertIn(diagnostic, result.stderr)

    def test_generic_unconfigured_caller_cannot_implicitly_select_native(self):
        self.makefile(native=True)
        result, calls = self.run_make()
        self.assert_preserved(result, calls)
        self.assertIn('DOCS_RENDERER_PROFILE must explicitly select', result.stderr)

    def test_explicit_native_cannot_bypass_managed_record_or_symlink(self):
        self.makefile(fields='DOCS_RENDERER_PROFILE := native')
        result, calls = self.run_make()
        self.assert_preserved(result, calls)
        self.assertIn('cannot bypass managed Bijux shell ownership', result.stderr)
        result, calls = self.run_make('docs', 'DOCS_PROJECTION_RECORD=absent', 'DOCS_CONFIG_PROJECTION_RECORD=absent')
        self.assert_preserved(result, calls)
        self.assertIn('cannot bypass managed Bijux shell ownership', result.stderr)
        self.record.unlink()
        self.record.symlink_to(self.repo / 'missing-record')
        result, calls = self.run_make()
        self.assert_preserved(result, calls)
        self.assertIn('cannot bypass managed Bijux shell ownership', result.stderr)

    def external_config(self):
        external = self.repo / 'external-reader'
        (external / '.bijux').mkdir(parents=True)
        (external / '.bijux/docs-projection.json').write_bytes(self.record.read_bytes())
        self.record.unlink()
        config = external / 'mkdocs.yml'
        config.write_text('site_name: External reader fixture\n')
        return config

    def test_external_config_managed_site_selects_admission(self):
        config = self.external_config()
        self.makefile(fields=f'DOCS_CONFIG := {config}')
        result, calls = self.run_make()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(calls[0]['args'], [str(self.shared / 'tooling/material/build_runtime.py'), '--check'])
        self.assertEqual(calls[2]['args'][:2], ['-m', 'mkdocs'])

    def test_external_config_managed_site_rejects_native(self):
        config = self.external_config()
        self.makefile(fields=f'DOCS_CONFIG := {config}\nDOCS_RENDERER_PROFILE := native')
        result, calls = self.run_make()
        self.assert_preserved(result, calls)
        self.assertIn(str(config.parent / '.bijux/docs-projection.json'), result.stderr)

    def test_explicit_native_preserves_custom_runner_flags_and_does_not_require_material(self):
        (self.shared / 'tooling/material/build_runtime.py').unlink()
        native = self.repo / 'native-docs'
        native.write_text(f'''#!{sys.executable}
import json,sys
from pathlib import Path
Path('artifacts/native-arguments.json').write_text(json.dumps(sys.argv[1:]))
if '--site-dir' in sys.argv:
 directory=Path(sys.argv[sys.argv.index('--site-dir')+1]);directory.mkdir(parents=True,exist_ok=True)
 (directory/'index.html').write_text('<main>Native renderer fixture</main>')
''')
        native.chmod(0o755)
        self.makefile(native=True, fields=f'DOCS_RENDERER_PROFILE := native\nDOCS_RUN := {native}\nDOCS_BUILD_FLAGS := --strict --verbose')
        result, calls = self.run_make()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(calls, [])
        arguments = json.loads((self.repo / 'artifacts/native-arguments.json').read_text())
        self.assertEqual(arguments[:3], ['build', '--strict', '--verbose'])
        self.assertEqual((self.prior / 'index.html').read_text(), '<main>Native renderer fixture</main>')

    def test_source_check_failure_after_admission_preserves_check_output(self):
        self.makefile(fields='DOCS_SOURCE_CHECK_TARGETS := reject-source')
        result, calls = self.run_make('docs-check')
        self.assert_preserved(result, calls, prepare=True)
        self.assertIn('authored source guard refused', result.stderr)
        self.assertEqual(calls[0]['args'], [str(self.shared / 'tooling/material/build_runtime.py'), '--check'])

    def test_preparation_cannot_replace_admitted_runtime_before_render(self):
        asset = json.loads((self.shared / 'tooling/material/runtime-provenance.json').read_text())['output_asset']
        self.makefile(fields='DOCS_PREPARE_TARGETS := replace-renderer')
        with (self.repo / 'Makefile').open('a') as output:
            output.write(f"replace-renderer:\n\t@printf 'changed' >> {self.shared / asset}\n")
        result, calls = self.run_make()
        self.assert_preserved(result, calls)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]['args'], calls[1]['args'])
        self.assertIn('compatibility output differs', result.stderr)

    def test_native_preparation_cannot_introduce_managed_shell_and_bypass_admission(self):
        native = self.repo / 'native-docs'
        native.write_text('#!/usr/bin/env bash\nexit 0\n')
        native.chmod(0o755)
        self.makefile(native=True, fields=f'DOCS_RENDERER_PROFILE := native\nDOCS_RUN := {native}\nDOCS_PREPARE_TARGETS := introduce-managed-shell')
        with (self.repo / 'Makefile').open('a') as output:
            output.write(f"introduce-managed-shell:\n\t@printf '{{}}' > {self.record}\n")
        result, calls = self.run_make()
        self.assert_preserved(result, calls)
        self.assertIn('cannot bypass managed Bijux shell ownership', result.stderr)
        self.assertTrue(self.record.exists())

    def test_source_check_cannot_change_admitted_runtime_before_cleanup(self):
        asset = json.loads((self.shared / 'tooling/material/runtime-provenance.json').read_text())['output_asset']
        self.makefile(fields='DOCS_PREPARE_TARGETS :=\nDOCS_SOURCE_CHECK_TARGETS := change-checked-renderer')
        with (self.repo / 'Makefile').open('a') as output:
            output.write(f"change-checked-renderer:\n\t@printf 'changed' >> {self.shared / asset}\n")
        result, calls = self.run_make('docs-check')
        self.assert_preserved(result, calls)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]['args'], calls[1]['args'])
        self.assertIn('compatibility output differs', result.stderr)

    def test_actual_strict_material_build_through_neutral_and_rust_profiles(self):
        asset = json.loads((self.shared / 'tooling/material/runtime-provenance.json').read_text())['output_asset']
        docs = self.repo / 'docs'
        (docs / 'overrides').mkdir(parents=True)
        (docs / 'index.md').write_text('# Admitted renderer\n\nA real static documentation fixture.\n')
        (docs / 'overrides/main.html').write_bytes((self.shared / 'partials/main.html').read_bytes())
        target = docs / asset
        target.parent.mkdir(parents=True)
        target.write_bytes((self.shared / asset).read_bytes())
        (self.repo / 'mkdocs.yml').write_text('site_name: Admitted renderer\nstrict: true\nexclude_docs: /overrides/\ntheme:\n  name: material\n  font: false\n  custom_dir: docs/overrides\nnav:\n  - Reader: index.md\n')
        for components in ('docs', 'docs rust'):
            with self.subTest(components=components):
                self.makefile(components)
                result, calls = self.run_make(real=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                html = (self.prior / 'index.html').read_text()
                (self.rendered / ('rust-rendered.html' if components == 'docs rust' else 'neutral-rendered.html')).write_text(html)
                self.assertIn('<h1 id="admitted-renderer">Admitted renderer</h1>', html)
                self.assertEqual(html.count(asset), 1)
                self.assertEqual(calls[0]['args'], [str(self.shared / 'tooling/material/build_runtime.py'), '--check'])
                self.assertEqual(calls[1]['args'], calls[0]['args'])
                self.assertEqual(calls[2]['args'][:3], ['-m', 'mkdocs', 'build'])


if __name__ == '__main__':
    unittest.main()
