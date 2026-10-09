"""Execute every source-owned renderer unit and verify its independent receipt."""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import hashlib
import posixpath
import re
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / 'tests/bijux-docs'
NODE_TEST_COUNT = 460
NODE_VERSION = 'v24.21.0'
GROUPS = ('renderer', 'passive-reader')
PASSIVE_READER_ID = ('test_standalone_reader_renderer.StandaloneRendererTests.'
                     'test_committed_passive_reader_and_native_search_reconstruct_together')


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



def group_python_ids(group: str | None = None) -> list[str]:
    expected = expected_python_ids()
    if group is None:
        return expected
    if group not in GROUPS or expected.count(PASSIVE_READER_ID) != 1:
        raise ValueError('Unknown renderer group or missing source-owned passive reader')
    return [name for name in expected if (name == PASSIVE_READER_ID) == (group == 'passive-reader')]


def group_node_count(group: str | None = None) -> int:
    group_python_ids(group)
    return 0 if group == 'passive-reader' else NODE_TEST_COUNT


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
            'modules': node_modules_identity(modules),
            'package_manifests': {name: (ROOT / 'artifacts/bijux-docs/node-runtime' / name / 'package.json').read_text()
                                  for name in source_node_packages()
                                  if (ROOT / 'artifacts/bijux-docs/node-runtime' / name / 'package.json').is_file()}}


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


def source_node_packages() -> dict:
    return {name: record for name, record in json.loads((TESTS / 'package-lock.json').read_text())['packages'].items()
            if name}


def node_environment(node: Path) -> dict:
    # Unit adapters and compiler subprocesses resolve only this owned installation.
    return dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                NODE_PATH=str(ROOT / 'artifacts/bijux-docs/node-runtime/node_modules'),
                PATH=str(node.absolute().parent) + os.pathsep + os.environ.get('PATH', ''))


def valid_digest(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def ordinary_relative(value) -> bool:
    return (isinstance(value, str) and bool(value) and '\\' not in value
            and not PurePosixPath(value).is_absolute() and '..' not in PurePosixPath(value).parts
            and str(PurePosixPath(value)) == value)


def validate_runtime(runtime: dict) -> None:
    if not isinstance(runtime, dict) or any(not isinstance(runtime.get(name), dict)
                                            for name in ('python', 'physical_python', 'node')):
        raise ValueError('Renderer runtime snapshot must contain typed identity objects')
    python, physical, node = (runtime.get(name, {}) for name in ('python', 'physical_python', 'node'))
    platform = physical.get('platform', {})
    if (python.get('scope') != 'installed-exact-lock-fixture-interpreter'
            or python.get('verification_only') is not True or python.get('publication_approval') is not False
            or python.get('distributions') != HELPERS.pins() or python.get('lock_sha256') != HELPERS.digest(HELPERS.LOCK)
            or not isinstance(python.get('executable'), str) or not Path(python['executable']).is_absolute()
            or not valid_digest(python.get('executable_sha256'))
            or not isinstance(python.get('version'), str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', python['version'])
            or python.get('implementation') != 'CPython'
            or not isinstance(python.get('system'), str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', python['system'])
            or not isinstance(python.get('machine'), str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', python['machine'])
            or platform != {'system': python['system'], 'machine': python['machine'], 'python': python['version'],
                            'implementation': 'cpython', 'cache_tag': 'cpython-' + ''.join(python['version'].split('.')[:2])}
            or physical.get('executable_sha256') != python['executable_sha256']):
        raise ValueError('Renderer Python executable/platform/lock identities are incomplete or disagree')
    stdlib, roots, packages, startup = (physical.get(name) for name in ('stdlib', 'physical_roots', 'packages', 'startup_inputs'))
    def files_record(record):
        return (isinstance(record, dict) and type(record.get('files_count')) is int and record['files_count'] > 0
                and valid_digest(record.get('files_sha256')))
    if (not files_record(stdlib) or not isinstance(roots, list) or not roots
            or any(not files_record(root) or root.get('root') != 'site-packages' for root in roots)
            or not isinstance(packages, list) or not packages or not isinstance(startup, list)):
        raise ValueError('Renderer Python physical source inventory is incomplete')
    normalize = lambda name: re.sub(r'[-_.]+', '-', name).lower()
    package_versions = {}
    for package in packages:
        if (not files_record(package) or not isinstance(package.get('name'), str)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', package['name'])
                or not isinstance(package.get('version'), str) or not package['version']):
            raise ValueError('Renderer Python physical package record is malformed')
        name = normalize(package['name'])
        if name in package_versions:
            raise ValueError('Renderer Python physical package ownership is duplicated')
        package_versions[name] = package['version']
    pins = {normalize(name): version for name, version in HELPERS.pins().items()}
    if (any(package_versions.get(name) != version for name, version in pins.items())
            or set(package_versions) - set(pins) - {'pip', 'setuptools', 'wheel'}):
        raise ValueError('Renderer Python physical packages differ from the source-owned lock')
    paths = set()
    for item in startup:
        if (not isinstance(item, dict) or not ordinary_relative(item.get('path')) or item['path'] in paths
                or not isinstance(item.get('source'), str) or not valid_digest(item.get('sha256'))
                or hashlib.sha256(item['source'].encode()).hexdigest() != item['sha256']
                or ('resolved_target' in item and (not isinstance(item['resolved_target'], str)
                                                  or not Path(item['resolved_target']).is_absolute()))):
            raise ValueError('Renderer Python startup source identity is malformed')
        paths.add(item['path'])
    if (node.get('version') != NODE_VERSION or not isinstance(node.get('executable'), str)
            or not Path(node['executable']).is_absolute() or not valid_digest(node.get('executable_sha256'))
            or node.get('package_lock_sha256') != HELPERS.digest(TESTS / 'package-lock.json')
            or not isinstance(node.get('modules'), dict) or not node['modules']
            or not isinstance(node.get('package_manifests'), dict)):
        raise ValueError('Renderer Node executable/lock/physical identities are incomplete')
    modules, manifests, declared = node['modules'], node['package_manifests'], source_node_packages()
    if (set(manifests) - set(declared)
            or any(name not in manifests for name, record in declared.items() if not record.get('optional'))):
        raise ValueError('Renderer Node package ownership differs from the source-owned lock')
    for name, text in manifests.items():
        if not isinstance(text, str):
            raise ValueError('Renderer Node package manifest must retain exact source bytes')
        relative = name.removeprefix('node_modules/') + '/package.json'
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError('Renderer Node package manifest must contain an object')
        if (data.get('version') != declared[name]['version']
                or data.get('name') != name.removeprefix('node_modules/')
                or modules.get(relative) != {'sha256': hashlib.sha256(text.encode()).hexdigest()}):
            raise ValueError('Renderer Node package manifest bytes/version differ from the owned lock')
    for name, record in modules.items():
        if (not ordinary_relative(name) or not isinstance(record, dict)
                or set(record) not in ({'sha256'}, {'sha256', 'target'}) or not valid_digest(record.get('sha256'))
                or (name not in {'.package-lock.json'} and not name.startswith('.bin/')
                    and not any(name.startswith(owner.removeprefix('node_modules/') + '/') for owner in manifests))):
            raise ValueError('Renderer Node physical module record is malformed or unowned')
        if 'target' in record:
            target = record['target']
            if not isinstance(target, str) or not target or PurePosixPath(target).is_absolute() or '\\' in target:
                raise ValueError('Renderer Node physical link target is malformed')
            resolved = posixpath.normpath(str(PurePosixPath(name).parent / target))
            if not ordinary_relative(resolved) or modules.get(resolved) != {'sha256': record['sha256']}:
                raise ValueError('Renderer Node physical link escapes or disagrees with its owned target')
    if '.package-lock.json' not in modules:
        raise ValueError('Renderer Node installed package-lock identity is missing')


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


def execute(output: Path, node: Path, group: str | None = None) -> dict:
    before = runtime_identity(node)
    suite = unittest.defaultTestLoader.discover(str(TESTS / 'generated'), pattern='test_*.py')
    all_expected = expected_python_ids()
    if sorted(test.id() for test in HELPERS.flatten(suite)) != all_expected:
        raise ValueError('Discovered renderer cases differ from their source-owned inventory')
    expected = group_python_ids(group)
    suite = unittest.TestSuite(test for test in HELPERS.flatten(suite) if test.id() in expected)
    files = node_files() if group_node_count(group) else []
    node_exit = 0
    if files:
        with (output / 'node-events.jsonl').open('w') as stdout, (output / 'node-stderr.log').open('w') as stderr:
            child = subprocess.run([str(node), '--test', '--test-reporter=' + str(Path(__file__).with_name('node_events.cjs')),
                                    *map(str, files)], cwd=ROOT, stdout=stdout, stderr=stderr, env=node_environment(node))
        node_exit = child.returncode
    # Retain independent interactive source/reference bytes inside this job's
    # uploaded evidence root so successful assertions remain physically reviewable.
    artifact_key = 'BIJUX_INTERACTIVE_TEST_ARTIFACTS_ROOT'
    previous_artifacts = os.environ.get(artifact_key)
    os.environ[artifact_key] = str(output / 'interactive-reports')
    try:
        with (output / 'python-unittest.log').open('w') as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=HELPERS.CommandResult).run(suite)
    finally:
        if previous_artifacts is None:
            os.environ.pop(artifact_key, None)
        else:
            os.environ[artifact_key] = previous_artifacts
    cases = node_cases(output / 'node-events.jsonl', files) if files else []
    if node_exit or not result.wasSuccessful():
        raise ValueError('Renderer unit execution failed')
    return {'expected_python_ids': expected, 'python_cases': result.records,
            'python_executed': result.testsRun, 'node_cases': cases, 'node_executed': len(cases),
            'node_exit': node_exit, 'group': group, 'runtime_before': before, 'runtime_after': runtime_identity(node)}


def verify_receipt(output: Path, current_source: dict | None = None, workflow: dict | None = None,
                   group: str | None = None) -> dict:
    receipt = json.loads((output / 'renderer-controls.json').read_text())
    source = current_source if current_source is not None else HELPERS.source_identity()
    identity = workflow if workflow is not None else HELPERS.workflow_identity()
    if (receipt.get('schema') != 1 or receipt.get('group') != group or receipt.get('status') != 'passed'
            or receipt.get('verification_only') is not True or receipt.get('publication_approval') is not False
            or receipt.get('workflow') != identity or receipt.get('source_before') != source
            or receipt.get('source_after') != source or receipt.get('child_exit') != 0 or receipt.get('node_exit') != 0):
        raise ValueError('Renderer controls lack passing current source/workflow execution')
    expected = group_python_ids(group)
    cases = receipt.get('python_cases', [])
    if (receipt.get('expected_python_ids') != expected or receipt.get('python_executed') != len(expected)
            or sorted(case['id'] for case in cases) != expected
            or any(case.get('status') != 'passed' or case.get('errors') for case in cases)):
        raise ValueError('Renderer Python execution accounting is incomplete or nonpassing')
    count = group_node_count(group)
    if not count and any((output / name).exists() for name in ('node-events.jsonl', 'node-stderr.log')):
        raise ValueError('Passive reader group cannot substitute unrelated Node execution')
    node = node_cases(output / 'node-events.jsonl', node_files()) if count else []
    if receipt.get('node_cases') != node or receipt.get('node_executed') != count:
        raise ValueError('Renderer Node case accounting differs from its native events')
    before = receipt.get('runtime_before', {})
    if before != receipt.get('runtime_after'):
        raise ValueError('Renderer runtime physical bytes changed during execution')
    validate_runtime(before)
    files = HELPERS.inventory(output)
    files.pop('renderer-controls.json', None)
    if receipt.get('artifact_digests') != files:
        raise ValueError('Renderer control artifacts are missing, extra or changed')
    return receipt



def verify(output: Path, current_source: dict | None = None, workflow: dict | None = None) -> dict:
    if (output / 'renderer-controls.json').exists():
        return verify_receipt(output, current_source, workflow)
    return verify_groups(output, current_source, workflow)


def verify_groups(output: Path, current_source: dict | None = None, workflow: dict | None = None) -> dict:
    if (not output.is_dir() or output.is_symlink()
            or {path.name for path in output.iterdir()} != set(GROUPS)
            or any(not (output / group).is_dir() or (output / group).is_symlink() for group in GROUPS)):
        raise ValueError('Renderer group evidence is missing, duplicated or unexpected')
    source = current_source if current_source is not None else HELPERS.source_identity()
    identity = workflow if workflow is not None else HELPERS.workflow_identity()
    receipts = {group: verify_receipt(output / group, source, identity, group) for group in GROUPS}
    python_ids = [case['id'] for receipt in receipts.values() for case in receipt['python_cases']]
    if sorted(python_ids) != expected_python_ids() or len(python_ids) != len(set(python_ids)):
        raise ValueError('Renderer group union does not execute every Python source case exactly once')
    if sum(receipt['node_executed'] for receipt in receipts.values()) != NODE_TEST_COUNT:
        raise ValueError('Renderer group union omitted native Node execution')
    return {'schema': 2, 'status': 'passed', 'verification_only': True, 'publication_approval': False,
            'source_before': source, 'source_after': source, 'workflow': identity, 'groups': receipts,
            'python_executed': len(python_ids), 'node_executed': NODE_TEST_COUNT}


def run(python: Path, node: Path, output: Path, group: str | None = None) -> None:
    if output.exists() and any(output.iterdir()):
        raise ValueError('Preserve existing renderer control evidence')
    output.mkdir(parents=True, exist_ok=True)
    group_python_ids(group)
    source, workflow = HELPERS.source_identity(), HELPERS.workflow_identity()
    started = time.monotonic()
    child = subprocess.run([str(python.absolute()), str(Path(__file__).resolve()), '_execute',
                            '--node', str(node.absolute()), '--output', str(output),
                            *(['--group', group] if group is not None else [])], cwd=ROOT,
                           env=node_environment(node),
                           capture_output=True, text=True)
    (output / 'runner.log').write_text(child.stdout + child.stderr)
    receipt = {'schema': 1, 'status': 'passed' if child.returncode == 0 else 'failed',
               'verification_only': True, 'publication_approval': False, 'group': group,
               'workflow': workflow, 'source_before': source, 'source_after': HELPERS.source_identity(),
               'child_exit': child.returncode, 'seconds': time.monotonic() - started}
    if (output / 'execution.json').is_file():
        receipt.update(json.loads((output / 'execution.json').read_text()))
    receipt['artifact_digests'] = HELPERS.inventory(output)
    HELPERS.write_json(output / 'renderer-controls.json', receipt)
    try:
        verify_receipt(output, group=group)
    except (ValueError, KeyError, OSError, TypeError) as error:
        receipt.update(status='failed', error=str(error))
        HELPERS.write_json(output / 'renderer-controls.json', receipt)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('run', 'verify', '_execute'))
    parser.add_argument('--group', choices=GROUPS)
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
            HELPERS.write_json(output / 'execution.json', execute(output, args.node, args.group))
        elif args.operation == 'run':
            run(args.python, args.node, output, args.group)
        else:
            if args.group is None:
                verify(output)
            else:
                verify_receipt(output, group=args.group)
    except (ValueError, KeyError, OSError, TypeError, subprocess.SubprocessError) as error:
        print('Renderer controls failed:', error)
        return 1
    print('Renderer controls verified; no publication approval')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
