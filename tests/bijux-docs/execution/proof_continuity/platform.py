"""Revalidate live accepted authority in the package producer's real platform."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType

PATH = Path(__file__).parent.parent / 'runtime_transport/container.py'
CONTAINER = ModuleType('bijux_proof_consumer_container')
CONTAINER.__file__ = str(PATH)
exec(compile(PATH.read_bytes(), str(PATH), 'exec'), CONTAINER.__dict__)
ENVIRONMENT = ('RUNNER_OS', 'RUNNER_ARCH', 'GITHUB_REPOSITORY', 'GITHUB_RUN_ID',
    'GITHUB_RUN_ATTEMPT', 'GITHUB_SHA', 'GITHUB_EVENT_NAME', 'GITHUB_REF',
    'EXPECTED_BASELINE', 'VERIFICATION_MODE', 'EXPECTED_FRONTEND', 'GH_TOKEN',
    'PLAN_RESULT', 'CHECK_RESULT', 'FIXTURE_RESULT', 'BROWSER_RESULT', 'COMMAND_RESULT',
    'RENDERER_RESULT', 'CATALOGUE_RESULT', 'PERSISTED_RESULT', 'FAULT_BROWSER_RESULT',
    'FAULT_PUBLIC_RESULT')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def execute(root, arguments):
    """Create all live capabilities inside the child; supplied receipts grant none."""
    root = Path(root).resolve(strict=True)
    require(root == Path(__file__).resolve().parents[4], 'Proof requires its owning physical source')
    require(shutil.which('docker') is not None, 'Docker is required for accepted proof platform')
    node, npm = (shutil.which(name) for name in ('node', 'npm'))
    require(node is not None and npm is not None, 'Current admitted Node and npm are required')
    node, npm = Path(node).resolve(strict=True), Path(npm).resolve(strict=True)
    require(npm.name == 'npm-cli.js' and npm.parent.name == 'bin', 'npm requires its installed package entrypoint')
    artifacts = root / 'artifacts'
    require(not any(path.is_symlink() for path in (artifacts, *artifacts.parents)), 'Linked proof output is refused')
    owner = artifacts / 'bijux-docs/proof-platform'
    owner.mkdir(parents=True, exist_ok=True)
    require(not any(path.is_symlink() for path in (owner, *owner.parents)), 'Linked proof platform output is refused')
    with tempfile.TemporaryDirectory(prefix='live-admission-', dir=owner) as folder:
        workspace = Path(folder)
        launchers = workspace / 'bin'; launchers.mkdir()
        (launchers / 'node').symlink_to('/bijux-toolchain/node')
        (launchers / 'npm').symlink_to('/bijux-toolchain/npm/bin/npm-cli.js')
        completion = workspace / 'completed'
        command = ['docker', 'run', '--rm', '--read-only', '--ipc=host', '--tmpfs', '/tmp',
            '--workdir', str(root), '--env', 'PYTHONDONTWRITEBYTECODE=1',
            '--env', 'GIT_CONFIG_COUNT=1', '--env', 'GIT_CONFIG_KEY_0=safe.directory',
            '--env', 'GIT_CONFIG_VALUE_0=' + str(root),
            '--env', 'GIT_OPTIONAL_LOCKS=0',
            '--env', 'PATH=/bijux-toolchain/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            '--env', 'GITHUB_OUTPUT=' + str(workspace / 'github-output')]
        # Docker reads these names from the parent. Tokens never enter command text.
        # Host ImageOS/ImageVersion are not properties of this immutable image.
        for name in ENVIRONMENT:
            if name in os.environ:
                command += ['--env', name]
        command += CONTAINER.mount(root, str(root))
        command += CONTAINER.mount(artifacts, str(artifacts), readonly=False)
        command += CONTAINER.mount(node, '/bijux-toolchain/node')
        command += CONTAINER.mount(npm.parent.parent, '/bijux-toolchain/npm')
        command += CONTAINER.mount(launchers, '/bijux-toolchain/bin')
        command += [CONTAINER.IMAGE, 'python3', '-B', str(Path(__file__).resolve()),
                    '--child', str(completion), *arguments]
        subprocess.run(command, check=True)
        require(completion.is_file() and not completion.is_symlink()
                and completion.read_bytes() == b'live-admission-completed\n',
                'Accepted proof child did not complete its actual operation')


def main():
    require(len(sys.argv) >= 4 and sys.argv[1] == '--child', 'Proof platform requires its source-owned child protocol')
    completion, arguments = Path(sys.argv[2]), sys.argv[3:]
    require(not completion.exists(), 'Preserve prior proof completion')
    path = Path(__file__).parent.parent / 'input_planning/cli.py'
    module = ModuleType('bijux_live_consumer_proof_cli')
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    sys.argv = [str(path), *arguments]
    module.main()
    with completion.open('xb') as stream:
        stream.write(b'live-admission-completed\n')


if __name__ == '__main__':
    main()
