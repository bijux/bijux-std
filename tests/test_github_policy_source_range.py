"""Bind protected-path policy to the immutable pull request event graph."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ('.github/workflows/github-policy.yml', 'shared/bijux-gh/workflows/github-policy.yml')


class PullRequestSourceRangeTests(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT / 'artifacts/contracts/policy-source-range'
        artifacts.mkdir(parents=True, exist_ok=True)
        self.sandbox = tempfile.TemporaryDirectory(prefix='event-graph-', dir=artifacts)
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name)
        self.source = self.root / 'source'
        self.proof = artifacts / 'proofs' / self._testMethodName
        self.proof.mkdir(parents=True, exist_ok=True)
        self.commands = []
        self.git(self.root, 'init', '-q', '-b', 'main', str(self.source))
        self.git(self.source, 'config', 'user.email', 'bijux@example.invalid')
        self.git(self.source, 'config', 'user.name', 'Bijux policy tests')
        self.common = self.commit('common.txt', 'Common source', 'test(policy): define common ancestry')
        self.git(self.source, 'checkout', '-qb', 'topic')
        self.commit('.github/workflows/bijux-std.yml', 'name: changed governance', 'test(policy): preserve earlier protected change')
        self.head = self.commit('docs/reader.md', '# Reader', 'test(policy): append reader change')
        self.git(self.source, 'checkout', '-q', 'main')
        self.base = self.commit('base-only.txt', 'Base-side addition', 'test(policy): advance event base separately')
        self.git(self.source, 'checkout', '-qb', 'preview')
        self.git(self.source, 'merge', '--no-ff', '-qm', 'test(policy): create event merge preview', 'topic')
        self.preview = self.git(self.source, 'rev-parse', 'HEAD').stdout.strip()
        self.git(self.source, 'checkout', '-q', 'main')
        self.later = self.commit('later-main.txt', 'Subsequent main addition', 'test(policy): advance mutable branch after event')
        self.git(self.source, 'bundle', 'create', str(self.proof / 'event-graph.bundle'), '--all')
        self.clone = self.root / 'checkout'
        self.git(self.root, 'clone', '-q', '--no-local', str(self.source), str(self.clone))
        self.git(self.clone, 'checkout', '-q', '--detach', self.preview)
        self.addCleanup(self.retain_commands)

    def git(self, directory, *args, check=True):
        command = ['git', '-C', str(directory), *args]
        result = subprocess.run(command, capture_output=True, text=True)
        self.commands.append({'command':command,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        if check:
            result.check_returncode()
        return result

    def commit(self, name, body, subject):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body + '\n')
        self.git(self.source, 'add', name)
        self.git(self.source, 'commit', '-qm', subject)
        return self.git(self.source, 'rev-parse', 'HEAD').stdout.strip()

    def retain_commands(self):
        self.git(self.clone, 'bundle', 'create', str(self.proof / 'qualified-event-graph.bundle'), '--all')
        (self.proof / 'commands.json').write_text(json.dumps({'base':self.base,'head':self.head,'preview':self.preview,'later_main':self.later,'commands':self.commands}, indent=2) + '\n')

    @staticmethod
    def gather_script(workflow):
        text = (ROOT / workflow).read_text()
        step = text.split('      - name: Gather changed files\n', 1)[1].split('      - name:', 1)[0]
        body = step.split('        run: |\n', 1)[1]
        script = '\n'.join(line[10:] for line in body.splitlines()) + '\n'
        return re.sub(r'\$\{\{\s*([^}]+)\}\}', lambda match: 'pull_request' if match.group(1).strip() == 'github.event_name' else '', script)

    def gather(self, workflow, base=None, head=None):
        output = self.proof / (Path(workflow).parts[0].replace('.', '') + '-changed-files.txt')
        output.unlink(missing_ok=True)
        script = self.gather_script(workflow).replace('/tmp/changed-files.txt', str(output))
        env = dict(os.environ, PR_BASE_SHA=self.base if base is None else base,
                   PR_HEAD_SHA=self.head if head is None else head, GITHUB_SHA=self.preview)
        result = subprocess.run(['bash', '-c', script], cwd=self.clone, env=env, capture_output=True, text=True)
        self.commands.append({'workflow':workflow,'shell':script,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        return result, output

    def rejection(self, *, base=None, head=None, reason):
        for workflow in WORKFLOWS:
            result, output = self.gather(workflow, base=base, head=head)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn(reason, result.stderr)
            self.assertFalse(output.exists(), 'Invalid event must not emit a fallback changed-file list')

    def test_mutable_shallow_base_severs_merge_preview_ancestry(self):
        self.assertEqual(self.git(self.clone, 'rev-parse', '--is-shallow-repository').stdout.strip(), 'false')
        self.git(self.clone, 'fetch', '--no-tags', '--prune', '--depth=1', 'origin', 'main')
        result = self.git(self.clone, 'diff', '--name-only', 'origin/main...HEAD', check=False)
        self.assertEqual(result.returncode, 128)
        self.assertIn('no merge base', result.stderr)
        self.assertEqual(self.git(self.clone, 'rev-parse', '--is-shallow-repository').stdout.strip(), 'true')

    def test_event_range_preserves_all_topic_paths_and_excludes_later_main(self):
        self.assertEqual(self.git(self.clone, 'rev-parse', 'origin/main').stdout.strip(), self.later)
        self.assertNotEqual(self.git(self.clone, 'merge-base', self.base, self.head).stdout.strip(), self.base)
        for workflow in WORKFLOWS:
            result, output = self.gather(workflow)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text().splitlines(), ['.github/workflows/bijux-std.yml', 'docs/reader.md'])
            self.assertEqual(self.git(self.clone, 'rev-parse', '--is-shallow-repository').stdout.strip(), 'false')

    def test_event_head_is_used_instead_of_merge_preview_tree(self):
        for workflow in WORKFLOWS:
            result, output = self.gather(workflow)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('base-only.txt', output.read_text())
            self.assertNotIn('later-main.txt', output.read_text())

    def test_empty_base_rejects_without_fallback(self):
        self.rejection(base='', reason='requires full base and head commit SHAs')

    def test_empty_head_rejects_without_fallback(self):
        self.rejection(head='', reason='requires full base and head commit SHAs')

    def test_symbolic_and_abbreviated_identities_reject(self):
        for identity in ('main', self.head[:12], 'null', '--all', self.head + ';true'):
            for role in ('base', 'head'):
                with self.subTest(identity=identity, role=role):
                    self.rejection(**{role:identity}, reason='requires full base and head commit SHAs')

    def test_unknown_full_commit_rejects_without_fallback(self):
        for role in ('base', 'head'):
            with self.subTest(role=role):
                self.rejection(**{role:'0' * 40}, reason='event commit is absent from checkout')

    def test_tag_object_cannot_impersonate_event_commit(self):
        self.git(self.clone, '-c', 'user.email=bijux@example.invalid', '-c', 'user.name=Bijux policy tests', 'tag', '-a', '-m', 'Tag object', 'tag-object', self.head)
        tag = self.git(self.clone, 'rev-parse', 'tag-object').stdout.strip()
        self.rejection(head=tag, reason='event commit is absent from checkout')

    def test_shallow_history_rejects_without_fallback(self):
        self.git(self.clone, 'fetch', '--depth=1', 'origin', 'main')
        self.rejection(reason='requires complete checkout history')

    def test_unrelated_event_commits_reject_without_fallback(self):
        self.git(self.clone, 'checkout', '-q', '--orphan', 'independent')
        self.git(self.clone, 'rm', '-rfq', '.')
        (self.clone / 'independent.txt').write_text('Unrelated root\n')
        self.git(self.clone, 'add', 'independent.txt')
        self.git(self.clone, '-c', 'user.email=bijux@example.invalid', '-c', 'user.name=Bijux policy tests', 'commit', '-qm', 'test(policy): define unrelated source')
        unrelated = self.git(self.clone, 'rev-parse', 'HEAD').stdout.strip()
        self.rejection(head=unrelated, reason='have no common ancestor')

    def test_earlier_protected_change_reaches_actual_policy_checker(self):
        result, output = self.gather(WORKFLOWS[0])
        self.assertEqual(result.returncode, 0, result.stderr)
        command = [sys.executable, '-B', str(ROOT / '.github/scripts/check_protected_github_changes.py'), '--changed-file-list', str(output)]
        result = subprocess.run(command, cwd=self.clone, capture_output=True, text=True)
        self.commands.append({'command':command,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        self.assertEqual(result.returncode, 1)
        self.assertIn('.github/workflows/bijux-std.yml', result.stdout)

    def test_generator_control_path_still_admits_protected_intent(self):
        result, output = self.gather(WORKFLOWS[0])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.git(self.clone, 'checkout', '-qb', 'generator-control', self.head)
        manifest = self.clone / '.github/standards/repo-config.manifest.json'
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text('{}\n')
        self.git(self.clone, 'add', '.github/standards/repo-config.manifest.json')
        self.git(self.clone, '-c', 'user.email=bijux@example.invalid', '-c', 'user.name=Bijux policy tests', 'commit', '-qm', 'test(policy): include reviewed generator control')
        authorized_head = self.git(self.clone, 'rev-parse', 'HEAD').stdout.strip()
        result, output = self.gather(WORKFLOWS[0], head=authorized_head)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('.github/standards/repo-config.manifest.json', output.read_text().splitlines())
        command = [sys.executable, '-B', str(ROOT / '.github/scripts/check_protected_github_changes.py'), '--changed-file-list', str(output)]
        result = subprocess.run(command, cwd=self.clone, capture_output=True, text=True)
        self.commands.append({'command':command,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == '__main__':
    unittest.main()
