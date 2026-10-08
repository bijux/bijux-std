"""Keep native workers page-relative and indexes confined to product mounts."""
import importlib.util
from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
