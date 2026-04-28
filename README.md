# bijux-std

`bijux-std` is the canonical standards distribution repository for the Bijux
ecosystem.

Policy baseline: repository-local governance files and shared standards sources.

It defines the shared repository surfaces that should stay aligned across Bijux
projects, distributes them for downstream use, and makes that alignment
verifiable in CI.

Its role is simple: edit shared standards once, propagate them deliberately,
and verify them everywhere.

## What `bijux-std` Is

`bijux-std` is not a product repository and not a general utilities dump.

It owns the cross-repository standards layer for Bijux: the shared assets,
automation, and checks that should remain consistent across repositories.

## What This Repository Owns

`bijux-std` owns only shared surfaces that are intended to remain aligned
across repositories.

- `shared/bijux-docs`
  Shared documentation shell: partials, styles, and scripts used by Bijux
  documentation sites.
- `shared/bijux-makes-py`
  Shared Python-oriented make modules and package automation building blocks.
- `shared/bijux-checks`
  Shared standard checks, update flows, and the policy file that defines the
  standard contract.
- `shared/bijux-docs/tooling`
  Shared docs synchronization and docs-contract/source-of-truth verification
  tooling used by consuming repositories.
- `.github`
  Canonical GitHub standards surfaces: reusable workflow templates, policy
  workflows, standards scripts, and manifest-driven generators for
  repository-local wrapper/config files.
- `shared/shared-dir-sha256.txt`
  Canonical SHA manifest for the shared directories above.

## What This Repository Does Not Own

`bijux-std` does not own:

- product or domain code
- repository-specific package logic
- repository-specific documentation content
- release behavior unique to a single repository
- one-off local automation
- live GitHub repository settings enforced through the GitHub API

Live GitHub governance now belongs in `bijux-iac`. `bijux-std` owns the
repository-local standards content that may be synchronized into consumers, but
it does not own the Terraform control plane that applies branch protection and
other repo-admin policy.

If a change belongs only to one repository, it should stay there.

## Why This Repository Exists

Without a canonical standards repository, shared behavior drifts quietly:

- one repository fixes a docs shell bug while others keep the old behavior
- one repository updates a make contract while another keeps stale targets
- one repository silently forks shared automation and stops behaving like the
  rest of the family

`bijux-std` prevents that by making the shared layer explicit, reviewable, and
machine-checkable.

## Repository Layout

```text
shared/
├── bijux-checks/          # shared compliance and update flows
├── bijux-docs/            # shared docs and website shell assets
├── bijux-docs/tooling/    # shared docs sync and verification tooling
├── bijux-gh/              # legacy shared GitHub policy sources
├── bijux-makes-py/        # shared Python-oriented make modules
└── shared-dir-sha256.txt  # canonical content-hash manifest
```

## Consumption Model

Consuming repositories vendor the shared directories from `bijux-std` into
their own `.bijux/shared/` tree.

The current standard is `.bijux`-only for consumers. Root-level `shared/`
content in consuming repositories is treated as legacy layout drift and fails
standard verification.

The expected flow is:

1. Update canonical shared files in `bijux-std`.
2. Propagate the changed shared directories into consuming repositories.
3. Commit synchronized changes in each consuming repository.
4. Run the standard verification target in CI.
5. Fail CI if vendored shared directories drift from the canonical standard.

This keeps repositories autonomous in domain behavior while preserving a stable
shared platform layer across the ecosystem.

The current standard directory contract is declared in
[`shared/bijux-checks/bijux-std-checks.yml`](shared/bijux-checks/bijux-std-checks.yml).

## Shared Inventory And Check Inputs

The canonical shared inventory currently includes:

- `shared/bijux-docs`
- `shared/bijux-makes-py`
- `shared/bijux-checks`
- `.github`

Checks and updates are driven by these standard inputs:

- Inventory and source policy:
  [`shared/bijux-checks/bijux-std-checks.yml`](shared/bijux-checks/bijux-std-checks.yml)
- Canonical inventory digests:
  [`shared/shared-dir-sha256.txt`](shared/shared-dir-sha256.txt)
- Canonical GitHub standards layer:
  [`.github/`](.github)
- Typed repository config manifest:
  [`.github/standards/repo-config.manifest.json`](.github/standards/repo-config.manifest.json)
- Workflow inventory registry:
  [`.github/standards/workflow-inventory.json`](.github/standards/workflow-inventory.json)
- Canonical renderer/sync tooling:
  [`.github/scripts/render_repo_configs.py`](.github/scripts/render_repo_configs.py),
  [`.github/scripts/sync_github_standards.py`](.github/scripts/sync_github_standards.py)

## Verification Model

`bijux-std` is designed to answer one concrete question:

> Does this repository still match the canonical Bijux shared standard?

The verification contract is intentionally strict:

- standard directories are declared explicitly in policy
- each standard directory has a canonical content hash
- downstream repositories carry vendored shared directories
- checks verify both:
  - the manifest matches `bijux-std`
  - directory contents match the recorded hashes

## Standard Commands

This repository exposes the same standard commands that consuming repositories
use:

### Verify compliance

```bash
make bijux-std-checks
```

Verifies configured shared directories against the canonical manifest.

### Update shared standard surfaces

```bash
make bijux-std-update
```

Refreshes shared directories from canonical `bijux-std`.

### Compatibility alias

```bash
make bijux-std
```

Backward-compatible alias for `make bijux-std-checks`.

The shared policy for these commands lives in
[`shared/bijux-checks/bijux-std-checks.yml`](shared/bijux-checks/bijux-std-checks.yml).

For workspace setups where `bijux-std` is not a sibling directory, standards
scripts that consume repository manifests can be pointed explicitly with
`BIJUX_STD_REPO=/absolute/path/to/bijux-std`.


## GitHub Workflow Contract

The canonical standards workflow is [`.github/workflows/bijux-std.yml`](.github/workflows/bijux-std.yml).

Repository-local filter policy:

- `bijux-std` keeps only standards governance workflows active under
  `.github/workflows`:
  - `bijux-std.yml`
  - `automerge-pr.yml`
- Shared release/docs/reusable workflow templates live under
  `shared/bijux-gh/workflows` and are synchronized into consumer repositories
  under `.github/workflows`.
- Consumer runtime workflow copies are filtered by manifest-driven
  `workflow_allowlist` entries, so each repository only gets registered
  allowlisted managed workflows.

It runs one matrix job (`checks`) with two entries on every pull request and push to `main`:

- `standard`: runs `make bijux-std-checks`
- `report`: runs the check-suite reporter and uploads `bijux-checks-report` artifacts

Branch protection should require both matrix check contexts:

- `checks (standard)`
- `checks (report)`

When workflow or job names change, update these files in the same change:

- `.github/required-status-checks.md`
- `.github/rulesets/main-branch-protection.json`

Ownership mapping for governance-sensitive paths is defined in:

- `.github/CODEOWNERS`

`automerge-pr.yml` enables auto-merge only when policy allows and either a
trusted CODEOWNER approval exists or the trusted PR author is a CODEOWNER.
The workflow attempts enablement on pull-request/review events and re-runs
after a successful `bijux-std` `workflow_run` to cover unstable early states.
When the follow-up run sees a clean merge-ready pull request, it merges
directly to complete the automation path.

## Live GitHub Governance

Live GitHub settings for Bijux repositories are enforced from `bijux-iac`, not
from `bijux-std`. That includes the Terraform-owned `main` branch protection
surface that previously lived under `infra/github/main-branch-protection` in
this repository.

## UI Regression Checks

`bijux-std` also includes viewport-aware UI/UX regression checks for the shared
docs shell in [`tests/`](tests).

### Install test dependencies

```bash
make ui-test-install
make ui-test-install-browsers
```

### Run UI checks

```bash
make ui-test
```

The suite validates expected behavior for phone, normal/tablet, and wide
desktop breakpoints, including drawer-first phone behavior, ribbon visibility
rules, and viewport profile contracts.

To run only navigation journey regressions:

```bash
make ui-test-navigation
```

To run the full navigation release gate (contract + deep quality checks):

```bash
make ui-test-release-gate
```

To run live-site navigation gates against real synced sites:

```bash
BIJUX_LIVE_E2E=1 make ui-test-live-navigation
```

Optionally pin a different hub entry URL:

```bash
BIJUX_LIVE_E2E=1 BIJUX_LIVE_HUB_URL=https://bijux.io/ make ui-test-live-navigation
```

## Update And Release Model

`bijux-std` supports two adoption modes:

- branch-based updates for active standards development
- tag-based updates for a stable, pinned baseline

Typical controls include:

- `BIJUX_STD_REF`
- `BIJUX_STD_UPDATE_CHANNEL`
- `BIJUX_STD_TAG_PATTERN`

This allows repositories to choose between faster adoption and stricter
stability while staying on the same standard contract.

## Change Policy

A change belongs in `bijux-std` when all of the following are true:

- it affects multiple repositories
- it should remain identical across those repositories
- it belongs to shared shell assets, shared automation, or shared compliance
- it should be centrally updated and centrally verified

A change does not belong in `bijux-std` when it is:

- product-specific
- domain-specific
- repository-specific
- release-specific
- intended only as a local customization

Keep `bijux-std` narrow. It should own the shared standards layer and nothing
else.

## In One Sentence

`bijux-std` is the canonical, CI-verifiable shared standards distribution
repository for Bijux documentation shell assets, docs verification tooling,
GitHub policy artifacts, Python-oriented make automation, and cross-repository
compliance.

## License

Apache-2.0. See `LICENSE` and `NOTICE`.
