"""Bind generated scenarios to actual renderer configuration bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import build as fixtures
from fixture_archive import configurations_digest, manifest_sites, validate_configurations

ROOT = Path(__file__).resolve().parents[3]


class FixtureConfigurationTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "artifacts/qualification/fixture-configuration/controls"
        parent.mkdir(parents=True, exist_ok=True)
        scratch = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(scratch.cleanup)
        self.output = Path(scratch.name)
        self.config = self.output / "inputs/hub/mkdocs.yml"
        self.config.parent.mkdir(parents=True)
        self.config.write_text("site_name: Exact reader\n")
        self.log = self.output / "render.log"

    def scenario(self, route="/", configuration=None):
        return {"identity": "bijux", "route": route, "kind": "hub",
                "configuration": configuration or fixtures.capture_configuration(self.config, self.output)}

    def manifest(self):
        scenarios = [self.scenario()]
        return {"scenarios": scenarios, "configurations_sha256": configurations_digest(scenarios),
                "site_files": {"index.html": "a" * 64}, "source_files": {"config/source.json": "b" * 64}}

    def test_record_captures_exact_yaml_bytes_not_recipe_or_toolchain(self):
        before = fixtures.capture_configuration(self.config, self.output)
        self.assertEqual(before, {"path": "inputs/hub/mkdocs.yml", "bytes": self.config.stat().st_size,
                                 "sha256": hashlib.sha256(self.config.read_bytes()).hexdigest()})
        self.config.write_text("site_name: Different reader\n")
        self.assertNotEqual(fixtures.capture_configuration(self.config, self.output)["sha256"], before["sha256"])

    def test_actual_mkdocs_renderer_keeps_the_captured_configuration(self):
        docs = self.output / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("# Exact reader\n")
        self.config.write_text(json.dumps({"site_name": "Exact reader", "site_url": "https://bijux.io/",
                                         "docs_dir": str(docs), "site_dir": str(self.output / "site"),
                                         "theme": {"name": "material", "font": False}, "plugins": ["search"]}))
        before = fixtures.capture_configuration(self.config, self.output)
        self.assertEqual(fixtures.render_configuration(self.config, self.output, self.log), before)
        self.assertTrue((self.output / "site/index.html").is_file())

    def test_successful_child_mutating_configuration_cannot_qualify(self):
        original = subprocess.run
        def mutate(_command, **kwargs):
            return original([sys.executable, "-B", "-c",
                             "from pathlib import Path;import sys;Path(sys.argv[1]).write_text('site_name: Mutated reader\\n')", str(self.config)], **kwargs)
        with patch.object(fixtures.subprocess, "run", side_effect=mutate):
            with self.assertRaisesRegex(RuntimeError, "configuration changed while rendering"):
                fixtures.render_configuration(self.config, self.output, self.log)

    def test_missing_config_after_successful_child_is_rejected(self):
        with patch.object(fixtures.subprocess, "run", side_effect=lambda *_args, **_kwargs: self.config.unlink()):
            with self.assertRaises(OSError):
                fixtures.render_configuration(self.config, self.output, self.log)

    def test_symlink_configuration_is_rejected_before_renderer(self):
        actual = self.config.with_name("authored.yml")
        self.config.rename(actual)
        self.config.symlink_to(actual)
        with patch.object(fixtures.subprocess, "run") as render:
            with self.assertRaises(OSError):
                fixtures.render_configuration(self.config, self.output, self.log)
            render.assert_not_called()

    def test_failed_preflight_removes_previous_success_manifest(self):
        manifest = self.output / "manifest.json"
        manifest.write_text('{"previous": "successful"}')
        source = self.output / "shared"
        source.mkdir()
        with patch.object(fixtures.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "renderer")):
            with self.assertRaises(subprocess.CalledProcessError):
                fixtures.build(source, self.output, "http://127.0.0.1:4173")
        self.assertFalse(manifest.exists())

    def test_later_scenario_cannot_change_an_earlier_configuration(self):
        scenarios = [self.scenario()]
        self.config.write_text("site_name: Changed after rendering\n")
        with self.assertRaisesRegex(RuntimeError, "configuration changed before manifest"):
            fixtures.verify_configuration_sources(self.output, scenarios)

    def test_aggregate_is_deterministic_for_record_order(self):
        record = {"path": "inputs/κόσμος/mkdocs.yml", "sha256": "a" * 64, "bytes": 42}
        scenarios = [self.scenario(), self.scenario("/κόσμος/", record)]
        self.assertEqual(configurations_digest(scenarios), configurations_digest(list(reversed(scenarios))))

    def test_missing_malformed_and_changed_configuration_metadata_rejects_transport(self):
        mutations = [lambda value: value.pop("configurations_sha256"),
                     lambda value: value.update(configurations_sha256="A" * 64),
                     lambda value: value["scenarios"][0].pop("configuration"),
                     lambda value: value["scenarios"][0]["configuration"].update(sha256="bad"),
                     lambda value: value["scenarios"][0]["configuration"].update(bytes=True),
                     lambda value: value["scenarios"][0]["configuration"].update(path="../mkdocs.yml"),
                     lambda value: value["scenarios"].append(value["scenarios"][0]),
                     lambda value: value["scenarios"][0]["configuration"].update(sha256="f" * 64)]
        for mutate in mutations:
            value = self.manifest()
            mutate(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                manifest_sites(json.dumps(value).encode())
        self.assertEqual(validate_configurations(self.manifest()), self.manifest()["configurations_sha256"])


if __name__ == "__main__":
    unittest.main()
