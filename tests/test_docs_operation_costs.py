"""Native cost observations cannot replace source identity or execution receipts."""
from contextlib import redirect_stderr
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('bijux_native_cost_controls', ROOT / 'tests/bijux-docs/execution/costs/observations.py')
COSTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COSTS)


class OperationCostTests(unittest.TestCase):
    def test_nested_runtime_inventories_do_not_count_the_same_interval_twice(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory, patch.object(COSTS, 'ROOT', Path(directory)), redirect_stderr(io.StringIO()) as output:
            inner = COSTS.measured('runtime_inventory')(lambda: hashlib.sha256(b'owned runtime bytes' * 50000).hexdigest())
            outer = COSTS.measured('runtime_inventory')(inner)
            self.assertEqual(outer(), hashlib.sha256(b'owned runtime bytes' * 50000).hexdigest())
            rows = [json.loads(line.split(COSTS.PREFIX, 1)[1]) for line in output.getvalue().splitlines()]
            self.assertGreater(rows[-1]['nested_seconds'], 0)
            self.assertLessEqual(sum(row['seconds'] for row in rows), rows[-1]['wall_seconds'])

    def test_success_and_failure_preserve_return_and_exception_with_distinct_non_authority_observations(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory, patch.object(COSTS, 'ROOT', Path(directory)), redirect_stderr(io.StringIO()) as output:
            identity = {'files': {'owned': 'digest'}, 'head': 'a' * 40}
            observed = COSTS.measured('source_inventory')(lambda: identity)()
            self.assertIs(observed, identity)
            def refuse():
                raise LookupError('physical runtime refused')
            with self.assertRaisesRegex(LookupError, 'physical runtime refused'):
                COSTS.measured('runtime_inventory')(refuse)()
            rows = [json.loads(line.split(COSTS.PREFIX, 1)[1]) for line in output.getvalue().splitlines()]
            journal = list((Path(directory) / 'artifacts/bijux-docs/cost-observations').glob('*.jsonl'))
            self.assertEqual([json.loads(line) for line in journal[0].read_text().splitlines()], rows)
            self.assertEqual([row['status'] for row in rows], ['complete', 'failed'])
            self.assertTrue(all(row['seconds'] >= 0 and 'not source, runtime or execution authority' in row['scope'] for row in rows))
            self.assertFalse(any(key in rows[0] for key in ('files', 'runtime', 'executed_cases', 'approval')))

    def test_invalid_clocks_and_journal_alias_refuse(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory, patch.object(COSTS, 'ROOT', Path(directory)):
            for operation, elapsed in [('unknown', 1), ('receipt_write', -1), ('receipt_write', float('nan'))]:
                with self.assertRaises(ValueError):
                    COSTS.record(operation, elapsed, 'complete')
            output = Path(directory) / 'artifacts/bijux-docs/cost-observations/local-source-observation.jsonl'
            output.parent.mkdir(parents=True)
            target = Path(directory) / 'preserved'; target.write_text('user work')
            output.symlink_to(target)
            with self.assertRaises(ValueError):
                COSTS.record('receipt_write', 0, 'complete')
            self.assertEqual(target.read_text(), 'user work')

    def test_native_javascript_source_inventory_keeps_stdout_identity_separate_from_cost_logs(self):
        identity = ROOT / 'tests/bijux-docs/reporting/identity.js'
        result = subprocess.run(['node', '-e', 'console.log(JSON.stringify(require(process.argv[1]).sourceIdentity()))', str(identity)],
                                cwd=ROOT, capture_output=True, text=True, check=True)
        source = json.loads(result.stdout)
        self.assertEqual(set(source), {'head', 'tree_sha256', 'files'})
        self.assertIn('tests/bijux-docs/reporting/identity.js', source['files'])
        records = [json.loads(line.split(COSTS.PREFIX, 1)[1]) for line in result.stderr.splitlines() if line.startswith(COSTS.PREFIX)]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['operation'], 'source_inventory')
        self.assertEqual(records[0]['status'], 'complete')


if __name__ == '__main__':
    unittest.main()
