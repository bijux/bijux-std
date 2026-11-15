"""Native provider declarations for fresh qualification, never execution authority.

GitLab job IDs identify individual executions; a pipeline has no synthetic global
attempt. Live provider metadata must independently establish receipt ownership.
"""
from __future__ import annotations

import os
import re
from urllib.parse import urlsplit


def gitlab() -> bool:
    detected = os.environ.get('GITLAB_CI') == 'true' or any(
        key in os.environ for key in ('CI_PROJECT_ID', 'CI_PIPELINE_ID', 'CI_JOB_ID', 'CI_SERVER_URL'))
    if detected and any(key in os.environ for key in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_ACTIONS')):
        raise ValueError('Ambiguous native CI provider identity')
    return detected


def validate(identity: dict) -> dict:
    keys = {'provider', 'server_url', 'project_id', 'project_path', 'pipeline_id', 'job_id', 'commit_sha'}
    if not isinstance(identity, dict) or set(identity) != keys or identity.get('provider') != 'gitlab':
        raise ValueError('Complete native GitLab execution identity is required')
    if any(not isinstance(identity[key], str) or re.fullmatch(r'[1-9][0-9]*', identity[key]) is None
           for key in ('project_id', 'pipeline_id', 'job_id')):
        raise ValueError('Actual positive GitLab project, pipeline and job IDs are required')
    server, project = identity['server_url'], identity['project_path']
    if not isinstance(server, str) or any(char.isspace() for char in server):
        raise ValueError('Native GitLab server URL is required')
    parsed = urlsplit(server)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        raise ValueError('Native GitLab server must be an HTTPS origin')
    if (not isinstance(project, str) or len(project.split('/')) < 2
            or any(re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', part) is None for part in project.split('/'))):
        raise ValueError('Native GitLab project path is required')
    if not isinstance(identity['commit_sha'], str) or re.fullmatch(r'[a-f0-9]{40}', identity['commit_sha']) is None:
        raise ValueError('Actual full GitLab checkout SHA is required')
    return dict(identity)


def execution_identity() -> dict:
    if not gitlab():
        raise ValueError('Native GitLab execution identity is unavailable')
    return validate({'provider': 'gitlab', **{name: os.environ.get(variable) for name, variable in (
        ('server_url', 'CI_SERVER_URL'), ('project_id', 'CI_PROJECT_ID'), ('project_path', 'CI_PROJECT_PATH'),
        ('pipeline_id', 'CI_PIPELINE_ID'), ('job_id', 'CI_JOB_ID'), ('commit_sha', 'CI_COMMIT_SHA'))}})


def pipeline_identity() -> dict:
    return {key: value for key, value in execution_identity().items() if key != 'job_id'}


def workflow_identity() -> dict:
    if gitlab():
        return execution_identity()
    return {'workflow_run_id': os.environ.get('GITHUB_RUN_ID'), 'workflow_attempt': os.environ.get('GITHUB_RUN_ATTEMPT')}


def verify_workflow(supplied: dict, expected: dict | None = None) -> dict:
    if gitlab():
        actual = validate(supplied)
        if {key: value for key, value in actual.items() if key != 'job_id'} != pipeline_identity():
            raise ValueError('Receipt does not bind this GitLab pipeline and checkout')
        if expected is not None and actual != validate(expected):
            raise ValueError('Receipt differs from its exact GitLab executor')
        return actual
    if supplied != (workflow_identity() if expected is None else expected):
        raise ValueError('Receipt workflow execution identity mismatch')
    return supplied


def refuse_retained_proof() -> None:
    if gitlab():
        execution_identity()
        raise ValueError('Unsupported operation: gitlab retained-proof recovery; full fresh execution is required')
