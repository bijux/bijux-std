from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "wait_for_ci.py"
SPEC = importlib.util.spec_from_file_location("bijux_std_wait_for_ci", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class WaitForCiTests(unittest.TestCase):
    def test_pending_run_returns_waiting_external_after_one_observation(self) -> None:
        pending = {
            "id": 12,
            "name": "CI",
            "event": "push",
            "head_branch": "main",
            "created_at": "2026-08-10T12:00:00Z",
            "updated_at": "2026-08-10T12:01:00Z",
            "status": "in_progress",
            "conclusion": None,
        }
        environment = {
            "GITHUB_TOKEN": "token",
            "GITHUB_REPOSITORY": "bijux/example",
            "TARGET_SHA": "a" * 40,
            "TARGET_REF_NAME": "main",
        }
        with (
            mock.patch.dict(MODULE.os.environ, environment, clear=True),
            mock.patch.object(
                MODULE,
                "github_get_json",
                return_value={"workflow_runs": [pending]},
            ) as get_json,
        ):
            self.assertEqual(MODULE.main(), MODULE.WAITING_EXTERNAL_EXIT_CODE)

        get_json.assert_called_once()

    def test_successful_run_passes_after_one_observation(self) -> None:
        completed = {
            "id": 13,
            "name": "CI",
            "event": "push",
            "head_branch": "main",
            "created_at": "2026-08-10T12:00:00Z",
            "updated_at": "2026-08-10T12:02:00Z",
            "status": "completed",
            "conclusion": "success",
        }
        environment = {
            "GITHUB_TOKEN": "token",
            "GITHUB_REPOSITORY": "bijux/example",
            "TARGET_SHA": "b" * 40,
            "TARGET_REF_NAME": "main",
        }
        with (
            mock.patch.dict(MODULE.os.environ, environment, clear=True),
            mock.patch.object(
                MODULE,
                "github_get_json",
                return_value={"workflow_runs": [completed]},
            ),
        ):
            self.assertEqual(MODULE.main(), 0)


if __name__ == "__main__":
    unittest.main()
