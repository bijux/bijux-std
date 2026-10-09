"""Protect authored configuration while adopting source-bound canonical defaults."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / 'shared/bijux-docs'
sys.path.insert(0, str(SHARED / 'tooling'))
from configuration import prior_assets
from configuration.ordered_assets import ordered_list

spec = importlib.util.spec_from_file_location('managed_config_sync', SHARED / 'tooling/scripts/sync_mkdocs_hub.py')
SYNC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SYNC)
PREVIOUS = [
    'assets/javascripts/vendor/mermaid-11.6.0.min.js',
    'assets/javascripts/mermaid-init.js',
    'assets/javascripts/shell/theme-persistence.js',
    'assets/javascripts/shell/viewport-profile.js',
    'assets/javascripts/shell/nav-state.js',
    'assets/javascripts/shell/detail-tabs.js',
    'assets/javascripts/shell/nav-reveal.js',
    'assets/javascripts/shell/bootstrap.js',
    'assets/javascripts/navigation-sync.js',
    'assets/javascripts/external-links.js',
]


class ManagedAssetAdoptionTests(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT / 'artifacts/qualification/managed-asset-adoption/controls'
        artifacts.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(directory.cleanup)
        self.repo = Path(directory.name) / 'consumer'
        self.repo.mkdir()
        self.authority = Path(directory.name) / 'accepted-standard'
        self.authority.mkdir()
        self.shared = self.repo / '.bijux/shared/bijux-docs'
        shutil.copytree(SHARED, self.shared)
        self.current = (self.shared / 'config/mkdocs-baseline.json').read_bytes()
        self.required = json.loads(self.current)['extra_javascript']
        self.context = {'mode': 'accepted-github', 'sha': 'a' * 40,
                        'origin': 'https://github.com/bijux/bijux-std.git',
                        'authority': str(self.authority)}
        self.pin = self.repo / prior_assets.PIN
        self.pin.parent.mkdir(parents=True)
        self.pin.write_text('a' * 40 + '\n')
        self.prefix = 'plugins:\n  - search\n  - autorefs\n  - redirects:\n      redirect_maps:\n        old.md: current.md\n  - git-revision-date-localized:\n      fallback_to_build_date: true\nextra:\n  bijux:\n    repository: bijux-canon\n'
        self.suffix = '\ncopyright: "Authored ownership"\n'
        self.plain = 'extra_javascript:\n' + ''.join('  - ' + name + '\n' for name in PREVIOUS)
        (self.repo / 'mkdocs.shared.yml').write_text(self.prefix + self.plain + self.suffix)
        (self.repo / 'mkdocs.yml').write_text('INHERIT: mkdocs.shared.yml\nsite_name: Canon\nextra:\n  bijux:\n    repository: bijux-canon\n')
        self.calls = []
        self.env = mock.patch.dict(os.environ, {'BIJUX_DOCS_SOURCE_MODE': 'accepted-github'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.context_patch = mock.patch.object(prior_assets, 'source_context', return_value=self.context)
        self.context_patch.start(); self.addCleanup(self.context_patch.stop)
        self.git_patch = mock.patch.object(prior_assets, 'git', side_effect=self.git)
        self.git_patch.start(); self.addCleanup(self.git_patch.stop)
        self.source_patch = mock.patch.object(prior_assets, 'published_bytes', side_effect=self.published)
        self.source_mock = self.source_patch.start(); self.addCleanup(self.source_patch.stop)

    def git(self, root, *args):
        if args == ('rev-parse', '--show-toplevel'): return str(root)
        if args == ('ls-tree', 'HEAD', '--', prior_assets.PIN): return '100644 blob ' + 'c' * 40 + '\t' + prior_assets.PIN
        if args == ('show', 'HEAD:' + prior_assets.PIN): return 'b' * 40
        if args == ('remote', 'get-url', 'origin'): return self.context['origin']
        if args == ('rev-parse', 'HEAD'): return self.context['sha']
        if args == ('status', '--porcelain', '--untracked-files=all'): return ''
        raise AssertionError(args)

    def published(self, context, sha, source):
        self.calls.append((sha, source))
        self.assertEqual(context, self.context)
        self.assertEqual(source, prior_assets.BASELINE)
        return self.current if sha == self.context['sha'] else json.dumps({'extra_javascript': PREVIOUS}).encode()

    def merge(self, content=None):
        return ordered_list(content or self.plain, 'extra_javascript', self.required,
                            self.repo / 'mkdocs.shared.yml', create=True,
                            prior_javascript=lambda: prior_assets.prior_javascript(self.repo, self.shared))

    def test_actual_prior_ten_entry_default_reorders_and_adds_current_dependencies(self):
        before = self.prefix + self.plain + self.suffix
        after = self.merge(before)
        expected = self.prefix + 'extra_javascript:\n' + ''.join('  - ' + name + '\n' for name in self.required) + self.suffix
        self.assertEqual(after, expected)
        self.assertEqual(len(PREVIOUS), 10)
        self.assertEqual(self.calls, [('a' * 40, prior_assets.BASELINE), ('b' * 40, prior_assets.BASELINE)])
        self.calls.clear()
        self.assertEqual(self.merge(after), after)
        self.assertEqual(self.calls, [])

    def test_all_config_projection_preserves_authored_capabilities_and_is_repeatable(self):
        with mock.patch.object(sys, 'argv', ['sync', str(self.repo), str(self.shared)]):
            self.assertEqual(SYNC.main(), 0)
        shared = (self.repo / 'mkdocs.shared.yml').read_text()
        self.assertTrue(shared.startswith(self.prefix))
        self.assertIn(self.suffix, shared)
        before = {name: (self.repo / name).read_bytes() for name in ('mkdocs.shared.yml', 'mkdocs.yml')}
        self.calls.clear()
        with mock.patch.object(sys, 'argv', ['sync', str(self.repo), str(self.shared), '--check']):
            self.assertEqual(SYNC.main(), 0)
        self.assertEqual(before, {name: (self.repo / name).read_bytes() for name in before})
        self.assertEqual(self.calls, [])

    def test_custom_order_and_attributes_and_comments_are_never_legacy_adoption(self):
        variants = [
            self.plain.replace('  - assets/javascripts/mermaid-init.js\n', '').replace('  - assets/javascripts/shell/bootstrap.js\n', '  - assets/javascripts/shell/bootstrap.js\n  - assets/javascripts/mermaid-init.js\n'),
            self.plain.replace('extra_javascript:\n', 'extra_javascript: # authored\n'),
            self.plain.replace('  - assets/javascripts/mermaid-init.js\n', '  - assets/javascripts/mermaid-init.js # ownership\n'),
            self.plain.replace('  - assets/javascripts/mermaid-init.js\n', '  # author explanation\n  - assets/javascripts/mermaid-init.js\n'),
            self.plain + '  - author.js\n',
            self.plain.replace('  - assets/javascripts/mermaid-init.js\n', '  - path: assets/javascripts/mermaid-init.js\n'),
            self.plain.replace('  - assets/javascripts/mermaid-init.js\n', '  - path: assets/javascripts/mermaid-init.js\n    defer: true\n'),
            self.plain.replace('  - assets/javascripts/mermaid-init.js\n', '  - "assets/javascripts/mermaid-init.js"\n'),
            self.plain.replace('  - assets/javascripts/mermaid-init.js\n', '  - assets/javascripts/mermaid-init.js\n  - assets/javascripts/mermaid-init.js\n'),
            self.plain.replace('  - assets/javascripts/mermaid-init.js\n', ''),
        ]
        for variant in variants:
            with self.subTest(content=variant), self.assertRaises(RuntimeError): self.merge(variant)

    def test_local_source_mode_cannot_admit_legacy_order(self):
        with mock.patch.dict(os.environ, {'BIJUX_DOCS_SOURCE_MODE': 'local-verification'}):
            with self.assertRaisesRegex(RuntimeError, 'canonical order conflicts'): self.merge()
        self.assertEqual(self.calls, [])

    def test_untracked_receipt_or_override_cannot_supply_committed_prior_pin(self):
        (self.repo / 'prior-source.json').write_text(json.dumps({'sha': 'b' * 40}))
        with mock.patch.dict(os.environ, {'BIJUX_DOCS_PREVIOUS_STD_REF': 'b' * 40}):
            with mock.patch.object(prior_assets, 'git', side_effect=lambda root, *args: (_ for _ in ()).throw(RuntimeError('required Git source unavailable')) if args == ('show', 'HEAD:' + prior_assets.PIN) else self.git(root, *args)):
                with self.assertRaisesRegex(RuntimeError, 'Git source unavailable'): self.merge()
        self.assertEqual(self.calls, [])

    def test_committed_symlink_directory_or_missing_pin_cannot_prove_old_ownership(self):
        for entry in ('', '120000 blob ' + 'c' * 40 + '\t' + prior_assets.PIN, '040000 tree ' + 'c' * 40 + '\t' + prior_assets.PIN):
            with self.subTest(entry=entry):
                with mock.patch.object(prior_assets, 'git', side_effect=lambda root, *args: entry if args == ('ls-tree', 'HEAD', '--', prior_assets.PIN) else self.git(root, *args)):
                    with self.assertRaisesRegex(RuntimeError, 'committed regular standard pin'): self.merge()
        self.assertEqual(self.calls, [])

    def test_malformed_committed_prior_pin_rejected(self):
        for previous in ('main', 'A' * 40, 'b' * 39, 'b' * 40 + '\n' + 'a' * 40):
            with self.subTest(previous=previous):
                with mock.patch.object(prior_assets, 'git', side_effect=lambda root, *args: previous if args == ('show', 'HEAD:' + prior_assets.PIN) else self.git(root, *args)):
                    with self.assertRaisesRegex(RuntimeError, 'committed exact previous'): self.merge()

    def test_working_pin_mismatch_and_symlink_are_rejected(self):
        self.pin.write_text('c' * 40)
        with self.assertRaisesRegex(RuntimeError, 'working standard pin differs'): self.merge()
        self.pin.unlink(); self.pin.symlink_to(self.repo / 'outside-pin')
        (self.repo / 'outside-pin').write_text('a' * 40)
        with self.assertRaisesRegex(RuntimeError, 'regular working standard pin'): self.merge()

    def test_same_committed_pin_cannot_explain_authored_current_order_drift(self):
        with mock.patch.object(prior_assets, 'git', side_effect=lambda root, *args: 'a' * 40 if args == ('show', 'HEAD:' + prior_assets.PIN) else self.git(root, *args)):
            with self.assertRaisesRegex(RuntimeError, 'canonical order conflicts'): self.merge()
        self.assertEqual(self.calls, [])

    def test_dirty_wrong_head_and_wrong_origin_authorities_rejected(self):
        changes = [(('status', '--porcelain', '--untracked-files=all'), ' M shared/config.json'),
                   (('rev-parse', 'HEAD'), 'c' * 40),
                   (('remote', 'get-url', 'origin'), 'https://github.com/another/standard.git')]
        for changed, answer in changes:
            with self.subTest(changed=changed):
                with mock.patch.object(prior_assets, 'git', side_effect=lambda root, *args: answer if root == self.authority and args == changed else self.git(root, *args)):
                    with self.assertRaisesRegex(RuntimeError, 'clean accepted GitHub'): self.merge()
        self.assertEqual(self.calls, [])

    def test_tampered_current_baseline_not_admitted_by_old_list_match(self):
        (self.shared / 'config/mkdocs-baseline.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'current baseline differs'): self.merge()

    def test_missing_prior_source_leaves_all_config_and_asset_bytes_unchanged(self):
        before = {p.relative_to(self.repo).as_posix(): p.read_bytes() for p in self.repo.rglob('*') if p.is_file()}
        with mock.patch.object(prior_assets, 'published_bytes', side_effect=lambda context, sha, source: self.current if sha == 'a' * 40 else (_ for _ in ()).throw(RuntimeError('prior accepted source unavailable'))):
            with mock.patch.object(sys, 'argv', ['sync', str(self.repo), str(self.shared)]):
                with self.assertRaisesRegex(RuntimeError, 'prior accepted source unavailable'): SYNC.main()
        self.assertEqual(before, {p.relative_to(self.repo).as_posix(): p.read_bytes() for p in self.repo.rglob('*') if p.is_file()})

    def test_malformed_prior_baseline_rejected(self):
        for data in (b'[]', b'{}', b'{', json.dumps({'extra_javascript': ['same.js', 'same.js']}).encode(), json.dumps({'extra_javascript': ['injected\nline.js']}).encode()):
            with self.subTest(data=data):
                with mock.patch.object(prior_assets, 'published_bytes', side_effect=lambda context, sha, source: self.current if sha == 'a' * 40 else data):
                    with self.assertRaisesRegex(RuntimeError, 'invalid previous accepted'): self.merge()


if __name__ == '__main__': unittest.main()
