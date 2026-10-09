"""Controlled source/composition prerequisites; no actual renderer approval."""
from pathlib import Path
import copy
import importlib.util
import io
import sys
import importlib
import json
import os
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def fixture(name):
    spec = importlib.util.spec_from_file_location("bijux_reader_publication_" + name, ROOT / "tests" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

standalone = fixture("test_docs_standalone_readers")
qualified = fixture("test_docs_publication_security")


class ReaderPublicationComposition(unittest.TestCase):
    def setUp(self):
        self.fixture = standalone.StandaloneReaderTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        c = self.case = self.fixture.case
        c.descriptor = c.repo / "docs/report/ownership.json"
        c.save_owner()
        c.git("add", "docs/report/ownership.json")
        c.git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "fixture: own reader publication descriptor")
        c.source_sha = c.git("rev-parse", "HEAD").strip()
        self.checkpoint = {"repository_source": {"sha": c.source_sha}}
        c.build.update(scope="actual-mkdocs-renderer", source_checkpoint=self.checkpoint)
        self.report, build = c.complete()
        self.build = build | {"verification_only": False}
        self.adapter = importlib.import_module(c.integration.__package__ + ".publication")
        self.calls = []
        class ControlledSource:
            def verify_source(inner, repository, checkpoint):
                self.assertEqual(repository, c.repo)
                self.assertEqual(checkpoint, self.checkpoint)
                self.assertEqual(c.git("rev-parse", "HEAD").strip(), checkpoint["repository_source"]["sha"])
                self.assertFalse(c.git("status", "--porcelain", "--untracked-files=all").strip())
                self.calls.append(copy.deepcopy(checkpoint))
        self.identity = ControlledSource()

    def verify(self, **kw):
        values = dict(repository=self.case.repo, identity=self.identity, checkpoint=self.checkpoint)
        values.update(kw)
        return self.adapter.verify_readers(self.case.site, self.report, self.build, **values)

    def test_source_checkpoint_and_passive_discovery_rederive_without_runtime_approval(self):
        result = self.verify()
        self.assertEqual(result["report_routes"], {"report/map.html"})
        self.assertEqual(set(result["reader_purposes"]), result["report_routes"])
        self.assertEqual(result["capabilities"]["report/map.html"]["script_sources"], ["'none'"])
        self.assertTrue(self.calls)
        self.assertNotIn("producer_authority", result)
        self.assertNotIn("renderer_profile", result)

    def test_missing_independent_source_verifier_or_checkpoint_cannot_grant_authority(self):
        for values in ({"identity": None}, {"checkpoint": None}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.verify(**values)

    def test_local_false_source_and_uncompleted_build_remain_rejected(self):
        original = self.build
        for changes in ({"verification_only": True}, {"state": "prepared"}, {"source_checkpoint": {"repository_source": {"sha": "0" * 40}}}):
            with self.subTest(changes=changes):
                self.build = original | changes
                with self.assertRaises(ValueError): self.verify()
        self.build = original

    def test_untracked_descriptor_cannot_rehash_into_source_admission(self):
        c = self.case
        other = c.repo / "artifacts/untracked-owner.json"
        other.write_bytes(c.descriptor.read_bytes())
        self.report["embedded"]["descriptor_path"] = str(other)
        with self.assertRaisesRegex(ValueError, "untracked or differs"):
            self.verify()

    def test_external_descriptor_never_selects_authority(self):
        self.report["embedded"]["descriptor_path"] = str(self.case.case / "external.json")
        with self.assertRaisesRegex(ValueError, "exact repository"):
            self.verify()

    def test_committed_unknown_descriptor_version_cannot_rehash_into_composition(self):
        c = self.case
        c.owner["schema"] = "unreviewed-report-contract"
        c.save_owner()
        c.git("add", "docs/report/ownership.json")
        c.git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "fixture: retain unsupported descriptor version")
        c.source_sha = c.git("rev-parse", "HEAD").strip()
        self.checkpoint = {"repository_source": {"sha": c.source_sha}}
        retained = self.report["embedded"]
        retained["source_sha"] = c.source_sha
        retained["descriptor_sha256"] = self.adapter.digest(c.descriptor.read_bytes())
        retained["build_receipt"]["source_checkpoint"] = self.checkpoint
        retained["build_receipt_sha256"] = self.adapter.digest(c.integration.canonical(retained["build_receipt"]))
        self.build["source_checkpoint"] = self.checkpoint
        self.report["policy_inputs"]["embedded"] = c.integration.inputs(retained)
        with self.assertRaisesRegex(ValueError, "supported source-owned descriptor schema"):
            self.verify()

    def test_self_declared_profiles_and_extra_descriptor_authority_reject(self):
        c = self.case
        c.owner["approved_profile"] = {"usage": "publication", "accepted": True}
        c.save_owner()
        with self.assertRaisesRegex(ValueError, "exact source-owned descriptor"):
            self.verify()

    def test_interactive_and_unknown_class_need_their_own_producer_review(self):
        c = self.case
        for name in ("interactive", "unknown"):
            c.owner["reports"][0]["report_class"] = name
            c.save_owner()
            with self.assertRaises(ValueError): self.verify()

    def test_changed_source_cannot_rehash_into_descriptor_admission(self):
        c = self.case
        c.owner["reports"][0]["source"]["sha256"] = "f" * 64
        c.save_owner()
        self.report["embedded"]["descriptor_sha256"] = self.adapter.digest(c.descriptor.read_bytes())
        with self.assertRaisesRegex(ValueError, "untracked or differs"):
            self.verify()

    def test_changed_search_sitemap_and_report_reject_with_rehashed_bundle(self):
        c = self.case
        for name, value in (("search/search_index.json", b'{"docs":[]}'), ("sitemap.xml", b'<urlset/>'), ("report/map.html", b'<html><head></head><body>Unknown</body></html>')):
            path = c.site / name; original = path.read_bytes()
            with self.subTest(name=name):
                path.write_bytes(value)
                original_build = self.build
                self.build = self.build | {"bundle_sha256": c.identity()}
                with self.assertRaises(ValueError): self.verify()
                self.build = original_build
                path.write_bytes(original)

    def test_missing_reader_purpose_cannot_be_ignored_by_publication(self):
        c = self.case
        c.owner.pop("reader_purpose")
        c.save_owner()
        with self.assertRaisesRegex(ValueError, "exact source-owned descriptor"):
            self.verify()

    def test_real_source_verifier_failure_is_not_replaced_by_receipt_claim(self):
        class Rejected:
            def verify_source(inner, repository, checkpoint):
                raise ValueError("controlled source authority rejected")
        with self.assertRaisesRegex(ValueError, "authority rejected"):
            self.verify(identity=Rejected())


class SerializedPublicationClaims(unittest.TestCase):
    def setUp(self):
        self.case = qualified.QualifiedPublicationTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def test_arbitrary_qualification_and_profile_claims_do_not_survive_exact_byte_check(self):
        c = self.case
        manifest = c.qualified()
        forged = copy.deepcopy(manifest)
        forged["producer_authority"] = {"verification_only": False, "approved_profile": "invented"}
        with self.assertRaisesRegex(ValueError, "changed after qualification"):
            qualified.publication.verify_manifest(c.root, forged, c.policy)
        forged = copy.deepcopy(manifest)
        forged["qualification"]["verification"]["receipt"]["passed"] = False
        with self.assertRaisesRegex(ValueError, "changed after qualification"):
            qualified.publication.verify_manifest(c.root, forged, c.policy)

    def test_changed_actual_qualification_file_fails_even_if_manifest_bytes_still_match(self):
        c = self.case
        manifest = c.qualified()
        c.records["build"]["verification_only"] = True
        c.write_records()
        with self.assertRaisesRegex(ValueError, "publication renderer identity"):
            qualified.publication.verify_manifest(c.root, manifest, c.policy)


class PreviousGoodRecovery(unittest.TestCase):
    def setUp(self):
        self.case = qualified.QualifiedPublicationTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def test_offline_bytes_do_not_retain_historical_profile_or_qualification_claims(self):
        c = self.case
        manifest = c.qualified()
        for path in c.paths.values(): (c.root / path).unlink()
        manifest["producer_authority"] = {"approved_profile": "invented"}
        result = qualified.publication.verify_retained_bytes(c.root, manifest, c.policy)
        self.assertEqual(result["scope"], "retained-public-bytes-only")
        self.assertTrue(result["verification_only"])
        self.assertFalse(result["publication_approval"])
        self.assertFalse(result["qualified_source_verified"])
        self.assertNotIn("producer_authority", result)
        self.assertNotIn("qualification", result)
        with self.assertRaises(ValueError):
            qualified.publication.verify_manifest(c.root, manifest, c.policy)

    def test_offline_cli_uses_only_retained_bytes_without_receipt_reconstruction(self):
        c = self.case
        manifest = c.qualified(); path = c.root / "artifacts/manifest.json"
        path.write_text(json.dumps(manifest))
        for receipt in c.paths.values(): (c.root / receipt).unlink()
        args = ["publication.py", "--repo-root", str(c.root), "verify", "--manifest", str(path), "--bytes-only"]
        with patch.object(sys, "argv", args), patch.object(qualified.publication, "qualified_manifest") as reconstructed, patch("sys.stdout", new_callable=io.StringIO) as stdout:
            self.assertEqual(qualified.publication.main(), 0)
            self.assertEqual(reconstructed.call_count, 0)
            result = json.loads(stdout.getvalue())
            self.assertFalse(result["publication_approval"])
            self.assertFalse(result["qualified_source_verified"])
            self.assertNotIn("qualification_receipts", result)

    def test_offline_inventory_changes_and_unsafe_links_are_rejected(self):
        c = self.case
        manifest = c.qualified()
        p = c.site / "index.html"; original = p.read_bytes()
        p.write_bytes(original + b"changed")
        with self.assertRaises(ValueError):
            qualified.publication.verify_retained_bytes(c.root, manifest, c.policy)
        p.write_bytes(original)
        other = c.site / "unlisted.txt"; other.write_text("Unlisted")
        with self.assertRaises(ValueError):
            qualified.publication.verify_retained_bytes(c.root, manifest, c.policy)
        other.unlink(); other.symlink_to(p)
        with self.assertRaises(ValueError):
            qualified.publication.verify_retained_bytes(c.root, manifest, c.policy)

    def test_require_qualified_cli_reconstructs_once(self):
        c = self.case
        manifest = c.qualified(); path = c.root / "artifacts/manifest.json"
        path.write_text(json.dumps(manifest))
        args = ["publication.py", "--repo-root", str(c.root), "verify", "--manifest", str(path), "--require-qualified"]
        with patch.object(sys, "argv", args), patch.object(qualified.publication, "qualified_manifest", wraps=qualified.publication.qualified_manifest) as reconstructed, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(qualified.publication.main(), 0)
            self.assertEqual(reconstructed.call_count, 1)

    def test_offline_mode_cannot_be_requested_as_qualified_publication(self):
        args = ["publication.py", "verify", "--manifest", "unread.json", "--bytes-only", "--require-qualified"]
        with patch.object(sys, "argv", args), patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit) as error:
            qualified.publication.main()
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__": unittest.main()
