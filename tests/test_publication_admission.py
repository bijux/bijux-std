from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("publication_admission", ROOT / "shared/bijux-gh/scripts/publication_admission.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
COMMIT = "a" * 40
HEAD = "b" * 40
BASE = "c" * 40


class PublicationAdmissionTests(unittest.TestCase):
    def environment(self):
        return {"PUBLICATION_REPOSITORY": "bijux/bijux-canon", "PUBLICATION_EVENT": "workflow_dispatch",
                "PUBLICATION_REF": "refs/heads/main", "PUBLICATION_ACTOR": "bijux-publication[bot]",
                "PUBLICATION_ACTOR_ID": "123", "PUBLICATION_CONTROLLER_ACTOR_ID": "123",
                "PUBLICATION_TRIGGERING_ACTOR": "bijux-publication[bot]",
                "PUBLICATION_COMMIT": COMMIT, "PUBLICATION_RUN_SHA": COMMIT,
                "PUBLICATION_WORKFLOW": "release-pypi", "PUBLICATION_TAG": "v1.2.3"}

    def runs(self):
        return [{"id": index + 1, "name": context, "head_sha": HEAD, "app": {"id": 15368},
                 "status": "completed", "conclusion": "success"}
                for index, context in enumerate(["policy / github", "policy / pr approval", "std / standard", "std / report"])]

    def pull(self):
        return {"number": 42, "state": "closed", "merged": True, "merged_at": "2026-10-11T00:00:00Z",
                "merge_commit_sha": COMMIT, "user": {"login": "bijux", "type": "User"},
                "base": {"ref": "main", "sha": BASE, "repo": {"full_name": "bijux/bijux-canon"}},
                "head": {"sha": HEAD, "repo": {"full_name": "bijux/bijux-canon"}}}

    def api(self, path):
        if path.startswith("users/"):
            return {"type": "Bot", "id": 123}
        if "/pulls/" in path:
            return self.pull()
        if "/commits/" in path:
            return {"sha": COMMIT, "parents": [{"sha": BASE}, {"sha": HEAD}]}
        return [{"type": "required_status_checks", "parameters": {"required_status_checks": [
            {"context": context, "integration_id": 15368}
            for context in ["policy / github", "policy / pr approval", "std / standard", "std / report"]]}}]

    def test_authorized_manual_request_is_bound_to_commit_and_version_tag(self):
        with patch.object(MODULE, "api", side_effect=self.api), patch.object(MODULE, "check_runs", return_value=self.runs()), patch.object(MODULE, "associated_pulls", return_value=[self.pull()]):
            receipt = MODULE.admit(self.environment())
        self.assertEqual(receipt["commit"], COMMIT)
        self.assertEqual(receipt["tag"], "v1.2.3")
        self.assertEqual(receipt["controller_actor_id"], "123")
        self.assertEqual(receipt["accepted_pull_request"], 42)
        self.assertEqual(receipt["verification_commit"], HEAD)
        self.assertIn("policy / pr approval", receipt["required_commit_checks"])

    def test_routed_foundations_cannot_publish_an_independent_site(self):
        for repository in ("bijux/bijux-std", "bijux/bijux-iac"):
            environment = {**self.environment(), "PUBLICATION_REPOSITORY": repository,
                           "PUBLICATION_WORKFLOW": "deploy-docs", "PUBLICATION_TAG": ""}
            with self.subTest(repository=repository), patch.object(MODULE, "api") as reader:
                with self.assertRaisesRegex(ValueError, "controller destination"):
                    MODULE.admit(environment)
                reader.assert_not_called()

    def test_unauthorized_and_automatic_requests_fail_before_api_calls(self):
        for changes in [{"PUBLICATION_EVENT": "push"}, {"PUBLICATION_ACTOR_ID": "456"},
                        {"PUBLICATION_TRIGGERING_ACTOR": "human-rerunner"},
                        {"PUBLICATION_REF": "refs/heads/feature"}, {"PUBLICATION_CONTROLLER_ACTOR_ID": ""},
                        {"PUBLICATION_COMMIT": "main"}, {"PUBLICATION_WORKFLOW": "renamed-publisher"}]:
            with self.subTest(changes=changes), patch.object(MODULE, "api") as api:
                with self.assertRaises(ValueError):
                    MODULE.admit({**self.environment(), **changes})
                api.assert_not_called()

    def test_unaccepted_commit_and_moved_release_tag_are_rejected(self):
        for suffix in ["main", "v1.2.3"]:
            def api(path):
                return {"sha": "b" * 40} if path.endswith("/commits/" + suffix) else self.api(path)
            with self.subTest(suffix=suffix), patch.object(MODULE, "api", side_effect=api):
                with self.assertRaises(ValueError):
                    MODULE.admit(self.environment())

    def test_each_unhealthy_latest_result_overrides_an_older_green_result(self):
        contexts = {"std / report"}
        for conclusion in ["failure", "cancelled", "skipped", None]:
            runs = self.runs()
            runs.append({**runs[-1], "id": 100, "conclusion": conclusion})
            with self.subTest(conclusion=conclusion), self.assertRaises(ValueError):
                MODULE.require_green_checks(contexts, HEAD, runs)
        for changes in [{"head_sha": "d" * 40}, {"app": {"id": 1}}, {"status": "in_progress"}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                MODULE.require_green_checks(contexts, HEAD, [{**self.runs()[-1], **changes}])
        with self.assertRaises(ValueError):
            MODULE.require_green_checks(contexts, HEAD, [])

    def test_normal_merge_requires_one_exact_human_PR_and_fresh_identity(self):
        accepted = self.api("repos/bijux/bijux-canon/commits/main")
        wrong_rows = []
        for mutation in [
            {"merge_commit_sha": "d" * 40}, {"state": "open"}, {"merged_at": None},
            {"number": True}, {"user": {"login": "dependabot[bot]", "type": "Bot"}},
            {"user": {"login": "dependabot[bot]", "type": "User"}},
            {"head": {"sha": "d" * 40, "repo": {"full_name": "bijux/bijux-canon"}}},
            {"head": {"sha": HEAD, "repo": {"full_name": "fork/bijux-canon"}}},
            {"base": {"ref": "other", "sha": BASE, "repo": {"full_name": "bijux/bijux-canon"}}},
            {"base": {"ref": "main", "sha": "d" * 40, "repo": {"full_name": "bijux/bijux-canon"}}},
        ]:
            wrong_rows.append({**self.pull(), **mutation})
        for rows in [[], [self.pull(), self.pull()], *[[row] for row in wrong_rows]]:
            with self.subTest(rows=rows), patch.object(MODULE, "associated_pulls", return_value=rows), patch.object(MODULE, "api", side_effect=self.api):
                with self.assertRaises(ValueError):
                    MODULE.accepted_pull_head("bijux/bijux-canon", COMMIT, accepted)
        for parents in [[], [{"sha": HEAD}], [{"sha": BASE}] * 2, [{"sha": "main"}, {"sha": HEAD}], accepted["parents"] * 2]:
            with self.subTest(parents=parents), patch.object(MODULE, "associated_pulls") as pulls:
                with self.assertRaises(ValueError):
                    MODULE.accepted_pull_head("bijux/bijux-canon", COMMIT, {"parents": parents})
                pulls.assert_not_called()
        for mutation in [{"merged": False}, {"number": 43}, {"merge_commit_sha": "d" * 40}]:
            with self.subTest(mutation=mutation), patch.object(MODULE, "associated_pulls", return_value=[self.pull()]), patch.object(MODULE, "api", return_value={**self.pull(), **mutation}):
                with self.assertRaises(ValueError):
                    MODULE.accepted_pull_head("bijux/bijux-canon", COMMIT, accepted)

    def test_main_checks_and_bot_notice_cannot_substitute_for_PR_verification(self):
        for runs in [[{**run, "head_sha": COMMIT} for run in self.runs()],
                     [{**run, "name": "unverified dependency / " + run["name"], "conclusion": "skipped"} for run in self.runs()],
                     [run for run in self.runs() if run["name"] != "policy / pr approval"]]:
            with self.subTest(runs=runs), patch.object(MODULE, "api", side_effect=self.api), patch.object(MODULE, "associated_pulls", return_value=[self.pull()]), patch.object(MODULE, "check_runs", return_value=runs):
                with self.assertRaises(ValueError):
                    MODULE.admit(self.environment())

    def test_main_movement_after_verification_is_rejected(self):
        observations = 0
        def api(path):
            nonlocal observations
            if path.endswith("/commits/main"):
                observations += 1
                if observations == 2:
                    return {"sha": "d" * 40}
            return self.api(path)
        with patch.object(MODULE, "api", side_effect=api), patch.object(MODULE, "associated_pulls", return_value=[self.pull()]), patch.object(MODULE, "check_runs", return_value=self.runs()):
            with self.assertRaisesRegex(ValueError, "moved during"):
                MODULE.admit(self.environment())

    def test_existing_events_policy_retains_main_check_admission(self):
        manifest = json.loads((ROOT / ".github/standards/repo-config.manifest.json").read_text())
        entry = next(repo for repo in manifest["repositories"] if repo["name"] == "bijux-canon")
        entry["workflow_execution_policy"]["main_verification"] = "existing-events"
        runs = [{**run, "head_sha": COMMIT} for run in self.runs()]
        with patch.object(MODULE.Path, "read_text", return_value=json.dumps(manifest)), patch.object(MODULE, "api", side_effect=self.api), patch.object(MODULE, "check_runs", return_value=runs), patch.object(MODULE, "associated_pulls") as pulls:
            receipt = MODULE.admit(self.environment())
        pulls.assert_not_called()
        self.assertIsNone(receipt["accepted_pull_request"])
        self.assertEqual(receipt["verification_commit"], COMMIT)

    def test_associated_PR_pagination_requires_structural_arrays(self):
        with patch.object(MODULE.subprocess, "check_output", return_value=json.dumps([[self.pull()], []])) as command:
            self.assertEqual(MODULE.associated_pulls("bijux/bijux-canon", COMMIT), [self.pull()])
        self.assertIn("--paginate", command.call_args.args[0])
        for pages in [{}, [None], [{"pulls": [self.pull()]}]]:
            with self.subTest(pages=pages), patch.object(MODULE.subprocess, "check_output", return_value=json.dumps(pages)):
                with self.assertRaises(ValueError):
                    MODULE.associated_pulls("bijux/bijux-canon", COMMIT)

    def test_public_source_admission_preserves_exact_foundation_checks_without_token_reads(self):
        env = {**self.environment(), "PUBLICATION_REPOSITORY": "bijux/bijux-std",
               "PUBLICATION_WORKFLOW": "deploy-docs", "PUBLICATION_TAG": ""}
        pull = copy.deepcopy(self.pull())
        for branch in ('base', 'head'):
            pull[branch]['repo']['full_name'] = 'bijux/bijux-std'
        def reader(path):
            if path == 'repos/bijux/bijux-std':
                return {'visibility': 'public'}
            return pull if '/pulls/' in path else self.api(path)
        for runs in (self.runs(), []):
            with self.subTest(runs=runs), patch.object(MODULE, 'api') as credential_read, \
                    patch.object(MODULE, 'public_api', side_effect=reader), \
                    patch.object(MODULE, 'public_associated_pulls', return_value=[pull]), \
                    patch.object(MODULE, 'public_check_runs', return_value=runs):
                if runs:
                    self.assertEqual(MODULE.admit(env, public_source=True)['verification_commit'], HEAD)
                else:
                    with self.assertRaisesRegex(ValueError, 'unhealthy'):
                        MODULE.admit(env, public_source=True)
                credential_read.assert_not_called()

    def test_public_source_mode_cannot_admit_other_consumers_or_releases(self):
        for change in ({}, {'PUBLICATION_REPOSITORY': 'bijux/bijux-std'},
                       {'PUBLICATION_REPOSITORY': 'bijux/bijux.github.io', 'PUBLICATION_WORKFLOW': 'deploy-docs'}):
            with self.subTest(change=change), patch.object(MODULE, 'public_api') as read:
                with self.assertRaisesRegex(ValueError, 'restricted'):
                    MODULE.admit({**self.environment(), **change}, public_source=True)
                read.assert_not_called()

    def test_public_pagination_collects_all_pages_without_authorization(self):
        from io import BytesIO
        path = f'repos/bijux/bijux-std/commits/{HEAD}/check-runs?per_page=100'
        initial = 'https://api.github.com/' + path
        class Response(BytesIO):
            def __init__(self, url, data, link=''):
                super().__init__(json.dumps(data).encode())
                self.url, self.headers = url, {'Link': link}
            def geturl(self):
                return self.url
        follow = initial + '&page=2'
        with patch.object(MODULE, 'urlopen', side_effect=[
                Response(initial, {'check_runs': [self.runs()[0]]}, f'<{follow}>; rel="next"'),
                Response(follow, {'check_runs': self.runs()[1:]})]) as read:
            self.assertEqual(MODULE.public_check_runs('bijux/bijux-std', HEAD), self.runs())
        self.assertEqual(read.call_count, 2)
        for call in read.call_args_list:
            self.assertNotIn('Authorization', dict(call.args[0].header_items()))
            self.assertEqual(call.args[0].get_header('X-github-api-version'), '2022-11-28')

    def test_numeric_pagination_requires_the_previously_bound_repository_identity(self):
        from io import BytesIO
        initial = f'https://api.github.com/repos/bijux/bijux-std/commits/{HEAD}/check-runs?per_page=100'
        class Response(BytesIO):
            def __init__(self, url, data, link=''):
                super().__init__(json.dumps(data).encode())
                self.url, self.headers = url, {'Link': link}
            def geturl(self):
                return self.url
        for identifier in (42, 43):
            follow = f'https://api.github.com/repositories/{identifier}/commits/{HEAD}/check-runs?per_page=100&page=2'
            with self.subTest(identifier=identifier), patch.dict(MODULE.PUBLIC_REPOSITORY_IDS, {}, clear=True), \
                    patch.object(MODULE, 'urlopen', side_effect=[
                        Response('https://api.github.com/repos/bijux/bijux-std', {'id': 42, 'full_name': 'bijux/bijux-std', 'visibility': 'public'}),
                        Response(initial, {'check_runs': []}, f'<{follow}>; rel="next"'),
                        Response(follow, {'check_runs': self.runs()})]) as read:
                MODULE.public_api('repos/bijux/bijux-std')
                if identifier == 42:
                    self.assertEqual(MODULE.public_check_runs('bijux/bijux-std', HEAD), self.runs())
                else:
                    with self.assertRaisesRegex(ValueError, 'exact GitHub endpoint'):
                        MODULE.public_check_runs('bijux/bijux-std', HEAD)
                    self.assertEqual(read.call_count, 2)

    def test_public_reads_refuse_foreign_endpoints_before_network(self):
        for path in ('repos/bijux/bijux-core/commits/main', 'https://evil.invalid/', '../secrets',
                     'users/another[bot]'):
            with self.subTest(path=path), patch.object(MODULE, 'urlopen') as read:
                with self.assertRaises(ValueError):
                    MODULE.public_api(path)
                read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
