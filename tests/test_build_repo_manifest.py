from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "scripts"
    / "build_repo_manifest.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bijux_std_build_repo_manifest",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildRepoManifestTests(unittest.TestCase):
    def test_builder_uses_adjacent_domain_package(self) -> None:
        self.assertEqual(Path(MODULE.WORKFLOW_EXECUTION.__file__).resolve(), SCRIPT_PATH.with_name("workflow_execution") / "__init__.py")
        self.assertTrue(hasattr(MODULE.WORKFLOW_EXECUTION, "validate_manifest"))

    def test_capture_retains_reviewed_policy_without_inferring_from_runtime(self) -> None:
        inventory = MODULE.load_workflow_inventory()
        policy = {"schema": 1, "automatic_runs": "repository-policy-only", "publication_entrypoints": {"deploy-docs": {"mode": "manual-only", "refs": "main-only"}}}
        with tempfile.TemporaryDirectory() as workspace:
            standard = Path(workspace) / "bijux-std"
            manifest_path = standard / ".github/standards/repo-config.manifest.json"
            manifest_path.parent.mkdir(parents=True)
            (manifest_path.parent / "node-workspaces.json").write_text(json.dumps({"version":1,"repositories":[]}))
            manifest_path.write_text(json.dumps({"workflow_inventory": inventory, "repositories": [{"name": "bijux-atlas", "workflow_allowlist": ["github-policy", "deploy-docs"], "workflow_execution_policy": policy}, {"name": "bijux-canon"}]}))
            atlas = Path(workspace) / "bijux-atlas"
            canon = Path(workspace) / "bijux-canon"
            atlas.mkdir()
            (canon / ".github/workflows").mkdir(parents=True)
            # Runtime mode never supplies owner approval to the canonical configuration.
            (canon / ".github/workflows/deploy-docs.yml").write_text("on:\n  workflow_dispatch:\njobs: {}\n")
            with (mock.patch.object(MODULE, "STD_REPO", standard),
                  mock.patch.object(MODULE, "MANAGED_REPOSITORIES", ["bijux-atlas", "bijux-canon"]),
                  mock.patch.object(MODULE, "load_workflow_inventory", return_value=inventory),
                  mock.patch.object(MODULE, "resolve_repository_checkout", side_effect=lambda name: Path(workspace) / name)):
                MODULE.main()
                first = manifest_path.read_bytes()
                MODULE.main()
            captured = json.loads(first)
            self.assertEqual(captured["repositories"][0]["workflow_execution_policy"], policy)
            self.assertNotIn("workflow_execution_policy", captured["repositories"][1])
            self.assertEqual(manifest_path.read_bytes(), first)

    def test_capture_refuses_invalid_reviewed_policy_before_output_change(self) -> None:
        inventory = MODULE.load_workflow_inventory()
        with tempfile.TemporaryDirectory() as workspace:
            standard = Path(workspace)
            path = standard / ".github/standards/repo-config.manifest.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"workflow_inventory": inventory, "repositories": [{"name": "bijux-atlas", "workflow_execution_policy": {"schema": True}}]}))
            before = path.read_bytes()
            with (mock.patch.object(MODULE, "STD_REPO", standard),
                  mock.patch.object(MODULE, "load_workflow_inventory", return_value=inventory),
                  mock.patch.object(MODULE, "resolve_repository_checkout") as resolve):
                with self.assertRaises(ValueError):
                    MODULE.main()
                resolve.assert_not_called()
            self.assertEqual(path.read_bytes(), before)

    def test_capture_refuses_to_drop_unmanaged_reviewed_policy(self) -> None:
        inventory = MODULE.load_workflow_inventory()
        with tempfile.TemporaryDirectory() as workspace:
            standard = Path(workspace)
            path = standard / ".github/standards/repo-config.manifest.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"workflow_inventory": inventory, "repositories": [{"name": "bijux-owned-extension", "workflow_execution_policy": {"schema": 1}}]}))
            before = path.read_bytes()
            with (mock.patch.object(MODULE, "STD_REPO", standard),
                  mock.patch.object(MODULE, "load_workflow_inventory", return_value=inventory)):
                with self.assertRaisesRegex(ValueError, "unmanaged repository"):
                    MODULE.main()
            self.assertEqual(path.read_bytes(), before)

    def test_repository_checkout_variable_normalizes_repository_name(self) -> None:
        self.assertEqual(
            MODULE.repository_checkout_variable("bijux.github.io"),
            "BIJUX_REPOSITORY_PATH_BIJUX_GITHUB_IO",
        )

    def test_resolve_repository_checkout_uses_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as checkout:
            with mock.patch.dict(
                os.environ,
                {"BIJUX_REPOSITORY_PATH_BIJUX_GNSS": checkout},
            ):
                self.assertEqual(
                    MODULE.resolve_repository_checkout("bijux-gnss"),
                    Path(checkout).resolve(),
                )

    def test_resolve_repository_checkout_rejects_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            with (
                mock.patch.object(MODULE, "ROOT", Path(workspace)),
                mock.patch.dict(os.environ, {}, clear=True),
            ):
                with self.assertRaisesRegex(
                    FileNotFoundError,
                    "BIJUX_REPOSITORY_PATH_BIJUX_GNSS",
                ):
                    MODULE.resolve_repository_checkout("bijux-gnss")

    def test_normalize_release_env_json_entry_drops_legacy_token_publish_auth(self) -> None:
        normalized = MODULE.normalize_release_env_json_entry(
            "BIJUX_PYPI_PACKAGE_MATRIX_JSON",
            [
                {"package_slug": "bijux-phylogenetics"},
                {"package_slug": "phylogenetic", "publish_auth": "token"},
                {"package_slug": "bijux-example", "publish_auth": "trusted"},
            ],
        )

        self.assertEqual(
            normalized,
            [
                {"package_slug": "bijux-phylogenetics"},
                {"package_slug": "phylogenetic"},
                {"package_slug": "bijux-example", "publish_auth": "trusted"},
            ],
        )


if __name__ == "__main__":
    unittest.main()


class NodeWorkspaceRegistryTests(unittest.TestCase):
    def test_registered_workspace_has_all_product_checks_and_publication_stays_disabled(self):
        profiles=MODULE.node_workspace_profiles()
        self.assertEqual(set(profiles),{'bijux-ro-crate-node'})
        entry=profiles['bijux-ro-crate-node']
        values={item['key']:item['value'] for item in entry['release_env']}
        self.assertIs(values['BIJUX_NPM_ENABLED'],False)
        self.assertEqual([p['name'] for p in values['BIJUX_NPM_PACKAGES_JSON']],['@bijux/ro-crate-core','@bijux/ro-crate-validator'])
        self.assertNotIn('deploy-docs',entry['workflow_allowlist'])
        self.assertEqual(len(entry['additional_required_status_checks']),4)
        self.assertEqual(entry['workflow_execution_policy']['publication_entrypoints'],{'release-npm':{'mode':'manual-only','controller':'iac'}})

    def test_node_generation_preserves_every_unrelated_repository_and_is_idempotent(self):
        original=json.loads((MODULE.STD_REPO/'.github/standards/repo-config.manifest.json').read_text())
        profiles=MODULE.node_workspace_profiles()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            target=root/'.github/standards/repo-config.manifest.json'
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(original))
            with mock.patch.object(MODULE,'STD_REPO',root),mock.patch.object(MODULE,'node_workspace_profiles',return_value=profiles):
                MODULE.register_node_workspaces()
                first=target.read_bytes()
                MODULE.register_node_workspaces()
            self.assertEqual(target.read_bytes(),first)
            result=json.loads(first)
            self.assertEqual([e for e in result['repositories'] if e['name'] not in profiles],
                             [e for e in original['repositories'] if e['name'] not in profiles])
