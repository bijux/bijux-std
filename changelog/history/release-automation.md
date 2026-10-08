# Release automation preceding artifact alignment

This archive follows the current first-parent history of accepted main `fd381b07a7c850915b86181ac0b1a960272decaf`. It lists preceding main-history commits beneath their first subsequent verified main PR. This association records graph order; it does not prove direct pushes, the original publisher or first publication by that PR. Historical rewritten Git identities and author/committer dates differ from original GitHub merge identities and verified PR merge dates. Later PRs may supersede these historical source states.

Each commit link identifies the full current Git SHA and its source patch. The recorded subject is original; changed paths and line counts come from the actual commit diff. Git timestamps below are current object metadata, not verified direct-push dates.

## Before PR 11

Subsequent verified PR: [#11](https://github.com/bijux/bijux-std/pull/11) — fix(release): align artifact publishing and wrapper manifest generation. Verified GitHub merge: 2026-04-19T11:57:34Z.

1. [9e6898c8](https://github.com/bijux/bijux-std/commit/9e6898c8e9b6a603f6b34466d29d691525fce5e2) — chore(standards): refresh managed manifest and checksum

   Change .github/bijux-std-shared.sha256, .github/standards/repo-config.manifest.json.

   Changed paths: `.github/bijux-std-shared.sha256` (+7 / -7); `.github/standards/repo-config.manifest.json` (+3 / -3).

   Git authored: 2026-04-19T03:44:20+02:00; committed: 2026-04-19T03:44:20+02:00.

2. [b397238d](https://github.com/bijux/bijux-std/commit/b397238d4d343d511068d1f7ba6990454ea9c983) — fix(release): honor tag push env flags in shared workflows

   Change shared/bijux-gh/workflows/release-artifacts.yml, shared/bijux-gh/workflows/release-crates.yml, shared/bijux-gh/workflows/release-ghcr.yml, shared/bijux-gh/workflows/release-github.yml and 2 additional owned paths.

   Changed paths: `shared/bijux-gh/workflows/release-artifacts.yml` (+25 / -5); `shared/bijux-gh/workflows/release-crates.yml` (+8 / -1); `shared/bijux-gh/workflows/release-ghcr.yml` (+12 / -2); `shared/bijux-gh/workflows/release-github.yml` (+28 / -6); `shared/bijux-gh/workflows/release-pypi.yml` (+12 / -2); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-19T03:44:20+02:00; committed: 2026-04-19T03:44:20+02:00.

3. [b3d692bc](https://github.com/bijux/bijux-std/commit/b3d692bc6d9c0d776391fc7f4a51fc331e2ad891) — fix(standards): preserve canon release workflow contracts

   Change .github/bijux-std-shared.sha256, .github/scripts/render_repo_configs.py, .github/standards/repo-config.manifest.json.

   Changed paths: `.github/bijux-std-shared.sha256` (+2 / -2); `.github/scripts/render_repo_configs.py` (+1 / -1); `.github/standards/repo-config.manifest.json` (+8 / -1).

   Git authored: 2026-04-19T03:47:05+02:00; committed: 2026-04-19T03:47:05+02:00.

4. [e6501aa3](https://github.com/bijux/bijux-std/commit/e6501aa3e7e3007d9db2af30810680ce5e286e89) — fix(standards): restore canon release env and dependabot policy

   Change .github/bijux-std-shared.sha256, .github/standards/repo-config.manifest.json.

   Changed paths: `.github/bijux-std-shared.sha256` (+1 / -1); `.github/standards/repo-config.manifest.json` (+166 / -13).

   Git authored: 2026-04-19T03:48:19+02:00; committed: 2026-04-19T03:48:19+02:00.

5. [3daffaa9](https://github.com/bijux/bijux-std/commit/3daffaa9303f2bd5d440c5905dbe7057a9054dd6) — fix(release): align reusable caller permissions for actions scope

   Change shared/bijux-gh/workflows/release-artifacts.yml, shared/shared-dir-sha256.txt.

   Changed paths: `shared/bijux-gh/workflows/release-artifacts.yml` (+2 / -0); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-19T03:50:14+02:00; committed: 2026-04-19T03:50:14+02:00.

6. [456cb339](https://github.com/bijux/bijux-std/commit/456cb33955c730e4e829c65dd089e2dbefb6a2ef) — fix(release): grant packages scope to github release caller

   Change shared/bijux-gh/workflows/release-artifacts.yml, shared/shared-dir-sha256.txt.

   Changed paths: `shared/bijux-gh/workflows/release-artifacts.yml` (+1 / -0); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-19T03:51:39+02:00; committed: 2026-04-19T03:51:39+02:00.

7. [5466c91c](https://github.com/bijux/bijux-std/commit/5466c91c85c4e787ab51b24dde235daa4c3ac925) — fix(release): checkout repo before resolving release env

   Change shared/bijux-gh/workflows/release-artifacts.yml, shared/bijux-gh/workflows/release-crates.yml, shared/bijux-gh/workflows/release-ghcr.yml, shared/bijux-gh/workflows/release-pypi.yml and 1 additional owned paths.

   Changed paths: `shared/bijux-gh/workflows/release-artifacts.yml` (+5 / -0); `shared/bijux-gh/workflows/release-crates.yml` (+5 / -0); `shared/bijux-gh/workflows/release-ghcr.yml` (+5 / -0); `shared/bijux-gh/workflows/release-pypi.yml` (+5 / -0); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-19T03:53:18+02:00; committed: 2026-04-19T03:53:18+02:00.

8. [7b78a79a](https://github.com/bijux/bijux-std/commit/7b78a79a7a23f2e84504079e9cc814052c4a1584) — fix(release): preserve matrix json inputs in shared resolvers

   Change shared/bijux-gh/workflows/release-ghcr.yml, shared/bijux-gh/workflows/release-pypi.yml.

   Changed paths: `shared/bijux-gh/workflows/release-ghcr.yml` (+15 / -7); `shared/bijux-gh/workflows/release-pypi.yml` (+13 / -6).

   Git authored: 2026-04-19T13:25:52+02:00; committed: 2026-04-19T13:25:52+02:00.

9. [df04d64a](https://github.com/bijux/bijux-std/commit/df04d64ad4355efa1f332a59ed6d521d51118456) — chore(standards): refresh shared directory checksums

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-19T13:26:50+02:00; committed: 2026-04-19T13:26:50+02:00.

10. [64b14729](https://github.com/bijux/bijux-std/commit/64b14729533f27d0e1f8157952eeb0b0e81f5f70) — fix(release): resolve boolean inputs without event-name coupling

   Change shared/bijux-gh/workflows/release-ghcr.yml, shared/bijux-gh/workflows/release-pypi.yml.

   Changed paths: `shared/bijux-gh/workflows/release-ghcr.yml` (+22 / -8); `shared/bijux-gh/workflows/release-pypi.yml` (+22 / -8).

   Git authored: 2026-04-19T13:33:32+02:00; committed: 2026-04-19T13:33:32+02:00.

11. [bcbe42ef](https://github.com/bijux/bijux-std/commit/bcbe42ef7fe32684a834cb9b3e02e4863a1b887c) — chore(standards): refresh shared directory checksums

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-19T13:33:33+02:00; committed: 2026-04-19T13:33:33+02:00.

12. [4069aae8](https://github.com/bijux/bijux-std/commit/4069aae8e07db715a9730651026e9215853e4899) — fix(release): pin download-artifact to valid v4.3.0 sha

   Change shared/bijux-gh/workflows/release-ghcr.yml, shared/bijux-gh/workflows/release-pypi.yml.

   Changed paths: `shared/bijux-gh/workflows/release-ghcr.yml` (+1 / -1); `shared/bijux-gh/workflows/release-pypi.yml` (+1 / -1).

   Git authored: 2026-04-19T13:40:09+02:00; committed: 2026-04-19T13:40:09+02:00.

13. [78c980d4](https://github.com/bijux/bijux-std/commit/78c980d4245d3f9c45456cdb5cfde74090405183) — chore(standards): refresh shared directory checksums

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-19T13:40:11+02:00; committed: 2026-04-19T13:40:11+02:00.
