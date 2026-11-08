"""Keep dynamic native data scripts inside their declared transport graph."""

import copy
import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared/bijux-docs/security"))
graph = importlib.import_module("embedded_reports.runtime_graph")


class RuntimeGraphTests(unittest.TestCase):
    def setUp(self):
        self.sha = "1" * 64
        self.payload = "2" * 64
        self.fields = [
            "domain",
            "sha256",
            "payload_sha256",
            "decoded_byte_count",
            "byte_count",
            "record_count",
        ]
        self.bootstrap = {
            "scope_slug": "example",
            "assets": {
                "schema_version": "atlas-static-asset-table.v3",
                "scope_slug": "example",
                "fields": self.fields,
                "record_count": 1,
                "records": [["nodes", self.sha, self.payload, 12, 64, 1]],
            },
            "budgets": dict(graph._CAPS),
        }
        self.path = "report/example.atlas-nodes.0000." + self.sha[:16] + ".js"
        self.resources = {
            self.path: {
                "kind": "data-registration",
                "source": "docs/" + self.path,
                "sha256": self.sha,
                "bytes": 64,
                "registration": {
                    "variable": "__BIJUX_ATLAS_RAW_CHUNKS__",
                    "asset_key": "nodes:0",
                    "payload_sha256": self.payload,
                    "decoded_bytes": 12,
                },
            }
        }
        self.payloads = [b"main", b"helpers", b"index"]

    def verify(self, binding_bytes=20):
        return graph.verify_registration_graph(
            self.bootstrap,
            self.resources,
            "report/map.html",
            self.payloads,
            binding_bytes,
            512,
        )

    def test_finite_transport_population_passes_without_interpreting_scientific_fields(
        self,
    ):
        self.assertEqual(self.verify(), {"registrations": 1, "registration_bytes": 64})
        self.bootstrap["assets"]["schema_version"] = "atlas-static-asset-table.v4"
        self.assertEqual(self.verify()["registrations"], 1)

    def test_table_row_scope_hash_byte_payload_and_key_mutations_refuse(self):
        original = copy.deepcopy((self.bootstrap, self.resources))
        for mutation in (
            "scope",
            "header",
            "row-shape",
            "population",
            "sha",
            "domain",
            "bytes",
            "decoded",
            "key",
            "payload",
            "variable",
            "path",
            "missing",
            "extra",
        ):
            with self.subTest(mutation=mutation):
                self.bootstrap, self.resources = copy.deepcopy(original)
                table = self.bootstrap["assets"]
                record = table["records"][0]
                resource = self.resources[self.path]
                if mutation == "scope":
                    table["scope_slug"] = "other"
                elif mutation == "header":
                    table["fields"].append("path")
                elif mutation == "row-shape":
                    record.append(0)
                elif mutation == "population":
                    table["record_count"] = True
                elif mutation == "sha":
                    record[1] = "3" * 64
                elif mutation == "domain":
                    record[0] = "../escape"
                elif mutation == "bytes":
                    record[4] += 1
                elif mutation == "decoded":
                    record[3] += 1
                elif mutation == "key":
                    resource["registration"]["asset_key"] = "nodes:1"
                elif mutation == "payload":
                    resource["registration"]["payload_sha256"] = "4" * 64
                elif mutation == "variable":
                    resource["registration"]["variable"] = "__OTHER__"
                elif mutation == "path":
                    resource["source"] = "docs/other.js"
                elif mutation == "missing":
                    self.resources.clear()
                else:
                    self.resources["report/extra.js"] = resource
                with self.assertRaises(ValueError):
                    self.verify()

    def test_original_initial_total_and_member_budgets_include_fixed_bindings(self):
        original = copy.deepcopy(self.bootstrap)
        for budget, value in (
            ("static_assets_max_files", 3),
            ("static_assets_max_bytes", 80),
            ("initial_max_bytes", 23),
            ("bootstrap_max_bytes", 511),
            ("document_max_bytes", 6),
            ("chunk_max_bytes", 63),
        ):
            with self.subTest(budget=budget):
                self.bootstrap = copy.deepcopy(original)
                self.bootstrap["budgets"][budget] = value
                with self.assertRaises(ValueError):
                    self.verify()
        self.bootstrap = copy.deepcopy(original)
        self.bootstrap["budgets"]["initial_max_bytes"] = (
            graph._CAPS["initial_max_bytes"] + 1
        )
        with self.assertRaisesRegex(ValueError, "original limits"):
            self.verify()
        self.bootstrap = copy.deepcopy(original)
        self.bootstrap["budgets"]["initial_max_bytes"] = 24
        self.assertEqual(self.verify()["registrations"], 1)
        with self.assertRaisesRegex(ValueError, "initial resource"):
            self.verify(binding_bytes=21)
