"""Collect finite workflow-owned inputs without merging unverified archives.

Source observations and inputs are process-local capabilities. Execution records
are declarations until compared with independently admitted API owners and bytes.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
EXECUTION = Path(__file__).resolve().parent
LINEAGE = ModuleType('bijux_collection_lineage')
LINEAGE.__file__ = str(EXECUTION / 'workflow_lineage.py')
exec(compile(Path(LINEAGE.__file__).read_bytes(), LINEAGE.__file__, 'exec'), LINEAGE.__dict__)
require = LINEAGE.require
_CREATED = object()


def registry() -> dict:
    """The checked-in partition declarations own the complete finite role set."""
    partitions = ModuleType('bijux_collection_partitions')
    partitions.__file__ = str(EXECUTION / 'browser_partitions.py')
    exec(compile(Path(partitions.__file__).read_bytes(), partitions.__file__, 'exec'), partitions.__dict__)
    tree = ast.parse((EXECUTION / 'renderer_controls.py').read_bytes())
    declarations = [node.value for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == 'GROUPS' for target in node.targets)]
    require(len(declarations) == 1, 'Exact renderer group declaration is required')
    renderers = ast.literal_eval(declarations[0])
    require(isinstance(renderers, tuple) and bool(renderers) and len(set(renderers)) == len(renderers)
            and all(re.fullmatch(r'[a-z][a-z0-9-]*', group) for group in renderers), 'Invalid renderer groups')
    roles = {}
    def add(role, job, prefix, upload, destination, subtree=None):
        require(role not in roles, 'Duplicate collection role')
        roles[role] = {'job_name': job, 'artifact_prefix': prefix, 'upload_step': upload,
                       'destination': destination, 'subtree': subtree}
    add('producer', 'std / navigation fixtures', 'docs-navigation-fixtures',
        'Retain source-bound fixtures and canonical case inventory', '')
    for group in partitions.GROUPS:
        for engine in partitions.ENGINES:
            owner = group + '-' + engine
            add('browser-' + owner, f'std / navigation {group} / {engine}', 'docs-navigation-' + owner,
                'Retain exact shard receipts and failure diagnostics', 'shards', owner)
    for group in renderers:
        add('renderer-' + group, 'std / renderer controls / ' + group, 'docs-renderer-controls-' + group,
            'Retain native unit events and physical runtime receipts', 'renderer-controls', group)
    add('commands', 'std / publication commands', 'docs-publication-commands',
        'Retain command receipts and mutation witnesses', 'publication-commands')
    add('persisted', 'std / persisted native reader / chromium', 'docs-persisted-native-reader',
        'Retain native cached reader evidence and failures', 'persisted-reader')
    for engine in partitions.ENGINES:
        add('fault-' + engine, 'std / frontend fault controls / ' + engine, 'docs-frontend-faults-browser-' + engine,
            'Retain intentional failure reports and clean controls', 'frontend-faults', engine)
    add('fault-public', 'std / frontend public artifact fault controls', 'docs-frontend-faults-public',
        'Retain real public fixture and mutated artifact receipts', 'frontend-faults/public')
    require(len(roles) <= LINEAGE.ARTIFACTS.MAX_ROLES
            and len({spec['job_name'] for spec in roles.values()}) == len(roles), 'Invalid collection ownership union')
    return roles


def checkout_state() -> dict:
    """Only the actual clean tracked checkout can consume API tree authority."""
    git = lambda *args: subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    require(Path(git('rev-parse', '--show-toplevel')).resolve() == ROOT.resolve(), 'Actual Git root differs from execution source')
    require(not git('status', '--porcelain', '--untracked-files=no'), 'Tracked checkout is dirty')
    closure = [str(path.relative_to(ROOT)) for path in (Path(__file__), EXECUTION / 'workflow_lineage.py',
               EXECUTION / 'workflow_artifacts.py', EXECUTION / 'workflow_jobs.py', EXECUTION / 'browser_partitions.py', EXECUTION / 'browser_partitions.json')]
    git('ls-files', '--error-unmatch', '--', *closure)
    return {'checkout_sha': git('rev-parse', 'HEAD'), 'source_tree': git('rev-parse', 'HEAD^{tree}')}


def context_from_environment(api, workflow_head: str) -> dict:
    """Bind runner environment to actual API source and local checkout, not job labels."""
    require(os.environ.get('GITHUB_REPOSITORY') == api.repository, 'Runner repository differs from API owner')
    run_id, attempt = int(os.environ['GITHUB_RUN_ID']), int(os.environ['GITHUB_RUN_ATTEMPT'])
    run = api.json('repos/' + api.repository + '/actions/runs/' + str(run_id))
    require(run.get('path') == '.github/workflows/bijux-std.yml', 'Collection requires the source-owned frontend workflow')
    state = checkout_state()
    checkout, source_tree = state['checkout_sha'], state['source_tree']
    require(os.environ.get('GITHUB_SHA') == checkout, 'Runner checkout differs from declared Git SHA')
    return {'run_id': run_id, 'attempt': attempt, 'head': workflow_head, 'checkout_sha': checkout,
            'source_tree': source_tree, 'workflow_id': run['workflow_id'], 'workflow_path': run['path'],
            'head_branch': run['head_branch']}


def decoded_record(data: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate execution JSON key')
            result[key] = value
        return result
    try:
        result = json.loads(data, object_pairs_hook=unique)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError('Invalid execution record JSON') from error
    require(isinstance(result, dict), 'Execution record must be an object')
    return result


def producer_declaration(producer) -> dict:
    data = producer.read('producer-envelope.json')
    envelope = producer.verify_receipt('producer-envelope.json', data)
    digests = envelope.get('artifact_digests')
    partitions = json.loads((EXECUTION / 'browser_partitions.json').read_text())
    suites = {entry['suite'] for entries in partitions['groups'].values() for entry in entries} | {'persisted-reader-history'}
    expected = {f'inventories/{suite}.json' for suite in suites} | {'browser-fixtures.tar.gz', 'renderer-source-observation.json'}
    require(isinstance(digests, dict) and set(digests) == expected, 'Producer envelope requires exact member digests')
    for name, digest in digests.items():
        require(producer.files.get(name) == digest, 'Producer envelope member differs from admitted body')
    return {**producer.workflow_identity(), 'source_head': producer.source_head,
            'envelope_sha256': hashlib.sha256(data).hexdigest(), 'artifact_digests': copy.deepcopy(digests)}


def _executor(identity: dict, role: str, job: dict) -> dict:
    return {'role': role, 'source_head': identity['checkout_sha'],
            'workflow_run_id': str(job['run_id']), 'workflow_attempt': str(job['run_attempt'])}


def _directory(path: Path) -> int:
    """Open every directory component without following a replacement symlink."""
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.absolute().parts[1:]:
            try:
                os.mkdir(part, mode=0o700, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except Exception:
        os.close(fd)
        raise


class Collection:
    """Complete API admission and exact output ownership for one collector."""
    def __init__(self, source, inputs, roles, *, _created=None):
        require(_created is _CREATED, 'Collection must be created by live API admission')
        self.source, self.inputs = source, dict(inputs)
        self.identity, self._roles = source.identity, copy.deepcopy(roles)
        self.paths = {role: spec['destination'] for role, spec in roles.items()}

    @property
    def producer(self):
        return self.inputs['producer']

    def executor_pointer(self, role: str) -> dict:
        """Current recovery executor; ordinary native declarations need no API calls."""
        roles = registry()
        require(role in roles and role != 'producer', 'Unknown native executor role')
        job = self.source.verify_jobs([roles[role]['job_name']])[0]
        require(job['run_attempt'] == self.identity['attempt'] and job.get('status') == 'in_progress'
                and job.get('conclusion') is None, 'Executor must be the actual current in-progress role')
        return _executor(self.identity, role, job)

    def execution_name(self, role: str) -> str:
        require(role in self._roles and role != 'producer', 'Unknown execution record owner')
        subtree = self._roles[role]['subtree']
        return (subtree + '/' if subtree else '') + 'execution.json'

    def verify_execution(self, role: str, record: dict) -> None:
        require(role in self.inputs and role != 'producer', 'Missing admitted execution owner')
        item = self.inputs[role]
        name = self.execution_name(role)
        try:
            owned = decoded_record(item.read(name))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError('Invalid owned execution record') from error
        require(isinstance(record, dict) and record == owned and set(record) == {'schema', 'executor', 'producer', 'files_sha256'}
                and type(record['schema']) is int and record['schema'] == 1, 'Execution record differs from admitted member')
        require(record['executor'] == _executor(self.identity, role, item._pin['owner_job']),
                'Execution declaration differs from actual API owner')
        require(record['producer'] == producer_declaration(self.producer), 'Execution input does not bind admitted producer')
        prefix = (self._roles[role]['subtree'] + '/') if self._roles[role]['subtree'] else ''
        require(record['files_sha256'] == {path[len(prefix):]: digest for path, digest in item.files.items() if path != name},
                'Execution record body inventory differs from admitted output')

    def plan(self) -> dict[str, bytes]:
        """No file is written until every role and cross-owner collision qualifies."""
        result = {}
        partitions = json.loads((EXECUTION / 'browser_partitions.json').read_text())
        suites = {entry['suite'] for entries in partitions['groups'].values() for entry in entries} | {'persisted-reader-history'}
        inventory_members = {f'inventories/{suite}{suffix}' for suite in suites for suffix in ('.json', '.json.contract.json')}
        producer_required = inventory_members | {'producer-envelope.json', 'renderer-source-observation.json',
                                                'browser-fixtures.tar.gz', 'browser-fixtures.sha256'}
        require(producer_required <= set(self.producer.files), 'Producer source-owned inventory is incomplete')
        for role, item in self.inputs.items():
            spec = self._roles[role]
            for name in item.files:
                path = PurePosixPath(name)
                require(not path.is_absolute() and path.parts and all(part not in ('', '.', '..') for part in path.parts),
                        'Invalid admitted output path')
                if role == 'producer':
                    # Producer is the sole root owner; consumer copies never
                    # acquire authority by colliding with it.
                    require(name in ('producer-envelope.json', 'renderer-source-observation.json',
                                     'browser-fixtures.tar.gz', 'browser-fixtures.sha256')
                            or name in inventory_members
                            or (path.parts[0] in ('generated', 'contrast-generated') and len(path.parts) == 2
                                and re.fullmatch(r'build-[a-z][a-z0-9-]*\.log', path.name)),
                            'Producer member lies outside source-owned namespaces')
                elif spec['subtree']:
                    require(path.parts[0] == spec['subtree'] and len(path.parts) > 1, 'Artifact crosses another role namespace')
                destination = str(PurePosixPath(spec['destination']) / path)
                require(destination not in result, 'Cross-owner output collision')
                require(not any(str(parent) in result for parent in PurePosixPath(destination).parents)
                        and not any(existing.startswith(destination + '/') for existing in result), 'Output file/directory collision')
                result[destination] = item.read(name)
        return result

    def materialize(self, output: Path) -> None:
        plan = self.plan()
        output = Path(output).absolute()
        require(not any(path.is_symlink() for path in (output, *output.parents)), 'Output directory has a symlink ancestor')
        require(not output.exists() or output.is_dir(), 'Output is not a directory')
        producer_paths = set(self.producer.files)
        pending = {}
        # Existing source-generated/runtime files outside this plan are untouched.
        for name, data in plan.items():
            destination = output / name
            require(not any(path.is_symlink() or (path.exists() and not path.is_dir())
                            for path in destination.parents if path == output or output in path.parents),
                    'Output ancestor is not an owned directory')
            if destination.exists() or destination.is_symlink():
                require(name in producer_paths and destination.is_file() and not destination.is_symlink()
                        and destination.read_bytes() == data, 'Existing output collision')
            else:
                pending[name] = data
        producer_declaration(self.producer)
        written = []
        try:
            for name, data in pending.items():
                destination = output / name
                parent = _directory(destination.parent)
                try:
                    fd = os.open(destination.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
                    written.append(destination)
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(data)
                finally:
                    os.close(parent)
        except Exception:
            for path in reversed(written):
                path.unlink()
            raise

    def export_record(self) -> dict:
        return {'schema': 1, 'collector': copy.deepcopy(self.identity), 'roles': copy.deepcopy(self._roles),
                'paths': dict(self.paths), 'admission': self.source.export_record(),
                'checkout_before': copy.deepcopy(getattr(self, 'checkout_before', None)),
                'checkout_after': copy.deepcopy(getattr(self, 'checkout_after', None)),
                'planned_files': {name: hashlib.sha256(data).hexdigest() for name, data in self.plan().items()}}


def collect(api, identity: dict, stage: str, output: Path, *, audit=None, caller=None, reconcile=False) -> Collection:
    source, collection, status = None, None, "failed"
    try:
        require(stage in ('producer', 'navigation'), 'Unknown collection stage')
        require(identity.get('workflow_path') == '.github/workflows/bijux-std.yml',
                'Collection requires the source-owned frontend workflow')
        roles = registry()
        caller_name = None
        if reconcile:
            require((stage == 'navigation' and caller == 'navigation')
                    or (stage == 'producer' and caller in roles and caller != 'producer'),
                    'Exact source-owned collector caller is required')
            caller_name = 'std / navigation' if caller == 'navigation' else roles[caller]['job_name']
        if stage == 'producer':
            roles = {'producer': roles['producer']}
        before = checkout_state()
        require(all(before[key] == identity[key] for key in before), 'Actual checkout differs from input source context')
        source = LINEAGE.observe_source(api, identity, reconcile=True, caller=caller_name,
            names=sorted({spec['job_name'] for spec in roles.values()} | {caller_name})) if reconcile else LINEAGE.observe_source(api, identity)
        specs = {role: {key: spec[key] for key in ('job_name', 'artifact_prefix', 'upload_step')} for role, spec in roles.items()}
        inputs = source.admit(specs, workers=8)
        collection = Collection(source, inputs, roles, _created=_CREATED)
        producer_declaration(collection.producer)
        if stage == 'navigation':
            for role in roles:
                if role.startswith('browser-') or role == 'persisted' or (role.startswith('fault-') and role != 'fault-public'):
                    try:
                        record = decoded_record(inputs[role].read(collection.execution_name(role)))
                    except (json.JSONDecodeError, UnicodeDecodeError) as error:
                        raise ValueError('Invalid execution record JSON') from error
                    collection.verify_execution(role, record)
        if hasattr(api, 'remaining'):
            api.remaining()
        require(checkout_state() == before, 'Tracked checkout changed during collection')
        collection.materialize(output)
        require(checkout_state() == before, 'Tracked checkout changed during materialization')
        collection.checkout_before, collection.checkout_after = copy.deepcopy(before), checkout_state()
        status = "admitted"
        return collection
    finally:
        if audit is not None:
            audit({"schema": 1, "stage": stage, "status": status, "collector": copy.deepcopy(identity),
                   "admission": source.export_record() if source is not None else None,
                   "collection": collection.export_record() if status == "admitted" else None})
