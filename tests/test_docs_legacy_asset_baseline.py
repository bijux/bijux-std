"""Bind explicitly reviewed historical asset ordering to accepted source bytes."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('legacy_managed_fixture', ROOT / 'tests/test_docs_managed_asset_adoption.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
prior = fixture.prior_assets


class ReviewedLegacyBaselineTests(unittest.TestCase):
    def setUp(self):
        fixture.ManagedAssetAdoptionTests.setUp(self)
        policy = self.shared / 'config/legacy-mkdocs-baselines.json'
        self.registry = json.loads(policy.read_bytes())
        entry = self.registry['baselines'][prior.LEGACY_PIN]
        self.sources = {path: ('controlled source: ' + path).encode() for path in entry['source_evidence']}
        entry['source_evidence'] = {path: hashlib.sha256(data).hexdigest() for path, data in self.sources.items()}
        self.write_registry()

    def write_registry(self):
        self.registry_bytes = json.dumps(self.registry).encode()
        (self.shared / 'config/legacy-mkdocs-baselines.json').write_bytes(self.registry_bytes)

    def git(self, root, *args):
        if args == ('show', 'HEAD:' + prior.PIN):
            return prior.LEGACY_PIN
        return fixture.ManagedAssetAdoptionTests.git(self, root, *args)

    def published(self, context, sha, source):
        self.calls.append((sha, source))
        self.assertEqual(context, self.context)
        if sha == self.context['sha'] and source == prior.BASELINE:
            return self.current
        if sha == self.context['sha'] and source == prior.LEGACY_REGISTRY:
            return self.registry_bytes
        self.assertEqual(sha, prior.LEGACY_PIN)
        return self.sources[source]

    merge = fixture.ManagedAssetAdoptionTests.merge

    def test_reviewed_plain_list_requires_all_bound_predecessor_sources(self):
        after = self.merge()
        self.assertEqual(after, 'extra_javascript:\n' + ''.join('  - ' + name + '\n' for name in self.required))
        self.assertEqual(set(source for sha, source in self.calls if sha == prior.LEGACY_PIN), set(self.sources))
        self.assertNotIn((prior.LEGACY_PIN, prior.BASELINE), self.calls)
        self.assertEqual(self.merge(after), after)

    def test_predecessor_source_digest_change_rejected(self):
        path = next(iter(self.sources))
        self.sources[path] += b' altered'
        with self.assertRaisesRegex(RuntimeError, 'legacy source evidence differs'):
            self.merge()

    def test_unavailable_predecessor_evidence_never_falls_back(self):
        original = self.published
        def unavailable(context, sha, source):
            if sha == prior.LEGACY_PIN:
                raise RuntimeError('controlled exact predecessor source unavailable')
            return original(context, sha, source)
        with mock.patch.object(prior, 'published_bytes', side_effect=unavailable):
            with self.assertRaisesRegex(RuntimeError, 'exact predecessor source unavailable'):
                self.merge()

    def test_untracked_or_changed_registry_cannot_supply_review(self):
        path = self.shared / 'config/legacy-mkdocs-baselines.json'
        for replacement in (b'{}', None):
            with self.subTest(replacement=replacement):
                if replacement is None:
                    path.unlink()
                else:
                    path.write_bytes(replacement)
                with self.assertRaisesRegex(RuntimeError, 'registry differs'):
                    self.merge()
                path.write_bytes(self.registry_bytes)

    def test_symlink_registry_rejected(self):
        path = self.shared / 'config/legacy-mkdocs-baselines.json'
        target = self.repo / 'registry-input.json'
        target.write_bytes(self.registry_bytes)
        path.unlink()
        path.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, 'registry differs'):
            self.merge()

    def test_registry_missing_wrong_or_extra_predecessor_rejected(self):
        original = copy.deepcopy(self.registry)
        for baselines in ({}, {'b' * 40: original['baselines'][prior.LEGACY_PIN]}, {**original['baselines'], 'b' * 40: {}}):
            with self.subTest(baselines=list(baselines)):
                self.registry['baselines'] = baselines
                self.write_registry()
                with self.assertRaisesRegex(RuntimeError, 'invalid reviewed legacy'):
                    self.merge()
        self.registry = original
        self.write_registry()

    def test_empty_evidence_and_invalid_source_paths_rejected(self):
        original = copy.deepcopy(self.registry)
        for evidence in ({}, dict(list(original['baselines'][prior.LEGACY_PIN]['source_evidence'].items())[1:]), {'bijux-docs/../outside': 'a' * 64}, {'bijux-docs/source': 'A' * 64}):
            with self.subTest(evidence=evidence):
                self.registry['baselines'][prior.LEGACY_PIN]['source_evidence'] = evidence
                self.write_registry()
                with self.assertRaisesRegex(RuntimeError, 'invalid reviewed legacy'):
                    self.merge()
        self.registry = original
        self.write_registry()

    def test_registry_malformed_shapes_and_unreviewed_records_rejected(self):
        original = copy.deepcopy(self.registry)
        for mutation in ('schema', 'review', 'record-extra'):
            self.registry = copy.deepcopy(original)
            if mutation == 'schema':
                self.registry['schema'] = True
            elif mutation == 'review':
                self.registry['baselines'][prior.LEGACY_PIN]['review'] = ''
            else:
                self.registry['baselines'][prior.LEGACY_PIN]['extra'] = 'unauthorized'
            self.write_registry()
            with self.subTest(mutation=mutation), self.assertRaisesRegex(RuntimeError, 'invalid reviewed legacy'):
                self.merge()

    def test_complete_literal_review_does_not_admit_authored_execution_changes(self):
        fixture.ManagedAssetAdoptionTests.test_custom_order_and_attributes_and_comments_are_never_legacy_adoption(self)

    def test_local_verification_cannot_use_accepted_legacy_review(self):
        fixture.ManagedAssetAdoptionTests.test_local_source_mode_cannot_admit_legacy_order(self)

    def test_missing_registry_leaves_configuration_and_assets_unchanged(self):
        before = {path.relative_to(self.repo).as_posix(): path.read_bytes() for path in self.repo.rglob('*') if path.is_file()}
        original = self.published
        def unavailable(context, sha, source):
            if source == prior.LEGACY_REGISTRY:
                raise RuntimeError('controlled accepted registry unavailable')
            return original(context, sha, source)
        with mock.patch.object(prior, 'published_bytes', side_effect=unavailable):
            with mock.patch.object(sys, 'argv', ['sync', str(self.repo), str(self.shared)]):
                with self.assertRaisesRegex(RuntimeError, 'accepted registry unavailable'):
                    fixture.SYNC.main()
        after = {path.relative_to(self.repo).as_posix(): path.read_bytes() for path in self.repo.rglob('*') if path.is_file()}
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
