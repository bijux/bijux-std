# Standards foundation archive

These are the 43 material statements preserved from the prior changelog at
[b11c6e1](https://github.com/bijux/bijux-std/commit/b11c6e19a3368ef31ed80c7f713e20794681f431).
They describe historical contracts; the PR history records subsequent changes.
Text-introduction commits identify when the changelog statement appeared, not
the first implementation of every described behavior. Foundational source
changes do not receive invented PR numbers or release dates.

## Governance and release foundations

Original changelog heading: `Unreleased`.

- **Changed.** Promoted `.github` as the canonical GitHub standards layer, including reusable CI/verify templates, protected-change policy checks, and centralized standards orchestration scripts.
  Text introduction: [7532d93](https://github.com/bijux/bijux-std/commit/7532d9334fb9448f5959f4eaecd21f41423487a9).

- **Changed.** Extended typed manifest coverage to include repository-local wrapper workflows (`.github/workflows/ci.yml`, `.github/workflows/verify.yml`) so wrappers are rendered instead of hand-maintained.
  Text introduction: [7532d93](https://github.com/bijux/bijux-std/commit/7532d9334fb9448f5959f4eaecd21f41423487a9).

- **Changed.** Added per-repository standard pin file `.github/standards/bijux-std.sha` and sync orchestration support for advancing this pin.
  Text introduction: [7532d93](https://github.com/bijux/bijux-std/commit/7532d9334fb9448f5959f4eaecd21f41423487a9).

- **Changed.** Extended standards checksum scope (`.github/bijux-std-shared.sha256`) to include manifest/generator/policy assets and shared workflow templates.
  Text introduction: [7532d93](https://github.com/bijux/bijux-std/commit/7532d9334fb9448f5959f4eaecd21f41423487a9).

- **Changed.** Applied a repository-local workflow filter in `bijux-std` so shared release/docs/reusable templates are stored under `shared/bijux-gh/workflows` and synchronized to consumer `.github/workflows`, while `bijux-std` itself keeps only standards verification workflow activation.
  Text introduction: [fb146e1](https://github.com/bijux/bijux-std/commit/fb146e1fa3ad5fe08c43337a982f523174d1a437) (delivered through [#1](https://github.com/bijux/bijux-std/pull/1)).

- **Changed.** Added a typed workflow inventory registry (`.github/standards/workflow-inventory.json`) and per-repository `workflow_allowlist` entries in the manifest so managed workflow sync is explicit and allowlist-driven.
  Text introduction: [c81d1f8](https://github.com/bijux/bijux-std/commit/c81d1f8097ffd007483cfee7a7bee00ceaa0d0f5) (delivered through [#1](https://github.com/bijux/bijux-std/pull/1)).

- **Changed.** Refreshed `shared/shared-dir-sha256.txt` so the canonical digest entry for `shared/bijux-gh` matches the current shared governance content.
  Text introduction: [7dd55e7](https://github.com/bijux/bijux-std/commit/7dd55e7f108d32db23a8a512fbc110788591a23e).

- **Changed.** Promoted a shared `release-pypi.yml` workflow template under `shared/bijux-gh/workflows` with one configuration surface (`.github/release.env` plus repository variables) and dual-mode publication support (`maturin` and artifact-based trusted publishing).
  Text introduction: [22fc8f1](https://github.com/bijux/bijux-std/commit/22fc8f15a6345e17701bf5481dc909c457b4d5af); [eab9500](https://github.com/bijux/bijux-std/commit/eab9500741de6c2f03b350c1caaf366f290666de).

- **Changed.** Promoted a shared `release-crates.yml` workflow template under `shared/bijux-gh/workflows` with one configuration surface (`.github/release.env` plus repository variables) and per-repository enable/disable controls.
  Text introduction: [22fc8f1](https://github.com/bijux/bijux-std/commit/22fc8f15a6345e17701bf5481dc909c457b4d5af); [8b3eb13](https://github.com/bijux/bijux-std/commit/8b3eb13f04cbd508ac5b60b6b29adf8267b40352).

- **Changed.** Promoted a shared `release-ghcr.yml` workflow template under `shared/bijux-gh/workflows` with one configuration surface (`.github/release.env` plus repository variables), plus matrix-based package publication controls for repositories that publish release bundles to GHCR.
  Text introduction: [02e46dd](https://github.com/bijux/bijux-std/commit/02e46dd6079f4007cc05a44ea268beef5bfbef7a); [22fc8f1](https://github.com/bijux/bijux-std/commit/22fc8f15a6345e17701bf5481dc909c457b4d5af).

- **Changed.** Added allowlist gates across shared release workflows so `.github/release.env` can explicitly constrain which crate/package slugs are publishable for crates.io, PyPI artifact mode, and GHCR.
  Text introduction: [0e55d21](https://github.com/bijux/bijux-std/commit/0e55d2116e9c282f43483c57c06f2c2d4d392cda).

- **Changed.** Added shared artifact release orchestration template: `shared/bijux-gh/workflows/release-artifacts.yml`, so repositories can run build, GHCR, PyPI artifact mode, and GitHub release publication from one standardized workflow contract.
  Text introduction: [18788d5](https://github.com/bijux/bijux-std/commit/18788d58be268a359584dfee6b37f4bdb273ad89) (delivered through [#15](https://github.com/bijux/bijux-std/pull/15)); [3d9262e](https://github.com/bijux/bijux-std/commit/3d9262ef9b68a784bbef2e1e750253876b3e1257).

- **Changed.** Extended `release-github.yml` with explicit enable/disable control (`BIJUX_RELEASE_ENABLED`) so repositories can avoid duplicate direct tag release runs when using orchestrated release lanes.
  Text introduction: [3d9262e](https://github.com/bijux/bijux-std/commit/3d9262ef9b68a784bbef2e1e750253876b3e1257).

- **Changed.** Added canonical issue and pull request template surfaces under `shared/bijux-gh/ISSUE_TEMPLATE` and `shared/bijux-gh/PULL_REQUEST_TEMPLATE` so consuming repositories can share one durable intake and review structure.
  Text introduction: [1a2b39d](https://github.com/bijux/bijux-std/commit/1a2b39d785594929cd59aa3880c4d5819ba3f12d).

- **Changed.** Added shared release helper script `shared/bijux-gh/scripts/wait_for_ci.py` and synchronized consuming repositories to use one canonical CI wait implementation through `.github/scripts/wait_for_ci.py`.
  Text introduction: [d0d881c](https://github.com/bijux/bijux-std/commit/d0d881c8f4dba52e35ac715998ab4bde6a5a1a60).

- **Changed.** Standard policy now treats `.bijux/shared/*` as the only valid consumer managed layout and actively flags legacy root `shared/` in consuming repositories as drift.
  Text introduction: [0f4d7e3](https://github.com/bijux/bijux-std/commit/0f4d7e31cc96b898625a2b11373f21189c173fe6) (delivered through [#3](https://github.com/bijux/bijux-std/pull/3)).

- **Changed.** Standards sync/update flows now remove legacy root `shared/*` managed directories after migration to `.bijux/shared/*`, including cleanup of empty legacy `shared/`.
  Text introduction: [0f4d7e3](https://github.com/bijux/bijux-std/commit/0f4d7e31cc96b898625a2b11373f21189c173fe6) (delivered through [#3](https://github.com/bijux/bijux-std/pull/3)).

- **Changed.** Pinned-action verification now scans workflow directories recursively and is run against full workflow trees (not single-file subsets) to eliminate coverage blind spots.
  Text introduction: [0f4d7e3](https://github.com/bijux/bijux-std/commit/0f4d7e31cc96b898625a2b11373f21189c173fe6) (delivered through [#3](https://github.com/bijux/bijux-std/pull/3)).

- **Changed.** Protected `.github` change policy now includes `automerge-pr.yml` and managed `.bijux/shared/*` paths so governance changes cannot bypass approved control paths.
  Text introduction: [0f4d7e3](https://github.com/bijux/bijux-std/commit/0f4d7e31cc96b898625a2b11373f21189c173fe6) (delivered through [#3](https://github.com/bijux/bijux-std/pull/3)).

- **Changed.** `automerge-pr.yml` now requires trusted approval from a user listed in `.github/CODEOWNERS`, and ignores stale approvals superseded by newer review states.
  Text introduction: [0f4d7e3](https://github.com/bijux/bijux-std/commit/0f4d7e31cc96b898625a2b11373f21189c173fe6) (delivered through [#3](https://github.com/bijux/bijux-std/pull/3)).

- **Changed.** Standards sync now includes `automerge-pr.yml` in the managed baseline file set for consumer repositories, so automerge policy updates propagate through normal sync flows.
  Text introduction: [ff80008](https://github.com/bijux/bijux-std/commit/ff800084887f841a728e92de83eb39f8a26c6514) (delivered through [#4](https://github.com/bijux/bijux-std/pull/4)).

- **Changed.** Standards scripts `build_repo_manifest.py` and `sync_github_standards.py` now resolve `bijux-std` root more robustly and support `BIJUX_STD_REPO` override for non-sibling workspace layouts.
  Text introduction: [ff80008](https://github.com/bijux/bijux-std/commit/ff800084887f841a728e92de83eb39f8a26c6514) (delivered through [#4](https://github.com/bijux/bijux-std/pull/4)).

- **Changed.** Manifest generation now reports actionable YAML parser errors when Ruby is unavailable or parsing fails.
  Text introduction: [ff80008](https://github.com/bijux/bijux-std/commit/ff800084887f841a728e92de83eb39f8a26c6514) (delivered through [#4](https://github.com/bijux/bijux-std/pull/4)).

- **Changed.** Sync cleanup now handles stale runtime workflow directories safely when removing non-allowlisted managed workflows.
  Text introduction: [ff80008](https://github.com/bijux/bijux-std/commit/ff800084887f841a728e92de83eb39f8a26c6514) (delivered through [#4](https://github.com/bijux/bijux-std/pull/4)).

## Recorded 0.1.1 notes

Original changelog heading: `0.1.1 - 2026-04-18`.

- **Added.** New shared GitHub governance tooling under `shared/bijux-gh`, including generated Dependabot configuration rendering from discovered Python manifests.
  Text introduction: [0b56e16](https://github.com/bijux/bijux-std/commit/0b56e16789453e0f9ebb4409bcf8db740765bfb8); [7d20e63](https://github.com/bijux/bijux-std/commit/7d20e6394c5d07e12415a64214151c3b737113cc).

- **Added.** New shared make surfaces for governance sync and drift checks that consume the canonical shared tooling tree.
  Text introduction: [7d20e63](https://github.com/bijux/bijux-std/commit/7d20e6394c5d07e12415a64214151c3b737113cc).

- **Added.** New standards tests and live navigation release-gate coverage for the shared docs shell behavior across phone, tablet, and desktop profiles.
  Text introduction: [7d20e63](https://github.com/bijux/bijux-std/commit/7d20e6394c5d07e12415a64214151c3b737113cc).

- **Changed.** Shared standards directory contracts and manifest digests were refreshed repeatedly as canonical docs shell, checks, and governance assets evolved.
  Text introduction: [7d20e63](https://github.com/bijux/bijux-std/commit/7d20e6394c5d07e12415a64214151c3b737113cc).

- **Changed.** Shared internal tooling layout now uses durable naming and directory ownership, including migration away from transitional internal naming.
  Text introduction: [7d20e63](https://github.com/bijux/bijux-std/commit/7d20e6394c5d07e12415a64214151c3b737113cc).

- **Changed.** Bookkeeping update: synchronized consuming repositories now document explicit contributor and automation identity boundaries for `bijux`, `dependabot[bot]`, and `github-actions[bot]` under their governance docs.
  Text introduction: [6372d5c](https://github.com/bijux/bijux-std/commit/6372d5c539a63099e23e93eef89de5a4b49a2b46).

- **Changed.** Standards CI now uses a single matrix workflow at `.github/workflows/bijux-std.yml` that runs both standard checks and checks reporting.
  Text introduction: [74d41d1](https://github.com/bijux/bijux-std/commit/74d41d186aef72679e67d50f7ef6c390f1f43062).

- **Changed.** Shared branch-protection status-check policy now tracks matrix contexts `checks (standard)` and `checks (report)` for the unified workflow.
  Text introduction: [74d41d1](https://github.com/bijux/bijux-std/commit/74d41d186aef72679e67d50f7ef6c390f1f43062).

- **Fixed.** Shared docs shell now restores canonical Mermaid initializer sync behavior.
  Text introduction: [7d20e63](https://github.com/bijux/bijux-std/commit/7d20e6394c5d07e12415a64214151c3b737113cc).

- **Fixed.** Shared docs navigation behavior was stabilized for scoped sidebars and mobile drawer interactions, including hub/project continuity across viewports.
  Text introduction: [7d20e63](https://github.com/bijux/bijux-std/commit/7d20e6394c5d07e12415a64214151c3b737113cc).

- **Fixed.** Shared manifest comparison logic now validates required directory entries deterministically against canonical standards inputs.
  Text introduction: [7d20e63](https://github.com/bijux/bijux-std/commit/7d20e6394c5d07e12415a64214151c3b737113cc).

- **Fixed.** Root README now documents the canonical shared inventory and check inputs, including workflow-template and manifest contract references.
  Text introduction: [9bf9639](https://github.com/bijux/bijux-std/commit/9bf96391d534ae0c35ea182c63cefba936296835).

## Recorded initial baseline notes

Original changelog heading: `0.1.0 - 2026-04-16`.

- **Added.** Canonical standards repository structure under `shared/`, including: `shared/bijux-docs`, `shared/bijux-makes-py`, and `shared/bijux-checks`.
  Text introduction: [b4446a6](https://github.com/bijux/bijux-std/commit/b4446a650e502f078f99fe8bd7d396045bb44244).

- **Added.** Shared SHA manifest contract at `shared/shared-dir-sha256.txt` for machine-verifiable standards drift detection.
  Text introduction: [b4446a6](https://github.com/bijux/bijux-std/commit/b4446a650e502f078f99fe8bd7d396045bb44244).

- **Added.** Shared standard policy and check/update scripts in `shared/bijux-checks`, including branch-based and tag-based update support.
  Text introduction: [b4446a6](https://github.com/bijux/bijux-std/commit/b4446a650e502f078f99fe8bd7d396045bb44244).

- **Added.** Repository-level make entrypoints: `bijux-std-checks`, `bijux-std-update`, and compatibility alias `bijux-std`.
  Text introduction: [b4446a6](https://github.com/bijux/bijux-std/commit/b4446a650e502f078f99fe8bd7d396045bb44244).

- **Added.** Standards CI workflow at `.github/workflows/bijux-std.yml`.
  Text introduction: [74d41d1](https://github.com/bijux/bijux-std/commit/74d41d186aef72679e67d50f7ef6c390f1f43062).

- **Added.** Root repository `README.md` documenting ownership boundaries, consumption model, verification model, and change rules.
  Text introduction: [b4446a6](https://github.com/bijux/bijux-std/commit/b4446a650e502f078f99fe8bd7d396045bb44244).

- **Changed.** Canonical standard remote address now uses the repository URL `https://github.com/bijux/bijux-std`, while raw-content fetch paths are derived internally by the checker.
  Text introduction: [b4446a6](https://github.com/bijux/bijux-std/commit/b4446a650e502f078f99fe8bd7d396045bb44244).

## Tag identities

The archived initial note date is `2026-04-16`; the actual `v0.1.0` tag was
created on `2026-04-18`. These dates describe different recorded events and
are kept distinct. Tags `v0.1.2` and `v0.1.3` also exist even though the earlier
changelog had no headings for them. No release date is inferred from a tag.

| Tag | Tag object | Target commit | Recorded tag creation |
| --- | --- | --- | --- |
| `v0.1.0` | `7b0069b42b5e63753625ca57ec6ad0d8a968f687` | [7d20e63](https://github.com/bijux/bijux-std/commit/7d20e6394c5d07e12415a64214151c3b737113cc) | `2026-04-18T02:25:11+02:00` |
| `v0.1.1` | `48b2fd4f0d40c44036d72d22c4b4bd71b87c3c8b` | [9bf9639](https://github.com/bijux/bijux-std/commit/9bf96391d534ae0c35ea182c63cefba936296835) | `2026-04-18T16:31:57+02:00` |
| `v0.1.2` | `4cbddef82ade37f756b23400899c5085fbed8bb1` | [7532d93](https://github.com/bijux/bijux-std/commit/7532d9334fb9448f5959f4eaecd21f41423487a9) | `2026-04-18T22:49:11+02:00` |
| `v0.1.3` | `8c5d5bfafedbeffda52d10464330475f640266d7` | [c0a1854](https://github.com/bijux/bijux-std/commit/c0a18541d1b15ca60abf212a155eee051f108406) | `2026-04-20T02:19:15+02:00` |

`v0.1.3` points to an original API-era commit for PR #33 that is outside the
rewritten main ancestry. A matching historical source tree is distinct from
both its original API merge identity and the current main tip.
