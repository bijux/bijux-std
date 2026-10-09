from pathlib import Path
import importlib
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / "shared/bijux-docs/security"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


csp = load("bijux_search_boundary_csp", SECURITY / "csp.py")
publication = load("bijux_search_boundary_publication", SECURITY / "publication.py")
integration = csp.embedded_module()
nav = importlib.import_module(integration.__package__ + ".navigation")
BASE = "https://bijux.io/bijux-pollenomics/"


class SourceMetadata(unittest.TestCase):
    def setUp(self):
        self.ownership = {"public/nordic-atlas/index.html": "a" * 64}
        self.html = '<html><head><meta charset="utf-8"></head><body><a href="public/nordic-atlas/?h=term#reader">report</a><script id="__config" type="application/json">{}</script></body></html>'

    def test_metadata_and_static_target_share_the_same_verified_partition(self):
        record = nav.normalize(self.html, "index.html", BASE, self.ownership)
        self.assertEqual(record["metadata"]["document_partition"], "ordinary")
        self.assertEqual(
            record["metadata"]["route_partitions"],
            [["public/nordic-atlas/index.html", "a" * 64]],
        )
        self.assertIn('target="_self"', record["normalized_html"])
        self.assertEqual(
            nav.restore(
                record["normalized_html"],
                {k: v for k, v in record.items() if k != "normalized_html"},
                BASE,
                self.ownership,
            ),
            self.html,
        )

    def test_own_parent_metadata_declares_exact_initial_policy(self):
        record = nav.normalize(
            self.html, "public/nordic-atlas/index.html", BASE, self.ownership
        )
        self.assertEqual(record["metadata"]["document_partition"], "a" * 64)

    def test_forged_table_hash_and_shape_cannot_supply_source_ownership(self):
        record = nav.normalize(self.html, "index.html", BASE, self.ownership)
        record["metadata"]["route_partitions"].append(["index.html", "a" * 64])
        record["metadata"]["table_sha256"] = integration.digest(
            integration.canonical(record["metadata"]["route_partitions"])
        )
        with self.assertRaisesRegex(ValueError, "verified source partitions"):
            nav.restore(
                record["normalized_html"],
                {k: v for k, v in record.items() if k != "normalized_html"},
                BASE,
                self.ownership,
            )

    def test_stale_partition_source_does_not_reuse_old_metadata(self):
        record = nav.normalize(self.html, "index.html", BASE, self.ownership)
        with self.assertRaisesRegex(ValueError, "verified source partitions"):
            nav.restore(
                record["normalized_html"],
                {k: v for k, v in record.items() if k != "normalized_html"},
                BASE,
                {"public/nordic-atlas/index.html": "b" * 64},
            )

    def test_source_cannot_predeclare_an_admitted_metadata_node(self):
        with self.assertRaisesRegex(ValueError, "predeclare"):
            nav.normalize(
                self.html.replace(
                    "</head>", '<meta name="bijux-csp-navigation" content="{}"></head>'
                ),
                "index.html",
                BASE,
                self.ownership,
            )

    def test_unambiguous_source_routes_and_bounded_table_are_required(self):
        with self.assertRaisesRegex(ValueError, "unambiguous"):
            nav.metadata("index.html", BASE, {"owned?.html": "a" * 64})
        with self.assertRaisesRegex(ValueError, "budget"):
            nav.metadata(
                "index.html", BASE, {str(i) + ".html": "a" * 64 for i in range(2049)}
            )


if __name__ == "__main__":
    unittest.main()
