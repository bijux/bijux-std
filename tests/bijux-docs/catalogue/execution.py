"""Run the bounded catalogue unittest groups with source and runtime receipts."""
from pathlib import Path
import argparse
import ast
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
import platform
import re
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
COUNTS = {'test_recipe_sources': 29, 'test_source_checkpoint': 8,
          'test_native_sources': 12, 'test_renderer_authority': 7, 'test_entrypoints': 2}
GROUPS = {'source': ('test_recipe_sources', 'test_source_checkpoint'),
          'renderer': ('test_native_sources', 'test_renderer_authority'),
          'typed-entrypoint': ('test_entrypoints.CatalogueEntrypoints.test_actual_typed_renderer_reconstructs_originals_without_publication_approval',),
          'tracked-entrypoint': ('test_entrypoints.CatalogueEntrypoints.test_actual_tracked_renderer_uses_the_unchanged_default_dependency_lock',)}
LOCK = HERE / 'requirements.lock.txt'


def load(path):
    spec = importlib.util.spec_from_file_location('bijux_catalogue_execution_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helpers = load(ROOT / 'tests/bijux-docs/execution/publication_gate.py')


def pins():
    return {re.sub(r'[-_.]+', '-', name).lower(): version for name, version in
            re.findall(r'^([A-Za-z0-9_.-]+)==([^\s]+)', LOCK.read_text(), re.M)}


def runtime():
    actual = {re.sub(r'[-_.]+', '-', distribution.metadata['Name']).lower(): distribution.version
              for distribution in importlib.metadata.distributions()}
    if actual != pins() or platform.python_version() != '3.14.4':
        raise ValueError('Catalogue controls require the exact isolated dependency lock and CPython 3.14.4')
    profiles = load(ROOT / 'shared/bijux-docs/security/renderer_profiles.py')
    return {'version': platform.python_version(), 'executable': sys.executable,
            'lock_sha256': helpers.digest(LOCK), 'distributions': actual,
            'physical': profiles.environment_snapshot(), 'verification_only': True,
            'publication_approval': False}


def expected(group):
    ids = []
    for selection in GROUPS[group]:
        name = selection.split('.')[0]
        count = COUNTS[name]
        tree = ast.parse((HERE / (name + '.py')).read_text())
        found = [name + '.' + owner.name + '.' + method.name
                 for owner in tree.body if isinstance(owner, ast.ClassDef)
                 for method in owner.body if isinstance(method, ast.FunctionDef) and method.name.startswith('test_')]
        if len(found) != count:
            raise ValueError('Catalogue maintained case inventory differs: ' + name)
        if selection == name:
            ids.extend(found)
        elif selection in found:
            ids.append(selection)
        else:
            raise ValueError('Catalogue selected case is missing: ' + selection)
    return sorted(ids)


def artifacts(group):
    locations = {'source': (), 'renderer': ('catalogue-native-sources',),
        'typed-entrypoint': ('catalogue-entrypoint-tests/typed-sites', 'catalogue-entrypoint-tests/typed-entrypoint.json'),
        'tracked-entrypoint': ('catalogue-entrypoint-tests/tracked-sites', 'catalogue-entrypoint-tests/tracked-entrypoint.json',
                               'catalogue-entrypoint-tests/tracked-entrypoint.log')}[group]
    result = {}
    for name in locations:
        path = ROOT / 'artifacts' / name
        if path.is_dir():
            result[name] = helpers.inventory(path)
        elif path.is_file() and not path.is_symlink():
            result[name] = helpers.digest(path)
        else:
            raise ValueError('Catalogue retained evidence is missing: ' + name)
    return result


def verify(receipt, group, source, selected_runtime):
    wanted = expected(group)
    if (receipt.get('schema') != 1 or receipt.get('group') != group
            or receipt.get('expected_ids') != wanted or receipt.get('executed_ids') != wanted
            or receipt.get('failed_ids') or receipt.get('skipped_ids') or not receipt.get('passed')
            or receipt.get('source_before') != source or receipt.get('source_after') != source
            or receipt.get('runtime_before') != selected_runtime or receipt.get('runtime_after') != selected_runtime
            or receipt.get('publication_approval') is not False
            or receipt.get('workflow') != helpers.workflow_identity()):
        raise ValueError('Catalogue controls failed or source/runtime/case identity changed')


class Outcome(unittest.TextTestResult):
    def __init__(self, *arguments):
        super().__init__(*arguments)
        self.executed_ids = []
        self.case_seconds = {}

    def startTest(self, test):
        self.executed_ids.append(test.id())
        self.started = time.monotonic()
        super().startTest(test)

    def stopTest(self, test):
        self.case_seconds[test.id()] = time.monotonic() - self.started
        super().stopTest(test)


def execute(group, output):
    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=True)
    helpers.write_json(output / 'receipt.json', {'schema': 1, 'group': group, 'passed': False,
        'publication_approval': False, 'workflow': helpers.workflow_identity(), 'error': 'Catalogue execution incomplete'})
    before = helpers.source_identity(); selected = runtime()
    sys.path.insert(0, str(HERE))
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in GROUPS[group])
    wanted = expected(group)
    found = sorted(test.id() for test in helpers.flatten(suite))
    if found != wanted:
        raise ValueError('Catalogue discovered cases differ from maintained source inventory')
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=Outcome).run(suite)
    (output / 'unittest.log').write_text(log.getvalue())
    after = helpers.source_identity(); after_runtime = runtime()
    receipt = {'schema': 1, 'group': group, 'expected_ids': wanted, 'executed_ids': sorted(result.executed_ids),
               'failed_ids': sorted(test.id() for test, _ in result.failures + result.errors),
               'skipped_ids': sorted(test.id() for test, _ in result.skipped),
               'case_seconds': result.case_seconds, 'execution_seconds': time.monotonic() - started,
               'artifacts': artifacts(group),
               'passed': result.wasSuccessful() and result.testsRun == len(wanted) and not result.skipped,
               'source_before': before, 'source_after': after,
               'runtime_before': selected, 'runtime_after': after_runtime,
               'workflow': helpers.workflow_identity(), 'unittest_log_sha256': helpers.digest(output / 'unittest.log'),
               'publication_approval': False}
    helpers.write_json(output / 'receipt.json', receipt)
    verify(receipt, group, after, after_runtime)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['run', 'verify', 'execute'])
    parser.add_argument('--group', choices=GROUPS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--python')
    options = parser.parse_args()
    output = options.output.absolute()
    if not output.resolve().is_relative_to((ROOT / 'artifacts').resolve()) or any(path.is_symlink() for path in [output, *output.parents]):
        parser.error('Catalogue receipts must use ordinary paths under repository artifacts')
    if options.operation == 'run':
        if not options.python:
            parser.error('Select the isolated catalogue interpreter explicitly')
        command = [options.python, '-B', str(Path(__file__)), 'execute', '--group', options.group, '--output', str(output)]
        result = subprocess.run(command, cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        return result.returncode
    if options.operation == 'execute':
        execute(options.group, output)
    else:
        receipt = json.loads((output / 'receipt.json').read_text())
        if receipt.get('artifacts') != artifacts(options.group):
            raise ValueError('Catalogue retained artifacts changed')
        if receipt.get('unittest_log_sha256') != helpers.digest(output / 'unittest.log'):
            raise ValueError('Catalogue unittest log changed')
        verify(receipt, options.group, helpers.source_identity(), runtime())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
