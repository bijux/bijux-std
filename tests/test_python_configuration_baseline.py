from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY_ROOT / "shared/bijux-makes-py/repository/configuration_baseline.py"
BASELINE_PATH = REPOSITORY_ROOT / "shared/bijux-makes-py/config/python-baseline.toml"


def load_validator_module():
    module_name = "configuration_baseline"
    spec = importlib.util.spec_from_file_location(module_name, VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class PythonConfigurationBaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_validator_module()
        self.fixture = Path(tempfile.mkdtemp())
        (self.fixture / "packages/example").mkdir(parents=True)
        (self.fixture / "pyproject.toml").write_text(
            """\
[project]
name = "fixture"
version = "0.0.0"
requires-python = ">=3.11,<4"
dependencies = []
""",
            encoding="utf-8",
        )
        (self.fixture / "packages/example/pyproject.toml").write_text(
            """\
[project]
name = "example"
version = "0.0.0"
requires-python = ">=3.11,<4"

[project.optional-dependencies]
dev = ["ruff>=0.13,<1.0", "mypy>=1.18,<3.0", "pytest>=9,<10"]
""",
            encoding="utf-8",
        )
        (self.fixture / "configs").mkdir()
        (self.fixture / "configs/package.json").write_text(
            json.dumps(
                {
                    "name": "bijux-openapi-tooling",
                    "private": True,
                    "engines": {"node": ">=22.12.0"},
                    "devDependencies": {
                        "@openapitools/openapi-generator-cli": "2.40.1",
                        "@redocly/cli": "2.41.0",
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.fixture / "tox.ini").write_text(
            """\
[tox]
minversion = 4.11
requires =
    tox>=4.11,<5
    tox-gh-actions>=3.1,<4
isolated_build = true
skip_missing_interpreters = true
toxworkdir = {tox_root}/artifacts/root/tox

[testenv]
package = skip
basepython = python3.11
skip_install = true
setenv =
    PIP_DISABLE_PIP_VERSION_CHECK = 1
    PYTHONDONTWRITEBYTECODE = 1
""",
            encoding="utf-8",
        )

    def validate(self) -> list[str]:
        return self.module.BaselineValidator(self.fixture, BASELINE_PATH).validate()

    def test_accepts_repository_owned_configuration_inside_shared_envelopes(self) -> None:
        self.assertEqual(self.validate(), [])

    def test_rejects_unbounded_python_and_tool_support(self) -> None:
        path = self.fixture / "packages/example/pyproject.toml"
        path.write_text(
            path.read_text(encoding="utf-8")
            .replace('requires-python = ">=3.11,<4"', 'requires-python = ">=3.11"')
            .replace('"ruff>=0.13,<1.0"', '"ruff>=0.13"'),
            encoding="utf-8",
        )

        errors = self.validate()

        self.assertTrue(any("requires-python" in error for error in errors))
        self.assertTrue(any("ruff" in error for error in errors))

    def test_rejects_repository_specific_openapi_identity(self) -> None:
        package_json = self.fixture / "configs/package.json"
        document = json.loads(package_json.read_text(encoding="utf-8"))
        document["name"] = "product-openapi-tooling"
        package_json.write_text(json.dumps(document), encoding="utf-8")

        self.assertTrue(any("name must be" in error for error in self.validate()))

    def test_rejects_tox_state_outside_artifacts(self) -> None:
        tox_path = self.fixture / "tox.ini"
        tox_path.write_text(
            tox_path.read_text(encoding="utf-8").replace(
                "{tox_root}/artifacts/root/tox",
                "{tox_root}/.tox",
            ),
            encoding="utf-8",
        )

        self.assertTrue(any("toxworkdir" in error for error in self.validate()))

    def test_ignores_generated_project_manifests(self) -> None:
        generated = self.fixture / "artifacts/generated"
        generated.mkdir(parents=True)
        generated.joinpath("pyproject.toml").write_text(
            """\
[project]
name = "generated"
version = "0.0.0"
requires-python = ">=3.8"
""",
            encoding="utf-8",
        )

        self.assertEqual(self.validate(), [])


if __name__ == "__main__":
    unittest.main()
