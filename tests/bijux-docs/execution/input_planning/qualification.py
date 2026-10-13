"""Require the current source-derived plan and every selected execution outcome."""
from __future__ import annotations

from .source import capture, fingerprint
from .ownership import closure, FRONTEND_FAMILIES

FRONTEND_CONTEXTS = ('fixtures', 'browsers', 'commands', 'renderer', 'catalogue', 'persisted', 'fault_browser', 'fault_public')


def verify_plan(supplied, root, expected_head, expected_baseline, event):
    expected = capture(root, expected_head, expected_baseline, event)
    if expected['checkout'] != expected_head:
        raise ValueError('Required selection must qualify the actual event checkout')
    if not isinstance(supplied, dict) or supplied != expected:
        raise ValueError('Missing altered or stale current-source input plan')
    return expected


def selected_families(plan, frontend):
    if frontend:
        return closure(FRONTEND_FAMILIES)
    if plan['frontend']:
        raise ValueError('Source-owned frontend changes cannot omit current execution')
    return plan['families']


def selection_observation(plan, selected_frontend=None):
    frontend = plan['frontend'] if selected_frontend is None else selected_frontend
    return {'schema': 1, 'status': 'execution_pending', 'source_head': plan['checkout'],
            'baseline': plan['baseline'], 'plan_sha256': fingerprint(plan),
            'selected_families': selected_families(plan, frontend), 'frontend_executed': False,
            'qualification_kind': 'current_source_selection_only',
            'limits': ['Requires the existing same-head API-created execution admission before report success.']}


def require_results(plan, results, *, plan_result, source_results=(), selected_frontend=None, proof=None):
    if plan_result != 'success' or any(result != 'success' for result in source_results):
        raise ValueError('Required input plan and source contexts must succeed')
    if not isinstance(results, dict) or set(results) != set(FRONTEND_CONTEXTS):
        raise ValueError('Every frontend context requires its actual outcome')
    frontend = plan['frontend'] if selected_frontend is None else selected_frontend
    families = selected_families(plan, frontend)
    if type(frontend) is not bool or frontend and proof is not None:
        raise ValueError('Fresh execution cannot inherit original case counts')
    expected = 'success' if frontend else 'skipped'
    if any(result != expected for result in results.values()):
        raise ValueError('Missing failed cancelled or unexpected-skip frontend context')
    return {'schema': 1, 'status': 'passed', 'source_head': plan['checkout'], 'baseline': plan['baseline'],
            'plan_sha256': fingerprint(plan), 'selected_families': families, 'actual_results': results,
            'frontend_executed': frontend, 'current_frontend_cases': None if frontend else 0,
            'qualification_kind': 'accepted_original_proof' if proof is not None else 'current_source_affected_input_selection',
            'original_proof': proof,
            'limits': ['Source-only omission and accepted original execution retain distinct qualification kinds.']}
