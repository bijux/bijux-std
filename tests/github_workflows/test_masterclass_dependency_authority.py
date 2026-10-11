"""The Masterclass dependency policy cannot silently advance its runtime baseline."""
from __future__ import annotations
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from .policy_fixtures import MODULE, ROOT


class MasterclassDependencyAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures = ROOT / 'artifacts/dependency-notification/masterclass-fixtures'
        fixtures.mkdir(parents=True, exist_ok=True)
        cls.directory = tempfile.TemporaryDirectory(dir=fixtures)
        cls.fixture = Path(cls.directory.name)
        cls.baseline = cls.fixture / 'baseline'
        cls.baseline.mkdir()
        archive = subprocess.check_output(['git', '-C', str(ROOT), 'archive', MODULE.masterclass.BASELINE_SHA,
                                           '.github', 'shared/bijux-gh', 'shared/bijux-checks/scripts/verify-accepted-source.sh'])
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(cls.baseline, filter='data')
        cls.target = cls.fixture / 'bijux-masterclass'
        cls.target.mkdir()
        cls.sha = 'a' * 40
        cls.expected, cls.absent = MODULE.masterclass.expected_masterclass(ROOT, cls.baseline, cls.target, cls.sha)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_product_docs_events_and_shared_runtime_keep_exact_historical_bytes(self):
        _, old_renderer = MODULE.canonical_sources.owning_scripts(self.baseline)
        before, _ = old_renderer.WORKFLOW_EXECUTION.verification.expected_projection(self.baseline, self.target, 'bijux-masterclass')
        for path, body in before.items():
            if path.startswith('.bijux/shared/') or path == '.github/workflows/deploy-docs.yml':
                self.assertEqual(self.expected[path], body, path)
        for path in ['.github/workflows/bijux-std.yml', '.github/workflows/pr-approval-policy.yml', '.github/workflows/github-policy.yml']:
            old = MODULE.parse_workflow(before[path], path)
            new = MODULE.parse_workflow(self.expected[path], path)
            self.assertEqual(old['on'], new['on'], path)
            for identity, old_job in old['jobs'].items():
                new_job = new['jobs'][identity]
                for key in set(old_job) | set(new_job):
                    if key in {'name', 'if'}:
                        continue
                    if key == 'steps' and path.endswith('/github-policy.yml'):
                        original = copy.deepcopy(old_job['steps']); actual = copy.deepcopy(new_job['steps'])
                        original_selector = next(item for item in original if item.get('name') == 'Select canonical workflow verification source')
                        actual_selector = next(item for item in actual if item.get('name') == 'Select canonical workflow verification source')
                        self.assertIn('dependency-notification-source.json', actual_selector['run'])
                        actual_selector['run'] = original_selector['run']
                        self.assertEqual(actual, original)
                    else:
                        self.assertEqual(new_job.get(key), old_job.get(key), (path, identity, key))

    def test_composition_has_two_exact_authorities_and_no_runtime_source_advancement(self):
        authority = json.loads(self.expected[MODULE.masterclass.AUTHORITY_PATH])
        self.assertEqual(authority, {'schema': 1, 'repository': 'bijux-masterclass',
                                     'baseline_sha': MODULE.masterclass.BASELINE_SHA, 'execution_policy_sha': self.sha})
        manifest = json.loads(self.expected['.github/standards/repo-config.manifest.json'])
        baseline_manifest = json.loads((self.baseline / '.github/standards/repo-config.manifest.json').read_text())
        for old, new in zip(baseline_manifest['repositories'], manifest['repositories']):
            if old['name'] != 'bijux-masterclass':
                self.assertEqual(old, new)
            else:
                for key in set(old) | set(new):
                    if key not in {'workflow_execution_policy', 'workflow_allowlist'}:
                        self.assertEqual(old.get(key), new.get(key), key)
                self.assertEqual(new['workflow_execution_policy']['main_verification'], 'existing-events')
        self.assertNotIn('.github/standards/bijux-std.sha', self.expected)
        self.assertNotIn('.bijux/shared/bijux-gh/workflows/dependency-notice.yml', self.expected)

    def write_projection(self):
        for relative, body in self.expected.items():
            if body is not None:
                path = self.target / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
        (self.target / '.github/standards/bijux-std.sha').write_text(MODULE.masterclass.BASELINE_SHA + '\n')
        (self.target / '.github/bijux-std-shared.sha256').write_text(''.join(
            hashlib.sha256(body).hexdigest() + '  ' + relative + '\n'
            for relative, body in sorted(self.expected.items()) if body is not None
        ))

    def test_forged_authority_baseline_and_additional_overlay_fields_fail_closed(self):
        self.write_projection()
        path = self.target / MODULE.masterclass.AUTHORITY_PATH
        good = json.loads(path.read_text())
        for mutation in [{'repository': 'bijux-canon'}, {'schema': True}, {'baseline_sha': 'b' * 40},
                         {'execution_policy_sha': 'main'}, {'extra_paths': ['docs/']}]:
            with self.subTest(mutation=mutation):
                path.write_text(json.dumps({**good, **mutation}))
                with self.assertRaises(ValueError):
                    MODULE.masterclass.read_authority(self.target)
        path.write_text(json.dumps(good))
        (self.target / '.github/standards/bijux-std.sha').write_text('b' * 40 + '\n')
        with self.assertRaises(ValueError):
            MODULE.masterclass.read_authority(self.target)

    def test_projection_admits_only_exact_composition_and_refuses_rebound_shared_bytes(self):
        self.write_projection()
        with patch.object(MODULE.masterclass, 'accepted_baseline', return_value=self.baseline):
            proof = MODULE.masterclass.verify_masterclass(ROOT, self.target)
            self.assertEqual(proof['execution_authorities']['execution_policy_sha'], self.sha)
            paths = ['.github/workflows/deploy-docs.yml', '.bijux/shared/bijux-gh/workflows/github-policy.yml',
                     '.github/scripts/workflow_execution/schema.py', '.github/workflows/dependency-notice.yml']
            for relative in paths:
                path = self.target / relative
                original = path.read_bytes()
                path.write_bytes(original + b'\n# noncanonical override\n')
                with self.subTest(path=relative), self.assertRaises(ValueError):
                    MODULE.masterclass.verify_masterclass(ROOT, self.target)
                path.write_bytes(original)
