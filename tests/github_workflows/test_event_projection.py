from __future__ import annotations
import copy
import importlib.util
import json
import tempfile
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock
from .policy_fixtures import ROOT, MODULE, INVENTORY, POLICY, manifest


class AutomaticEventProjectionTests(unittest.TestCase):
    def test_automatic_projection_preserves_all_nontrigger_source_and_required_events(self):
        source = {"name": "standard", "on": ["push", "pull_request", "merge_group", "workflow_dispatch"], "jobs": {"checks": {"name": "std / check", "if": "${{ always() }}"}}, "permissions": {"contents": "read"}}
        before = copy.deepcopy(source)
        projected = MODULE.project_automatic_events("bijux-std", source, {"schema": 1, "automatic_runs": "repository-policy-only"})
        self.assertEqual(set(projected["on"]), {"pull_request", "merge_group", "workflow_dispatch"})
        self.assertEqual({k: v for k, v in projected.items() if k != "on"}, {k: v for k, v in source.items() if k != "on"})
        self.assertEqual(source, before)
        self.assertEqual(MODULE.project_automatic_events("bijux-std", source, None), source)
        self.assertEqual(MODULE.project_automatic_events("bijux-std", source, {"schema": 1, "automatic_runs": "canonical"}), source)

    def test_repository_policy_restricts_main_and_preserves_paths_and_PR_configuration(self):
        source = {"on": {"push": {"branches": ["main", "feature"], "tags": ["v*"], "paths": [".github/**"]}, "pull_request": {"branches": ["main"]}}, "jobs": {}}
        policy = {"schema": 1, "automatic_runs": "repository-policy-only"}
        projected = MODULE.project_automatic_events("github-policy", source, policy)
        self.assertEqual(projected["on"]["push"], {"branches": ["main"], "paths": [".github/**"]})
        self.assertEqual(projected["on"]["pull_request"], source["on"]["pull_request"])
        self.assertEqual(MODULE.project_automatic_events("github-policy", projected, policy), projected)

    def test_automatic_projection_admits_null_map_list_and_string_manual_events(self):
        for events in ["workflow_dispatch", ["workflow_dispatch"], {"workflow_dispatch": None}, {"workflow_dispatch": {}}]:
            with self.subTest(events=events):
                projected = MODULE.project_automatic_events("release-github", {"on": events, "jobs": {}}, {"schema": 1, "automatic_runs": "repository-policy-only"})
                self.assertEqual(set(projected["on"]), {"workflow_dispatch"})

    def test_automatic_projection_refuses_unsupported_ambiguous_and_missing_entrypoints(self):
        for identity, events in [
            ("ci", ["push"]), ("ci", ["pull_request", "pull_request"]),
            ("ci", {"schedule": [{"cron": "0 0 * * *"}]}),
            ("ci", {"pull_request": "branches: main"}),
            ("ci", {"push": {"branches": "main"}, "pull_request": None}),
            ("ci", {"push": {"branches": ["main"], "branches-ignore": ["other"]}, "pull_request": None}),
            ("github-policy", {"push": None}),
            ("github-policy", {"push": {"branches": ["feature"]}}),
            ("bijux-std", {"pull_request": None, "workflow_dispatch": None}),
        ]:
            with self.subTest(events=events), self.assertRaises(ValueError):
                MODULE.project_automatic_events(identity, {"on": events, "jobs": {}}, {"schema": 1, "automatic_runs": "repository-policy-only"})


if __name__ == "__main__":
    unittest.main()
