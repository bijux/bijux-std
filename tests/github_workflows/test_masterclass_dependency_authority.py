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

    def test_program_runtime_keeps_exact_historical_bytes_and_docs_use_current_source(self):
        _, old_renderer = MODULE.canonical_sources.owning_scripts(self.baseline)
        before, _ = old_renderer.WORKFLOW_EXECUTION.verification.expected_projection(self.baseline, self.target, 'bijux-masterclass')
        for path, body in before.items():
            if path.startswith('.bijux/shared/') and not path.endswith(('deploy-docs.yml', 'publication_admission.py')):
                self.assertEqual(self.expected[path], body, path)
        for path in ['.github/workflows/bijux-std.yml', '.github/workflows/pr-approval-policy.yml', '.github/workflows/github-policy.yml']:
            old = MODULE.parse_workflow(before[path], path)
            new = MODULE.parse_workflow(self.expected[path], path)
            old = MODULE.masterclass.project_action_pins(old, MODULE.masterclass.action_pins(ROOT))
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
        current, _ = MODULE.verification.expected_projection(ROOT, self.target, 'bijux-masterclass')
        self.assertEqual(self.expected['.github/workflows/deploy-docs.yml'], current['.github/workflows/deploy-docs.yml'])
        for path in (ROOT / 'shared/bijux-docs').rglob('*'):
            if path.is_file():
                self.assertEqual(self.expected['.bijux/' + path.relative_to(ROOT).as_posix()], path.read_bytes())

    def test_complete_github_tree_retains_baseline_and_finite_publication_overlays(self):
        baseline = MODULE.masterclass.baseline_github_tree(self.baseline)
        promoted = {'.bijux/shared/bijux-gh/workflows/deploy-docs.yml',
                    '.bijux/shared/bijux-gh/scripts/publication_admission.py'}
        for relative, body in baseline.items():
            if relative not in promoted:
                self.assertEqual(self.expected[relative], body, relative)
        self.assertIn('.bijux/shared/bijux-gh/README.md', self.expected)
        self.assertIn('.bijux/shared/bijux-gh/scripts/render-dependabot.sh', self.expected)

    def test_unexpected_github_paths_are_rejected_without_replacing_them(self):
        self.write_projection()
        directory = self.target / '.bijux/shared/bijux-gh'
        extra = directory / 'scripts/unreviewed.py'
        extra.write_text('retained source outside either authority')
        with patch.object(MODULE.masterclass, 'accepted_baseline', return_value=self.baseline):
            with self.assertRaisesRegex(ValueError, 'complete Masterclass GitHub projection'):
                MODULE.masterclass.verify_masterclass(ROOT, self.target)
        self.assertEqual(extra.read_text(), 'retained source outside either authority')
        extra.unlink()

    def test_uncovered_baseline_byte_changes_and_link_aliases_fail_closed(self):
        self.write_projection()
        path = self.target / '.bijux/shared/bijux-gh/scripts/render-dependabot.sh'
        original = path.read_bytes()
        path.write_bytes(original + b'\n# changed baseline source\n')
        with self.assertRaisesRegex(ValueError, 'complete Masterclass GitHub projection'):
            MODULE.masterclass.verify_github_tree(self.target, self.expected)
        path.write_bytes(original)
        destination = path.with_suffix('.retained'); path.rename(destination); path.symlink_to(destination)
        with self.assertRaisesRegex(ValueError, 'path aliases'):
            MODULE.masterclass.verify_github_tree(self.target, self.expected)
        path.unlink(); destination.rename(path)

    def test_composition_has_two_exact_authorities_and_no_runtime_source_advancement(self):
        authority = json.loads(self.expected[MODULE.masterclass.AUTHORITY_PATH])
        self.assertEqual(authority, {'schema': 1, 'repository': 'bijux-masterclass',
                                     'baseline_sha': MODULE.masterclass.BASELINE_SHA, 'execution_policy_sha': self.sha})
        manifest = json.loads(self.expected['.github/standards/repo-config.manifest.json'])
        baseline_manifest = json.loads((self.baseline / '.github/standards/repo-config.manifest.json').read_text())
        for old, new in zip(baseline_manifest['repositories'], manifest['repositories']):
            for key in set(old) | set(new):
                if key not in {'workflow_execution_policy', 'workflow_allowlist'}:
                    self.assertEqual(old.get(key), new.get(key), key)
            for key, value in old.get('workflow_execution_policy', {}).items():
                if key != 'publication_entrypoints' and old['name'] != 'bijux-masterclass':
                    self.assertEqual(new['workflow_execution_policy'][key], value)
            for name, value in old.get('workflow_execution_policy', {}).get('publication_entrypoints', {}).items():
                if name != 'deploy-docs':
                    self.assertEqual(new['workflow_execution_policy']['publication_entrypoints'][name], value)
            MODULE.documentation_destination(new)
            if old['name'] == 'bijux-masterclass':
                self.assertEqual(new['workflow_execution_policy']['main_verification'], 'existing-events')
        self.assertNotIn('.github/standards/bijux-std.sha', self.expected)
        self.assertEqual(self.expected['.github/standards/bijux-docs.sha'], (self.sha + '\n').encode())
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
                     '.github/scripts/workflow_execution/schema.py', '.github/workflows/dependency-notice.yml',
                     '.github/standards/bijux-docs.sha', '.bijux/shared/bijux-docs/security/build_identity.py']
            for relative in paths:
                path = self.target / relative
                original = path.read_bytes()
                path.write_bytes(original + b'\n# noncanonical override\n')
                with self.subTest(path=relative), self.assertRaises(ValueError):
                    MODULE.masterclass.verify_masterclass(ROOT, self.target)
                path.write_bytes(original)

    def test_finite_action_promotion_preserves_every_other_field(self):
        document = {'on': {'push': {'branches': ['main']}}, 'jobs': {'docs': {
            'steps': [{'uses': 'actions/setup-node@' + 'b' * 40, 'with': {'node-version': '20'}},
                      {'uses': 'actions/setup-node-extra@' + 'c' * 40},
                      {'uses': './actions/setup-node'}, {'run': 'echo docs'}]}}}
        pins = MODULE.masterclass.action_pins(ROOT)
        actual = MODULE.masterclass.project_action_pins(document, pins)
        expected = copy.deepcopy(document)
        expected['jobs']['docs']['steps'][0]['uses'] = pins['actions/setup-node']
        self.assertEqual(actual, expected)
        self.assertEqual(document['jobs']['docs']['steps'][0]['uses'], 'actions/setup-node@' + 'b' * 40)
        self.assertEqual(MODULE.masterclass.project_action_pins(actual, pins), actual)

    def test_missing_mutable_and_ambiguous_canonical_pins_are_rejected(self):
        original = MODULE.masterclass.read_owned
        relative = MODULE.masterclass.ACTION_PIN_SOURCES['actions/setup-node']
        for body in [b'jobs: {docs: {steps: [{uses: actions/setup-node@v7}]}}',
                     b'jobs: {docs: {steps: []}}',
                     ('jobs: {docs: {steps: [{uses: actions/setup-node@' + 'a' * 40
                      + '}, {uses: actions/setup-node@' + 'b' * 40 + '}]}}').encode()]:
            def replacement(root, path):
                return body if path == relative else original(root, path)
            with self.subTest(body=body), patch.object(MODULE.masterclass, 'read_owned', side_effect=replacement):
                with self.assertRaises(ValueError):
                    MODULE.masterclass.action_pins(ROOT)

    def test_previous_projection_is_verified_by_its_own_accepted_policy(self):
        self.write_projection()
        from types import SimpleNamespace
        observed = []
        verifier = SimpleNamespace(verify_masterclass=lambda source, target: observed.append((source, target)))
        renderer = SimpleNamespace(WORKFLOW_EXECUTION=SimpleNamespace(masterclass=verifier))
        previous = self.fixture / 'previous-policy'
        with patch.object(MODULE.masterclass, 'accepted_policy', return_value=previous) as admission, \
                patch.object(MODULE.masterclass, 'owning_scripts', return_value=(None, renderer)):
            self.assertEqual(MODULE.masterclass.admit_previous_projection(ROOT, self.target), previous)
            admission.assert_called_once_with(ROOT, self.target, self.sha)
        self.assertEqual(observed, [(previous, self.target)])

    def test_previous_projection_drift_and_unaccepted_policy_fail_before_mutation(self):
        self.write_projection()
        before = (self.target / MODULE.masterclass.AUTHORITY_PATH).read_bytes()
        from types import SimpleNamespace
        def refused(*args):
            raise ValueError('noncanonical previous bytes')
        renderer = SimpleNamespace(WORKFLOW_EXECUTION=SimpleNamespace(masterclass=SimpleNamespace(verify_masterclass=refused)))
        with patch.object(MODULE.masterclass, 'accepted_policy', return_value=self.fixture), \
                patch.object(MODULE.masterclass, 'owning_scripts', return_value=(None, renderer)):
            with self.assertRaises(ValueError):
                MODULE.masterclass.admit_previous_projection(ROOT, self.target)
        with patch.object(MODULE.masterclass, 'accepted_policy', side_effect=ValueError('unaccepted source')):
            with self.assertRaises(ValueError):
                MODULE.masterclass.admit_previous_projection(ROOT, self.target)
        self.assertEqual((self.target / MODULE.masterclass.AUTHORITY_PATH).read_bytes(), before)

    def test_promotion_advances_only_after_previous_projection_admission(self):
        from .policy_fixtures import source_fixture
        self.write_projection()
        with tempfile.TemporaryDirectory(dir=self.target / 'artifacts' if (self.target / 'artifacts').exists() else self.fixture) as directory:
            # Source admission is mocked only for this authored fixture. Production
            # retains the official accepted-GitHub check before any projection write.
            artifact = self.target / 'artifacts/promotion-contract'
            artifact.mkdir(parents=True, exist_ok=True)
            source, owned = source_fixture(artifact)
            import shutil
            shutil.copytree(ROOT / 'shared/bijux-docs', source / 'shared/bijux-docs')
            fixture_manifest = json.loads((source / '.github/standards/repo-config.manifest.json').read_text())
            canonical = json.loads((ROOT / '.github/standards/repo-config.manifest.json').read_text())
            fixture_manifest['repositories'] = canonical['repositories']
            (source / '.github/standards/repo-config.manifest.json').write_text(json.dumps(fixture_manifest, indent=2) + '\n')
            from .policy_fixtures import refresh_snapshots
            refresh_snapshots(source, owned)
            new_sha = 'b' * 40
            original_owning = owned.masterclass.owning_scripts
            from types import SimpleNamespace
            def previous_verification(previous, target):
                with patch.object(MODULE.masterclass, 'accepted_baseline', return_value=self.baseline):
                    return MODULE.masterclass.verify_masterclass(ROOT, target)
            previous_renderer = SimpleNamespace(WORKFLOW_EXECUTION=SimpleNamespace(
                masterclass=SimpleNamespace(verify_masterclass=previous_verification,
                    expected_masterclass=MODULE.masterclass.expected_masterclass)))
            def owning(root):
                return (None, previous_renderer) if root == ROOT else original_owning(root)
            def git(root, *args):
                if args == ('rev-parse', '--show-toplevel'):
                    return str(source)
                if args == ('rev-parse', 'HEAD'):
                    return new_sha
                if args == ('remote', 'get-url', 'origin'):
                    return 'https://github.com/bijux/bijux-std.git'
                if args == ('status', '--porcelain', '--untracked-files=all'):
                    return ''
                raise AssertionError(args)
            import shutil
            original_run = subprocess.run
            def admitted_fixture(command, **kwargs):
                if command[0] == 'git':
                    return subprocess.CompletedProcess(command, 0, stdout=git(Path(command[2]), *command[3:]), stderr='')
                if command[0] == 'bash' and command[1].endswith('/verify-accepted-source.sh'):
                    return subprocess.CompletedProcess(command, 0)
                return original_run(command, **kwargs)
            try:
                with patch.object(owned.source_authority, 'git', side_effect=git), \
                        patch.object(owned.masterclass.subprocess, 'run', side_effect=admitted_fixture), \
                        patch.object(owned.masterclass, 'accepted_baseline', return_value=self.baseline), \
                        patch.object(owned.masterclass, 'accepted_policy', return_value=ROOT) as previous, \
                        patch.object(owned.masterclass, 'owning_scripts', side_effect=owning):
                    authority_before = (self.target / owned.masterclass.AUTHORITY_PATH).read_bytes()
                    docs = self.target / '.github/workflows/deploy-docs.yml'
                    original_docs = docs.read_bytes()
                    docs.write_bytes(original_docs + b'\n# rejected drift\n')
                    with self.assertRaises(ValueError):
                        owned.masterclass.promote_masterclass(source, self.target, new_sha)
                    self.assertEqual((self.target / owned.masterclass.AUTHORITY_PATH).read_bytes(), authority_before)
                    self.assertEqual(docs.read_bytes(), original_docs + b'\n# rejected drift\n')
                    docs.write_bytes(original_docs)
                    previous.side_effect = ValueError('previous source is not accepted')
                    with self.assertRaises(ValueError):
                        owned.masterclass.promote_masterclass(source, self.target, new_sha)
                    self.assertEqual((self.target / owned.masterclass.AUTHORITY_PATH).read_bytes(), authority_before)
                    previous.side_effect = None
                    extra = self.target / '.bijux/shared/bijux-gh/scripts/uncovered.py'
                    extra.write_text('preserved source beyond the previous partial projection')
                    with patch.object(previous_renderer.WORKFLOW_EXECUTION.masterclass,
                                      'verify_masterclass', return_value={}):
                        with self.assertRaisesRegex(ValueError, 'complete Masterclass GitHub projection'):
                            owned.masterclass.promote_masterclass(source, self.target, new_sha)
                    self.assertEqual(extra.read_text(), 'preserved source beyond the previous partial projection')
                    self.assertEqual((self.target / owned.masterclass.AUTHORITY_PATH).read_bytes(), authority_before)
                    extra.unlink()
                    previous.reset_mock()
                    result = owned.masterclass.promote_masterclass(source, self.target, new_sha)
                    previous.assert_called_once_with(source, self.target, self.sha)
                    self.assertEqual(result['authorities']['execution_policy_sha'], new_sha)
                    self.assertEqual(result['authorities']['baseline_sha'], owned.masterclass.BASELINE_SHA)
                    second = owned.masterclass.promote_masterclass(source, self.target, new_sha)
                    self.assertEqual(second['changed_paths'], [])
                    self.assertEqual(previous.call_count, 1)
            finally:
                shutil.rmtree(artifact)
