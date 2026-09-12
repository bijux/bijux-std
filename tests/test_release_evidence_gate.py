from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / 'shared/bijux-gh/workflows/release-pypi.yml'


class ReleaseEvidenceGateTests(unittest.TestCase):
    def test_every_publish_route_requires_successful_prepublication(self) -> None:
        workflow = WORKFLOW.read_text()
        jobs = dict(re.findall(r'^  ([a-z_]+):\n(.*?)(?=^  [a-z_]+:\n|\Z)', workflow, re.M | re.S))
        publish_jobs = {name: body for name, body in jobs.items() if 'uses: pypa/gh-action-pypi-publish@' in body or 'Publish PyPI distributions with custom command' in body}
        self.assertEqual(set(publish_jobs), {'publish_artifact', 'publish_maturin'})
        for name, body in publish_jobs.items():
            with self.subTest(route=name):
                needs = re.search(r'^    needs:\n((?:      - [^\n]+\n)+)', body, re.M)
                self.assertIsNotNone(needs)
                self.assertIn('      - prepublication\n', needs.group(1))
                condition = re.search(r'^    if: (.+)$', body, re.M).group(1)
                self.assertNotIn('always()', condition)
                self.assertNotIn('failure()', condition)
                self.assertNotIn('cancelled()', condition)
        gate = jobs['prepublication']
        self.assertNotIn('github.event_name', gate)
        self.assertNotIn('continue-on-error', gate)
        self.assertIn('ref: ${{ github.sha }}', gate)
        self.assertIn('TARGET_SHA: ${{ github.sha }}', gate)
        self.assertIn('TARGET_REF_NAME: ${{ needs.resolve.outputs.release_tag }}', gate)
        self.assertNotIn('id-token: write', gate)

    def test_required_command_failure_propagates_without_waiting(self) -> None:
        workflow = WORKFLOW.read_text()
        gate = workflow.split('  prepublication:\n', 1)[1].split('  build:\n', 1)[0]
        run = gate.split('        run: |\n', 1)[1]
        script = '\n'.join(line[10:] for line in run.splitlines() if line.startswith('          '))
        self.assertNotIn('sleep', script)
        self.assertNotIn('|| true', script)
        for command, expected in [('printf certified', 0), ('exit 17', 17)]:
            with self.subTest(command=command):
                result = subprocess.run(['bash', '-c', script], env={**os.environ, 'VERIFICATION_COMMAND': command}, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, expected)
                if expected == 0:
                    self.assertEqual(result.stdout, 'certified')

    def test_artifact_revision_refusal_precedes_configured_guard(self) -> None:
        workflow = (ROOT / 'shared/bijux-gh/workflows/release-artifacts.yml').read_text()
        section = workflow.split('      - name: Verify release revision and repository artifact policy', 1)[1].split('      - name: Upload publish artifacts', 1)[0]
        run = section.split('        run: |\n', 1)[1]
        script = '\n'.join(line[10:] for line in run.splitlines() if line.startswith('          '))
        fake_git = 'git() { if [[ "$*" == *refs/tags/* ]]; then printf "%s" "$TEST_TAG_SHA"; else printf "%s" "$TEST_HEAD_SHA"; fi; };\n'
        with tempfile.TemporaryDirectory() as temporary:
            staging = Path(temporary)
            (staging / 'dist').mkdir()
            (staging / 'release').mkdir()
            (staging / 'dist/package-0.2.0-py3-none-any.whl').write_bytes(b'wheel')
            (staging / 'release/package-dist-package-0.2.0-py3-none-any.whl').write_bytes(b'wheel')
            for tag, head, expected in [('a' * 40, 'a' * 40, 17), ('b' * 40, 'a' * 40, 1), ('a' * 40, 'b' * 40, 1)]:
                with self.subTest(tag=tag, head=head):
                    result = subprocess.run(['bash', '-c', fake_git + script], cwd=temporary, env={**os.environ, 'RELEASE_TAG': 'v0.2.0', 'DIST_DIR': str(staging / 'dist'), 'RELEASE_ASSET_DIR': str(staging / 'release'), 'PACKAGE_SLUG': 'package', 'GITHUB_SHA': 'a' * 40, 'TEST_TAG_SHA': tag, 'TEST_HEAD_SHA': head, 'BIJUX_RELEASE_ARTIFACT_VERIFICATION_COMMAND': 'exit 17'}, capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, expected, result.stderr)
        self.assertIn('ref: ${{ github.sha }}', workflow)
        self.assertIn('fetch-tags: true', workflow)

    def test_all_release_callers_preserve_tag_identity(self) -> None:
        for name in ('release-pypi', 'release-ghcr', 'release-github'):
            workflow = (ROOT / f'shared/bijux-gh/workflows/{name}.yml').read_text()
            calls = workflow.split('    uses: ./.github/workflows/release-artifacts.yml')[1:]
            self.assertTrue(calls)
            for call in calls:
                self.assertIn('      release_tag: ${{ needs.resolve.outputs.release_tag }}', re.split(r'\n  [a-z_]+:', call, maxsplit=1)[0])

    def test_staged_distribution_bytes_are_guarded_before_policy(self) -> None:
        workflow = (ROOT / 'shared/bijux-gh/workflows/release-artifacts.yml').read_text()
        section = workflow.split('      - name: Verify release revision and repository artifact policy', 1)[1].split('      - name: Upload publish artifacts', 1)[0]
        run = section.split('        run: |\n', 1)[1]
        script = '\n'.join(line[10:] for line in run.splitlines() if line.startswith('          '))
        fake_git = 'git() { printf "%s" "$GITHUB_SHA"; };\n'
        for scenario in ('matching', 'different-bytes', 'extra-release', 'missing-release', 'empty'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / 'dist').mkdir()
                (root / 'release').mkdir()
                filename = 'package-0.2.0-py3-none-any.whl'
                if scenario != 'empty':
                    (root / 'dist' / filename).write_bytes(b'original')
                    if scenario != 'missing-release':
                        (root / 'release' / ('package-dist-' + filename)).write_bytes(b'changed' if scenario == 'different-bytes' else b'original')
                if scenario == 'extra-release':
                    (root / 'release/package-dist-extra-0.2.0.tar.gz').write_bytes(b'extra')
                env = {**os.environ, 'RELEASE_TAG': 'v0.2.0', 'GITHUB_SHA': 'a' * 40, 'DIST_DIR': str(root / 'dist'), 'RELEASE_ASSET_DIR': str(root / 'release'), 'PACKAGE_SLUG': 'package', 'BIJUX_RELEASE_ARTIFACT_VERIFICATION_COMMAND': 'touch verifier-ran; exit 17'}
                result = subprocess.run(['bash', '-c', fake_git + script], cwd=root, env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual((root / 'verifier-ran').exists(), scenario == 'matching')
                if scenario == 'matching':
                    self.assertEqual(result.returncode, 17)
                else:
                    self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
