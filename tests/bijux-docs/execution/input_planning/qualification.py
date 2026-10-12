"""Require the current source-derived plan and every selected execution outcome."""
from __future__ import annotations

from .source import capture, fingerprint

FRONTEND_CONTEXTS = ('fixtures', 'browsers', 'commands', 'renderer', 'catalogue', 'persisted', 'fault_browser', 'fault_public')


def verify_plan(supplied, root, expected_head, expected_baseline, event):
    expected = capture(root, expected_head, expected_baseline, event)
    if expected['checkout'] != expected_head:
        raise ValueError('Required selection must qualify the actual event checkout')
    if not isinstance(supplied, dict) or supplied != expected:
        raise ValueError('Missing altered or stale current-source input plan')
    return expected


def selection_observation(plan):
    return {'schema': 1, 'status': 'execution_pending', 'source_head': plan['checkout'],
            'baseline': plan['baseline'], 'plan_sha256': fingerprint(plan),
            'selected_families': plan['families'], 'frontend_executed': False,
            'qualification_kind': 'current_source_selection_only',
            'limits': ['Requires the existing same-head API-created execution admission before report success.']}


def require_results(plan, results, *, plan_result, source_results=()):
    if plan_result != 'success' or any(result != 'success' for result in source_results):
        raise ValueError('Required input plan and source contexts must succeed')
    if not isinstance(results, dict) or set(results) != set(FRONTEND_CONTEXTS):
        raise ValueError('Every frontend context requires its actual outcome')
    expected = 'success' if plan['frontend'] else 'skipped'
    if any(result != expected for result in results.values()):
        raise ValueError('Missing failed cancelled or unexpected-skip frontend context')
    return {'schema': 1, 'status': 'passed', 'source_head': plan['checkout'], 'baseline': plan['baseline'],
            'plan_sha256': fingerprint(plan), 'selected_families': plan['families'], 'actual_results': results,
            'frontend_executed': plan['frontend'],
            'qualification_kind': 'current_source_affected_input_selection',
            'limits': ['Unselected families are not reported executed or inherited from another head.']}
