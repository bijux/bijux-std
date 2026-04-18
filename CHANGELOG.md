# Changelog

This file records notable repository-level changes for `bijux-std`.

It does not replace package-level release history. `bijux-std` exists to own
cross-repository standards surfaces, not product package release streams.

The goal of this changelog is to explain standard changes that affect how
multiple Bijux repositories verify, synchronize, and consume shared contracts.

## Unreleased

### Changed

- Refreshed `shared/shared-dir-sha256.txt` so the canonical digest entry for
  `shared/bijux-gh` matches the current shared governance content.
- Promoted a shared `release-pypi.yml` workflow template under
  `shared/bijux-gh/workflows` with one configuration surface
  (`.github/release.env` plus repository variables) and dual-mode
  publication support (`maturin` and artifact-based trusted publishing).
- Promoted a shared `release-crates.yml` workflow template under
  `shared/bijux-gh/workflows` with one configuration surface
  (`.github/release.env` plus repository variables) and per-repository
  enable/disable controls.
- Promoted a shared `release-ghcr.yml` workflow template under
  `shared/bijux-gh/workflows` with one configuration surface
  (`.github/release.env` plus repository variables), plus matrix-based
  package publication controls for repositories that publish release bundles to
  GHCR.
- Added allowlist gates across shared release workflows so `.github/release.env`
  can explicitly constrain which crate/package slugs are publishable for
  crates.io, PyPI artifact mode, and GHCR.
- Added shared artifact release orchestration templates:
  `shared/bijux-gh/workflows/build-release-artifacts.yml` and
  `shared/bijux-gh/workflows/release-artifacts.yml`, so repositories can run
  build, GHCR, PyPI artifact mode, and GitHub release publication from one
  standardized workflow contract.
- Extended `release-github.yml` with explicit enable/disable control
  (`BIJUX_RELEASE_ENABLED`) so repositories can avoid duplicate direct tag
  release runs when using orchestrated release lanes.
- Added canonical issue and pull request template surfaces under
  `shared/bijux-gh/ISSUE_TEMPLATE` and `shared/bijux-gh/PULL_REQUEST_TEMPLATE`
  so consuming repositories can share one durable intake and review structure.

## 0.1.1 - 2026-04-18

### Added

- New shared GitHub governance tooling under `shared/bijux-gh`, including
  generated Dependabot configuration rendering from discovered Python
  manifests.
- New shared make surfaces for governance sync and drift checks that consume
  the canonical shared tooling tree.
- New standards tests and live navigation release-gate coverage for the shared
  docs shell behavior across phone, tablet, and desktop profiles.

### Changed

- Shared standards directory contracts and manifest digests were refreshed
  repeatedly as canonical docs shell, checks, and governance assets evolved.
- Shared internal tooling layout now uses durable naming and directory
  ownership, including migration away from transitional internal naming.
- Bookkeeping update: synchronized consuming repositories now document explicit
  contributor and automation identity boundaries for `bijux`,
  `dependabot[bot]`, and `github-actions[bot]` under their governance docs.
- Standards CI now uses a single matrix workflow at
  `.github/workflows/bijux-std.yml` that runs both standard checks and checks
  reporting.
- Shared branch-protection status-check policy now tracks matrix contexts
  `checks (standard)` and `checks (report)` for the unified workflow.

### Fixed

- Shared docs shell now restores canonical Mermaid initializer sync behavior.
- Shared docs navigation behavior was stabilized for scoped sidebars and mobile
  drawer interactions, including hub/project continuity across viewports.
- Shared manifest comparison logic now validates required directory entries
  deterministically against canonical standards inputs.
- Root README now documents the canonical shared inventory and check inputs,
  including workflow-template and manifest contract references.

## 0.1.0 - 2026-04-16

### Added

- Canonical standards repository structure under `shared/`, including:
  `shared/bijux-docs`, `shared/bijux-makes-py`, and `shared/bijux-checks`.
- Shared SHA manifest contract at `shared/shared-dir-sha256.txt` for
  machine-verifiable standards drift detection.
- Shared standard policy and check/update scripts in `shared/bijux-checks`,
  including branch-based and tag-based update support.
- Repository-level make entrypoints:
  `bijux-std-checks`, `bijux-std-update`, and compatibility alias
  `bijux-std`.
- Standards CI workflow at `.github/workflows/bijux-std.yml`.
- Root repository `README.md` documenting ownership boundaries, consumption
  model, verification model, and change rules.

### Changed

- Canonical standard remote address now uses the repository URL
  `https://github.com/bijux/bijux-std`, while raw-content fetch paths are
  derived internally by the checker.

## Changelog Scope

Use this file for changes such as:

- shared standards surfaces under `shared/`
- repository-level standard verification and update workflows
- cross-repository contract policy and checksum model changes
- standards release and adoption guidance

Do not use this file for project-specific domain behavior or package-only
release notes from consuming repositories.
