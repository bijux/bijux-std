"""Qualify declaration ownership on actual styles and adversarial source copies."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "shared/bijux-docs"
COMMAND = DOCS / "tooling/quality/styles/cascade.mjs"
DEPENDENCIES = Path(os.environ.get("BIJUX_DIAGRAM_DEPENDENCIES", ROOT / "artifacts/website-security/dependencies/build"))


class CascadeContractTests(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT / "artifacts/qualification/cascade-contract/tests"
        artifacts.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(self.directory.cleanup)
        self.case = Path(self.directory.name)
        self.styles = self.case / "styles"
        shutil.copytree(DOCS / "styles", self.styles)
        self.policy_path = self.case / "cascade-contract.json"
        shutil.copyfile(DOCS / "config/cascade-contract.json", self.policy_path)
        self.policy = json.loads(self.policy_path.read_text())

    def run_guard(self, *, dependencies=None):
        return subprocess.run(["node", str(COMMAND), "--styles-dir", str(self.styles), "--policy", str(self.policy_path),
                               "--dependencies", str(dependencies or DEPENDENCIES)], cwd=ROOT, capture_output=True, text=True)

    def mutate(self, filename, old, new):
        source = self.styles / filename
        text = source.read_text()
        self.assertEqual(text.count(old), 1)
        source.write_text(text.replace(old, new))

    def save_policy(self):
        self.policy_path.write_text(json.dumps(self.policy) + "\n")

    def assert_guard_error(self, kind):
        result = self.run_guard()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        errors = [row for row in report["errors"] if row["kind"] == kind]
        self.assertTrue(errors, report)
        return errors

    def append(self, css):
        source = self.styles / "07-utilities.css"
        source.write_text(source.read_text() + "\n" + css + "\n")

    def test_actual_imported_styles_preserve_reviewed_exceptions_and_fallbacks(self):
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["styles"], len(self.policy["styles"]))
        self.assertEqual(report["important_declarations"], len(self.policy["important_exceptions"]))
        self.assertEqual(report["duplicate_fallbacks"], len(self.policy["duplicate_fallbacks"]))
        self.assertEqual(report["layer_strategy"], self.policy["layer_strategy"])
        self.assertEqual(report["import_graph"]["entry"], "extra.css")
        self.assertEqual([row["target"] for row in report["import_graph"]["edges"]], self.policy["styles"])
        self.assertEqual(set(report["source_files"]), {"extra.css", *self.policy["styles"]})
        self.assertFalse(any(row["file"] == "06-components.css" for row in self.policy["important_exceptions"]))
        self.assertTrue(any(row["kind"] == "viewport_fallback" for row in report["diagnostics"]))

    def test_footer_priorities_cannot_reclaim_normal_cascade_ownership(self):
        original = (DOCS / "styles/06-components.css").read_text()
        for selector, property_name, value in (
                (".md-footer__inner.bijux-footer-nav", "background", "transparent"),
                (".md-footer__inner.bijux-footer-nav", "display", "grid"),
                (".md-footer__inner.bijux-footer-nav .md-footer__link--prev", "margin", "0"),
                (".md-footer__inner.bijux-footer-nav .md-footer__link--next", "margin", "0")):
            with self.subTest(selector=selector, property=property_name):
                start = original.index(selector + " {")
                end = original.index("}", start)
                declaration = f"{property_name}: {value};"
                block = original[start:end]
                self.assertEqual(block.count(declaration), 1)
                (self.styles / "06-components.css").write_text(
                    original[:start] + block.replace(declaration, f"{property_name}: {value} !important;") + original[end:])
                error = self.assert_guard_error("unreviewed_important")[0]
                self.assertEqual((error["file"], error["selectors"], error["property"]),
                                 ("06-components.css", [selector], property_name))
                self.assertGreater(error["line"], 0)

    def test_layer_cannot_demote_existing_component_declarations_below_material(self):
        source = self.styles / "06-components.css"
        source.write_text("@layer bijux-components {\n" + source.read_text() + "\n}\n")
        error = self.assert_guard_error("unreviewed_layer")[0]
        self.assertEqual((error["file"], error["conditions"], error["value"]),
                         ("06-components.css", [], "@layer bijux-components"))
        self.assertGreater(error["line"], 0)
        self.assertGreater(error["column"], 0)

    def test_named_anonymous_ordered_and_nested_layers_require_explicit_ownership(self):
        original = (DOCS / "styles/07-utilities.css").read_text()
        for css, conditions in (
                ("@layer shell { .bijux-layer-example { color:inherit; } }", []),
                ("@layer { .bijux-layer-example { color:inherit; } }", []),
                ("@layer material, shell;", []),
                ("@layer/**/shell { .bijux-layer-example { color:inherit; } }", []),
                ("@media screen { @layer shell { .bijux-layer-example { color:inherit; } } }", ["@media screen"]),
                ("@supports (display:grid) { @layer shell; }", ["@supports (display:grid)"])):
            with self.subTest(css=css):
                (self.styles / "07-utilities.css").write_text(original)
                self.append(css)
                error = self.assert_guard_error("unreviewed_layer")[0]
                self.assertEqual(error["conditions"], conditions)
                self.assertIn("@layer", (self.styles / error["file"]).read_text().splitlines()[error["line"] - 1])

    def test_case_and_escape_equivalent_layer_keywords_cannot_bypass_ownership(self):
        original = (DOCS / "styles/07-utilities.css").read_text()
        for keyword in ["@LAYER", r"@\6c ayer", r"@la\79 er"]:
            with self.subTest(keyword=keyword):
                (self.styles / "07-utilities.css").write_text(original)
                self.append(f"{keyword} shell {{ .bijux-layer-example {{ color:inherit; }} }}")
                self.assert_guard_error("unreviewed_layer")

    def test_layer_text_in_comments_and_quoted_values_does_not_change_ownership(self):
        self.append('/* @layer shell { } */ .bijux-layer-example { --example:"@layer shell;"; content:"@layer"; }')
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_escaped_space_in_a_different_at_keyword_is_not_layer_ownership(self):
        self.append(r'@layer\20 shell { .bijux-layer-example { color:inherit; } }')
        self.append('@la/**/yer shell { .bijux-layer-example { color:inherit; } }')
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_layer_strategy_cannot_silently_admit_unreviewed_architecture(self):
        original = self.policy["layer_strategy"]
        for strategy in (None, {}, {**original, "mode": "layered"}, {**original, "owner": "consumer"},
                         {**original, "reason": " "}, {**original, "allowed_layers": ["shell"]}):
            with self.subTest(strategy=strategy):
                self.policy["layer_strategy"] = strategy
                self.save_policy()
                result = self.run_guard()
                self.assertEqual(result.returncode, 1)
                self.assertIn("malformed or unsupported layer_strategy", result.stderr)

    def test_missing_layer_strategy_is_not_an_implicit_permission(self):
        del self.policy["layer_strategy"]
        self.save_policy()
        result = self.run_guard()
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown or missing fields", result.stderr)

    def test_unknown_priority_reports_actual_selector_property_and_source_line(self):
        self.append(".bijux-header-tools { z-index:2147483647!important; }")
        error = self.assert_guard_error("unreviewed_important")[0]
        self.assertEqual((error["file"], error["selectors"], error["property"]),
                         ("07-utilities.css", [".bijux-header-tools"], "z-index"))
        self.assertIn("z-index", (self.styles / error["file"]).read_text().splitlines()[error["line"] - 1])
        self.assertGreater(error["column"], 0)

    def test_conflicting_duplicate_reports_both_values_and_source_locations(self):
        self.mutate("07-utilities.css", "outline-offset: 3px;", "outline-offset: 3px; outline-offset: 0;")
        error = self.assert_guard_error("unintended_duplicate")[0]
        self.assertEqual(error["values"], ["3px", "0"])
        self.assertIn(":focus-visible", " ".join(error["selectors"]))
        self.assertGreaterEqual(error["line"], error["earlier_line"])

    def test_case_and_escape_equivalent_properties_cannot_hide_duplicates(self):
        for property_name in ["OUTLINE-OFFSET", r"outline-\6f ffset"]:
            with self.subTest(property_name=property_name):
                source = DOCS / "styles/07-utilities.css"
                (self.styles / source.name).write_text(source.read_text())
                self.mutate(source.name, "outline-offset: 3px;", f"outline-offset: 3px; {property_name}: 0;")
                self.assertEqual(self.assert_guard_error("unintended_duplicate")[0]["property"], "outline-offset")

    def test_native_priority_spellings_cannot_bypass_new_exception_review(self):
        for priority in ["!IMPORTANT", "! important", "!/**/important", r"!\69mportant"]:
            with self.subTest(priority=priority):
                (self.styles / "07-utilities.css").write_text((DOCS / "styles/07-utilities.css").read_text())
                self.append(f".bijux-header-tools {{ z-index:2147483647{priority}; }}")
                self.assert_guard_error("unreviewed_important")

    def test_quoted_or_function_argument_important_text_is_not_priority(self):
        self.append('.bijux-cascade-example { --quoted:"!important;"; background:url("!important"); }')
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_escaped_custom_properties_retain_native_case_sensitive_identity(self):
        self.append(r'.bijux-cascade-example { --Identity:orange; \2d \2d identity:teal; }')
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exception_cannot_allow_additional_identical_priority_use(self):
        self.append('.md-visually-hidden { position:absolute!important; }')
        self.assert_guard_error("repeated_important_exception")

    def test_hidden_display_cannot_be_waived_by_altered_exception_policy(self):
        self.mutate("07-utilities.css", "display: none !important;", "display: flex !important;")
        for row in self.policy["important_exceptions"]:
            if row["file"] == "07-utilities.css" and row["property"] == "display":
                row["value"] = "flex!important"
        self.save_policy()
        self.assert_guard_error("semantic_hidden_invariant")

    def test_missing_hidden_rule_remains_an_invariant_even_without_allowlist_entry(self):
        self.mutate("07-utilities.css", '[hidden]:not([hidden="until-found"]) {\n  display: none !important;\n}', "")
        self.policy["important_exceptions"] = [row for row in self.policy["important_exceptions"]
                                               if not (row["file"] == "07-utilities.css" and row["property"] == "display")]
        self.save_policy()
        self.assert_guard_error("semantic_hidden_invariant")

    def test_missing_known_priority_exception_is_not_silently_baselined(self):
        self.policy["important_exceptions"].pop()
        self.save_policy()
        self.assert_guard_error("unreviewed_important")

    def test_stale_priority_identity_requires_review_instead_of_unused_permission(self):
        self.policy["important_exceptions"][0]["value"] = "black!important"
        self.save_policy()
        self.assert_guard_error("stale_important_exception")

    def test_duplicate_policy_identity_is_rejected(self):
        self.policy["important_exceptions"].append(self.policy["important_exceptions"][0])
        self.save_policy()
        result = self.run_guard()
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate important_exceptions identity", result.stderr)

    def test_unknown_policy_fields_cannot_enable_an_unbounded_allowance(self):
        self.policy["allow_all_important"] = True
        self.save_policy()
        result = self.run_guard()
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown or missing fields", result.stderr)

    def test_exception_without_ownership_reason_is_rejected(self):
        self.policy["important_exceptions"][0]["reason"] = ""
        self.save_policy()
        result = self.run_guard()
        self.assertEqual(result.returncode, 1)
        self.assertIn("malformed important_exceptions", result.stderr)

    def test_changed_and_reversed_viewport_fallbacks_are_not_generic_duplicate_exceptions(self):
        original = (DOCS / "styles/08-responsive.css").read_text()
        pair = "max-height: calc(100vh - var(--md-header-height, 3rem));\n    max-height: calc(100dvh - var(--md-header-height, 3rem));"
        for replacement in [pair.replace("100dvh", "90dvh"),
                            "max-height: calc(100dvh - var(--md-header-height, 3rem));\n    max-height: calc(100vh - var(--md-header-height, 3rem));"]:
            with self.subTest(replacement=replacement):
                (self.styles / "08-responsive.css").write_text(original)
                self.mutate("08-responsive.css", pair, replacement)
                self.assert_guard_error("unintended_duplicate")
                self.assert_guard_error("stale_duplicate_fallback")

    def test_omitted_imported_sheet_fails_before_declaration_qualification(self):
        self.mutate("extra.css", '@import url("./01-theme.css");\n', "")
        result = self.run_guard()
        self.assertEqual(result.returncode, 1)
        self.assertIn("import order differs", result.stderr)

    def test_domain_import_cannot_hide_priority_outside_the_reviewed_source_graph(self):
        source = self.styles / "02-layout.css"
        source.write_text('@import url("./unreviewed-components.css");\n' + source.read_text())
        (self.styles / "unreviewed-components.css").write_text('.md-footer__inner.bijux-footer-nav { display:flex!important; }\n')
        result = self.run_guard()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["stage"], "import_graph")
        self.assertEqual(report["declarations"], 0)
        self.assertNotIn("unreviewed-components.css", report["source_files"])
        error = next(row for row in report["errors"] if row["kind"] == "unreviewed_import")
        self.assertEqual((error["file"], error["conditions"], error["line"]), ("02-layout.css", [], 1))
        self.assertIn("unreviewed-components.css", error["value"])

    def test_import_keyword_forms_and_conditions_cannot_open_a_domain_leaf(self):
        original = (DOCS / "styles/02-layout.css").read_text()
        for css in ('@IMPORT url("./unreviewed.css");', r'@\69mport url("./unreviewed.css");',
                    r'@\69 mport url("./unreviewed.css");', '@import/**/url("./unreviewed.css");',
                    '@import "./unreviewed.css";', '@import url(./unreviewed.css);',
                    '@import url("./unreviewed.css") screen;', '@import url("./unreviewed.css") supports(display:grid);',
                    '@import url("./unreviewed.css") layer(shell);', '@media screen { @import "./unreviewed.css"; }'):
            with self.subTest(css=css):
                (self.styles / "02-layout.css").write_text(css + "\n" + original)
                error = self.assert_guard_error("unreviewed_import")[0]
                self.assertEqual(error["file"], "02-layout.css")
                self.assertGreater(error["line"], 0)
                self.assertEqual(error["conditions"], ["@media screen"] if css.startswith("@media") else [])

    def test_import_text_in_comments_and_quoted_declarations_is_inert(self):
        self.append('/* @import url("./unreviewed.css"); */ .bijux-import-example { --example:"@import url(../unreviewed.css);"; }')
        self.append(r'@import\20 url("./unreviewed.css");')
        self.append('@im/**/port url("./unreviewed.css");')
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unknown_local_remote_data_duplicate_and_cyclic_domain_edges_are_refused(self):
        original = (DOCS / "styles/02-layout.css").read_text()
        for url in ('./06-components.css', './02-layout.css', '../unreviewed.css', '/unreviewed.css',
                    'https://styles.example.invalid/unreviewed.css', '//styles.example.invalid/unreviewed.css',
                    'data:text/css,.md-footer__inner%7Bdisplay:flex%7D', './%2e%2e/unreviewed.css'):
            with self.subTest(url=url):
                (self.styles / "02-layout.css").write_text(f'@import url("{url}");\n' + original)
                error = self.assert_guard_error("unreviewed_import")[0]
                self.assertEqual(error["line"], 1)

    def test_entry_cannot_replace_canonical_edges_with_external_or_traversing_resources(self):
        original = (DOCS / "styles/extra.css").read_text()
        for url in ('../00-tokens.css', './%30%30-tokens.css', '/00-tokens.css', 'https://styles.example.invalid/00-tokens.css'):
            with self.subTest(url=url):
                (self.styles / "extra.css").write_text(original.replace('./00-tokens.css', url))
                result = self.run_guard()
                self.assertEqual(result.returncode, 1)
                self.assertIn("canonical local stylesheet imports", result.stderr)

    def test_entry_conditions_cannot_demote_or_disable_a_canonical_sheet(self):
        original = (DOCS / "styles/extra.css").read_text()
        for condition in ('screen', 'supports(display:grid)', 'layer(shell)'):
            with self.subTest(condition=condition):
                (self.styles / "extra.css").write_text(original.replace('@import url("./06-components.css");',
                                                                         f'@import url("./06-components.css") {condition};'))
                result = self.run_guard()
                self.assertEqual(result.returncode, 1)
                self.assertIn("canonical local stylesheet imports", result.stderr)

    def test_canonical_sheet_must_not_link_to_an_unowned_resource(self):
        source = self.styles / "02-layout.css"
        external = self.case / "external.css"
        external.write_text(source.read_text())
        source.unlink()
        source.symlink_to(external)
        result = self.run_guard()
        self.assertEqual(result.returncode, 1)
        self.assertIn("owned regular file without linked path components", result.stderr)

    def test_unselected_consumer_styles_do_not_become_shared_graph_ownership(self):
        (self.styles / "consumer.css").write_text('@import url("https://styles.example.invalid/consumer.css");\n'
                                                '@layer consumer { .consumer { color:teal!important; } }\n')
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_import_policy_cannot_silently_enable_arbitrary_graph_traversal(self):
        original = self.policy["import_graph"]
        for graph in (None, {}, {**original, "entry": "../extra.css"}, {**original, "mode": "recursive"},
                      {**original, "owner": "consumer"}, {**original, "reason": " "}, {**original, "allow_remote": True}):
            with self.subTest(graph=graph):
                self.policy["import_graph"] = graph
                self.save_policy()
                result = self.run_guard()
                self.assertEqual(result.returncode, 1)
                self.assertIn("malformed or unsupported import_graph", result.stderr)

    def test_missing_import_graph_is_not_implicit_traversal_authority(self):
        del self.policy["import_graph"]
        self.save_policy()
        result = self.run_guard()
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown or missing fields", result.stderr)

    def test_missing_imported_file_fails(self):
        (self.styles / "01-theme.css").unlink()
        result = self.run_guard()
        self.assertEqual(result.returncode, 1)
        self.assertIn("01-theme.css", result.stderr)

    def test_conditional_priority_cannot_reuse_an_unconditional_exception(self):
        self.append('@media screen { [hidden]:not([hidden="until-found"]) { display:none!important; } }')
        error = self.assert_guard_error("unreviewed_important")[0]
        self.assertEqual(error["conditions"], ["@media screen"])

    def parser_copy(self):
        destination = self.case / "dependencies"
        destination.mkdir()
        for name in ["package.json", "package-lock.json"]:
            shutil.copyfile(DEPENDENCIES / name, destination / name)
        package = destination / "node_modules/stylis/package.json"
        package.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DEPENDENCIES / "node_modules/stylis/package.json", package)
        provenance = json.loads((DOCS / "tooling/diagrams/provenance.json").read_text())
        for row in provenance["bundled_inputs"]:
            if row["path"].startswith("node_modules/stylis/"):
                target = destination / row["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(DEPENDENCIES / row["path"], target)
        return destination

    def test_changed_parser_source_fails_before_import(self):
        dependencies = self.parser_copy()
        source = dependencies / "node_modules/stylis/src/Parser.js"
        source.write_text(source.read_text() + "\nthrow new Error('unowned parser executed');\n")
        result = self.run_guard(dependencies=dependencies)
        self.assertEqual(result.returncode, 1)
        self.assertIn("changed admitted parser source", result.stderr)
        self.assertNotIn("unowned parser executed", result.stderr)

    def test_foreign_install_lock_fails_before_import(self):
        dependencies = self.parser_copy()
        lock = dependencies / "package-lock.json"
        lock.write_text(lock.read_text() + "\n")
        result = self.run_guard(dependencies=dependencies)
        self.assertEqual(result.returncode, 1)
        self.assertIn("installed diagram manifest differs", result.stderr)

    def test_wrong_installed_parser_identity_fails(self):
        dependencies = self.parser_copy()
        package = dependencies / "node_modules/stylis/package.json"
        metadata = json.loads(package.read_text())
        metadata["version"] = "3.0.0"
        package.write_text(json.dumps(metadata))
        result = self.run_guard(dependencies=dependencies)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Installed Stylis parser identity differs", result.stderr)


if __name__ == "__main__":
    unittest.main()
