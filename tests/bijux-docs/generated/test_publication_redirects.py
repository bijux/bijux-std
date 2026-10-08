from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = Path(sys.executable)
MODULE = ROOT / "shared/bijux-docs/security/redirects.py"


class DocumentationRedirectTests(unittest.TestCase):
    """Render real pinned plugin output, then exercise the source-derived boundary."""

    def setUp(self):
        self.assertTrue(RUNTIME.is_file(), "Prepare actual renderer: make ui-test-install-docs; install mkdocs-redirects==1.2.3")
        parent = ROOT / "artifacts/website-security/redirect-tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.docs = self.root / "docs"
        self.docs.mkdir()
        for name, text in (("index.md", "# Overview\n"), ("target.md", "# Destination\n\n## Known heading\n"),
                           ("bridge.md", "# Previous destination\n"), ("second.md", "# Secondary\n"),
                           ("science-λ.md", '# Unicode destination\n\n<h2 id="λ-measurement">λ measurement</h2>\n')):
            (self.docs / name).write_text(text)
        self.config = {"site_name": "Redirect reference", "site_url": "https://bijux.io/bijux-core/",
                       "site_dir": "artifacts/docs/site", "theme": {"name": "material", "font": False},
                       "plugins": ["search", {"redirects": {"redirect_maps": {"old.md": "target.md", "nested/old.md": "second.md"}}}]}
        self.config_path = self.root / "mkdocs.yml"
        self.site = self.root / "artifacts/docs/site"
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    def build(self):
        self.config_path.write_text(json.dumps(self.config))
        result = subprocess.run([str(RUNTIME), "-m", "mkdocs", "build", "--strict", "--config-file", str(self.config_path)],
                                cwd=self.root, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def normalize(self, *, expected_success=True, check=False):
        self.config_path.write_text(json.dumps(self.config))
        result = subprocess.run([str(RUNTIME), str(MODULE), "--config", "mkdocs.yml", "--site-dir", "artifacts/docs/site",
                                 "--output", "artifacts/website-security/redirects.json", *(["--check"] if check else [])], cwd=self.root,
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, expected_success, result.stderr)
        if expected_success:
            return json.loads((self.root / "artifacts/website-security/redirects.json").read_text())
        return result.stderr

    def identity_probe(self, body, *, expected_success=True):
        script = ('import sys,json,hashlib\nfrom pathlib import Path\n'
                  f'sys.path.insert(0,{str(MODULE.parent)!r})\n'
                  'import build_identity as identity\nfrom mkdocs.config import load_config\n'
                  'configuration=load_config("mkdocs.yml")\n' + body)
        result = subprocess.run([str(RUNTIME), "-c", script], cwd=self.root, env=self.env,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, expected_success, result.stderr)
        return result.stdout if expected_success else result.stderr

    def test_actual_plugin_identity_binds_module_version_and_declared_map(self):
        self.build()
        report = self.normalize(check=True)
        rendered = json.loads(self.identity_probe('print(json.dumps(identity.renderer(configuration)))'))
        plugin = rendered["plugins"]["redirects"]
        self.assertEqual(plugin["source"]["sha256"], report["policy_inputs"]["plugin"]["module_sha256"])
        self.assertEqual(plugin["distributions"]["mkdocs-redirects"], "1.2.3")
        self.assertEqual(plugin["redirect_map_sha256"], report["policy_inputs"]["redirect_map_sha256"])

    def test_authored_hook_module_is_fingerprinted_and_untracked_publication_hook_rejected(self):
        hook = self.root / "configs/docs/assets.py"
        hook.parent.mkdir(parents=True)
        hook.write_text('def on_config(config):\n    return config\n')
        self.config["hooks"] = ["configs/docs/assets.py"]
        self.build()
        rendered = json.loads(self.identity_probe('print(json.dumps(identity.renderer(configuration)))'))
        actual = [row for row in rendered["plugins"].values() if row["source"]["name"] == "assets.py"]
        self.assertEqual(len(actual), 1)
        import hashlib
        self.assertEqual(actual[0]["source"]["sha256"], hashlib.sha256(hook.read_bytes()).hexdigest())
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True, capture_output=True)
        error = self.identity_probe('identity.source_inputs(configuration,Path.cwd(),publication_scope=True)', expected_success=False)
        self.assertIn("required Git operation failed", error)
        hook.write_text(hook.read_text() + '# Renderer ownership changed\n')
        changed = json.loads(self.identity_probe('print(json.dumps(identity.renderer(configuration)))'))
        newer = [row for row in changed["plugins"].values() if row["source"]["name"] == "assets.py"][0]
        self.assertNotEqual(actual[0]["source"]["sha256"], newer["source"]["sha256"])

    def test_unreviewed_plugin_module_rejected_without_mutation(self):
        self.build()
        before = {p: p.read_bytes() for p in self.site.rglob("*") if p.is_file()}
        error = self.identity_probe('import redirects\nredirects.PLUGIN_MODULE_SHA256="0"*64\nredirects.normalize_redirects(configuration,Path(configuration.site_dir),configuration.site_url)', expected_success=False)
        self.assertIn("reviewed", error)
        self.assertTrue(all(path.read_bytes() == content for path, content in before.items()))

    def test_actual_csp_transaction_receipt_is_accepted_by_publication_redirect_guard(self):
        overrides = self.root / "overrides/partials/javascripts"
        overrides.mkdir(parents=True)
        for name in ("base.html", "palette.html"):
            shutil.copy(MODULE.parents[1] / "partials/javascripts" / name, overrides / name)
        self.config["theme"]["custom_dir"] = "overrides"
        self.build()
        command = [str(RUNTIME), str(MODULE.with_name("csp.py")), "--config", "mkdocs.yml",
                   "--site-dir", "artifacts/docs/site", "--output", "artifacts/website-security/csp.json"]
        result = subprocess.run(command, cwd=self.root, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        body = ('import publication\n'
                'report=json.loads(Path("artifacts/website-security/csp.json").read_text())\n'
                'build={"renderer":identity.renderer(configuration),"resolved_config_sha256":identity.configuration_identity(configuration,Path.cwd())}\n'
                f'accepted=publication.qualified_redirects(Path({str(MODULE.parents[1])!r}),build,report,Path(configuration.site_dir),configuration.site_url)\n'
                'print(json.dumps(accepted))')
        accepted = json.loads(self.identity_probe(body))
        self.assertEqual(set(accepted), {"old/index.html", "nested/old/index.html"})

    def test_directory_routes_absolute_canonical_exact_script_and_idempotence(self):
        self.build()
        report = self.normalize()
        self.assertEqual(len(report["records"]), 2)
        old = next(row for row in report["records"] if row["source"] == "old.md")
        self.assertEqual(old["canonical"], self.config["site_url"] + "target/")
        content = (self.site / old["path"]).read_text()
        self.assertIn('window.location.replace(target.href)', content)
        self.assertIn('href="' + old["canonical"] + '"', content)
        self.assertIn(old["script"], content)
        self.assertIn('get("h")', old["script"])
        again = self.normalize()
        self.assertEqual([row["normalized_sha256"] for row in report["records"]],
                         [row["normalized_sha256"] for row in again["records"]])

    def test_flat_routes_and_unicode_destinations(self):
        self.config["use_directory_urls"] = False
        self.config["plugins"][1]["redirects"]["redirect_maps"] = {"old.md": "science-λ.md#λ-measurement"}
        self.build()
        report = self.normalize()
        self.assertEqual(report["records"][0]["target"], self.config["site_url"] + "science-%CE%BB.html#%CE%BB-measurement")
        self.assertEqual(report["records"][0]["path"], "old.html")

    def test_chain_flattens_to_existing_terminal_and_first_configured_fragment_wins(self):
        self.config["plugins"][1]["redirects"]["redirect_maps"] = {"old.md": "bridge.md", "bridge.md": "target.md#known-heading"}
        self.build()
        report = self.normalize()
        self.assertTrue(all(row["target"].endswith("target/#known-heading") for row in report["records"]))

    def test_self_redirect_and_cycle_reject_without_mutation(self):
        for mapping in ({"bridge.md": "bridge.md"}, {"bridge.md": "second.md", "second.md": "bridge.md"}):
            self.config["plugins"][1]["redirects"]["redirect_maps"] = mapping
            self.build()
            before = {p: p.read_bytes() for p in self.site.rglob("*.html")}
            self.assertIn("cycle", self.normalize(expected_success=False))
            self.assertTrue(all(path.read_bytes() == content for path, content in before.items()))

    def test_missing_fragment_preflight_leaves_all_stubs_unchanged(self):
        self.config["plugins"][1]["redirects"]["redirect_maps"]["nested/old.md"] = "second.md#missing"
        self.build()
        before = (self.site / "old/index.html").read_bytes()
        self.assertIn("fixed fragment", self.normalize(expected_success=False))
        self.assertEqual((self.site / "old/index.html").read_bytes(), before)

    def test_appended_script_or_wrong_target_rejected_before_any_writes(self):
        self.build()
        before = (self.site / "nested/old/index.html").read_bytes()
        stub = self.site / "old/index.html"
        stub.write_text(stub.read_text().replace("</head>", "<script>window.attacked=true</script></head>"))
        self.assertIn("exact declared", self.normalize(expected_success=False))
        self.assertEqual((self.site / "nested/old/index.html").read_bytes(), before)

    def test_source_route_collision_rejected(self):
        self.config["plugins"][1]["redirects"]["redirect_maps"] = {"old.md": "target.md", "old/index.md": "target.md"}
        self.build()
        self.assertIn("colliding", self.normalize(expected_success=False))

    def test_undeclared_redirect_target_and_symlink_rejected(self):
        self.build()
        target = self.site / "target/index.html"
        target.write_text('<meta http-equiv="refresh" content="0;url=https://remote.example/">')
        self.assertIn("undeclared redirect", self.normalize(expected_success=False))
        target.unlink()
        target.symlink_to(self.site / "second/index.html")
        self.assertIn("symlink", self.normalize(expected_success=False))

    def test_external_ambiguous_or_absent_declared_targets_rejected(self):
        self.build()
        for new in ("https://remote.example/", "../target.md", "target.md?x=1", "target%2emd", "missing.md", 'target.md#x";attack'):
            self.config["plugins"][1]["redirects"]["redirect_maps"] = {"old.md": new}
            self.normalize(expected_success=False)

    def test_empty_plugin_map_and_disabled_plugin_have_explicit_scope(self):
        self.config["plugins"] = ["search"]
        self.build()
        report = self.normalize()
        self.assertEqual(report["records"], [])
        self.assertIsNone(report["policy_inputs"]["plugin"])

    def test_complete_dry_run_preserves_public_tree_and_reapplication_revalidates_source(self):
        self.build()
        before = {path: path.read_bytes() for path in self.site.rglob("*") if path.is_file()}
        plan = self.normalize(check=True)
        self.assertFalse(plan["applied"])
        self.assertTrue(all(path.read_bytes() == content for path, content in before.items()))
        self.assertTrue(all(row["normalized_html"] and row["script"] in row["normalized_html"] for row in plan["records"]))
        changed = self.site / "old/index.html"
        changed.write_text(changed.read_text().replace("</head>", '<script>attack()</script></head>'))
        self.assertIn("exact declared", self.normalize(expected_success=False))
        self.assertEqual((self.site / "nested/old/index.html").read_bytes(), before[self.site / "nested/old/index.html"])


if __name__ == "__main__":
    unittest.main()
