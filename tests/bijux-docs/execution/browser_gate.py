"""Build once, execute bounded engine journeys and require complete coverage."""
from __future__ import annotations

import argparse
import hashlib
import inspect
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / 'tests/bijux-docs'
ARTIFACTS = ROOT / 'artifacts/bijux-docs'
PARTITIONS_PATH = TESTS / 'execution/browser_partitions.py'
PARTITIONS_SPEC = importlib.util.spec_from_file_location('browser_partitions', PARTITIONS_PATH)
PARTITIONS = importlib.util.module_from_spec(PARTITIONS_SPEC)
PARTITIONS_SPEC.loader.exec_module(PARTITIONS)
GROUPS, ENGINES, SUITES = PARTITIONS.GROUPS, PARTITIONS.ENGINES, PARTITIONS.SUITES
PERSISTED_SUITE = "persisted-reader-history"


def partition_plan() -> dict:
    return PARTITIONS.plan({suite: json.loads((ARTIFACTS / 'inventories' / f'{suite}.json').read_text())
                            for suite in SUITES})



def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def environment(suite: str, output: Path) -> dict[str, str]:
    env = dict(os.environ)
    env['BIJUX_GENERATED_ROOT'] = str(ARTIFACTS / ('contrast-generated' if suite == 'contrast' else 'generated'))
    env['BIJUX_UI_ARTIFACT_ROOT'] = str(output)
    env['BIJUX_UI_FULL_GATE'] = '1'
    return env


def playwright() -> str:
    return str(ARTIFACTS / 'node-runtime/node_modules/.bin/playwright')


def fixture_roots() -> list[str]:
    return sorted({str(Path(environment(suite, ARTIFACTS / 'inventories' / suite)['BIJUX_GENERATED_ROOT']).relative_to(ARTIFACTS)) for suite in SUITES})


def fixture_transport():
    path = TESTS / 'execution/fixture_archive.py'
    spec = importlib.util.spec_from_file_location('fixture_transport', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare() -> None:
    if any(name in os.environ for name in ('BIJUX_UI_BROWSER_ENGINE', 'BIJUX_UI_PROJECTS', 'BIJUX_UI_PROFILE')):
        raise ValueError('Canonical inventory must not select projects')
    inventory = ARTIFACTS / 'inventories'
    for suite in (*SUITES, PERSISTED_SUITE):
        env = environment(suite, inventory / suite)
        config = TESTS / f'playwright.{suite}.config.js'
        subprocess.run(['node', str(TESTS / 'reporting/inventory.js'), '--config', str(config), '--output', str(inventory / f'{suite}.json')], cwd=ROOT, env=env, check=True)
    partition_plan()
    archive = ARTIFACTS / 'browser-fixtures.tar.gz'
    receipt = fixture_transport().pack(ARTIFACTS, fixture_roots(), archive)
    print('Fixture transport: ' + json.dumps(receipt, sort_keys=True))
    (ARTIFACTS / 'browser-fixtures.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '\n')
    paths = [archive, ARTIFACTS / 'renderer-source-observation.json'] + [inventory / f'{suite}.json' for suite in (*SUITES, PERSISTED_SUITE)]
    write_json(ARTIFACTS / 'producer-envelope.json', {
        'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'workflow_run_id': os.environ.get('GITHUB_RUN_ID'),
        'workflow_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
        'partition_registry_sha256': hashlib.sha256(PARTITIONS.REGISTRY_PATH.read_bytes()).hexdigest(),
        'artifact_digests': {str(path.relative_to(ARTIFACTS)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
    })


def workflow_controllers():
    return load_module(TESTS / 'execution/workflow_controllers.py', 'browser_workflow_controllers')


def verify_producer_envelope(admission=None) -> dict:
    data = (ARTIFACTS / 'producer-envelope.json').read_bytes()
    receipt = json.loads(data)
    expected = {'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'workflow_run_id': os.environ.get('GITHUB_RUN_ID'), 'workflow_attempt': os.environ.get('GITHUB_RUN_ATTEMPT')}
    if admission is not None:
        if (type(admission).__name__ != 'ArtifactInput'
                or Path(inspect.getfile(type(admission).verify_receipt)).resolve() != TESTS / 'execution/workflow_lineage.py'):
            raise ValueError('API-created source-owned producer input is required')
        admission.verify_receipt('producer-envelope.json', data)
        expected.update(admission.workflow_identity())
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError('Producer workflow/candidate identity mismatch')
    if receipt.get('partition_registry_sha256') != hashlib.sha256(PARTITIONS.REGISTRY_PATH.read_bytes()).hexdigest():
        raise ValueError('Producer browser partition registry mismatch')
    paths = ['browser-fixtures.tar.gz', 'renderer-source-observation.json'] + [f'inventories/{suite}.json' for suite in (*SUITES, PERSISTED_SUITE)]
    if set(receipt.get('artifact_digests', {})) != set(paths):
        raise ValueError('Producer evidence inventory mismatch')
    for name in paths:
        body = (ARTIFACTS / name).read_bytes()
        if admission is not None:
            admission.verify_file(name, body)
        if hashlib.sha256(body).hexdigest() != receipt['artifact_digests'][name]:
            raise ValueError('Producer evidence digest mismatch: ' + name)
    observation = json.loads((ARTIFACTS / 'renderer-source-observation.json').read_text())
    if observation['source']['sha'] != expected['source_head'] or observation['verification_only'] is not True or observation['admission_created'] is not False:
        raise ValueError('Renderer observation is not this candidate verification evidence')
    return receipt


def unpack() -> None:
    archive = ARTIFACTS / 'browser-fixtures.tar.gz'
    expected = (ARTIFACTS / 'browser-fixtures.sha256').read_text().strip()
    if len(expected) != 64 or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError('Fixture archive digest mismatch')
    fixture_transport().unpack(archive, ARTIFACTS, fixture_roots(), expected)


def install_browser_runtime() -> None:
    runtime = ARTIFACTS / 'node-runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    for name in ('package.json', 'package-lock.json'):
        shutil.copyfile(TESTS / name, runtime / name)
    link = TESTS / 'node_modules'
    if link.is_symlink():
        if link.resolve() != runtime / 'node_modules':
            raise ValueError('Browser dependencies belong to another runtime')
    elif link.exists():
        raise ValueError('Preserve existing browser dependencies')
    else:
        link.symlink_to(runtime / 'node_modules', target_is_directory=True)
    env = dict(os.environ, NPM_CONFIG_CACHE=str(ARTIFACTS / 'npm-cache'))
    subprocess.run(['npm', '--prefix', str(runtime), 'ci'], cwd=ROOT, env=env, check=True)


def run(group: str, engine: str) -> None:
    if any(name in os.environ for name in ('BIJUX_UI_BROWSER_ENGINE', 'BIJUX_UI_PROJECTS', 'BIJUX_UI_PROFILE')):
        raise ValueError('Browser execution selection must come from its assigned group/engine')
    assignments = partition_plan()
    if group not in GROUPS or engine not in ENGINES:
        raise ValueError('Unknown assigned browser group or engine')
    controllers = workflow_controllers()
    collection = controllers.collect('producer') if controllers.recovery() else None
    producer = verify_producer_envelope(collection.producer if collection is not None else None)
    unpack()
    install_browser_runtime()
    failed = []
    for suite in GROUPS[group]:
        output = ARTIFACTS / 'shards' / f'{group}-{engine}' / suite
        output.mkdir(parents=True, exist_ok=True)
        env = environment(suite, output)
        env.update(PARTITIONS.selection(group, suite, engine))
        if not assignments[(f'{group}-{engine}', suite)]:
            raise ValueError('Browser partition must execute cases')
        result = subprocess.run([playwright(), 'test', '--config', str(TESTS / f'playwright.{suite}.config.js')], cwd=ROOT, env=env)
        if result.returncode:
            failed.append(suite)
    if failed:
        raise ValueError('Browser qualification failed: ' + ', '.join(failed))
    controllers.record_execution(ARTIFACTS / 'shards' / f'{group}-{engine}', f'browser-{group}-{engine}', producer)


def aggregate(collection=None) -> None:
    module_path = TESTS / 'reporting/aggregate.py'
    spec = importlib.util.spec_from_file_location('browser_aggregation', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inventories = [ARTIFACTS / 'inventories' / f'{suite}.json' for suite in SUITES]
    # Each shard owns a unique group/engine directory; reject absent or extra receipts.
    reports = sorted((ARTIFACTS / 'shards').rglob('qualification.json'))
    expected = {(f'{group}-{engine}', suite) for group, suites in GROUPS.items() for engine in ENGINES for suite in suites}
    actual = [(path.parent.parent.name, path.parent.name) for path in reports]
    output = ARTIFACTS / 'navigation-qualification.json'
    try:
        if collection is None and any(os.environ.get(name, 'success') != 'success' for name in ('FIXTURE_RESULT', 'BROWSER_RESULT', 'COMMAND_RESULT', 'RENDERER_RESULT', 'PERSISTED_RESULT')):
            raise ValueError('A required fixture/browser job or publication command job failed or was cancelled')
        if len(actual) != len(expected) or set(actual) != expected:
            raise ValueError('Missing, duplicate or unexpected browser shard receipt')
        if collection is not None:
            workflow_controllers().require_collection(collection)
        producer = verify_producer_envelope(collection.producer if collection is not None else None)
        controllers = workflow_controllers()
        if collection is not None:
            for group in GROUPS:
                for engine in ENGINES:
                    controllers.verify_execution(collection, f'browser-{group}-{engine}', ARTIFACTS / 'shards' / f'{group}-{engine}')
        assignments = partition_plan()
        evidence = []
        partition_reports = []
        for path in reports:
            report = json.loads(path.read_text())
            report['junit']['path'] = str(path.parent / report['junit']['path'])
            evidence.append(report)
            partition_reports.append((path.parent.parent.name, path.parent.name, report))
        PARTITIONS.verify_reports(assignments, partition_reports)
        result = module.aggregate([json.loads(path.read_text()) for path in inventories], evidence)
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(filter(None, files))}
        tree_digest = hashlib.sha256(json.dumps(hashes, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        if result['source_identity'] != {'head': head, 'tree_sha256': tree_digest, 'files': hashes}:
            raise ValueError('Browser receipts do not qualify this Git candidate')
        commands_spec = importlib.util.spec_from_file_location('publication_commands', TESTS / 'execution/publication_gate.py')
        commands = importlib.util.module_from_spec(commands_spec)
        commands_spec.loader.exec_module(commands)
        result['publication_commands'] = commands.verify(ARTIFACTS / 'publication-commands',
            workflow=collection.inputs['commands'].workflow_identity() if collection is not None else None)
        controls_spec = importlib.util.spec_from_file_location('renderer_controls', TESTS / 'execution/renderer_controls.py')
        controls = importlib.util.module_from_spec(controls_spec)
        controls_spec.loader.exec_module(controls)
        if collection is None:
            result['renderer_controls'] = controls.verify_groups(ARTIFACTS / 'renderer-controls')
        else:
            result['renderer_controls'] = controls.verify_groups(ARTIFACTS / 'renderer-controls',
                workflows={group: collection.inputs['renderer-' + group].workflow_identity() for group in controls.GROUPS})
        persisted = persisted_reader()
        cached = persisted.verify(ARTIFACTS / 'persisted-reader')
        if collection is not None:
            controllers.verify_execution(collection, 'persisted', ARTIFACTS / 'persisted-reader')
        if cached['source_identity'] != result['source_identity']:
            raise ValueError('Cached reader receipt does not qualify this Git candidate')
        result['persisted_native_reader'] = cached
        result['producer_envelope'] = producer
        result['browser_partitions'] = {f'{group}/{suite}': names for (group, suite), names in assignments.items()}
        result['inputs'] = [{'path': str(path.relative_to(ARTIFACTS)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in inventories + reports]
        if collection is not None:
            result['workflow_input_admission'] = collection.export_record()
    except (ValueError, KeyError, OSError, TypeError, ET.ParseError) as error:
        result = {'schema': 1, 'status': 'failed', 'error': str(error)}
    write_json(output, result)
    print(f"Navigation qualification: {result['status']}: {result.get('executed_cases', result.get('error'))}")
    if result['status'] != 'passed':
        raise ValueError(result['error'])


def persisted_reader():
    return load_module(TESTS / 'execution/persisted_reader.py', 'persisted_reader_gate')


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'run', 'aggregate'))
    parser.add_argument('--group', choices=GROUPS)
    parser.add_argument('--engine', choices=ENGINES)
    args = parser.parse_args()
    if args.operation == 'run' and (not args.group or not args.engine):
        parser.error('Browser execution requires an assigned group and engine')
    try:
        if args.operation == 'prepare':
            prepare()
        elif args.operation == 'run':
            run(args.group, args.engine)
        else:
            aggregate()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'Browser gate failed: {error}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
