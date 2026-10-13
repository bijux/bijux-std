"""Observe producer packages in the browser consumer's immutable platform."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import ModuleType

IMAGE = 'mcr.microsoft.com/playwright@sha256:6446946a1d9fd62d9ae501312a2d76a43ee688542b21622056a372959b65d63d'
FORWARDED_ENVIRONMENT = ('RUNNER_OS', 'RUNNER_ARCH', 'GITHUB_RUN_ID',
                         'GITHUB_RUN_ATTEMPT', 'GITHUB_SHA', 'BIJUX_COST_OWNER')


def archive_module():
    path = Path(__file__).with_name('archive.py')
    module = ModuleType('bijux_container_runtime_archive')
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


def mount(source, destination, *, readonly=True):
    source = Path(source).resolve(strict=True)
    if ',' in str(source) or '\n' in str(source):
        raise ValueError('Container mount must have a bounded physical path')
    return ['--mount', f'type=bind,src={source},dst={destination}' + (',readonly' if readonly else '')]


@contextmanager
def prepared_image():
    """Overlap only image transport; await it before observing runtime identity."""
    docker = shutil.which('docker')
    if docker is None:
        raise ValueError('Docker is required for consumer-platform preparation')
    command = [docker, 'pull', IMAGE]
    child = subprocess.Popen(command)
    try:
        yield
        status = child.wait()
        if status:
            raise subprocess.CalledProcessError(status, command)
    except BaseException:
        if child.poll() is None:
            child.kill()
        child.wait()
        raise


def pack(runtime, source, archive):
    """Execute current source bytes; no supplied platform or receipt can qualify them."""
    transport = archive_module()
    source, runtime, archive = Path(source).absolute(), Path(runtime).absolute(), Path(archive).absolute()
    root = Path(__file__).resolve().parents[4]
    transport.require(source == root / 'tests/bijux-docs', 'Container preparation requires the owning source package')
    transport.require(not any(path.is_symlink() for path in (runtime, *runtime.parents)), 'Linked installed runtime input')
    transport.require(not any(path.is_symlink() for path in (archive, *archive.parents)), 'Linked runtime archive output')
    transport.require(not archive.exists(), 'Preserve existing runtime archive')
    transport.require(shutil.which('docker') is not None, 'Docker is required for consumer-platform preparation')
    node, npm = (shutil.which(name) for name in ('node', 'npm'))
    transport.require(node is not None and npm is not None, 'Admitted Node and npm executables are required')
    node, npm = Path(node).resolve(strict=True), Path(npm).resolve(strict=True)
    transport.require(npm.name == 'npm-cli.js' and npm.parent.name == 'bin', 'npm must use its installed package entrypoint')
    npm_root = npm.parent.parent
    archive.parent.mkdir(parents=True, exist_ok=True)
    costs = root / 'artifacts/bijux-docs/cost-observations'
    transport.require(not any(path.is_symlink() for path in (costs, *costs.parents)), 'Linked package observation output')
    costs.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='package-platform-', dir=archive.parent) as folder:
        workspace = Path(folder)
        launchers, output = workspace / 'bin', workspace / 'output'
        launchers.mkdir(); output.mkdir()
        (launchers / 'node').symlink_to('/bijux-toolchain/node')
        (launchers / 'npm').symlink_to('/bijux-toolchain/npm/bin/npm-cli.js')
        command = ['docker', 'run', '--rm', '--read-only', '--network=none', '--ipc=host',
                   '--tmpfs', '/tmp', '--env', 'PYTHONDONTWRITEBYTECODE=1',
                   '--env', 'PATH=/bijux-toolchain/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin']
        for name in FORWARDED_ENVIRONMENT:
            if name in os.environ:
                command.extend(['--env', name + '=' + os.environ[name]])
        command += mount(root, '/bijux/source') + mount(runtime, '/bijux/runtime')
        command += mount(node, '/bijux-toolchain/node') + mount(npm_root, '/bijux-toolchain/npm')
        command += mount(launchers, '/bijux-toolchain/bin')
        command += mount(output, '/bijux-package-output', readonly=False)
        command += mount(costs, '/bijux/source/artifacts/bijux-docs/cost-observations', readonly=False)
        command += [IMAGE, 'python3', '-B', '/bijux/source/tests/bijux-docs/execution/runtime_transport/container.py']
        subprocess.run(command, check=True)
        prepared = output / 'browser-packages.tar.gz'
        declaration = transport.IDENTITY.decoded(transport.IDENTITY.read(output / 'browser-packages.json')[0])
        body = transport.IDENTITY.read(prepared, transport.IDENTITY.MAX_BYTES)[0]
        transport.require(declaration.get('archive_sha256') == transport.IDENTITY.digest(body), 'Prepared package archive bytes differ')
        with archive.open('xb') as destination:
            destination.write(body)
        return declaration


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    transport = archive_module()
    declaration = transport.pack('/bijux/runtime', '/bijux/source/tests/bijux-docs',
                                 '/bijux-package-output/browser-packages.tar.gz')
    Path('/bijux-package-output/browser-packages.json').write_bytes(transport.IDENTITY.canonical(declaration) + b'\n')


if __name__ == '__main__':
    main()
