from __future__ import annotations

from pathlib import Path
import subprocess
import sys
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


    def test_distribution_validation_preserves_failure_status_and_output(self) -> None:
        for target in ("build", "build-package", "build-check"):
            for shell in ("/bin/sh", "/bin/bash"):
                for checker_status in (0, 7):
                    with self.subTest(target=target, shell=shell, status=checker_status):
                        with tempfile.TemporaryDirectory() as directory:
                            fixture = Path(directory)
                            package = fixture / "package"
                            package.mkdir()
                            (package / "pyproject.toml").write_text("[project]\nname = 'fixture'\n")
                            output = fixture / "artifacts/build"
                            output.mkdir(parents=True)
                            (output / "fixture package.whl").touch()
                            (output / "fixture package.tar.gz").touch()
                            marker = fixture / "post-build-ran"
                            checker = fixture / "python"
                            checker.write_text(
                                f"#!{sys.executable}\n"
                                "import sys\n"
                                "if sys.argv[1:3] == ['-m', 'twine']:\n"
                                "    print('distribution validator stdout', flush=True)\n"
                                "    print('distribution validator stderr', file=sys.stderr, flush=True)\n"
                                f"    sys.exit({checker_status})\n"
                            )
                            checker.chmod(0o755)
                            makefile = fixture / "Makefile"
                            makefile.write_text(
                                f"include {PYTHON_MAKE_ROOT / 'ci/build.mk'}\n"
                                ".PHONY: post-build\n"
                                f"post-build:\n\t@touch {marker}\n"
                            )
                            result = subprocess.run(
                                [
                                    "make", "-f", str(makefile), target,
                                    f"SHELL={shell}", ".SHELLFLAGS=-c",
                                    "BUILD_TOOLS_COMMAND=true", "VENV_PYTHON=/usr/bin/true",
                                    f"BUILD_PYTHON={checker}", f"PACKAGE_DIR={package}",
                                    f"BUILD_PACKAGE_DIR={package}",
                                    f"PROJECT_ARTIFACTS_DIR={fixture / 'artifacts'}",
                                    "BUILD_POST_TARGETS=post-build", "BUILD_TEMP_CLEAN_PATHS=",
                                ],
                                cwd=fixture, check=False, capture_output=True, text=True,
                            )
                            log = (output / "twine-check.log").read_text()
                            for message in ("distribution validator stdout", "distribution validator stderr"):
                                self.assertIn(message, log)
                                self.assertIn(message, result.stdout)
                            if checker_status:
                                self.assertNotEqual(result.returncode, 0)
                                self.assertNotIn("Package artifacts ready", result.stdout)
                                self.assertFalse(marker.exists())
                            else:
                                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                                self.assertEqual(marker.exists(), target != "build-check")

    def test_distribution_validation_rejects_an_unwritable_log(self) -> None:
        for target in ("build-package", "build-check"):
            with self.subTest(target=target):
                with tempfile.TemporaryDirectory() as directory:
                    fixture = Path(directory)
                    output = fixture / "artifacts/build"
                    output.mkdir(parents=True)
                    (output / "fixture.whl").touch()
                    (output / "twine-check.log").mkdir()
                    makefile = fixture / "Makefile"
                    makefile.write_text(f"include {PYTHON_MAKE_ROOT / 'ci/build.mk'}\n")
                    result = subprocess.run(
                        [
                            "make", "-f", str(makefile), target,
                            "SHELL=/bin/sh", ".SHELLFLAGS=-c",
                            "BUILD_TOOLS_COMMAND=true", "BUILD_PYTHON=/usr/bin/true",
                            "VENV_PYTHON=/usr/bin/true", "PACKAGE_DIR=.",
                            "BUILD_REQUIRE_PYPROJECT=0",
                            f"PROJECT_ARTIFACTS_DIR={fixture / 'artifacts'}",
                        ],
                        cwd=fixture, check=False, capture_output=True, text=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("Package artifacts ready", result.stdout)


if __name__ == "__main__":
    unittest.main()
