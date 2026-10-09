from __future__ import annotations

import copy
import os
import subprocess
import unittest
from .policy_fixtures import MODULE, ROOT


POLICY = {"schema": 1, "publication_entrypoints": {
    "deploy-docs": {"mode": "manual-only", "refs": "main-only"},
}}
GUARD_NAME = "Validate publication event and ref"


class DocsPublicationRefsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MODULE.parse_workflow(
            (ROOT / "shared/bijux-gh/workflows/deploy-docs.yml").read_bytes(), "deploy-docs.yml"
        )

    def project(self, source=None, policy=POLICY):
        return MODULE.project_publication_entrypoints("deploy-docs", self.source if source is None else source, policy)

    def test_literal_main_dispatch_predicates_and_first_named_guard(self):
        candidate = self.project()
        for identity in ["build", "deploy"]:
            predicate = candidate["jobs"][identity]["if"]
            self.assertIn("github.event_name == 'workflow_dispatch'", predicate)
            self.assertIn("github.ref == 'refs/heads/main'", predicate)
            self.assertNotIn("default_branch", predicate)
            self.assertNotIn("refs/tags", predicate)
        self.assertIn("needs.build.outputs.site_available == 'true'", candidate["jobs"]["deploy"]["if"])
        self.assertEqual(candidate["jobs"]["build"]["steps"][0]["name"], GUARD_NAME)

    def test_actual_shell_guard_accepts_only_main_dispatch_independent_of_default_branch(self):
        guard = self.project()["jobs"]["build"]["steps"][0]
        for event, ref in [("workflow_dispatch", "refs/heads/main"), ("workflow_dispatch", "refs/heads/master"),
                           ("workflow_dispatch", "refs/tags/v1.2.3"), ("workflow_call", "refs/heads/main"),
                           ("push", "refs/heads/main"), ("release", "refs/heads/main"),
                           ("pull_request", "refs/heads/main"), ("pull_request_target", "refs/heads/main"),
                           ("", ""), ("workflow_dispatch", "refs/heads/main\n")]:
            with self.subTest(event=event, ref=ref):
                environment = dict(os.environ, PUBLICATION_EVENT=event, PUBLICATION_REF=ref,
                                   PUBLICATION_DEFAULT_BRANCH="master")
                result = subprocess.run(["bash", "--noprofile", "--norc", "-c", guard["run"]],
                                        env=environment, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, event == "workflow_dispatch" and ref == "refs/heads/main")

    def test_every_non_guard_body_and_dispatch_type_remains_owned(self):
        before = copy.deepcopy(self.source)
        candidate = self.project()
        self.assertEqual(self.source, before)
        self.assertEqual(candidate["on"], {"workflow_dispatch": before["on"]["workflow_dispatch"]})
        self.assertEqual({k: v for k, v in candidate.items() if k not in {"on", "jobs"}},
                         {k: v for k, v in before.items() if k not in {"on", "jobs"}})
        for identity in ["build", "deploy"]:
            exclusions = {"if", "steps"} if identity == "build" else {"if"}
            self.assertEqual({k: v for k, v in candidate["jobs"][identity].items() if k not in exclusions},
                             {k: v for k, v in before["jobs"][identity].items() if k not in exclusions})
        self.assertEqual(candidate["jobs"]["build"]["steps"][1:],
                         [step for step in before["jobs"]["build"]["steps"] if step["name"] != GUARD_NAME])

    def test_canonical_refs_or_absent_selection_preserve_existing_guard(self):
        for policy in [None, {"schema": 1}, {"schema": 1, "publication_entrypoints": {
            "deploy-docs": {"mode": "canonical", "refs": "canonical"}}}]:
            self.assertEqual(self.project(policy=policy), self.source)
        manual = {"schema": 1, "publication_entrypoints": {"deploy-docs": {"mode": "manual-only", "refs": "canonical"}}}
        self.assertEqual(self.project(policy=manual)["jobs"], self.source["jobs"])

    def test_projection_is_idempotent_only_with_complete_owned_guard(self):
        candidate = self.project()
        self.assertEqual(self.project(candidate), candidate)

    def test_projected_predicates_cannot_qualify_an_incomplete_shell_guard(self):
        for variant in ["missing", "later", "skippable", "env", "script"]:
            candidate = self.project()
            steps = candidate["jobs"]["build"]["steps"]
            guard = steps[0]
            if variant == "missing":
                steps.remove(guard)
            elif variant == "later":
                steps.reverse()
            elif variant == "skippable":
                guard["if"] = False
            elif variant == "env":
                guard["env"]["PUBLICATION_REF"] = "refs/heads/main"
            else:
                guard["run"] = "true\n"
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.project(candidate)

    def test_missing_boolean_or_unrecognized_job_conditions_refuse(self):
        for identity in ["build", "deploy"]:
            for predicate in [None, True, False, "true", "${{ always() }}"]:
                source = copy.deepcopy(self.source)
                if predicate is None:
                    del source["jobs"][identity]["if"]
                else:
                    source["jobs"][identity]["if"] = predicate
                with self.subTest(identity=identity, predicate=predicate), self.assertRaises(ValueError):
                    self.project(source)

    def test_missing_ambiguous_or_changed_guard_refuses(self):
        for variant in ["missing", "duplicate", "shell", "env", "run", "skippable"]:
            source = copy.deepcopy(self.source)
            steps = source["jobs"]["build"]["steps"]
            guard = next(step for step in steps if step["name"] == GUARD_NAME)
            if variant == "missing":
                steps.remove(guard)
            elif variant == "duplicate":
                steps.append(copy.deepcopy(guard))
            elif variant == "skippable":
                guard["if"] = False
            else:
                guard[variant] = False if variant != "run" else "echo unreviewed guard\n"
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.project(source)

    def test_new_jobs_or_dependency_changes_need_source_review(self):
        for variant in ["extra-job", "needs", "jobs"]:
            source = copy.deepcopy(self.source)
            if variant == "extra-job":
                source["jobs"]["unowned"] = {"runs-on": "ubuntu-latest", "steps": []}
            elif variant == "needs":
                source["jobs"]["deploy"]["needs"] = "another-job"
            else:
                source["jobs"] = []
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.project(source)


if __name__ == "__main__":
    unittest.main()
