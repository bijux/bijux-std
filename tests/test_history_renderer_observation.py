"""Keep candidate history observations exact and separate from admission."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('history_observation', ROOT / 'tests/bijux-docs/execution/observe_history_renderer.py')
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class HistoryRendererRecipe(unittest.TestCase):
    def setUp(self):
        self.recipe = json.loads((ROOT / gate.RECIPE).read_text())
        self.lock = (ROOT / gate.LOCK).read_bytes()

    def test_exact_candidate_recipe_has36_packages_and_never_creates_admission(self):
        pins = gate.validate_recipe(self.recipe, self.lock)
        self.assertEqual(len(pins), 36)
        self.assertEqual(pins['mkdocs-git-revision-date-localized-plugin'], '1.5.1')
        self.assertFalse(self.recipe['publication_admission'])

    def test_history_lock_has_recipe_ownership_outside_mutable_fixture_dependencies(self):
        self.assertEqual(gate.LOCK, 'tests/bijux-docs/execution/recipes/canon-docs/requirements.lock')
        self.assertFalse((ROOT / 'tests/bijux-docs/generated/requirements-canon-docs.lock.txt').exists())
        self.assertNotIn(Path(gate.LOCK).suffix, {'.txt', '.in'})
        self.assertEqual(gate.observer.sha(self.lock), 'd59e4fdbc3f947a0bcd31e390fd3d1fb1c07fb121b0221d451e2097b1ed29bdb')

    def test_normal_renderer_keeps_current_urllib3_security_revision(self):
        pins = dict(gate.observer.locked_packages((ROOT / 'tests/bijux-docs/generated/requirements.lock.txt').read_bytes()))
        self.assertEqual(pins['urllib3'], '2.8.0')
        self.assertNotIn('gitpython', pins)
        self.assertEqual(self.recipe['packages']['urllib3'], '2.7.0')
        self.assertEqual(self.recipe['packages']['gitpython'], '3.1.59')

    def test_dependency_revisions_cannot_relabel_frozen_canon_source(self):
        for old, new in [(b'urllib3==2.7.0', b'urllib3==2.8.0'), (b'gitpython==3.1.59', b'gitpython==3.1.62')]:
            with self.subTest(package=old):
                changed = self.lock.replace(old, new)
                self.assertNotEqual(changed, self.lock)
                self.assertRaisesRegex(gate.observer.ObservationError, 'lock identity', gate.validate_recipe, self.recipe, changed)
                recipe = {**self.recipe, 'lock_sha256': gate.observer.sha(changed)}
                self.assertRaisesRegex(gate.observer.ObservationError, 'complete Canon', gate.validate_recipe, recipe, changed)

    def test_old_dependency_manifest_path_cannot_claim_relocated_recipe(self):
        recipe = {**self.recipe, 'lock_path': 'tests/bijux-docs/generated/requirements-canon-docs.lock.txt'}
        self.assertRaisesRegex(gate.observer.ObservationError, 'lock identity', gate.validate_recipe, recipe, self.lock)

    def test_observation_workflow_installs_only_the_explicit_frozen_recipe(self):
        workflow = (ROOT / '.github/workflows/renderer-observation.yml').read_text()
        self.assertIn('--requirement ' + gate.LOCK, workflow)
        self.assertIn('      - ' + gate.LOCK, workflow)
        self.assertNotIn('requirements-canon-docs.lock.txt', workflow)

    def test_changed_locked_bytes_rejected(self):
        self.assertRaisesRegex(gate.observer.ObservationError, 'lock identity', gate.validate_recipe, self.recipe, self.lock.replace(b'backrefs==6.2', b'backrefs==8.0'))

    def test_missing_package_cannot_certify_exact36_even_with_fresh_digest(self):
        lock = self.lock.replace(b'smmap==5.0.3\n', b'')
        self.recipe['lock_sha256'] = gate.observer.sha(lock)
        self.assertRaisesRegex(gate.observer.ObservationError, 'complete Canon', gate.validate_recipe, self.recipe, lock)

    def test_observation_cannot_claim_profile_or_source_acceptance(self):
        for field, value in [('publication_admission', True), ('source_kind', 'accepted'), ('source_repository', 'https://example.org/repository')]:
            recipe = {**self.recipe, field: value}
            with self.subTest(field=field):
                self.assertRaises(gate.observer.ObservationError, gate.validate_recipe, recipe, self.lock)

    def test_source_hashes_and_declared_runtime_are_exact(self):
        for field, value in [('source_commit', 'abc'), ('source_uv_lock_sha256', 'z' * 64), ('target_python', '3.12'), ('target_machine', 'arm64')]:
            recipe = {**self.recipe, field: value}
            with self.subTest(field=field):
                self.assertRaises(gate.observer.ObservationError, gate.validate_recipe, recipe, self.lock)

    def test_actual_platform_mismatch_cannot_inherit_recipe_label(self):
        good = {'platform': {'system': 'Linux', 'machine': 'x86_64', 'python': '3.11.13', 'implementation': 'cpython'}}
        gate.validate_runtime(self.recipe, good)
        for field, value in [('system', 'Darwin'), ('machine', 'arm64'), ('python', '3.12.3'), ('implementation', 'pypy')]:
            actual = copy.deepcopy(good)
            actual['platform'][field] = value
            with self.subTest(field=field):
                self.assertRaisesRegex(gate.observer.ObservationError, 'Actual runtime differs', gate.validate_runtime, self.recipe, actual)

    def test_recipe_or_observer_changed_after_commit_cannot_certify_source(self):
        with patch.object(gate.observer, 'source_snapshot', return_value={'files': []}), patch.object(gate.subprocess, 'check_output', return_value=b'other-source'):
            self.assertRaisesRegex(gate.observer.ObservationError, 'differs from committed source', gate.source_snapshot)


if __name__ == '__main__':
    unittest.main()
