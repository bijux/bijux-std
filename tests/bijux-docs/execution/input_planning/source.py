"""Capture immutable checkout/base identity and original Git change records."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

from .ownership import select

PLANNER_ROOT = 'tests/bijux-docs/execution/input_planning/'
CANONICAL_WORKFLOW = '.github/standards/workflow-sources/bijux-std.yml'


def git(root, *arguments):
    return subprocess.check_output(['git', *arguments], cwd=root, stderr=subprocess.PIPE)


def revision(root, name):
    value = git(root, 'rev-parse', '--verify', name + '^{commit}').decode().strip()
    if not re.fullmatch(r'[a-f0-9]{40}', value):
        raise ValueError('Full immutable source revision is required')
    return value


def tree(root, source):
    records = git(root, 'ls-tree', '-rz', source).split(b'\0')
    result = {}
    for record in filter(None, records):
        metadata, name = record.split(b'\t', 1)
        mode, kind, object_id = metadata.decode().split()
        result[name.decode('utf-8', 'strict')] = {'mode': mode, 'kind': kind, 'object': object_id}
    return result


def changes(root, baseline, head):
    values = git(root, 'diff', '--name-status', '-z', '--find-renames', baseline, head).split(b'\0')
    rows, offset = [], 0
    while offset < len(values) and values[offset]:
        status = values[offset].decode('ascii', 'strict')
        count = 2 if status.startswith(('R', 'C')) else 1
        paths = [value.decode('utf-8', 'strict') for value in values[offset + 1:offset + 1 + count]]
        if len(paths) != count or not all(paths):
            raise ValueError('Incomplete Git changed-input record')
        rows.append({'status': status, 'paths': paths})
        offset += count + 1
    return rows


def capture(root, expected_head, expected_baseline, event, mode="full"):
    root, reasons = Path(root).resolve(), []
    head = revision(root, 'HEAD')
    if expected_head != head:
        reasons.append('checkout differs from event source')
    qualification = event == 'workflow_dispatch' and mode == 'accepted-proof-qualification'
    if mode not in ('full', 'accepted-proof-qualification'):
        reasons.append('unknown verification mode')
    if event not in ('pull_request', 'merge_group') and not qualification:
        reasons.append('event has no qualified affected-input baseline')
    if mode != 'full' and not qualification:
        reasons.append('accepted-proof mode requires its explicit manual event')
    try:
        remote = git(root, 'remote', 'get-url', 'origin').decode().strip()
        if remote not in ('https://github.com/bijux/bijux-std', 'https://github.com/bijux/bijux-std.git', 'git@github.com:bijux/bijux-std.git'):
            reasons.append('baseline remote is not the owning repository')
        baseline = revision(root, 'refs/remotes/origin/main')
        if qualification and (head != baseline or expected_baseline != head):
            reasons.append('accepted-proof qualification requires the exact official main checkout')
        if baseline != expected_baseline or not re.fullmatch(r'[a-f0-9]{40}', expected_baseline or ''):
            reasons.append('baseline differs from independent event main identity')
        if subprocess.run(['git', 'merge-base', '--is-ancestor', baseline, head], cwd=root, capture_output=True).returncode:
            reasons.append('baseline is not a checkout ancestor')
        before, current = tree(root, baseline), tree(root, head)
        owned = lambda records: {name: record for name, record in records.items() if name.startswith(PLANNER_ROOT)}
        if not owned(before) or owned(before) != owned(current):
            reasons.append('planner is absent from baseline or its owned source changed')
        if before.get(CANONICAL_WORKFLOW) != current.get(CANONICAL_WORKFLOW):
            reasons.append('canonical workflow changed')
        for name, record in current.items():
            if record['mode'] != '100644' and record['mode'] != '100755':
                reasons.append('nonregular canonical input selects complete verification')
        changed = changes(root, baseline, head)
    except (subprocess.CalledProcessError, UnicodeError, ValueError):
        baseline, before, current, changed = None, {}, tree(root, head), []
        reasons.append('baseline or changed-input observation is unavailable')
    if git(root, 'status', '--porcelain', '--untracked-files=normal').strip():
        reasons.append('working source differs from immutable checkout')
    selection = select(changed, reasons)
    return {'schema': 1, 'checkout': head, 'checkout_tree': revision_tree(root, head),
            'baseline': baseline, 'event_baseline': expected_baseline, 'event_source': expected_head,
            'event': event, 'qualification_mode': mode, 'changes': changed, 'source_objects': current,
            'planner_objects': {name: value for name, value in current.items() if name.startswith(PLANNER_ROOT)},
            **selection, 'execution_claim': 'Selection only; no prior execution or cross-head proof reused.'}


def revision_tree(root, head):
    return git(root, 'rev-parse', head + '^{tree}').decode().strip()


def fingerprint(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
