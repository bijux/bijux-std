"""Source-owned standalone discovery without fabricating a Material report shell."""

from pathlib import Path
import gzip
import importlib.util
import json
import os
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "bijux_standalone_composition_fixtures",
    ROOT / "tests/test_docs_embedded_reports.py",
)
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
sys.path.insert(0, str(ROOT / "shared/bijux-docs/tooling/quality"))
from validate_site_routes import qualify


class StandaloneReaderTests(unittest.TestCase):
    def setUp(self):
        os.environ["BIJUX_EMBEDDED_TEST_ARTIFACTS_ROOT"] = str(
            ROOT / "artifacts/standalone-reader-controls"
        )
        self.case = fixtures.EmbeddedReportCompositionTests()
        self.case._testMethodName = (
            "test_static_reader_composes_without_bootstrap_or_executable_authority"
        )
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        c = self.case
        c.static_reader()
        for name in ("index.html", "reader/index.html"):
            content = (
                (c.site / name)
                .read_text()
                .replace(
                    '"base":',
                    '"search": "'
                    + ("../" if name.startswith("reader/") else "")
                    + 'assets/search.js", "base":',
                )
            )
            content = content.replace(
                "<body>",
                '<body><input data-md-component="search-query" aria-label="Search documentation">',
                1,
            )
            c.write_output(name, content)
            if name.startswith("reader/"):
                c.parent_html = content
                c.owner["parents"][0]["built_html_sha256"] = fixtures.digest(
                    content.encode()
                )
        c.write_output("assets/search.js", "self.onmessage=()=>{};")
        c.write_output(
            "search/search_index.json",
            json.dumps(
                {
                    "docs": [
                        {
                            "location": "reader/",
                            "title": "Sweden lake evidence",
                            "text": "Sweden unavailable-data notice and reader documentation",
                        }
                    ]
                }
            ),
        )
        c.write_output(
            "sitemap.xml",
            "<urlset><url><loc>"
            + fixtures.BASE
            + "</loc></url><url><loc>"
            + fixtures.BASE
            + "reader/</loc></url></urlset>",
        )
        c.site.joinpath("sitemap.xml.gz").write_bytes(
            gzip.compress(c.site.joinpath("sitemap.xml").read_bytes(), mtime=0)
        )
        self.purpose = {
            "schema": 1,
            "readers": [
                {
                    "output": "report/map.html",
                    "title": "Sweden lake evidence richness",
                    "purpose": "Read the frozen unavailable-data notice and its documentation limitations.",
                    "return_route": "reader/index.html",
                    "search_route": "index.html",
                    "query": "Sweden",
                }
            ],
        }
        c.write_source("docs/report/readers.json", json.dumps(self.purpose))
        c.git("add", "docs/report/readers.json")
        c.git(
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "fixture: own frozen reader discovery purpose",
        )
        c.source_sha = c.git("rev-parse", "HEAD").strip()
        c.owner["reader_purpose"] = c.input_record("docs/report/readers.json")
        c.save_owner()

    def evidence(self, report, build):
        return {
            "csp": report,
            "completed_build": build,
            "source_sha": self.case.source_sha,
        }

    def test_source_owned_reader_return_search_sitemap_and_csp_compose(self):
        c = self.case
        original = (c.site / "report/map.html").read_text()
        report, build = c.complete()
        result = c.verify(report, build)
        output = (c.site / "report/map.html").read_text()
        self.assertIn("Return to documentation", output)
        self.assertIn("Search documentation", output)
        self.assertIn('href="../?q=Sweden"', output)
        self.assertNotIn("__config", output)
        import importlib

        reader = importlib.import_module(c.integration.__package__ + ".reader")
        restored = reader.restore(output, "report/map.html", self.purpose["readers"][0])
        self.assertEqual(restored.split("<body>", 1)[1], original.split("<body>", 1)[1])
        self.assertEqual(
            gzip.decompress((c.site / "sitemap.xml.gz").read_bytes()),
            (c.site / "sitemap.xml").read_bytes(),
        )
        self.assertIn(
            fixtures.BASE + "report/map.html", (c.site / "sitemap.xml").read_text()
        )
        indexed = json.loads((c.site / "search/search_index.json").read_text())["docs"]
        self.assertEqual(
            [e for e in indexed if e["location"] == "report/map.html"],
            [
                {
                    "location": "report/map.html",
                    "title": self.purpose["readers"][0]["title"],
                    "text": self.purpose["readers"][0]["purpose"],
                }
            ],
        )
        routes = qualify(
            c.site, fixtures.BASE, [], embedded_evidence=self.evidence(report, build)
        )
        self.assertEqual(routes["errors"], [])
        self.assertEqual(set(routes["standalone_readers"]), {"report/map.html"})
        self.assertTrue(result["verification_only"])

    def test_native_documentation_filenames_preserve_exact_reader_destinations(self):
        c = self.case
        import importlib
        from urllib.parse import urljoin

        reader = importlib.import_module(c.integration.__package__ + ".reader")
        root_html = (c.site / "index.html").read_text()
        for destination in (
            "index.html",
            "reader/index.html",
            "guideindex.html",
            "guide.html",
        ):
            with self.subTest(destination=destination):
                if destination not in ("index.html", "reader/index.html"):
                    c.write_output(destination, root_html)
                reader._target(c.site, fixtures.BASE, destination)
                actual = urljoin(
                    fixtures.BASE + "report/map.html",
                    reader._href("report/map.html", destination),
                )
                self.assertEqual(actual, reader._route(fixtures.BASE, destination))

    def test_unverified_report_still_requires_material_search(self):
        c = self.case
        report, build = c.complete()
        routes = qualify(c.site, fixtures.BASE, [])
        self.assertTrue(
            any(
                "report/map.html: native search configuration" in e
                for e in routes["errors"]
            )
        )

    def test_reader_documentation_target_needs_real_delivered_native_controls(self):
        c = self.case
        root = (c.site / "index.html").read_bytes()
        for replacement in (
            root.replace(b'data-md-component="search-query"', b'data-unowned="query"'),
            root.replace(
                b'"search": "assets/search.js"', b'"search": "assets/missing.js"'
            ),
        ):
            with self.subTest(replacement=replacement):
                (c.site / "index.html").write_bytes(replacement)
                with self.assertRaises(ValueError):
                    c.plan()
        (c.site / "index.html").write_bytes(root)

    def test_reader_site_identity_cannot_be_rewritten_in_retained_evidence(self):
        c = self.case
        report, build = c.complete()
        report["embedded"]["site_url"] = "https://foreign.invalid/"
        with self.assertRaisesRegex(ValueError, "site identity differs"):
            qualify(
                c.site,
                fixtures.BASE,
                [],
                embedded_evidence=self.evidence(report, build),
            )

    def test_wrong_source_identity_cannot_supply_standalone_exemption(self):
        c = self.case
        report, build = c.complete()
        evidence = self.evidence(report, build)
        evidence["source_sha"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "identity differs"):
            qualify(c.site, fixtures.BASE, [], embedded_evidence=evidence)

    def test_unknown_or_dead_documentation_purpose_rejects_before_write(self):
        c = self.case
        for key, value in [
            ("output", "unowned.html"),
            ("return_route", "missing/index.html"),
            ("search_route", "report/map.html"),
            ("query", "UnmatchedUnknownTerm"),
            ("return_route", "https://foreign.invalid/"),
            ("search_route", "../index.html"),
        ]:
            with self.subTest(key=key):
                changed = json.loads(json.dumps(self.purpose))
                changed["readers"][0][key] = value
                c.write_source("docs/report/readers.json", json.dumps(changed))
                c.git("add", "docs/report/readers.json")
                c.git(
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "--quiet",
                    "-m",
                    "fixture: retain rejected reader purpose",
                )
                c.source_sha = c.git("rev-parse", "HEAD").strip()
                c.owner["reader_purpose"] = c.input_record("docs/report/readers.json")
                c.save_owner()
                before = c.identity()
                with self.assertRaises(ValueError):
                    c.plan()
                self.assertEqual(before, c.identity())

    def test_mutated_report_or_purpose_cannot_rehash_into_committed_source(self):
        c = self.case
        c.write_source(
            "docs/report/readers.json",
            json.dumps(self.purpose).replace("Sweden", "Unreviewed"),
        )
        c.owner["reader_purpose"] = c.input_record("docs/report/readers.json")
        c.save_owner()
        with self.assertRaisesRegex(ValueError, "differs from selected commit"):
            c.plan()

    def test_fake_material_report_configuration_is_rejected(self):
        c = self.case
        c.static_reader(
            '<html><head><meta charset="utf-8"></head><body><script id="__config" type="application/json">{"search":"../assets/search.js"}</script>Unavailable</body></html>'
        )
        with self.assertRaisesRegex(ValueError, "cannot own scripts"):
            c.plan()

    def test_unrelated_route_cannot_gain_standalone_search_exemption(self):
        c = self.case
        c.write_output(
            "unknown.html",
            '<html><head><meta charset="utf-8"><link rel="canonical" href="'
            + fixtures.BASE
            + 'unknown.html"></head><body>Unknown</body></html>',
        )
        with self.assertRaisesRegex(ValueError, "coverage differs"):
            c.plan()

    def test_omitted_extra_foreign_duplicate_or_different_gzip_sitemap_rejects(self):
        c = self.case
        original = (c.site / "sitemap.xml").read_bytes()
        compressed = (c.site / "sitemap.xml.gz").read_bytes()
        mutations = [
            original.replace(
                (fixtures.BASE + "reader/").encode(),
                (fixtures.BASE + "missing/").encode(),
            ),
            original.replace(
                b"</urlset>", b"<url><loc>https://foreign.invalid/</loc></url></urlset>"
            ),
            original.replace(
                b"</urlset>",
                b"<url><loc>" + fixtures.BASE.encode() + b"</loc></url></urlset>",
            ),
        ]
        for raw in mutations:
            with self.subTest(raw=raw):
                c.site.joinpath("sitemap.xml").write_bytes(raw)
                c.site.joinpath("sitemap.xml.gz").write_bytes(
                    gzip.compress(raw, mtime=0)
                )
                with self.assertRaises(ValueError):
                    c.plan()
        c.site.joinpath("sitemap.xml").write_bytes(original)
        c.site.joinpath("sitemap.xml.gz").write_bytes(b"not gzip")
        with self.assertRaisesRegex(ValueError, "gzip"):
            c.plan()
        c.site.joinpath("sitemap.xml.gz").write_bytes(compressed)

    def test_valid_gzip_with_unexpected_large_payload_is_not_equivalent(self):
        c = self.case
        (c.site / "sitemap.xml.gz").write_bytes(gzip.compress(b"x" * 1000000, mtime=0))
        with self.assertRaisesRegex(ValueError, "gzip differs"):
            c.plan()

    def test_changed_sitemap_after_preflight_preserves_all_html(self):
        c = self.case
        plan = c.plan()
        c.site.joinpath("sitemap.xml").write_text("<urlset/>")
        before = c.site.joinpath("report/map.html").read_bytes()
        with self.assertRaisesRegex(ValueError, "changed after source planning"):
            c.apply(plan)
        self.assertEqual(before, c.site.joinpath("report/map.html").read_bytes())

    def test_final_dead_reader_link_or_canonical_sitemap_change_rejects_rehashed_bundle(
        self,
    ):
        c = self.case
        report, build = c.complete()
        original = {
            name: (c.site / name).read_bytes()
            for name in (
                "report/map.html",
                "sitemap.xml",
                "sitemap.xml.gz",
                "search/search_index.json",
            )
        }
        for name, raw in [
            (
                "report/map.html",
                original["report/map.html"].replace(b"../reader/", b"../missing/"),
            ),
            (
                "report/map.html",
                original["report/map.html"].replace(
                    (fixtures.BASE + "report/map.html").encode(), fixtures.BASE.encode()
                ),
            ),
            ("sitemap.xml", b"<urlset/>"),
            ("sitemap.xml.gz", gzip.compress(b"<urlset/>", mtime=0)),
            ("search/search_index.json", b'{"docs":[]}'),
        ]:
            with self.subTest(path=name):
                (c.site / name).write_bytes(raw)
                with self.assertRaises(ValueError):
                    qualify(
                        c.site,
                        fixtures.BASE,
                        [],
                        embedded_evidence=self.evidence(
                            report, build | {"bundle_sha256": c.identity()}
                        ),
                    )
                (c.site / name).write_bytes(original[name])


if __name__ == "__main__":
    unittest.main()
