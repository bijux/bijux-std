from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest

from github_workflows.policy_fixtures import MODULE


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/automerge-pr.yml"
HARNESS = r'''
import fs from 'node:fs';
const {script, scenario} = JSON.parse(fs.readFileSync(0, 'utf8'));
const sha = 'a'.repeat(40);
const pr = {
  number: 43, node_id: 'PR_reviewed', state: 'open', draft: false,
  labels: [{name: 'automerge'}], mergeable_state: 'clean', auto_merge: null,
  head: {repo: {full_name: 'bijux/bijux-atlas'}, sha}, base: {ref: 'main'},
  user: {login: 'dependabot[bot]'}, author_association: 'NONE', ...scenario.pr,
};
const listFiles = () => {}, listReviews = () => {};
const requests = [];
const github = {
  rest: {
    pulls: {get: async () => ({data: pr}), listFiles, listReviews},
    repos: {getContent: async () => ({data: {type: 'file', content: Buffer.from('* @bijux\n').toString('base64')}})},
  },
  paginate: async (method) => method === listFiles
    ? (scenario.files || [{filename: 'Cargo.lock'}])
    : [{user: {login: 'bijux'}, state: 'APPROVED', author_association: 'OWNER',
        commit_id: scenario.staleApproval ? 'b'.repeat(40) : sha,
        submitted_at: '2026-10-01T00:00:00Z'}],
  graphql: async (query, variables) => {requests.push({query, variables}); return {};},
};
const core = {info: () => {}, warning: () => {}};
const context = {repo: {owner: 'bijux', repo: 'bijux-atlas'}, payload: {pull_request: {number: 43}}};
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
await new AsyncFunction('github', 'context', 'core', 'Buffer', script)(github, context, core, Buffer);
process.stdout.write(JSON.stringify(requests));
'''


class AutomergeRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        document = MODULE.parse_workflow(WORKFLOW.read_bytes(), "automerge-pr")
        cls.script = document["jobs"]["enable"]["steps"][0]["with"]["script"]

    def execute(self, scenario: dict) -> list[dict]:
        result = subprocess.run(
            ["node", "--input-type=module", "-e", HARNESS],
            input=json.dumps({"script": self.script, "scenario": scenario}),
            text=True, capture_output=True, check=True,
        )
        return json.loads(result.stdout)

    def test_reviewed_safe_bot_requests_history_preserving_merge(self) -> None:
        requests = self.execute({})
        self.assertEqual(len(requests), 1)
        self.assertIn("mergeMethod: MERGE", requests[0]["query"])
        self.assertNotIn("SQUASH", requests[0]["query"])
        self.assertEqual(requests[0]["variables"], {"pullRequestId": "PR_reviewed"})

    def test_draft_never_requests_automatic_merge(self) -> None:
        self.assertEqual(self.execute({"pr": {"draft": True}}), [])

    def test_governance_changes_never_request_automatic_merge(self) -> None:
        self.assertEqual(self.execute({"files": [{"filename": ".github/workflows/ci.yml"}]}), [])

    def test_approval_for_previous_commit_never_admits_merge(self) -> None:
        self.assertEqual(self.execute({"staleApproval": True}), [])


if __name__ == "__main__":
    unittest.main()
