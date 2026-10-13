"""Own stable source domains and their complete verification dependencies."""
from __future__ import annotations

from pathlib import PurePosixPath

SOURCE_FAMILIES = ('standard', 'contracts')
FRONTEND_FAMILIES = ('fixtures', 'browser-matrix', 'renderer-controls', 'publication-commands',
                     'catalogue', 'browser-faults', 'public-faults', 'persisted-reader')
DEPENDENCIES = {
    'browser-matrix': ('fixtures',), 'browser-faults': ('fixtures',), 'persisted-reader': ('fixtures',),
    'fixtures': ('renderer-controls', 'publication-commands', 'catalogue', 'public-faults'),
}


def closure(families):
    selected = set(families) | set(SOURCE_FAMILIES)
    unknown = selected - set(SOURCE_FAMILIES + FRONTEND_FAMILIES)
    if unknown:
        raise ValueError('Unknown verification family')
    while True:
        expanded = selected | {dependency for family in selected for dependency in DEPENDENCIES.get(family, ())}
        if expanded == selected:
            return [family for family in SOURCE_FAMILIES + FRONTEND_FAMILIES if family in selected]
        selected = expanded


def classify(path):
    """Unknown input ownership is explicit; callers must select complete coverage."""
    if not isinstance(path, str) or not path or '\\' in path or ':' in path:
        return None
    relative = PurePosixPath(path)
    if relative.is_absolute() or str(relative) != path or any(part in ('.', '..') for part in relative.parts):
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in path):
        return None
    if path.startswith(('.github/workflows/', '.github/scripts/', '.github/standards/', '.bijux/shared/')):
        return 'workflow-and-policy', SOURCE_FAMILIES + FRONTEND_FAMILIES
    if path.startswith(('tests/', 'shared/bijux-docs/', 'shared/bijux-gh/', 'makes/')) or path == 'Makefile':
        return 'documentation-verification', SOURCE_FAMILIES + FRONTEND_FAMILIES
    if path.startswith(('shared/bijux-checks/', 'shared/bijux-makes/', 'shared/bijux-makes-py/', 'shared/bijux-makes-rs/')):
        return 'shared-source-contracts', SOURCE_FAMILIES + FRONTEND_FAMILIES
    if path.startswith(('.github/ISSUE_TEMPLATE/', '.github/PULL_REQUEST_TEMPLATE/', '.github/rulesets/')):
        return 'repository-governance', SOURCE_FAMILIES
    if path in {'.gitattributes', '.gitignore', '.bijux/checks.consumer.json', 'shared/shared-dir-sha256.txt'}:
        return 'source-materialization-and-admission', SOURCE_FAMILIES + FRONTEND_FAMILIES
    if path in {'.github/CODEOWNERS', '.github/automation-identity.md', '.github/bijux-std-shared.sha256',
                '.github/codecov.yml', '.github/dependabot.yml', '.github/labeler.yml', '.github/release.env',
                '.github/required-status-checks.md'}:
        return 'repository-governance', SOURCE_FAMILIES
    if path in {'CHANGELOG.md', 'LICENSE', 'NOTICE', 'README.md'}:
        return 'repository-metadata', SOURCE_FAMILIES
    return None


def select(changes, refusal_reasons=()):
    """Deletion/rename/ambiguity cannot silently narrow the existing full matrix."""
    reasons, owners, selected = list(refusal_reasons), [], set(SOURCE_FAMILIES)
    if not isinstance(changes, list):
        reasons.append('invalid changed-input inventory')
        changes = []
    for change in changes:
        if not isinstance(change, dict) or set(change) != {'status', 'paths'}:
            reasons.append('ambiguous changed-input record')
            continue
        status, paths = change['status'], change['paths']
        if not isinstance(paths, list) or len(paths) != 1 or not isinstance(status, str) or status not in ('A', 'M'):
            reasons.append('deleted renamed or ambiguous input selects complete verification')
            continue
        owned = classify(paths[0])
        if owned is None:
            reasons.append('unknown or invalid input owner')
            continue
        domain, families = owned
        owners.append({'path': paths[0], 'domain': domain})
        selected.update(families)
    if reasons:
        selected.update(FRONTEND_FAMILIES)
    return {'families': closure(selected), 'frontend': bool(selected & set(FRONTEND_FAMILIES)),
            'input_owners': owners, 'full_verification_reasons': sorted(set(reasons))}
