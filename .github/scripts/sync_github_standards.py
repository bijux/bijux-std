#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STD_REPO = ROOT / "bijux-std"

DEFAULT_REPOS = [
    "bijux-atlas",
    "bijux-canon",
    "bijux-core",
    "bijux-masterclass",
    "bijux-pollenomics",
    "bijux-proteomics",
    "bijux.github.io",
]

SHARED_FILES = [
    ".github/ISSUE_TEMPLATE/bug-report.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/feature-request.yml",
    ".github/PULL_REQUEST_TEMPLATE/default.md",
    ".github/PULL_REQUEST_TEMPLATE/release-change.md",
    ".github/automation-identity.md",
    ".github/required-status-checks.md",
    ".github/rulesets/main-branch-protection.json",
    ".github/scripts/check_pinned_actions.py",
    ".github/scripts/wait_for_ci.py",
    ".github/workflows/bijux-std.yml",
    ".github/workflows/build-release-artifacts.yml",
    ".github/workflows/deploy-docs.yml",
    ".github/workflows/release-artifacts.yml",
    ".github/workflows/release-github.yml",
    ".github/workflows/reusable-ci-python-packages.yml",
    ".github/workflows/reusable-verify-python-packages.yml",
    ".github/workflows/reusable-ci-rust-stack.yml",
    ".github/bijux-std-shared.sha256",
]


def run(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def copy_shared_files(target_repo: str) -> None:
    for relative in SHARED_FILES:
        source = STD_REPO / relative
        destination = ROOT / target_repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())


def has_changes(repo_name: str) -> bool:
    status = run(["git", "status", "--short"], cwd=ROOT / repo_name)
    return bool(status)


def commit_and_optionally_pr(repo_name: str, args: argparse.Namespace) -> None:
    repo_dir = ROOT / repo_name
    branch_name = f"{args.branch_prefix}/{repo_name}"

    if args.create_branch:
        run(["git", "checkout", "-b", branch_name], cwd=repo_dir)

    run(["git", "add", ".github"], cwd=repo_dir)
    run(["git", "commit", "-m", args.commit_message], cwd=repo_dir)

    if args.open_pr:
        run(["git", "push", "-u", "origin", branch_name], cwd=repo_dir)
        run(
            [
                "gh",
                "pr",
                "create",
                "--base",
                args.base_branch,
                "--head",
                branch_name,
                "--title",
                args.pr_title,
                "--body",
                args.pr_body,
            ],
            cwd=repo_dir,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync shared .github standards into consumer repositories")
    parser.add_argument("--repo", action="append", default=[], help="Repository name (repeatable)")
    parser.add_argument("--create-branch", action="store_true", help="Create per-repo branch before commit")
    parser.add_argument("--open-pr", action="store_true", help="Push and open PR for each changed repository")
    parser.add_argument("--base-branch", default="main", help="PR base branch")
    parser.add_argument("--branch-prefix", default="chore/github-standards-sync", help="Branch prefix")
    parser.add_argument("--commit-message", default="chore(github): sync shared standards and generated config", help="Commit message")
    parser.add_argument("--pr-title", default="chore(github): sync shared standards and generated config", help="PR title")
    parser.add_argument("--pr-body", default="Synchronize shared .github templates from bijux-std and regenerate repository-local config files.", help="PR body")
    args = parser.parse_args()

    repos = args.repo or DEFAULT_REPOS

    render_script = STD_REPO / ".github/scripts/render_repo_configs.py"
    subprocess.run(["python3", str(render_script), "--repo", "bijux-std"], check=True)

    for repo in repos:
        copy_shared_files(repo)
        subprocess.run(["python3", str(render_script), "--repo", repo], check=True)
        subprocess.run(["sha256sum", "--check", ".github/bijux-std-shared.sha256"], cwd=ROOT / repo, check=True)

        if has_changes(repo):
            commit_and_optionally_pr(repo, args)


if __name__ == "__main__":
    main()
