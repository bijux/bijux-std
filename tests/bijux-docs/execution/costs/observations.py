"""Keep isolated monotonic timings separate from source identity and proof receipts."""
from __future__ import annotations

from functools import wraps
from contextvars import ContextVar
import json
import math
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
PREFIX = 'Bijux operation cost: '
OPERATIONS = {'source_inventory', 'runtime_inventory', 'npm_installation', 'receipt_write'}
FRAMES = ContextVar('bijux_native_operation_clocks', default=())


def record(operation, elapsed, status, *, nested_seconds=0):
    if operation not in OPERATIONS or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('Operation clock must retain a finite nonnegative monotonic observation')
    owner = os.environ.get('BIJUX_COST_OWNER', 'local-source-observation')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9-]{0,200}', owner):
        raise ValueError('Operation cost owner must be a bounded execution role')
    if not isinstance(nested_seconds, (int, float)) or not math.isfinite(nested_seconds) or not 0 <= nested_seconds <= elapsed:
        raise ValueError('Nested operation clocks must remain inside their owning interval')
    data = {'schema': 1, 'operation': operation, 'seconds': elapsed - nested_seconds,
            'wall_seconds': elapsed, 'nested_seconds': nested_seconds, 'status': status,
            'owner': owner, 'workflow_run_id': os.environ.get('GITHUB_RUN_ID'),
            'workflow_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
            'workflow_checkout': os.environ.get('GITHUB_SHA'), 'pid': os.getpid(),
            'scope': 'Cost observation only; not source, runtime or execution authority.'}
    directory = ROOT / 'artifacts/bijux-docs/cost-observations'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (owner + '.jsonl')
    if path.is_symlink():
        raise ValueError('Operation journal cannot use a linked output')
    body = json.dumps(data, separators=(',', ':')) + '\n'
    with path.open('a') as stream:
        stream.write(body)
    # Existing job/runner logs retain the observation without another upload action.
    print(PREFIX + body.rstrip(), file=sys.stderr, flush=True)


def measured(operation):
    if operation not in OPERATIONS:
        raise ValueError('Unknown native operation clock')

    def decorate(procedure):
        @wraps(procedure)
        def invoke(*arguments, **keywords):
            started, status = time.monotonic(), 'failed'
            parents, frame = FRAMES.get(), {'nested_seconds': 0}
            token = FRAMES.set((*parents, frame))
            try:
                result = procedure(*arguments, **keywords)
                status = 'complete'
                return result
            finally:
                elapsed = time.monotonic() - started
                FRAMES.reset(token)
                try:
                    record(operation, elapsed, status, nested_seconds=frame['nested_seconds'])
                finally:
                    if parents:
                        parents[-1]['nested_seconds'] += time.monotonic() - started
        return invoke
    return decorate
