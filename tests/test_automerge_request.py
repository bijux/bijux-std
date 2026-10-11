"""The canonical legacy entrypoint cannot enable merge or execute bot proposals."""
from __future__ import annotations
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from github_workflows.policy_fixtures import MODULE

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/automerge-pr.yml'


class OwnerConsolidationPolicyTests(unittest.TestCase):
    def test_no_automatic_event_or_repository_write_permission(self):
        document = MODULE.parse_workflow(WORKFLOW.read_bytes(), 'automerge-pr')
        self.assertEqual(set(document['on']), {'workflow_dispatch'})
        self.assertEqual(document['permissions'], {'contents': 'read'})
        self.assertEqual(set(document['jobs']), {'owner-consolidation'})
        job = document['jobs']['owner-consolidation']
        self.assertEqual(job['timeout-minutes'], 1)
        self.assertTrue(all('uses' not in step for step in job['steps']))
        source = WORKFLOW.read_text()
        for forbidden in ['enablePullRequestAutoMerge', 'github.graphql', 'pull-requests: write', 'pull_request:', 'pull_request_review:']:
            self.assertNotIn(forbidden, source)

    def test_actual_manual_script_emits_ownership_notice_only(self):
        document = MODULE.parse_workflow(WORKFLOW.read_bytes(), 'automerge-pr')
        script = document['jobs']['owner-consolidation']['steps'][0]['run']
        with tempfile.TemporaryDirectory() as folder:
            summary = Path(folder) / 'summary.md'
            subprocess.run(['bash', '-c', script], env=dict(os.environ, GITHUB_STEP_SUMMARY=str(summary)), check=True)
            self.assertEqual(set(Path(folder).iterdir()), {summary})
            self.assertIn('verified human-authored consolidation PR', summary.read_text())
            self.assertIn('never enables or performs automatic merge', summary.read_text())


if __name__ == '__main__':
    unittest.main()
