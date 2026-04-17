# bijux-std

`bijux-std` is the canonical standards distribution repository for the Bijux
ecosystem.

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
- `shared/shared-dir-sha256.txt`
  Canonical SHA manifest for the shared directories above.

## What This Repository Does Not Own

`bijux-std` does not own:

- product or domain code
- repository-specific package logic
- repository-specific documentation content
- release behavior unique to a single repository
- one-off local automation

If a change belongs only to one repository, it should stay there.

## Why This Repository Exists

Without a canonical standards repository, shared behavior drifts quietly:

- one repository fixes a docs shell bug while others keep the old behavior
- one repository updates a make contract while another keeps stale targets
- one repository silently forks shared automation and stops behaving like the
  rest of the family

`bijux-std` prevents that by making the shared layer explicit, reviewable, and
machine-checkable.

## Consumption Model

Sibling repositories vendor the shared directories into their own `shared/`
tree and expose standard commands through their `Makefile` or `makes/`
modules.

The expected flow is:

1. Update canonical shared files in `bijux-std`.
2. Propagate the changed shared directories into consuming repositories.
3. Run `make bijux-std-checks` in each repository to verify that local shared
   copies still match this standard.
4. Commit the propagated changes in each repository.

Repositories may extend their own local automation, but they must not silently
fork the shared standard surfaces.

## Standard Commands

This repository exposes the same standard commands that consuming repositories
use:

- `make bijux-std-checks`
  Verifies the configured shared directories against the canonical manifest.
- `make bijux-std-update`
  Refreshes shared directories from the canonical `bijux-std` source, using
  either a branch ref or the latest matching tag.
- `make bijux-std`
  Backward-compatible alias for `make bijux-std-checks`.

The shared policy for these commands lives in
[`shared/bijux-checks/bijux-std-checks.yml`](shared/bijux-checks/bijux-std-checks.yml).

## Verification Model

The standard contract is intentionally simple:

- a fixed list of shared directories is declared in the policy file
- each directory has a canonical tree SHA in `shared/shared-dir-sha256.txt`
- consuming repositories verify both:
  - their manifest matches `bijux-std`
  - their actual directory contents match the recorded SHA

This gives Bijux one durable, machine-checkable answer to the question:
"does this repository still match the shared standard?"

## Release Model

`bijux-std` is meant to support both fast and stable adoption paths:

- branch-based updates for active standard development
- tag-based updates for repositories that want a more stable pinned standard

That is why the update flow supports both `BIJUX_STD_REF` and
`BIJUX_STD_UPDATE_CHANNEL=tag`.

## Change Rules

Changes belong in `bijux-std` when they affect multiple repositories and should
remain identical across them over time.

Changes do not belong here when they only describe one repository's domain,
release stream, package surface, or product behavior.

The goal is not to centralize everything. The goal is to centralize only the
shared layer that must stay consistent.
