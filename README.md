# bijux-std

This repo is where we keep the shared Bijux standards in one place.

Workspace policy baseline: [`/Users/bijan/bijux/README.md`](/Users/bijan/bijux/README.md)

The working model is straightforward:

1. change the shared thing here
2. sync it into the repos that consume it
3. run checks so drift is caught fast

That is the whole point of `bijux-std`. We do not want ten repos quietly
forking the same docs shell, GitHub files, make targets, or compliance checks.

## What this repo is

This is not a product repo and not a random utilities bucket.

This is the canonical source for the shared repo surfaces that should stay the
same across the Bijux repos.

## What lives here

- `shared/bijux-docs`
  Shared docs shell files: partials, styles, scripts, and assets used by Bijux
  docs sites.
- `shared/bijux-makes-py`
  Shared make building blocks used in Python-oriented repos.
- `shared/bijux-checks`
  Shared standards checks, update flows, and the contract that says what the
  standard is.
- `shared/bijux-docs/tooling`
  Shared docs sync and verification tooling.
- `.github`
  Canonical GitHub standards content: managed workflows, policy workflows,
  standards scripts, manifests, and generators for repo-local config.
- `shared/shared-dir-sha256.txt`
  The canonical hash manifest for the shared directories above.

## What does not live here

Do not use `bijux-std` for:

- product code
- domain logic
- repo-specific package behavior
- repo-specific docs content
- one-off local automation
- release behavior that belongs to only one repo
- live GitHub admin settings applied through the API

Live GitHub governance moved to `bijux-iac`.

So the split is:

- `bijux-std` owns synced repo content
- `bijux-iac` owns live GitHub admin control

If a change belongs to one repo only, keep it there.

## Why we keep this repo

Without a real source of truth, shared behavior drifts fast.

One repo fixes a docs shell bug. Another repo keeps the old shell.
One repo changes a make contract. Another repo still exposes the old target.
One repo hand-edits shared GitHub files and slowly stops behaving like the rest.

`bijux-std` exists so we stop that kind of slow drift.

## Layout

```text
shared/
├── bijux-checks/          # shared compliance and update flows
├── bijux-docs/            # shared docs and website shell assets
├── bijux-docs/tooling/    # shared docs sync and verification tooling
├── bijux-gh/              # legacy shared GitHub policy sources
├── bijux-makes-py/        # shared Python-oriented make modules
└── shared-dir-sha256.txt  # canonical content-hash manifest
```

## How consumer repos use this

Consumer repos vendor the shared directories from `bijux-std` into their own
`.bijux/shared/` tree.

The current standard is `.bijux` only for consumers. Root-level `shared/` in a
consumer repo is treated as legacy drift and should fail verification.

Normal flow:

1. update the canonical shared files here
2. sync the changed directories into the consumer repos
3. commit the synced changes there
4. run the standard checks
5. let CI fail if the shared layer drifted

That gives each repo freedom in its own domain while the shared platform layer
stays aligned.

The current shared-directory contract lives in
[`shared/bijux-checks/bijux-std-checks.yml`](shared/bijux-checks/bijux-std-checks.yml).

## Shared inventory and check inputs

Current shared inventory:

- `shared/bijux-docs`
- `shared/bijux-makes-py`
- `shared/bijux-checks`
- `.github`

The main inputs behind checks and sync are:

- Inventory and source policy:
  [`shared/bijux-checks/bijux-std-checks.yml`](shared/bijux-checks/bijux-std-checks.yml)
- Canonical shared digests:
  [`shared/shared-dir-sha256.txt`](shared/shared-dir-sha256.txt)
- Canonical GitHub standards layer:
  [`.github/`](.github)
- Typed repo config manifest:
  [`.github/standards/repo-config.manifest.json`](.github/standards/repo-config.manifest.json)
- Workflow inventory:
  [`.github/standards/workflow-inventory.json`](.github/standards/workflow-inventory.json)
- Renderer and sync tooling:
  [`.github/scripts/render_repo_configs.py`](.github/scripts/render_repo_configs.py),
  [`.github/scripts/sync_github_standards.py`](.github/scripts/sync_github_standards.py)

## How verification works

The check we care about is simple:

> does this repo still match the canonical Bijux shared standard?

The answer is enforced with explicit inventory, explicit hashes, vendored shared
directories in downstream repos, and checks that compare both the manifest and
the actual directory contents.

## Standard commands

These are the standard commands consumer repos use too.

### Verify compliance

```bash
make bijux-std-checks
```

This verifies configured shared directories against the canonical manifest.

### Update shared standard surfaces

```bash
make bijux-std-update
```

This refreshes shared directories from canonical `bijux-std`.

### Compatibility alias

```bash
make bijux-std
```

This is just the backward-compatible alias for `make bijux-std-checks`.

The policy behind these commands lives in
[`shared/bijux-checks/bijux-std-checks.yml`](shared/bijux-checks/bijux-std-checks.yml).

If your workspace layout is unusual and `bijux-std` is not a sibling
directory, point the scripts explicitly with
`BIJUX_STD_REPO=/absolute/path/to/bijux-std`.

## GitHub workflow contract

The canonical standards workflow is
[`.github/workflows/bijux-std.yml`](.github/workflows/bijux-std.yml).

`bijux-std` itself keeps only the standards governance workflows active under
`.github/workflows`:

- `bijux-std.yml`
- `automerge-pr.yml`

Shared release/docs/reusable workflow templates live under
`shared/bijux-gh/workflows` and get synced into consumer repos under
`.github/workflows`.

What each consumer repo actually gets is controlled by manifest-driven
`workflow_allowlist` entries.

The standard workflow runs a matrix with two entries on pull requests and pushes
to `main`:

- `standard`: runs `make bijux-std-checks`
- `report`: runs the check-suite reporter and uploads `bijux-checks-report`
  artifacts

Branch protection should require both matrix contexts:

- `checks (standard)`
- `checks (report)`

If workflow or job names change, update these in the same change:

- `.github/required-status-checks.md`
- `.github/rulesets/main-branch-protection.json`

Governance-sensitive path ownership is declared in:

- `.github/CODEOWNERS`

`automerge-pr.yml` turns on auto-merge only when policy allows it and the PR is
already trusted and merge-ready.

## Live GitHub governance

Live GitHub settings for Bijux repos are enforced from `bijux-iac`, not from
`bijux-std`.

That includes the Terraform-owned `main` branch protection surface that used to
live under `infra/github/main-branch-protection` here.

## UI regression checks

`bijux-std` also carries viewport-aware UI checks for the shared docs shell in
[`tests/`](tests).

### Install test dependencies

```bash
make ui-test-install
make ui-test-install-browsers
```

### Run UI checks

```bash
make ui-test
```

The suite checks phone, normal/tablet, and wide desktop behavior, including
drawer-first phone behavior, ribbon visibility rules, and viewport profile
contracts.

To run only navigation journey regressions:

```bash
make ui-test-navigation
```

To run the full navigation release gate:

```bash
make ui-test-release-gate
```

To run live-site navigation gates against real synced sites:

```bash
BIJUX_LIVE_E2E=1 make ui-test-live-navigation
```

To pin a different hub entry URL:

```bash
BIJUX_LIVE_E2E=1 BIJUX_LIVE_HUB_URL=https://bijux.io/ make ui-test-live-navigation
```

## Update and release model

`bijux-std` supports two adoption modes:

- branch-based updates for active standards work
- tag-based updates for a stricter pinned baseline

Typical controls:

- `BIJUX_STD_REF`
- `BIJUX_STD_UPDATE_CHANNEL`
- `BIJUX_STD_TAG_PATTERN`

That gives each repo a choice between faster adoption and stricter stability
without leaving the shared contract.

## Change policy

A change belongs here when all of this is true:

- it affects multiple repos
- it should stay identical across those repos
- it belongs to shared shell assets, shared automation, or shared compliance
- it should be updated and verified centrally

A change does not belong here when it is:

- product-specific
- domain-specific
- repo-specific
- release-specific
- only a local customization

Keep `bijux-std` narrow. It should own the shared layer and not more than that.

## In one line

`bijux-std` is the place where we define the shared Bijux repo standard once
and make the rest of the repos prove they still match it.

## License

This repository is licensed under the MIT License. Copyright 2026 Bijan
Mousavi <bijan@bijux.io>. See [`LICENSE`](LICENSE).
