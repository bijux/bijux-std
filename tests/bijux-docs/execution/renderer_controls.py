"""Execute every source-owned renderer unit and verify its independent receipt."""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / 'tests/bijux-docs'
NODE_TEST_COUNT = 405
NODE_VERSION = 'v24.21.0'


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HELPERS = load('renderer_command_helpers', Path(__file__).with_name('publication_gate.py'))


def expected_python_ids() -> list[str]:
    ids = []
    for path in sorted((TESTS / 'generated').glob('test_*.py')):
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.ClassDef):
                ids.extend(f'{path.stem}.{node.name}.{method.name}' for method in node.body
                           if isinstance(method, ast.FunctionDef) and method.name.startswith('test_'))
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Renderer Python source inventory is empty or duplicated')
    return sorted(ids)


def node_files() -> list[Path]:
    return sorted([*(TESTS / 'unit').glob('*.test.js'), *(TESTS / 'unit').glob('*.test.cjs')])


def node_identity(node: Path) -> dict:
    version = subprocess.check_output([str(node), '--version'], text=True).strip()
    if version != NODE_VERSION:
        raise ValueError('Renderer controls require the admitted Node version')
    modules = ROOT / 'artifacts/bijux-docs/node-runtime/node_modules'
    if not modules.is_dir() or modules.is_symlink():
        raise ValueError('Renderer controls require their own installed Node dependencies')
    return {'version': version, 'executable': str(node.absolute()),
            'executable_sha256': HELPERS.digest(node.resolve()),
            'package_lock_sha256': HELPERS.digest(TESTS / 'package-lock.json'),
            'modules': node_modules_identity(modules)}


def node_modules_identity(root: Path) -> dict:
    records = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            target = path.resolve(strict=True)
            if not target.is_relative_to(root.resolve()) or not target.is_file():
                raise ValueError('Node dependency link escapes its installed owner')
            records[path.relative_to(root).as_posix()] = {
                'target': os.readlink(path), 'sha256': HELPERS.digest(target)}
        elif path.is_file():
            records[path.relative_to(root).as_posix()] = {'sha256': HELPERS.digest(path)}
    return records


def runtime_identity(node: Path) -> dict:
    profiles = load('renderer_control_profiles', ROOT / 'shared/bijux-docs/security/renderer_profiles.py')
    return {'python': HELPERS.runtime_identity(), 'physical_python': profiles.environment_snapshot(),
            'node': node_identity(node)}


def node_cases(path: Path, files: list[Path], expected_count: int | None = None) -> list[dict]:
    expected_count = NODE_TEST_COUNT if expected_count is None else expected_count
    events = [json.loads(line) for line in path.read_text().splitlines()]
    summaries = [event['data'] for event in events if event['type'] == 'test:summary'
                 and 'file' not in event['data']]
    if len(summaries) != 1:
        raise ValueError('Missing or duplicated native Node terminal summary')
    summary = summaries[0]
    counts = summary['counts']
    if (summary.get('success') is not True or counts.get('tests') != expected_count
            or counts.get('passed') != expected_count or counts.get('suites') != 0
            or any(counts.get(name) != 0 for name in ('failed', 'cancelled', 'skipped', 'todo'))):
        raise ValueError('Incomplete or nonpassing native Node execution')
    expected_files = {str(path.resolve()) for path in files}
    records = []
    for event in events:
        if event['type'] not in ('test:pass', 'test:fail'):
            continue
        data = event['data']
        if (event['type'] != 'test:pass' or data.get('skip') or data.get('todo')
                or data.get('details', {}).get('type') != 'test'
                or data.get('file') not in expected_files or data.get('entryFile') != data['file']
                or type(data.get('line')) is not int or type(data.get('column')) is not int
                or not isinstance(data.get('name'), str) or not data['name']):
            raise ValueError('Unowned, skipped or nonpassing Node case')
        records.append({'id': [str(Path(data['file']).relative_to(ROOT)), data['line'], data['column'], data['name']],
                        'status': 'passed', 'seconds': data['details']['duration_ms'] / 1000})
    ids = [json.dumps(row['id']) for row in records]
    if len(records) != expected_count or len(ids) != len(set(ids)):
        raise ValueError('Missing or duplicated native Node case')
    if {data['id'][0] for data in records} != {str(path.relative_to(ROOT)) for path in files}:
        raise ValueError('Native Node execution omitted a source-owned unit file')
    return records


def execute(output: Path, node: Path) -> dict:
    before = runtime_identity(node)
    suite = unittest.defaultTestLoader.discover(str(TESTS / 'generated'), pattern='test_*.py')
    expected = expected_python_ids()
    if sorted(test.id() for test in HELPERS.flatten(suite)) != expected:
        raise ValueError('Discovered renderer cases differ from their source-owned inventory')
    files = node_files()
    with (output / 'node-events.jsonl').open('w') as stdout, (output / 'node-stderr.log').open('w') as stderr:
        child = subprocess.run([str(node), '--test', '--test-reporter=' + str(Path(__file__).with_name('node_events.cjs')),
                                *map(str, files)], cwd=ROOT, stdout=stdout, stderr=stderr)
    with (output / 'python-unittest.log').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=HELPERS.CommandResult).run(suite)
    cases = node_cases(output / 'node-events.jsonl', files)
    if child.returncode or not result.wasSuccessful():
        raise ValueError('Renderer unit execution failed')
    return {'expected_python_ids': expected, 'python_cases': result.records,
            'python_executed': result.testsRun, 'node_cases': cases, 'node_executed': len(cases),
            'node_exit': child.returncode, 'runtime_before': before, 'runtime_after': runtime_identity(node)}


def verify(output: Path, current_source: dict | None = None, workflow: dict | None = None) -> dict:
    receipt = json.loads((output / 'renderer-controls.json').read_text())
    source = current_source if current_source is not None else HELPERS.source_identity()
    identity = workflow if workflow is not None else HELPERS.workflow_identity()
    if (receipt.get('schema') != 1 or receipt.get('status') != 'passed'
            or receipt.get('verification_only') is not True or receipt.get('publication_approval') is not False
            or receipt.get('workflow') != identity or receipt.get('source_before') != source
            or receipt.get('source_after') != source or receipt.get('child_exit') != 0 or receipt.get('node_exit') != 0):
        raise ValueError('Renderer controls lack passing current source/workflow execution')
    expected = expected_python_ids()
    cases = receipt.get('python_cases', [])
    if (receipt.get('expected_python_ids') != expected or receipt.get('python_executed') != len(expected)
            or sorted(case['id'] for case in cases) != expected
            or any(case.get('status') != 'passed' or case.get('errors') for case in cases)):
        raise ValueError('Renderer Python execution accounting is incomplete or nonpassing')
    node = node_cases(output / 'node-events.jsonl', node_files())
    if receipt.get('node_cases') != node or receipt.get('node_executed') != NODE_TEST_COUNT:
        raise ValueError('Renderer Node case accounting differs from its native events')
    before = receipt.get('runtime_before', {})
    if before != receipt.get('runtime_after'):
        raise ValueError('Renderer runtime physical bytes changed during execution')
    python = before.get('python', {})
    node_runtime = before.get('node', {})
    if (python.get('distributions') != HELPERS.pins() or python.get('lock_sha256') != HELPERS.digest(HELPERS.LOCK)
            or python.get('verification_only') is not True or python.get('publication_approval') is not False
            or not before.get('physical_python') or node_runtime.get('version') != NODE_VERSION
            or not node_runtime.get('modules') or node_runtime.get('package_lock_sha256') != HELPERS.digest(TESTS / 'package-lock.json')):
        raise ValueError('Renderer runtime has incomplete or mismatched installed lock identity')
    files = HELPERS.inventory(output)
    files.pop('renderer-controls.json', None)
    if receipt.get('artifact_digests') != files:
        raise ValueError('Renderer control artifacts are missing, extra or changed')
    return receipt


def run(python: Path, node: Path, output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise ValueError('Preserve existing renderer control evidence')
    output.mkdir(parents=True, exist_ok=True)
    source, workflow = HELPERS.source_identity(), HELPERS.workflow_identity()
    started = time.monotonic()
    child = subprocess.run([str(python.absolute()), str(Path(__file__).resolve()), '_execute',
                            '--node', str(node.absolute()), '--output', str(output)], cwd=ROOT,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PATH=str(node.absolute().parent) + os.pathsep + os.environ.get('PATH', '')),
                           capture_output=True, text=True)
    (output / 'runner.log').write_text(child.stdout + child.stderr)
    receipt = {'schema': 1, 'status': 'passed' if child.returncode == 0 else 'failed',
               'verification_only': True, 'publication_approval': False,
               'workflow': workflow, 'source_before': source, 'source_after': HELPERS.source_identity(),
               'child_exit': child.returncode, 'seconds': time.monotonic() - started}
    if (output / 'execution.json').is_file():
        receipt.update(json.loads((output / 'execution.json').read_text()))
    receipt['artifact_digests'] = HELPERS.inventory(output)
    HELPERS.write_json(output / 'renderer-controls.json', receipt)
    try:
        verify(output)
    except (ValueError, KeyError, OSError, TypeError) as error:
        receipt.update(status='failed', error=str(error))
        HELPERS.write_json(output / 'renderer-controls.json', receipt)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('run', 'verify', '_execute'))
    parser.add_argument('--python', type=Path)
    parser.add_argument('--node', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.operation == 'run' and (args.python is None or args.node is None):
        parser.error('Renderer execution requires selected Python and Node interpreters')
    output = args.output.absolute()
    if not output.resolve().is_relative_to((ROOT / 'artifacts').resolve()):
        parser.error('Renderer control evidence belongs under repository artifacts/')
    try:
        if args.operation == '_execute':
            HELPERS.write_json(output / 'execution.json', execute(output, args.node))
        elif args.operation == 'run':
            run(args.python, args.node, output)
        else:
            verify(output)
    except (ValueError, KeyError, OSError, TypeError, subprocess.SubprocessError) as error:
        print('Renderer controls failed:', error)
        return 1
    print('Renderer controls verified; no publication approval')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
