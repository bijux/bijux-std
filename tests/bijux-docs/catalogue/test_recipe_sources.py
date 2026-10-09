"""Exercise actual committed recipe in independent owned Git fixtures."""

from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from fixture_source import create_fixture

HERE = Path(__file__).resolve()
REPO = next(
    parent
    for parent in HERE.parents
    if (parent / "shared/bijux-docs/security/catalogue_recipe.py").is_file()
)
OUTPUT = REPO / "artifacts/catalogue-recipe-tests"
OUTPUT.mkdir(parents=True, exist_ok=True)


def load(path):
    spec = importlib.util.spec_from_file_location(
        "catalogue_controls_" + path.stem, path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecipeControls(unittest.TestCase):
    def setUp(self):
        import tempfile

        directory = tempfile.TemporaryDirectory(dir=OUTPUT)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "source"
        create_fixture(REPO, self.root)
        self.shared = self.root / ".bijux/shared/bijux-docs"
        self.recipe = load(self.shared / "security/catalogue_recipe.py")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def derive(self, **kwargs):
        return self.recipe.derive(self.root, self.shared, self.recipe.RECIPE, **kwargs)

    def committed(self, name, data):
        p = self.root / name
        p.write_bytes(data)
        self.git("add", name)
        self.git("commit", "-qm", "test(docs): bind owned recipe counterexample")

    def test_clean_actual_capture_and_native_mapping(self):
        context = self.derive()
        self.assertEqual(len(context.map), 4)
        self.assertEqual(context.record["owner"]["path"], "mkdocs.yml")
        self.assertIsNone(context.record["environment"]["SITE_URL"])
        self.assertEqual(context.record["documents"], 4)

    def test_valid_native_cache_is_bound_to_captured_hook(self):
        import py_compile

        source = self.root / "docs/hooks/publish_site_assets.py"
        py_compile.compile(str(source), doraise=True)
        self.assertEqual(len(self.derive().map), 4)

    def test_changed_native_cache_payload_rejected(self):
        import py_compile

        source = self.root / "docs/hooks/publish_site_assets.py"
        cache = Path(py_compile.compile(str(source), doraise=True))
        cache.write_bytes(cache.read_bytes() + b"forged")
        with self.assertRaisesRegex(ValueError, "one code object"):
            self.derive()

    def test_unowned_source_cache_rejected(self):
        import py_compile

        source = self.root / "docs/hooks/foreign.py"
        source.write_text('print("foreign")')
        py_compile.compile(str(source), doraise=True)
        source.unlink()
        with self.assertRaises(ValueError):
            self.derive()

    def test_shared_inheritance_cannot_load_ignored_configuration(self):
        name = "mkdocs.shared.yml"
        self.committed(
            name, b"INHERIT: artifacts/foreign.yml\n" + (self.root / name).read_bytes()
        )
        with self.assertRaisesRegex(ValueError, "uncaptured configuration"):
            self.derive()

    def test_unknown_recipe_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown recipe"):
            self.recipe.derive(self.root, self.shared, "unreviewed-catalogue")

    def test_committed_changed_generator_rejected(self):
        name = "scripts/docs_nav.py"
        self.committed(name, (self.root / name).read_bytes() + b"\n# distinct code\n")
        with self.assertRaisesRegex(ValueError, "generator source differs"):
            self.derive()

    def test_untracked_document_rejected(self):
        (self.root / "docs/unowned.md").write_text("# Foreign")
        with self.assertRaisesRegex(ValueError, "source is dirty"):
            self.derive()

    def test_changed_derived_document_rejected(self):
        (self.root / "docs/index.md").write_text("# Forged")
        with self.assertRaisesRegex(ValueError, "extra bytes"):
            self.derive()

    def test_changed_derived_configuration_rejected(self):
        (self.root / "artifacts/mkdocs.root.yml").write_text("site_name: Forged\n")
        with self.assertRaisesRegex(ValueError, "configuration differs"):
            self.derive()

    def test_missing_derived_document_rejected(self):
        (self.root / "docs/index.md").unlink()
        with self.assertRaisesRegex(ValueError, "missing or extra bytes"):
            self.derive()

    def test_configuration_symlink_rejected(self):
        p = self.root / "artifacts/mkdocs.root.yml"
        p.unlink()
        p.symlink_to(self.root / "mkdocs.yml")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.derive()

    def test_output_hardlink_rejected_without_source_damage(self):
        p = self.root / "docs/index.md"
        p.unlink()
        source = self.root / "programs/README.md"
        before = source.read_bytes()
        os.link(source, p)
        with self.assertRaisesRegex(ValueError, "unlinked"):
            self.derive()
        self.assertEqual(source.read_bytes(), before)

    def test_record_map_digest_cannot_be_relabelled(self):
        record = self.derive().record
        record["document_map_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "record differs"):
            self.derive(expected=record)

    def test_absent_environment_and_empty_environment_are_distinct(self):
        context = self.derive()
        with patch.dict(os.environ, {"SITE_URL": ""}):
            with self.assertRaisesRegex(ValueError, "configuration differs"):
                self.derive(expected=context.record)

    def test_unknown_environment_reference_rejected(self):
        name = "mkdocs.yml"
        self.committed(
            name,
            (self.root / name).read_bytes().replace(b"SITE_URL", b"UNREVIEWED_URL"),
        )
        with self.assertRaisesRegex(ValueError, "unreviewed configuration ENV"):
            self.derive()

    def test_dirty_original_rejected(self):
        (self.root / "programs/README.md").write_text("# Changed")
        with self.assertRaises(ValueError):
            self.derive()

    def test_caller_capture_cannot_replace_committed_capture(self):
        with self.assertRaisesRegex(ValueError, "caller input differs"):
            self.derive(inputs={})

    def test_ambient_generator_module_does_not_own_import(self):
        import types

        fake = types.ModuleType("scripts.docs_nav")
        fake.prune_nav = lambda *args: (_ for _ in ()).throw(
            AssertionError("ambient called")
        )
        with patch.dict(sys.modules, {"scripts.docs_nav": fake}):
            self.assertEqual(len(self.derive().map), 4)

    def test_shallow_source_history_rejected(self):
        (self.root / ".git/shallow").write_text(self.git("rev-parse", "HEAD"))
        with self.assertRaisesRegex(ValueError, "complete native original history"):
            self.derive()

    def test_native_replacement_history_rejected(self):
        head = self.git("rev-parse", "HEAD").strip()
        self.git("update-ref", "refs/replace/" + head, head)
        with self.assertRaisesRegex(ValueError, "repository source operation failed"):
            self.derive()

    def test_alternate_native_replacement_namespace_rejected(self):
        head = self.git("rev-parse", "HEAD").strip()
        tree = self.git("rev-parse", "HEAD^{tree}").strip()
        replacement = subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "commit-tree",
                tree,
                "-m",
                "controlled history replacement",
            ],
            check=True,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "GIT_AUTHOR_DATE": "2050-01-02T03:04:05+00:00",
                "GIT_COMMITTER_DATE": "2051-02-03T04:05:06+00:00",
            },
        ).stdout.strip()
        self.git("update-ref", "refs/bijux-history-replacements/" + head, replacement)
        with patch.dict(
            os.environ, {"GIT_REPLACE_REF_BASE": "refs/bijux-history-replacements/"}
        ):
            with self.assertRaisesRegex(
                ValueError, "alternate native replacement namespace"
            ):
                self.derive()

    def foreign_history(self):
        head = self.git("rev-parse", "HEAD").strip()
        tree = self.git("rev-parse", "HEAD^{tree}").strip()
        replacement = subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "commit-tree",
                tree,
                "-m",
                "controlled identical-tree history",
            ],
            check=True,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "GIT_AUTHOR_DATE": "2050-01-02T03:04:05+00:00",
                "GIT_COMMITTER_DATE": "2051-02-03T04:05:06+00:00",
            },
        ).stdout.strip()
        foreign = self.root.parent / "foreign-git"
        shutil.copytree(self.root / ".git", foreign)
        branch = self.git("symbolic-ref", "HEAD").strip()
        (foreign / branch).write_text(replacement + "\n")
        return head, replacement, foreign

    def test_external_graft_cannot_replace_original_course_history(self):
        head, replacement, _ = self.foreign_history()
        original = self.git("log", "--format=%H:%at:%ct:%P", "HEAD", "--", "programs")
        graft = self.root.parent / "external-grafts"
        graft.write_text(head + " " + replacement + "\n")
        with patch.dict(os.environ, {"GIT_GRAFT_FILE": str(graft)}):
            # Same HEAD and committed bytes, but Git's actual ancestry has changed.
            self.assertEqual(self.git("rev-parse", "HEAD").strip(), head)
            self.assertNotEqual(
                self.git("log", "--format=%H:%at:%ct:%P", "HEAD", "--", "programs"),
                original,
            )
            with self.assertRaisesRegex(
                ValueError, "environment override forbidden: GIT_GRAFT_FILE"
            ):
                self.derive()
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), head)

    def test_foreign_git_store_cannot_own_identical_committed_source_history(self):
        head, replacement, foreign = self.foreign_history()
        with patch.dict(os.environ, {"GIT_DIR": str(foreign)}):
            self.assertEqual(self.git("rev-parse", "HEAD").strip(), replacement)
            with self.assertRaisesRegex(
                ValueError, "environment override forbidden: GIT_DIR"
            ):
                self.derive()
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), head)

    def test_bound_worktree_cannot_admit_foreign_git_history(self):
        head, replacement, foreign = self.foreign_history()
        with patch.dict(
            os.environ, {"GIT_DIR": str(foreign), "GIT_WORK_TREE": str(self.root)}
        ):
            self.assertEqual(
                Path(self.git("rev-parse", "--show-toplevel").strip()), self.root
            )
            self.assertEqual(self.git("rev-parse", "HEAD").strip(), replacement)
            with self.assertRaisesRegex(
                ValueError, "environment override forbidden: GIT_DIR"
            ):
                self.derive()
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), head)

    def test_common_directory_override_has_no_captured_owner_authority(self):
        _, _, foreign = self.foreign_history()
        with patch.dict(os.environ, {"GIT_COMMON_DIR": str(foreign)}):
            with self.assertRaisesRegex(
                ValueError, "environment override forbidden: GIT_COMMON_DIR"
            ):
                self.derive()

    def test_explicit_worktree_override_has_no_captured_owner_authority(self):
        with patch.dict(os.environ, {"GIT_WORK_TREE": str(self.root)}):
            with self.assertRaisesRegex(
                ValueError, "environment override forbidden: GIT_WORK_TREE"
            ):
                self.derive()

    def test_empty_native_history_overrides_are_not_absence(self):
        for name in ("GIT_GRAFT_FILE", "GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE"):
            with self.subTest(environment=name), patch.dict(os.environ, {name: ""}):
                with self.assertRaisesRegex(
                    ValueError, "environment override forbidden: " + name
                ):
                    self.derive()

    def test_source_mutation_after_native_mapping_rejected(self):
        context = self.derive()
        (self.root / "programs/README.md").write_text("# Changed")
        with self.assertRaisesRegex(ValueError, "changed after capture"):
            context.sources.unchanged()


if __name__ == "__main__":
    unittest.main(verbosity=2)
