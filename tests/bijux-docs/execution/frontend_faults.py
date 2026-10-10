"""Require real frontend faults to be rejected by browser and artifact gates."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / 'tests/bijux-docs'
OUT = ROOT / 'artifacts/bijux-docs/frontend-faults'
ENGINES = ('chromium', 'firefox', 'webkit')
FAULT_CONTROLS = {
    'unmodified production ribbons and ordinary drawer input qualify': None,
    'painted hidden ribbons fail the real navigation assertion': 'Hidden navigation must not paint',
    'blocked ordinary toggle fails actual opened-state acceptance': 'Ordinary navigation toggle must actually open',
    'trusted palette activation rejects uncaught runtime failure': 'bijux frontend runtime fault witness',
}
FAULT_ERRORS = tuple(error for error in FAULT_CONTROLS.values() if error)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def hashes(root: Path):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def source():
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    files = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
             for name in sorted(filter(None, names))}
    return {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'files': files, 'tree_sha256': hashlib.sha256(json.dumps(files, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()}


def execute(argv, output: Path, env=None):
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w') as stream:
        result = subprocess.run(argv, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    return {'argv': [str(x) for x in argv], 'exit': result.returncode,
            'log': str(output), 'log_sha256': hashlib.sha256(output.read_bytes()).hexdigest()}


def validate_pair(clean: dict, fault: dict):
    for key in ('source_identity', 'fixture_identity', 'canonical_projects',
                'assigned_project_names', 'expected_cases'):
        if clean.get(key) != fault.get(key) or clean.get(key) is None:
            raise ValueError('Fault comparison identity differs: ' + key)
    if clean.get('status') != 'passed' or fault.get('status') != 'failed':
        raise ValueError('Clean/fault gate statuses are not pass/fail')
    for report in (clean, fault):
        if report.get('qualification_kind') != 'assigned_engine_shard':
            raise ValueError('Assigned fault engine receipt required')
        rows = report['results']
        if len(rows) != 4 or len({row['case_id'] for row in rows}) != 4:
            raise ValueError('Exactly four unique fault controls required per engine')
        if {row['case_id'] for row in rows} != {case['id'] for case in report['expected_cases']}:
            raise ValueError('Executed fault IDs differ from exact expected cases')
        if any(row['retry'] or row['status'] not in ('passed', 'failed') for row in rows):
            raise ValueError('Skipped, retried or nonterminal fault control')
        for row in rows:
            versions = [x['description'] for x in row['annotations'] if x['type'] == 'browser-version']
            if len(versions) != 1 or not versions[0]:
                raise ValueError('Exact actual engine version required')
    for report in (clean, fault):
        data = Path(report['junit']['path']).read_bytes()
        if hashlib.sha256(data).hexdigest() != report['junit']['sha256']:
            raise ValueError('Fault JUnit digest changed')
        xml = ET.fromstring(data)
        expected_failures = 0 if report is clean else 3
        if xml.tag != 'testsuites' or int(xml.get('tests', '-1')) != 4 or int(xml.get('failures', '-1')) != expected_failures or any(int(xml.get(key, '-1')) for key in ('skipped', 'errors')) or len(xml.findall('.//testcase')) != 4 or len(xml.findall('.//failure')) != expected_failures:
            raise ValueError('Fault JUnit execution/status differs')
    if any(row['status'] != 'passed' or row['errors'] for row in clean['results']):
        raise ValueError('Clean controls did not all pass')
    expected = {case['id']: case for case in fault['expected_cases']}
    if len(expected) != len(FAULT_CONTROLS) or {case.get('title') for case in expected.values()} != set(FAULT_CONTROLS):
        raise ValueError('Exact named frontend fault controls are required')
    for row in fault['results']:
        title = expected[row['case_id']]['title']
        error = FAULT_CONTROLS[title]
        if error is None:
            if row['status'] != 'passed' or row['errors']:
                raise ValueError('Unmodified ordinary-input control must still pass')
        elif row['status'] != 'failed' or not any(error in message for message in row['errors']):
            raise ValueError('Intended real fault must fail its exact named case: ' + title)



def browser(engine: str):
    gate = load(TESTS / 'execution/browser_gate.py', 'browser_gate')
    controllers = gate.workflow_controllers()
    collection = controllers.collect('producer', caller='fault-' + engine) if controllers.retained_producer() else None
    producer = gate.verify_producer_envelope(collection.producer if collection is not None else None)
    gate.unpack()
    gate.install_browser_runtime()
    folder = OUT / engine
    before = source()
    config = TESTS / 'playwright.frontend-faults.config.js'
    commands = []
    inventory = folder / 'inventory.json'
    env = gate.environment('navigation', folder / 'inventory')
    result = execute(['node', str(TESTS / 'reporting/inventory.js'), '--config', str(config),
                      '--output', str(inventory)], folder / 'inventory.log', env)
    commands.append(result)
    if result['exit']:
        raise ValueError('Fault inventory failed')
    for mode in ('clean', 'fault'):
        output = folder / mode
        env = gate.environment('navigation', output)
        env.update(BIJUX_UI_BROWSER_ENGINE=engine, BIJUX_FRONTEND_FAULT_MODE=mode)
        result = execute([gate.playwright(), 'test', '--config', str(config)], output / 'browser.log', env)
        commands.append(result)
        if result['exit'] != (0 if mode == 'clean' else 1):
            raise ValueError('Unexpected actual browser exit for ' + mode)
    pair = [json.loads((folder / mode / 'qualification.json').read_text()) for mode in ('clean', 'fault')]
    for mode, report in zip(('clean', 'fault'), pair):
        if report['source_identity'] != before:
            raise ValueError('Browser report does not qualify actual current source')
        report['junit']['path'] = str(folder / mode / report['junit']['path'])
    validate_pair(*pair)
    if source() != before:
        raise ValueError('Source changed during fault execution')
    write(folder / 'receipt.json', {'schema': 1, 'source': before, 'engine': engine,
          'workflow_run_id': os.environ.get('GITHUB_RUN_ID'),
          'workflow_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
          'commands': commands, 'files': hashes(folder), 'status': 'passed'})
    controllers.record_execution(folder, 'fault-' + engine, producer)


def public(python: Path):
    folder = OUT / 'public'
    generated = folder / 'generated'
    before = source()
    commands = [execute([str(python), '-B', str(TESTS / 'generated/build.py'),
                        '--output', str(generated), '--base-url', 'https://bijux.io'], folder / 'build.log')]
    if commands[-1]['exit']:
        raise ValueError('Actual public-origin Material render failed')
    # Select the actual independent Hub site; merged fixture sitemap/index is not one public site.
    manifest = json.loads((generated / 'manifest.json').read_text())
    if manifest['source_sha'] != before['head'] or any(before['files'].get('shared/bijux-docs/' + name) != digest for name, digest in manifest['source_files'].items()):
        raise ValueError('Public producer source does not bind actual current source')
    baseline = generated / 'inputs/hub/site'
    original = hashes(baseline)
    registry = json.loads((ROOT / 'shared/bijux-docs/config/hub-links.json').read_text())
    entries = registry if isinstance(registry, list) else registry['hub_links']
    registry = [{**entry, 'url': 'https://bijux.io/' + ('' if entry['key'] == 'bijux' else entry['key'] + '/')}
                for entry in entries]
    links = folder / 'hub-links.json'
    write(links, registry)
    for mode in ('clean', 'missing-index', 'missing-worker', 'loopback-canonical', 'loopback-sitemap'):
        site = folder / mode / 'site'
        shutil.copytree(baseline, site)
        if mode == 'missing-index':
            (site / 'search/search_index.json').unlink()
        elif mode == 'missing-worker':
            workers = list((site / 'assets/javascripts/workers').glob('search.*.min.js'))
            if len(workers) != 1:
                raise ValueError('Require exact current configured Material search worker')
            workers[0].unlink()
        elif mode == 'loopback-canonical':
            file = site / 'index.html'
            text, count = re.subn(r'(<link[^>]*rel="canonical"[^>]*href=")https://bijux.io/',
                                 r'\g<1>http://127.0.0.1:4173/', file.read_text())
            if count != 1:
                raise ValueError('Require one real current homepage canonical')
            file.write_text(text)
        elif mode == 'loopback-sitemap':
            file = site / 'sitemap.xml'
            text = file.read_text()
            if text.count('<loc>https://bijux.io/</loc>') != 1:
                raise ValueError('Require exact real Hub sitemap root')
            file.write_text(text.replace('<loc>https://bijux.io/</loc>', '<loc>http://127.0.0.1:4173/</loc>', 1))
        changed = hashes(site)
        delta = [name for name in sorted(set(original) | set(changed)) if original.get(name) != changed.get(name)]
        if len(delta) != (0 if mode == 'clean' else 1):
            raise ValueError('A controlled fault must change exactly one delivered file')
        report = folder / mode / 'validation.json'
        result = execute([str(python), '-B', str(ROOT / 'shared/bijux-docs/tooling/quality/validate_site_routes.py'),
                          '--repo-root', str(ROOT), '--site-dir', str(site), '--site-url', 'https://bijux.io/',
                          '--hub-links', str(links), '--output', str(report)], folder / mode / 'validator.log')
        commands.append(result)
        data = json.loads(report.read_text())
        if result['exit'] != (0 if mode == 'clean' else 1) or data['result'] != ('pass' if mode == 'clean' else 'fail'):
            raise ValueError('Artifact validator did not reject the actual fault: ' + mode)
        expected = {'missing-index': 'Search index is absent', 'missing-worker': 'configured search worker is absent',
                    'loopback-canonical': 'canonical', 'loopback-sitemap': 'sitemap'}.get(mode)
        if expected and not any(expected.lower() in error.lower() for error in data['errors']):
            raise ValueError('Unexpected artifact failure reason: ' + mode)
        write(folder / mode / 'mutation.json', {'baseline': original, 'actual': changed, 'changed_paths': delta})
    if source() != before:
        raise ValueError('Source changed during public fault execution')
    write(folder / 'receipt.json', {'schema': 1, 'source': before, 'status': 'passed',
          'workflow_run_id': os.environ.get('GITHUB_RUN_ID'), 'workflow_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
          'verification_only': True, 'publication_admission': False, 'commands': commands, 'files': hashes(folder)})


def aggregate(collection=None):
    if collection is not None:
        load(TESTS / 'execution/workflow_controllers.py', 'fault_workflow_controllers').require_collection(collection)
    current = source()
    inventories, clean, fault = [], [], []
    for owner in (*ENGINES, 'public'):
        folder = OUT / owner
        receipt = json.loads((folder / 'receipt.json').read_text())
        identity = collection.inputs['fault-public' if owner == 'public' else 'fault-' + owner].workflow_identity() if collection is not None else {
            'workflow_run_id': os.environ.get('GITHUB_RUN_ID'), 'workflow_attempt': os.environ.get('GITHUB_RUN_ATTEMPT')}
        if receipt['source'] != current or receipt['status'] != 'passed' or any(receipt[key] != value for key, value in identity.items()):
            raise ValueError('Current source/run fault receipt is required: ' + owner)
        for name, expected in receipt['files'].items():
            if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
                raise ValueError('Fault artifact digest changed: ' + owner + '/' + name)
        if owner == 'public':
            continue
        if collection is not None:
            load(TESTS / 'execution/workflow_controllers.py', 'fault_workflow_controllers').verify_execution(collection, 'fault-' + owner, folder)
        inventory = json.loads((folder / 'inventory.json').read_text())
        if inventory['source_identity'] != current:
            raise ValueError('Fault inventory does not bind current source')
        if inventories and inventory != inventories[0]:
            raise ValueError('Fault inventory differs between engine jobs')
        inventories = [inventory]
        reports = []
        for mode in ('clean', 'fault'):
            report = json.loads((folder / mode / 'qualification.json').read_text())
            if report['source_identity'] != current:
                raise ValueError('Fault report does not bind current source')
            report['junit']['path'] = str(folder / mode / report['junit']['path'])
            reports.append(report)
        validate_pair(*reports)
        clean.append(reports[0]); fault.append(reports[1])
    qualifier = load(TESTS / 'reporting/aggregate.py', 'frontend_fault_aggregation')
    positive = qualifier.aggregate(inventories, clean)
    try:
        qualifier.aggregate(inventories, fault)
    except ValueError as error:
        if str(error) != 'Failed or non-shard evidence':
            raise
        rejection = str(error)
    else:
        raise ValueError('Canonical aggregator accepted actual failed fault reports')
    write(OUT / 'qualification.json', {'schema': 1, 'status': 'passed', 'source': current,
          'clean_browser_cases': positive['executed_cases'], 'fault_browser_cases': 12,
          'intentional_browser_failures': 9, 'aggregate_rejection': rejection,
          'public_controls': 5, 'publication_admission': False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('browser', 'public', 'aggregate'))
    parser.add_argument('--engine', choices=ENGINES)
    parser.add_argument('--python', type=Path)
    args = parser.parse_args()
    if args.operation == 'browser' and not args.engine or args.operation == 'public' and not args.python:
        parser.error('The selected operation needs its exact engine or renderer')
    try:
        if args.operation == 'browser': browser(args.engine)
        elif args.operation == 'public': public(args.python)
        else: aggregate()
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError, subprocess.CalledProcessError) as error:
        print('Frontend fault gate failed:', error)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
