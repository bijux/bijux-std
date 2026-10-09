"""Actual renderer entrypoints in declared, isolated verification-only fixtures."""
from pathlib import Path
import importlib.util
import json
import subprocess
import shutil

from fixture_source import create_fixture


def load(path):
    spec = importlib.util.spec_from_file_location('bijux_catalogue_entrypoint_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def execute(repository, root, *, catalogue, retained):
    create_fixture(repository, root)
    shared = root / '.bijux/shared/bijux-docs'
    profiles = load(shared / 'security/renderer_profiles.py')
    actual = profiles.environment_snapshot()
    table_path = shared / 'security/renderer-producer-admission.json'
    table = json.loads(table_path.read_text())
    # This source-owned test fixture binds the actual test process, not a
    # production environment. It must reject publication even after rendering.
    fixture = {'id': 'catalogue-entrypoint-test-runtime', 'usage': 'verification-only',
               'environment': actual}
    table['profiles'] = [profile for profile in table['profiles']
                         if profile.get('environment') != actual]
    table['profiles'].append(fixture)
    table_path.write_text(json.dumps(table, indent=2) + '\n')
    subprocess.run(['git', '-C', str(root), 'add', '.bijux/shared/bijux-docs/security/renderer-producer-admission.json'], check=True)
    subprocess.run(['git', '-C', str(root), 'commit', '-qm', 'test(docs): bind verification-only fixture runtime'], check=True)
    renderer = load(shared / 'security/render_publication.py')
    result = renderer.build_artifact(
        root, 'artifacts/mkdocs.root.yml' if catalogue else 'stock.yml', 'artifacts/site',
        source_recipe='masterclass-catalogue' if catalogue else None,
    )
    if result.get('verification_only') is not True:
        raise AssertionError('Test fixture must not acquire publication qualification')
    try:
        profiles.select(shared, root, publication=True)
    except ValueError as error:
        if 'not approved for publication' not in str(error):
            raise
    else:
        raise AssertionError('The verification fixture admitted publication')
    identity = json.loads((root / 'artifacts/website-security/build-identity.json').read_text())
    reconstruction = json.loads((root / 'artifacts/website-security/producer-reconstruction.json').read_text())
    routes = json.loads((root / 'artifacts/website-security/site-verification.json').read_text())
    if identity.get('verification_only') is not True or identity.get('source_checkpoint') is not None:
        raise AssertionError('Entry point mislabeled verification source')
    publication = load(shared / 'security/publication.py')
    destination = Path(retained) / ('typed-sites' if catalogue else 'tracked-sites') / result['bundle_sha256']
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if publication.public_bundle_identity(destination)[1] != result['bundle_sha256']:
            raise AssertionError('Existing retained entrypoint bundle differs')
    else:
        shutil.copytree(root / 'artifacts/site', destination)
    if publication.public_bundle_identity(destination)[1] != result['bundle_sha256']:
        raise AssertionError('Retained entrypoint bundle differs from actual renderer output')
    return {'retained_site': str(destination), 'fixture_head': subprocess.check_output(
                ['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
            'result': {key: value for key, value in result.items() if key != 'producer'},
            'identity': identity, 'reconstruction': reconstruction, 'routes': routes,
            'runtime_usage': 'verification-only', 'publication_approval': False}
