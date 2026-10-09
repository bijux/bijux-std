from __future__ import annotations

import importlib.util
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / "shared/bijux-docs/security"
WORKFLOW = ROOT / "shared/bijux-gh/workflows/deploy-docs.yml"
spec = importlib.util.spec_from_file_location("bijux_docs_publication", SECURITY / "publication.py")
assert spec and spec.loader
publication = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publication)
identity = publication.identity_module()


def shell_step(name: str) -> str:
    text = WORKFLOW.read_text()
    start = text.index("      - name: " + name + "\n")
    end = text.find("\n      - name:", start + 1)
    section = text[start:end if end >= 0 else len(text)]
    run = section.index("        run: |\n") + len("        run: |\n")
    lines = []
    for line in section[run:].splitlines():
        if line and not line.startswith("          "):
            break
        lines.append(line[10:])
    return "\n".join(lines) + "\n"


class PublicationSecurityTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "artifacts/website-security/tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.site = self.root / "artifacts/docs/site"
        self.site.mkdir(parents=True)
        self.url = "https://bijux.io/bijux-core/"
        self.html = f'<html><head><title>Core</title><link rel="canonical" href="{self.url}"></head><body><a href="guide/">Guide</a></body></html>'
        (self.site / "index.html").write_text(self.html)
        self.policy = publication.load_policy()
        self.config = dict(repository="bijux/bijux-core", event="workflow_dispatch", ref="refs/heads/main",
                           default_branch="main", site_url=self.url, site_dir="artifacts/docs/site",
                           verify_command="make gh-docs-verify", repo_root=self.root)

    def manifest(self):
        return publication.bundle_manifest(self.root, "artifacts/docs/site", self.url, "a" * 40, self.policy)

    def test_default_branch_and_version_tags_admitted(self):
        publication.validate_config(**self.config)
        for ref in ("refs/tags/v1.2.3", "refs/tags/v1.2.3-rc.1"):
            publication.validate_config(**(self.config | {"event": "push", "ref": ref}))

    def test_untrusted_events_and_reusable_feature_refs_rejected(self):
        for event in ("pull_request", "pull_request_target", "workflow_run"):
            with self.subTest(event=event), self.assertRaises(publication.AdmissionError):
                publication.validate_config(**(self.config | {"event": event}))
        for ref in ("refs/heads/feature", "refs/tags/vanything", "refs/tags/latest"):
            with self.subTest(ref=ref), self.assertRaises(publication.AdmissionError):
                publication.validate_config(**(self.config | {"event": "workflow_call", "ref": ref}))

    def test_foreign_loopback_and_newline_site_identity_rejected(self):
        for url in ("http://127.0.0.1:8000/", "https://foreign.example/", self.url + "\nsite_available=true", "https://bijux.io/bijux-other/", self.url + "?q=private"):
            with self.subTest(url=url), self.assertRaises(publication.AdmissionError):
                publication.validate_config(**(self.config | {"site_url": url}))

    def test_empty_and_multiline_verifier_rejected(self):
        for command in ("", "  ", "make verify\nother=value"):
            with self.subTest(command=command), self.assertRaises(publication.AdmissionError):
                publication.validate_config(**(self.config | {"verify_command": command}))

    def test_traversal_shell_and_foreign_output_paths_rejected(self):
        for path in ("docs/site", "/tmp/site", "artifacts/../private", "artifacts/site;echo", "artifacts/site\nextra=true"):
            with self.subTest(path=path), self.assertRaises(publication.AdmissionError):
                publication.site_directory(self.root, path)

    def test_symlink_root_and_nested_file_rejected(self):
        (self.root / "artifacts/linked").symlink_to(self.site, target_is_directory=True)
        with self.assertRaises(publication.AdmissionError):
            publication.site_directory(self.root, "artifacts/linked")
        (self.site / "leak.txt").symlink_to(self.root / "private.txt")
        with self.assertRaisesRegex(publication.AdmissionError, "symlink"):
            self.manifest()

    def test_missing_exact_output_does_not_admit_stale_candidate(self):
        stale = self.root / "artifacts/root/docs/site"
        stale.mkdir(parents=True)
        (stale / "index.html").write_text(self.html)
        shutil.rmtree(self.site)
        with self.assertRaises(publication.AdmissionError):
            self.manifest()

    def test_private_configs_maps_and_executables_rejected(self):
        for name in (".env", "mkdocs.yml", "private.map", "shell.sh"):
            path = self.site / name
            path.write_text("private output")
            with self.subTest(name=name), self.assertRaises(publication.AdmissionError):
                self.manifest()
            path.unlink()

    def test_owned_map_exception_cannot_admit_private_dotfile(self):
        self.policy["public_exceptions"] = [{"pattern": "public.map", "purpose": "Public runtime source debugging"}]
        (self.site / "public.map").write_text('{}')
        self.manifest()
        self.policy["public_exceptions"].append({"pattern": ".env", "purpose": "fixture"})
        (self.site / ".env").write_text("PRIVATE=value")
        with self.assertRaises(publication.AdmissionError):
            self.manifest()

    def test_private_marker_error_never_prints_private_value(self):
        for content in ("ghp_" + "A" * 36, "-----BEGIN PRIVATE KEY-----"):
            (self.site / "config.json").write_text(content)
            with self.assertRaises(publication.AdmissionError) as caught:
                self.manifest()
            self.assertNotIn(content, str(caught.exception))
            self.assertIn("private-material", str(caught.exception))

    def test_executable_attributes_and_wrong_canonical_rejected(self):
        for change in (self.html.replace(self.url, "http://127.0.0.1:8000/"),
                       self.html.replace('href="guide/"', 'href="java&#x73;cript:alert(1)"'),
                       self.html.replace('href="guide/"', 'href="java%73cript:alert(1)"'),
                       self.html.replace('<body>', '<body onclick="alert(1)">'),
                       self.html.replace('<body>', '<body><script src="http://example.invalid/unsafe.js"></script>')):
            (self.site / "index.html").write_text(change)
            with self.subTest(html=change), self.assertRaises(publication.AdmissionError):
                self.manifest()

    def test_escaped_code_example_remains_readable(self):
        (self.site / "index.html").write_text(self.html.replace("</body>", '<code>&lt;a onclick="example"&gt;</code></body>'))
        self.manifest()

    def test_changed_added_and_removed_upload_bytes_rejected(self):
        previous = self.manifest()
        (self.site / "extra.txt").write_text("new")
        with self.assertRaisesRegex(publication.AdmissionError, "changed after qualification"):
            publication.verify_manifest(self.root, previous, self.policy)
        (self.site / "extra.txt").unlink()
        publication.verify_manifest(self.root, previous, self.policy)
        (self.site / "index.html").write_text(self.html.replace("Guide", "Changed"))
        with self.assertRaises(publication.AdmissionError):
            publication.verify_manifest(self.root, previous, self.policy)

    def test_previous_byte_restore_qualifies_recovery_identity(self):
        previous = self.manifest()
        (self.site / "index.html").write_text(self.html.replace("Core", "Broken"))
        with self.assertRaises(publication.AdmissionError):
            publication.verify_manifest(self.root, previous, self.policy)
        (self.site / "index.html").write_text(self.html)
        self.assertEqual(publication.verify_manifest(self.root, previous, self.policy), previous)

    def test_policy_change_invalidates_previous_admission(self):
        previous = self.manifest()
        self.policy["maximum_files"] += 1
        with self.assertRaises(publication.AdmissionError):
            publication.verify_manifest(self.root, previous, self.policy)

    def test_size_and_file_budgets_reject_candidate(self):
        self.policy["maximum_bytes"] = 1
        with self.assertRaisesRegex(publication.AdmissionError, "size budget"):
            self.manifest()
        self.policy["maximum_bytes"] = 100000
        self.policy["maximum_files"] = 0
        with self.assertRaisesRegex(publication.AdmissionError, "file budget"):
            self.manifest()

    def test_scientific_svg_remains_a_passive_public_figure(self):
        figure = b'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<metadata><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:cc="http://creativecommons.org/ns#">
<cc:Work rdf:about=""><dc:type rdf:resource="http://purl.org/dc/dcmitype/StillImage"/>
<dc:date>2026-10-08T12:00:00</dc:date><dc:format>image/svg+xml</dc:format>
<dc:creator><cc:Agent><dc:title>Matplotlib and scientific figure author</dc:title></cc:Agent></dc:creator>
<dc:subject><rdf:Bag><rdf:li>Scientific provenance</rdf:li></rdf:Bag></dc:subject>
<cc:license rdf:resource="https://creativecommons.org/licenses/by/4.0/"/></cc:Work>
<cc:License rdf:about="https://creativecommons.org/licenses/by/4.0/"><cc:requires rdf:resource="http://creativecommons.org/ns#Attribution"/></cc:License>
</rdf:RDF></metadata>
<defs><path id="glyph" d="M0 0L2 2"/><clipPath id="clip"><rect width="2" height="2"/></clipPath></defs>
<style>* {stroke-linecap: butt} .plot {clip-path:url(#clip)}</style>
<g class="plot"><use xlink:href="#glyph"/><image href="data:image/png;base64,iVBORw0KGgo="/></g>
<a href="https://bijux.io/guide/"><text>Figure reference</text></a></svg>'''
        (self.site / "figure.svg").write_bytes(figure)
        self.assertIn("figure.svg", [item["path"] for item in self.manifest()["files"]])

    def test_scientific_metadata_cannot_admit_active_or_unscoped_foreign_content(self):
        contents = (
            '<metadata><script xmlns="http://purl.org/dc/elements/1.1/">attack</script></metadata>',
            '<metadata><title xmlns="http://purl.org/dc/elements/1.1/" onload="attack()">author</title></metadata>',
            '<metadata><title xmlns="http://purl.org/dc/elements/1.1/" href="https://remote.example/pixel">author</title></metadata>',
            '<metadata><image href="https://remote.example/pixel"/></metadata>',
            '<metadata><title xmlns="http://purl.org/dc/elements/1.1/" style="fill:url(https://remote.example/pixel)">author</title></metadata>',
            '<title xmlns="http://purl.org/dc/elements/1.1/">outside metadata</title>',
            '<metadata><unknown xmlns="http://www.inkscape.org/namespaces/inkscape"/></metadata>',
        )
        for content in contents:
            with self.subTest(content=content), self.assertRaises(publication.AdmissionError):
                publication.static_svg(('<svg xmlns="http://www.w3.org/2000/svg">'+content+'</svg>').encode(), 10000)
        publication.static_svg(b'<svg xmlns="http://www.w3.org/2000/svg"><metadata><clipboard xmlns="http://www.inkscape.org/namespaces/inkscape" min="0,0" max="10,10"/></metadata></svg>', 10000)

    def test_active_and_external_svg_document_content_rejected(self):
        fragments = (
            '<script>alert(1)</script>', '<foreignObject><div>HTML</div></foreignObject>',
            '<form xmlns="http://www.w3.org/1999/xhtml" action="https://remote.example/">content</form>',
            '<rect onload="alert(1)"/>', '<a href="javascript:alert(1)">click</a>',
            '<set attributeName="href" to="javascript:alert(1)"/>',
            '<image href="https://remote.example/pixel"/>', '<use href="//remote.example/vector.svg#x"/>',
            '<image href="\\\\remote.example/pixel"/>',
            '<g xml:base="https://remote.example/"><image href="pixel"/></g>',
            '<style>@import "https://remote.example/style";</style>',
            '<rect style="fill:u\\72l(https://remote.example/pixel)"/>',
            '<style>.x {fill: url(https://remote.example/pixel)}</style>',
            '<image href="data:image/svg+xml;base64,PHN2Zy8+"/>',
            '<image href="data:image/png;base64,PHN2Zy8+"/>',
        )
        for fragment in fragments:
            (self.site / "figure.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg">{fragment}</svg>')
            with self.subTest(fragment=fragment), self.assertRaisesRegex(publication.AdmissionError, "unadmitted-svg-content"):
                self.manifest()

    def test_svg_parser_declarations_and_asset_budget_fail_closed(self):
        values = (b'<?xml-stylesheet href="https://remote.example/x"?><svg/>',
                  b'<!DOCTYPE svg [<!ENTITY content "injected">]><svg>&content;</svg>',
                  '<!DOCTYPE svg [<!ENTITY content "injected">]><svg>&content;</svg>'.encode("utf-16"),
                  b'<svg><path></svg>', b'<html/>')
        for content in values:
            (self.site / "figure.svg").write_bytes(content)
            with self.subTest(content=content), self.assertRaisesRegex(publication.AdmissionError, "unadmitted-svg-content"):
                self.manifest()
        (self.site / "figure.svg").write_bytes(b'<svg/>')
        self.policy["maximum_svg_bytes"] = 1
        with self.assertRaisesRegex(publication.AdmissionError, "unadmitted-svg-content"):
            self.manifest()

    def resolver(self, *, make_verifier=True, **overrides):
        guard = self.root / "shared/bijux-docs/security"
        guard.mkdir(parents=True, exist_ok=True)
        shutil.copy(SECURITY / "publication.py", guard)
        makefile = "gh-docs-build:\n\t@true\n" + ("gh-docs-verify:\n\t@true\n" if make_verifier else "")
        (self.root / "Makefile").write_text(makefile)
        script = shell_step("Validate publication event and ref") + shell_step("Resolve docs deploy configuration")
        env = {key: value for key, value in os.environ.items() if not key.startswith(("BIJUX_DOCS_", "VARS_DOCS_"))}
        env.update(GITHUB_REPOSITORY="bijux/bijux-core", GITHUB_EVENT_NAME="workflow_dispatch",
                   GITHUB_REF="refs/heads/main", DOCS_DEFAULT_BRANCH="main", GITHUB_OUTPUT=str(self.root / "outputs"))
        for key in re.findall(r'\$(VARS_DOCS_[A-Z_]+)', script):
            env[key] = ""
        env.update(overrides)
        env.update(PUBLICATION_EVENT=env["GITHUB_EVENT_NAME"], PUBLICATION_REF=env["GITHUB_REF"], PUBLICATION_DEFAULT_BRANCH=env["DOCS_DEFAULT_BRANCH"])
        return subprocess.run(["bash", "-c", script], cwd=self.root, env=env, text=True, capture_output=True)

    def test_real_workflow_resolver_passes_default_and_rejects_reusable_feature(self):
        passing = self.resolver()
        self.assertEqual(passing.returncode, 0, passing.stderr)
        self.assertNotEqual(self.resolver(GITHUB_EVENT_NAME="workflow_call", GITHUB_REF="refs/heads/untrusted").returncode, 0)

    def test_real_workflow_resolver_requires_verifier_and_rejects_output_injection(self):
        failed = self.resolver(make_verifier=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("verification command", failed.stderr)
        self.assertNotEqual(self.resolver(VARS_DOCS_SITE_DIR="artifacts/docs/site\nsite_available=true").returncode, 0)
        self.assertNotEqual(self.resolver(VARS_DOCS_SETUP_NODE="true\ninjected=true").returncode, 0)

    def test_real_workflow_output_step_never_selects_stale_fallback(self):
        stale = self.root / "artifacts/root/docs/site"
        stale.mkdir(parents=True)
        (stale / "index.html").write_text(self.html)
        env = dict(os.environ, DOCS_SITE_DIR="artifacts/absent", GITHUB_OUTPUT=str(self.root / "output"))
        result = subprocess.run(["bash", "-c", shell_step("Resolve docs artifact directory")], cwd=self.root,
                                env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "output").exists())

    def test_build_has_no_publication_privileges_or_interpolated_shell_data(self):
        text = WORKFLOW.read_text()
        build = text.split("  build:\n", 1)[1].split("\n  deploy:", 1)[0]
        self.assertNotIn("pages: write", build)
        self.assertNotIn("id-token: write", build)
        self.assertNotIn("run: ${{", text)
        self.assertIn("persist-credentials: false", build)
        self.assertIn("pages: write", text.split("\n  deploy:", 1)[1])


class QualifiedPublicationTests(unittest.TestCase):
    """Exercise receipt invariants using clean Git fixtures and an isolated test producer.

    This source fixture does not qualify the real renderer. Separate producer
    reconstruction tests cover actual executable/index and profile authority.
    """

    def setUp(self):
        PublicationSecurityTests.setUp(self)
        self.standard = self.root / "artifacts/accepted-standard"
        self.standard.mkdir()
        canonical = self.standard / "shared/bijux-docs/security"
        canonical.mkdir(parents=True)
        for name in ("publication.py", "build_identity.py", "policy.json", "csp.py", "redirects.py"):
            shutil.copy(SECURITY / name, canonical / name)
        (canonical / "producer_authority.py").write_text(
            "def verify_publication(root, site, shared, build, csp, checkpoint):\n"
            "    return {'scope': 'isolated-receipt-contract-test', 'verification_only': True}\n")
        for name in ("base.html", "palette.html"):
            destination = self.standard / "shared/bijux-docs/partials/javascripts" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(SECURITY.parent / "partials/javascripts" / name, destination)
        self.git(self.standard, "init", "-q")
        self.git(self.standard, "add", "shared")
        self.git(self.standard, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture source")
        self.standard_sha = self.git(self.standard, "rev-parse", "HEAD").strip()
        self.git(self.standard, "remote", "add", "origin", "https://github.com/bijux/bijux-std.git")
        (self.standard / ".git/FETCH_HEAD").write_text(self.standard_sha + "\t\tfixture of https://github.com/bijux/bijux-std\n")
        shutil.copytree(self.standard / "shared/bijux-docs", self.root / ".bijux/shared/bijux-docs")
        (self.root / ".github/standards").mkdir(parents=True)
        (self.root / ".github/standards/bijux-std.sha").write_text(self.standard_sha + "\n")
        (self.root / ".gitignore").write_text("artifacts/\n")
        (self.root / "docs").mkdir()
        (self.root / "docs/index.md").write_text("# Fixture\n")
        self.config_file = self.root / "mkdocs.yml"
        self.config_file.write_text(f"site_name: Fixture\nsite_url: !ENV [SITE_URL, '{self.url}']\ntheme:\n  name: material\n  font: false\n")
        self.git(self.root, "init", "-q")
        self.git(self.root, "add", ".gitignore", ".github", ".bijux", "mkdocs.yml", "docs")
        self.git(self.root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture consumer")
        self.source_sha = self.git(self.root, "rev-parse", "HEAD").strip()
        actual_git = identity.git

        def fixture_fetch(root, *args):
            if args and args[0] == "fetch":
                self.assertEqual(Path(root), self.standard)
                self.assertEqual(args, ("fetch", "--quiet", "--depth", "1", "origin", self.standard_sha))
                return ""
            return actual_git(root, *args)

        with mock.patch.object(identity, "git", side_effect=fixture_fetch):
            self.source = identity.source_checkpoint(self.root, self.source_sha, "artifacts/accepted-standard", self.url,
                                                     "artifacts/docs/site", "make docs", "make gh-docs-verify")
        policy = "; ".join(["default-src 'self'", "base-uri 'self'", "object-src 'none'", "form-action 'self'",
                            "script-src 'self'", "script-src-attr 'none'", "style-src 'self' 'unsafe-inline'",
                            "font-src 'self'", "connect-src 'self'", "worker-src 'self' blob:",
                            "img-src 'self' data: https://img.shields.io https://raw.githubusercontent.com",
                            "media-src 'self'", "frame-src 'none'", "manifest-src 'self'"])
        (self.site / "index.html").write_text(self.html.replace("<head>", '<head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="' + policy + '">'))
        _, bundle = publication.public_bundle_identity(self.site)
        common = {"schema": 1, "site_url": self.url, "site_dir": "artifacts/docs/site", "bundle_sha256": bundle}
        self.records = {
            "source": self.source,
            "build": common | {"state": "complete", "verification_only": False, "scope": "actual-mkdocs-renderer",
                                "config": {"path": "mkdocs.yml", "sha256": hashlib.sha256(self.config_file.read_bytes()).hexdigest()},
                                "resolved_config_sha256": "c" * 64,
                                "renderer_inputs": [{"path": "docs", "sha256": identity.tree_identity(self.root / "docs")}],
                                "processor_sha256": hashlib.sha256((SECURITY / "build_identity.py").read_bytes()).hexdigest(),
                                "source_checkpoint": self.source, "source_checkpoint_sha256": identity.json_digest(self.source),
                                "renderer": {"python": "3.11.0", "implementation": "cpython", "plugins": {},
                                             "material_templates": [{"path": "partials/javascripts/fixture.html", "sha256": "f" * 64}],
                                             "packages": {name: "9.7.7" if name == "mkdocs-material" else "fixture" for name in
                                                          ("mkdocs", "mkdocs-material", "Jinja2", "PyYAML", "Markdown", "Pygments", "pymdown-extensions")}}},
            "verification": common | {"passed": True, "verification_only": False,
                                       "checks": [{"id": name, "passed": True, "errors": []} for name in
                                                  ("PUBLIC-ROUTES", "SEARCH-DELIVERY", "PRODUCTION-URLS")],
                                       "source_checks": {"before": True, "after": True, "mode": "exact_fetched",
                                                         "standard_sha": self.standard_sha, "origin": self.source["standard"]["origin"]},
                                       "scope": ["PUBLIC-ROUTES", "SEARCH-DELIVERY", "PRODUCTION-URLS"]},
            "csp": common | {"policy": "early-meta-hashes", "material": "9.7.7", "pages": 1, "script_hashes": [],
                             "redirects": {"schema": 1, "policy": "exact-declared-redirects", "site_url": self.url,
                                           "applied": True, "records": []},
                             "processor_sha256": hashlib.sha256((SECURITY / "csp.py").read_bytes()).hexdigest(),
                             "policy_inputs": {
                                 "canonical": [{"path": "partials/javascripts/" + name,
                                                "sha256": hashlib.sha256((canonical.parent / "partials/javascripts" / name).read_bytes()).hexdigest()}
                                               for name in ("base.html", "palette.html")],
                                 "material_templates": [{"path": "partials/javascripts/fixture.html", "sha256": "f" * 64}],
                                 "redirects": {"processor_sha256": hashlib.sha256((SECURITY / "redirects.py").read_bytes()).hexdigest(),
                                               "resolved_config_sha256": "c" * 64, "plugin": None, "redirect_map_sha256": None}}}}
        self.paths = {name: f"artifacts/website-security/{name}.json" for name in self.records}
        self.write_records()

    @staticmethod
    def git(root, *args):
        result = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout

    def write_records(self):
        for name, value in self.records.items():
            path = self.root / self.paths[name]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))

    def qualified(self):
        self.write_records()
        return publication.qualified_manifest(self.root, "artifacts/docs/site", self.url, self.source_sha,
                                              self.policy, self.paths["source"], self.paths["build"],
                                              self.paths["verification"], self.paths["csp"])

    def test_local_embedded_candidate_receipt_cannot_bypass_independent_producer(self):
        original_import = __import__
        def guarded_import(name, *args, **kwargs):
            if name == "mkdocs" or name.startswith("mkdocs."):
                raise AssertionError("Missing source-owned descriptor must fail before optional renderer import")
            return original_import(name, *args, **kwargs)
        cases = ({"verification_only":True,"applied":True},
                 {"descriptor_path":""},
                 {"descriptor_path":"../outside-owner.json"},
                 {"descriptor_path":str(self.root.parent/'outside-owner.json')},
                 {"descriptor_path":str(self.root/'missing-owner.json')})
        for retained in cases:
            with self.subTest(retained=retained):
                self.records["csp"]["embedded"] = retained
                with mock.patch("builtins.__import__", side_effect=guarded_import):
                    with self.assertRaisesRegex(publication.AdmissionError, "independently reconstructed producer capability admission"):
                        self.qualified()

    def test_scoped_receipts_bind_real_clean_source_and_exact_standard(self):
        manifest = self.qualified()
        self.assertEqual(manifest["schema"], 2)
        self.assertEqual(manifest["standard_sha"], self.standard_sha)
        self.assertEqual(manifest["repository_source_sha"], self.source_sha)
        publication.verify_manifest(self.root, manifest, self.policy)

    def redirect_fixture(self):
        spec = importlib.util.spec_from_file_location("bijux_redirect_fixture", SECURITY / "redirects.py")
        processor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(processor)
        script = processor.SCRIPT.format(target=json.dumps(self.url, ensure_ascii=True))
        raw = processor.TEMPLATE.format(canonical=self.url, target=self.url, script=script)
        hashed = hashlib.sha256(script.encode()).digest()
        csp_hash = "'sha256-" + base64.b64encode(hashed).decode() + "'"
        policy = publication.DocumentPolicy()
        policy.feed((self.site / "index.html").read_text())
        effective = policy.csp[0].replace("script-src 'self'", "script-src 'self' " + csp_hash)
        (self.site / "old").mkdir()
        (self.site / "old/index.html").write_text(raw.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" content="' + effective + '">'))
        mapping = {"old.md": "index.md"}
        plugin = {"module": "mkdocs_redirects.plugin", "distributions": {"mkdocs-redirects": "1.2.3"},
                  "source": {"name": "plugin.py", "sha256": processor.PLUGIN_MODULE_SHA256},
                  "redirect_maps": mapping, "redirect_map_sha256": identity.json_digest(mapping), "use_directory_urls": True,
                  "routes": [{"source": "old.md", "path": "old/index.html", "declared_target": "index.md",
                              "destination": "index.html", "url": ""}]}
        self.records["build"]["renderer"]["plugins"]["redirects"] = plugin
        self.records["csp"]["policy_inputs"]["redirects"].update({
            "plugin": {"distribution": "mkdocs-redirects", "version": "1.2.3", "module": "mkdocs_redirects/plugin.py",
                       "module_sha256": processor.PLUGIN_MODULE_SHA256, "template_sha256": processor.PLUGIN_TEMPLATE_SHA256},
            "redirect_map_sha256": identity.json_digest(mapping)})
        self.records["csp"]["redirects"]["records"] = [{"path": "old/index.html", "source": "old.md", "declared_target": "index.md",
              "destination": "index.html", "target": self.url, "canonical": self.url,
              "input_sha256": "a" * 64, "normalized_sha256": hashlib.sha256(raw.encode()).hexdigest(),
              "script_sha256": hashed.hex(), "csp_hash": csp_hash}]
        self.records["csp"].update(pages=2, script_hashes=[csp_hash])
        _, bundle = publication.public_bundle_identity(self.site)
        for name in ("build", "verification", "csp"):
            self.records[name]["bundle_sha256"] = bundle
        return csp_hash

    def test_declared_redirect_receipt_binds_exact_page_and_actual_plugin(self):
        self.redirect_fixture()
        self.assertEqual(self.qualified()["schema"], 2)

    def test_redirect_forgery_cannot_launder_matching_bundle_receipts(self):
        self.redirect_fixture()
        baseline = copy.deepcopy(self.records)
        changes = [lambda: self.records["csp"]["policy_inputs"]["redirects"].update(processor_sha256="0" * 64),
                   lambda: self.records["csp"]["policy_inputs"]["redirects"].update(resolved_config_sha256="0" * 64),
                   lambda: self.records["build"]["renderer"]["plugins"]["redirects"]["source"].update(sha256="0" * 64),
                   lambda: self.records["csp"]["redirects"].update(records=[]),
                   lambda: self.records["csp"]["redirects"]["records"][0].update(target="https://foreign.example/"),
                   lambda: self.records["csp"]["redirects"]["records"][0].update(script_sha256="0" * 64),
                   lambda: self.records["csp"]["redirects"]["records"].append(copy.deepcopy(self.records["csp"]["redirects"]["records"][0]))]
        for change in changes:
            self.records = copy.deepcopy(baseline)
            change()
            with self.assertRaisesRegex(ValueError, "Redirect receipt"):
                self.qualified()

    def test_redirect_hash_is_not_global_script_permission(self):
        csp_hash = self.redirect_fixture()
        page = self.site / "index.html"
        page.write_text(page.read_text().replace("script-src 'self'", "script-src 'self' " + csp_hash))
        _, bundle = publication.public_bundle_identity(self.site)
        for name in ("build", "verification", "csp"):
            self.records[name]["bundle_sha256"] = bundle
        with self.assertRaisesRegex(ValueError, "another route"):
            self.qualified()

    def test_redirect_final_page_cannot_add_scripts_with_same_policy_receipt(self):
        self.redirect_fixture()
        page = self.site / "old/index.html"
        page.write_text(page.read_text().replace("</head>", '<script src="/unexpected.js"></script></head>'))
        _, bundle = publication.public_bundle_identity(self.site)
        for name in ("build", "verification", "csp"):
            self.records[name]["bundle_sha256"] = bundle
        with self.assertRaisesRegex(ValueError, "exact admitted template"):
            self.qualified()

    def test_dirty_tracked_or_untracked_source_cannot_be_laundered(self):
        for path in (self.config_file, self.root / "unreviewed.md"):
            original = path.read_bytes() if path.exists() else None
            path.write_text("unreviewed input")
            with self.assertRaisesRegex(ValueError, "source is dirty"):
                self.qualified()
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)

    def test_wrong_source_commit_rejected(self):
        self.records["source"]["repository_source"]["sha"] = "a" * 40
        with self.assertRaisesRegex(ValueError, "checkout HEAD differs"):
            self.qualified()

    def test_changed_accepted_checkout_rejected_even_when_consumer_clean(self):
        (self.standard / "shared/bijux-docs/security/policy.json").write_text("changed")
        with self.assertRaisesRegex(ValueError, "source is dirty"):
            self.qualified()

    def test_wrong_fetched_object_rejected(self):
        (self.standard / ".git/FETCH_HEAD").write_text(self.source_sha + "\t\twrong object\n")
        with self.assertRaises(ValueError):
            self.qualified()

    def test_ignored_standard_inputs_cannot_claim_accepted_git_identity(self):
        (self.standard / ".git/info/exclude").write_text("ignored.js\n")
        (self.standard / "shared/bijux-docs/security/ignored.js").write_text("unreviewed")
        with self.assertRaisesRegex(ValueError, "ignored or untracked shared inputs"):
            self.qualified()

    def test_stale_receipts_wrong_scope_and_candidate_flags_rejected(self):
        for name, field, value in (("build", "bundle_sha256", "d" * 64),
                                   ("verification", "verification_only", True),
                                   ("verification", "scope", ["PUBLIC-ROUTES"]),
                                   ("verification", "passed", False),
                                   ("csp", "pages", 0), ("csp", "site_url", "https://bijux.io/other/")):
            original = self.records[name][field]
            self.records[name][field] = value
            with self.subTest(name=name, field=field), self.assertRaises(ValueError):
                self.qualified()
            self.records[name][field] = original

    def test_guard_python_cannot_supply_missing_actual_renderer_identity(self):
        self.records["build"]["renderer"] = {"python": "guard-system-python", "packages": {}}
        with self.assertRaisesRegex(ValueError, "actual MkDocs renderer package identity missing"):
            self.qualified()

    def test_mechanical_checks_and_source_authority_cannot_be_replaced_by_pass_flag(self):
        self.records["verification"]["checks"] = []
        with self.assertRaisesRegex(ValueError, "missing mechanical checks"):
            self.qualified()

    def test_changed_installed_policy_templates_and_canonical_hashes_rejected(self):
        for category in ("canonical", "material_templates"):
            original = self.records["csp"]["policy_inputs"][category][0]["sha256"]
            self.records["csp"]["policy_inputs"][category][0]["sha256"] = "0" * 64
            with self.subTest(category=category), self.assertRaises(ValueError):
                self.qualified()
            self.records["csp"]["policy_inputs"][category][0]["sha256"] = original

    def test_broadened_or_late_csp_cannot_reuse_matching_policy_receipt(self):
        original = (self.site / "index.html").read_text()
        for content in (original.replace("script-src 'self'", "script-src 'self' 'unsafe-eval'"),
                        original.replace("default-src 'self'", "default-src *"),
                        original.replace("<head>", '<head><script src="assets/main.js"></script>'),
                        original.replace("<head>", '<head><base href="https://remote.example/">'),
                        original.replace("<head>", '<head><link rel="prefetch" href="https://remote.example/">')):
            (self.site / "index.html").write_text(content)
            _, digest = publication.public_bundle_identity(self.site)
            for name in ("build", "verification", "csp"):
                self.records[name]["bundle_sha256"] = digest
            with self.assertRaisesRegex(ValueError, "CSP receipt"):
                self.qualified()
        (self.site / "index.html").write_text(original)




if __name__ == "__main__":
    unittest.main()
