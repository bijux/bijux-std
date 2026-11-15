from pathlib import Path
import importlib.util
import json
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]


class GitLabPipelineTests(unittest.TestCase):
    def module(self):
        path = ROOT / "shared/bijux-gitlab/pipeline.py"
        self.assertTrue(path.is_file(), "GitLab pipeline composer is required")
        spec = importlib.util.spec_from_file_location("bijux_gitlab_pipeline", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_preserves_complete_physical_browser_and_frontend_inventory(self):
        module = self.module()
        jobs = module.job_contracts(ROOT)
        browsers = [name for name, value in jobs.items() if value["operation"] == "browser"]
        self.assertEqual(len(browsers), 54)
        self.assertIn("std / navigation reader-history / webkit", browsers)
        self.assertEqual(sum(v["frontend"] for v in jobs.values()), 73)
        self.assertEqual(len(jobs), 83)
        self.assertEqual(jobs["std / navigation fixtures"]["image"], module.PLAYWRIGHT_IMAGE)
        self.assertEqual(jobs["std / navigation reader-history / webkit"]["image"], module.PLAYWRIGHT_IMAGE)

    def test_six_fresh_contract_partitions_are_distinct_mandatory_physical_owners(self):
        module = self.module()
        contracts = module.job_contracts(ROOT)
        names = ['std / contracts'] + [f'std / contracts / partition {index}' for index in range(2, 7)]
        self.assertEqual({name: row['args'] for name, row in contracts.items() if row['operation'] == 'contracts'},
                         {name: [index] for index, name in enumerate(names)})
        pipeline = module.compose(ROOT)
        for name in names:
            with self.subTest(owner=name):
                self.assertNotIn('allow_failure', pipeline[name])
                self.assertEqual(pipeline[name]['stage'], 'validation')
                self.assertEqual(pipeline[name]['dependencies'], [])
                self.assertEqual(pipeline[name]['artifacts']['paths'], ['artifacts/gitlab/jobs/$CI_JOB_ID/'])
        self.assertNotIn('needs', pipeline['std / report'])

    def test_pipeline_uses_canonical_guard_and_has_no_mirror_writer(self):
        pipeline = self.module().compose(ROOT)
        first = pipeline["workflow"]["rules"][0]
        self.assertEqual(first["when"], "never")
        self.assertIn('88948041', first["if"])
        self.assertIn('bijux-oss/bijux-std', first["if"])
        for name, job in pipeline.items():
            if not isinstance(job, dict) or "script" not in job:
                continue
            self.assertNotIn("allow_failure", job)
            self.assertNotIn("git push", "\n".join(job["script"]))
            self.assertNotIn("GH_TOKEN", json.dumps(job))
        self.assertNotIn("needs", pipeline["std / report"])
        self.assertEqual(pipeline["std / report"]["dependencies"], [])

    def test_runtime_pins_and_artifact_retention_are_explicit(self):
        module = self.module()
        pipeline = module.compose(ROOT)
        self.assertEqual(module.NODE_VERSION, "24.21.0")
        self.assertEqual(module.UV_VERSION, "0.11.17")
        self.assertEqual(pipeline["std / standard"]["image"], "ruby:3.3.12-bookworm")
        self.assertEqual(pipeline["std / contracts"]["image"], "ruby:3.3.12-bookworm")
        self.assertIn("python3-yaml", " ".join(pipeline["std / contracts"]["before_script"]))
        self.assertEqual(pipeline["std / report"]["artifacts"]["expire_in"], "1 year")
        self.assertEqual(pipeline["std / navigation fixtures"]["artifacts"]["expire_in"], "14 days")

    def test_generated_include_reproduces_the_committed_configuration(self):
        module = self.module()
        target = ROOT / "shared/bijux-gitlab/ci/standards.yml"
        self.assertTrue(target.is_file(), "Generated GitLab include is required")
        self.assertEqual(json.loads(target.read_text()), module.compose(ROOT))

    def test_gitlab_package_is_governed_and_explicitly_selected(self):
        resolver = ROOT / "shared/bijux-checks/scripts/resolve-shared-directories.sh"
        config = ROOT / "shared/bijux-checks/bijux-std-checks.yml"
        def selected(*args):
            return subprocess.check_output([str(resolver), *args, str(config)] if args == ("--all",)
                else [str(resolver), "--select", str(config), *args], text=True).splitlines()
        self.assertIn("shared/bijux-gitlab", selected("--all"))
        self.assertIn("shared/bijux-gitlab", selected("gitlab"))
        self.assertNotIn("shared/bijux-gitlab", selected("common"))
