"""Bind original native paths to independently authenticated Git blobs and modes."""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from types import ModuleType

EXECUTION = Path(__file__).resolve().parent.parent
_PATH = EXECUTION / 'input_planning/ownership.py'
OWNERSHIP = ModuleType('bijux_continuity_input_owners')
OWNERSHIP.__file__ = str(_PATH)
exec(compile(_PATH.read_bytes(), str(_PATH), 'exec'), OWNERSHIP.__dict__)
_COST_PATH = EXECUTION / 'costs/observations.py'
COSTS = ModuleType('bijux_accepted_source_inventory_costs')
COSTS.__file__ = str(_COST_PATH)
exec(compile(_COST_PATH.read_bytes(), str(_COST_PATH), 'exec'), COSTS.__dict__)
_CREATED = object()


def require(value, message):
    if not value:
        raise ValueError(message)


def frontend(objects):
    return {name: row for name, row in objects.items()
            if (owner := OWNERSHIP.classify(name)) is None
            or set(owner[1]) & set(OWNERSHIP.FRONTEND_FAMILIES)}


def api_tree(payload, expected_tree):
    require(isinstance(payload, dict) and payload.get('sha') == expected_tree
            and payload.get('truncated') is False and isinstance(payload.get('tree'), list),
            'Complete authenticated original Git tree is required')
    result = {}
    for row in payload['tree']:
        require(isinstance(row, dict), 'Invalid original Git tree row')
        name = row.get('path')
        require(isinstance(name, str) and name and '\\' not in name and ':' not in name
                and str(PurePosixPath(name)) == name and not name.startswith('/')
                and not any(part in ('.', '..') for part in name.split('/'))
                and all(ord(char) >= 32 and ord(char) != 127 for char in name),
                'Invalid original Git input path')
        if row.get('type') == 'tree':
            require(row.get('mode') == '040000', 'Invalid original Git directory mode')
            continue
        require(row.get('type') == 'blob' and row.get('mode') in ('100644', '100755')
                and re.fullmatch('[a-f0-9]{40}', row.get('sha', '')) and name not in result,
                'Original source must contain unique regular Git blobs')
        result[name] = {'mode': row['mode'], 'kind': 'blob', 'object': row['sha']}
    require(result, 'Original source tree is empty')
    return result


class OriginalSource:
    """Process-local source closure; exported receipt dictionaries cannot recreate it."""
    def __init__(self, root, original, objects, *, _created=None):
        require(_created is _CREATED, 'Original source requires authenticated closure admission')
        self.root, self.identity, self.objects = Path(root).resolve(), original, dict(objects)
        self._native_root = None

    def native_relative(self, value, files):
        require(isinstance(value, str) and value.startswith('/') and '\\' not in value
                and ':' not in value and str(PurePosixPath(value)) == value
                and not any(part in ('.', '..') for part in value.split('/')[1:]),
                'Original native event path is not canonical')
        names = [str(Path(path).relative_to(self.root)) for path in files]
        matches = [name for name in names if value.endswith('/' + name)]
        require(len(matches) == 1, 'Original native path has no unique source-owned Git blob')
        name = matches[0]
        require(name in self.objects and self.objects[name]['mode'] in ('100644', '100755'),
                'Original native path lacks authenticated Git mode')
        prefix = value[:-len(name)]
        require(self._native_root is None or self._native_root == prefix,
                'Original native event changed its execution root')
        self._native_root = prefix
        return name


@COSTS.measured('source_inventory')
def admit(root, plan, original, original_tree, checkout_authority):
    require(type(checkout_authority).__name__ == 'AcceptedCheckout'
            and Path(inspect.getfile(type(checkout_authority))).resolve() == Path(__file__).with_name('authority.py'),
            'Original native paths require live accepted checkout authority')
    checkout_authority.verify_source_objects(original_tree, original)
    require(isinstance(original, dict) and set(original) == {'head', 'tree_sha256', 'files'}
            and re.fullmatch('[a-f0-9]{40}', original.get('head', ''))
            and isinstance(original.get('files'), dict) and set(original['files']) == set(original_tree)
            and all(isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value)
                    for value in original['files'].values()), 'Original source inventory is incomplete')
    source_digest = hashlib.sha256(json.dumps(original['files'], separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    require(original['tree_sha256'] == source_digest, 'Original physical source inventory digest differs')
    current = frontend(plan['source_objects'])
    require(current and current == frontend(original_tree), 'Owned frontend Git blob or mode closure changed')
    root = Path(root).resolve()
    for name, record in current.items():
        path = root / name
        require(not any(value.is_symlink() for value in (path, *path.parents))
                and path.is_file() and record['mode'] in ('100644', '100755') and record['kind'] == 'blob',
                'Current frontend source is not a regular owned input')
        data = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        mode = '100755' if stat.S_IMODE(path.stat().st_mode) & 0o111 else '100644'
        require(blob == record['object'] and mode == record['mode']
                and hashlib.sha256(data).hexdigest() == original['files'][name],
                'Fresh frontend bytes differ from authenticated original Git source')
    return OriginalSource(root, original, original_tree, _created=_CREATED)


def unchanged(root, plan):
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=root)
    require(head == plan['checkout'] and not dirty.strip(), 'Current source changed during accepted-proof qualification')
