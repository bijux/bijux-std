"""Execute and independently verify the isolated renderer command qualification."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
COMMANDS = ROOT / 'tests/bijux-docs/generated/commands'
LOCK = ROOT / 'tests/bijux-docs/generated/requirements.lock.txt'
MODULE = 'test_publication_renderer_commands'
PRIMARY = MODULE + '.PublicationRendererCommandTests.'
EXPECTED_IDS = tuple(sorted((
    PRIMARY + 'test_actual_renderer_qualifies_supported_profile_or_rejects_unsupported_before_mutation',
    PRIMARY + 'test_runtime_admission_rejects_changed_owned_bundle_before_cleanup',
    MODULE + '.UnsupportedPublicationRendererCommandTests.test_unreviewed_profile_rejects_before_public_artifact_mutation',
)))
UNSUPPORTED = 'Renderer profile: unsupported environment; retain actual hosted fingerprints and review a source-owned profile'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def source_identity() -> dict:
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    files = {name: digest(ROOT / name) for name in sorted(set(filter(None, names)))}
    return {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'tree_sha256': hashlib.sha256(json.dumps(files, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest(), 'files': files}


def workflow_identity() -> dict:
    return {'workflow_run_id': os.environ.get('GITHUB_RUN_ID'), 'workflow_attempt': os.environ.get('GITHUB_RUN_ATTEMPT')}


def pins() -> dict:
    return dict(line.split('==', 1) for line in LOCK.read_text().splitlines() if line and not line.startswith('#'))


def runtime_identity() -> dict:
    versions = {name: importlib.metadata.version(name) for name in pins()}
    if versions != pins():
        raise ValueError('Selected fixture interpreter does not match the exact renderer lock')
    return {'scope': 'installed-exact-lock-fixture-interpreter', 'verification_only': True,
            'publication_approval': False, 'executable': sys.executable, 'executable_sha256': digest(Path(sys.executable)),
            'version': platform.python_version(), 'implementation': platform.python_implementation(),
            'system': platform.system(), 'machine': platform.machine(), 'distributions': versions, 'lock_sha256': digest(LOCK)}


def inventory(directory: Path) -> dict:
    if not directory.is_dir():
        return {}
    paths = sorted(directory.rglob('*'))
    if any(path.is_symlink() for path in paths):
        raise ValueError('Command evidence must not contain symlinks')
    return {path.relative_to(directory).as_posix(): digest(path) for path in paths if path.is_file()}


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def contained(output: Path, name: str) -> Path:
    relative = Path(name)
    if not name or relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe command artifact path')
    selected = output / relative
    if not selected.resolve().is_relative_to(output.resolve()):
        raise ValueError('Command artifact escapes its evidence root')
    return selected


def capture_case(test, destination: Path, facts: dict) -> None:
    repo = getattr(test, 'repo', None)
    facts['public_after'] = inventory(getattr(test, 'site', destination / 'missing'))
    if repo and (repo / 'artifacts').is_dir():
        shutil.copytree(repo / 'artifacts', destination / 'fixture-artifacts')
    retained = ROOT / 'artifacts/website-delivery/renderer-command-qualification' / test._testMethodName
    if retained.is_dir():
        shutil.copytree(retained, destination / 'renderer-evidence')
    if hasattr(test, 'shared'):
        for path in (test.shared / 'assets/javascripts').glob('material-search.*.js'):
            target = destination / 'source-inputs' / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


class CommandResult(unittest.TextTestResult):
    """Keep every actual result, including capture errors and nonpassing subtests."""
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.records = []
        self.started = {}

    def startTest(self, test):
        super().startTest(test)
        self.records.append({'id': test.id(), 'status': 'running', 'errors': []})
        self.started[test.id()] = time.monotonic()

    def stopTest(self, test):
        super().stopTest(test)
        self.records[-1]['seconds'] = time.monotonic() - self.started[test.id()]

    def record(self, test, status, error=None):
        row = next(row for row in reversed(self.records) if row['id'] == test.id())
        if row['status'] not in ('failed', 'error', 'skipped', 'unexpected-success'):
            row['status'] = status
        if error:
            row['errors'].append(self._exc_info_to_string(error, test))

    def addSuccess(self, test):
        super().addSuccess(test); self.record(test, 'passed')

    def addFailure(self, test, err):
        super().addFailure(test, err); self.record(test, 'failed', err)

    def addError(self, test, err):
        super().addError(test, err); self.record(test, 'error', err)

    def addSkip(self, test, reason):
        super().addSkip(test, reason); self.record(test, 'skipped')

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err); self.record(test, 'failed', err)

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test); self.record(test, 'unexpected-success')

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err:
            self.record(test, 'failed', err)


def execute(output: Path) -> dict:
    runtime_before = runtime_identity()
    suite = unittest.defaultTestLoader.discover(str(COMMANDS), pattern='test_*.py')
    cases = list(flatten(suite))
    if sorted(test.id() for test in cases) != list(EXPECTED_IDS):
        raise ValueError('Missing, duplicate or unexpected renderer command case')
    facts = {}
    for test in cases:
        destination = output / 'cases' / hashlib.sha256(test.id().encode()).hexdigest()
        destination.mkdir(parents=True)
        facts[test.id()] = {'id': test.id(), 'commands': [], 'public_before': {}, 'public_after': {}}
        method, cleanups = getattr(test, test._testMethodName), test.doCleanups
        def invoke(test=test, method=method):
            data = facts[test.id()]
            data['public_before'] = inventory(getattr(test, 'site', output / 'missing'))
            original = subprocess.run
            def observe(*args, **kwargs):
                result = original(*args, **kwargs)
                argv = args[0] if args else kwargs.get('args')
                if isinstance(argv, (tuple, list)) and argv and str(argv[0]) == 'make':
                    data['commands'].append({'argv': list(map(str, argv)), 'cwd': str(kwargs.get('cwd')),
                        'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
                return result
            subprocess.run = observe
            try:
                return method()
            finally:
                subprocess.run = original
        def preserve(test=test, destination=destination, cleanups=cleanups):
            try:
                capture_case(test, destination, facts[test.id()])
            except Exception:
                test._outcome.result.addError(test, sys.exc_info())
            return cleanups()
        setattr(test, test._testMethodName, invoke)
        test.doCleanups = preserve
    with (output / 'unittest.log').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=CommandResult).run(suite)
    for record in result.records:
        destination = output / 'cases' / hashlib.sha256(record['id'].encode()).hexdigest()
        data = {**facts[record['id']], **record}
        data['artifacts'] = inventory(destination)
        write_json(destination / 'case.json', data)
        record['receipt'] = str((destination / 'case.json').relative_to(output))
        record['receipt_sha256'] = digest(destination / 'case.json')
    return {'expected_ids': list(EXPECTED_IDS), 'executed': result.testsRun, 'cases': result.records,
            'failed': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
            'runtime_before': runtime_before, 'runtime_after': runtime_identity()}


def validate_case(case: dict, output: Path) -> None:
    path = contained(output, case['receipt'])
    if digest(path) != case['receipt_sha256']:
        raise ValueError('Command case receipt digest mismatch')
    data = json.loads(path.read_text())
    if data['id'] != case['id'] or data['status'] != 'passed' or data['errors']:
        raise ValueError('Nonpassing or mismatched command case')
    artifacts = inventory(path.parent)
    artifacts.pop('case.json', None)
    if data['artifacts'] != artifacts or not artifacts:
        raise ValueError('Missing, unexpected or corrupt command artifacts')
    if not data['public_before'] or not data['public_after']:
        raise ValueError('Command case lacks actual before/after public artifact inventories')
    commands = data['commands']
    if len(commands) != 1 or commands[0]['argv'] != ['make', 'docs-check']:
        raise ValueError('Command case did not execute its exact Make journey')
    command = commands[0]
    if 'test_runtime_admission_rejects' in case['id']:
        if command['returncode'] == 0 or 'differs from exact admitted source' not in command['stderr'] or data['public_before'] != data['public_after']:
            raise ValueError('Runtime rejection did not preserve the public artifact')
        return
    availability = json.loads((path.parent / 'renderer-evidence/profile-availability.json').read_text())
    if command['returncode']:
        if UNSUPPORTED not in command['stderr'] or availability.get('state') != 'unsupported-profile-rejected-before-public-mutation' or availability.get('positive_qualification_pending') is not True or availability.get('known_profile_positive_executed') is not False or data['public_before'] != data['public_after']:
            raise ValueError('Unsupported profile was not exactly rejected before mutation')
        for name in ('build-identity', 'csp', 'producer-reconstruction', 'site-verification'):
            receipt = json.loads((path.parent / f'fixture-artifacts/website-security/{name}.json').read_text())
            if receipt.get('passed') is not False or receipt.get('verification_only') is not True:
                raise ValueError('Unsupported profile retained a passing publication receipt')
    else:
        if 'test_unreviewed_profile' in case['id']:
            raise ValueError('Deliberate unsupported profile unexpectedly qualified')
        if availability.get('state') != 'known-verification-profile-qualified' or availability.get('known_profile_positive_executed') is not True or availability.get('publication_approval') is not False:
            raise ValueError('Known profile evidence has invalid qualification scope')
        root = path.parent / 'fixture-artifacts/website-security'
        build, csp, routes = (json.loads((root / f'{name}.json').read_text()) for name in ('build-identity', 'csp', 'site-verification'))
        if build.get('state') != 'complete' or routes.get('passed') is not True or routes.get('verification_only') is not True or routes.get('search_entries', 0) < 1 or len(build.get('bundle_sha256', '')) != 64 or build['bundle_sha256'] != csp.get('bundle_sha256') or build['bundle_sha256'] != routes.get('bundle_sha256'):
            raise ValueError('Known profile build, policy and route evidence disagree')


def verify(output: Path, current_source: dict | None = None, workflow: dict | None = None) -> dict:
    receipt = json.loads((output / 'command-receipt.json').read_text())
    source = source_identity() if current_source is None else current_source
    identity = workflow_identity() if workflow is None else workflow
    if receipt.get('schema') != 1 or receipt.get('status') != 'passed' or receipt.get('verification_only') is not True or receipt.get('publication_approval') is not False:
        raise ValueError('Publication command receipt is not passing verification evidence')
    if receipt.get('workflow') != identity or receipt.get('source_before') != source or receipt.get('source_after') != source:
        raise ValueError('Publication command workflow/current source identity mismatch')
    if receipt.get('child_exit') != 0 or receipt.get('expected_ids') != list(EXPECTED_IDS) or receipt.get('executed') != 3 or any(receipt.get(name) != 0 for name in ('failed', 'errors', 'skipped')):
        raise ValueError('Publication command execution accounting is incomplete')
    cases = receipt.get('cases', [])
    if sorted(case['id'] for case in cases) != list(EXPECTED_IDS) or any(case['status'] != 'passed' or case['errors'] for case in cases):
        raise ValueError('Missing, duplicate or nonpassing command case')
    runtime = receipt.get('runtime_before', {})
    if runtime != receipt.get('runtime_after') or runtime.get('scope') != 'installed-exact-lock-fixture-interpreter' or runtime.get('verification_only') is not True or runtime.get('publication_approval') is not False or runtime.get('distributions') != pins() or runtime.get('lock_sha256') != digest(LOCK) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', runtime.get('version', '')) or not re.fullmatch(r'[0-9a-f]{64}', runtime.get('executable_sha256', '')) or not runtime.get('executable') or not runtime.get('implementation') or not runtime.get('system') or not runtime.get('machine') or receipt.get('selected_python') != runtime.get('executable'):
        raise ValueError('Selected fixture runtime identity is incomplete or changed')
    for case in cases:
        validate_case(case, output)
    artifacts = inventory(output)
    artifacts.pop('command-receipt.json', None)
    if receipt.get('artifact_digests') != artifacts:
        raise ValueError('Missing, unexpected or corrupt command run artifacts')
    return receipt


def run(python: Path, output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise ValueError('Preserve existing command evidence; select an empty output directory')
    output.mkdir(parents=True, exist_ok=True)
    source, workflow = source_identity(), workflow_identity()
    started = time.monotonic()
    child = subprocess.run([str(python.absolute()), str(Path(__file__).resolve()), '_execute', '--output', str(output)], cwd=ROOT,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True)
    (output / 'runner.log').write_text(child.stdout + child.stderr)
    receipt = {'schema': 1, 'status': 'failed', 'verification_only': True, 'publication_approval': False,
        'workflow': workflow, 'source_before': source, 'source_after': source_identity(), 'child_exit': child.returncode,
        'selected_python': str(python.absolute()), 'seconds': time.monotonic() - started}
    child_receipt = output / 'execution.json'
    if child_receipt.exists():
        receipt.update(json.loads(child_receipt.read_text()))
    receipt['status'] = 'passed' if child.returncode == 0 else 'failed'
    receipt['artifact_digests'] = inventory(output)
    write_json(output / 'command-receipt.json', receipt)
    try:
        verify(output)
    except (ValueError, KeyError, OSError, TypeError) as error:
        receipt['status'], receipt['error'] = 'failed', str(error)
        write_json(output / 'command-receipt.json', receipt)
        raise ValueError(str(error)) from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('run', 'verify', '_execute'))
    parser.add_argument('--python', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.operation == 'run' and args.python is None:
        parser.error('Command execution requires its selected fixture interpreter')
    output = args.output.absolute()
    if not output.resolve().is_relative_to((ROOT / 'artifacts').resolve()):
        parser.error('Command outputs belong under repository artifacts/')
    try:
        if args.operation == '_execute':
            write_json(output / 'execution.json', execute(output))
        elif args.operation == 'run':
            run(args.python, output)
        else:
            verify(output)
    except (ValueError, KeyError, OSError, TypeError, importlib.metadata.PackageNotFoundError) as error:
        print(f'Publication command gate failed: {error}')
        return 1
    print('Publication command qualification: verified execution; no publication approval')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
