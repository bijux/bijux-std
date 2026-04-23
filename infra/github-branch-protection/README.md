# GitHub Branch Protection IaC

Terraform source for PR-only protection on critical repositories.

## Managed repositories

- `bijux/bijux-std`
- `bijux/bijux.github.io`

## Main branch policy

- pull request required
- one approving review required
- admin bypass disabled
- force push disabled
- branch deletion disabled
- conversation resolution required

## CI flow

- `.github/workflows/github-governance-plan.yml` on pull requests
- `.github/workflows/github-governance-apply.yml` on `main` and manual dispatch

CI imports current branch protection resources before plan/apply so governance can run without a separate persistent Terraform backend.

## Required secret

Set repository secret on `bijux-std`:

- `GH_ADMIN_TOKEN`: token with repository administration permission for both managed repositories.
