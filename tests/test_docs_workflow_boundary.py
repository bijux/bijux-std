"""Run publication event, configured-output and verifier gates without deployment."""

from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "shared/bijux-gh/workflows/deploy-docs.yml"


def step(name):
    text = WORKFLOW.read_text()
    start = text.index("      - name: " + name + "\n")
    end = text.find("\n      - name:", start + 1)
    section = text[start : end if end != -1 else len(text)]
    run = section.index("        run: |\n") + len("        run: |\n")
    return (
        "\n".join(
            line[10:]
            for line in section[run:].splitlines()
            if not line or line.startswith("          ")
        )
        + "\n"
    )


class WorkflowBoundaryTests(unittest.TestCase):
    def setUp(self):
        artifact = ROOT / "artifacts/qualification/docs-workflow-boundary"
        artifact.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=artifact)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.output = self.root / "output"

    def run_gate(self, name, **changes):
        script = step(name)
        env = {**os.environ, "GITHUB_OUTPUT": str(self.output)}
        env.update(changes)
        return subprocess.run(
            ["bash", "--noprofile", "--norc", "-c", script],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_all_permitted_events_follow_repository_default_or_semantic_release_ref(
        self,
    ):
        for event in ("push", "release", "workflow_dispatch", "workflow_call"):
            for branch in ("main", "documentation"):
                for ref in (
                    "refs/heads/" + branch,
                    "refs/tags/v0.0.0",
                    "refs/tags/v10.20.30",
                    "refs/tags/v1.2.3",
                    "refs/tags/v1.2.3-rc.1",
                    "refs/tags/v1.2.3+build.2",
                    "refs/tags/v1.2.3-rc.1+build.2",
                    "refs/tags/v1.2.3-0",
                    "refs/tags/v1.2.3-01alpha",
                    "refs/tags/v1.2.3-alpha-2",
                    "refs/tags/v1.2.3+001",
                    "refs/tags/v1.2.3+exp.sha.5114f85",
                ):
                    with self.subTest(event=event, branch=branch, ref=ref):
                        result = self.run_gate(
                            "Validate publication event and ref",
                            PUBLICATION_EVENT=event,
                            PUBLICATION_REF=ref,
                            PUBLICATION_DEFAULT_BRANCH=branch,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)

    def test_untrusted_events_feature_refs_and_malformed_release_tags_fail(self):
        for event in (
            "pull_request",
            "pull_request_target",
            "issues",
            "unknown",
            "workflow_call",
        ):
            refs = (
                ("refs/heads/main",)
                if event != "workflow_call"
                else (
                    "refs/heads/feature",
                    "refs/tags/v",
                    "refs/tags/vmalformed",
                    "refs/tags/v1.2",
                    "refs/tags/v1.2.3/escape",
                    "refs/tags/v01.2.3",
                    "refs/tags/v1.02.3",
                    "refs/tags/v1.2.03",
                    "refs/tags/v1.2.3-01",
                    "refs/tags/v1.2.3-alpha.01",
                    "refs/tags/v1.2.3-..",
                    "refs/tags/v1.2.3-",
                    "refs/tags/v1.2.3+",
                    "refs/tags/v1.2.3-alpha..beta",
                    "refs/tags/v1.2.3+build..2",
                    "refs/tags/v1.2.3-rc.1++build",
                    "refs/tags/v1.2.3+build/2",
                    "refs/tags/v1.2.3_rc",
                    "refs/tags/v1.2.3-rc_1",
                    "refs/tags/v1.2.3+build_2",
                    "refs/tags/v1.2.3+build.",
                    "refs/tags/v1.2.3-.alpha",
                    "refs/tags/v1.2.3+.build",
                )
            )
            for ref in refs:
                with self.subTest(event=event, ref=ref):
                    self.assertNotEqual(
                        self.run_gate(
                            "Validate publication event and ref",
                            PUBLICATION_EVENT=event,
                            PUBLICATION_REF=ref,
                            PUBLICATION_DEFAULT_BRANCH="main",
                        ).returncode,
                        0,
                    )

    def resolver(self, verifier=True, **changes):
        (self.root / "Makefile").write_text(
            "gh-docs-build:\n\t@true\n"
            + ("gh-docs-verify:\n\t@true\n" if verifier else "")
        )
        script = step("Resolve docs deploy configuration")
        env = {key: "" for key in re.findall(r"\$(VARS_DOCS_[A-Z_]+)", script)}
        env.update(GITHUB_REPOSITORY="bijux/bijux-core")
        env.update(changes)
        return self.run_gate("Resolve docs deploy configuration", **env)

    def test_repository_defaults_produce_one_output_and_actual_verifier(self):
        result = self.resolver()
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.output.read_text()
        self.assertIn("site_dir=artifacts/docs/site\n", text)
        self.assertIn("verify_command=make gh-docs-verify\n", text)

    def test_missing_verifier_rejects_before_output_selection(self):
        self.assertNotEqual(self.resolver(False).returncode, 0)
        self.assertFalse(self.output.exists())

    def test_control_character_and_path_data_cannot_inject_job_outputs(self):
        for key, value in (
            ("VARS_DOCS_SITE_DIR", "artifacts/docs/site\nsite_available=true"),
            ("VARS_DOCS_BUILD_COMMAND", "make docs\nid_token=write"),
            ("VARS_DOCS_SETUP_NODE", "true\ninjected=true"),
            ("VARS_DOCS_SITE_DIR", "artifacts/../outside"),
            ("VARS_DOCS_SITE_DIR", "../site"),
            ("VARS_DOCS_SITE_URL", "https://foreign.invalid/"),
        ):
            with self.subTest(key=key):
                self.assertNotEqual(self.resolver(**{key: value}).returncode, 0)
        self.assertFalse(self.output.exists())

    def test_stale_sibling_output_cannot_replace_missing_selected_bundle(self):
        stale = self.root / "artifacts/root/docs/site"
        stale.mkdir(parents=True)
        (stale / "index.html").write_text("stale")
        result = self.run_gate(
            "Resolve docs artifact directory", DOCS_SITE_DIR="artifacts/absent"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())

    def test_exact_selected_bundle_passes_without_rebuilding(self):
        site = self.root / "artifacts/docs/site"
        site.mkdir(parents=True)
        (site / "index.html").write_text("selected")
        result = self.run_gate(
            "Resolve docs artifact directory", DOCS_SITE_DIR="artifacts/docs/site"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("site_dir=artifacts/docs/site\n", self.output.read_text())

    def test_symlink_or_noncanonical_output_fails(self):
        actual = self.root / "owned"
        actual.mkdir()
        (actual / "index.html").write_text("owned")
        (self.root / "artifacts").mkdir()
        (self.root / "artifacts/link").symlink_to(actual, target_is_directory=True)
        for directory in (
            "artifacts/link",
            "artifacts/../owned",
            "artifacts/./docs/site",
            "artifacts//docs/site",
        ):
            with self.subTest(directory=directory):
                self.assertNotEqual(
                    self.run_gate(
                        "Resolve docs artifact directory", DOCS_SITE_DIR=directory
                    ).returncode,
                    0,
                )

    def test_deployment_privileges_and_command_data_stay_in_owned_boundaries(self):
        text = WORKFLOW.read_text()
        build = text.split("  build:\n", 1)[1].split("\n  deploy:", 1)[0]
        deploy = text.split("\n  deploy:", 1)[1]
        self.assertNotIn("pages: write", build)
        self.assertNotIn("id-token: write", build)
        self.assertNotIn("run: ${{", text)
        self.assertIn("persist-credentials: false", build)
        self.assertNotIn("Configure Pages", build)
        self.assertIn("pages: write", deploy)
        self.assertIn("id-token: write", deploy)
        self.assertNotIn("github.event_name == 'workflow_call' ||", deploy)
        self.assertNotIn("Build docs site fallback", text)


if __name__ == "__main__":
    unittest.main()
