from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "shared/bijux-checks/scripts/directory-tree-sha256.sh"
ARTIFACTS = ROOT / "artifacts/tests/directory-digest-batching"
LEGACY = r'''#!/usr/bin/env bash
set -euo pipefail
if [[ "$#" -ne 1 ]]; then exit 2; fi
if [[ ! -d "$1" ]]; then exit 1; fi
(
  cd "$1"
  find . \
    \( -type d \( \
      -name __pycache__ -o \
      -name .mypy_cache -o \
      -name .pytest_cache -o \
      -name .ruff_cache \
    \) -prune \) -o \
    \( -type f \
      ! -name .DS_Store \
      ! -name '*.py[co]' \
      -print \
    \) |
    LC_ALL=C sort |
    while IFS= read -r file_rel; do
      shasum -a 256 "${file_rel}"
    done
) | shasum -a 256 | awk '{print $1}'
'''


class DirectoryDigestBatchingTests(unittest.TestCase):
    def setUp(self):
        self.directory = ARTIFACTS / self._testMethodName
        shutil.rmtree(self.directory, ignore_errors=True)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.tree = self.directory / "tree"
        self.tree.mkdir(exist_ok=True)
        self.legacy = self.directory / "legacy.sh"
        self.legacy.write_text(LEGACY)

    def run_digest(self, helper, tree=None, env=None):
        start = time.monotonic()
        result = subprocess.run(
            ["bash", str(helper), str(tree or self.tree)],
            capture_output=True, env=env,
        )
        return result, time.monotonic() - start

    def assert_equivalent(self, tree=None):
        old, old_seconds = self.run_digest(self.legacy, tree)
        new, new_seconds = self.run_digest(HELPER, tree)
        self.assertEqual(old.returncode, 0, old.stderr)
        self.assertEqual(new.returncode, 0, new.stderr)
        self.assertEqual(new.stdout, old.stdout)
        return old.stdout.decode().strip(), old_seconds, new_seconds

    def test_actual_six_canonical_tree_digests_and_timings(self):
        records = []
        for name in ("bijux-checks", "bijux-docs", "bijux-gh", "bijux-makes", "bijux-makes-py", "bijux-makes-rs"):
            with self.subTest(directory=name):
                digest, old_seconds, new_seconds = self.assert_equivalent(ROOT / "shared" / name)
                records.append({"directory": "shared/" + name, "digest": digest,
                                "legacy_seconds": old_seconds, "batched_seconds": new_seconds})
        (self.directory / "timings.json").write_text(json.dumps(records, indent=2) + "\n")

    def test_literal_filename_bytes_and_perl_escaping_are_preserved(self):
        for name in ("space name", "back\\slash", "tab\tname", "carriage\rname", "-leading", "é漢字", "[pattern]*?"):
            (self.tree / name).write_bytes(name.encode())
        if sys.platform != "darwin":
            raw = os.fsencode(self.tree) + b"/invalid-\xff"
            with open(raw, "wb") as output:
                output.write(b"non-UTF filename\n")
        self.assert_equivalent()

    def test_empty_directory_keeps_empty_stream_digest(self):
        digest, _, _ = self.assert_equivalent()
        self.assertEqual(digest, hashlib.sha256(b"").hexdigest())

    def test_existing_cache_pruning_and_file_filters_are_preserved(self):
        (self.tree / "keep").write_bytes(b"owned")
        for name in ("__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"):
            cache = self.tree / name
            cache.mkdir(exist_ok=True)
            (cache / "hidden").write_bytes(b"ignored")
        for name in (".DS_Store", "compiled.pyc", "compiled.pyo"):
            (self.tree / name).write_bytes(b"ignored")
        (self.tree / "link").symlink_to("keep")
        expected = self.assert_equivalent()[0]
        (self.tree / "__pycache__/hidden").write_bytes(b"changed ignored")
        self.assertEqual(self.assert_equivalent()[0], expected)

    def test_newline_filename_keeps_existing_failure_boundary(self):
        (self.tree / "line\nbreak").write_bytes(b"unrepresentable legacy line")
        for helper in (self.legacy, HELPER):
            result, _ = self.run_digest(helper)
            self.assertNotEqual(result.returncode, 0)

    def test_missing_directory_refuses(self):
        for helper in (self.legacy, HELPER):
            result, _ = self.run_digest(helper, self.directory / "absent")
            self.assertNotEqual(result.returncode, 0)

    def wrapper_environment(self, fail=False):
        bin_dir = self.directory / "bin"
        bin_dir.mkdir(exist_ok=True)
        wrapper = bin_dir / "shasum"
        real = shutil.which("shasum")
        wrapper.write_text("#!" + shutil.which("python3") + "\n" +
            "import json,os,subprocess,sys\n" +
            "args=sys.argv[1:]\n" +
            "with open(os.environ['HASH_CALLS'],'a') as out: out.write(json.dumps(args)+'\\n')\n" +
            ("if './reject' in args: raise SystemExit(17)\n" if fail else "") +
            "raise SystemExit(subprocess.call([" + repr(real) + ",*args]))\n")
        wrapper.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
        env["HASH_CALLS"] = str(self.directory / "calls.jsonl")
        return env

    def test_nonzero_hash_batch_propagates(self):
        (self.tree / "reject").write_bytes(b"must refuse")
        env = self.wrapper_environment(fail=True)
        for helper in (self.legacy, HELPER):
            result, _ = self.run_digest(helper, env=env)
            self.assertEqual(result.returncode, 17, result.stderr)

    def test_argument_count_and_byte_budgets_are_bounded(self):
        for nested in (False, True):
            with self.subTest(byte_budget_profile=nested):
                shutil.rmtree(self.tree)
                self.tree.mkdir()
                parent = self.tree / ("directory" * 25) if nested else self.tree
                parent.mkdir(exist_ok=True)
                for index in range(310):
                    (parent / (str(index).zfill(4) + "x" * 230)).write_bytes(b"owned")
                env = self.wrapper_environment()
                Path(env["HASH_CALLS"]).unlink(missing_ok=True)
                result, _ = self.run_digest(HELPER, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = [json.loads(line) for line in Path(env["HASH_CALLS"]).read_text().splitlines()]
                batches = [args for args in calls if len(args) > 2]
                self.assertGreater(len(batches), 1)
                self.assertEqual(sum(len(args) - 2 for args in batches), 310)
                if nested:
                    self.assertLess(len(batches[0]) - 2, 125)
                else:
                    self.assertEqual(len(batches[0]) - 2, 125)
                for args in batches:
                    self.assertLessEqual(len(args) + 1, 128)
                    self.assertLessEqual(sum(len(os.fsencode(arg)) + 1 for arg in ["shasum", *args]), 32768)
                self.assert_equivalent()


if __name__ == "__main__":
    unittest.main()
