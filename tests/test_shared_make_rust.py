from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SHARED_ROOT = REPOSITORY_ROOT / "shared"
RUST_SHARED_ROOT = SHARED_ROOT / "bijux-makes-rs"
TEST_ROOT = REPOSITORY_ROOT / "artifacts" / "tests" / "shared-make-rust"


class SharedMakeRustTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)
        TEST_ROOT.mkdir(parents=True)

    def prepare_workspace(self, name: str) -> Path:
        workspace = TEST_ROOT / name
        (workspace / "configs/rust").mkdir(parents=True)
        (workspace / "Cargo.toml").write_text(
            '[workspace]\nresolver = "2"\nmembers = []\n',
            encoding="utf-8",
        )
        (workspace / "configs/rust/nextest.toml").write_text(
            "[profile.default]\nretries = 0\n",
            encoding="utf-8",
        )
        (workspace / "configs/rust/deny.toml").write_text(
            "[advisories]\nversion = 2\n",
            encoding="utf-8",
        )
        return workspace

    def test_rust_component_registers_check_only_and_ci_targets(self) -> None:
        workspace = self.prepare_workspace("make-targets")
        gate = workspace / "rust-gate-fixture"
        gate.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
mkdir -p "${ARTIFACT_ROOT}/fixture"
printf '%s\\n' "$1" >>"${ARTIFACT_ROOT}/fixture/commands.txt"
""",
            encoding="utf-8",
        )
        gate.chmod(0o755)
        (workspace / "Makefile").write_text(
            (
                "BIJUX_MAKE_COMPONENTS := rust\n"
                f"BIJUX_MAKES_SHARED_ROOT := {SHARED_ROOT}\n"
                "RUST_GATE_BIN := ./rust-gate-fixture\n"
                f"include {SHARED_ROOT}/bijux-makes/bijux.mk\n"
            ),
            encoding="utf-8",
        )

        result = subprocess.run(
            ["make", "--no-print-directory", "doctor-rs", "ci-fast"],
            cwd=workspace,
            check=True,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            (workspace / "artifacts/fixture/commands.txt")
            .read_text(encoding="utf-8")
            .splitlines(),
            ["fmt", "lint", "test"],
        )

        subprocess.run(
            ["make", "--no-print-directory", "format", "ci-docs"],
            cwd=workspace,
            check=True,
            text=True,
            capture_output=True,
        )
        self.assertEqual(
            (workspace / "artifacts/fixture/commands.txt")
            .read_text(encoding="utf-8")
            .splitlines()[-2:],
            ["format", "rustdoc"],
        )

        help_output = subprocess.run(
            ["make", "--no-print-directory", "help"],
            cwd=workspace,
            check=True,
            text=True,
            capture_output=True,
        ).stdout
        self.assertIn("fmt-rs", help_output)
        self.assertIn("test-all-frozen", help_output)
        self.assertNotIn("docs-check", help_output)

    def test_nextest_expression_combines_namespace_and_roster(self) -> None:
        workspace = self.prepare_workspace("nextest-expression")
        roster = workspace / "configs/rust/nextest-slow-roster.txt"
        roster.write_text(
            "# governed slow tests\ncrate::tests::large_fixture\n",
            encoding="utf-8",
        )
        script = RUST_SHARED_ROOT / "scripts/nextest_expr.sh"
        environment = {
            **os.environ,
            "PROJECT_ROOT": str(workspace),
            "NEXTEST_SLOW_ROSTER": str(roster),
        }

        slow = subprocess.run(
            [str(script), "slow"],
            check=True,
            text=True,
            capture_output=True,
            env=environment,
        ).stdout.strip()
        fast = subprocess.run(
            [str(script), "fast"],
            check=True,
            text=True,
            capture_output=True,
            env=environment,
        ).stdout.strip()

        self.assertIn("slow_", slow)
        self.assertIn(r"crate\:\:tests\:\:large_fixture", slow)
        self.assertEqual(fast, f"not ({slow})")

    def test_rust_executor_records_commands_and_preserves_failure(self) -> None:
        workspace = self.prepare_workspace("rust-executor")
        fake_bin = workspace / "fake-bin"
        fake_bin.mkdir()
        cargo = fake_bin / "cargo"
        cargo.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >>"${FAKE_CARGO_LOG}"
if [[ "$*" == *"nextest run"* ]]; then
  printf 'Summary [ 0.001s] 1 test run: 1 passed, 0 skipped\\n'
fi
if [[ -n "${FAKE_CARGO_FAIL_MATCH:-}" && "$*" == *"${FAKE_CARGO_FAIL_MATCH}"* ]]; then
  if [[ "$*" == *"nextest run"* ]]; then
    printf 'Summary [ 0.001s] 1 test run: 0 passed, 1 failed, 0 skipped\\n'
  fi
  exit 17
fi
if [[ "$*" == *"--output-path"* ]]; then
  args=("$@")
  for ((index=0; index<${#args[@]}; index++)); do
    if [[ "${args[$index]}" == "--output-path" ]]; then
      mkdir -p "$(dirname "${args[$((index + 1))]}")"
      printf 'TN:\\n' >"${args[$((index + 1))]}"
    fi
  done
fi
""",
            encoding="utf-8",
        )
        cargo.chmod(0o755)
        for tool in ("cargo-nextest", "cargo-deny", "cargo-audit", "cargo-llvm-cov"):
            path = fake_bin / tool
            path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            path.chmod(0o755)

        log_path = workspace / "artifacts/fake-cargo.log"
        environment = {
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "PROJECT_ROOT": str(workspace),
            "ARTIFACT_ROOT": str(workspace / "artifacts"),
            "RS_ARTIFACT_ROOT": str(workspace / "artifacts/rust"),
            "NEXTEST_CONFIG_FILE": str(workspace / "configs/rust/nextest.toml"),
            "NEXTEST_SLOW_ROSTER": str(
                workspace / "configs/rust/nextest-slow-roster.txt"
            ),
            "NEXTEST_EXPR_BIN": str(
                RUST_SHARED_ROOT / "scripts/nextest_expr.sh"
            ),
            "RUST_DENY_CONFIG": str(workspace / "configs/rust/deny.toml"),
            "FAKE_CARGO_LOG": str(log_path),
        }
        executor = RUST_SHARED_ROOT / "scripts/rust_gate.sh"

        for command in ("fmt", "test", "audit", "rustdoc"):
            subprocess.run(
                [str(executor), command],
                cwd=workspace,
                check=True,
                text=True,
                capture_output=True,
                env=environment,
            )

        cargo_commands = log_path.read_text(encoding="utf-8")
        self.assertIn("fmt --all -- --check", cargo_commands)
        self.assertIn("nextest run --workspace", cargo_commands)
        self.assertIn("deny check bans licenses sources", cargo_commands)
        self.assertIn("audit", cargo_commands)
        self.assertIn("doc --workspace --no-deps", cargo_commands)
        self.assertTrue(
            (workspace / "artifacts/rust/test/local/nextest.log").is_file()
        )

        failed_test = subprocess.run(
            [str(executor), "test-all"],
            cwd=workspace,
            check=False,
            text=True,
            capture_output=True,
            env={**environment, "FAKE_CARGO_FAIL_MATCH": "nextest run"},
        )
        self.assertEqual(failed_test.returncode, 17)
        self.assertIn("nextest-summary:", failed_test.stdout)
        self.assertIn("1 test run: 0 passed, 1 failed, 0 skipped", failed_test.stdout)
        self.assertIn("nextest-mode: all", failed_test.stdout)

        failed = subprocess.run(
            [str(executor), "lint"],
            cwd=workspace,
            check=False,
            text=True,
            capture_output=True,
            env={**environment, "FAKE_CARGO_FAIL_MATCH": "clippy"},
        )
        self.assertEqual(failed.returncode, 17)
        self.assertTrue(
            (workspace / "artifacts/rust/lint/local/report.txt").is_file()
        )

        escaped = subprocess.run(
            [str(executor), "fmt"],
            cwd=workspace,
            check=False,
            text=True,
            capture_output=True,
            env={**environment, "RS_TARGET_DIR": str(workspace / "target")},
        )
        self.assertNotEqual(escaped.returncode, 0)
        self.assertIn("Rust gate path must stay under", escaped.stderr)


if __name__ == "__main__":
    unittest.main()
