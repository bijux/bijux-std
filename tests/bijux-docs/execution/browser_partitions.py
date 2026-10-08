"""Declare exact browser ownership without changing canonical suite coverage."""
from __future__ import annotations

import json
from pathlib import Path
import re

REGISTRY_PATH = Path(__file__).with_suffix('.json')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_registry(registry: dict) -> dict:
    require(set(registry) == {'schema', 'engines', 'profiles', 'groups'} and registry['schema'] == 1,
            'Invalid browser partition registry')
    require(registry['engines'] == ['chromium', 'firefox', 'webkit'], 'All admitted engines are required')
    require(registry['profiles'] == ['phone', 'compact', 'desktop'], 'All canonical viewport profiles are required')
    groups = registry['groups']
    require(isinstance(groups, dict) and bool(groups), 'Browser groups are required')
    for group, entries in groups.items():
        require(bool(re.fullmatch(r'[a-z][a-z0-9-]*', group)), 'Invalid browser group name')
        require(isinstance(entries, list) and bool(entries), 'Browser group must own suites')
        seen = set()
        for entry in entries:
            require(isinstance(entry, dict) and set(entry) in ({'suite'}, {'suite', 'profile'}),
                    'Invalid browser partition entry')
            require(isinstance(entry['suite'], str) and bool(re.fullmatch(r'[a-z][a-z0-9-]*', entry['suite'])),
                    'Invalid browser suite name')
            require('profile' not in entry or entry['profile'] in registry['profiles'], 'Unknown viewport profile')
            require(entry['suite'] not in seen, 'Duplicate suite in browser group')
            seen.add(entry['suite'])
    return registry


REGISTRY = validate_registry(json.loads(REGISTRY_PATH.read_text()))
GROUPS = {group: tuple(entry['suite'] for entry in entries) for group, entries in REGISTRY['groups'].items()}
ENGINES = tuple(REGISTRY['engines'])
SUITES = tuple(dict.fromkeys(suite for suites in GROUPS.values() for suite in suites))


def selection(group: str, suite: str, engine: str, registry: dict = REGISTRY) -> dict[str, str]:
    require(engine in registry['engines'] and group in registry['groups'], 'Unknown assigned browser group or engine')
    entries = [entry for entry in registry['groups'][group] if entry['suite'] == suite]
    require(len(entries) == 1, 'Suite is not owned by assigned browser group')
    env = {'BIJUX_UI_BROWSER_ENGINE': engine}
    if 'profile' in entries[0]:
        env['BIJUX_UI_PROFILE'] = entries[0]['profile']
    return env


def plan(inventories: dict[str, dict], registry: dict = REGISTRY) -> dict[tuple[str, str], list[str]]:
    """Require one group/engine owner for every actual canonical project."""
    validate_registry(registry)
    suites = {entry['suite'] for entries in registry['groups'].values() for entry in entries}
    require(set(inventories) == suites, 'Partition inventory suite set mismatch')
    canonical = {}
    for suite, inventory in inventories.items():
        projects = inventory['canonical_projects']
        require(bool(projects) and len({project['name'] for project in projects}) == len(projects),
                'Invalid canonical project inventory')
        require(all(project['engine'] in registry['engines'] and type(project['count']) is int and project['count'] > 0
                    for project in projects), 'Invalid canonical engine or count')
        cases = inventory['cases']
        require(len({case['id'] for case in cases}) == len(cases), 'Duplicate canonical case ID')
        require({case['project'] for case in cases} == {project['name'] for project in projects},
                'Canonical case/project mismatch')
        require(all(sum(case['project'] == project['name'] for case in cases) == project['count']
                    for project in projects), 'Canonical case count mismatch')
        canonical[suite] = projects
    owned = set()
    result = {}
    for group, entries in registry['groups'].items():
        for engine in registry['engines']:
            for entry in entries:
                suite = entry['suite']
                names = [project['name'] for project in canonical[suite]
                         if project['engine'] == engine and
                         ('profile' not in entry or project['name'] == f"{engine}-{entry['profile']}")]
                require(bool(names), 'Assigned browser partition owns no canonical projects')
                for name in names:
                    require((suite, name) not in owned, 'Duplicate browser project ownership')
                    owned.add((suite, name))
                result[(f'{group}-{engine}', suite)] = names
    expected = {(suite, project['name']) for suite, projects in canonical.items() for project in projects}
    require(owned == expected, 'Browser project partition coverage is incomplete')
    return result


def verify_reports(assignments: dict[tuple[str, str], list[str]], reports: list[tuple[str, str, dict]]) -> None:
    """Reject moved, overlapping, incomplete or nonterminal partition evidence."""
    actual = [(group, suite) for group, suite, _ in reports]
    require(len(actual) == len(assignments) and set(actual) == set(assignments),
            'Missing, duplicate or unexpected browser shard receipt')
    for group, suite, report in reports:
        require(report['assigned_project_names'] == assignments[(group, suite)],
                'Browser receipt does not match its assigned engine/profile partition')
        require(report['status'] == 'passed' and report['qualification_kind'] == 'assigned_engine_shard',
                'Failed or nonterminal browser partition evidence')
