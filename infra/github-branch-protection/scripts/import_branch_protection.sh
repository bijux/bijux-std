#!/usr/bin/env bash
set -euo pipefail

repos=("bijux-std" "bijux.github.io")

for repo in "${repos[@]}"; do
  echo "Importing ${repo}:main"
  terraform import -input=false "github_branch_protection.main[\"${repo}\"]" "${repo}:main" >/dev/null 2>&1 || true
done
