from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bijux_docs_monitor", ROOT / "shared/bijux-docs/security/monitor.py")
assert spec and spec.loader
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class MonitorSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.responses = {}
        cls.requests = []
        cls.delays = {}
        cls.lengths = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                cls.requests.append(self.path)
                status, kind, data, headers = cls.responses.get(self.path, (404, "text/html", b"Missing", {}))
                self.send_response(status)
                self.send_header("Content-Type", kind)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(cls.lengths.get(self.path, len(data))))
                self.end_headers()
                time.sleep(cls.delays.get(self.path, 0))
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    # Deadline controls intentionally disconnect the synthetic server.
                    pass

            def log_message(self, *args):
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/bijux-core/"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.requests.clear()
        self.canonical = "https://bijux.io/bijux-core/"
        self.responses.clear()
        self.delays.clear()
        self.lengths.clear()
        for path in ("", "guide/"):
            body = f'<html><title>Core</title><link rel="canonical" href="{self.canonical}{path}"><a id="install" href="guide/">Guide</a></html>'.encode()
            self.responses["/bijux-core/" + path] = (200, "text/html", body, {"Cache-Control": "max-age=600"})
        corpus = {"docs": [{"location": "guide/#install", "title": "Install", "text": "Installation works"}]}
        self.responses["/bijux-core/search/search_index.json"] = (200, "application/json", json.dumps(corpus).encode(), {})
        self.responses["/bijux-core/assets/stylesheets/main.css"] = (200, "text/css", b"body{color:black}", {})

    def smoke(self, **extra):
        return monitor.smoke(self.url, canonical_root=self.canonical, deep_path="guide/", query="install", **extra)

    def test_complete_static_delivery_passes_with_five_bounded_requests(self):
        result = self.smoke()
        self.assertTrue(result["passed"])
        self.assertEqual(len(self.requests), 5)
        self.assertEqual(result["request_budget"], 5)
        self.assertIn("do not certify rendered menu", result["limitations"][0])

    def test_root_200_cannot_mask_missing_search(self):
        del self.responses["/bijux-core/search/search_index.json"]
        result = self.smoke()
        self.assertFalse(result["passed"])
        self.assertTrue(result["checks"][0]["passed"])
        self.assertFalse(next(c for c in result["checks"] if c["kind"] == "search-corpus")["passed"])

    def test_loopback_wrong_canonical_fails_real_document_contract(self):
        status, kind, body, headers = self.responses["/bijux-core/"]
        self.responses["/bijux-core/"] = (status, kind, body.replace(self.canonical.encode(), b"http://127.0.0.1:8000/"), headers)
        self.assertFalse(self.smoke()["passed"])

    def test_unknown_query_and_executable_search_destination_fail(self):
        self.responses["/bijux-core/search/search_index.json"] = (200, "application/json", b'{"docs":[{"location":"guide/","title":"Unrelated"}]}', {})
        self.assertFalse(self.smoke()["passed"])
        self.responses["/bijux-core/search/search_index.json"] = (200, "application/json", b'{"docs":[{"location":"javascript:alert(1)","title":"Install"}]}', {})
        self.assertFalse(self.smoke()["passed"])

    def test_asset_html_soft_404_and_missing_route_200_fail(self):
        self.responses["/bijux-core/assets/stylesheets/main.css"] = (200, "text/html", b"Missing asset", {})
        self.assertFalse(self.smoke()["passed"])
        self.responses["/bijux-core/assets/stylesheets/main.css"] = (200, "text/css", b"body{}", {})
        self.responses["/bijux-core/bijux-monitor-missing-destination/"] = (200, "text/html", b"Fallback", {})
        self.assertFalse(self.smoke()["passed"])

    def test_cross_origin_redirect_refused_before_second_request(self):
        self.responses["/bijux-core/"] = (302, "text/html", b"", {"Location": "https://foreign.invalid/private"})
        result = self.smoke()
        self.assertFalse(result["passed"])
        self.assertEqual(result["checks"][0]["error_type"], "ValueError")
        self.assertNotIn("private", json.dumps(result))

    def test_same_origin_redirect_hops_are_recorded(self):
        self.responses["/bijux-core/redirect/"] = (301, "text/html", b"", {"Location": self.url + "guide/"})
        result, body = monitor.request(self.url + "redirect/", live=False, timeout=5)
        self.assertTrue(result["passed"])
        self.assertEqual(result["redirects"][0]["status"], 301)
        self.assertEqual(result["final_url"], self.url + "guide/")

    def test_sensitive_targets_and_nonloopback_local_mode_rejected(self):
        for url in (self.url + "?token=private", "http://foreign.invalid/", "http://user:private@127.0.0.1/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                monitor.validate_target(url, False)
        with self.assertRaises(ValueError):
            monitor.validate_target("https://bijux.io.evil.invalid/", True)

    def test_paths_cannot_escape_product_or_include_query(self):
        for path in ("../private", "https://foreign.invalid/", "/other/", "guide/?token=private"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                monitor.smoke(self.url, canonical_root=self.canonical, deep_path=path)

    def test_query_never_retained_in_report(self):
        result = monitor.smoke(self.url, canonical_root=self.canonical, query="private-query-unique")
        self.assertFalse(result["passed"])
        self.assertNotIn("private-query-unique", json.dumps(result))
        self.assertNotIn("Installation works", json.dumps(result))

    def test_oversized_response_is_a_bounded_failure(self):
        old_budget = monitor.MAX_BYTES
        self.addCleanup(setattr, monitor, "MAX_BYTES", old_budget)
        monitor.MAX_BYTES = 10
        result, body = monitor.request(self.url, live=False, timeout=5)
        self.assertFalse(result["passed"])
        self.assertEqual(body, b"")

    def test_missing_known_destination_and_anchor_are_real_failures(self):
        self.responses["/bijux-core/search/search_index.json"] = (200, "application/json", b'{"docs":[{"location":"missing/","title":"Install","text":"Installation"}]}', {})
        result = self.smoke()
        self.assertFalse(result["passed"])
        self.assertIn("/bijux-core/missing/", self.requests)
        self.setUp()
        status, kind, body, headers = self.responses["/bijux-core/guide/"]
        self.responses["/bijux-core/guide/"] = (status, kind, body.replace(b'id="install"', b'id="another"'), headers)
        self.assertFalse(self.smoke()["passed"])

    def test_empty_asset_and_wrong_mime_html_payload_fail(self):
        for body in (b"", b"<!doctype html><html>Fallback</html>"):
            self.responses["/bijux-core/assets/stylesheets/main.css"] = (200, "text/css", body, {})
            self.assertFalse(self.smoke()["passed"])

    def test_critical_css_mime_and_declared_payload_length_are_enforced(self):
        path = "/bijux-core/assets/stylesheets/main.css"
        self.responses[path] = (200, "application/json", b"{}", {})
        self.assertFalse(self.smoke()["passed"])
        self.responses[path] = (200, "text/css", b"body{}", {})
        self.lengths[path] = 1000
        result = self.smoke()
        self.assertFalse(result["passed"])
        self.assertEqual(next(c for c in result["checks"] if c["kind"] == "critical-asset")["error_type"], "HTTPException")

    def test_corpus_requires_real_location_title_and_text_types(self):
        for entry in ({"location": 123}, {"location": "guide/", "title": "Install"}, {"location": "guide/", "title": "Install", "text": []}):
            self.responses["/bijux-core/search/search_index.json"] = (200, "application/json", json.dumps({"docs": [entry]}).encode(), {})
            self.assertFalse(self.smoke()["passed"])

    def test_known_query_and_declared_asset_are_required_before_requests(self):
        for values in ({"query": ""}, {"asset_path": ""}):
            with self.assertRaises(ValueError):
                monitor.smoke(self.url, canonical_root=self.canonical, **values)
        self.assertEqual(self.requests, [])

    def test_dot_encoded_and_backslash_paths_are_rejected_before_io(self):
        for path in ("../private/", "%2e%2e/private/", "%252e%252e/private/", "guide%2fprivate/", "guide\\private/", "guide//private/", "guide/./"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                monitor.smoke(self.url, canonical_root=self.canonical, deep_path=path, query="install")
        self.assertEqual(self.requests, [])

    def test_canonical_uses_existing_strict_production_identity(self):
        for canonical in ("https://user:fixture@bijux.io/bijux-core/", "https://bijux.io:443/bijux-core/", "https://bijux.io/bijux-core/?token=/", "https://bijux.io/bijux-core/../private/", "https://bijux.io/another-product/"):
            with self.subTest(canonical=canonical), self.assertRaises(ValueError):
                monitor.smoke(self.url, canonical_root=canonical, query="install")
        self.assertEqual(self.requests, [])

    def test_same_origin_cross_product_redirect_is_rejected_before_follow(self):
        self.responses["/bijux-core/assets/stylesheets/main.css"] = (302, "text/plain", b"", {"Location": "/other-product/main.css"})
        self.responses["/other-product/main.css"] = (200, "text/css", b"body{}", {})
        self.assertFalse(self.smoke()["passed"])
        self.assertNotIn("/other-product/main.css", self.requests)

    def test_explicit_product_boundary_cannot_be_a_prefix_or_sensitive_url(self):
        for boundary in (self.url.rstrip("/"), self.url + "?token=fixture"):
            with self.assertRaises(ValueError):
                monitor.request(self.url, live=False, timeout=2, product_root=boundary)
        self.assertEqual(self.requests, [])

    def test_redirect_body_and_aggregate_payload_budget_are_enforced(self):
        old = monitor.MAX_BYTES; self.addCleanup(setattr, monitor, "MAX_BYTES", old); monitor.MAX_BYTES = 32
        self.responses["/bijux-core/oversized/"] = (302, "text/plain", b"x" * 100000, {"Location": self.url + "tiny/"})
        self.responses["/bijux-core/tiny/"] = (200, "text/plain", b"ok", {})
        result, body = monitor.request(self.url + "oversized/", live=False, timeout=2, product_root=self.url)
        self.assertFalse(result["passed"]); self.assertEqual(body, b"")
        self.assertNotIn("/bijux-core/tiny/", self.requests)
        self.requests.clear()
        self.responses["/bijux-core/oversized/"] = (302, "text/plain", b"x" * 24, {"Location": self.url + "tiny/"})
        self.responses["/bijux-core/tiny/"] = (200, "text/plain", b"x" * 24, {})
        self.assertFalse(monitor.request(self.url + "oversized/", live=False, timeout=2, product_root=self.url)[0]["passed"])

    def test_redirect_hop_limit_and_unsafe_destination_do_not_continue(self):
        for index in range(5):
            self.responses[f"/bijux-core/hop-{index}/"] = (302, "text/plain", b"", {"Location": self.url + f"hop-{index + 1}/"})
        result, _ = monitor.request(self.url + "hop-0/", live=False, timeout=2, product_root=self.url)
        self.assertFalse(result["passed"]); self.assertEqual(len(self.requests), 4)
        self.requests.clear()
        self.responses["/bijux-core/hop-0/"] = (302, "text/plain", b"", {"Location": self.url + "guide/?secret=fixture"})
        result, _ = monitor.request(self.url + "hop-0/", live=False, timeout=2, product_root=self.url)
        self.assertFalse(result["passed"]); self.assertEqual(len(self.requests), 1)
        self.assertNotIn("secret", json.dumps(result))

    def test_slow_body_hits_actual_transport_deadline(self):
        self.delays["/bijux-core/guide/"] = 0.15
        result, body = monitor.request(self.url + "guide/", live=False, timeout=0.03, product_root=self.url)
        self.assertFalse(result["passed"]); self.assertEqual(result["error_type"], "TimeoutError"); self.assertEqual(body, b"")

    def test_proxy_environment_cannot_redirect_local_observation(self):
        with mock.patch.dict("os.environ", {"http_proxy": "http://127.0.0.1:1", "HTTP_PROXY": "http://127.0.0.1:1", "no_proxy": "", "NO_PROXY": ""}):
            self.assertTrue(self.smoke()["passed"])

    def test_response_policy_and_html_values_are_not_retained(self):
        status, kind, body, headers = self.responses["/bijux-core/"]
        self.responses["/bijux-core/"] = (status, kind, body + b'<meta http-equiv="Content-Security-Policy" content="private-fixture-value">', {"Content-Security-Policy": "private-fixture-value", "ETag": "private-fixture-value"})
        result = self.smoke(); self.assertTrue(result["passed"])
        self.assertNotIn("private-fixture-value", json.dumps(result))
        self.assertEqual(result["checks"][0]["meta_csp_count"], 1)

    def test_empty_root_location_and_encoded_unicode_anchor_are_valid(self):
        status, kind, body, headers = self.responses["/bijux-core/"]
        self.responses["/bijux-core/"] = (status, kind, body.replace(b'id="install"', 'id="α"'.encode()), headers)
        self.responses["/bijux-core/search/search_index.json"] = (200, "application/json", b'{"docs":[{"location":"#%CE%B1","title":"Install","text":"Installation"}]}', {})
        self.assertTrue(self.smoke()["passed"])

    def test_retained_manifest_matches_samples_and_rejects_changed_bytes(self):
        artifacts = ROOT / "artifacts/qualification/static-delivery/process"; artifacts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=artifacts) as location:
            repo = Path(location); site = repo / "artifacts/site"; site.mkdir(parents=True)
            for url, (_, _, data, _) in self.responses.items():
                path = url.removeprefix("/bijux-core/")
                file = site / (path + "index.html" if not path or path.endswith("/") else path)
                file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(data)
            publication = monitor.sibling_module("monitor_fixture_publication", ROOT / "shared/bijux-docs/security/publication.py")
            manifest = publication.bundle_manifest(repo, "artifacts/site", self.canonical, "a" * 40, publication.load_policy())
            path = Path("artifacts/retained-manifest.json"); (repo / path).write_text(json.dumps(manifest))
            result = self.smoke(manifest_path=path, repo_root=repo)
            self.assertTrue(result["passed"])
            self.assertEqual(result["artifact_binding"]["kind"], "retained_artifact_sample")
            status, kind, body, headers = self.responses["/bijux-core/assets/stylesheets/main.css"]
            self.responses["/bijux-core/assets/stylesheets/main.css"] = (status, kind, body + b"/* different publication */", headers)
            self.assertFalse(self.smoke(manifest_path=path, repo_root=repo)["passed"])
            (repo / "artifacts/site/index.html").write_text("changed retained bundle")
            with self.assertRaises(ValueError): self.smoke(manifest_path=path, repo_root=repo)


    @contextmanager
    def retained_fixture(self, schema=2):
        artifacts = ROOT / "artifacts/qualification/retained-monitor/process"
        artifacts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=artifacts) as location:
            repo = Path(location)
            site = repo / "artifacts/site"
            site.mkdir(parents=True)
            for url, (_, _, data, _) in self.responses.items():
                path = url.removeprefix("/bijux-core/")
                selected = site / (path + "index.html" if not path or path.endswith("/") else path)
                selected.parent.mkdir(parents=True, exist_ok=True)
                selected.write_bytes(data)
            identity = monitor.sibling_module("retained_monitor_identity", ROOT / "shared/bijux-docs/security/build_identity.py")
            publication = identity.publication()
            manifest = publication.bundle_manifest(repo, "artifacts/site", self.canonical, "a" * 40, publication.load_policy())
            if schema == 2:
                # Sampling cannot grant authority from unavailable historical assertions.
                manifest |= {"schema": 2, "qualification": {"source": {"path": "artifacts/absent.json"}},
                             "producer_authority": {"approved_profile": "untrusted historical assertion"}}
            path = Path("artifacts/retained-manifest.json")
            (repo / path).write_text(json.dumps(manifest))
            with mock.patch.object(monitor, "sibling_module", return_value=identity), mock.patch.object(identity, "publication", return_value=publication):
                yield repo, path, publication

    def test_schema_two_sampling_is_physical_only_without_source_or_producer(self):
        with self.retained_fixture() as (repo, path, publication):
            with mock.patch.object(publication, "qualified_manifest", side_effect=AssertionError("source reconstruction forbidden")) as qualified, mock.patch.object(publication, "verify_manifest", side_effect=AssertionError("strict qualification forbidden")) as strict, mock.patch.object(publication, "verify_retained_bytes", wraps=publication.verify_retained_bytes) as physical:
                result = self.smoke(manifest_path=path, repo_root=repo)
            self.assertTrue(result["passed"])
            self.assertEqual(len(self.requests), 5)
            self.assertEqual(physical.call_count, 2)
            qualified.assert_not_called()
            strict.assert_not_called()
            binding = result["artifact_binding"]
            self.assertEqual(binding["verification_mode"], "retained-public-bytes-only")
            self.assertFalse(binding["qualified_source_verified"])
            self.assertFalse(binding["publication_approval"])
            self.assertNotIn("approved_profile", json.dumps(result))

    def test_schema_one_sampling_preserves_mechanical_admission(self):
        with self.retained_fixture(schema=1) as (repo, path, publication):
            with mock.patch.object(publication, "verify_manifest", wraps=publication.verify_manifest) as mechanical, mock.patch.object(publication, "verify_retained_bytes", side_effect=AssertionError("schema one admission lost")):
                result = self.smoke(manifest_path=path, repo_root=repo)
            self.assertTrue(result["passed"])
            self.assertEqual(mechanical.call_count, 2)
            self.assertEqual(result["artifact_binding"]["verification_mode"], "mechanical-bundle")
            self.assertFalse(result["artifact_binding"]["publication_approval"])

    def test_schema_two_sampling_rejects_retained_file_change_after_requests(self):
        with self.retained_fixture() as (repo, path, _):
            original = monitor.request
            def changing_request(*args, **kwargs):
                response = original(*args, **kwargs)
                (repo / "artifacts/site/index.html").write_text("changed physical artifact")
                return response
            with mock.patch.object(monitor, "request", side_effect=changing_request):
                with self.assertRaisesRegex(ValueError, "physical inventory differs"):
                    self.smoke(manifest_path=path, repo_root=repo)
            self.assertEqual(len(self.requests), 5)

    def test_schema_two_sampling_rejects_selected_manifest_change_after_requests(self):
        with self.retained_fixture() as (repo, path, _):
            original = monitor.request
            def changing_request(*args, **kwargs):
                response = original(*args, **kwargs)
                manifest = json.loads((repo / path).read_text())
                manifest["producer_authority"] = {"approved_profile": "changed declaration"}
                (repo / path).write_text(json.dumps(manifest))
                return response
            with mock.patch.object(monitor, "request", side_effect=changing_request):
                with self.assertRaisesRegex(ValueError, "retained manifest changed"):
                    self.smoke(manifest_path=path, repo_root=repo)
            self.assertEqual(len(self.requests), 5)


if __name__ == "__main__":
    unittest.main()
