"""Exercise accepted component retention with real Git sources and updater entrypoints."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared/bijux-checks"
DIRECTORIES = ["bijux-docs", "bijux-makes", "bijux-makes-py", "bijux-makes-rs", "bijux-checks", "bijux-gh"]


class SharedComponentRefreshTests(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT / "artifacts/tests/shared-component-refresh"
        artifacts.mkdir(parents=True, exist_ok=True)
        self.sandbox = tempfile.TemporaryDirectory(prefix="accepted-components-", dir=artifacts)
        self.addCleanup(self.sandbox.cleanup)
        self.base = Path(self.sandbox.name)
        self.source = self.base / "source"
        self.consumer = self.base / "consumer"
        for root in (self.source, self.consumer):
            root.mkdir()
            self.git(root, "init", "-q")
            self.git(root, "config", "user.email", "bijux@example.invalid")
            self.git(root, "config", "user.name", "Bijux tests")
        for name in DIRECTORIES:
            tree = self.source / "shared" / name
            tree.mkdir(parents=True)
            (tree / "contract.txt").write_text("retained component\n")
        self.write_manifest()
        self.git(self.source, "add", "shared")
        self.git(self.source, "commit", "-qm", "test(std): define retained component source")
        self.old_sha = self.git(self.source, "rev-parse", "HEAD").stdout.strip()
        shutil.copytree(self.source / "shared", self.consumer / ".bijux/shared")
        for name in ("bijux-makes", "bijux-checks", "bijux-gh", "bijux-docs"):
            (self.source / "shared" / name / "contract.txt").write_text("new component\n")
        self.write_manifest()
        self.git(self.source, "add", "shared")
        self.git(self.source, "commit", "-qm", "test(std): define newer common and reader components")
        self.new_sha = self.git(self.source, "rev-parse", "HEAD").stdout.strip()
        pins = self.consumer / ".github/standards"
        pins.mkdir(parents=True)
        for name in ("bijux-std.sha", "bijux-docs.sha"):
            (pins / name).write_text(self.old_sha + "\n")
        self.commit_consumer()
        self.env = dict(os.environ, BIJUX_STD_CONFIG=str(SHARED / "bijux-std-checks.yml"),
                        BIJUX_STD_GIT_URL=str(self.source), BIJUX_STD_REF=self.new_sha,
                        BIJUX_STD_CAPABILITIES="common", BIJUX_STD_SELF_REPO_MODE="off",
                        BIJUX_STD_ALLOW_LOCAL_SOURCE="1", BIJUX_STD_UPDATE_PRESERVE_UNSELECTED="1")

    @staticmethod
    def git(root, *arguments):
        return subprocess.run(["git", "-C", str(root), *arguments], text=True, capture_output=True, check=True)

    def commit_consumer(self):
        self.git(self.consumer, "add", ".bijux", ".github")
        self.git(self.consumer, "commit", "-qm", "test(std): retain exact consumer components")

    @staticmethod
    def digest(tree):
        return subprocess.check_output([str(SHARED / "scripts/directory-tree-sha256.sh"), str(tree)], text=True).strip()

    def write_manifest(self):
        rows = [f"{self.digest(self.source / 'shared' / name)} shared/{name}\n" for name in DIRECTORIES]
        (self.source / "shared/shared-dir-sha256.txt").write_text("".join(rows))

    def snapshot(self):
        return {p.relative_to(self.consumer).as_posix(): p.read_bytes()
                for tree in (self.consumer / ".bijux", self.consumer / "shared")
                for p in tree.rglob("*") if p.is_file()}

    def refresh(self, **values):
        return subprocess.run(["bash", str(SHARED / "update-bijux-std.sh")], cwd=self.consumer,
                              env=dict(self.env, **values), text=True, capture_output=True)

    def assert_refusal_preserves_inputs(self, **values):
        before = self.snapshot()
        result = self.refresh(**values)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.snapshot(), before)
        return result

    def test_additive_refresh_keeps_reader_and_language_bytes_and_rows(self):
        before = self.snapshot()
        result = self.refresh()
        self.assertEqual(result.returncode, 0, result.stderr)
        after = self.snapshot()
        for name in ("bijux-docs", "bijux-makes-py", "bijux-makes-rs"):
            path = f".bijux/shared/{name}/contract.txt"
            self.assertEqual(after[path], before[path])
        for name in ("bijux-makes", "bijux-checks", "bijux-gh"):
            self.assertEqual(after[f".bijux/shared/{name}/contract.txt"], b"new component\n")
        rows = (self.consumer / ".bijux/shared/shared-dir-sha256.txt").read_text().splitlines()
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0], before[".bijux/shared/shared-dir-sha256.txt"].decode().splitlines()[0])
        receipt = json.loads((self.consumer / "artifacts/bijux-std/source-provenance.json").read_text())
        self.assertTrue(receipt["preserve_unselected"])
        self.assertEqual({r["directory"] for r in receipt["retained_components"]},
                         {"shared/bijux-docs", "shared/bijux-makes-py", "shared/bijux-makes-rs"})
        self.assertEqual({r["source_sha"] for r in receipt["retained_components"]}, {self.old_sha})

    def test_default_refresh_still_prunes_unselected_components(self):
        result = self.refresh(BIJUX_STD_UPDATE_PRESERVE_UNSELECTED="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.consumer / ".bijux/shared/bijux-docs").exists())
        self.assertEqual(len((self.consumer / ".bijux/shared/shared-dir-sha256.txt").read_text().splitlines()), 3)

    def test_additive_dry_run_keeps_all_inputs_and_never_plans_reader_removal(self):
        before = self.snapshot()
        result = self.refresh(BIJUX_STD_UPDATE_DRY_RUN="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertNotIn("Remove unselected", result.stdout)

    def test_laundered_committed_retained_component_is_refused(self):
        (self.consumer / ".bijux/shared/bijux-docs/contract.txt").write_text("laundered reader\n")
        manifest = self.consumer / ".bijux/shared/shared-dir-sha256.txt"
        rows = manifest.read_text().splitlines()
        rows[0] = f"{self.digest(self.consumer / '.bijux/shared/bijux-docs')} shared/bijux-docs"
        manifest.write_text("\n".join(rows) + "\n")
        self.commit_consumer()
        result = self.assert_refusal_preserves_inputs()
        self.assertIn("differs from its accepted source", result.stderr)

    def test_unavailable_retained_pin_refuses_before_selected_mutation(self):
        (self.consumer / ".github/standards/bijux-docs.sha").write_text("f" * 40 + "\n")
        self.commit_consumer()
        self.assert_refusal_preserves_inputs()

    def test_untracked_retained_input_is_not_discarded(self):
        (self.consumer / ".bijux/shared/bijux-docs/untracked.txt").write_text("user work\n")
        result = self.assert_refusal_preserves_inputs()
        self.assertIn("preserve untracked", result.stderr)

    def test_ignored_retained_input_is_refused(self):
        (self.consumer / ".git/info/exclude").write_text("*.cache\n")
        (self.consumer / ".bijux/shared/bijux-docs/reader.cache").write_text("ignored user work\n")
        result = self.assert_refusal_preserves_inputs()
        self.assertIn("only tracked inputs", result.stderr)

    def test_duplicate_manifest_row_is_refused(self):
        manifest = self.consumer / ".bijux/shared/shared-dir-sha256.txt"
        manifest.write_text(manifest.read_text() + manifest.read_text().splitlines()[0] + "\n")
        self.commit_consumer()
        result = self.assert_refusal_preserves_inputs()
        self.assertIn("unique canonical", result.stderr)

    def test_missing_retained_directory_with_surviving_row_is_refused(self):
        shutil.rmtree(self.consumer / ".bijux/shared/bijux-docs")
        self.commit_consumer()
        result = self.assert_refusal_preserves_inputs()
        self.assertIn("component or manifest row is missing", result.stderr)

    def test_missing_optional_retained_component_and_row_remain_absent(self):
        shutil.rmtree(self.consumer / ".bijux/shared/bijux-makes-rs")
        manifest = self.consumer / ".bijux/shared/shared-dir-sha256.txt"
        manifest.write_text("\n".join(row for row in manifest.read_text().splitlines() if not row.endswith("shared/bijux-makes-rs")) + "\n")
        self.commit_consumer()
        result = self.refresh()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.consumer / ".bijux/shared/bijux-makes-rs").exists())

    def test_invalid_preservation_selector_refuses(self):
        self.assert_refusal_preserves_inputs(BIJUX_STD_UPDATE_PRESERVE_UNSELECTED="yes")

    def test_incomplete_source_override_is_incompatible_with_additive_refresh(self):
        result = self.assert_refusal_preserves_inputs(BIJUX_STD_UPDATE_ALLOW_MISSING_DIRS="1")
        self.assertIn("all required", result.stderr)

    def test_retained_documentation_pin_does_not_require_equal_runtime_pin(self):
        (self.consumer / ".github/standards/bijux-std.sha").write_text(self.new_sha + "\n")
        self.commit_consumer()
        # Python/Rust have identical source bytes in both commits; docs remain old.
        result = self.refresh()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_changed_retained_runtime_requires_selecting_its_capability(self):
        (self.source / "shared/bijux-makes-py/contract.txt").write_text("new Python contract\n")
        self.write_manifest()
        self.git(self.source, "add", "shared")
        self.git(self.source, "commit", "-qm", "test(std): change language authority")
        sha = self.git(self.source, "rev-parse", "HEAD").stdout.strip()
        result = self.assert_refusal_preserves_inputs(BIJUX_STD_REF=sha)
        self.assertIn("select its capability", result.stderr)

    def test_dirty_retained_pin_is_preserved_and_refused(self):
        (self.consumer / ".github/standards/bijux-docs.sha").write_text(self.new_sha + "\n")
        result = self.assert_refusal_preserves_inputs()
        self.assertIn("preserve local managed", result.stderr)

    def test_retained_symlink_cannot_hide_behind_directory_digest(self):
        outside = self.base / "outside.txt"
        outside.write_text("external source\n")
        (self.consumer / ".bijux/shared/bijux-docs/link.txt").symlink_to(outside)
        self.commit_consumer()
        result = self.assert_refusal_preserves_inputs()
        self.assertIn("regular source paths", result.stderr)

    def prepare_full_reader_contract(self):
        tree = self.source / "shared/bijux-docs"
        shutil.rmtree(tree)
        shutil.copytree(ROOT / "shared/bijux-docs", tree,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        workflow = self.source / "shared/bijux-gh/workflows"
        workflow.mkdir()
        shutil.copy(ROOT / "shared/bijux-gh/workflows/release-pypi.yml", workflow)
        self.write_manifest()
        self.git(self.source, "add", "shared")
        self.git(self.source, "commit", "-qm", "test(docs): define complete native reader contract")
        self.old_sha = self.git(self.source, "rev-parse", "HEAD").stdout.strip()
        shutil.rmtree(self.consumer / ".bijux/shared")
        shutil.copytree(self.source / "shared", self.consumer / ".bijux/shared")
        (tree / "reader-contract-fixture.txt").write_text("different reader source\n")
        (self.source / "shared/bijux-makes/contract.txt").write_text("new workflow common contract\n")
        self.write_manifest()
        self.git(self.source, "add", "shared")
        self.git(self.source, "commit", "-qm", "test(std): separate workflow and reader source bytes")
        self.new_sha = self.git(self.source, "rev-parse", "HEAD").stdout.strip()
        # Actual canonical shell/navigation/release checks remain active.
        shutil.copytree(ROOT / ".github/scripts", self.consumer / ".github/scripts",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy(ROOT / ".github/standards/repo-config.manifest.json",
                    self.consumer / ".github/standards/repo-config.manifest.json")
        for name in ("bijux-makes", "bijux-checks", "bijux-gh"):
            shutil.rmtree(self.consumer / ".bijux/shared" / name)
            shutil.copytree(self.source / "shared" / name, self.consumer / ".bijux/shared" / name)
        self.env["BIJUX_STD_REF"] = self.new_sha
        (self.consumer / ".github/standards/bijux-std.sha").write_text(self.new_sha + "\n")
        (self.consumer / ".github/standards/bijux-docs.sha").write_text(self.old_sha + "\n")
        manifest = self.consumer / ".bijux/shared/shared-dir-sha256.txt"
        manifest.write_text("".join(f"{self.digest(self.consumer / '.bijux/shared' / name)} shared/{name}\n" for name in DIRECTORIES))
        self.commit_consumer()

    def check_components(self, **values):
        env = dict(self.env, BIJUX_STD_CAPABILITIES="docs python rust", BIJUX_STD_STRICT_REMOTE="1",
                   BIJUX_STD_REQUIRE_REMOTE_MATCH="1", PYTHONPYCACHEPREFIX=str(self.consumer / "artifacts/pycache"))
        env.update(values)
        return subprocess.run(["bash", str(SHARED / "check-bijux-std.sh")], cwd=self.consumer,
                              env=env, text=True, capture_output=True)

    def test_full_checker_admits_exact_new_common_and_retained_docs_sources(self):
        self.prepare_full_reader_contract()
        result = self.check_components()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Complete navigation source", result.stdout)
        self.assertIn("bijux-std check passed", result.stdout)

    def test_full_checker_refuses_wrong_documentation_pin_and_matching_local_hash(self):
        self.prepare_full_reader_contract()
        (self.consumer / ".github/standards/bijux-docs.sha").write_text(self.new_sha + "\n")
        result = self.check_components()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest drift", result.stderr)

    def test_full_checker_refuses_changed_retained_docs_even_with_rehashed_manifest(self):
        self.prepare_full_reader_contract()
        tree = self.consumer / ".bijux/shared/bijux-docs"
        (tree / "reader-contract-fixture.txt").write_text("unaccepted reader change\n")
        manifest = self.consumer / ".bijux/shared/shared-dir-sha256.txt"
        rows = manifest.read_text().splitlines()
        rows[0] = f"{self.digest(tree)} shared/bijux-docs"
        manifest.write_text("\n".join(rows) + "\n")
        result = self.check_components()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest drift", result.stderr)

    def test_paired_checker_rejects_non_official_authority_without_local_opt_in(self):
        self.prepare_full_reader_contract()
        result = self.check_components(BIJUX_STD_ALLOW_LOCAL_SOURCE="0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GitHub source", result.stderr)

    def test_provider_uses_own_shared_source_despite_historical_metadata_pins(self):
        self.prepare_full_reader_contract()
        provider = self.base / "bijux-std"
        self.consumer.rename(provider)
        self.consumer = provider
        shutil.rmtree(provider / ".bijux")
        shutil.copytree(self.source / "shared", provider / "shared")
        result = self.check_components()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("documentation-source", result.stdout)

    def test_default_same_pin_non_strict_fallback_is_retained(self):
        self.prepare_full_reader_contract()
        fallback = self.base / "fallback-source"
        self.git(self.base, "clone", "-q", str(self.source), str(fallback))
        self.git(fallback, "checkout", "-q", "--detach", self.old_sha)
        shutil.rmtree(self.consumer / ".bijux/shared")
        shutil.copytree(fallback / "shared", self.consumer / ".bijux/shared")
        result = self.check_components(BIJUX_STD_REF=self.old_sha, BIJUX_STD_GIT_URL=str(self.base / "unavailable-origin"),
                                       BIJUX_STD_STRICT_REMOTE="0", BIJUX_STD_ROOT=str(fallback))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("using local bijux-std manifest", result.stdout)

    def test_additive_provider_mode_is_refused_even_with_forced_external_mode(self):
        provider = self.base / "bijux-std"
        self.consumer.rename(provider)
        self.consumer = provider
        shutil.copytree(provider / ".bijux/shared", provider / "shared")
        result = self.assert_refusal_preserves_inputs()
        self.assertIn("explicit consumer capabilities", result.stderr)

    def load_writer(self):
        spec = importlib.util.spec_from_file_location("bijux_component_sync", ROOT / ".github/scripts/sync_github_standards.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_pin_writer_preserves_explicit_reader_authority(self):
        module = self.load_writer()
        with patch.object(module, "resolve_repository_checkout", return_value=self.consumer):
            module.write_std_pin("consumer", self.new_sha, preserve_docs=True)
        self.assertEqual((self.consumer / ".github/standards/bijux-docs.sha").read_text(), self.old_sha + "\n")
        self.assertEqual((self.consumer / ".github/standards/bijux-std.sha").read_text(), self.new_sha + "\n")

    def test_pin_writer_refuses_dirty_tracked_docs_before_runtime_mutation(self):
        module = self.load_writer()
        docs_path = ".github/standards/bijux-docs.sha"
        docs_pin = self.consumer / docs_path
        for staged in (False, True):
            with self.subTest(staged=staged):
                docs_pin.write_text(self.old_sha + "\n")
                self.git(self.consumer, "add", "--", docs_path)
                docs_pin.write_text(self.new_sha + "\n")
                if staged:
                    self.git(self.consumer, "add", "--", docs_path)
                before = (self.consumer / ".github/standards/bijux-std.sha").read_bytes()
                with patch.object(module, "resolve_repository_checkout", return_value=self.consumer):
                    with self.assertRaises(subprocess.CalledProcessError):
                        module.write_std_pin("consumer", self.new_sha, preserve_docs=True)
                self.assertEqual((self.consumer / ".github/standards/bijux-std.sha").read_bytes(), before)
                self.assertEqual(docs_pin.read_text(), self.new_sha + "\n")

    def test_default_pin_writer_still_couples_both_roles(self):
        module = self.load_writer()
        with patch.object(module, "resolve_repository_checkout", return_value=self.consumer):
            module.write_std_pin("consumer", self.new_sha)
        self.assertEqual((self.consumer / ".github/standards/bijux-docs.sha").read_text(), self.new_sha + "\n")

    def test_invalid_retained_pin_refuses_before_runtime_pin_mutation(self):
        module = self.load_writer()
        docs = self.consumer / ".github/standards/bijux-docs.sha"
        docs.write_text("main\n")
        before = (self.consumer / ".github/standards/bijux-std.sha").read_bytes()
        with patch.object(module, "resolve_repository_checkout", return_value=self.consumer):
            with self.assertRaisesRegex(ValueError, "full lowercase"):
                module.write_std_pin("consumer", self.new_sha, preserve_docs=True)
        self.assertEqual((self.consumer / ".github/standards/bijux-std.sha").read_bytes(), before)
    def test_pin_writer_refuses_untracked_docs_authority(self):
        module = self.load_writer()
        self.git(self.consumer, "rm", "--cached", ".github/standards/bijux-docs.sha")
        before = (self.consumer / ".github/standards/bijux-std.sha").read_bytes()
        with patch.object(module, "resolve_repository_checkout", return_value=self.consumer):
            with self.assertRaises(subprocess.CalledProcessError):
                module.write_std_pin("consumer", self.new_sha, preserve_docs=True)
        self.assertEqual((self.consumer / ".github/standards/bijux-std.sha").read_bytes(), before)

    def test_pin_writer_refuses_non_boolean_retention_before_mutation(self):
        module = self.load_writer()
        before = (self.consumer / ".github/standards/bijux-std.sha").read_bytes()
        with patch.object(module, "resolve_repository_checkout", return_value=self.consumer):
            with self.assertRaisesRegex(ValueError, "boolean"):
                module.write_std_pin("consumer", self.new_sha, preserve_docs="false")
        self.assertEqual((self.consumer / ".github/standards/bijux-std.sha").read_bytes(), before)



if __name__ == "__main__":
    unittest.main()
