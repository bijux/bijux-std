"""Bind ordinary controller declarations to independently admitted recovery inputs.

Native jobs declare their actual execution and physically verified producer.
Those declarations are audit data. Only live source-owned API admission can
authorize retained inputs for a later collector.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / 'artifacts/bijux-docs'


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load(name: str):
    path = Path(__file__).with_name(name + '.py')
    data = path.read_bytes()
    dependencies = b''
    if name == 'workflow_collection':
        dependencies = b''.join(path.with_name(value + '.py').read_bytes()
                                for value in ('workflow_lineage', 'workflow_artifacts', 'workflow_jobs', 'browser_partitions'))
    key = 'bijux_controller_' + hashlib.sha256(str(path.resolve()).encode() + data + dependencies).hexdigest()
    if key not in sys.modules:
        module = ModuleType(key)
        module.__file__ = str(path)
        sys.modules[key] = module
        try:
            exec(compile(data, str(path), 'exec'), module.__dict__)
        except BaseException:
            sys.modules.pop(key, None)
            raise
    return sys.modules[key]


def recovery() -> bool:
    if os.environ.get('GITHUB_REPOSITORY') != 'bijux/bijux-std':
        return False
    attempt = os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    require(re.fullmatch(r'[1-9][0-9]*', attempt) is not None, 'Actual positive workflow attempt is required')
    return int(attempt) > 1


def collect(stage: str, *, caller=None):
    require(recovery(), 'Retained inputs require an owning-repository recovery execution')
    collection = load('workflow_collection')
    token = os.environ.get('GH_TOKEN')
    head = os.environ.get('EXPECTED_WORKFLOW_HEAD')
    require(isinstance(token, str) and bool(token), 'Read-only workflow token is required for recovery')
    require(isinstance(head, str) and re.fullmatch(r'[a-f0-9]{40}', head) is not None,
            'Actual full workflow source SHA is required for recovery')
    api = collection.LINEAGE.ARTIFACTS.GitHubAPI(os.environ['GITHUB_REPOSITORY'], token)
    def retain(record):
        folder = ARTIFACTS / 'collection'
        parent = collection._directory(folder)
        try:
            descriptor = os.open(stage + '.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=parent)
            with os.fdopen(descriptor, 'w') as stream:
                stream.write(json.dumps(record, indent=2) + '\n')
        finally:
            os.close(parent)
    identity = collection.context_from_environment(api, head)
    return collection.collect(api, identity, stage, ARTIFACTS, audit=retain, caller=caller, reconcile=True)


def producer_record(producer: dict) -> dict:
    path = ARTIFACTS / 'producer-envelope.json'
    data = path.read_bytes()
    require(json.loads(data) == producer, 'Physical producer envelope differs from verified input')
    return {key: producer[key] for key in ('source_head', 'workflow_run_id', 'workflow_attempt', 'artifact_digests')} | {
        'envelope_sha256': hashlib.sha256(data).hexdigest()}


def file_hashes(folder: Path) -> dict[str, str]:
    require(folder.is_dir() and not folder.is_symlink(), 'Execution output must be an owned directory')
    result = {}
    for path in sorted(folder.rglob('*')):
        require(not path.is_symlink(), 'Execution outputs cannot contain links')
        if path.is_file():
            result[str(path.relative_to(folder))] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            require(path.is_dir(), 'Execution output contains unsupported entries')
    return result


def require_collection(collection) -> None:
    try:
        owned = type(collection).__name__ == 'Collection' and Path(inspect.getfile(type(collection).__init__)).resolve() == Path(__file__).with_name('workflow_collection.py').resolve()
    except TypeError:
        owned = False
    require(owned, 'API-created source-owned collection is required')


def record_execution(folder: Path, role: str, producer: dict) -> dict | None:
    """Write a declaration after terminal-success; this never creates admission."""
    if os.environ.get('GITHUB_RUN_ID') is None and os.environ.get('GITHUB_RUN_ATTEMPT') is None:
        return None
    require(isinstance(role, str) and re.fullmatch(r'[a-z][a-z0-9-]*', role) is not None,
            'Canonical controller role is required')
    roles = load('workflow_collection').registry()
    require(role in roles and (role.startswith('browser-') or role.startswith('fault-') and role != 'fault-public'
                              or role == 'persisted'), 'Unknown native controller role')
    spec = roles[role]
    owner = ARTIFACTS / spec['destination']
    if spec['subtree'] is not None:
        owner /= spec['subtree']
    require(folder.absolute() == owner.absolute(), 'Execution declaration differs from canonical role destination')
    run, attempt = os.environ.get('GITHUB_RUN_ID'), os.environ.get('GITHUB_RUN_ATTEMPT')
    require(isinstance(run, str) and re.fullmatch(r'[1-9][0-9]*', run) is not None
            and isinstance(attempt, str) and re.fullmatch(r'[1-9][0-9]*', attempt) is not None,
            'Actual workflow execution identity is required')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    require(producer.get('source_head') == head, 'Producer does not bind this executor source')
    require(producer.get('workflow_run_id') == run, 'Producer does not bind this workflow run')
    require(isinstance(producer.get('workflow_attempt'), str)
            and re.fullmatch(r'[1-9][0-9]*', producer['workflow_attempt']) is not None
            and int(producer['workflow_attempt']) <= int(attempt), 'Producer attempt is invalid or newer than executor')
    require(folder.resolve().is_relative_to(ARTIFACTS.resolve()), 'Execution declaration belongs under owned artifacts')
    require(folder.absolute().is_relative_to(ARTIFACTS.absolute()), 'Execution path must belong to the canonical artifact tree')
    for ancestor in (folder, *folder.parents):
        require(not ancestor.is_symlink(), 'Execution path cannot traverse links')
        if ancestor == ARTIFACTS:
            break
    target = folder / 'execution.json'
    require(not target.exists() and not target.is_symlink(), 'Preserve existing execution declaration')
    record = {'schema': 1, 'executor': {'role': role, 'source_head': head,
              'workflow_run_id': run, 'workflow_attempt': attempt},
              'producer': producer_record(producer), 'files_sha256': file_hashes(folder)}
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(json.dumps(record, indent=2) + '\n')
    return record


def verify_execution(collection, role: str, folder: Path) -> dict:
    require_collection(collection)
    data = (folder / 'execution.json').read_bytes()
    collection.inputs[role].verify_file(collection.execution_name(role), data)
    record = json.loads(data)
    collection.verify_execution(role, record)
    hashes = file_hashes(folder)
    hashes.pop('execution.json', None)
    require(record['files_sha256'] == hashes, 'Materialized execution body differs from admitted input')
    return record


def aggregate() -> None:
    collection = collect('navigation', caller='navigation')
    # Each controller still rederives its own native/config/runtime duties.
    # Source admission replaces stale dependency booleans, never those duties.
    load('frontend_faults').aggregate(collection=collection)
    load('browser_gate').aggregate(collection=collection)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('aggregate',))
    parser.parse_args()
    try:
        aggregate()
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as error:
        print('Workflow controller qualification failed:', error)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
