from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PYTHON_MAKE_ROOT = REPOSITORY_ROOT / "shared/bijux-makes-py"


class PythonMakeFailureContractTests(unittest.TestCase):
    def test_recursive_targets_stop_after_the_first_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            marker = fixture / "unexpected-success"
            makefile = fixture / "Makefile"
            makefile.write_text(
                "\n".join(
                    (
                        f"include {PYTHON_MAKE_ROOT / 'ci/util.mk'}",
                        ".PHONY: all fail pass",
                        "all:",
                        "\t$(call run_make_targets,fail pass,$(MAKE))",
                        "fail:",
                        "\t@exit 7",
                        "pass:",
                        f"\t@touch {marker}",
                    )
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                ["make", "-f", str(makefile), "all"],
                cwd=fixture,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())

    def test_package_build_cannot_report_success_after_builder_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            package = fixture / "package"
            package.mkdir()
            package.joinpath("pyproject.toml").write_text(
                """\
[build-system]
requires = []
build-backend = "missing.backend"
""",
                encoding="utf-8",
            )
            makefile = fixture / "Makefile"
            makefile.write_text(
                f"include {PYTHON_MAKE_ROOT / 'ci/build.mk'}\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "make",
                    "-f",
                    str(makefile),
                    "build-package",
                    "BUILD_PRE_TARGETS=",
                    "BUILD_POST_TARGETS=",
                    "BUILD_TOOLS_COMMAND=true",
                    "BUILD_PYTHON=false",
                    "BUILD_CHECK_DISTS=0",
                    f"PACKAGE_DIR={package}",
                    "VENV_PYTHON=/usr/bin/true",
                    f"PROJECT_ARTIFACTS_DIR={fixture / 'artifacts'}",
                ],
                cwd=fixture,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Package artifacts ready", result.stdout)


if __name__ == "__main__":
    unittest.main()
