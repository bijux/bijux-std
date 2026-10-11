from __future__ import annotations

import copy
import json
import unittest

from .policy_fixtures import ROOT, MODULE, RENDERER


class DocumentationRoutingTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / '.github/standards/repo-config.manifest.json').read_text())
        self.repositories = {entry['name']: entry for entry in self.manifest['repositories']}

    def test_every_family_member_has_the_same_manual_main_contract(self):
        self.assertEqual(len(self.repositories), 12)
        for name, entry in self.repositories.items():
            with self.subTest(repository=name):
                destination = MODULE.documentation_destination(entry)
                self.assertEqual(destination['repository'], 'bijux.github.io' if name in {'bijux-std', 'bijux-iac'} else name)
                MODULE.validate_manifest(self.manifest, [name])

    def test_foundation_aliases_keep_the_real_hub_routes(self):
        self.assertEqual(MODULE.documentation_destination(self.repositories['bijux-std']),
                         {'repository': 'bijux.github.io', 'path': '/standards/'})
        self.assertEqual(MODULE.documentation_destination(self.repositories['bijux-iac']),
                         {'repository': 'bijux.github.io', 'path': '/infrastructure/'})

    def test_foundations_can_adopt_owned_sites_without_changing_the_manual_contract(self):
        for name in ('bijux-std', 'bijux-iac'):
            changed = copy.deepcopy(self.manifest)
            entry = next(row for row in changed['repositories'] if row['name'] == name)
            entry['workflow_execution_policy']['publication_entrypoints']['deploy-docs']['destination'] = {
                'repository': name, 'path': f'/{name}/'}
            MODULE.validate_manifest(changed, [name])
            self.assertEqual(MODULE.documentation_destination(entry)['repository'], name)

    def test_foreign_redirects_cycles_traversal_and_arbitrary_routes_refuse(self):
        for name in self.repositories:
            for bad in ({'repository': 'outside', 'path': '/'},
                        {'repository': name, 'path': '../private/'},
                        {'repository': 'bijux-std', 'path': '/standards/'},
                        {'repository': 'bijux-atlas', 'path': '/bijux-atlas/'},
                        {'repository': 'bijux.github.io', 'path': '/', 'token': 'unused'}):
                if bad == MODULE.documentation_destination(self.repositories[name]):
                    continue
                changed = copy.deepcopy(self.manifest)
                selected = next(entry for entry in changed['repositories'] if entry['name'] == name)
                selected['workflow_execution_policy']['publication_entrypoints']['deploy-docs']['destination'] = bad
                with self.subTest(repository=name, destination=bad), self.assertRaises(ValueError):
                    MODULE.validate_manifest(changed, [name])

    def test_missing_destination_or_control_cannot_be_inferred(self):
        for key in ('destination', 'controller', 'refs', 'mode'):
            entry = copy.deepcopy(self.repositories['bijux-iac'])
            del entry['workflow_execution_policy']['publication_entrypoints']['deploy-docs'][key]
            with self.subTest(field=key), self.assertRaises(ValueError):
                MODULE.documentation_destination(entry)

    def test_destination_is_not_a_release_permission(self):
        changed = copy.deepcopy(self.manifest)
        entry = next(row for row in changed['repositories'] if row['name'] == 'bijux-core')
        entry['workflow_execution_policy']['publication_entrypoints']['release-pypi']['destination'] = {'repository': 'bijux-core', 'path': '/bijux-core/'}
        with self.assertRaises(ValueError):
            MODULE.validate_manifest(changed, ['bijux-core'])

    def test_all_twelve_managed_workflows_are_identical_manual_entrypoints(self):
        sync = MODULE.source_loading.load_script(ROOT / '.github/scripts/sync_github_standards.py', 'bijux_docs_route_sync')
        sync.resolve_repository_checkout = lambda name: ROOT
        workflows = []
        for entry in self.repositories.values():
            projected = sync.prepare_runtime_workflows(entry, self.manifest)
            document = MODULE.parse_workflow(projected['.github/workflows/deploy-docs.yml'], 'deploy-docs')
            self.assertEqual(set(document['on']), {'workflow_dispatch'})
            self.assertTrue(document['on']['workflow_dispatch']['inputs']['accepted_commit']['required'])
            workflows.append(document)
        self.assertTrue(all(workflow == workflows[0] for workflow in workflows))


if __name__ == '__main__':
    unittest.main()
