"""Related browser groups share setup while retaining individual native receipts."""
from __future__ import annotations

import json
from pathlib import Path
import re

REGISTRY_PATH = Path(__file__).with_name('registry.json')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate browser batch key')
        result[key] = value
    return result


def validate(registry, groups):
    require(isinstance(registry, dict) and set(registry) == {'schema', 'batches'}
            and type(registry['schema']) is int and registry['schema'] == 1, 'Invalid browser batch schema')
    batches = registry['batches']
    require(isinstance(batches, dict) and 0 < len(batches) <= len(groups), 'Finite browser batches are required')
    owned = []
    for batch, members in batches.items():
        require(isinstance(batch, str) and re.fullmatch(r'[a-z][a-z0-9-]*', batch)
                and isinstance(members, list) and 1 <= len(members) <= 3
                and all(isinstance(group, str) and group in groups for group in members), 'Unknown browser batch group')
        owned.extend(members)
    require(len(owned) == len(set(owned)) and set(owned) == set(groups), 'Missing or duplicate canonical batch group ownership')
    return {batch: tuple(members) for batch, members in batches.items()}


def registry(groups):
    require(REGISTRY_PATH.is_file() and not REGISTRY_PATH.is_symlink(), 'Browser batch registry must be ordinary source')
    return validate(json.loads(REGISTRY_PATH.read_bytes(), object_pairs_hook=unique), groups)


def owner(batches, group):
    matches = [batch for batch, members in batches.items() if group in members]
    require(len(matches) == 1, 'Canonical browser group has no unique physical batch')
    return matches[0]
