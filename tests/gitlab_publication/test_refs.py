"""Exercise publication decisions using actual Git ancestry and tag objects."""
from pathlib import Path
import importlib.util
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ReferencePublicationTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'shared/bijux-gitlab/publication/refs.py').is_file(),
                        'Accepted-reference publication must have a source-owned ancestry gate')
        spec = importlib.util.spec_from_file_location('bijux_publication_refs', ROOT / 'shared/bijux-gitlab/publication/refs.py')
        self.refs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.refs)
        self.scratch = tempfile.TemporaryDirectory(dir=ROOT / 'artifacts')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.git('init', '--quiet', '--initial-branch=main')
        self.git('config', 'user.name', 'Bijux publication fixture')
        self.git('config', 'user.email', 'publication@example.invalid')
        self.first = self.commit('baseline')
        self.candidate = self.commit('accepted')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True, stderr=subprocess.PIPE).strip()

    def commit(self, value):
        (self.root / 'source.txt').write_text(value)
        self.git('add', 'source.txt')
        self.git('commit', '--quiet', '-m', value)
        return self.git('rev-parse', 'HEAD')

    def test_only_fast_forward_or_exact_replay_is_admitted(self):
        self.assertEqual(self.refs.branch_action(self.root, self.first, self.candidate), 'advance')
        self.assertEqual(self.refs.branch_action(self.root, self.candidate, self.candidate), 'unchanged')
        with self.assertRaises(ValueError):
            self.refs.branch_action(self.root, self.candidate, self.first)
        self.git('checkout', '--quiet', self.first)
        divergent = self.commit('unreviewed destination')
        with self.assertRaises(ValueError):
            self.refs.branch_action(self.root, divergent, self.candidate)

    def test_unknown_or_noncommit_objects_cannot_authorize_default_branch(self):
        for value in ('a' * 40, 'HEAD', '--all', '', self.git('rev-parse', 'HEAD:source.txt')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.refs.branch_action(self.root, value, self.candidate)

    def test_tag_object_identity_is_retained_and_conflicts_are_refused(self):
        self.git('tag', '-a', 'v1.0.0', '-m', 'immutable tag', self.candidate)
        tag = self.git('rev-parse', 'refs/tags/v1.0.0')
        self.assertNotEqual(tag, self.candidate)
        self.assertEqual(self.refs.tag_action('', tag), 'create')
        self.assertEqual(self.refs.tag_action(tag, tag), 'unchanged')
        with self.assertRaises(ValueError): self.refs.tag_action(self.first, tag)

    def test_push_is_fast_forward_only_and_returns_independent_acknowledgement(self):
        bare = self.root / 'mirror.git'
        self.git('init', '--quiet', '--bare', str(bare))
        self.git('push', '--quiet', str(bare), self.first + ':refs/heads/main')
        result = self.refs.publish_branch(self.root, str(bare), self.candidate)
        self.assertEqual(result['before'], self.first)
        self.assertEqual(result['after'], self.candidate)
        self.assertEqual(result['status'], 'published')
        replay = self.refs.publish_branch(self.root, str(bare), self.candidate)
        self.assertEqual(replay['status'], 'unchanged')
        self.assertEqual(self.git('ls-remote', str(bare), 'refs/heads/main').split()[0], self.candidate)

    def test_foreign_ahead_destination_is_preserved(self):
        bare = self.root / 'mirror.git'
        self.git('init', '--quiet', '--bare', str(bare))
        newer = self.commit('later destination')
        self.git('push', '--quiet', str(bare), newer + ':refs/heads/main')
        with self.assertRaises(ValueError): self.refs.publish_branch(self.root, str(bare), self.candidate)
        self.assertEqual(self.git('ls-remote', str(bare), 'refs/heads/main').split()[0], newer)
