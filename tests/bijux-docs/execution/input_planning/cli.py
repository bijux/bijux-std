"""Write and independently recheck current-head affected-input observations."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from types import ModuleType

PACKAGE = Path(__file__).resolve().parent
NAMESPACE = 'bijux_current_source_input_planning'
package = ModuleType(NAMESPACE)
package.__path__ = [str(PACKAGE)]
sys.modules[NAMESPACE] = package
# Source selection executes physical checkout bytes, never retained bytecode.
for name in ('ownership', 'source', 'qualification'):
    path = PACKAGE / (name + '.py')
    module = ModuleType(NAMESPACE + '.' + name)
    module.__file__, module.__package__ = str(path), NAMESPACE
    sys.modules[module.__name__] = module
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
source, qualification = (sys.modules[NAMESPACE + '.' + name] for name in ('source', 'qualification'))
capture = source.capture
FRONTEND_CONTEXTS = qualification.FRONTEND_CONTEXTS
require_results, selection_observation, verify_plan = (qualification.require_results,
    qualification.selection_observation, qualification.verify_plan)

ROOT = Path(__file__).resolve().parents[4]


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate input-plan JSON key')
            result[key] = value
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def continuity():
    path = PACKAGE.parent / 'proof_continuity/gate.py'
    module = ModuleType('bijux_current_source_accepted_proof')
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('plan', 'select', 'verify'))
    parser.add_argument('--consumer-platform', action='store_true', help='Independently admit proof in its immutable consumer platform')
    parser.add_argument('--accepted-proof', action='store_true', help='Require independent accepted original proof before omission')
    parser.add_argument('--selection', type=Path, default=ROOT / 'artifacts/bijux-docs/input-plan/selection.json')
    parser.add_argument('--navigation-output', type=Path)
    parser.add_argument('--selection-only', action='store_true', help='Record selection pending independent execution admission')
    parser.add_argument('--plan', type=Path, default=ROOT / 'artifacts/bijux-docs/input-plan/plan.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/bijux-docs/input-plan/qualification.json')
    args = parser.parse_args()
    mode = os.environ.get('VERIFICATION_MODE') or 'full'
    head, baseline, event = (os.environ.get(key) for key in ('GITHUB_SHA', 'EXPECTED_BASELINE', 'GITHUB_EVENT_NAME'))
    if args.operation == 'plan':
        plan = capture(ROOT, head, baseline, event, mode)
        write(args.plan, plan)
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write('frontend=' + str(plan['frontend']).lower() + '\n')
        return
    plan = verify_plan(load(args.plan), ROOT, head, baseline, event, mode)
    if args.consumer_platform and not plan['frontend'] and (args.operation == 'select' or
            args.accepted_proof and load(args.selection).get('frontend') is False):
        platform = continuity().load('proof_continuity/consumer_platform.py')
        try:
            platform.execute(ROOT, [value for value in sys.argv[1:] if value != '--consumer-platform'])
        except (ValueError, OSError, platform.subprocess.SubprocessError) as error:
            if args.operation != 'select':
                raise ValueError('Accepted proof consumer-platform revalidation failed') from error
            selected = continuity().refused(plan, 'Consumer platform unavailable or refused')
            write(args.selection, selected)
        if args.operation == 'select':
            selected = load(args.selection)
            with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
                stream.write('frontend=' + str(selected['frontend']).lower() + '\n')
        return
    if args.operation == 'select':
        selected = continuity().select(ROOT, plan)
        write(args.selection, selected)
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write('frontend=' + str(selected['frontend']).lower() + '\n')
        return
    selected, proof = plan['frontend'], None
    if args.accepted_proof:
        decision = continuity().verify(ROOT, plan, load(args.selection), os.environ.get('EXPECTED_FRONTEND'))
        selected, proof = decision['frontend'], decision['proof']
    elif os.environ.get('EXPECTED_FRONTEND') != str(plan['frontend']).lower():
        raise ValueError('Actual execution selection differs from current source-derived plan')
    if args.selection_only and selected:
        write(args.output, selection_observation(plan, selected))
        return
    names = {'fixtures': 'FIXTURE_RESULT', 'browsers': 'BROWSER_RESULT', 'commands': 'COMMAND_RESULT'}
    results = {context: os.environ.get(names.get(context, context.upper() + '_RESULT')) for context in FRONTEND_CONTEXTS}
    receipt = require_results(plan, results, plan_result=os.environ.get('PLAN_RESULT'),
        source_results=[os.environ.get('CHECK_RESULT')] if 'CHECK_RESULT' in os.environ else (),
        selected_frontend=selected, proof=proof)
    write(args.output, receipt)
    if args.navigation_output is not None and not selected:
        write(args.navigation_output, receipt)


if __name__ == '__main__':
    main()
