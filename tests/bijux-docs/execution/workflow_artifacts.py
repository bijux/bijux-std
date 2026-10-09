"""Select and transport exact job-owned GitHub workflow artifacts.

API observations identify transport and execution ownership. They do not replace
the caller's source, configuration, runtime or native receipt verification.
Earlier-attempt inputs require a separate lineage admission and are refused here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import zipfile

API = 'https://api.github.com'
MAX_PAGES = 100
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 100_000
MAX_ROLES = 128


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def positive(value: object) -> bool:
    return type(value) is int and value > 0


def sha(value: object, length: int = 40) -> bool:
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{' + str(length) + '}', value) is not None


def timestamp(value: object) -> datetime:
    require(isinstance(value, str), 'Actual timezone-bound timestamp is required')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError('Invalid actual timestamp') from error
    require(result.tzinfo is not None and result.utcoffset() is not None, 'Timestamp timezone is required')
    return result


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubAPI:
    """Read-only bounded API transport; signed CDN requests never carry a token."""

    def __init__(self, repository: str, token: str, *, opener=None):
        require(isinstance(repository, str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository),
                'Invalid repository identity')
        require(all(part not in ('.', '..') for part in repository.split('/')), 'Invalid repository identity')
        require(isinstance(token, str) and bool(token) and '\r' not in token and '\n' not in token,
                'API token is required')
        self.repository, self._token = repository, token
        self._opener = opener or build_opener(NoRedirect())

    def _read(self, url: str, *, authenticated: bool, maximum: int) -> tuple[int, dict, bytes]:
        parsed = urlsplit(url)
        require(parsed.scheme == 'https' and not parsed.username and not parsed.password and not parsed.fragment
                and parsed.port in (None, 443), 'Invalid HTTPS transport URL')
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'bijux-workflow-artifacts',
                   'X-GitHub-Api-Version': '2022-11-28'}
        if authenticated:
            require(parsed.netloc == 'api.github.com', 'Credentials are confined to GitHub API origin')
            headers['Authorization'] = 'Bearer ' + self._token
        request = Request(url, headers=headers, method='GET')
        try:
            response = self._opener.open(request, timeout=60)
        except HTTPError as error:
            if error.code in (301, 302, 303, 307, 308):
                location = error.headers.get('Location')
                error.close()
                return error.code, {'Location': location}, b''
            # Provider error bodies/URLs may contain credentials or signed query strings.
            code = error.code
            error.close()
            raise ValueError('GitHub transport failed with HTTP ' + str(code)) from None
        except (URLError, OSError):
            raise ValueError('GitHub transport could not complete') from None
        with response:
            require(response.status == 200, 'Unexpected transport status')
            length = response.headers.get('Content-Length')
            if length is not None:
                require(length.isdecimal() and int(length) <= maximum, 'Transport exceeds byte limit')
            data = response.read(maximum + 1)
            require(len(data) <= maximum, 'Transport exceeds byte limit')
            return response.status, dict(response.headers), data

    def json(self, endpoint: str) -> dict:
        require(isinstance(endpoint, str) and endpoint.startswith('repos/' + self.repository + '/')
                and not any(part in ('', '.', '..') for part in endpoint.split('?')[0].split('/'))
                and '#' not in endpoint and '\\' not in endpoint, 'API endpoint is outside the repository')
        status, _, data = self._read(API + '/' + endpoint, authenticated=True, maximum=MAX_JSON_BYTES)
        require(status == 200, 'JSON API redirects are not admitted')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result, 'Duplicate API JSON key')
                result[key] = value
            return result
        try:
            result = json.loads(data, object_pairs_hook=unique)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError('Invalid API JSON') from error
        require(isinstance(result, dict), 'API response must be an object')
        return result

    def archive(self, artifact_id: int) -> bytes:
        require(positive(artifact_id), 'Actual artifact ID is required')
        endpoint = API + '/repos/' + self.repository + '/actions/artifacts/' + str(artifact_id) + '/zip'
        status, headers, data = self._read(endpoint, authenticated=True, maximum=MAX_ARCHIVE_BYTES)
        if status == 200:
            return data
        require(status == 302, 'Artifact API must return its signed download redirect')
        location = headers.get('Location')
        require(isinstance(location, str), 'Missing artifact download location')
        parsed = urlsplit(location)
        host = parsed.hostname or ''
        require(host.endswith('.blob.core.windows.net') or host.endswith('.actions.githubusercontent.com')
                or host.endswith('.githubusercontent.com'), 'Unrecognized artifact CDN origin')
        status, _, data = self._read(location, authenticated=False, maximum=MAX_ARCHIVE_BYTES)
        require(status == 200, 'Artifact CDN redirects are not admitted')
        return data


def pages(fetch, endpoint: str, key: str) -> dict:
    """Keep every page; incoherent totals or duplicate IDs are not silently deduplicated."""
    require(key in ('jobs', 'artifacts'), 'Unknown paginated collection')
    rows, retained, total = [], [], None
    for page in range(1, MAX_PAGES + 1):
        payload = fetch(endpoint + ('&' if '?' in endpoint else '?') + 'per_page=100&page=' + str(page))
        require(isinstance(payload, dict) and type(payload.get('total_count')) is int
                and 0 <= payload['total_count'] <= MAX_PAGES * 100, 'Invalid API collection total')
        require(total is None or total == payload['total_count'], 'API collection changed during pagination')
        total = payload['total_count']
        part = payload.get(key)
        require(isinstance(part, list) and len(part) <= 100, 'Invalid API page')
        require(all(isinstance(row, dict) and positive(row.get('id')) for row in part), 'Actual API IDs are required')
        retained.append(payload)
        rows.extend(part)
        require(len({row['id'] for row in rows}) == len(rows), 'Duplicate API ID')
        require(len(rows) <= total, 'API page exceeds declared total')
        if len(rows) == total:
            return {'total_count': total, key: rows, 'pages': retained}
        require(len(part) == 100, 'Incomplete API pagination')
    raise ValueError('API pagination limit exceeded')


def observe(api, identity: dict) -> dict:
    """Capture run, checkout, workflow, complete latest/history and artifact metadata."""
    required = {'run_id', 'attempt', 'head', 'checkout_sha', 'source_tree', 'workflow_id', 'workflow_path', 'head_branch'}
    require(isinstance(identity, dict) and set(identity) == required, 'Exact workflow identity is required')
    require(all(positive(identity[key]) for key in ('run_id', 'attempt', 'workflow_id'))
            and all(sha(identity[key]) for key in ('head', 'checkout_sha', 'source_tree')), 'Invalid workflow identity')
    require(isinstance(identity['workflow_path'], str) and re.fullmatch(r'\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml', identity['workflow_path'])
            and isinstance(identity['head_branch'], str) and bool(identity['head_branch']), 'Workflow path/ref is required')
    prefix = 'repos/' + api.repository + '/'
    run_path = prefix + 'actions/runs/' + str(identity['run_id'])
    run = api.json(run_path)
    require(all(run.get(key) == identity[value] for key, value in
                (('id', 'run_id'), ('run_attempt', 'attempt'), ('head_sha', 'head'), ('workflow_id', 'workflow_id'),
                 ('path', 'workflow_path'), ('head_branch', 'head_branch'))), 'Workflow run identity mismatch')
    require(run.get('repository', {}).get('full_name') == api.repository
            and run.get('head_repository', {}).get('full_name') == api.repository, 'Workflow repository mismatch')
    workflow = api.json(prefix + 'actions/workflows/' + str(identity['workflow_id']))
    require(workflow.get('id') == identity['workflow_id'] and workflow.get('path') == identity['workflow_path'],
            'Workflow owner mismatch')
    commits = {name: api.json(prefix + 'git/commits/' + identity[name]) for name in ('head', 'checkout_sha')}
    require(all(commit.get('sha') == identity[name] and commit.get('tree', {}).get('sha') == identity['source_tree']
                for name, commit in commits.items()), 'Checkout source tree mismatch')
    if identity['checkout_sha'] != identity['head']:
        parents = commits['checkout_sha'].get('parents')
        require(isinstance(parents, list) and len(parents) == 2 and parents[1].get('sha') == identity['head'],
                'Checkout is not the candidate preview merge')
    latest = pages(api.json, run_path + '/jobs?filter=latest', 'jobs')
    history = pages(api.json, run_path + '/jobs?filter=all', 'jobs')
    artifacts = pages(api.json, run_path + '/artifacts', 'artifacts')
    require(len({row.get('name') for row in latest['jobs']}) == len(latest['jobs']), 'Duplicate latest job name')
    histories = {row['id']: row for row in history['jobs']}
    for row in history['jobs']:
        require(row.get('run_id') == identity['run_id'] and row.get('head_sha') == identity['head']
                and positive(row.get('run_attempt')) and row['run_attempt'] <= identity['attempt'], 'History run/source/attempt mismatch')
    for row in latest['jobs']:
        require(histories.get(row['id']) == row, 'Latest job is absent or differs from complete history')
        siblings = [item for item in history['jobs'] if item.get('name') == row.get('name')]
        require(max(item['run_attempt'] for item in siblings) == row['run_attempt']
                and sum(item['run_attempt'] == row['run_attempt'] for item in siblings) == 1,
                'Latest job hides a newer or ambiguous execution')
    require({row.get('name') for row in history['jobs']} == {row.get('name') for row in latest['jobs']},
            'Latest inventory omits a history owner')
    require(len({row.get('name') for row in artifacts['artifacts']}) == len(artifacts['artifacts']), 'Duplicate artifact name')
    return {'identity': dict(identity), 'run': run, 'workflow': workflow, 'commits': commits,
            'latest': latest, 'history': history, 'artifacts': artifacts}


def select(api, observation: dict, roles: dict, *, now: datetime | None = None) -> dict:
    """Pin one artifact per source-owned role from its latest successful same-attempt job."""
    require(isinstance(roles, dict) and 0 < len(roles) <= MAX_ROLES, 'Finite source-owned roles are required')
    identity = observation['identity']
    latest = observation['latest']['jobs']
    selected, owner_names = {}, set()
    now = now or datetime.now(timezone.utc)
    require(now.tzinfo is not None, 'Expiry observation timezone is required')
    for role, spec in roles.items():
        require(isinstance(role, str) and re.fullmatch(r'[a-z][a-z0-9-]*', role)
                and isinstance(spec, dict) and set(spec) == {'job_name', 'artifact_prefix', 'upload_step'}, 'Invalid source-owned role')
        require(all(isinstance(value, str) and bool(value) for value in spec.values())
                and re.fullmatch(r'[A-Za-z0-9_.-]+', spec['artifact_prefix']), 'Invalid artifact owner specification')
        require(spec['job_name'] not in owner_names, 'Duplicate source-owned job role')
        owner_names.add(spec['job_name'])
        matches = [row for row in latest if row.get('name') == spec['job_name']]
        require(len(matches) == 1, 'Missing or duplicate latest owner')
        job = api.json('repos/' + api.repository + '/actions/jobs/' + str(matches[0]['id']))
        require(job == matches[0], 'Owner job changed since complete API observation')
        require(job.get('run_id') == identity['run_id'] and job.get('head_sha') == identity['head']
                and job.get('run_attempt') == identity['attempt'], 'Cross-attempt input requires explicit lineage admission')
        require(job.get('status') == 'completed' and job.get('conclusion') == 'success', 'Latest owner is not terminal-success')
        created, started, ended = (timestamp(job.get(key)) for key in ('created_at', 'started_at', 'completed_at'))
        require(created <= started <= ended and (ended - started).total_seconds() < 180, 'Owner reached the strict 180-second job limit')
        steps = job.get('steps')
        require(isinstance(steps, list) and bool(steps), 'Actual owner steps are required')
        require(all(step.get('status') == 'completed' and step.get('conclusion') in ('success', 'skipped') for step in steps),
                'Owner has failed or nonterminal steps')
        uploads = [step for step in steps if step.get('name') == spec['upload_step']]
        require(len(uploads) == 1 and uploads[0].get('conclusion') == 'success', 'Exactly one successful owned upload step is required')
        before, after = timestamp(uploads[0].get('started_at')), timestamp(uploads[0].get('completed_at'))
        require(started <= before <= after <= ended, 'Upload step is outside owner execution')
        name = spec['artifact_prefix'] + '-' + identity['checkout_sha'] + '-' + str(job['run_attempt'])
        artifacts = [row for row in observation['artifacts']['artifacts'] if row.get('name') == name]
        require(len(artifacts) == 1, 'Missing or duplicate exact owned artifact')
        artifact = api.json('repos/' + api.repository + '/actions/artifacts/' + str(artifacts[0]['id']))
        require(artifact == artifacts[0], 'Artifact changed since complete API observation')
        require(artifact.get('expired') is False and timestamp(artifact.get('expires_at')) > now, 'Artifact is expired')
        require(type(artifact.get('size_in_bytes')) is int and 0 < artifact['size_in_bytes'] <= MAX_ARCHIVE_BYTES,
                'Artifact byte count is unbounded')
        require(isinstance(artifact.get('digest'), str) and re.fullmatch(r'sha256:[a-f0-9]{64}', artifact['digest']),
                'Actual API artifact SHA256 is required')
        workflow_run = artifact.get('workflow_run', {})
        require(workflow_run.get('id') == identity['run_id'] and workflow_run.get('head_sha') == identity['head']
                and workflow_run.get('head_branch') == identity['head_branch']
                and workflow_run.get('repository_id') == observation['run']['repository'].get('id')
                and workflow_run.get('head_repository_id') == observation['run']['head_repository'].get('id'),
                'Artifact workflow source/repository mismatch')
        require(before <= timestamp(artifact.get('created_at')) <= after, 'Artifact was not created by the owned upload interval')
        selected[role] = {'role': role, 'identity': dict(identity), 'owner_job': job, 'artifact': artifact,
                          'binding': 'exact-source-owned-name-and-successful-upload-interval',
                          'limits': ['API transport ownership does not certify internal receipt/source/configuration bodies.']}
    require(len({pin['artifact']['id'] for pin in selected.values()}) == len(selected), 'Artifact ID is shared by distinct owners')
    return selected


def archive_members(data: bytes, expected_digest: str) -> dict[str, bytes]:
    """Validate the complete bounded ZIP before creating any output."""
    require(isinstance(data, bytes) and 0 < len(data) <= MAX_ARCHIVE_BYTES, 'Invalid artifact archive size')
    require(isinstance(expected_digest, str) and re.fullmatch(r'sha256:[a-f0-9]{64}', expected_digest)
            and hashlib.sha256(data).hexdigest() == expected_digest[7:], 'Artifact API digest mismatch')
    files, names, total = {}, set(), 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            require(0 < len(entries) <= MAX_MEMBERS, 'Artifact member count is unbounded')
            for item in entries:
                name = item.filename.rstrip('/') if item.is_dir() else item.filename
                parts = name.split('/')
                require(bool(name) and len(name) <= 4096 and len(parts) <= 128
                        and all(part not in ('', '.', '..') and len(part) <= 255 for part in parts)
                        and not PurePosixPath(name).is_absolute() and '\\' not in name and ':' not in name
                        and all(ord(char) >= 32 and ord(char) != 127 for char in name), 'Unsafe artifact member path')
                require(name not in names, 'Duplicate artifact member path')
                names.add(name)
                mode = stat.S_IFMT(item.external_attr >> 16)
                require(mode in ((0, stat.S_IFDIR) if item.is_dir() else (0, stat.S_IFREG)), 'Nonregular artifact member')
                require(not item.flag_bits & 1 and 0 <= item.file_size <= MAX_MEMBER_BYTES, 'Artifact member is encrypted or unbounded')
                total += item.file_size
                require(total <= MAX_EXPANDED_BYTES, 'Expanded artifact exceeds byte limit')
                if not item.is_dir():
                    body = archive.read(item)
                    require(len(body) == item.file_size, 'Artifact member byte count differs')
                    files[name] = body
            require(bool(files), 'Artifact must contain ordinary files')
            require(all('/'.join(name.split('/')[:index]) not in files
                        for name in names for index in range(1, len(name.split('/')))), 'Artifact file/directory collision')
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ValueError('Invalid artifact ZIP') from error
    return files


def refresh_owner(api, pin: dict) -> None:
    """An unchanged old job record cannot hide a newly started owner execution."""
    identity = pin['identity']
    prefix = 'repos/' + api.repository + '/actions/runs/' + str(identity['run_id'])
    run = api.json(prefix)
    require(all(run.get(key) == identity[value] for key, value in
                (('id', 'run_id'), ('run_attempt', 'attempt'), ('head_sha', 'head'),
                 ('workflow_id', 'workflow_id'), ('path', 'workflow_path'), ('head_branch', 'head_branch'))),
            'Pinned workflow run was superseded or changed')
    require(run.get('repository', {}).get('full_name') == api.repository
            and run.get('head_repository', {}).get('full_name') == api.repository
            and run['repository'].get('id') == pin['artifact']['workflow_run']['repository_id']
            and run['head_repository'].get('id') == pin['artifact']['workflow_run']['head_repository_id'],
            'Pinned workflow repository was changed')
    latest = pages(api.json, prefix + '/jobs?filter=latest', 'jobs')['jobs']
    require(len({row.get('name') for row in latest}) == len(latest), 'Duplicate latest job name')
    require(all(row.get('run_id') == identity['run_id'] and row.get('head_sha') == identity['head']
                and positive(row.get('run_attempt')) and row['run_attempt'] <= identity['attempt'] for row in latest),
            'Latest inventory run/source/attempt mismatch')
    owners = [row for row in latest if row.get('name') == pin['owner_job']['name']]
    require(len(owners) == 1 and owners[0] == pin['owner_job'], 'Pinned owner is no longer the actual latest execution')


def download(api, pin: dict, destination: Path) -> dict:
    """Materialize one verified artifact in a fresh owned directory; never merge outputs."""
    destination = Path(destination)
    require(not destination.exists() and not destination.is_symlink(), 'Artifact destination collision')
    require(destination.parent.is_dir() and not any(path.is_symlink() for path in (destination.parent, *destination.parent.parents)),
            'Artifact destination parent must be an ordinary directory')
    refresh_owner(api, pin)
    artifact = pin['artifact']
    require(api.json('repos/' + api.repository + '/actions/artifacts/' + str(artifact['id'])) == artifact,
            'Pinned artifact changed before download')
    require(api.json('repos/' + api.repository + '/actions/jobs/' + str(pin['owner_job']['id'])) == pin['owner_job'],
            'Pinned owner changed before download')
    data = api.archive(artifact['id'])
    require(len(data) == artifact['size_in_bytes'], 'Artifact API byte count mismatch')
    files = archive_members(data, artifact['digest'])
    # Downloads can outlast a rerun request. Reobserve the run and role once the
    # entire body is verified, before materializing any candidate input bytes.
    refresh_owner(api, pin)
    # Exclusive reservation refuses a concurrent destination instead of replacing
    # it. Directory-relative no-follow writes cannot escape through a symlink.
    destination.mkdir()
    root = os.open(destination, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name, body in files.items():
            directory = os.dup(root)
            try:
                parts = name.split('/')
                for component in parts[:-1]:
                    try:
                        os.mkdir(component, dir_fd=directory)
                    except FileExistsError:
                        pass
                    child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                    os.close(directory)
                    directory = child
                descriptor = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o644, dir_fd=directory)
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(body)
            finally:
                os.close(directory)
    finally:
        os.close(root)
    return {**pin, 'files': {name: hashlib.sha256(body).hexdigest() for name, body in files.items()},
            'archive_sha256': hashlib.sha256(data).hexdigest(), 'archive_bytes': len(data)}
