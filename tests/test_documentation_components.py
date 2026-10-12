"""Verify paired documentation authority through real Git and unchanged local checks."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / "shared/bijux-checks"
GUARD = CHECKS / "scripts/verify-documentation-components.sh"
NAMES = ("bijux-docs", "bijux-makes", "bijux-checks", "bijux-gh", "bijux-makes-py", "bijux-makes-rs")


class DocumentationCompositionContractTests(unittest.TestCase):
    def compose(self, retained, canonical):
        artifacts = ROOT / "artifacts/tests/documentation-components"
        artifacts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="composition-contract-", dir=artifacts) as directory:
            root = Path(directory)
            for name, body in (("retained", retained), ("canonical", canonical)):
                (root / name).write_bytes(body)
            source = GUARD.read_text().split('python3 - "${old_guard}"', 1)[1].split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
            result = subprocess.run([sys.executable, "-", str(root / "retained"), str(root / "canonical"), str(root / "composed")], input=source, text=True, capture_output=True)
            return result, (root / "composed").read_bytes() if (root / "composed").exists() else None

    def test_unknown_retained_version_refuses_without_output(self):
        canonical = (ROOT / "shared/bijux-docs/tooling/scripts/verify_bijux_docs_source_of_truth.sh").read_bytes()
        result, output = self.compose(canonical + b"# unknown contract\n", canonical)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported retained", result.stderr)
        self.assertIsNone(output)

    def test_ambiguous_canonical_boundary_refuses_without_output(self):
        canonical = (ROOT / "shared/bijux-docs/tooling/scripts/verify_bijux_docs_source_of_truth.sh").read_bytes()
        ambiguous = canonical + b'std_root="${BIJUX_STD_ROOT}"\n'
        result, output = self.compose(ambiguous, ambiguous)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("boundaries are ambiguous", result.stderr)
        self.assertIsNone(output)


class DocumentationComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        artifacts = ROOT / "artifacts/tests/documentation-components"
        artifacts.mkdir(parents=True, exist_ok=True)
        cls.sandbox = tempfile.TemporaryDirectory(prefix="accepted-sources-", dir=artifacts)
        cls.base = Path(cls.sandbox.name)
        cls.source = cls.base / "source"
        cls.source.mkdir()
        cls.git(cls.source, "init", "-q")
        cls.git(cls.source, "config", "user.email", "bijux@example.invalid")
        cls.git(cls.source, "config", "user.name", "Bijux tests")
        for path in (".github", "shared"):
            shutil.copytree(ROOT / path, cls.source / path, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        cls.manifest(cls.source / "shared")
        cls.git(cls.source, "add", ".github", "shared")
        cls.git(cls.source, "commit", "-qm", "test(std): define accepted documentation source")
        cls.docs_sha = cls.git(cls.source, "rev-parse", "HEAD").stdout.strip()
        cls.seed = cls.base / "seed"
        cls.seed.mkdir()
        shutil.copytree(cls.source / ".github", cls.seed / ".github")
        shutil.copytree(cls.source / "shared", cls.seed / ".bijux/shared")
        (cls.source / "shared/bijux-gh/README.md").write_text("# Reviewed common component fixture\n")
        cls.manifest(cls.source / "shared")
        cls.git(cls.source, "add", "shared")
        cls.git(cls.source, "commit", "-qm", "test(std): define independently accepted common source")
        cls.std_sha = cls.git(cls.source, "rev-parse", "HEAD").stdout.strip()
        for name in NAMES:
            if name != "bijux-docs":
                shutil.rmtree(cls.seed / ".bijux/shared" / name)
                shutil.copytree(cls.source / "shared" / name, cls.seed / ".bijux/shared" / name)
        cls.manifest(cls.seed / ".bijux/shared")
        cls.git(cls.seed, "init", "-q")
        cls.git(cls.seed, "config", "user.email", "bijux@example.invalid")
        cls.git(cls.seed, "config", "user.name", "Bijux tests")
        for name, sha in (("bijux-std", cls.std_sha), ("bijux-docs", cls.docs_sha)):
            (cls.seed / f".github/standards/{name}.sha").write_text(sha + "\n")
        (cls.seed / "docs").mkdir()
        (cls.seed / "docs/index.md").write_text("# Bijux documentation fixture\n")
        (cls.seed / "mkdocs.yml").write_text("INHERIT: mkdocs.shared.yml\nsite_name: Bijux\nsite_url: https://bijux.io/bijux-core/\nextra:\n  bijux:\n    active_repo: bijux-core\n")
        (cls.seed / "mkdocs.shared.yml").write_text("theme:\n  name: material\nextra:\n  bijux:\n    active_repo: bijux-core\n")
        cls.commit(cls.seed)
        transport = cls.base / "transport"
        transport.mkdir()
        real_git = shutil.which("git")
        (transport / "git").write_text(
            f"#!{sys.executable}\nimport os,subprocess,sys\nargs=sys.argv[1:]\n"
            f"if 'fetch' in args: args=['-c', 'url.{cls.source}.insteadOf=https://github.com/bijux/bijux-std.git', *args]\n"
            "marker=os.environ.get('COMPONENT_MUTATION_MARKER')\n"
            "if marker and not os.path.exists(marker) and any(':' in a and 'shared/bijux-docs' in a for a in args) and 'show' in args:\n"
            " open(marker,'w').write('observed retained projection source read')\n"
            " mode=os.environ['COMPONENT_MUTATION_MODE']; root=os.environ['COMPONENT_CONSUMER']\n"
            " if mode=='pin': open(root+'/.github/standards/bijux-std.sha','w').write('0'*40+'\\n')\n"
            " if mode=='source': open(os.environ['COMPONENT_DOCS_SOURCE']+'/shared/bijux-docs/README.md','a').write('\\nchanged during local controls\\n')\n"
            f"raise SystemExit(subprocess.run([{real_git!r}, *args]).returncode)\n"
        )
        (transport / "git").chmod(0o755)
        cls.env = dict(os.environ, PATH=str(transport) + os.pathsep + os.environ["PATH"], PYTHONDONTWRITEBYTECODE="1")
        for name in tuple(cls.env):
            if name.startswith("BIJUX_STD_"):
                del cls.env[name]
        cls.docs_source = cls.base / "accepted-docs"
        cls.git(cls.docs_source.parent, "clone", "-q", str(cls.source), str(cls.docs_source))
        cls.git(cls.docs_source, "remote", "set-url", "origin", "https://github.com/bijux/bijux-std.git")
        cls.git(cls.docs_source, "checkout", "-q", "--detach", cls.docs_sha)
        env = dict(cls.env, BIJUX_STD_ROOT=str(cls.docs_source), BIJUX_STD_REF=cls.docs_sha)
        scripts = cls.seed / ".bijux/shared/bijux-docs/tooling/scripts"
        for name in ("project_bijux_docs.py", "sync_mkdocs_hub.py"):
            result = subprocess.run(["bash", "-c", 'set -e; source "$1/docs_source_authority.sh"; verify_docs_authority "$2" "$3"; "$4" "$1/$5" "$2" "$3"', "fixture", str(scripts), str(cls.seed), str(scripts.parents[1]), sys.executable, name], env=env, capture_output=True, text=True)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
        cls.commit(cls.seed)

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.cleanup()

    @staticmethod
    def git(root, *args):
        return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)

    @classmethod
    def commit(cls, root):
        cls.git(root, "add", ".github", ".bijux", "docs", "mkdocs.yml", "mkdocs.shared.yml")
        cls.git(root, "commit", "-qm", "test(docs): retain accepted component fixture")

    @staticmethod
    def manifest(shared):
        rows = []
        for name in NAMES:
            if (shared / name).is_dir():
                digest = subprocess.check_output([str(CHECKS / "scripts/directory-tree-sha256.sh"), str(shared / name)], text=True).strip()
                rows.append(f"{digest} shared/{name}\n")
        (shared / "shared-dir-sha256.txt").write_text("".join(rows))

    def setUp(self):
        self.consumer = self.base / self._testMethodName
        shutil.copytree(self.seed, self.consumer)

    def run_guard(self, **values):
        result = subprocess.run(["bash", str(GUARD)], cwd=self.consumer, env=dict(self.env, **values), capture_output=True, text=True)
        return result

    def refuse(self, needle, **values):
        result = self.run_guard(**values)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(needle, result.stdout + result.stderr)
        self.assertNotIn("passed against both exact accepted component sources", result.stdout)

    def test_actual_accepted_split_preserves_projection_provenance(self):
        marker = self.consumer / ".bijux/docs-projection.json"
        before = marker.read_bytes()
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, marker.read_bytes())
        self.assertIn("passed against both exact accepted component sources", result.stdout)

    def test_python_only_installed_profile_is_complete(self):
        shutil.rmtree(self.consumer / ".bijux/shared/bijux-makes-rs")
        self.manifest(self.consumer / ".bijux/shared")
        self.commit(self.consumer)
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rust_only_installed_profile_is_complete(self):
        shutil.rmtree(self.consumer / ".bijux/shared/bijux-makes-py")
        self.manifest(self.consumer / ".bijux/shared")
        self.commit(self.consumer)
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_laundered_common_hash_refuses(self):
        (self.consumer / ".bijux/shared/bijux-gh/README.md").write_text("forged common source\n")
        self.manifest(self.consumer / ".bijux/shared")
        self.commit(self.consumer)
        self.refuse("local manifest drift")

    def test_laundered_documentation_hash_refuses(self):
        (self.consumer / ".bijux/shared/bijux-docs/README.md").write_text("forged docs source\n")
        self.manifest(self.consumer / ".bijux/shared")
        self.commit(self.consumer)
        self.refuse("local manifest drift")

    def test_missing_manifest_row_refuses(self):
        manifest = self.consumer / ".bijux/shared/shared-dir-sha256.txt"
        manifest.write_text("\n".join(manifest.read_text().splitlines()[1:]) + "\n")
        self.refuse("complete installed capability closure")

    def test_duplicate_manifest_row_refuses(self):
        manifest = self.consumer / ".bijux/shared/shared-dir-sha256.txt"
        manifest.write_text(manifest.read_text() + manifest.read_text().splitlines()[0] + "\n")
        self.refuse("duplicate rows")

    def test_manifest_symlink_refuses(self):
        manifest = self.consumer / ".bijux/shared/shared-dir-sha256.txt"
        manifest.rename(manifest.with_suffix(".copy"))
        manifest.symlink_to(manifest.with_suffix(".copy").name)
        self.refuse("regular unaliased file")

    def test_installed_hardlink_refuses(self):
        readme = self.consumer / ".bijux/shared/bijux-gh/README.md"
        os.link(readme, self.consumer / "linked-readme")
        self.refuse("aliases or special files")

    def test_local_source_bypass_refuses(self):
        self.refuse("forbid local-source bypass", BIJUX_STD_ALLOW_LOCAL_SOURCE="1")

    def test_conflicting_documentation_ref_refuses(self):
        self.refuse("differs from the declared docs pin", BIJUX_STD_REF=self.std_sha)

    def test_site_failure_propagates(self):
        self.refuse("public bundle: selected directory is missing", DOCS_SITE_DIR=str(self.consumer / "artifacts/missing-site"),
                    SITE_URL="https://bijux.io/bijux-core/")

    def test_pin_mutation_during_local_controls_refuses(self):
        marker = self.consumer / "artifacts/mutation-observed"
        marker.parent.mkdir(exist_ok=True)
        self.refuse("pins changed", COMPONENT_MUTATION_MARKER=str(marker), COMPONENT_MUTATION_MODE="pin", COMPONENT_CONSUMER=str(self.consumer))
        self.assertTrue(marker.exists())

    def test_source_mutation_during_local_controls_refuses(self):
        source = self.consumer / "artifacts/documentation-components/documentation" / self.docs_sha
        (self.consumer / "artifacts").mkdir(exist_ok=True)
        marker = self.consumer / "artifacts/mutation-observed"
        self.refuse("modified or untracked inputs", COMPONENT_MUTATION_MARKER=str(marker), COMPONENT_MUTATION_MODE="source",
                    COMPONENT_CONSUMER=str(self.consumer), COMPONENT_DOCS_SOURCE=str(source))
        self.assertTrue(marker.exists())


if __name__ == "__main__":
    unittest.main()
