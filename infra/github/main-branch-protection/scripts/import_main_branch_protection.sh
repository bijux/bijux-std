#!/usr/bin/env bash
set -euo pipefail

readonly TFVARS_PATH="terraform.auto.tfvars.json"

while IFS= read -r repo; do
  if [[ -z "${repo}" ]]; then
    continue
  fi
  echo "Importing ${repo}:main"
  terraform import -input=false "github_branch_protection.main[\"${repo}\"]" "${repo}:main" >/dev/null 2>&1 || true
done < <(
  TFVARS_PATH="${TFVARS_PATH}" python3 - <<'PY'
import json
import os

with open(os.environ["TFVARS_PATH"], encoding="utf-8") as handle:
    data = json.load(handle)

for repo in data.get("protected_repositories", []):
    print(repo)
PY
)
