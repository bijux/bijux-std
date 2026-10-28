"""Historical template custody is explicit, finite and never execution authority."""
from __future__ import annotations

from pathlib import Path
import copy
import importlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / "shared/bijux-docs/security"
spec = importlib.util.spec_from_file_location("bijux_retained_template_policy", SECURITY / "csp.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
package = policy.embedded_module().__package__
contract = importlib.import_module(package + ".contract")
html = importlib.import_module(package + ".html")
planning = importlib.import_module(package + ".planning")
rendering = importlib.import_module(package + ".interactive_rendering")


class RetainedTemplateTests(unittest.TestCase):
    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.root), *args], stderr=subprocess.PIPE
        ).decode().strip()

    def put(self, name, body):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return path

    def commit(self, message):
        self.git("add", "--", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def setUp(self):
        artifacts = ROOT / "artifacts/retained-template-controls"
        artifacts.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Bijux verification")
        self.git("config", "user.email", "verification@bijux.io")
        self.name = "renderer/document.html"
        self.old = b"<script>const answer = __VALUE__;</script>"
        self.put(self.name, self.old)
        self.put("mkdocs.yml", b"site_name: Tiny retained reader\n")
        self.put("readers.json", b"{}\n")
        self.put("docs/report.html", b"<script>const answer = 7;</script>")
        self.revision = self.commit("test(docs): retain literal template")
        blob = self.git("rev-parse", self.revision + ":" + self.name)
        self.pointer = {
            "path": self.name,
            "sha256": contract.digest(self.old),
            "storage": {"role": "retained-template", "commit": self.revision,
                        "blob": blob, "bytes": len(self.old)},
        }
        self.put(self.name, b"<script>const newer = 99;</script>")
        self.current = self.commit("test(docs): change current template")
        self.report = {
            "report_class": "interactive", "output": "report.html",
            "source": self.pin("docs/report.html"), "resources": {},
            "recipe": {"template": self.name, "expansions": [],
                       "slots": {"__VALUE__": {"kind": "number", "maximum": 10}}},
            "providers": {}, "reviewed_provider_origins": [], "provider_calls": [],
        }
        self.descriptor = {
            "config": self.pin("mkdocs.yml"), "reader_purpose": self.pin("readers.json"),
            "producer_inputs": [self.pointer], "reports": [self.report], "parents": [],
        }

    def pin(self, name):
        return {"path": name, "sha256": contract.digest((self.root / name).read_bytes())}

    def inputs(self, descriptor=None):
        descriptor = self.descriptor if descriptor is None else descriptor
        return contract.source_inputs(
            self.root, self.current, planning._descriptor_inputs(descriptor),
            descriptor=descriptor,
        )

    def recipe(self, descriptor=None):
        descriptor = self.descriptor if descriptor is None else descriptor
        return html.report_recipe(
            self.root, html.Document("<script>const answer = 7;</script>"),
            descriptor["reports"][0], "https://example.org/", "report.html",
            source_sha=self.current, source_descriptor=descriptor,
        )

    def test_old_template_is_selected_despite_different_current_body(self):
        current = (self.root / self.name).read_bytes()
        rendering._shape(self.descriptor)
        checked = next(row for row in self.inputs() if row["path"] == self.name)
        self.assertEqual(checked["sha256"], contract.digest(self.old))
        self.assertEqual(checked["storage"], self.pointer["storage"])
        self.assertEqual(checked["git_blob"], self.pointer["storage"]["blob"])
        self.assertEqual(self.recipe()["recipe_sha256"], contract.digest(self.old))
        self.assertEqual((self.root / self.name).read_bytes(), current)

    def test_explicit_git_storage_does_not_need_or_restore_current_file(self):
        (self.root / self.name).unlink()
        self.inputs()
        self.recipe()
        self.assertFalse((self.root / self.name).exists())

    def test_checked_source_receipt_revalidation_retains_storage_identity(self):
        checked = self.inputs()
        self.assertEqual(
            checked, contract.source_inputs(self.root, self.current, checked, descriptor=self.descriptor)
        )
        forged = copy.deepcopy(checked)
        next(row for row in forged if row["path"] == self.name)["storage"]["bytes"] += 1
        with self.assertRaises(contract.AdmissionError):
            contract.source_inputs(self.root, self.current, forged, descriptor=self.descriptor)

    def test_default_recipe_and_input_admission_remain_current_physical(self):
        with self.assertRaises(contract.AdmissionError):
            contract.source_inputs(self.root, self.current, [self.pointer])
        ordinary = {"path": self.name, "sha256": contract.digest(self.old)}
        with self.assertRaisesRegex(contract.AdmissionError, "fingerprint differs"):
            contract.source_inputs(self.root, self.current, [ordinary])
        with self.assertRaisesRegex(contract.AdmissionError, "executable body differs"):
            html.report_recipe(self.root, html.Document("<script>const answer = 7;</script>"),
                               self.report, "https://example.org/", "report.html")

    def test_required_exact_identity_fields_reject_tampering(self):
        variants = [
            ("sha256", "0" * 64), ("commit", "0" * 40), ("blob", "0" * 40),
            ("bytes", len(self.old) + 1), ("bytes", True), ("bytes", 0),
            ("bytes", 2 * 1024**2 + 1), ("bytes", float(len(self.old))),
            ("role", "canonical-source"), ("commit", "HEAD"),
            ("blob", "abc"), ("extra", False),
        ]
        for key, value in variants:
            with self.subTest(key=key, value=value):
                descriptor = copy.deepcopy(self.descriptor)
                pointer = descriptor["producer_inputs"][0]
                (pointer if key == "sha256" else pointer["storage"])[key] = value
                with self.assertRaises(contract.AdmissionError):
                    self.inputs(descriptor)
                with self.assertRaises(contract.AdmissionError):
                    self.recipe(descriptor)

    def test_same_canonical_path_must_exist_in_historical_tree(self):
        descriptor = copy.deepcopy(self.descriptor)
        descriptor["producer_inputs"][0]["path"] = "renderer/other.html"
        descriptor["reports"][0]["recipe"]["template"] = "renderer/other.html"
        with self.assertRaises(contract.AdmissionError):
            self.inputs(descriptor)

    def test_commit_identity_does_not_peel_tags_or_accept_blob(self):
        self.git("-c", "tag.gpgsign=false", "tag", "-a", "retained", "-m", "explicit tag", self.revision)
        for revision in (self.git("rev-parse", "retained"), self.pointer["storage"]["blob"]):
            with self.subTest(revision=revision):
                descriptor = copy.deepcopy(self.descriptor)
                descriptor["producer_inputs"][0]["storage"]["commit"] = revision
                with self.assertRaisesRegex(contract.AdmissionError, "revision must be a commit"):
                    self.inputs(descriptor)

    def test_historical_revision_must_be_ancestor_of_selected_commit(self):
        tree = self.git("rev-parse", self.revision + "^{tree}")
        other = self.git("commit-tree", tree, "-m", "unrelated retained source")
        descriptor = copy.deepcopy(self.descriptor)
        descriptor["producer_inputs"][0]["storage"]["commit"] = other
        with self.assertRaisesRegex(contract.AdmissionError, "Git custody differs"):
            self.inputs(descriptor)
        future = self.pointer | {"storage": self.pointer["storage"] | {"commit": self.current}}
        with self.assertRaisesRegex(contract.AdmissionError, "Git custody differs"):
            contract.source_inputs(self.root, self.revision, [future], descriptor=self.descriptor | {
                "producer_inputs": [future]
            })

    def test_link_mode_cannot_be_presented_as_template_blob(self):
        path = self.root / self.name
        path.unlink()
        path.symlink_to("other.html")
        revision = self.commit("test(docs): retain alias mode")
        self.current = revision
        descriptor = copy.deepcopy(self.descriptor)
        pointer = descriptor["producer_inputs"][0]
        pointer["sha256"] = contract.digest(b"other.html")
        pointer["storage"].update(commit=revision, blob=self.git("rev-parse", revision + ":" + self.name), bytes=len(b"other.html"))
        with self.assertRaisesRegex(contract.AdmissionError, "ordinary blob"):
            self.inputs(descriptor)

    def test_duplicate_and_ordinary_producer_aliases_refuse_before_deduplication(self):
        for pointer in (self.pointer, {"path": self.name, "sha256": self.pointer["sha256"]}):
            descriptor = copy.deepcopy(self.descriptor)
            descriptor["producer_inputs"].append(copy.deepcopy(pointer))
            with self.subTest(pointer=pointer), self.assertRaisesRegex(contract.AdmissionError, "duplicate producer"):
                planning._descriptor_inputs(descriptor)

    def test_non_template_roles_cannot_borrow_git_storage(self):
        for role in ("config", "reader", "source", "resource", "parent", "expansion", "unused"):
            descriptor = copy.deepcopy(self.descriptor)
            report = descriptor["reports"][0]
            if role == "config": descriptor["config"]["path"] = self.name
            elif role == "reader": descriptor["reader_purpose"]["path"] = self.name
            elif role == "source": report["source"]["path"] = self.name
            elif role == "resource": report["resources"]["data.js"] = {"source": self.name}
            elif role == "parent": descriptor["parents"] = [{"source": {"path": self.name}}]
            elif role == "expansion": report["recipe"]["expansions"] = [{"token": "__EXTRA__", "path": self.name}]
            else: report["recipe"]["template"] = "renderer/unused.html"
            with self.subTest(role=role), self.assertRaisesRegex(contract.AdmissionError, "recipe-only"):
                planning._descriptor_inputs(descriptor)

    def test_identical_ordinary_producers_still_deduplicate(self):
        descriptor = copy.deepcopy(self.descriptor)
        ordinary = self.pin("mkdocs.yml")
        descriptor["producer_inputs"].extend([ordinary, dict(ordinary)])
        self.assertEqual(self.inputs(descriptor), self.inputs())
        descriptor["producer_inputs"][-1]["sha256"] = "0" * 64
        with self.assertRaisesRegex(contract.AdmissionError, "contradictory source ownership"):
            planning._descriptor_inputs(descriptor)

    def test_non_template_pointer_shape_stays_closed(self):
        descriptor = copy.deepcopy(self.descriptor)
        descriptor["config"]["storage"] = self.pointer["storage"]
        with self.assertRaises(contract.AdmissionError):
            rendering._shape(descriptor)

    def test_ordinary_physical_drift_and_untracked_source_still_refuse(self):
        path = self.root / "mkdocs.yml"
        before = path.read_bytes()
        path.write_bytes(before + b"drift")
        with self.assertRaisesRegex(contract.AdmissionError, "fingerprint differs"):
            self.inputs()
        path.write_bytes(before)
        untracked = self.put("untracked.txt", b"not admitted")
        with self.assertRaisesRegex(contract.AdmissionError, "untracked or differs"):
            contract.source_inputs(self.root, self.current, [self.pin(untracked.name)])

    def test_repeated_plan_input_gates_receive_same_descriptor_and_source(self):
        path = self.put("owner.json", json.dumps(self.descriptor).encode())
        checked = self.inputs()
        plan = {"repo": str(self.root), "site": str(self.root / "site"),
                "records": [], "navigation": [],
                "source_sha": self.current, "source_inputs": checked,
                "descriptor_path": str(path), "descriptor_sha256": contract.digest(path.read_bytes()),
                "initial_bundle_sha256": "unchanged"}
        class Checked(Exception):
            pass
        calls = []
        def observe(repo, source, inputs, *, descriptor=None):
            calls.append((repo, source, descriptor))
            contract.source_inputs(repo, source, inputs, descriptor=descriptor)
            raise Checked
        for function in (planning.apply_plan, planning.final_receipt):
            with self.subTest(function=function.__name__), mock.patch.object(planning, "source_inputs", observe), mock.patch.object(planning, "bundle_identity", return_value=(None, "unchanged")), self.assertRaises(Checked):
                if function is planning.apply_plan: function(plan)
                else: function(plan, {}, [])
            self.assertEqual(calls[-1], (self.root, self.current, self.descriptor))


if __name__ == "__main__":
    unittest.main()
