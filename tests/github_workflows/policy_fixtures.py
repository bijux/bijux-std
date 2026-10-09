"""Source-owned workflow policy fixtures and package loader for focused controls."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("bijux_policy_fixture_renderer", ROOT / ".github/scripts/render_repo_configs.py")
assert SPEC is not None and SPEC.loader is not None
RENDERER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RENDERER)
MODULE = RENDERER.WORKFLOW_EXECUTION
INVENTORY = json.loads((ROOT / ".github/standards/workflow-inventory.json").read_text())
POLICY = {
    "schema": 1,
    "automatic_runs": "repository-policy-only",
    "dependency_pull_requests": "skip-managed-jobs",
    "publication_entrypoints": {
        "deploy-docs": {"mode": "manual-only", "refs": "main-only"},
        "release-github": {"mode": "manual-only"},
    },
}


def manifest(policy=POLICY, name="bijux-atlas"):
    return {"workflow_inventory": copy.deepcopy(INVENTORY), "repositories": [{
        "name": name, "workflow_allowlist": ["github-policy", "deploy-docs", "release-github"],
        "workflow_execution_policy": copy.deepcopy(policy),
    }]}
