"""Admit actual same-source artifact owners without rewriting execution attempts.

The API-created observation is an in-memory verification boundary. Exported
records are audit data and cannot recreate it or authorize retained inputs.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from threading import Lock
from types import ModuleType

_SOURCE = Path(__file__).with_name('workflow_artifacts.py')
ARTIFACTS = ModuleType('bijux_workflow_artifacts')
ARTIFACTS.__file__ = str(_SOURCE)
exec(compile(_SOURCE.read_bytes(), str(_SOURCE), 'exec'), ARTIFACTS.__dict__)
_CREATED = object()
MAX_REFRESHES = 32
MAX_INPUT_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024


def require(condition: bool, message: str) -> None:
    ARTIFACTS.require(condition, message)


def _hashes(files: dict[str, bytes]) -> dict[str, str]:
    return {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}


def _inventory_digest(files: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


class ArtifactInput:
    """Exact API-digest-bound bytes and the actual execution that produced them."""

    def __init__(self, pin: dict, files: dict[str, bytes], *, _created=None):
        require(_created is _CREATED, 'Artifact input must be created by API source admission')
        self._pin, self._files = copy.deepcopy(pin), dict(files)
        self._hashes = _hashes(files)

    def workflow_identity(self) -> dict[str, str]:
        return {'workflow_run_id': str(self._pin['owner_job']['run_id']),
                'workflow_attempt': str(self._pin['owner_job']['run_attempt'])}

    @property
    def source_head(self) -> str:
        return self._pin['identity']['checkout_sha']

    @property
    def files(self) -> dict[str, str]:
        return dict(self._hashes)

    def read(self, name: str) -> bytes:
        require(isinstance(name, str) and name in self._files, 'Unowned artifact member')
        return self._files[name]

    def verify_file(self, name: str, data: bytes) -> None:
        require(isinstance(data, bytes) and isinstance(name, str) and name in self._hashes
                and hashlib.sha256(data).hexdigest() == self._hashes[name], 'Artifact member differs from admitted API body')

    def pointer(self) -> dict:
        # An input pointer describes its producer. Collector identity belongs in
        # the separate admission record, so later collectors can verify unchanged inputs.
        pin, job, artifact = self._pin, self._pin['owner_job'], self._pin['artifact']
        return {'schema': 1, 'role': pin['role'], 'workflow_run_id': job['run_id'],
                'owner_job_id': job['id'], 'owner_job_name': job['name'], 'owner_attempt': job['run_attempt'],
                'source_head': pin['identity']['checkout_sha'], 'source_tree': pin['identity']['source_tree'],
                'artifact': {key: artifact[key] for key in ('id', 'name', 'digest')},
                'files_sha256': _inventory_digest(self._hashes)}

    def verify_pointer(self, supplied: dict) -> None:
        require(isinstance(supplied, dict)
                and all(type(supplied.get(key)) is int for key in ('schema', 'workflow_run_id', 'owner_job_id', 'owner_attempt'))
                and isinstance(supplied.get('artifact'), dict) and type(supplied['artifact'].get('id')) is int
                and supplied == self.pointer(), 'Input pointer does not name the admitted producer/body')

    def verify_receipt(self, name: str, data: bytes, *, workflow_path: tuple[str, ...] = (),
                       source_paths: tuple[tuple[str, ...], ...] = (('source_head',),)) -> dict:
        """Verify owned receipt bytes and identity; native/config/runtime checks remain separate."""
        self.verify_file(name, data)
        def unique(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result, 'Duplicate receipt JSON key')
                result[key] = value
            return result
        try:
            receipt = json.loads(data, object_pairs_hook=unique)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError('Invalid owned receipt JSON') from error
        require(isinstance(receipt, dict), 'Owned receipt must be an object')
        require(isinstance(workflow_path, tuple) and all(isinstance(key, str) and key for key in workflow_path)
                and isinstance(source_paths, tuple) and bool(source_paths)
                and all(isinstance(path, tuple) and bool(path) and all(isinstance(key, str) and key for key in path)
                        for path in source_paths), 'Source-owned receipt identity paths are required')
        def at(path):
            value = receipt
            for key in path:
                require(isinstance(value, dict) and key in value, 'Owned receipt identity field is missing')
                value = value[key]
            return value
        workflow = at(workflow_path)
        require(isinstance(workflow, dict) and all(workflow.get(key) == value for key, value in self.workflow_identity().items()),
                'Receipt does not retain its actual owner execution')
        require(all(at(path) == self.source_head for path in source_paths), 'Receipt source differs from admitted checkout')
        return receipt


class SourceObservation:
    """Shared source snapshot and authoritative finite per-owner cache."""

    def __init__(self, api, observed: dict, *, _created=None):
        require(_created is _CREATED, 'Source observation must be created by live API source verification')
        self._api, self._observed = api, copy.deepcopy(observed)
        self._cache, self._inputs, self._specs, self._refreshes = {}, {}, {}, []
        self._report_observations = []
        self._lock = Lock()

    @property
    def identity(self) -> dict:
        return copy.deepcopy(self._observed['identity'])

    @property
    def observation(self) -> dict:
        return copy.deepcopy(self._observed)

    @property
    def repository(self) -> str:
        return self._api.repository

    def json(self, endpoint: str) -> dict:
        """Cache immutable per-ID observations, never run/latest inventories."""
        cacheable = re.fullmatch(r'repos/' + re.escape(self.repository) + r'/actions/(jobs|artifacts)/[1-9][0-9]*', endpoint)
        if cacheable:
            with self._lock:
                if endpoint in self._cache:
                    return copy.deepcopy(self._cache[endpoint])
        value = self._api.json(endpoint)
        if cacheable:
            with self._lock:
                previous = self._cache.setdefault(endpoint, copy.deepcopy(value))
                require(previous == value, 'Concurrent authoritative owner observations disagree')
        return copy.deepcopy(value)

    def _names(self, names) -> list[str]:
        require(isinstance(names, (list, tuple, set)) and 0 < len(names) <= ARTIFACTS.MAX_ROLES
                and all(isinstance(name, str) and bool(name) for name in names)
                and len(set(names)) == len(names), 'Finite unique source-owned job names are required')
        return sorted(names)

    def _current_report(self, row: dict) -> bool:
        return row.get('name') == 'std / report' and row.get('run_attempt') == self.identity['attempt']

    def refresh(self, names) -> None:
        """One coherent current-source boundary for all needed owners, not one query per artifact."""
        names = self._names(names)
        require(len(self._refreshes) < MAX_REFRESHES, 'Source refresh observation limit exceeded')
        frame = {'names': names, 'run': None, 'latest': None, 'status': 'observing'}
        self._refreshes.append(frame)
        identity = self._observed['identity']
        endpoint = 'repos/' + self.repository + '/actions/runs/' + str(identity['run_id'])
        run = self._api.json(endpoint)
        frame['run'] = copy.deepcopy(run)
        require(all(run.get(key) == identity[value] for key, value in
                    (('id', 'run_id'), ('run_attempt', 'attempt'), ('head_sha', 'head'), ('workflow_id', 'workflow_id'),
                     ('path', 'workflow_path'), ('head_branch', 'head_branch'))), 'Observed source run was superseded or changed')
        require(all(run.get(key) == self._observed['run'].get(key) for key in ('repository', 'head_repository')),
                'Observed source repository changed')
        latest_observation = ARTIFACTS.pages(self._api.json, endpoint + '/jobs?filter=latest', 'jobs')
        frame['latest'] = copy.deepcopy(latest_observation)
        latest = latest_observation['jobs']
        require(len({row.get('name') for row in latest}) == len(latest), 'Duplicate refreshed latest owner name')
        require(all(row.get('run_id') == identity['run_id'] and row.get('head_sha') == identity['head']
                    and ARTIFACTS.positive(row.get('run_attempt')) and row['run_attempt'] <= identity['attempt'] for row in latest),
                'Refreshed latest owner run/source/attempt differs')
        selected = {row['name']: row for row in latest}
        original = {row['name']: row for row in self._observed['latest']['jobs']}
        require(all(name in original and name in selected
                    and (ARTIFACTS.job_identity(selected[name]) == ARTIFACTS.job_identity(original[name])
                         if self._current_report(original[name]) else selected[name] == original[name]) for name in names),
                'Source-owned latest execution changed since observation')
        frame['status'] = 'passed'

    def verify_jobs(self, names, workers: int = 8) -> list[dict]:
        """Return authoritative actual latest rows, preserving their individual attempts."""
        names = self._names(names)
        require(type(workers) is int and 1 <= workers <= 8, 'Owner verification concurrency must be between 1 and 8')
        latest = {row['name']: row for row in self._observed['latest']['jobs']}
        require(all(name in latest for name in names), 'Missing source-owned latest execution')
        self.refresh(names)
        def verify(name):
            expected = latest[name]
            endpoint = 'repos/' + self.repository + '/actions/jobs/' + str(expected['id'])
            if self._current_report(expected):
                # Only this current reporting execution may change while its
                # own budget controller is observing it. Never cache active rows.
                observed = self._api.json(endpoint)
                with self._lock:
                    self._report_observations.append({'endpoint': endpoint, 'job': copy.deepcopy(observed)})
                require(ARTIFACTS.job_identity(observed) == ARTIFACTS.job_identity(expected),
                        'Authoritative current report execution identity changed')
            else:
                observed = self.json(endpoint)
                require(observed == expected, 'Authoritative job differs from source latest/history observation')
            return observed
        with ThreadPoolExecutor(max_workers=min(workers, len(names))) as executor:
            records = list(executor.map(verify, names))
        self.refresh(names)
        return records

    def admit(self, roles: dict, *, workers: int = 8, now: datetime | None = None) -> dict[str, ArtifactInput]:
        """Retained ownership becomes usable only after API metadata AND complete body proof."""
        require(isinstance(roles, dict) and 0 < len(roles) <= ARTIFACTS.MAX_ROLES, 'Finite source-owned input roles are required')
        owner_names = []
        for role, spec in roles.items():
            require(isinstance(role, str) and re.fullmatch(r'[a-z][a-z0-9-]*', role)
                    and isinstance(spec, dict) and set(spec) == {'job_name', 'artifact_prefix', 'upload_step'}
                    and all(isinstance(value, str) and bool(value) for value in spec.values())
                    and re.fullmatch(r'[A-Za-z0-9_.-]+', spec['artifact_prefix']), 'Invalid source-owned input role')
            require(role not in self._specs or self._specs[role] == spec, 'Input role changed its source ownership')
            owner_names.append(spec['job_name'])
        require(len(set(owner_names)) == len(owner_names)
                and not any(old_role != role and old_spec['job_name'] == spec['job_name']
                            for role, spec in roles.items() for old_role, old_spec in self._specs.items()), 'Duplicate source-owned input job')
        jobs = {row['name']: row for row in self.verify_jobs(owner_names, workers)}
        now = now or datetime.now(timezone.utc)
        require(now.tzinfo is not None, 'Input admission expiry timezone is required')
        # Fetch each exact needed artifact once in parallel before pure pin
        # verification. Other roles do not cause serial network queries.
        metadata = self._observed['artifacts']['artifacts']
        endpoints = []
        for spec in roles.values():
            job = jobs[spec['job_name']]
            name = spec['artifact_prefix'] + '-' + self.identity['checkout_sha'] + '-' + str(job['run_attempt'])
            matches = [row for row in metadata if row.get('name') == name]
            require(len(matches) == 1, 'Missing or duplicate exact owned artifact')
            endpoints.append('repos/' + self.repository + '/actions/artifacts/' + str(matches[0]['id']))
        with ThreadPoolExecutor(max_workers=min(workers, len(endpoints))) as executor:
            list(executor.map(self.json, endpoints))
        pins = {role: ARTIFACTS._owner_pin(self, self._observed, role, spec, jobs[spec['job_name']], now)
                for role, spec in roles.items()}
        require(len({pin['artifact']['id'] for pin in pins.values()}) == len(pins), 'Distinct input roles share an artifact ID')
        require(sum(pin['artifact']['size_in_bytes'] for pin in pins.values()) <= MAX_INPUT_ARCHIVE_BYTES,
                'Admitted compressed input union exceeds byte limit')
        self.refresh(owner_names)
        expanded = sum(len(data) for role, item in self._inputs.items() if role in roles for data in item._files.values())
        reservation_lock = Lock()
        def reserve(size):
            nonlocal expanded
            with reservation_lock:
                expanded += size
                require(expanded <= ARTIFACTS.MAX_EXPANDED_BYTES, 'Admitted input union exceeds byte limit')
        def body(role):
            pin = pins[role]
            if role in self._inputs:
                require(self._inputs[role]._pin == pin, 'Cached input ownership changed')
                return self._inputs[role]
            data = self._api.archive(pin['artifact']['id'])
            require(len(data) == pin['artifact']['size_in_bytes'], 'Input API artifact byte count differs')
            return ArtifactInput(pin, ARTIFACTS.archive_members(data, pin['artifact']['digest'], reserve=reserve), _created=_CREATED)
        with ThreadPoolExecutor(max_workers=min(workers, len(roles))) as executor:
            inputs = dict(zip(roles, executor.map(body, roles)))
        require(sum(len(data) for item in inputs.values() for data in item._files.values()) <= ARTIFACTS.MAX_EXPANDED_BYTES,
                'Admitted input union exceeds byte limit')
        self.refresh(owner_names)
        self._specs.update(copy.deepcopy(roles))
        self._inputs.update(inputs)
        return inputs

    def export_record(self) -> dict:
        return {'schema': 1, 'scope': 'API-created same-source ownership and artifact body admission',
                'collector': self.identity, 'observation': self.observation,
                'authoritative_per_id': copy.deepcopy(self._cache),
                'refresh_observations': copy.deepcopy(self._refreshes),
                'current_report_observations': copy.deepcopy(self._report_observations),
                'inputs': {role: item.pointer() for role, item in sorted(self._inputs.items())},
                'limits': ['Audit JSON cannot recreate source admission.',
                           'Recovery is scoped to heads owned by the workflow repository; ordinary fork qualification remains separate.',
                           'Native cases, configuration, runtime, browser and publication checks remain separate mandatory duties.']}


def observe_source(api, identity: dict) -> SourceObservation:
    """Verify an owning-repository head; this does not enable fork recovery."""
    return SourceObservation(api, ARTIFACTS.observe(api, identity), _created=_CREATED)
