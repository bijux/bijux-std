"""Qualify lightweight complete-navigation admission without browser or network setup."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared/bijux-docs"
CHECKER = ROOT / "shared/bijux-checks/check-bijux-std.sh"
ARTIFACTS = ROOT / "artifacts/tests/navigation-source-admission"


def admitted_functions():
    source = CHECKER.read_text()
    resolver = source[source.index("resolve_local_rel() {"):source.index("verify_no_legacy_root_shared_dirs() {")]
    admission = source[source.index("verify_complete_navigation_source_contract() {"):source.index("verify_workflow_run_shell_preambles() {")]
    return resolver + admission


class NavigationSourceAdmissionTests(unittest.TestCase):
    def fixture(self, consumer=False):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=ARTIFACTS)
        self.addCleanup(directory.cleanup)
        repo = Path(directory.name) / ("consumer" if consumer else "bijux-std")
        shared = repo / (".bijux/shared/bijux-docs" if consumer else "shared/bijux-docs")
        shared.parent.mkdir(parents=True)
        shutil.copytree(SHARED, shared)
        return repo, shared

    def admit(self, repo):
        script = 'set -euo pipefail\nrepo_root="$1"\n' + admitted_functions() + '\nverify_complete_navigation_source_contract\n'
        return subprocess.run(["bash", "-c", script, "navigation-admission", str(repo)], cwd=repo, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)

    def reject(self, repo, diagnostic):
        result = self.admit(repo)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(diagnostic, result.stderr)

    def project(self, repo, shared):
        for source in (shared / "partials").glob("*.html"):
            destination = repo / "docs/overrides/partials" / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        for source in (shared / "styles").glob("*.css"):
            destination = repo / "docs/assets/styles" / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        for name in ("bootstrap.js", "detail-tabs.js", "nav-reveal.js", "nav-state.js", "viewport-profile.js", "nav-sync.js"):
            destination = repo / ("docs/assets/javascripts/navigation-sync.js" if name == "nav-sync.js" else "docs/assets/javascripts/shell/" + name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(shared / "scripts" / name, destination)

    def test_source_only_std_and_managed_consumer_use_the_same_admission(self):
        for consumer in (False, True):
            with self.subTest(consumer=consumer):
                repo, _ = self.fixture(consumer)
                result = self.admit(repo)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Complete navigation source", result.stdout)

    def test_retired_item_source_has_a_useful_dependency_error(self):
        repo, shared = self.fixture()
        (shared / "partials/nav-item.html").unlink()
        self.reject(repo, "missing owned dependency")
        self.reject(repo, "nav-item.html")

    def test_removed_recursive_disclosure_or_real_destination_is_rejected(self):
        for before, after in (("<details ", "<div "), ("<summary ", "<span "), ("render(child,", "title(child,"), ("href=", "data-target=")):
            with self.subTest(before=before):
                repo, shared = self.fixture()
                path = shared / "partials/nav-item.html"
                path.write_text(path.read_text().replace(before, after))
                self.reject(repo, "native disclosures and ordinary destination anchors")

    def test_registry_remains_available_independently_of_document_tree(self):
        repo, shared = self.fixture()
        path = shared / "partials/nav.html"
        path.write_text("{% if nav %}\n" + path.read_text() + "\n{% endif %}")
        self.reject(repo, "must not depend on a nonempty document tree")

    def test_legacy_conditional_navigation_model_is_rejected(self):
        repo, shared = self.fixture()
        path = shared / "partials/nav.html"
        path.write_text(path.read_text().replace("bijux-nav--mobile", "bijux-nav--scoped"))
        self.reject(repo, "retired conditional navigation model")

    def test_owned_runtime_must_be_loaded_by_the_declared_baseline(self):
        repo, shared = self.fixture()
        path = shared / "config/mkdocs-baseline.json"
        value = json.loads(path.read_text())
        value["extra_javascript"].remove("assets/javascripts/shell/bootstrap.js")
        path.write_text(json.dumps(value))
        self.reject(repo, "baseline does not load owned navigation dependency")

    def test_stylesheet_dependency_retirement_or_omission_is_rejected(self):
        repo, shared = self.fixture()
        (shared / "styles/08-responsive.css").unlink()
        self.reject(repo, "missing owned dependency")
        repo, shared = self.fixture()
        path = shared / "styles/extra.css"
        path.write_text(path.read_text().replace('@import url("./07-utilities.css");', ""))
        self.reject(repo, "stylesheet manifest omits navigation dependency")

    def test_stylesheet_import_cannot_escape_owned_source(self):
        repo, shared = self.fixture()
        path = shared / "styles/extra.css"
        path.write_text(path.read_text() + '\n@import url("../unowned.css");\n')
        self.reject(repo, "stylesheet import escapes its owned directory")

    def test_applicable_consumer_projection_must_be_complete_and_byte_identical(self):
        repo, shared = self.fixture(True)
        self.project(repo, shared)
        self.assertEqual(self.admit(repo).returncode, 0)
        path = repo / "docs/overrides/partials/nav-item.html"
        path.unlink()
        self.reject(repo, "incomplete consumer projection")
        shutil.copy2(shared / "partials/nav-item.html", path)
        (repo / "docs/overrides/partials/nav.html").write_text("<nav>Legacy incomplete tree</nav>")
        self.reject(repo, "consumer projection differs from owned source")

    def test_admission_failure_preserves_consumer_content(self):
        repo, shared = self.fixture(True)
        self.project(repo, shared)
        (repo / "docs/overrides/partials/nav.html").write_text("User-authored pending changes")
        before = {path.relative_to(repo): path.read_bytes() for path in repo.rglob("*") if path.is_file()}
        self.reject(repo, "consumer projection differs")
        after = {path.relative_to(repo): path.read_bytes() for path in repo.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
