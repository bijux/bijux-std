"""Exercise embedded ownership and CSP transactions without an installed renderer."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(
    os.environ.get(
        "BIJUX_EMBEDDED_TEST_SOURCE_ROOT", Path(__file__).resolve().parents[1]
    )
)
SECURITY = ROOT / "shared/bijux-docs/security"
BASE = "https://bijux.io/bijux-pollenomics/"
TRUSTED = "window.bijuxTrusted = true;"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


csp = load("bijux_embedded_test_csp", SECURITY / "csp.py")
publication = load("bijux_embedded_test_publication", SECURITY / "publication.py")


def digest(data):
    return hashlib.sha256(data).hexdigest()


class StaticTemplate:
    """The fixture has no template expressions; model that renderer boundary only."""

    def __init__(self, content):
        self.content = content

    def render(self, **kwargs):
        return self.content


class StaticEnvironment:
    def from_string(self, content):
        if "{{" in content or "{%" in content:
            raise AssertionError("Renderer-free fixtures must be literal templates")
        return StaticTemplate(content)


class EmbeddedReportCompositionTests(unittest.TestCase):
    def setUp(self):
        parent = Path(
            os.environ.get(
                "BIJUX_EMBEDDED_TEST_ARTIFACTS_ROOT",
                ROOT / "artifacts/website-security/embedded-report-tests",
            )
        )
        parent.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(directory.cleanup)
        self.case = Path(directory.name)
        self.repo = self.case / "owner"
        self.repo.mkdir()
        self.site = self.repo / "artifacts/site"
        self.site.mkdir(parents=True)
        self.shared = self.case / "shared"
        snippets = self.shared / "partials/javascripts"
        snippets.mkdir(parents=True)
        (snippets / "base.html").write_text(
            '<script>var __md_scope = new URL(".", location);</script>'
        )
        (snippets / "palette.html").write_text("<script>" + TRUSTED + "</script>")
        self.templates = self.case / "dependency/templates"
        (self.templates / "partials/javascripts").mkdir(parents=True)
        (self.templates / "partials/javascripts/static.html").write_text(
            "<script>window.dependency = true;</script>"
        )
        jinja = ModuleType("jinja2")
        jinja.Environment = StaticEnvironment
        material = ModuleType("material")
        material.__file__ = str(self.templates.parent / "__init__.py")
        self.modules = patch.dict(sys.modules, {"jinja2": jinja, "material": material})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        original_version = importlib.metadata.version
        version = patch.object(
            importlib.metadata,
            "version",
            side_effect=lambda name: (
                "9.7.7" if name == "mkdocs-material" else original_version(name)
            ),
        )
        version.start()
        self.addCleanup(version.stop)
        self.integration = csp.embedded_module()
        self.body = (
            'window.records={"url":"https://bijux.io/bijux-pollenomics/reader/"};'
        )
        self.bootstrap = '{"asset":"records"}'
        payload = '{"records":[{"url":"https://bijux.io/bijux-pollenomics/reader/"}]}'
        envelope = {
            "asset_key": "records",
            "payload_encoding": "json",
            "payload_json": payload,
            "payload_sha256": digest(payload.encode()),
        }
        self.resource = (
            "globalThis.__RECORDS__=globalThis.__RECORDS__||[];globalThis.__RECORDS__.push("
            + json.dumps(envelope)
            + ");\n"
        ).encode()
        raw_report = (
            '<html><head><meta charset="utf-8"><link rel="icon" href="data:,"></head><body>'
            '<script id="owned-bootstrap" type="application/json">'
            + self.bootstrap
            + "</script>"
            '<script src="records.js"></script><script>'
            + self.body
            + "</script></body></html>"
        )
        self.write_source(
            "mkdocs.yml",
            "site_name: Source ownership fixture\nsite_url: " + BASE + "\n",
        )
        self.write_source(
            "producer/report.html",
            "<html><script>window.records=__DATA__;</script></html>",
        )
        self.write_source("docs/report/map.html", raw_report)
        self.write_source("docs/report/records.js", self.resource)
        parent_frame = (
            '<iframe src="../report/map.html" title="Owned records"></iframe>'
        )
        self.write_source("docs/reader.md", "# Reader\n\n" + parent_frame)
        self.parent_html = self.document(
            "<h1>Reader</h1>" + parent_frame, route="reader"
        )
        self.ordinary = self.document('<h1>Ordinary</h1><a href="reader/">Reader</a>')
        self.write_output("index.html", self.ordinary)
        self.write_output("reader/index.html", self.parent_html)
        self.write_output("report/map.html", raw_report)
        self.write_output("report/records.js", self.resource)
        self.write_source(".gitignore", "artifacts/\n")
        self.git("init", "--quiet")
        self.git("config", "user.name", "Bijux fixture")
        self.git("config", "user.email", "fixture@bijux.invalid")
        self.git(
            "add",
            ".gitignore",
            "mkdocs.yml",
            "producer/report.html",
            "docs/report/map.html",
            "docs/report/records.js",
            "docs/reader.md",
        )
        self.git(
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "fixture: own static report sources",
        )
        self.source_sha = self.git("rev-parse", "HEAD").strip()
        config = self.input_record("mkdocs.yml")
        resource_record = {
            "source": "docs/report/records.js",
            "sha256": digest(self.resource),
            "bytes": len(self.resource),
            "kind": "data-registration",
            "registration": {
                "variable": "__RECORDS__",
                "asset_key": "records",
                "payload_sha256": digest(payload.encode()),
                "decoded_bytes": len(payload.encode()),
                "maximum_decoded_bytes": 4096,
            },
        }
        self.owner = {
            "schema": "owned-embedded-reports.v1",
            "site_url": BASE,
            "config": config,
            "resolved_config_sha256": digest(b"literal resolved config"),
            "producer_inputs": [self.input_record("producer/report.html")],
            "reports": [
                {
                    "output": "report/map.html",
                    "source": self.input_record("docs/report/map.html"),
                    "resources": {"report/records.js": resource_record},
                    "reviewed_scripts": [digest(self.body.encode())],
                    "bootstrap_id": "owned-bootstrap",
                    "bootstrap_sha256": digest(
                        self.integration.canonical(json.loads(self.bootstrap))
                    ),
                    "recipe": {
                        "template": "producer/report.html",
                        "expansions": [],
                        "slots": {"__DATA__": {"kind": "json"}},
                    },
                    "providers": {},
                    "reviewed_provider_origins": [],
                    "provider_calls": [],
                }
            ],
            "parents": [
                {
                    "output": "reader/index.html",
                    "source": self.input_record("docs/reader.md"),
                    "reports": ["report/map.html"],
                    "built_html_sha256": digest(self.parent_html.encode()),
                }
            ],
        }
        self.descriptor = self.repo / "artifacts/descriptor.json"
        self.save_owner()
        self.build = {
            "schema": 1,
            "scope": "source-projection-compatibility",
            "verification_only": True,
            "state": "prepared",
            "site_url": BASE,
            "config": config,
            "resolved_config_sha256": self.owner["resolved_config_sha256"],
        }

    def git(self, *args):
        result = subprocess.run(
            ["git", "-C", str(self.repo), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def write_source(self, name, value):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else value.encode())

    def write_output(self, name, value):
        path = self.site / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else value.encode())

    def input_record(self, name):
        return {"path": name, "sha256": digest((self.repo / name).read_bytes())}

    def document(self, body, route=""):
        return (
            '<html><head><meta charset="utf-8"><link rel="canonical" href="'
            + BASE
            + (route + "/" if route else "")
            + '"></head><body>'
            + body
            + '<script id="__config" type="application/json">'
            + json.dumps({"base": ".." if route else "."})
            + "</script><script>"
            + TRUSTED
            + "</script></body></html>"
        )

    def save_owner(self):
        self.descriptor.write_text(json.dumps(self.owner))

    def identity(self):
        return self.integration.bundle_identity(self.site)[1]

    def plan(self):
        return self.integration.plan_embedded_reports(
            self.repo,
            self.site,
            self.descriptor,
            self.build,
            source_sha=self.source_sha,
        )

    def apply(self, plan=None):
        return csp.apply(
            self.site,
            self.shared,
            self.templates,
            embedded_plan=plan if plan is not None else self.plan(),
        )

    def complete(self):
        report = self.apply()
        build = self.build | {"state": "complete", "bundle_sha256": self.identity()}
        return report, build

    def verify(self, report, build):
        return publication.verify_embedded_candidate(
            self.repo,
            "artifacts/site",
            BASE,
            self.source_sha,
            publication.load_policy(),
            report,
            build,
            canonical_root=self.shared,
        )

    def static_reader(self, source=None):
        source = source or (
            '<!doctype html><html><head><meta charset="utf-8">'
            '<title>Unavailable evidence</title><style>p{line-height:1.6}</style>'
            '</head><body><main><h1>Unavailable evidence</h1>'
            '<p>No observations are available in this frozen report.</p></main></body></html>'
        )
        self.write_source("docs/report/map.html", source)
        self.write_output("report/map.html", source)
        self.git("add", "docs/report/map.html")
        if self.git("diff", "--cached", "--name-only", "--", "docs/report/map.html").strip():
            self.git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m",
                     "fixture: own non-executable reader source")
        self.source_sha = self.git("rev-parse", "HEAD").strip()
        self.owner["producer_inputs"] = []
        self.owner["reports"] = [{
            "report_class": "static-reader", "output": "report/map.html",
            "source": self.input_record("docs/report/map.html"), "resources": {},
            "reviewed_scripts": [], "providers": {}, "reviewed_provider_origins": [],
            "provider_calls": [],
        }]
        self.save_owner()
        return source

    def test_static_reader_composes_without_bootstrap_or_executable_authority(self):
        source = self.static_reader()
        report, build = self.complete()
        result = self.verify(report, build)
        self.assertTrue(result["verification_only"])
        record = next(r for r in result["embedded"]["records"] if r["kind"] == "owned-report")
        self.assertEqual(record["resources"], [])
        self.assertEqual(record["chunk_count"], 0)
        self.assertEqual(record["capability"]["script_sources"], ["'none'"])
        self.assertEqual(record["capability"]["script_hashes"], [])
        content = (self.site / "report/map.html").read_text()
        self.assertIn("script-src 'none'", content)
        self.assertIn("style-src 'unsafe-inline'", content)
        self.assertNotIn("__config", content)
        self.assertNotIn("<script", content)
        self.assertEqual(content.split("<body>", 1)[1], source.split("<body>", 1)[1])
        self.assertEqual((self.site / "report/records.js").read_bytes(), self.resource)

    def test_static_reader_rejects_fetching_css_before_any_output_write(self):
        styles = (
            "p{background:url(https://unreviewed.invalid/a)}",
            "@import 'https://unreviewed.invalid/style.css';p{color:white}",
            r"p{background:u\72l(https://unreviewed.invalid/a)}",
            "p{background:u/**/rl(https://unreviewed.invalid/a)}",
            "p{background:image-set('https://unreviewed.invalid/a' 1x)}",
            "@font-face{font-family:unreviewed;src:url(font.woff2)}",
            "p{--image:url(https://unreviewed.invalid/a);background:var(--image)}",
            "p{unknown-property:white}", "p{display:unknown-value}",
            "p{color:rgba(999,0,0,0.5)}", "p{color:rgba(1,2,3,2)}",
            "p{color:rgba(1,2,3)}", "p{border:1px unknown white}",
        )
        for style in styles:
            with self.subTest(style=style):
                source = '<html><head><meta charset="utf-8"><style>'+style+'</style></head><body><p>Evidence unavailable</p></body></html>'
                self.static_reader(source)
                before = (self.site / "report/map.html").read_bytes()
                with self.assertRaisesRegex(ValueError, "static reader"):
                    self.plan()
                self.assertEqual((self.site / "report/map.html").read_bytes(), before)
        for style in ("background:url(a.png)", r"background:u\72l(a.png)", "unknown:white"):
            with self.subTest(style_attribute=style):
                self.static_reader('<html><head><meta charset="utf-8"></head><body><p style="'+style+'">Unavailable</p></body></html>')
                with self.assertRaisesRegex(ValueError, "static reader"):
                    self.plan()

    def test_static_reader_rejects_resource_attributes_and_unsupported_metadata(self):
        markup = (
            '<body background="https://unreviewed.invalid/a">Unavailable</body>',
            '<p srcset="https://unreviewed.invalid/a 2x">Unavailable</p>',
            '<a href="reader/" ping="https://unreviewed.invalid/track">Reader</a>',
            '<link rel="stylesheet" href="https://unreviewed.invalid/style.css">',
            '<link rel="preconnect" href="https://unreviewed.invalid/">',
            '<img srcset="https://unreviewed.invalid/a 2x">',
            '<svg><image href="https://unreviewed.invalid/a"></image></svg>',
            '<p onclick="alert(1)">Unavailable</p>',
            '<meta http-equiv="refresh" content="0;url=https://unreviewed.invalid/">',
            '<meta http-equiv="Content-Security-Policy" content="default-src *">',
            '<meta name="unknown" content="unreviewed">',
            '<p unknown="unreviewed">Unavailable</p>',
            '<a href="javascript:alert(1)">Reader</a>',
            '<a href="reader/" target="unowned">Reader</a>',
        )
        for item in markup:
            with self.subTest(markup=item):
                self.static_reader('<html><head><meta charset="utf-8"></head><body>'+item+'</body></html>')
                with self.assertRaises(ValueError):
                    self.plan()

    def test_static_reader_none_fallbacks_are_independently_verified(self):
        for directive in ("default-src", "font-src", "media-src", "manifest-src", "frame-src", "base-uri", "form-action"):
            with self.subTest(directive=directive):
                self.static_reader()
                report, build = self.complete()
                result = self.verify(report, build)
                path = self.site / "report/map.html"
                content = path.read_bytes()
                self.assertIn((directive+" 'none'").encode(), content)
                path.write_bytes(content.replace((directive+" 'none'").encode(), (directive+" 'self'").encode()))
                changed = build | {"bundle_sha256": self.identity()}
                with self.assertRaisesRegex(ValueError, "exceeds reviewed capability"):
                    self.verify(report, changed)
                path.write_bytes(content)
                self.assertTrue(result["verification_only"])
                self.write_output("index.html", self.ordinary)
                self.write_output("reader/index.html", self.parent_html)

    def test_static_reader_external_style_authority_is_independently_rejected(self):
        self.static_reader()
        report, build = self.complete()
        path = self.site / "report/map.html"
        original = path.read_bytes()
        path.write_bytes(original.replace(b"style-src 'unsafe-inline'", b"style-src 'self' 'unsafe-inline'"))
        with self.assertRaisesRegex(ValueError, "exceeds reviewed capability"):
            self.verify(report, build | {"bundle_sha256": self.identity()})

    def test_static_reader_finite_inline_notice_styles_and_navigation_compose(self):
        source = ('<html lang="en"><head><meta charset="utf-8">'
                  '<meta name="viewport" content="width=device-width, initial-scale=1">'
                  '<style>body{margin:0;background:#f8fafc;font-family:ui-sans-serif, system-ui, sans-serif}'
                  'main{padding:2rem;box-shadow:0 20px 45px rgba(15, 23, 42, 0.08)}'
                  '.meta{font-size:0.95rem;color:#475569}</style></head><body><main>'
                  '<h1>Unavailable evidence</h1><p style="line-height:1.6;color:rgb(1,2,3)">'
                  'No observations are available.</p><a href="../reader/" title="Read documentation" target="_self">Reader</a>'
                  '</main></body></html>')
        self.static_reader(source)
        report, build = self.complete()
        result = self.verify(report, build)
        output = (self.site / "report/map.html").read_text()
        self.assertEqual(source.split("<body>",1)[1], output.split("<body>",1)[1])
        self.assertIn('href="../reader/"', output)
        self.assertTrue(result["verification_only"])

    def test_static_reader_requires_explicit_finite_class(self):
        self.static_reader()
        self.owner["reports"][0].pop("report_class")
        self.save_owner()
        with self.assertRaisesRegex(ValueError, "exactly one executable"):
            self.plan()
        self.owner["reports"][0]["report_class"] = "arbitrary-reader"
        self.save_owner()
        with self.assertRaisesRegex(ValueError, "unknown reviewed report class"):
            self.plan()

    def test_static_reader_rejects_all_script_kinds_even_reviewed_hashes(self):
        for script in ('<script>window.attack=true</script>',
                       '<script src="records.js"></script>',
                       '<script type="application/json" id="owned-bootstrap">{}</script>',
                       '<script type="application/ld+json">{}</script>',
                       '<script type="module">export default 1</script>'):
            with self.subTest(script=script):
                self.static_reader('<html><head><meta charset="utf-8"></head><body>'+script+'</body></html>')
                if 'window.attack' in script:
                    self.owner["reports"][0]["reviewed_scripts"] = [digest(b"window.attack=true")]
                    self.save_owner()
                before = self.identity()
                with self.assertRaisesRegex(ValueError, "cannot own scripts"):
                    self.plan()
                self.assertEqual(before, self.identity())

    def test_static_reader_rejects_recipe_bootstrap_and_foreign_descriptor_members(self):
        self.static_reader()
        for field, value in (("recipe", {"template": "producer/report.html"}),
                             ("bootstrap_id", "owned-bootstrap"),
                             ("bootstrap_sha256", digest(b"{}")),
                             ("accepted", True)):
            with self.subTest(field=field):
                self.owner["reports"][0][field] = value
                self.save_owner()
                with self.assertRaisesRegex(ValueError, "exact non-executable descriptor"):
                    self.plan()
                del self.owner["reports"][0][field]

    def test_static_reader_rejects_resource_and_provider_authority(self):
        self.static_reader()
        for field, value in (("resources", {"report/records.js": {
                "source": "docs/report/records.js", "sha256": digest(self.resource),
                "bytes": len(self.resource), "kind": "reviewed-script"}}),
                            ("providers", {"https://tracker.example.invalid": {}}),
                            ("reviewed_provider_origins", ["https://tracker.example.invalid"]),
                            ("provider_calls", [{"callee": "fetch"}])):
            with self.subTest(field=field):
                self.owner["reports"][0][field] = value
                self.save_owner()
                with self.assertRaisesRegex(ValueError, "cannot own scripts"):
                    self.plan()
                self.owner["reports"][0][field] = {} if field in ("resources", "providers") else []

    def test_static_reader_rejects_active_foreign_and_linked_resource_markup(self):
        for markup in ('<img src="local.png">', '<svg></svg>', '<math></math>',
                       '<video></video>', '<template></template>', '<button>Run</button>',
                       '<link rel="stylesheet" href="style.css">',
                       '<base href="https://tracker.example.invalid/">',
                       '<meta http-equiv="refresh" content="0;url=https://tracker.example.invalid/">',
                       '<p onclick="attack()">Read</p>'):
            with self.subTest(markup=markup):
                self.static_reader('<html><head><meta charset="utf-8"></head><body>'+markup+'</body></html>')
                with self.assertRaises(ValueError):
                    self.plan()

    def test_static_reader_forged_script_capability_rejects_before_any_write(self):
        self.static_reader()
        plan = self.plan()
        record = next(r for r in plan["records"] if r["kind"] == "owned-report")
        record["capability"]["script_sources"] = ["'self'"]
        record["capability_sha256"] = digest(self.integration.canonical(record["capability"]))
        before = self.identity()
        with self.assertRaisesRegex(ValueError, "independently rederived"):
            self.apply(plan)
        self.assertEqual(before, self.identity())

    def test_static_reader_script_policy_widening_rejects_rehashed_final_artifact(self):
        for widened in ("'self'", "'none' "+csp.hash_source(TRUSTED)):
            with self.subTest(widened=widened):
                self.static_reader()
                report, build = self.complete()
                path = self.site / "report/map.html"
                path.write_text(path.read_text().replace("script-src 'none'", "script-src "+widened))
                build["bundle_sha256"] = self.identity()
                with self.assertRaisesRegex(ValueError, "exceeds reviewed capability"):
                    self.verify(report, build)
                self.write_output("index.html", self.ordinary)
                self.write_output("reader/index.html", self.parent_html)

    def test_static_reader_uncommitted_source_cannot_rehash_into_old_commit(self):
        self.static_reader()
        self.write_source("docs/report/map.html", '<html><head><meta charset="utf-8"></head><body>Changed</body></html>')
        self.write_output("report/map.html", (self.repo / "docs/report/map.html").read_bytes())
        self.owner["reports"][0]["source"] = self.input_record("docs/report/map.html")
        self.save_owner()
        with self.assertRaisesRegex(ValueError, "differs from selected commit"):
            self.plan()

    def test_static_reader_mismatched_output_preserves_bundle_before_composition(self):
        self.static_reader()
        self.write_output("report/map.html", '<html><head><meta charset="utf-8"></head><body>Changed</body></html>')
        before = self.identity()
        with self.assertRaisesRegex(ValueError, "differs from reviewed tracked source"):
            self.apply()
        self.assertEqual(before, self.identity())

    def test_static_reader_reconstructed_receipt_cannot_claim_publication(self):
        self.static_reader()
        report, build = self.complete()
        with self.assertRaisesRegex(ValueError, "differs from selected commit|untracked"):
            self.integration.verify_composition(self.site, report, build | {"verification_only": False},
                publication=True, repository=self.repo, checkpoint={"accepted": True})

    def test_tracked_report_registration_parent_and_ordinary_composition_reconstructs(
        self,
    ):
        report, build = self.complete()
        result = self.verify(report, build)
        self.assertTrue(result["verification_only"])
        self.assertEqual(len(result["embedded"]["records"]), 2)
        self.assertEqual(
            sum(r.get("chunk_count", 0) for r in result["embedded"]["records"]), 1
        )
        self.assertIn(
            BASE + "report/map.html", (self.site / "reader/index.html").read_text()
        )
        self.assertEqual((self.site / "report/records.js").read_bytes(), self.resource)

    def test_late_unreviewed_ordinary_script_preserves_every_original_byte(self):
        self.write_output(
            "z-last.html", self.document("<script>window.attack=true</script>")
        )
        before = self.identity()
        with self.assertRaisesRegex(csp.PolicyError, "lacks exact"):
            self.apply()
        self.assertEqual(before, self.identity())

    def test_owned_report_executable_cannot_be_reused_on_an_ordinary_route(self):
        self.write_output(
            "z-last.html", self.document("<script>" + self.body + "</script>")
        )
        before = self.identity()
        with self.assertRaisesRegex(csp.PolicyError, "lacks exact"):
            self.apply()
        self.assertEqual(before, self.identity())

    def test_other_parent_cannot_embed_an_owned_report(self):
        self.write_output(
            "z-last.html",
            self.document('<iframe src="report/map.html" title="Other"></iframe>'),
        )
        before = self.identity()
        with self.assertRaisesRegex(csp.PolicyError, "source-owned parent"):
            self.apply()
        self.assertEqual(before, self.identity())

    def test_forged_capability_and_recomputed_digest_cannot_create_resource_authority(
        self,
    ):
        plan = self.plan()
        record = next(r for r in plan["records"] if r["kind"] == "owned-report")
        record["capability"]["image_sources"].append("https://tracker.example.invalid")
        record["capability_sha256"] = digest(
            self.integration.canonical(record["capability"])
        )
        before = self.identity()
        with self.assertRaisesRegex(csp.PolicyError, "independently rederived"):
            self.apply(plan)
        self.assertEqual(before, self.identity())

    def test_changed_tracked_producer_rejects_before_any_output_write(self):
        plan = self.plan()
        self.write_source("producer/report.html", "changed tracked producer")
        before = self.identity()
        with self.assertRaisesRegex(csp.PolicyError, "source fingerprint differs"):
            self.apply(plan)
        self.assertEqual(before, self.identity())

    def test_rehashed_uncommitted_producer_cannot_select_the_previous_source_commit(
        self,
    ):
        self.write_source(
            "producer/report.html",
            "<html><script>window.records=__DATA__;/*uncommitted*/</script></html>",
        )
        self.owner["producer_inputs"] = [self.input_record("producer/report.html")]
        self.save_owner()
        with self.assertRaisesRegex(ValueError, "differs from selected commit"):
            self.plan()

    def test_changed_resource_during_ordinary_preflight_preserves_all_html(self):
        plan = self.plan()
        before = {p: p.read_bytes() for p in self.site.rglob("*.html")}
        qualify = csp.qualify_html
        changed = False

        def mutate(*args, **kwargs):
            nonlocal changed
            if not changed:
                (self.site / "report/records.js").write_bytes(
                    self.resource + b"changed"
                )
                changed = True
            return qualify(*args, **kwargs)

        with (
            patch.object(csp, "qualify_html", side_effect=mutate),
            self.assertRaisesRegex(csp.PolicyError, "resources changed"),
        ):
            self.apply(plan)
        self.assertEqual(before, {p: p.read_bytes() for p in self.site.rglob("*.html")})

    def test_changed_processor_during_preflight_preserves_all_html(self):
        plan = self.plan()
        before = {p: p.read_bytes() for p in self.site.rglob("*.html")}
        original = self.integration.processor_inputs
        qualify = csp.qualify_html
        changed = False

        def mutate(*args, **kwargs):
            nonlocal changed
            changed = True
            return qualify(*args, **kwargs)

        def inputs():
            values = original()
            if changed:
                values[0]["sha256"] = "0" * 64
            return values

        with (
            patch.object(self.integration, "processor_inputs", side_effect=inputs),
            patch.object(csp, "qualify_html", side_effect=mutate),
            self.assertRaisesRegex(
                csp.PolicyError, "processor/source/config inputs changed"
            ),
        ):
            self.apply(plan)
        self.assertEqual(before, {p: p.read_bytes() for p in self.site.rglob("*.html")})

    def test_report_policy_widening_rejects_even_with_rehashed_final_bundle(self):
        report, build = self.complete()
        path = self.site / "report/map.html"
        path.write_text(
            path.read_text().replace(
                "img-src 'self'", "img-src https://tracker.example.invalid 'self'"
            )
        )
        build["bundle_sha256"] = self.identity()
        with self.assertRaisesRegex(ValueError, "exceeds reviewed capability"):
            self.verify(report, build)

    def test_owned_report_hash_cannot_be_laundered_into_ordinary_policy(self):
        report, build = self.complete()
        path = self.site / "index.html"
        path.write_text(
            path.read_text().replace(
                "script-src 'self'", "script-src 'self' " + csp.hash_source(self.body)
            )
        )
        build["bundle_sha256"] = self.identity()
        with self.assertRaisesRegex(ValueError, "another route|independently admitted"):
            self.verify(report, build)

    def test_changed_recipe_attribution_rejects_with_unchanged_served_bytes(self):
        report, build = self.complete()
        next(r for r in report["embedded"]["records"] if r["kind"] == "owned-report")[
            "recipe"
        ]["parameters_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "independently reviewed source"):
            self.verify(report, build)

    def test_empty_icon_exception_stays_exact_and_owned(self):
        html = '<html><head><link rel="icon" href="data:,"></head></html>'
        ordinary = publication.DocumentPolicy()
        ordinary.feed(html)
        self.assertIn("unadmitted data URL", ordinary.failures)
        owned = publication.DocumentPolicy(owned_report=True)
        owned.feed(html)
        self.assertFalse(owned.failures)
        malicious = publication.DocumentPolicy(owned_report=True)
        malicious.feed(
            html.replace("data:,", "data:text/html,<script>attack()</script>")
        )
        self.assertIn("unadmitted data URL", malicious.failures)

    def test_artifact_descriptor_and_projection_receipt_cannot_claim_publication(self):
        report, build = self.complete()
        with self.assertRaisesRegex(
            ValueError, "differs from selected commit|untracked"
        ):
            self.integration.verify_composition(
                self.site,
                report,
                build | {"verification_only": False},
                publication=True,
                repository=self.repo,
                checkpoint={"accepted": True},
            )

    def test_unsafe_data_url_rejects_at_actual_renderer_recipe_slot(self):
        body = self.body.replace(
            '"url":"https://bijux.io/bijux-pollenomics/reader/"',
            '"url":"javascript:window.attack=true"',
        )
        with self.assertRaisesRegex(ValueError, "unsafe data URL"):
            self.integration.reviewed_recipe(
                self.repo,
                body,
                self.owner["reports"][0]["recipe"],
                BASE,
                "report/map.html",
            )

    def test_unknown_executable_resource_cannot_hide_beside_the_owned_report(self):
        self.write_output("report/unowned.js", "window.unowned=true;")
        before = self.identity()
        with self.assertRaisesRegex(ValueError, "undeclared executable/style resource"):
            self.plan()
        self.assertEqual(before, self.identity())

    def test_altered_registration_wrapper_or_payload_cannot_reuse_its_ownership(self):
        spec = self.owner["reports"][0]["resources"]["report/records.js"][
            "registration"
        ]
        for changed in (
            self.resource + b"window.attack=true;",
            self.resource.replace(b'"payload_sha256":', b'"forged_payload":'),
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.integration.registration_data(
                    changed, spec, BASE, "report/map.html"
                )

    def test_forged_navigation_partition_cannot_survive_independent_restore(self):
        report, build = self.complete()
        record = next(
            r for r in report["embedded"]["navigation"] if r["path"] == "index.html"
        )
        record["changes"][0]["destination_partition"] = "ordinary"
        with self.assertRaisesRegex(ValueError, "route-derived attribution"):
            self.verify(report, build)


if __name__ == "__main__":
    unittest.main()
