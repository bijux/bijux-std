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
                                           '.github', 'shared/bijux-gh', 'shared/bijux-docs',
                                           'shared/bijux-checks/scripts/verify-accepted-source.sh'])
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(cls.baseline, filter='data')
        cls.target = cls.fixture / 'bijux-masterclass'
        cls.target.mkdir()
        manifest = cls.target / MODULE.masterclass.DIRECTORY_MANIFEST_PATH
        manifest.parent.mkdir(parents=True)
        manifest.write_text('0' * 64 + '  shared/bijux-docs\n' + '1' * 64 + '  shared/bijux-makes\n')
        cls.sha = 'a' * 40
        cls.expected, cls.absent = MODULE.masterclass.expected_masterclass(ROOT, cls.baseline, cls.target, cls.sha)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_program_runtime_keeps_exact_historical_bytes_and_docs_use_current_source(self):
        _, old_renderer = MODULE.canonical_sources.owning_scripts(self.baseline)
        before, _ = old_renderer.WORKFLOW_EXECUTION.verification.expected_projection(self.baseline, self.target, 'bijux-masterclass')
        for path, body in before.items():
            if (path.startswith('.bijux/shared/') and not path.startswith(MODULE.masterclass.DOCS_DESTINATION)
                    and not path.endswith(('deploy-docs.yml', 'publication_admission.py'))):
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
        current_docs = {'.bijux/' + path.relative_to(ROOT).as_posix(): path.read_bytes()
                        for path in (ROOT / 'shared/bijux-docs').rglob('*') if path.is_file()}
        self.assertEqual({path: body for path, body in self.expected.items()
                          if path.startswith(MODULE.masterclass.DOCS_DESTINATION)}, current_docs)
        self.assertTrue(set(before) & set(self.expected))

    def test_complete_github_tree_retains_baseline_and_finite_publication_overlays(self):
        baseline = MODULE.masterclass.baseline_github_tree(self.baseline)
        promoted = {'.bijux/shared/bijux-gh/workflows/deploy-docs.yml',
                    '.bijux/shared/bijux-gh/scripts/publication_admission.py'}
        for relative, body in baseline.items():
            if relative not in promoted:
                self.assertEqual(self.expected[relative], body, relative)
        self.assertIn('.bijux/shared/bijux-gh/README.md', self.expected)
        self.assertIn('.bijux/shared/bijux-gh/scripts/render-dependabot.sh', self.expected)

    def test_documentation_directory_row_follows_exact_component_and_preserves_other_rows(self):
        self.write_projection()
        path = self.target / MODULE.masterclass.DIRECTORY_MANIFEST_PATH
        original = path.read_bytes()
        rows = original.splitlines(keepends=True)
        rows[0] = b'0' * 64 + b' shared/bijux-docs\n'
        path.write_bytes(b''.join(rows))
        expected = MODULE.masterclass.documentation_directory_manifest(ROOT, ROOT, self.target)
        self.assertEqual(expected.splitlines()[0].split()[0], original.splitlines()[0].split()[0])
        self.assertEqual(expected.splitlines(keepends=True)[1:], rows[1:])
        with patch.object(MODULE.masterclass, 'accepted_baseline', return_value=self.baseline):
            with self.assertRaisesRegex(ValueError, 'noncanonical bounded Masterclass projection'):
                MODULE.masterclass.verify_masterclass(ROOT, self.target)
        self.assertEqual(path.read_bytes(), b''.join(rows))
        path.write_bytes(original)

    def test_directory_manifest_refuses_missing_duplicate_and_aliased_rows(self):
        self.write_projection()
        path = self.target / MODULE.masterclass.DIRECTORY_MANIFEST_PATH
        original = path.read_bytes()
        rows = original.splitlines(keepends=True)
        for body in (rows[1], original + rows[0], b'malformed\n'):
            with self.subTest(body=body):
                path.write_bytes(body)
                with self.assertRaises(ValueError):
                    MODULE.masterclass.documentation_directory_manifest(ROOT, ROOT, self.target)
                self.assertEqual(path.read_bytes(), body)
        path.write_bytes(original)
        alias = path.with_suffix('.retained')
        path.rename(alias); path.symlink_to(alias)
        with self.assertRaises(ValueError):
            MODULE.masterclass.documentation_directory_manifest(ROOT, ROOT, self.target)
        path.unlink(); alias.rename(path)

    def test_manifest_repair_uses_previous_projection_and_refuses_dirty_metadata(self):
        from .policy_fixtures import source_fixture
        import shutil
        self.write_projection()
        artifact = self.target / 'artifacts/manifest-owner'
        artifact.mkdir(parents=True, exist_ok=True)
        source, owned = source_fixture(artifact)
        shutil.copyfile(ROOT / 'shared/bijux-checks/scripts/directory-tree-sha256.sh',
                        source / 'shared/bijux-checks/scripts/directory-tree-sha256.sh')
        path = self.target / owned.masterclass.DIRECTORY_MANIFEST_PATH
        correct = path.read_bytes()
        stale = b'0' * 64 + correct[64:]
        path.write_bytes(stale)
        # Real Git owns all consumer preimages; only official source acceptance is
        # substituted for this authored fixture, as in the promotion contract.
        subprocess.run(['git', '-C', str(self.target), 'init', '--quiet'], check=True)
        subprocess.run(['git', '-C', str(self.target), 'add', '.bijux', '.github'], check=True)
        subprocess.run(['git', '-C', str(self.target), '-c', 'user.name=Bijux fixture',
                        '-c', 'user.email=fixture@bijux.local', 'commit', '--quiet', '-m',
                        'test(std): bind component fixture preimages'], check=True)
        import sys
        authority_module = sys.modules[owned.masterclass.__package__ + '.source_authority']
        original_git = authority_module.git
        def git(root, *args):
            if root == source:
                return {('rev-parse', 'HEAD'): 'b' * 40,
                        ('remote', 'get-url', 'origin'): 'https://github.com/bijux/bijux-std.git',
                        ('status', '--porcelain', '--untracked-files=all'): ''}[args]
            return original_git(root, *args)
        original_run = subprocess.run
        def accepted(command, **kwargs):
            if command[0] == 'bash' and command[1].endswith('/verify-accepted-source.sh'):
                return subprocess.CompletedProcess(command, 0)
            return original_run(command, **kwargs)
        checksum = self.target / '.github/bijux-std-shared.sha256'
        checksum.write_text(''.join(line for line in checksum.read_text().splitlines(keepends=True)
                                    if owned.masterclass.DIRECTORY_MANIFEST_PATH not in line))
        try:
            with patch.object(authority_module, 'git', side_effect=git), \
                    patch.object(owned.masterclass.subprocess, 'run', side_effect=accepted), \
                    patch.object(owned.masterclass, 'admit_previous_projection', return_value=ROOT) as previous, \
                    patch.object(owned.masterclass, 'accepted_baseline', return_value=self.baseline):
                path.write_bytes(stale + b'invalid user change\n')
                with self.assertRaises(subprocess.CalledProcessError):
                    owned.masterclass.reconcile_documentation_directory_manifest(source, self.target, 'b' * 40)
                previous.assert_not_called()
                path.write_bytes(stale)
                before = {relative: (self.target / relative).read_bytes() for relative, body in self.expected.items()
                          if body is not None and relative != owned.masterclass.DIRECTORY_MANIFEST_PATH}
                result = owned.masterclass.reconcile_documentation_directory_manifest(source, self.target, 'b' * 40)
                previous.assert_called_once_with(source, self.target)
                self.assertEqual(result['changed_paths'], [owned.masterclass.DIRECTORY_MANIFEST_PATH])
                self.assertEqual(path.read_bytes(), correct)
                self.assertEqual(before, {relative: (self.target / relative).read_bytes() for relative in before})
        finally:
            shutil.rmtree(artifact)

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

    def retained_docs_projection(self):
        docs_source = self.fixture / 'accepted-documentation'
        directory = docs_source / 'shared/bijux-docs'
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'reader.js').write_text('exact independently accepted renderer')
        expected, _ = MODULE.masterclass.expected_masterclass(
            ROOT, self.baseline, self.target, self.sha,
            documentation_root=docs_source, documentation_sha='c' * 40)
        self.write_projection()
        import shutil
        shutil.rmtree(self.target / '.bijux/shared/bijux-docs')
        for relative, body in expected.items():
            if body is not None:
                path = self.target / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
        (self.target / '.github/bijux-std-shared.sha256').write_text(''.join(
            hashlib.sha256(body).hexdigest() + '  ' + relative + '\n'
            for relative, body in sorted(expected.items()) if body is not None))
        subprocess.run(['git', '-C', str(self.target), 'init', '--quiet'], check=True)
        subprocess.run(['git', '-C', str(self.target), 'add', MODULE.masterclass.DOCS_PIN_PATH], check=True)
        return docs_source, expected

    def test_retained_docs_keep_independent_pin_bytes_and_execution_authority(self):
        docs_source, expected = self.retained_docs_projection()
        with patch.object(MODULE.masterclass, 'accepted_baseline', return_value=self.baseline), \
                patch.object(MODULE.masterclass, 'accepted_policy', return_value=docs_source) as accepted:
            proof = MODULE.masterclass.verify_masterclass(ROOT, self.target)
        self.assertEqual(proof['execution_authorities']['execution_policy_sha'], self.sha)
        self.assertEqual(expected[MODULE.masterclass.DOCS_PIN_PATH], ('c' * 40 + '\n').encode())
        self.assertEqual(accepted.call_count, 2)
        accepted.assert_called_with(ROOT, self.target, 'c' * 40)
        self.assertEqual(expected['.bijux/shared/bijux-docs/reader.js'], b'exact independently accepted renderer')

    def test_retained_docs_unaccepted_source_and_untracked_pin_refuse(self):
        self.retained_docs_projection()
        with patch.object(MODULE.masterclass, 'accepted_policy', side_effect=ValueError('unaccepted docs')):
            with self.assertRaisesRegex(ValueError, 'unaccepted docs'):
                MODULE.masterclass.documentation_authority(ROOT, self.target, self.sha)
        subprocess.run(['git', '-C', str(self.target), 'rm', '--cached', MODULE.masterclass.DOCS_PIN_PATH], check=True, capture_output=True)
        with self.assertRaises(subprocess.CalledProcessError):
            MODULE.masterclass.documentation_authority(ROOT, self.target, self.sha)
        subprocess.run(['git', '-C', str(self.target), 'add', MODULE.masterclass.DOCS_PIN_PATH], check=True)

    def test_retained_docs_rebound_bytes_extra_paths_and_symlinks_refuse(self):
        docs_source, expected = self.retained_docs_projection()
        directory = self.target / '.bijux/shared/bijux-docs'
        owned = directory / 'reader.js'
        original = owned.read_bytes()
        for mutation in ['changed', 'extra', 'link', 'fifo']:
            with self.subTest(mutation=mutation):
                extra = directory / 'unadmitted.js'
                if mutation == 'changed': owned.write_bytes(original + b' changed')
                elif mutation == 'extra': extra.write_bytes(original)
                elif mutation == 'link': owned.unlink(); owned.symlink_to(docs_source / 'shared/bijux-docs/reader.js')
                else:
                    import os
                    os.mkfifo(extra)
                with self.assertRaises(ValueError):
                    MODULE.masterclass.verify_documentation_tree(self.target, expected)
                if mutation in {'extra', 'fifo'}: extra.unlink()
                elif mutation == 'link': owned.unlink(); owned.write_bytes(original)
                else: owned.write_bytes(original)

    def test_retained_docs_physical_source_mutation_at_exit_refuses(self):
        docs_source, _ = self.retained_docs_projection()
        path = docs_source / 'shared/bijux-docs/reader.js'
        calls = []
        def accepted(*args):
            calls.append(args)
            if len(calls) == 2: path.write_text('changed accepted source during verification')
            return docs_source
        with patch.object(MODULE.masterclass, 'accepted_baseline', return_value=self.baseline), \
                patch.object(MODULE.masterclass, 'accepted_policy', side_effect=accepted):
            with self.assertRaisesRegex(ValueError, 'source authority changed'):
                MODULE.masterclass.verify_masterclass(ROOT, self.target)
        self.assertEqual(len(calls), 2)

    def test_retained_docs_pin_mutation_during_projection_refuses(self):
        docs_source, _ = self.retained_docs_projection()
        original = MODULE.masterclass.verify_github_tree
        def mutate_pin(target, expected):
            original(target, expected)
            (target / MODULE.masterclass.DOCS_PIN_PATH).write_text('d' * 40 + '\n')
        with patch.object(MODULE.masterclass, 'accepted_baseline', return_value=self.baseline), \
                patch.object(MODULE.masterclass, 'accepted_policy', return_value=docs_source), \
                patch.object(MODULE.masterclass, 'verify_github_tree', side_effect=mutate_pin):
            with self.assertRaisesRegex(ValueError, 'documentation authority changed'):
                MODULE.masterclass.verify_masterclass(ROOT, self.target)

    def test_retained_docs_require_complete_finite_authority_pair(self):
        for kwargs in [{'documentation_root': ROOT}, {'documentation_sha': 'c' * 40},
                       {'documentation_root': ROOT, 'documentation_sha': 'main'}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                MODULE.masterclass.expected_masterclass(ROOT, self.baseline, self.target, self.sha, **kwargs)
        for value in [1, 'true', None]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'explicit boolean'):
                MODULE.masterclass.promote_masterclass(ROOT, self.target, self.sha, keep_documentation=value)

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
            shutil.copyfile(ROOT / 'shared/bijux-checks/scripts/directory-tree-sha256.sh',
                            source / 'shared/bijux-checks/scripts/directory-tree-sha256.sh')
            fixture_manifest = json.loads((source / '.github/standards/repo-config.manifest.json').read_text())
            canonical = json.loads((ROOT / '.github/standards/repo-config.manifest.json').read_text())
            fixture_manifest['repositories'] = canonical['repositories']
            (source / '.github/standards/repo-config.manifest.json').write_text(json.dumps(fixture_manifest, indent=2) + '\n')
            from .policy_fixtures import refresh_snapshots
            refresh_snapshots(source, owned)
            old_asset = next((ROOT / 'shared/bijux-docs/assets/javascripts').glob('material-search.*.js'))
            old_relative = '.bijux/' + old_asset.relative_to(ROOT).as_posix()
            replacement_body = old_asset.read_bytes() + b'\n// admitted documentation asset fixture\n'
            replacement_name = 'material-search.' + hashlib.sha256(replacement_body).hexdigest() + '.js'
            replacement = source / old_asset.relative_to(ROOT).parent / replacement_name
            replacement.write_bytes(replacement_body)
            (source / old_asset.relative_to(ROOT)).unlink()
            replacement_relative = '.bijux/' + replacement.relative_to(source).as_posix()
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
                if args == ('ls-files', '--error-unmatch', owned.masterclass.DOCS_PIN_PATH):
                    return owned.masterclass.DOCS_PIN_PATH
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
                    old_target = self.target / old_relative
                    original_asset = old_target.read_bytes()
                    docs_extra = old_target.parent / 'unadmitted.js'
                    for mutation in ('changed', 'extra', 'symlink', 'hardlink'):
                        with self.subTest(documentation_mutation=mutation):
                            if mutation == 'changed':
                                old_target.write_bytes(original_asset + b' changed')
                            elif mutation == 'extra':
                                docs_extra.write_bytes(original_asset)
                            elif mutation == 'symlink':
                                old_target.unlink(); old_target.symlink_to(old_asset)
                            else:
                                import os
                                os.link(old_target, docs_extra)
                            with patch.object(previous_renderer.WORKFLOW_EXECUTION.masterclass,
                                              'verify_masterclass', return_value={}):
                                with self.assertRaisesRegex(ValueError, 'Masterclass documentation'):
                                    owned.masterclass.promote_masterclass(source, self.target, new_sha)
                            self.assertEqual((self.target / owned.masterclass.AUTHORITY_PATH).read_bytes(), authority_before)
                            self.assertFalse((self.target / replacement_relative).exists())
                            if mutation in ('extra', 'hardlink'): docs_extra.unlink()
                            elif mutation == 'symlink': old_target.unlink(); old_target.write_bytes(original_asset)
                            else: old_target.write_bytes(original_asset)
                    checksum = self.target / '.github/bijux-std-shared.sha256'
                    checksum_before = checksum.read_bytes()
                    old_binding = hashlib.sha256(original_asset).hexdigest() + '  ' + old_relative + '\n'
                    self.assertIn(old_binding.encode(), checksum_before)
                    for changed_checksum in (checksum_before.replace(old_binding.encode(), b''),
                                             checksum_before + old_binding.encode(),
                                             checksum_before.replace(old_binding.encode(), ('0' * 64 + '  ' + old_relative + '\n').encode())):
                        with self.subTest(checksum_retirement=changed_checksum):
                            checksum.write_bytes(changed_checksum)
                            with self.assertRaisesRegex(ValueError, 'exact prior checksum'):
                                owned.masterclass.promote_masterclass(source, self.target, new_sha)
                            self.assertEqual(old_target.read_bytes(), original_asset)
                            self.assertFalse((self.target / replacement_relative).exists())
                            self.assertEqual((self.target / owned.masterclass.AUTHORITY_PATH).read_bytes(), authority_before)
                    checksum.write_bytes(checksum_before)
                    previous.reset_mock()
                    result = owned.masterclass.promote_masterclass(source, self.target, new_sha)
                    previous.assert_called_once_with(source, self.target, self.sha)
                    self.assertEqual(result['authorities']['execution_policy_sha'], new_sha)
                    self.assertEqual(result['authorities']['baseline_sha'], owned.masterclass.BASELINE_SHA)
                    self.assertFalse(old_target.exists())
                    self.assertIn(old_relative, result['changed_paths'])
                    self.assertEqual((self.target / replacement_relative).read_bytes(), replacement_body)
                    self.assertNotIn(old_relative, checksum.read_text())
                    self.assertIn(replacement_relative, checksum.read_text())
                    second = owned.masterclass.promote_masterclass(source, self.target, new_sha)
                    self.assertEqual(second['changed_paths'], [])
                    self.assertEqual(previous.call_count, 1)
                    (self.target / replacement_relative).unlink()
                    self.write_projection()
                    previous.reset_mock()
                    reader = source / 'shared/bijux-docs/README.md'
                    reader.write_bytes(reader.read_bytes() + b'\nchanged next-source documentation\n')
                    original_reader = (ROOT / 'shared/bijux-docs/README.md').read_bytes()
                    kept = owned.masterclass.promote_masterclass(source, self.target, new_sha, keep_documentation=True)
                    self.assertEqual(kept['authorities']['execution_policy_sha'], new_sha)
                    self.assertEqual((self.target / owned.masterclass.DOCS_PIN_PATH).read_text().strip(), self.sha)
                    self.assertEqual((self.target / '.bijux/shared/bijux-docs/README.md').read_bytes(), original_reader)
                    self.assertEqual(old_target.read_bytes(), original_asset)
                    self.assertFalse((self.target / replacement_relative).exists())
                    self.assertEqual((self.target / '.github/standards/bijux-std.sha').read_text().strip(), owned.masterclass.BASELINE_SHA)
                    self.assertGreaterEqual(previous.call_count, 3)
                    self.assertEqual(owned.masterclass.promote_masterclass(source, self.target, new_sha, keep_documentation=True)['changed_paths'], [])
            finally:
                shutil.rmtree(artifact)
