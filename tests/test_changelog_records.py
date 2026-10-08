from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("changelog_records", ROOT / ".github/scripts/changelog.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ARTIFACTS = ROOT / "artifacts/qualification/changelog-contract/process"


def record(number=12):
    return {"schema": 1, "pr": number, "title": "fix(docs): retain readable search counts", "type": "fix", "scope": "docs", "summary": "Readers can distinguish the current search result count.", "details": ["Qualify actual text and backgrounds across the admitted engine matrix."], "status": "pending", "merged_at": None, "breaking": False}


class ChangeRecordTests(unittest.TestCase):
    def setUp(self):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=ARTIFACTS)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "changelog/fragments/docs").mkdir(parents=True)
        (self.root / "changelog/config.json").write_text(json.dumps({"schema": 1, "repository": "bijux/example", "mode": "pr-history"}))
        self.path = self.root / "changelog/fragments/docs/search-counts.json"
        self.write(record())

    def write(self, value, path=None):
        (path or self.path).write_text(json.dumps(value), encoding="utf-8")

    def cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return MODULE.main(["--root", str(self.root), *args])

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True, stderr=subprocess.DEVNULL).strip()

    def base(self, existing=False):
        self.git("init", "--quiet")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Bijux change-record fixture")
        if not existing:
            self.path.unlink()
        self.git("add", "changelog/config.json")
        if existing:
            self.git("add", str(self.path.relative_to(self.root)))
        self.git("commit", "--quiet", "-m", "test(governance): admit isolated fixture history")
        return self.git("rev-parse", "HEAD")

    def test_final_record_and_projection_are_deterministic(self):
        self.assertEqual(self.cli("validate"), 0)
        self.assertEqual(MODULE.project(self.root), MODULE.project(self.root))
        self.assertIn("https://github.com/bijux/example/pull/12", MODULE.project(self.root))

    def test_history_header_leads_directly_to_pr_sections(self):
        text = MODULE.project(self.root)
        self.assertTrue(text.startswith("# Changelog\n\nThis file records notable repository-level changes for `example`.\n\n## Pull request history\n\n### Pending review\n\n"))
        self.assertNotIn("projected from", text)
        self.assertNotIn("Records describe", text)

    def test_draft_identity_is_explicit_and_cannot_project(self):
        self.write(record(None))
        self.assertEqual(self.cli("validate"), 1)
        self.assertEqual(self.cli("validate", "--draft"), 0)
        self.assertEqual(self.cli("render"), 1)

    def test_assign_binds_actual_number_and_rejects_reassignment(self):
        self.write(record(None))
        path = str(self.path.relative_to(self.root))
        self.assertEqual(self.cli("assign", "--fragment", path, "--pr", "31"), 0)
        self.assertEqual(MODULE.read_json(self.path)["pr"], 31)
        self.assertEqual(self.cli("assign", "--fragment", path, "--pr", "32"), 1)

    def test_duplicate_pr_is_not_admitted(self):
        self.write(record(), self.path.with_name("query-focus.json"))
        self.assertEqual(self.cli("validate"), 1)

    def test_wrong_scope_and_non_durable_paths_are_rejected(self):
        for path in ["query.json", "other/query.json", "docs/iteration07.json", "docs/nested/query.json"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                MODULE.validate_record(record(), Path(path))

    def test_missing_unknown_and_duplicate_keys_fail(self):
        value = record(); del value["details"]; self.write(value)
        self.assertEqual(self.cli("validate"), 1)
        value = record(); value["actor_exemption"] = True; self.write(value)
        self.assertEqual(self.cli("validate"), 1)
        self.path.write_text('{"schema": 1, "schema": 1}')
        self.assertEqual(self.cli("validate"), 1)

    def test_empty_malformed_and_multiline_content_fails(self):
        controls = [("summary", ""), ("summary", "   "), ("summary", "two\nlines"), ("title", ""), ("details", []), ("details", [""]), ("details", "text"), ("pr", True), ("pr", 0), ("schema", True), ("breaking", 0)]
        for key, value in controls:
            with self.subTest(key=key, value=value):
                item = record(); item[key] = value; self.write(item)
                self.assertEqual(self.cli("validate"), 1)

    def test_pending_title_exact_type_scope_and_breaking_contract(self):
        for title in ["adjust records", "feat(docs): readable counts", "fix(ci): readable counts", "fix(docs)!: readable counts"]:
            with self.subTest(title=title):
                item = record(); item["title"] = title; self.write(item)
                self.assertEqual(self.cli("validate"), 1)

    def test_historical_title_is_retained_without_fabricated_date(self):
        item = record(); item.update(title="Original historic pull request title", status="merged")
        self.write(item); text = MODULE.project(self.root)
        self.assertIn(item["title"], text)
        self.assertIn("unverified dates", text)
        self.assertNotIn("None", text)

    def test_newest_pr_identity_leads_without_rewriting_actual_merge_dates(self):
        old = record(99); old.update(status="merged", merged_at="2026-01-01T12:00:00Z"); self.write(old)
        recent = record(1); recent.update(status="merged", merged_at="2026-02-01T12:00:00Z"); self.write(recent, self.path.with_name("drawer-focus.json"))
        text = MODULE.project(self.root)
        self.assertLess(text.index("[#99]"), text.index("[#1]"))
        self.assertIn("2026-01-01T12:00:00Z — [#99]", text)
        self.assertIn("2026-02-01T12:00:00Z — [#1]", text)

    def test_each_review_status_section_orders_newest_pr_first(self):
        self.path.unlink()
        for status, stamp, numbers in (("pending", None, [12, 9]), ("merged", "2026-01-01T12:00:00Z", [8, 10]), ("merged", None, [4, 6])):
            for number in numbers:
                item = record(number); item.update(status=status, merged_at=stamp)
                self.write(item, self.path.with_name(f"search-count-{number}.json"))
        text = MODULE.project(self.root)
        positions = [text.index(f"[#{number}]") for number in [12, 9, 10, 8, 6, 4]]
        self.assertEqual(positions, sorted(positions))

    def test_pending_dates_and_malformed_historical_dates_fail(self):
        for status, stamp in [("pending", "2026-01-01T12:00:00Z"), ("merged", "2026-02-30T12:00:00Z"), ("merged", "2026-01-01T12:00:00+00:00"), ("merged", "2999-01-01T12:00:00Z")]:
            item = record(); item.update(status=status, merged_at=stamp); self.write(item)
            self.assertEqual(self.cli("validate"), 1)

    def test_append_mode_preserves_package_history_exactly(self):
        config = MODULE.configuration(self.root); config["mode"] = "append"
        self.write(config, self.root / "changelog/config.json")
        before = "# Package releases\n\n## 1.2.3\n\n- Exact existing release.\n\n"
        after = "\n## Older release\n\n- Also retained.\n"
        (self.root / "CHANGELOG.md").write_text(before + MODULE.START + "\nobsolete projection\n" + MODULE.END + after)
        output = MODULE.project(self.root)
        self.assertTrue(output.startswith(before + MODULE.START))
        self.assertTrue(output.endswith(MODULE.END + after))
        self.assertNotIn("obsolete projection", output)

    def test_append_missing_duplicate_or_reversed_markers_fail(self):
        config = MODULE.configuration(self.root); config["mode"] = "append"; self.write(config, self.root / "changelog/config.json")
        for text in ["# Existing package changelog", MODULE.START * 2 + MODULE.END, MODULE.END + MODULE.START]:
            (self.root / "CHANGELOG.md").write_text(text)
            self.assertEqual(self.cli("render"), 1)

    def test_foundation_archive_remains_separate_from_pr_projection(self):
        foundation = self.root / "changelog/FOUNDATION.md"
        foundation.write_text("# Audited source material\n\nA fact without an independently verified PR.\n")
        text = MODULE.project(self.root)
        self.assertNotIn("foundation", text.lower())
        self.assertNotIn("A fact without", text)
        foundation.unlink(); foundation.symlink_to(self.path)
        self.assertEqual(self.cli("render"), 1)

    def test_stale_projection_fails_check_then_regeneration_passes(self):
        (self.root / "CHANGELOG.md").write_text("# Old projection\n")
        self.assertEqual(self.cli("render", "--check"), 1)
        self.assertEqual(self.cli("render", "--write"), 0)
        self.assertEqual(self.cli("render", "--check"), 0)

    def test_preview_output_stays_in_artifacts_and_escapes_active_markup(self):
        item = record(); item["summary"] = '<script>alert("x")</script> [destination](javascript:alert)'; self.write(item)
        self.assertEqual(self.cli("render"), 0)
        preview = (self.root / "artifacts/changelog/CHANGELOG.md").read_text()
        self.assertNotIn("<script>", preview)
        self.assertIn("&lt;script&gt;", preview)
        self.assertEqual(self.cli("render", "--output", "../escaped.md"), 1)

    def test_symlink_fragment_and_unknown_files_fail(self):
        self.path.with_name("alias.json").symlink_to(self.path)
        self.assertEqual(self.cli("validate"), 1)
        self.path.with_name("alias.json").unlink()
        self.path.with_name("extra.txt").write_text("unexpected")
        self.assertEqual(self.cli("validate"), 1)

    def test_actual_git_review_requires_exact_changed_tracked_record(self):
        base = self.base(); self.write(record()); self.git("add", str(self.path.relative_to(self.root)))
        MODULE.check_pr(self.root, 12, base, record()["title"])
        with self.assertRaisesRegex(ValueError, "Missing exact"):
            MODULE.check_pr(self.root, 13, base)
        with self.assertRaisesRegex(ValueError, "actual PR title"):
            MODULE.check_pr(self.root, 12, base, "fix(docs): another title")

    def test_existing_or_untracked_record_is_not_current_review_evidence(self):
        base = self.base(existing=True)
        with self.assertRaisesRegex(ValueError, "tracked fragment"):
            MODULE.check_pr(self.root, 12, base)
        extra = record(13); self.write(extra, self.path.with_name("untracked-query.json"))
        with self.assertRaisesRegex(ValueError, "tracked fragment"):
            MODULE.check_pr(self.root, 13, base)

    def test_reassigning_prior_history_is_not_a_valid_new_record(self):
        base = self.base(existing=True)
        self.write(record(13)); self.git("add", str(self.path.relative_to(self.root)))
        with self.assertRaisesRegex(ValueError, "removed or reassigned"):
            MODULE.check_pr(self.root, 13, base)

    def test_event_binds_actual_number_title_and_base(self):
        base = self.base(); self.write(record()); self.git("add", str(self.path.relative_to(self.root)))
        self.cli("render", "--write")
        event = self.root / "event.json"
        payload = {"number": 12, "pull_request": {"number": 12, "title": record()["title"], "base": {"sha": base}}}
        self.write(payload, event)
        self.assertIn("passed", MODULE.check_event(self.root, event, "pull_request", "bijux/example"))
        for key, value in [("number", 13), ("title", None), ("title", "fix(docs): wrong actual title")]:
            changed = copy.deepcopy(payload)
            if key == "number": changed[key] = value
            else: changed["pull_request"][key] = value
            self.write(changed, event)
            with self.assertRaises(ValueError): MODULE.check_event(self.root, event, "pull_request", "bijux/example")

    def test_unadopted_consumer_is_explicit_but_std_cannot_bypass(self):
        (self.root / "changelog/config.json").unlink()
        self.assertIn("Not adopted", MODULE.check_event(self.root, self.root / "absent.json", "push", "bijux/example"))
        with self.assertRaisesRegex(ValueError, "requires its changelog"):
            MODULE.check_event(self.root, self.root / "absent.json", "push", "bijux/bijux-std")

    def test_broken_config_link_does_not_become_an_adoption_exemption(self):
        path = self.root / "changelog/config.json"
        path.unlink(); path.symlink_to(self.root / "missing-config.json")
        with self.assertRaises(ValueError):
            MODULE.check_event(self.root, self.root / "event.json", "push", "bijux/example")

    def test_shared_distribution_and_source_manifest_ownership_match(self):
        self.assertEqual((ROOT / ".github/scripts/changelog.py").read_bytes(), (ROOT / "shared/bijux-gh/scripts/changelog.py").read_bytes())
        self.assertIn('(".github/scripts/changelog.py", ".github/scripts/changelog.py")', (ROOT / ".github/scripts/sync_github_standards.py").read_text())
        self.assertIn('.github/scripts/changelog.py', (ROOT / ".github/scripts/check_protected_github_changes.py").read_text())
