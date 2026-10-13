"""Observe installed package bytes, executable links and the current toolchain."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import subprocess
from types import ModuleType

MAX_FILES = 100_000
MAX_BYTES = 512 * 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
_COST_PATH = Path(__file__).parent.parent / 'costs/observations.py'
COSTS = ModuleType('bijux_package_transport_inventory_costs')
COSTS.__file__ = str(_COST_PATH)
exec(compile(_COST_PATH.read_bytes(), str(_COST_PATH), 'exec'), COSTS.__dict__)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate runtime JSON key')
        result[key] = value
    return result


def decoded(data):
    value = json.loads(data, object_pairs_hook=unique)
    require(isinstance(value, dict), 'Runtime JSON object is required')
    return value


def name(value):
    require(isinstance(value, str) and 0 < len(value) <= 4096 and '\\' not in value
            and ':' not in value and all(31 < ord(char) < 127 for char in value)
            and len(value.split('/')) <= 128
            and all(part not in ('', '.', '..') and len(part) <= 255 for part in value.split('/')),
            'Unsafe runtime path')
    return value


def read(path, maximum=MAX_FILE_BYTES, parent=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= maximum,
                'Runtime input must be a bounded regular file')
        data = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        fields = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        require(len(data) == before.st_size and fields(before) == fields(after), 'Runtime bytes changed during observation')
        return data, (0o755 if before.st_mode & 0o111 else 0o644)


@COSTS.measured('runtime_inventory')
def inventory(root):
    """Include directory and symlink topology without following any package link."""
    root = Path(root).absolute()
    require(not any(path.is_symlink() for path in (root, *root.parents)), 'Runtime root contains a symlink ancestor')
    require(root.is_dir(), 'Installed runtime directory is required')
    records, objects = {}, {}
    total = 0
    def visit(folder, prefix=''):
        nonlocal total
        before = os.fstat(folder)
        for entry in sorted(os.scandir(folder), key=lambda item: item.name):
            key = name(prefix + entry.name)
            info = os.stat(entry.name, dir_fd=folder, follow_symlinks=False)
            require(len(records) < MAX_FILES, 'Runtime file limit exceeded')
            if stat.S_ISDIR(info.st_mode):
                records[key] = {'kind': 'directory'}
                child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=folder)
                try:
                    visit(child, key + '/')
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                require(info.st_nlink == 1, 'Hard-linked runtime input is refused')
                data, mode = read(entry.name, parent=folder)
                records[key] = {'kind': 'file', 'sha256': digest(data), 'bytes': len(data), 'mode': mode}
                if digest(data) not in objects:
                    total += len(data)
                    objects[digest(data)] = data
                require(total <= MAX_BYTES, 'Runtime byte limit exceeded')
            elif stat.S_ISLNK(info.st_mode):
                records[key] = {'kind': 'link', 'target': os.readlink(entry.name, dir_fd=folder)}
                after_link = os.stat(entry.name, dir_fd=folder, follow_symlinks=False)
                fields = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
                require(fields(info) == fields(after_link), 'Runtime link changed while reading')
            else:
                raise ValueError('Unsupported installed runtime type')
        after = os.fstat(folder)
        require((before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns), 'Runtime directory changed while reading')
    descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in root.parts[1:]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor); descriptor = child
        visit(descriptor)
    finally:
        os.close(descriptor)
    return records, objects


def validate_packages(records, objects, lock):
    """Every installed package belongs to the exact lock, including optional OS constraints."""
    require(lock.get('lockfileVersion') == 3 and isinstance(lock.get('packages'), dict), 'Exact npm lock inventory is required')
    bins = {}
    expected_packages = {}
    for package_path, declaration in lock['packages'].items():
        if not package_path:
            continue
        name(package_path)
        require(package_path.startswith('node_modules/') and isinstance(declaration, dict)
                and isinstance(declaration.get('version'), str) and not declaration.get('link'), 'Unsupported locked package')
        package_file = package_path + '/package.json'
        if package_file not in records:
            constraints = declaration.get('os', [])
            current_os = {'Darwin': 'darwin', 'Linux': 'linux', 'Windows': 'win32'}.get(platform.system())
            excluded = constraints and (('!' + current_os) in constraints or
                        (any(not item.startswith('!') for item in constraints) and current_os not in constraints))
            require(declaration.get('optional') is True and excluded, 'Required locked package is missing')
            continue
        record = records[package_file]
        require(record.get('kind') == 'file', 'Installed package metadata must be regular')
        package = decoded(objects[record['sha256']])
        require(package.get('version') == declaration['version'], 'Installed package version differs from lock')
        expected_packages[package_file] = declaration['version']
        executable = package.get('bin', {})
        if isinstance(executable, str):
            executable = {package['name'].split('/')[-1]: executable}
        require(isinstance(executable, dict), 'Invalid package executable declaration')
        for binary, relative in executable.items():
            name(binary); name(relative.removeprefix('./'))
            require('/' not in binary, 'Invalid executable name')
            target = package_path + '/' + relative.removeprefix('./')
            require(records.get(target, {}).get('kind') == 'file' and records[target]['mode'] == 0o755,
                    'Package executable is missing or not executable')
            parent = package_path.rsplit('/node_modules/', 1)[0] if '/node_modules/' in package_path else ''
            link = (parent + '/' if parent else '') + 'node_modules/.bin/' + binary
            bins.setdefault(link, set()).add(target)
    installed = {key for key in records if key.endswith('/package.json') and
                 records[key].get('kind') == 'file' and key in {path + '/package.json' for path in lock['packages'] if path}}
    require(installed == set(expected_packages), 'Installed lock inventory differs')
    for key, record in records.items():
        if record.get('kind') != 'link':
            continue
        target = record['target']
        require(key in bins and isinstance(target, str) and not PurePosixPath(target).is_absolute()
                and '\\' not in target and ':' not in target, 'Undeclared runtime symlink')
        resolved = os.path.normpath(str(PurePosixPath(key).parent / target))
        require(resolved in bins[key], 'Runtime executable link escapes its declared package')
    require({key for key, record in records.items() if record.get('kind') == 'link'} == set(bins),
            'Package executable topology is incomplete')
    # Nested package.json files are authored package content; package boundaries
    # themselves must come from the lock and cannot carry an unlisted install.
    for key, record in records.items():
        remainder = key.split('node_modules/')[-1]
        boundary = remainder.count('/') == 0 or (remainder.startswith('@') and remainder.count('/') == 1)
        if record.get('kind') == 'directory' and 'node_modules/' in key and boundary:
            require(key in lock['packages'] or key.endswith('/.bin') or key.split('/')[-1].startswith('@'),
                    'Unlisted installed dependency directory')
    return expected_packages


@COSTS.measured('runtime_inventory')
def toolchain():
    node = Path(shutil.which('node') or '')
    npm = Path(shutil.which('npm') or '')
    require(node.is_file() and npm.is_file(), 'Current Node and npm executables are required')
    node = node.resolve(); npm = npm.resolve()
    npm_root = npm.parent.parent
    npm_records, npm_objects = inventory(npm_root)
    # npm's own internal links are inventoried, never executed to qualify a transport.
    for key, record in npm_records.items():
        if record.get('kind') == 'link':
            target = record['target']
            require(not PurePosixPath(target).is_absolute() and
                    not os.path.normpath(str(PurePosixPath(key).parent / target)).startswith('../'), 'npm link escapes package')
    metadata = decoded(read(npm_root / 'package.json')[0])
    node_bytes, _ = read(node, 256 * 1024 * 1024)
    return {'node_version': subprocess.check_output([str(node), '--version'], text=True).strip(),
            'node_sha256': digest(node_bytes), 'npm_version': metadata['version'],
            'npm_tree_sha256': digest(canonical(npm_records)), 'npm_cli_sha256': digest(read(npm)[0]),
            'platform': {'system': platform.system(), 'machine': platform.machine(),
                         'release': platform.release(), 'libc': list(platform.libc_ver()),
                         'os_release_sha256': digest(Path('/etc/os-release').read_bytes()) if Path('/etc/os-release').is_file() else None,
                         'runner_os': os.environ.get('RUNNER_OS'), 'runner_arch': os.environ.get('RUNNER_ARCH'),
                         'image_os': os.environ.get('ImageOS'), 'image_version': os.environ.get('ImageVersion')}}


@COSTS.measured('runtime_inventory')
def input_identity(source, observed_toolchain=None):
    package = read(Path(source) / 'package.json')[0]
    lock = read(Path(source) / 'package-lock.json')[0]
    return {'toolchain': observed_toolchain if observed_toolchain is not None else toolchain(),
            'package_sha256': digest(package), 'lock_sha256': digest(lock)}, decoded(lock)
