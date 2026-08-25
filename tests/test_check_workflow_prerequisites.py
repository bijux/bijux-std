from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "scripts"
    / "check_workflow_prerequisites.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bijux_std_check_workflow_prerequisites",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CheckWorkflowPrerequisitesTests(unittest.TestCase):
    def test_pending_prerequisite_returns_waiting_external_after_one_observation(self) -> None:
        event = {
            "pull_request": {"head": {"sha": "a" * 40}},
        }
        pending_run = {
            "id": 60,
            "name": "standards verification",
            "path": ".github/workflows/bijux-std.yml",
            "event": "pull_request",
            "created_at": "2026-08-10T12:00:00Z",
            "run_number": 20,
            "status": "in_progress",
            "conclusion": None,
        }

        with (
            mock.patch.dict(
                MODULE.os.environ,
                {"GITHUB_EVENT_NAME": "pull_request"},
                clear=True,
            ),
            mock.patch.object(MODULE, "_event_payload", return_value=event),
            mock.patch.object(MODULE, "_list_workflow_runs", return_value=[pending_run]) as list_runs,
            mock.patch.object(MODULE, "_run_has_materialized_jobs", return_value=True),
        ):
            with self.assertRaisesRegex(SystemExit, "75"):
                MODULE.main()

        list_runs.assert_called_once_with("a" * 40)

    def test_latest_run_ignores_wrong_event_and_zero_job_run(self) -> None:
        workflow = MODULE.RequiredWorkflow(
            ".github/workflows/bijux-std.yml",
            allowed_events=("pull_request",),
        )
        runs = [
            {
                "id": 30,
                "name": "standards verification",
                "path": ".github/workflows/bijux-std.yml",
                "event": "push",
                "created_at": "2026-06-28T12:28:25Z",
                "run_number": 459,
            },
            {
                "id": 31,
                "name": "standards verification",
                "path": ".github/workflows/bijux-std.yml",
                "event": "pull_request",
                "created_at": "2026-06-28T12:28:26Z",
                "run_number": 460,
            },
            {
                "id": 32,
                "name": "standards verification",
                "path": ".github/workflows/bijux-std.yml",
                "event": "pull_request",
                "created_at": "2026-06-28T12:28:27Z",
                "run_number": 461,
            },
        ]
        jobs_cache: dict[int, bool] = {}

        def fake_has_jobs(run: dict, cache: dict[int, bool]) -> bool:
            self.assertIs(cache, jobs_cache)
            return run["id"] != 31

        with mock.patch.object(MODULE, "_run_has_materialized_jobs", side_effect=fake_has_jobs):
            latest = MODULE._latest_run_for_identifier(runs, workflow, jobs_cache)

        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest["id"], 32)

    def test_workflow_path_survives_display_name_change(self) -> None:
        workflow = MODULE.RequiredWorkflow(
            ".github/workflows/pr-approval-policy.yml",
            allowed_events=("pull_request_target",),
        )
        runs = [
            {
                "id": 40,
                "name": "policy / pr approval",
                "path": ".github/workflows/pr-approval-policy.yml",
                "event": "pull_request_target",
                "created_at": "2026-07-19T19:14:35Z",
                "run_number": 12,
            }
        ]

        with mock.patch.object(
            MODULE,
            "_run_has_materialized_jobs",
            return_value=True,
        ):
            latest = MODULE._latest_run_for_identifier(runs, workflow, {})

        self.assertEqual(latest, runs[0])

    def test_workflow_name_identifier_remains_supported(self) -> None:
        workflow = MODULE.RequiredWorkflow("repository policy")
        runs = [
            {
                "id": 50,
                "name": "repository policy",
                "path": ".github/workflows/github-policy.yml",
                "event": "pull_request",
                "created_at": "2026-07-19T19:14:19Z",
                "run_number": 18,
            }
        ]

        with mock.patch.object(
            MODULE,
            "_run_has_materialized_jobs",
            return_value=True,
        ):
            latest = MODULE._latest_run_for_identifier(runs, workflow, {})

        self.assertEqual(latest, runs[0])

    def test_pull_request_prerequisites_are_event_scoped(self) -> None:
        workflows = MODULE._required_workflows("pull_request")

        self.assertEqual(
            workflows,
            [
                MODULE.RequiredWorkflow(
                    ".github/workflows/bijux-std.yml",
                    allowed_events=("pull_request",),
                ),
                MODULE.RequiredWorkflow(
                    ".github/workflows/pr-approval-policy.yml",
                    allowed_events=("pull_request_target", "pull_request_review"),
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
