"""Reviewed profiles govern inventory without taking ownership of product CI."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / '.github/scripts' / f'{name}.py'
    spec = importlib.util.spec_from_file_location(f'bijux_{name}_profiles', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load_script('build_repo_manifest')
RENDERER = load_script('render_repo_configs')
SYNC = load_script('sync_github_standards')


class RepositoryProfileTests(unittest.TestCase):
    def test_capture_uses_reviewed_profile_without_capturing_product_workflow(self):
        profile = {
            'name': 'bijux-ontology',
            'standard_capabilities': ['common', 'python'],
            'release_env': [],
            'workflow_allowlist': ['github-policy', 'pr-approval-policy'],
            'workflow_execution_policy': {'schema': 1, 'publication_entrypoints': {}},
        }
        inventory = BUILDER.load_workflow_inventory()
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            standard = Path(directory) / 'bijux-std'
            standards = standard / '.github/standards'
            standards.mkdir(parents=True)
            (standards / 'node-workspaces.json').write_text(json.dumps({'version': 1, 'repositories': []}))
            (standards / 'repository-profiles.json').write_text(json.dumps({'version': 1, 'repositories': [profile]}))
            (standards / 'repo-config.manifest.json').write_text(json.dumps({'workflow_inventory': inventory, 'repositories': []}))
            consumer = Path(directory) / 'bijux-ontology'
            workflow = consumer / '.github/workflows/verify.yml'
            workflow.parent.mkdir(parents=True)
            authored = 'name: product checks\non: [push, pull_request]\njobs: {}\n'
            workflow.write_text(authored)
            with (mock.patch.object(BUILDER, 'STD_REPO', standard),
                  mock.patch.object(BUILDER, 'MANAGED_REPOSITORIES', ['bijux-ontology']),
                  mock.patch.object(BUILDER, 'load_workflow_inventory', return_value=inventory),
                  mock.patch.object(BUILDER, 'resolve_repository_checkout', return_value=consumer)):
                BUILDER.main()
            manifest = json.loads((standards / 'repo-config.manifest.json').read_text())
            self.assertEqual(manifest['repositories'], [profile])
            with mock.patch.object(RENDERER, 'resolve_repository_checkout', return_value=consumer):
                RENDERER.render_repo('bijux-ontology', manifest)
            self.assertEqual(workflow.read_text(), authored)
            self.assertNotIn('deploy-docs', manifest['repositories'][0]['workflow_allowlist'])

    def test_governed_inventory_renders_all_fourteen_repositories_once(self):
        expected = {
            'bijux.github.io', 'bijux-masterclass', 'bijux-iac', 'bijux-std',
            'bijux-genomics', 'bijux-pollenomics', 'bijux-proteomics',
            'bijux-phylogenetics', 'bijux-gnss', 'bijux-atlas', 'bijux-core',
            'bijux-canon', 'bijux-ontology', 'bijux-ro-crate-node',
        }
        manifest = json.loads((ROOT / '.github/standards/repo-config.manifest.json').read_text())
        names = [entry['name'] for entry in manifest['repositories']]
        self.assertEqual(set(names), expected)
        self.assertEqual(len(names), len(expected))
        self.assertEqual(set(BUILDER.MANAGED_REPOSITORIES), expected)
        for name in names:
            with self.subTest(repository=name):
                prepared = RENDERER.prepare_repo_files(name, manifest)
                self.assertIn('.github/rulesets/main-branch-protection.json', prepared)

    def test_profile_registration_preserves_existing_records_and_is_idempotent(self):
        original = json.loads((ROOT / '.github/standards/repo-config.manifest.json').read_text())
        original['repositories'] = [entry for entry in original['repositories'] if entry['name'] != 'bijux-ontology']
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            standard = Path(directory)
            target = standard / '.github/standards/repo-config.manifest.json'
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(original))
            for name in ('repository-profiles.json', 'node-workspaces.json', 'workflow-inventory.json'):
                (target.parent / name).write_bytes((ROOT / '.github/standards' / name).read_bytes())
            with mock.patch.object(BUILDER, 'STD_REPO', standard):
                BUILDER.register_repository_profiles()
                first = target.read_bytes()
                BUILDER.register_repository_profiles()
            self.assertEqual(target.read_bytes(), first)
            captured = json.loads(first)
            self.assertEqual([entry for entry in captured['repositories'] if entry['name'] != 'bijux-ontology'], original['repositories'])
            self.assertEqual(len(captured['repositories']), 14)

    def test_ontology_sync_preserves_authored_product_ci_and_tracks_profile_checksums(self):
        manifest = json.loads((ROOT / '.github/standards/repo-config.manifest.json').read_text())
        ontology = next(entry for entry in manifest['repositories'] if entry['name'] == 'bijux-ontology')
        self.assertEqual(ontology['workflow_execution_policy'].get('main_verification'), 'existing-events')
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            consumer = Path(directory)
            workflow = consumer / '.github/workflows/verify.yml'
            workflow.parent.mkdir(parents=True)
            authored = 'name: product checks\non: [push, pull_request]\njobs: {}\n'
            workflow.write_text(authored)
            with (mock.patch.object(SYNC, 'resolve_repository_checkout', return_value=consumer),
                  mock.patch.object(RENDERER, 'resolve_repository_checkout', return_value=consumer)):
                SYNC.sync_repo_files('bijux-ontology', manifest)
                RENDERER.render_repo('bijux-ontology', manifest)
                SYNC.refresh_shared_checksums(consumer)
                SYNC.verify_shared_checksums(consumer)
            self.assertEqual(workflow.read_text(), authored)
            ruleset = json.loads((consumer / '.github/rulesets/main-branch-protection.json').read_text())
            checks = next(rule for rule in ruleset['rules'] if rule['type'] == 'required_status_checks')['parameters']['required_status_checks']
            self.assertTrue({'python / 3.11', 'python / 3.13'} <= {check['context'] for check in checks})
            self.assertFalse((consumer / '.github/workflows/deploy-docs.yml').exists())
            self.assertFalse((consumer / '.github/workflows/release-pypi.yml').exists())
            self.assertTrue((consumer / '.github/standards/repository-profiles.json').is_file())
