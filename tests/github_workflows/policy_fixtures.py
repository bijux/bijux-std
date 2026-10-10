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


def source_fixture(directory, *, selected=False):
    """Build an owning standard fixture; never read a consumer checkout."""
    import shutil
    root = (Path(directory) / "owning-standard").resolve()
    shutil.copytree(ROOT / ".github", root / ".github", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "shared/bijux-gh", root / "shared/bijux-gh")
    guard = "shared/bijux-checks/scripts/verify-accepted-source.sh"
    (root / guard).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / guard, root / guard)
    actual_manifest = json.loads((root / ".github/standards/repo-config.manifest.json").read_text())
    repo = next(entry for entry in actual_manifest["repositories"] if entry["name"] == "bijux-atlas")
    # The default fixture deliberately exercises an unselected repository;
    # production family entries now select the controller publication policy.
    repo.pop("workflow_execution_policy", None)
    (root / ".github/standards/repo-config.manifest.json").write_text(json.dumps(actual_manifest, indent=2) + "\n")
    if selected:
        repo["workflow_allowlist"] = [entry["id"] for entry in actual_manifest["workflow_inventory"]["managed_workflows"]]
        repo["workflow_execution_policy"] = copy.deepcopy(POLICY)
        for name in ["release-ghcr", "release-crates"]:
            repo["workflow_execution_policy"]["publication_entrypoints"][name] = {"mode": "manual-only"}
        (root / ".github/standards/repo-config.manifest.json").write_text(json.dumps(actual_manifest, indent=2) + "\n")
    loader = root / ".github/scripts/workflow_execution/source_loading.py"
    from types import ModuleType
    module = ModuleType("bijux_owned_fixture_loader")
    module.__file__ = str(loader)
    source = loader.read_bytes()
    exec(compile(source, str(loader), "exec"), module.__dict__)
    owned = module.load_package(source)
    refresh_snapshots(root, owned)
    return root, owned


def refresh_snapshots(root, owned):
    for relative, body in owned.capture_sources(root).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)


def projection_fixture(source, owned, target, repository="bijux-atlas"):
    expected, _ = owned.verification.expected_projection(source, target, repository)
    for relative, body in expected.items():
        if body is not None:
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
    return expected


def byte_tree(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file() and ".git" not in path.relative_to(root).parts}
