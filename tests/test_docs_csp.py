from __future__ import annotations
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bijux_csp", ROOT / "shared/bijux-docs/security/csp.py")
csp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csp)


class StaticPolicyTests(unittest.TestCase):
    def html(self, body="window.bijuxTrusted = true;"):
        return '<!doctype html><html><head><meta charset="utf-8"><script>' + body + '</script></head><body></body></html>'

    def test_policy_precedes_scripts_and_hashes_exact_admitted_bytes(self):
        body = "window.bijuxTrusted = true;"
        html, hashes = csp.qualify_html(self.html(body), {body}, "")
        self.assertLess(html.index('http-equiv="Content-Security-Policy"'), html.index('<script>'))
        self.assertEqual(hashes, [csp.hash_source(body)])
        self.assertIn("script-src-attr 'none'", html)
        self.assertNotIn("unsafe-eval", html)

    def test_same_origin_prefetch_retains_explicit_resource_boundaries(self):
        html, _ = csp.qualify_html(self.html(), {"window.bijuxTrusted = true;"}, "")
        self.assertIn("default-src 'self'", html)
        for directive in ("object-src 'none'", "frame-src 'none'", "script-src-attr 'none'",
                          "connect-src 'self'", "font-src 'self'", "media-src 'self'",
                          "manifest-src 'self'", "worker-src 'self' blob:"):
            self.assertIn(directive, html)

    def test_arbitrary_inline_code_cannot_launder_its_hash(self):
        with self.assertRaisesRegex(csp.PolicyError, "lacks exact"):
            csp.qualify_html(self.html("window.unreviewed = true;"), {"window.bijuxTrusted = true;"}, "")

    def test_json_data_is_not_treated_as_executable_admission(self):
        html = self.html().replace('<script>', '<script type="application/json">').replace('window.bijuxTrusted = true;', '{"name":"Bijux"}')
        _, hashes = csp.qualify_html(html, set(), "")
        self.assertEqual(hashes, [])

    def test_duplicate_script_attribute_and_existing_policy_are_rejected(self):
        for html in (self.html().replace('<script>', '<script type="application/json" type="text/javascript">'),
                     self.html().replace('<script>', '<meta http-equiv="Content-Security-Policy" content="old"><script>')):
            with self.subTest(html=html), self.assertRaises(csp.PolicyError):
                csp.qualify_html(html, {"window.bijuxTrusted = true;"}, "")

    def test_scope_variants_are_exact_and_local(self):
        source = 'var __md_scope = new URL("../..", location);\nwindow.bijuxTrusted = true;'
        normalized = 'var __md_scope = BIJUX_REVIEWED_SCOPE;\nwindow.bijuxTrusted = true;'
        csp.qualify_html(self.html(source), set(), normalized)
        with self.assertRaises(csp.PolicyError):
            csp.qualify_html(self.html(source.replace('../..', 'https://foreign.invalid/')), set(), normalized)
        with self.assertRaises(csp.PolicyError):
            csp.qualify_html(self.html(source + 'window.payload=1;'), set(), normalized)

    def test_charset_after_script_is_not_early_enforcement(self):
        html = self.html().replace('<meta charset="utf-8">', '').replace('</head>', '<meta charset="utf-8"></head>')
        with self.assertRaisesRegex(csp.PolicyError, "precede"):
            csp.qualify_html(html, {"window.bijuxTrusted = true;"}, "")

    def redirect(self, site):
        import hashlib, json
        from html import escape
        spec = importlib.util.spec_from_file_location("bijux_csp_test_redirect", ROOT / "shared/bijux-docs/security/redirects.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        target = "https://bijux.io/bijux-core/target/"
        script = module.SCRIPT.format(target=json.dumps(target, ensure_ascii=True))
        normalized = module.TEMPLATE.format(canonical=escape(target, quote=True), target=escape(target, quote=True), script=script)
        old = site / "old.html"
        old.write_text('<html><head><meta charset="utf-8"></head><body>Original redirect</body></html>')
        record = {"path": "old.html", "target": target, "canonical": target, "script": script,
                  "normalized_html": normalized, "input_sha256": hashlib.sha256(old.read_bytes()).hexdigest(),
                  "normalized_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
                  "script_sha256": hashlib.sha256(script.encode()).hexdigest(), "csp_hash": csp.hash_source(script)}
        return {"schema": 1, "policy": "exact-declared-redirects", "applied": False,
                "policy_inputs": {"processor_sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()},
                "records": [record]}

    def exercise_redirect(self, operation):
        from unittest.mock import patch
        parent = ROOT / "artifacts/website-security/csp-tests"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            site = Path(directory)
            plan = self.redirect(site)
            with patch.object(csp, "admitted_scripts", return_value=({"window.bijuxTrusted = true;"}, "")):
                operation(site, plan)

    def test_normalized_redirect_gets_early_route_specific_policy(self):
        def operation(site, plan):
            report = csp.apply(site, site, site, plan)
            html = (site / "old.html").read_text()
            self.assertLess(html.index('http-equiv="Content-Security-Policy"'), html.index('<script>'))
            self.assertIn("window.location.replace", html)
            self.assertEqual(report["script_hashes"], [plan["records"][0]["csp_hash"]])
            self.assertTrue(report["redirects"]["applied"])
            self.assertNotIn("normalized_html", report["redirects"]["records"][0])
        self.exercise_redirect(operation)

    def test_valid_redirect_and_late_unadmitted_page_leave_all_bytes_intact(self):
        def operation(site, plan):
            (site / "z.html").write_text(self.html("window.unreviewed=1;"))
            before = {p: p.read_bytes() for p in site.iterdir()}
            with self.assertRaises(csp.PolicyError):
                csp.apply(site, site, site, plan)
            self.assertEqual(before, {p: p.read_bytes() for p in site.iterdir()})
        self.exercise_redirect(operation)

    def test_redirect_script_is_not_admitted_on_an_ordinary_page(self):
        def operation(site, plan):
            (site / "z.html").write_text(self.html(plan["records"][0]["script"]))
            before = {p: p.read_bytes() for p in site.iterdir()}
            with self.assertRaisesRegex(csp.PolicyError, "lacks exact"):
                csp.apply(site, site, site, plan)
            self.assertEqual(before, {p: p.read_bytes() for p in site.iterdir()})
        self.exercise_redirect(operation)

    def test_changed_redirect_and_missing_route_are_rejected_before_any_write(self):
        def operation(site, plan):
            path = site / "old.html"
            path.write_text(path.read_text() + "changed")
            before = path.read_bytes()
            with self.assertRaisesRegex(csp.PolicyError, "changed after"):
                csp.apply(site, site, site, plan)
            self.assertEqual(before, path.read_bytes())
            path.unlink()
            (site / "index.html").write_text(self.html())
            before = (site / "index.html").read_bytes()
            with self.assertRaisesRegex(csp.PolicyError, "missing"):
                csp.apply(site, site, site, plan)
            self.assertEqual(before, (site / "index.html").read_bytes())
        self.exercise_redirect(operation)

    def test_self_consistent_unreviewed_redirect_script_cannot_launder_admission(self):
        def operation(site, plan):
            import hashlib
            record = plan["records"][0]
            record["script"] += "window.unreviewed=1;"
            record["script_sha256"] = hashlib.sha256(record["script"].encode()).hexdigest()
            record["csp_hash"] = csp.hash_source(record["script"])
            before = (site / "old.html").read_bytes()
            with self.assertRaisesRegex(csp.PolicyError, "canonical route template"):
                csp.apply(site, site, site, plan)
            self.assertEqual(before, (site / "old.html").read_bytes())
        self.exercise_redirect(operation)

    def test_late_rejection_preserves_every_page(self):
        from unittest.mock import patch
        parent = ROOT / "artifacts/website-security/csp-tests"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            site = Path(directory)
            first, late = site / "index.html", site / "late.html"
            first.write_text(self.html())
            late.write_text(self.html("window.unreviewed=1;"))
            before = {p: p.read_bytes() for p in site.iterdir()}
            with patch.object(csp, "admitted_scripts", return_value=({"window.bijuxTrusted = true;"}, "")):
                with self.assertRaises(csp.PolicyError):
                    csp.apply(site, site, site)
            self.assertEqual(before, {p: p.read_bytes() for p in site.iterdir()})


if __name__ == "__main__":
    unittest.main()
