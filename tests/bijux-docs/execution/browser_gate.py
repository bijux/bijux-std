"""Build once, execute bounded engine journeys and require complete coverage."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / 'tests/bijux-docs'
ARTIFACTS = ROOT / 'artifacts/bijux-docs'
GROUPS = {
    'navigation': ('navigation', 'drawer', 'preferences', 'repository'),
    'search': ('search', 'search-invoker'),
    'reader': ('native-navigation', 'reader'),
    'rendering': ('diagrams', 'contrast'),
}
ENGINES = ('chromium', 'firefox', 'webkit')
SUITES = tuple(suite for group in GROUPS.values() for suite in group)


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


def prepare() -> None:
    if 'BIJUX_UI_BROWSER_ENGINE' in os.environ or 'BIJUX_UI_PROJECTS' in os.environ:
        raise ValueError('Canonical inventory must not select projects')
    inventory = ARTIFACTS / 'inventories'
    for suite in SUITES:
        env = environment(suite, inventory / suite)
        config = TESTS / f'playwright.{suite}.config.js'
        subprocess.run(['node', str(TESTS / 'reporting/inventory.js'), '--config', str(config), '--output', str(inventory / f'{suite}.json')], cwd=ROOT, env=env, check=True)
    archive = ARTIFACTS / 'browser-fixtures.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=1) as bundle:
        for directory in ('generated', 'contrast-generated'):
            for name in ('manifest.json', 'site'):
                path = ARTIFACTS / directory / name
                bundle.add(path, arcname=str(path.relative_to(ARTIFACTS)))
    (ARTIFACTS / 'browser-fixtures.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '\n')


def unpack() -> None:
    archive = ARTIFACTS / 'browser-fixtures.tar.gz'
    expected = (ARTIFACTS / 'browser-fixtures.sha256').read_text().strip()
    if len(expected) != 64 or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError('Fixture archive digest mismatch')
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            name = Path(member.name)
            if name.is_absolute() or '..' in name.parts or not name.parts or name.parts[0] not in ('generated', 'contrast-generated') or not (member.isfile() or member.isdir()):
                raise ValueError('Unexpected fixture archive member')
        bundle.extractall(ARTIFACTS, filter='data')


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
    unpack()
    install_browser_runtime()
    failed = []
    for suite in GROUPS[group]:
        output = ARTIFACTS / 'shards' / f'{group}-{engine}' / suite
        output.mkdir(parents=True, exist_ok=True)
        env = environment(suite, output)
        env['BIJUX_UI_BROWSER_ENGINE'] = engine
        result = subprocess.run([playwright(), 'test', '--config', str(TESTS / f'playwright.{suite}.config.js')], cwd=ROOT, env=env)
        if result.returncode:
            failed.append(suite)
    if failed:
        raise ValueError('Browser qualification failed: ' + ', '.join(failed))


def aggregate() -> None:
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
        if len(actual) != len(expected) or set(actual) != expected:
            raise ValueError('Missing, duplicate or unexpected browser shard receipt')
        evidence = []
        for path in reports:
            report = json.loads(path.read_text())
            report['junit']['path'] = str(path.parent / report['junit']['path'])
            evidence.append(report)
        result = module.aggregate([json.loads(path.read_text()) for path in inventories], evidence)
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(filter(None, files))}
        tree_digest = hashlib.sha256(json.dumps(hashes, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        if result['source_identity'] != {'head': head, 'tree_sha256': tree_digest, 'files': hashes}:
            raise ValueError('Browser receipts do not qualify this Git candidate')
        result['inputs'] = [{'path': str(path.relative_to(ARTIFACTS)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in inventories + reports]
    except (ValueError, KeyError, OSError, TypeError, ET.ParseError) as error:
        result = {'schema': 1, 'status': 'failed', 'error': str(error)}
    write_json(output, result)
    print(f"Navigation qualification: {result['status']}: {result.get('executed_cases', result.get('error'))}")
    if result['status'] != 'passed':
        raise ValueError(result['error'])


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
