"""Bind one reviewed retained PDF build to distinct historical/current source epochs."""
from __future__ import annotations

import io
import json
from pathlib import PurePosixPath
import re
import subprocess
import tomllib

ADMISSION = {
    'context_path': 'presentation/retained-build-source-context.json',
    'context_sha256': '1ad22d57414a717c243d03f8a94c23374aca9c9dff0d1d2ff650a11eaf57ebd7',
    'source_lock_sha256': 'e5f3ccf408cbea0b3961c5ca9abf2b11edeaa2710d1587b62f60d5145bdd696e',
    'accepted_revision': '4ec5f1f614ba2e0e1c8b16f3e9b3aa1abd73c3c3',
    'source_revision': '2f526aee907574df061318ef2982af11012626e4',
    'source_count': 121,
    'reviewed_delta_count': 15,
    'previous_context_path': 'presentation/retained-source-context.json',
    'previous_context_sha256': '14f1d06e8f1470e5810865f4ae6d56b8d7cd08e30f3b73ad07d43fdda9bd0818',
    'previous_revision': '11079034b7dc0c1a0d94d26c97c70ec59fcf27f7',
    'previous_source_lock_sha256': '42fc24dc8c0a4f43bb754d4176f8259bb93a61133fa73ee00a9c20e27b2cad5b',
    'previous_source_count': 98,
    'pdf_sha256': {
        'presentation/big-picture.pdf': 'd1c924e807c77c79c98fe64ad29c1b7bac3df41f6862cbd006591655f129e739',
        'presentation/developer.pdf': 'ddb85077744cf4a9cefd2223280572e0c534bb51d8d1336c1083a4495738fde6',
        'presentation/scientific-evidence.pdf': '7a9ec3066a0a577b5b4775a937ddae6df3e50cafd6049adc6a48778df7478031',
    },
}


def _path(name, require):
    require(isinstance(name, str) and name and '\\' not in name
            and not any(ord(c) < 32 for c in name), 'Retained build: canonical source path required')
    value = PurePosixPath(name)
    require(not value.is_absolute() and '..' not in value.parts and value.as_posix() == name,
            'Retained build: source path escapes its owner')
    return name


def _git(root, *arguments, request=None):
    return subprocess.run(['git', '--no-replace-objects', '-C', str(root), *arguments],
                          input=request, capture_output=True, check=True, timeout=30).stdout


def _blobs(root, revision, paths, require):
    require(isinstance(revision, str) and re.fullmatch('[0-9a-f]{40}', revision) is not None,
            'Retained build: exact Git revision required')
    require(0 < len(paths) <= 128 and len(set(paths)) == len(paths),
            'Retained build: bounded unique source population required')
    for name in paths:
        _path(name, require)
    tree = _git(root, 'ls-tree', '-r', '-z', revision, '--', *paths)
    modes = {}
    for record in tree.split(b'\0'):
        if not record:
            continue
        metadata, encoded = record.split(b'\t', 1)
        mode, kind, _ = metadata.split()
        name = encoded.decode()
        require(mode in {b'100644', b'100755'} and kind == b'blob' and name not in modes,
                'Retained build: unique regular historical source required')
        modes[name] = mode
    require(set(modes) == set(paths), 'Retained build: historical source population differs')
    request = ''.join(f'{revision}:{name}\n' for name in paths).encode()
    stream = io.BytesIO(_git(root, 'cat-file', '--batch', request=request))
    values = {}
    for name in paths:
        header = stream.readline().split()
        require(len(header) == 3 and header[1] == b'blob' and header[2].isdigit(),
                'Retained build: historical source stream differs')
        size = int(header[2])
        require(size <= 32 * 1024 * 1024, 'Retained build: historical source exceeds byte budget')
        content = stream.read(size)
        require(len(content) == size and stream.read(1) == b'\n',
                'Retained build: truncated historical source stream')
        values[name] = content
    require(stream.read() == b'', 'Retained build: unrequested historical source stream')
    return values, modes


def capture(hook, root, regular, require, digest, previous_context):
    """Independently check the exact approved capsule; caller binds loaded hook code."""
    rule = ADMISSION
    require(hook.CURRENT_DECK_CONTEXT_PATH == rule['context_path']
            and hook.CURRENT_DECK_CONTEXT_SHA256 == rule['context_sha256']
            and hook.CURRENT_DECK_SOURCE_LOCK_SHA256 == rule['source_lock_sha256']
            and hook.CURRENT_DECK_ACCEPTED_REVISION == rule['accepted_revision']
            and hook.RETAINED_CONTEXT_PATH == rule['previous_context_path']
            and hook.RETAINED_CONTEXT_SHA256 == rule['previous_context_sha256']
            and hook.RETAINED_CONTEXT == previous_context
            and hook.subprocess is subprocess and hook.tomllib is tomllib and hook.io is io,
            'Retained build: context constants or native dependency bindings differ')
    raw = regular(root, root / rule['context_path'])
    require(digest(raw) == rule['context_sha256'], 'Retained build: raw source context differs')
    context = json.loads(raw)
    require(set(context) == {'schema_version', 'retained_build', 'previous_deck_epoch',
                            'current_source_sha256', 'reviewed_deltas', 'qualification'}
            and context['schema_version'] == 'retained-deck-current-source-correspondence.v1',
            'Retained build: source-context schema differs')
    build = context['retained_build']
    require(build['accepted_revision'] == rule['accepted_revision']
            and build['source_revision'] == rule['source_revision']
            and build['source_lock_path'] == 'presentation/source-lock.json'
            and build['source_lock_sha256'] == rule['source_lock_sha256']
            and build['source_count'] == rule['source_count']
            and build['pdf_sha256'] == rule['pdf_sha256'],
            'Retained build: original build identity differs')
    old_raw = regular(root, root / rule['previous_context_path'])
    require(digest(old_raw) == rule['previous_context_sha256']
            and json.loads(old_raw) == previous_context,
            'Retained build: previous source context differs')
    previous = context['previous_deck_epoch']
    require(previous['context_path'] == rule['previous_context_path']
            and previous['context_sha256'] == rule['previous_context_sha256']
            and previous['source_revision'] == rule['previous_revision']
            and previous['source_lock_sha256'] == rule['previous_source_lock_sha256']
            and previous['source_count'] == rule['previous_source_count'],
            'Retained build: previous source epoch differs')
    for revision in (rule['previous_revision'], rule['accepted_revision'], rule['source_revision']):
        _git(root, 'merge-base', '--is-ancestor', revision, 'HEAD')
    old, _ = _blobs(root, rule['previous_revision'], ['presentation/source-lock.json'], require)
    require(digest(old['presentation/source-lock.json']) == rule['previous_source_lock_sha256'],
            'Retained build: original previous lock differs')
    old_lock = json.loads(old['presentation/source-lock.json'])
    require(old_lock['decks'] == list(hook.DECKS)
            and len(old_lock['sources']) == rule['previous_source_count'],
            'Retained build: previous source population differs')
    lock_raw = regular(root, root / 'presentation/source-lock.json')
    require(digest(lock_raw) == rule['source_lock_sha256'], 'Retained build: retained source lock differs')
    lock = json.loads(lock_raw)
    paths = sorted(lock['sources'])
    require(lock['decks'] == list(hook.DECKS) and len(paths) == rule['source_count']
            and set(context['current_source_sha256']) == set(paths),
            'Retained build: source population differs')
    historical, _ = _blobs(root, rule['accepted_revision'], [*paths, 'presentation/source-lock.json'], require)
    require(historical['presentation/source-lock.json'] == lock_raw,
            'Retained build: lock differs from accepted build')
    head = _git(root, 'rev-parse', '--verify', 'HEAD').decode().strip()
    committed, modes = _blobs(root, head, paths, require)
    historical_inputs, current_inputs, changed = [], [], []
    for name in paths:
        content = regular(root, root / _path(name, require))
        original_hash, current_hash = digest(historical[name]), digest(content)
        require(original_hash == lock['sources'][name], 'Retained build: historical input differs')
        require(current_hash == context['current_source_sha256'][name] and content == committed[name],
                'Retained build: current input differs from reviewed committed source')
        mode = b'100755' if (root / name).stat().st_mode & 0o100 else b'100644'
        require(mode == modes[name], 'Retained build: current source mode differs')
        historical_inputs.append({'path': name, 'sha256': original_hash})
        current_inputs.append({'path': name, 'sha256': current_hash})
        if content != historical[name]:
            changed.append(name)
    deltas = context['reviewed_deltas']
    require(len(deltas) == rule['reviewed_delta_count']
            and changed == [row['path'] for row in deltas], 'Retained build: reviewed delta population differs')
    for row in deltas:
        name = row['path']
        require(row['retained_sha256'] == lock['sources'][name]
                and row['current_sha256'] == context['current_source_sha256'][name]
                and isinstance(row['review'], str) and len(row['review'].strip()) >= 20,
                'Retained build: reviewed source delta identity differs')
    for name, expected in rule['pdf_sha256'].items():
        require(digest(regular(root, root / name)) == expected, 'Retained build: original retained PDF differs')
    result = {'context': context, 'historical_inputs': historical_inputs, 'current_inputs': current_inputs}
    require(hook.retained_deck_sources(root) == result,
            'Retained build: callback source correspondence differs from independent capture')
    return result
