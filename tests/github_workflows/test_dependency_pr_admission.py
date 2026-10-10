from __future__ import annotations

import copy
import unittest
from .policy_fixtures import MODULE


POLICY = {"schema": 1, "dependency_pull_requests": "skip-managed-jobs"}


def observed_condition(condition, event, author, actor="human", successful=True):
    # This bounded expression fixture observes only strings/booleans used by these controls.
    expression = condition.removeprefix("${{").removesuffix("}}").strip()
    for variable, value in {"github.event_name": event, "github.event.pull_request.user.login": author,
                            "github.actor": actor, "needs.build.result": "success" if successful else "failure"}.items():
        expression = expression.replace(variable, repr(value))
    expression = expression.replace("always()", "True").replace("success()", repr(successful))
    expression = expression.replace("&&", " and ").replace("||", " or ")
    return eval(expression, {"__builtins__": {}}, {})


class DependencyPullRequestAdmissionTests(unittest.TestCase):
    def source(self, condition=None, events=None):
        job = {"name": "owned / check", "runs-on": "ubuntu-latest", "needs": "build",
               "strategy": {"matrix": {"python": ["3.11", "3.12"]}}, "steps": [{"run": "owned command"}]}
        if condition is not None:
            job["if"] = condition
        return {"on": events or {"pull_request": None, "pull_request_target": None,
                                 "pull_request_review": None, "merge_group": None, "workflow_dispatch": None},
                "jobs": {"owned": job}}

    def project(self, source=None, policy=POLICY):
        return MODULE.project_dependency_pull_requests("owned-workflow", self.source() if source is None else source, policy)

    def test_dependency_author_is_denied_on_all_PR_events_before_matrix(self):
        candidate = self.project()
        for event in ["pull_request", "pull_request_target", "pull_request_review"]:
            for actor in ["dependabot[bot]", "human-reviewer"]:
                with self.subTest(event=event, actor=actor):
                    self.assertFalse(observed_condition(candidate["jobs"]["owned"]["if"], event, "dependabot[bot]", actor))
        self.assertNotIn("if", candidate["jobs"]["owned"]["steps"][0])
        self.assertEqual(candidate["jobs"]["owned"]["strategy"], self.source()["jobs"]["owned"]["strategy"])

    def test_human_PR_and_non_PR_events_do_not_gain_an_actor_restriction(self):
        predicate = self.project()["jobs"]["owned"]["if"]
        for event in ["pull_request", "pull_request_target", "pull_request_review"]:
            self.assertTrue(observed_condition(predicate, event, "human-owner", "dependabot[bot]"))
        for event in ["push", "merge_group", "workflow_dispatch", "workflow_call"]:
            self.assertTrue(observed_condition(predicate, event, "dependabot[bot]", "dependabot[bot]"))

    def test_existing_always_needs_and_result_semantics_are_composed(self):
        source = self.source("${{ always() && needs.build.result == 'success' }}")
        before = copy.deepcopy(source)
        candidate = self.project(source)
        predicate = candidate["jobs"]["owned"]["if"]
        self.assertIn("always() && needs.build.result == 'success'", predicate)
        self.assertFalse(observed_condition(predicate, "pull_request_review", "dependabot[bot]"))
        self.assertTrue(observed_condition(predicate, "pull_request_review", "human", successful=True))
        self.assertFalse(observed_condition(predicate, "pull_request_review", "human", successful=False))
        self.assertEqual(source, before)
        self.assertEqual({k: v for k, v in candidate["jobs"]["owned"].items() if k != "if"}, {k: v for k, v in before["jobs"]["owned"].items() if k != "if"})

    def test_or_inside_original_condition_cannot_escape_the_new_guard(self):
        predicate = self.project(self.source("always() || success()"))["jobs"]["owned"]["if"]
        self.assertFalse(observed_condition(predicate, "pull_request_target", "dependabot[bot]"))
        self.assertTrue(observed_condition(predicate, "pull_request_target", "human"))

    def test_projection_is_idempotent_and_preserves_event_and_job_names(self):
        candidate = self.project(self.source("always()"))
        self.assertEqual(self.project(candidate), candidate)
        self.assertEqual(candidate["on"], self.source()["on"])
        self.assertEqual(candidate["jobs"]["owned"]["name"], "owned / check")

    def test_absent_canonical_or_non_PR_selection_does_not_change_jobs(self):
        source = self.source("${{ always() }}")
        for policy in [None, {"schema": 1}, {"schema": 1, "dependency_pull_requests": "canonical"}]:
            self.assertEqual(self.project(source, policy), source)
        non_PR = self.source(events={"workflow_dispatch": None, "workflow_call": None})
        self.assertEqual(self.project(non_PR), non_PR)

    def test_boolean_null_empty_or_ambiguous_conditions_require_source_review(self):
        for condition in [True, False, None, 1, [], "", " ", "${{ }}", "${{ always()", "always() }}",
                          "${{ success() }} || true", "${{ '${{ nested }}' }}", "always())", "(always()", "'unterminated", "${{ success() }}}", "{always()}"]:
            source = self.source()
            source["jobs"]["owned"]["if"] = condition
            with self.subTest(condition=condition), self.assertRaises(ValueError):
                self.project(source)

    def test_all_managed_jobs_are_qualified_before_any_partial_projection(self):
        source = self.source()
        source["jobs"]["invalid"] = {"if": False, "uses": "./.github/workflows/owned.yml"}
        before = copy.deepcopy(source)
        with self.assertRaises(ValueError):
            self.project(source)
        self.assertEqual(source, before)

    def test_reusable_jobs_are_gated_at_job_ownership_not_caller_steps(self):
        source = {"on": ["pull_request_review"], "jobs": {
            "call": {"uses": "./.github/workflows/release-artifacts.yml", "with": {"owned": "value"}},
        }}
        candidate = self.project(source)
        self.assertFalse(observed_condition(candidate["jobs"]["call"]["if"], "pull_request_review", "dependabot[bot]"))
        self.assertEqual(candidate["jobs"]["call"]["uses"], source["jobs"]["call"]["uses"])
        self.assertNotIn("steps", candidate["jobs"]["call"])

    def test_trailing_disjunction_cannot_reuse_an_apparent_guard_prefix(self):
        candidate = self.project(self.source("always()"))
        expression = candidate["jobs"]["owned"]["if"].removeprefix("${{").removesuffix("}}").strip()
        candidate["jobs"]["owned"]["if"] = "${{ " + expression + " || (always()) }}"
        with self.assertRaisesRegex(ValueError, "unbalanced"):
            self.project(candidate)

    def test_quoted_parentheses_and_doubled_quotes_keep_source_expression_boundaries(self):
        source = self.source("contains('owner''s (scope)', '(scope)')")
        candidate = self.project(source)
        self.assertIn("contains('owner''s (scope)', '(scope)')", candidate["jobs"]["owned"]["if"])
        self.assertEqual(self.project(candidate), candidate)

    def test_empty_or_nonobject_PR_jobs_are_not_silently_skipped(self):
        for jobs in [{}, [], {"owned": None}]:
            with self.subTest(jobs=jobs), self.assertRaises(ValueError):
                self.project({"on": "pull_request", "jobs": jobs})


if __name__ == "__main__":
    unittest.main()
