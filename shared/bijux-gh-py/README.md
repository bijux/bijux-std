# Bijux GitHub Governance Pack (Python)

Canonical source-of-truth for Python-first Bijux repositories:

- `.github/dependabot.yml`
- `.github/required-status-checks.md`
- `.github/rulesets/main-branch-protection.json`

Usage in a repository:

1. Keep this pack synchronized via `make bijux-std-update`.
2. Apply files into `.github/` with `make bijux-gh-py-sync`.
3. Enforce drift checks with `make bijux-gh-py-check`.

This keeps branch protection and bot update policy consistent across Python repositories.
