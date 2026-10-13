"""Content-addressed npm transport with exact bytes and declared executable links."""
from __future__ import annotations

import gzip
import io
import json
import os
from pathlib import Path
import re
import stat
import tarfile
from types import ModuleType


def load(relative):
    path = Path(__file__).parent / relative
    module = ModuleType('bijux_runtime_' + path.stem)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


IDENTITY = load('identity.py')
FILES = load('../fixture_archive.py')
FORMAT = 'bijux-installed-npm-objects'
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
require = IDENTITY.require


class InputIdentityMismatch(ValueError):
    """Refuse reuse while retaining a bounded observation of known identity fields."""
    def __init__(self, producer, current):
        super().__init__('Runtime platform, toolchain or source lock differs')
        fields = [('package_sha256',), ('lock_sha256',)]
        fields += [('toolchain', name) for name in
                   ('node_version', 'node_sha256', 'npm_version', 'npm_tree_sha256', 'npm_cli_sha256')]
        fields += [('toolchain', 'platform', name) for name in
                   ('system', 'machine', 'release', 'libc', 'os_release_sha256',
                    'runner_os', 'runner_arch', 'image_os', 'image_version')]

        def observed(value, path):
            for part in path:
                if not isinstance(value, dict) or part not in value:
                    return {'present': False}
                value = value[part]
            field = path[-1]
            safe = value is None
            if isinstance(value, str) and len(value) <= 128:
                if field.endswith('_sha256'):
                    safe = bool(SHA256.fullmatch(value))
                elif field in ('node_version', 'npm_version'):
                    safe = bool(re.fullmatch(r'v?[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]{1,64})?', value))
                elif field == 'release':
                    safe = bool(re.fullmatch(r'[0-9][A-Za-z0-9_.+-]{0,127}', value))
                elif field == 'image_version':
                    safe = bool(re.fullmatch(r'[0-9]{8}(?:\.[0-9]{1,10}){1,3}', value))
                elif field == 'image_os':
                    safe = bool(re.fullmatch(r'(?:ubuntu|win|macos)[0-9]{2,4}', value))
                else:
                    allowed = {'system': ('Linux', 'Darwin', 'Windows'),
                               'machine': ('x86_64', 'aarch64', 'arm64', 'AMD64', 'i386', 'i686', 'armv7l'),
                               'runner_os': ('Linux', 'macOS', 'Windows'),
                               'runner_arch': ('X64', 'ARM64', 'X86', 'ARM')}
                    safe = value in allowed.get(field, ())
            elif field == 'libc' and isinstance(value, list) and len(value) == 2:
                safe = value[0] in ('glibc', 'musl', '') and isinstance(value[1], str) and len(value[1]) <= 32 \
                    and bool(re.fullmatch(r'(?:[0-9]+(?:\.[0-9]+){0,3})?', value[1]))
            if safe:
                return {'present': True, 'value': value}
            return {'present': True, 'redacted_sha256': IDENTITY.digest(IDENTITY.canonical(value))}

        differences = []
        for path in fields:
            before, after = observed(producer, path), observed(current, path)
            if before != after:
                differences.append({'field': '.'.join(path), 'producer': before, 'current': after})
        self.diagnosis = {'schema': 1, 'producer_inputs_sha256': IDENTITY.digest(IDENTITY.canonical(producer)),
                          'current_inputs_sha256': IDENTITY.digest(IDENTITY.canonical(current)),
                          'differing_fields': differences,
                          'scope': 'Known package, lock, toolchain and platform fields only; observation never authorizes reuse.'}


def validate(index, objects, expected_inputs, source):
    require(set(index) == {'schema', 'format', 'inputs', 'members'} and type(index['schema']) is int
            and index['schema'] == 1 and index['format'] == FORMAT, 'Unsupported runtime archive schema')
    if index['inputs'] != expected_inputs:
        raise InputIdentityMismatch(index['inputs'], expected_inputs)
    records = index['members']
    require(isinstance(records, dict) and 0 < len(records) <= IDENTITY.MAX_FILES, 'Invalid runtime inventory')
    total = 0
    used = set()
    for key, record in records.items():
        IDENTITY.name(key)
        require(isinstance(record, dict), 'Invalid runtime member')
        for parent in Path(key).parents:
            if str(parent) != '.':
                require(records.get(str(parent)) == {'kind': 'directory'}, 'Runtime topology has an absent or linked parent')
        kind = record.get('kind')
        if kind == 'directory':
            require(set(record) == {'kind'}, 'Invalid runtime directory record')
        elif kind == 'link':
            require(set(record) == {'kind', 'target'}, 'Invalid runtime link record')
        else:
            require(kind == 'file' and set(record) == {'kind', 'sha256', 'bytes', 'mode'}
                    and isinstance(record['sha256'], str) and SHA256.fullmatch(record['sha256'])
                    and type(record['bytes']) is int and 0 <= record['bytes'] <= IDENTITY.MAX_FILE_BYTES
                    and type(record['mode']) is int and record['mode'] in (0o644, 0o755), 'Invalid runtime file record')
            total += record['bytes']
            require(total <= IDENTITY.MAX_BYTES, 'Runtime reconstructed byte limit exceeded')
            body = objects.get(record['sha256'])
            require(isinstance(body, bytes) and len(body) == record['bytes'] and IDENTITY.digest(body) == record['sha256'],
                    'Runtime object bytes differ')
            used.add(record['sha256'])
    require(used == set(objects), 'Unexpected runtime object')
    require(set(key for key in records if '/' not in key) == {'package.json', 'package-lock.json', 'node_modules'},
            'Runtime root namespace differs')
    for key, field in (('package.json', 'package_sha256'), ('package-lock.json', 'lock_sha256')):
        require(records[key].get('sha256') == expected_inputs[field]
                and objects[records[key]['sha256']] == IDENTITY.read(Path(source) / key)[0], 'Transported source dependency bytes differ')
    IDENTITY.validate_packages(records, objects, IDENTITY.decoded(IDENTITY.read(Path(source) / 'package-lock.json')[0]))
    return records


def receipt(index, data):
    return {'schema': 1, 'format': FORMAT, 'inputs': index['inputs'], 'archive_sha256': IDENTITY.digest(data),
            'archive_bytes': len(data), 'members_sha256': IDENTITY.digest(IDENTITY.canonical(index['members'])),
            'member_count': len(index['members']),
            'file_bytes': sum(record.get('bytes', 0) for record in index['members'].values())}


def pack(runtime, source, archive, observed_toolchain=None):
    inputs, _ = IDENTITY.input_identity(source, observed_toolchain)
    records, objects = IDENTITY.inventory(runtime)
    index = {'schema': 1, 'format': FORMAT, 'inputs': inputs, 'members': records}
    validate(index, objects, inputs, source)
    require(len(IDENTITY.canonical(index)) <= FILES.MAX_INDEX_BYTES, 'Runtime index byte limit exceeded')
    destination = Path(archive)
    require(not any(path.is_symlink() for path in (destination, *destination.parents)), 'Linked runtime archive output')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as output:
        with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0, compresslevel=6) as zipped:
            with tarfile.open(fileobj=zipped, mode='w', format=tarfile.USTAR_FORMAT) as stream:
                for key, data in [('index.json', IDENTITY.canonical(index))] + [('objects/' + key, objects[key]) for key in sorted(objects)]:
                    member = tarfile.TarInfo(key)
                    member.size, member.mode = len(data), 0o644
                    stream.addfile(member, io.BytesIO(data))
    return receipt(index, IDENTITY.read(destination, IDENTITY.MAX_BYTES)[0])


def decode(archive, declaration, source, observed_toolchain=None):
    inputs, _ = IDENTITY.input_identity(source, observed_toolchain)
    data = IDENTITY.read(archive, IDENTITY.MAX_BYTES)[0]
    require(isinstance(declaration, dict) and declaration.get('archive_sha256') == IDENTITY.digest(data), 'Runtime archive digest differs')
    index, objects, total = None, {}, 0
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data), mode='rb') as stream:
            for member, body in FILES.regular_members(stream):
                if index is None:
                    require(member.name == 'index.json', 'Runtime index must be first')
                    index = IDENTITY.decoded(body)
                    continue
                key = member.name.removeprefix('objects/')
                require(member.name == 'objects/' + key and SHA256.fullmatch(key) and key not in objects,
                        'Unexpected or duplicate runtime member')
                objects[key] = body
                total += len(body)
                require(total <= IDENTITY.MAX_BYTES, 'Runtime object byte limit exceeded')
    except (EOFError, tarfile.TarError) as error:
        raise ValueError('Invalid runtime archive encoding') from error
    require(index is not None, 'Runtime archive index is missing')
    records = validate(index, objects, inputs, source)
    require(declaration == receipt(index, data), 'Runtime receipt differs from observed transport')
    return records, objects


def unpack(archive, declaration, source, destination, observed_toolchain=None):
    records, objects = decode(archive, declaration, source, observed_toolchain)
    destination = Path(destination).absolute()
    require(not any(path.is_symlink() for path in (destination, *destination.parents)), 'Linked runtime destination')
    require(not destination.exists(), 'Preserve existing runtime destination')
    destination.mkdir(parents=True)
    root = FILES.open_directory(destination)
    try:
        for key, record in sorted(records.items(), key=lambda item: (item[0].count('/'), item[0])):
            parts = key.split('/')
            parent = root
            descriptors = []
            try:
                for component in parts[:-1]:
                    parent = FILES.open_directory(Path(component), parent)
                    descriptors.append(parent)
                if record['kind'] == 'directory':
                    os.mkdir(parts[-1], 0o755, dir_fd=parent)
                elif record['kind'] == 'file':
                    fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, record['mode'], dir_fd=parent)
                    with os.fdopen(fd, 'wb') as output:
                        output.write(objects[record['sha256']])
                        os.fchmod(output.fileno(), record['mode'])
                else:
                    os.symlink(record['target'], parts[-1], dir_fd=parent)
            finally:
                for fd in reversed(descriptors):
                    os.close(fd)
    finally:
        os.close(root)
    actual, actual_objects = IDENTITY.inventory(destination)
    require(actual == records and set(actual_objects) == set(objects), 'Reconstructed runtime identity differs')
    return declaration
