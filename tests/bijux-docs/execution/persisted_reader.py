"""Require actual cached Chromium journeys without weakening the engine matrix."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / 'tests/bijux-docs'
ARTIFACTS = ROOT / 'artifacts/bijux-docs'
SUITE = 'persisted-reader-history'
SCOPE = 'persisted_native_diagram_reader_chromium'
PROJECTS = ('chromium-reader-narrow', 'chromium-reader-phone', 'chromium-reader-desktop')
JOB = 'std / persisted native reader / chromium'


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_paths() -> tuple[Path, ...]:
    return (Path(__file__), TESTS / f'playwright.{SUITE}.config.js',
            TESTS / f'ui/generated-specs/{SUITE}.spec.js')


def annotation(result: dict, name: str) -> dict:
    values = [item['description'] for item in result['annotations'] if item['type'] == name]
    require(len(values) == 1, 'Missing or duplicate persisted runtime/journey evidence')
    value = json.loads(values[0])
    require(isinstance(value, dict), 'Invalid persisted runtime/journey evidence')
    return value


def qualify_journey(result: dict) -> dict:
    runtime = annotation(result, 'persisted-browser-runtime')
    args = runtime['commandLine']['arguments']
    require(isinstance(args, list) and bool(args) and all(isinstance(item, str) for item in args),
            'Actual browser command line is required')
    executable = args[0]
    require(Path(executable).name.lower() in {'chrome', 'chrome.exe', 'chromium', 'google chrome for testing'}
            and not re.search('headless[_-]shell', executable, re.I), 'Full Chromium executable is required')
    require('--disable-back-forward-cache' not in args, 'Browser cache was disabled by its actual arguments')
    require(bool(re.fullmatch('[a-f0-9]{64}', runtime['executableSha256'])), 'Physical executable digest is required')
    versions = [item['description'] for item in result['annotations'] if item['type'] == 'browser-version']
    require(len(versions) == 1 and runtime['version']['product'] == 'Chrome/' + versions[0],
            'Actual Chromium protocol version is required')
    journey = annotation(result, 'persisted-native-journey')
    diagnostics = annotation(result, 'persisted-cache-diagnostics')
    require(set(diagnostics) == {'rejections', 'lifecycle'}
            and diagnostics['rejections'] == [] and isinstance(diagnostics['lifecycle'], list)
            and all(isinstance(event, dict) and isinstance(event.get('frameId'), str)
                    and isinstance(event.get('loaderId'), str) and isinstance(event.get('name'), str)
                    and type(event.get('timestamp')) in (int, float) for event in diagnostics['lifecycle']),
            'Missing native cache diagnostics or actual browser cache rejection')
    require(len({event['loaderId'] for event in diagnostics['lifecycle'] if event['name'] == 'load'}) >= 2,
            'Browser load observations for both native documents are required')
    departure, initial, target = (journey[key] for key in ('departure', 'initial', 'target'))
    require(departure['trusted'] is True and departure['type'] == 'click', 'Trusted native departure is required')
    require(isinstance(departure['entryKey'], str) and bool(departure['entryKey'])
            and departure['entryKey'] == initial['entryKey'] and departure['href'] == initial['href'],
            'Actual departing reader entry identity is required')
    require(initial['sources'] == departure['sources'] and len(initial['sources']) == 5
            and all(isinstance(value, str) and value for value in initial['sources']), 'Exact authored sources are required')
    require(departure['disclosures'] == [True, False, False, False, False], 'Actual source inspection is required')
    require(journey['external'] == [], 'Unexpected external provider requests')
    cycles = [record for record in journey['records'] if record['label'] == 'cached native cycle']
    require(len(cycles) == 2 and [record['cycle'] for record in cycles] == [0, 1], 'Two unique cached native cycles are required')
    reader_sequence, target_sequence = departure['sequence'], target['sequence']
    require(type(reader_sequence) is int and reader_sequence > 0 and type(target_sequence) is int and target_sequence > 0,
            'Actual departure lifecycle sequence is required')
    for cycle in cycles:
        returned, forward = cycle['returned'], cycle['forward']
        for event, expected in ((cycle['back'], initial), (cycle['shown'], target)):
            require(event['type'] == 'pageshow' and event['trusted'] is True and event['persisted'] is True,
                    'Actual trusted persisted pageshow is required')
            require(event['entryKey'] == expected['entryKey'] and event['href'] == expected['href']
                    and event['timeOrigin'] == expected['timeOrigin'], 'Cached realm/entry/URL identity differs')
        require(type(cycle['back']['sequence']) is int and cycle['back']['sequence'] > reader_sequence
                and type(cycle['shown']['sequence']) is int and cycle['shown']['sequence'] > target_sequence,
                'Replayed lifecycle cannot stand in for a new native cached return')
        reader_sequence, target_sequence = cycle['back']['sequence'], cycle['shown']['sequence']
        require(returned['entryKey'] == initial['entryKey'] and returned['timeOrigin'] == initial['timeOrigin']
                and returned['href'] == initial['href'], 'Returned reader realm/entry/URL differs')
        require(forward['entryKey'] == target['entryKey'] and forward['timeOrigin'] == target['timeOrigin']
                and forward['href'] == target['href'], 'Forward realm/entry/URL differs')
        require(returned['sources'] == initial['sources'] and returned['disclosures'] == departure['disclosures'],
                'Cached authored source or inspection differs')
        require(type(returned['top']) in (int, float) and type(departure['top']) in (int, float)
                and abs(returned['top'] - departure['top']) < 1
                and cycle['absoluteOffset'] == abs(returned['top'] - departure['top']), 'Cached offset reached the original one-pixel limit')
    return {'project': result['project'], 'cycles': 2, 'runtime': runtime, 'journey': journey,
            'cache_diagnostics': diagnostics}


def current_source_identity() -> dict:
    owner = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, text=True).strip()
    require(Path(owner) == ROOT, 'Dedicated cached reader source must own its Git root')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT, text=True).split('\0')
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(filter(None, names))}
    tree = hashlib.sha256(json.dumps(hashes, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    return {'head': head, 'tree_sha256': tree, 'files': hashes}


def derive(output: Path, inventory_path: Path) -> dict:
    inventory = json.loads(inventory_path.read_text())
    report_path = output / 'qualification.json'
    report = json.loads(report_path.read_text())
    canonical = [{'name': name, 'engine': 'chromium', 'count': 1} for name in PROJECTS]
    require(inventory['qualification_scope'] == SCOPE and report['qualification_scope'] == SCOPE
            and inventory['canonical_projects'] == canonical, 'Dedicated Chromium capability inventory differs')
    junit = Path(report['junit']['path'])
    require(not junit.is_absolute() and '..' not in junit.parts and not (output / junit).is_symlink(),
            'JUnit must belong to the dedicated artifact owner')
    report['junit']['path'] = str(output / junit)
    aggregate = load(TESTS / 'reporting/aggregate.py', 'persisted_browser_aggregation')
    qualified = aggregate.aggregate([inventory], [report])
    require(qualified['source_identity'] == current_source_identity(), 'Cached evidence does not qualify the actual source tree')
    observations = [qualify_journey(result) for result in report['results']]
    require({item['project'] for item in observations} == set(PROJECTS), 'Missing dedicated viewport journey')
    inputs = {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in (report_path, output / junit)}
    inputs['canonical_inventory'] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    return {'schema': 1, 'status': 'passed', 'qualification_scope': SCOPE,
            'source_identity': qualified['source_identity'], 'fixture_identity': inventory['fixture_identity'],
            'executed_cases': qualified['executed_cases'], 'cached_native_cycles': 6,
            'observations': observations, 'inputs': inputs,
            'execution_sources': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths()},
            'limits': ['Chromium cached native journeys do not qualify Firefox/WebKit cache capability, physical devices or live production. Material may replace its serialized state marker.']}


def verify(output: Path) -> dict:
    retained = json.loads((output / 'receipt.json').read_text())
    current = derive(output, ARTIFACTS / 'inventories' / f'{SUITE}.json')
    require(retained == current, 'Retained cached reader receipt differs from physical source-bound evidence')
    return current


def run() -> None:
    require(not any(name in os.environ for name in ('BIJUX_UI_BROWSER_ENGINE', 'BIJUX_UI_PROJECTS', 'BIJUX_UI_PROFILE')),
            'Dedicated cached reader owner does not admit external project selection')
    gate = load(TESTS / 'execution/browser_gate.py', 'persisted_fixture_gate')
    controllers = gate.workflow_controllers()
    collection = controllers.collect('producer', caller='persisted') if controllers.recovery() else None
    producer = gate.verify_producer_envelope(collection.producer if collection is not None else None)
    gate.unpack()
    gate.install_browser_runtime()
    output = ARTIFACTS / 'persisted-reader'
    output.mkdir(parents=True, exist_ok=True)
    env = gate.environment(SUITE, output)
    env['BIJUX_UI_BROWSER_ENGINE'] = 'chromium'
    command = [gate.playwright(), 'test', '--config', str(TESTS / f'playwright.{SUITE}.config.js')]
    process = subprocess.run(command, cwd=ROOT, env=env)
    try:
        require(process.returncode == 0, 'Dedicated cached reader process was not terminal-success')
        receipt = derive(output, ARTIFACTS / 'inventories' / f'{SUITE}.json')
    except (ValueError, KeyError, OSError, TypeError, ET.ParseError) as error:
        receipt = {'schema': 1, 'status': 'failed', 'error': str(error), 'terminal_exit': process.returncode}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    require(receipt['status'] == 'passed', receipt.get('error', 'Cached reader qualification failed'))
    controllers.record_execution(output, 'persisted', producer)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('run', 'verify'))
    args = parser.parse_args()
    try:
        if args.operation == 'run':
            run()
        else:
            verify(ARTIFACTS / 'persisted-reader')
    except (ValueError, KeyError, OSError, TypeError, ET.ParseError, subprocess.CalledProcessError) as error:
        print('Persisted native reader qualification failed:', error)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
