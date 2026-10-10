from __future__ import annotations

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


class PublicationAdmissionTests(unittest.TestCase):
    def environment(self):
        return {"PUBLICATION_REPOSITORY": "bijux/bijux-canon", "PUBLICATION_EVENT": "workflow_dispatch",
                "PUBLICATION_REF": "refs/heads/main", "PUBLICATION_ACTOR": "bijux-publication[bot]",
                "PUBLICATION_ACTOR_ID": "123", "PUBLICATION_CONTROLLER_ACTOR_ID": "123",
                "PUBLICATION_TRIGGERING_ACTOR": "bijux-publication[bot]",
                "PUBLICATION_COMMIT": COMMIT, "PUBLICATION_RUN_SHA": COMMIT,
                "PUBLICATION_WORKFLOW": "release-pypi", "PUBLICATION_TAG": "v1.2.3"}

    def runs(self):
        return [{"id": index + 1, "name": context, "head_sha": COMMIT, "app": {"id": 15368},
                 "status": "completed", "conclusion": "success"}
                for index, context in enumerate(["policy / github", "std / standard", "std / report"])]

    def api(self, path):
        if path.startswith("users/"):
            return {"type": "Bot", "id": 123}
        if "/commits/" in path:
            return {"sha": COMMIT}
        return [{"type": "required_status_checks", "parameters": {"required_status_checks": [
            {"context": context, "integration_id": 15368}
            for context in ["policy / github", "policy / pr approval", "std / standard", "std / report"]]}}]

    def test_authorized_manual_request_is_bound_to_commit_and_version_tag(self):
        with patch.object(MODULE, "api", side_effect=self.api), patch.object(MODULE, "check_runs", return_value=self.runs()):
            receipt = MODULE.admit(self.environment())
        self.assertEqual(receipt["commit"], COMMIT)
        self.assertEqual(receipt["tag"], "v1.2.3")
        self.assertEqual(receipt["controller_actor_id"], "123")

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
                MODULE.require_green_checks(contexts, COMMIT, runs)
        for changes in [{"head_sha": "b" * 40}, {"app": {"id": 1}}, {"status": "in_progress"}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                MODULE.require_green_checks(contexts, COMMIT, [{**self.runs()[-1], **changes}])
        with self.assertRaises(ValueError):
            MODULE.require_green_checks(contexts, COMMIT, [])


if __name__ == "__main__":
    unittest.main()
