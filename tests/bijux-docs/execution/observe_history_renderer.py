"""Capture a source-owned history renderer recipe without creating admission."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
RECIPE = 'tests/bijux-docs/generated/canon-docs-renderer.json'
LOCK = 'tests/bijux-docs/execution/recipes/canon-docs/requirements.lock'
DEPENDENCIES = (
    'tests/bijux-docs/execution/observe_history_renderer.py', RECIPE, LOCK,
    '.github/workflows/renderer-observation.yml',
    'shared/bijux-docs/security/renderer_profiles.py',
    'shared/bijux-docs/security/producer_capabilities.py',
)


def load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


observer = load('shared/bijux-docs/tooling/security/renderer_fingerprints.py', 'history_renderer_observer')
profiles = load('shared/bijux-docs/security/renderer_profiles.py', 'history_renderer_profiles')
capabilities = load('shared/bijux-docs/security/producer_capabilities.py', 'history_renderer_capabilities')


def validate_recipe(recipe: dict, lock: bytes):
    pins = dict(observer.locked_packages(lock))
    observer.require(recipe.get('schema') == 1 and recipe.get('producer') == 'canon-docs'
                     and recipe.get('publication_admission') is False, 'Explicit observation-only producer recipe required')
    observer.require(recipe.get('source_kind') == 'local-candidate' and recipe.get('source_repository') == 'https://github.com/bijux/bijux-canon', 'Exact candidate provenance required; no upstream acceptance is inferred')
    observer.require(recipe.get('lock_path') == LOCK and recipe.get('lock_sha256') == observer.sha(lock), 'Recipe lock identity differs')
    observer.require(recipe.get('target_platform') == 'Linux' and recipe.get('target_python') == '3.11' and recipe.get('target_machine') == 'x86_64' and recipe.get('target_implementation') == 'cpython', 'Exact declared hosted runtime selector required')
    observer.require(recipe.get('packages') == pins and len(pins) == 36, 'Exact complete Canon documentation package recipe required')
    for key in ('source_commit', 'source_pyproject_sha256', 'source_uv_lock_sha256'):
        value = recipe.get(key)
        observer.require(isinstance(value, str) and len(value) == (40 if key == 'source_commit' else 64)
                         and all(c in '0123456789abcdef' for c in value), 'Exact source provenance hash required: ' + key)
    return pins


def validate_runtime(recipe: dict, environment: dict):
    actual = environment.get('platform', {})
    observer.require(actual.get('system') == recipe['target_platform']
                     and actual.get('machine') == recipe['target_machine']
                     and actual.get('python', '').startswith(recipe['target_python'] + '.')
                     and actual.get('implementation') == recipe['target_implementation'],
                     'Actual runtime differs from source-owned platform selector')


def source_snapshot():
    source = observer.source_snapshot(ROOT)
    for name in DEPENDENCIES:
        data = observer.regular(ROOT / name)
        committed = subprocess.check_output(['git', '-C', str(ROOT), 'show', 'HEAD:' + name])
        observer.require(data == committed, 'Observation recipe differs from committed source: ' + name)
        source['files'].append({'path': name, 'sha256': observer.sha(data)})
    return source


def callbacks(output: Path):
    from mkdocs.config import load_config
    docs = output.parent / 'callback-docs'
    docs.mkdir()
    config_file = output.parent / 'callback-config.yml'
    with config_file.open('x') as stream:
        stream.write('site_name: History renderer observation\ndocs_dir: callback-docs\nsite_dir: callback-site\ntheme:\n  name: material\nplugins:\n  - search\n  - autorefs\n  - redirects\n  - git-revision-date-localized:\n      enable_creation_date: false\n      fallback_to_build_date: true\n')
    config = load_config(config_file=str(config_file))
    return {'scope': 'source-owned callback observation configuration; not consumer routes/hooks/history',
            'configuration_sha256': observer.sha(config_file.read_bytes()),
            'plugins': list(config.plugins), 'records': capabilities.callback_records(config, ROOT)}


def capture(root_output: str):
    output = observer.output_path(ROOT, root_output)
    before = source_snapshot()
    lock = observer.regular(ROOT / LOCK)
    recipe = json.loads(observer.regular(ROOT / RECIPE))
    validate_recipe(recipe, lock)
    packages = observer.observe_packages(lock)
    output.parent.mkdir(parents=True, exist_ok=True)
    registered = callbacks(output)
    try:
        environment = profiles.environment_snapshot()
        validate_runtime(recipe, environment)
    except ValueError as error:
        failed = {'schema': 1, 'scope': 'observed-incomplete-history-renderer',
                  'verification_only': True, 'admission_created': False,
                  'status': 'failed', 'source': before, 'recipe': recipe,
                  'packages': packages, 'registered_callbacks': registered,
                  'runtime': observer.runtime_snapshot(packages), 'error': str(error)}
        with output.open('x') as stream:
            stream.write(json.dumps(failed, indent=2) + '\n')
        raise
    runtime = observer.runtime_snapshot(packages)
    observer.require(environment == profiles.environment_snapshot(), 'Profile-shaped environment changed during capture')
    observer.require(packages == observer.observe_packages(lock), 'Installed dependency bytes changed during capture')
    observer.require(runtime == observer.runtime_snapshot(packages), 'Physical runtime changed during capture')
    observer.require(before == source_snapshot(), 'Committed source changed during capture')
    report = {'schema': 1, 'scope': 'observed-canon-history-renderer', 'verification_only': True,
              'admission_created': False, 'publication_admission': False, 'source': before,
              'recipe': recipe, 'packages': packages, 'environment': environment,
              'hosted_context': {name: os.environ.get(name) for name in ('GITHUB_REPOSITORY', 'GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_EVENT_NAME', 'RUNNER_OS', 'ImageOS')},
              'runtime': runtime, 'registered_callbacks': registered,
              'limitations': runtime['limitations'] + [
                  'The actual hosted patch version is captured; a floating 3.11 selector cannot guarantee future profile identity.',
                  'No consumer source acceptance, authored hook/history qualification, full build, browser journey or publication profile follows from this observation.']}
    observer.output_path(ROOT, root_output)
    with output.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    print('Observed 36 history renderer packages; admission_created:false')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        capture(args.output)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print('History renderer observation failed:', error)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
