"""Keep native workers page-relative and indexes confined to product mounts."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bijux_producer_routes", ROOT / "shared/bijux-docs/security/producer_authority.py")
producer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(producer)
WORKER = "assets/javascripts/workers/search.2c215733.min.js"


class NativeRouteTests(unittest.TestCase):
    def test_hub_and_product_deep_paths_follow_actual_material_url_semantics(self):
        for mount in ("https://bijux.io/", "https://bijux.io/bijux-atlas/"):
            for depth in range(4):
                route = "guide/" * depth
                config = {"base": "/".join([".."] * depth) or ".", "search": "../" * depth + WORKER}
                with self.subTest(mount=mount, depth=depth):
                    self.assertEqual(producer.native_resources(config, mount + route + "index.html", mount), (WORKER, "search/search_index.json"))
    def test_worker_cannot_ascend_outside_product_mount(self):
        with self.assertRaises(producer.ProducerError):
            producer.native_resources({"base": "..", "search": "../../" + WORKER}, "https://bijux.io/bijux-atlas/guide/index.html", "https://bijux.io/bijux-atlas/")
    def test_index_cannot_ascend_outside_product_mount(self):
        with self.assertRaises(producer.ProducerError):
            producer.native_resources({"base": "../..", "search": "../" + WORKER}, "https://bijux.io/bijux-atlas/guide/index.html", "https://bijux.io/bijux-atlas/")
    def test_foreign_worker_origin_and_malformed_resource_remain_rejected(self):
        for worker in ("https://foreign.invalid/search.js", "//foreign.invalid/search.js", "../%2e%2e/search.js", "../assets/search.js?foreign=1", "../assets/search.js#fragment", "", None):
            with self.subTest(worker=worker), self.assertRaises(producer.ProducerError):
                producer.native_resources({"base": "..", "search": worker}, "https://bijux.io/bijux-atlas/guide/index.html", "https://bijux.io/bijux-atlas/")
    def test_foreign_or_nonstring_index_base_remains_rejected(self):
        for base in ("https://foreign.invalid/", None, [], "../../outside"):
            with self.subTest(base=base), self.assertRaises(producer.ProducerError):
                producer.native_resources({"base": base, "search": "../" + WORKER}, "https://bijux.io/bijux-atlas/guide/index.html", "https://bijux.io/bijux-atlas/")


class NativeReferenceEqualityTests(unittest.TestCase):
    def test_changed_html_body_cannot_borrow_identical_native_references(self):
        artifacts = ROOT / 'artifacts/publication-producer-routes'
        artifacts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=artifacts) as directory:
            site = Path(directory) / 'site'
            site.mkdir()
            config = json.dumps({'base': '.', 'search': WORKER})
            original = ('<html><body>Owned article<script src="' + WORKER + '"></script>'
                        '<script id="__config" type="application/json">' + config + '</script></body></html>').encode()
            changed = original.replace(b'Owned article', b'Changed article')
            before, after = producer.References(), producer.References()
            before.feed(original.decode())
            after.feed(changed.decode())
            self.assertEqual((before.external, before.configs), (after.external, after.configs))
            (site / 'index.html').write_bytes(changed)
            worker = site / WORKER
            worker.parent.mkdir(parents=True)
            worker.write_bytes(b'owned worker')
            index = site / 'search/search_index.json'
            index.parent.mkdir()
            index.write_bytes(b'{"docs": []}')
            reference = producer.files(site)
            reference['index.html'] = original
            prepared = producer.PreparedProducer(
                Path(directory), 'mkdocs.yml', ROOT / 'shared/bijux-docs', site, site,
                {}, {}, reference, {}, {}, '', {}, {}, False)
            prepared.reader_source = None
            modules = {
                'script_authority.py': SimpleNamespace(verify_ordinary=lambda *args, **kwargs: {}),
                'producer_capabilities.py': SimpleNamespace(verify_outputs=lambda *args: None),
                'publication.py': SimpleNamespace(qualified_redirects=lambda *args: {}),
            }
            # Isolate the exact-byte guard; renderer and callback admission have
            # separate existing controls and are not qualified by this fixture.
            with patch.object(producer.PreparedProducer, 'unchanged'), \
                    patch.object(producer, 'module', side_effect=lambda path: modules[path.name]):
                with self.assertRaisesRegex(producer.ProducerError, 'public resource bytes differ.*index.html'):
                    producer.verify(site, prepared, {}, {}, 'https://bijux.io/bijux-atlas/')


if __name__ == "__main__":
    unittest.main()
