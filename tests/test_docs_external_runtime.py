"""Counterexamples for source-bound external native executable ownership."""

import base64
import copy
import hashlib
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared/bijux-docs/security"))
external = importlib.import_module("embedded_reports.external_runtime")
html = importlib.import_module("embedded_reports.html")
planning = importlib.import_module("embedded_reports.planning")
BASE = "https://bijux.io/example/"


class ExternalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.case = tempfile.TemporaryDirectory(dir=ROOT / "artifacts")
        self.addCleanup(self.case.cleanup)
        self.root = Path(self.case.name)
        self.loader = "<script>loadOwnedRuntime();</script>"
        self.factory = "globalThis.helpers=function(){%s};"
        self.begin = "/* owned-helpers:begin */"
        self.end = "/* owned-helpers:end */"
        self.helper = "\nfunction helper(){return __VALUE__;}\n"
        self.main_before = "\n(async () => {\nconst value=__VALUE__;\n"
        self.main_after = (
            '\nL.tileLayer("https://tiles.example/{z}");\n})().catch(fail);\n'
        )
        self.pattern = (
            self.main_before + self.begin + self.helper + self.end + self.main_after
        )
        self.write(
            "producer/template.html",
            '<script id="state" type="application/json">__STATE__</script><script id="bootstrap" type="application/json">__BOOTSTRAP__</script><script>'
            + self.pattern
            + "</script>",
        )
        self.producer = (
            "LOADER="
            + repr(self.loader)
            + "\nFACTORY="
            + repr(self.factory)
            + "\nBEGIN="
            + repr(self.begin)
            + "\nEND="
            + repr(self.end)
            + '\nraise RuntimeError("must never execute")\n'
        )
        self.original_template = (self.root / "producer/template.html").read_text()
        self.write("producer/runtime.py", self.producer)
        self.write("producer/index.js", "globalThis.indexTransport=true;")
        self.report = {
            "recipe": {
                "template": "producer/template.html",
                "expansions": [],
                "slots": {
                    "__VALUE__": {"kind": "number", "maximum": 10},
                    "__STATE__": {"kind": "json"},
                    "__BOOTSTRAP__": {"kind": "json"},
                },
                "external_runtime": {
                    "producer": "producer/runtime.py",
                    "loader_symbol": "LOADER",
                    "helper_factory_symbol": "FACTORY",
                    "helper_markers": ["BEGIN", "END"],
                    "controller_source": "producer/index.js",
                },
            },
            "bootstrap_id": "bootstrap",
            "resources": {},
            "providers": {
                "https://tiles.example": {
                    k: "reviewed"
                    for k in ("purpose", "activation", "attribution", "terms")
                }
            },
            "reviewed_provider_origins": ["https://tiles.example"],
            "provider_calls": [{"callee": "L.tileLayer"}],
        }
        main = (self.main_before + self.main_after).replace("__VALUE__", "3")
        helper = (self.factory % self.helper).replace("__VALUE__", "3")
        refs = [
            self.resource(main, "atlas-runtime"),
            self.resource(helper, "atlas-evidence-tools"),
            self.resource("globalThis.indexTransport=true;", "atlas-index-transport"),
        ]
        self.bootstrap = {
            "scope_slug": "example",
            "assets": {
                "schema_version": "atlas-static-asset-table.v3",
                "scope_slug": "example",
                "fields": [
                    "domain",
                    "sha256",
                    "payload_sha256",
                    "decoded_byte_count",
                    "byte_count",
                    "record_count",
                ],
                "record_count": 0,
                "records": [],
            },
            "budgets": {
                "bootstrap_max_bytes": 262144,
                "chunk_max_bytes": 4194304,
                "document_max_bytes": 524288,
                "static_assets_max_bytes": 134217728,
                "static_assets_max_files": 512,
                "initial_max_requests": 4,
                "initial_max_bytes": 1048576,
            },
            "runtime": {
                **refs[0],
                "optional_controllers": {
                    "evidence_tools": refs[1],
                    "index_transport": refs[2],
                },
            },
        }
        self.state = '{"value":3}'

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode() if isinstance(content, str) else content)

    def resource(self, body, kind):
        raw = body.encode()
        sha = hashlib.sha256(raw).hexdigest()
        name = "map." + kind + "." + sha[:16] + ".js"
        self.write("docs/report/" + name, raw)
        self.report["resources"]["report/" + name] = {
            "source": "docs/report/" + name,
            "kind": "reviewed-script",
            "bytes": len(raw),
            "sha256": sha,
        }
        return {
            "path": name,
            "byte_count": len(raw),
            "integrity": "sha256-" + base64.b64encode(bytes.fromhex(sha)).decode(),
        }

    def document(self):
        return html.Document(
            '<script id="state" type="application/json">'
            + self.state
            + '</script><script id="bootstrap" type="application/json">'
            + json.dumps(self.bootstrap)
            + "</script>"
            + self.loader
        )

    def verify(self):
        return external.verify_external_runtime(
            self.root, self.document(), self.report, BASE, "report/map.html"
        )

    def test_selected_source_reconstruction_and_external_provider_audit_pass(self):
        receipt, bodies = self.verify()
        self.assertEqual(len(receipt["external_runtime"]), 3)
        self.assertEqual(
            planning.reviewed_providers(self.report, bodies), self.report["providers"]
        )
        self.assertEqual(len(html.executable_scripts(self.document())), 1)
        self.assertIn(
            "producer/runtime.py", external.recipe_paths(self.report["recipe"])
        )

    def test_runtime_sri_name_controller_and_graph_tampering_refuse(self):
        original = copy.deepcopy((self.bootstrap, self.report))
        for mutation in (
            "sri",
            "path",
            "size",
            "missing-controller",
            "extra-controller",
            "extra-script",
            "bytes",
            "source",
        ):
            with self.subTest(mutation=mutation):
                self.bootstrap, self.report = copy.deepcopy(original)
                runtime = self.bootstrap["runtime"]
                if mutation == "sri":
                    runtime["integrity"] = "sha256-" + "A" * 44
                elif mutation == "path":
                    runtime["path"] = "../outside.js"
                elif mutation == "size":
                    runtime["byte_count"] = True
                elif mutation == "missing-controller":
                    runtime["optional_controllers"].pop("evidence_tools")
                elif mutation == "extra-controller":
                    runtime["optional_controllers"]["other"] = dict(runtime)
                elif mutation == "extra-script":
                    self.report["resources"]["report/unknown.js"] = {
                        "kind": "reviewed-script"
                    }
                elif mutation == "source":
                    self.report["resources"]["report/" + runtime["path"]]["source"] = (
                        "producer/index.js"
                    )
                else:
                    self.report["resources"]["report/" + runtime["path"]]["sha256"] = (
                        "0" * 64
                    )
                with self.assertRaises(ValueError):
                    self.verify()

    def test_rehashed_changed_runtime_still_requires_original_source_recipe(self):
        replacement = self.resource('alert("unreviewed");', "atlas-runtime")
        old = self.bootstrap["runtime"]
        self.report["resources"].pop("report/" + old["path"])
        self.bootstrap["runtime"] = {
            **replacement,
            "optional_controllers": old["optional_controllers"],
        }
        with self.assertRaisesRegex(ValueError, "reviewed renderer recipe"):
            self.verify()

    def test_duplicate_dynamic_nested_and_reassigned_literal_authority_refuse(self):
        for suffix in (
            'LOADER="other"',
            'if True:\n LOADER="other"',
            'LOADER += "other"',
        ):
            with self.subTest(suffix=suffix):
                self.write("producer/runtime.py", self.producer + suffix + "\n")
                with self.assertRaisesRegex(ValueError, "direct string literal"):
                    self.verify()
        self.write(
            "producer/runtime.py",
            self.producer.replace(repr(self.loader), 'str("dynamic")'),
        )
        with self.assertRaisesRegex(ValueError, "direct string literal"):
            self.verify()

    def test_loader_and_json_population_mutation_refuse(self):
        self.loader = "<script>unreviewed();</script>"
        with self.assertRaisesRegex(ValueError, "loader differs"):
            self.verify()
        self.loader = "<script>loadOwnedRuntime();</script>"
        self.state = '{"value": NaN}'
        with self.assertRaises(ValueError):
            self.verify()
        self.state = 'null</script><script id="state" type="application/json">null'
        with self.assertRaisesRegex(ValueError, "exact JSON binding"):
            self.verify()

    def test_helper_scope_and_cross_script_slot_disagreement_refuse(self):
        self.write(
            "producer/template.html",
            "<script>"
            + self.begin
            + self.helper
            + self.end
            + self.main_before
            + self.main_after
            + "</script>",
        )
        with self.assertRaisesRegex(ValueError, "safe IIFE"):
            self.verify()
        self.write("producer/template.html", self.original_template)
        helper = self.bootstrap["runtime"]["optional_controllers"]["evidence_tools"]
        self.report["resources"].pop("report/" + helper["path"])
        self.bootstrap["runtime"]["optional_controllers"]["evidence_tools"] = (
            self.resource(
                (self.factory % self.helper).replace("__VALUE__", "4"),
                "atlas-evidence-tools",
            )
        )
        with self.assertRaisesRegex(ValueError, "inconsistent repeated"):
            self.verify()

    def test_alias_controller_source_refuses(self):
        source = self.root / "producer/index.js"
        source.unlink()
        source.symlink_to(self.root / "producer/runtime.py")
        with self.assertRaises(ValueError):
            self.verify()

    def test_extra_json_node_and_duplicate_non_script_identity_refuse(self):
        original = self.loader
        for extra in (
            '<script id="extra" type="application/json">null</script>',
            '<div id="state"></div>',
        ):
            with self.subTest(extra=extra):
                self.loader = original + extra
                with self.assertRaisesRegex(ValueError, "JSON binding"):
                    self.verify()

    def test_json_parameter_repeated_across_code_and_node_must_agree(self):
        self.write(
            "producer/template.html",
            self.original_template.replace("__STATE__", "__VALUE__"),
        )
        self.report["recipe"]["slots"]["__VALUE__"] = {"kind": "json"}
        self.state = "4"
        with self.assertRaisesRegex(ValueError, "inconsistent repeated"):
            self.verify()

    def test_missing_aliased_and_changed_runtime_bytes_refuse(self):
        runtime = self.bootstrap["runtime"]
        key = "report/" + runtime["path"]
        resource = self.report["resources"].pop(key)
        with self.assertRaisesRegex(ValueError, "reviewed script resource"):
            self.verify()
        self.report["resources"][key] = resource
        target = self.root / resource["source"]
        target.unlink()
        target.symlink_to(self.root / "producer/index.js")
        with self.assertRaises(ValueError):
            self.verify()
        target.unlink()
        target.write_text("Changed sealed executable")
        with self.assertRaisesRegex(ValueError, "bytes/name/SRI"):
            self.verify()

    def test_external_provider_drift_is_inspected_after_source_reconstruction(self):
        self.write(
            "producer/template.html",
            self.original_template.replace(
                "https://tiles.example", "https://other.example"
            ),
        )
        runtime = self.bootstrap["runtime"]
        self.report["resources"].pop("report/" + runtime["path"])
        body = (
            (self.main_before + self.main_after)
            .replace("__VALUE__", "3")
            .replace("https://tiles.example", "https://other.example")
        )
        self.bootstrap["runtime"] = {
            **self.resource(body, "atlas-runtime"),
            "optional_controllers": runtime["optional_controllers"],
        }
        _, bodies = self.verify()
        with self.assertRaisesRegex(ValueError, "declared providers differ"):
            planning.reviewed_providers(self.report, bodies)

    def test_factory_expression_and_multiple_target_assignments_refuse(self):
        for source in (
            self.producer.replace(repr(self.factory), "make_factory()"),
            self.producer.replace("FACTORY=", "OTHER=FACTORY="),
        ):
            with self.subTest(source=source):
                self.write("producer/runtime.py", source)
                with self.assertRaisesRegex(ValueError, "direct string literal"):
                    self.verify()

    def test_annotated_literal_requires_a_direct_name_target(self):
        for target in ("LOADER.attribute", "LOADER[0]"):
            with self.subTest(target=target):
                self.write(
                    "producer/runtime.py",
                    self.producer.replace("LOADER=", target + ": str ="),
                )
                with self.assertRaisesRegex(ValueError, "direct string literal"):
                    self.verify()
        self.write(
            "producer/runtime.py", self.producer.replace("LOADER=", "LOADER: str =")
        )
        self.assertEqual(len(self.verify()[0]["external_runtime"]), 3)
