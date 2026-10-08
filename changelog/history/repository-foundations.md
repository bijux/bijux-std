# Repository foundations before the first PR

This archive follows the current first-parent history of accepted main `fd381b07a7c850915b86181ac0b1a960272decaf`. It lists preceding main-history commits beneath their first subsequent verified main PR. This association records graph order; it does not prove direct pushes, the original publisher or first publication by that PR. Historical rewritten Git identities and author/committer dates differ from original GitHub merge identities and verified PR merge dates. Later PRs may supersede these historical source states.

Each commit link identifies the full current Git SHA and its source patch. The recorded subject is original; changed paths and line counts come from the actual commit diff. Git timestamps below are current object metadata, not verified direct-push dates.

## Before PR 1

Subsequent verified PR: [#1](https://github.com/bijux/bijux-std/pull/1) — refactor(github): move shared workflow templates out of active workflows. Verified GitHub merge: 2026-04-18T21:45:42Z.

1. [c2c5df7d](https://github.com/bijux/bijux-std/commit/c2c5df7df73aeb76340893a609cef7c2d90e8070) — chore(std): add shared ssot assets and directory sha manifest

   Change shared/bijux-docs/CONTRACT.md, shared/bijux-docs/README.md, shared/bijux-docs/partials/bijux-nav.html, shared/bijux-docs/partials/footer-profile-links.html and 49 additional owned paths. Added or revised definitions: runShellNavigationSync, ensureBound, syncDetailStripPresence, syncDetailStripVisibility, syncDetailStripActiveState, activeDetailPath, syncCourseStripVisibility, syncCourseStripActiveState. Added or revised selectors: .md-main, .bijux-hub-strip, .bijux-hub-strip::-webkit-scrollbar, .bijux-hub-strip::after, .bijux-hub-strip::before.

   Changed paths: `shared/bijux-docs/CONTRACT.md` (+23 / -0); `shared/bijux-docs/README.md` (+17 / -0); `shared/bijux-docs/partials/bijux-nav.html` (+50 / -0); `shared/bijux-docs/partials/footer-profile-links.html` (+20 / -0); `shared/bijux-docs/partials/footer.html` (+45 / -0); `shared/bijux-docs/partials/header.html` (+224 / -0); `shared/bijux-docs/partials/nav-item.html` (+150 / -0); `shared/bijux-docs/partials/nav.html` (+110 / -0); `shared/bijux-docs/scripts/README.md` (+9 / -0); `shared/bijux-docs/scripts/bootstrap.js` (+25 / -0); `shared/bijux-docs/scripts/detail-tabs.js` (+290 / -0); `shared/bijux-docs/scripts/nav-reveal.js` (+106 / -0); `shared/bijux-docs/scripts/nav-state.js` (+115 / -0); `shared/bijux-docs/scripts/nav-sync.js` (+7 / -0); `shared/bijux-docs/scripts/theme-persistence.js` (+391 / -0); `shared/bijux-docs/scripts/viewport-profile.js` (+57 / -0); `shared/bijux-docs/styles/00-tokens.css` (+21 / -0); `shared/bijux-docs/styles/01-theme.css` (+218 / -0); `shared/bijux-docs/styles/02-layout.css` (+27 / -0); `shared/bijux-docs/styles/03-header.css` (+145 / -0); `shared/bijux-docs/styles/04-nav.css` (+475 / -0); `shared/bijux-docs/styles/05-content.css` (+144 / -0); `shared/bijux-docs/styles/06-components.css` (+488 / -0); `shared/bijux-docs/styles/07-utilities.css` (+17 / -0); `shared/bijux-docs/styles/08-responsive.css` (+343 / -0); `shared/bijux-docs/styles/README.md` (+13 / -0); `shared/bijux-docs/styles/extra.css` (+10 / -0); `shared/bijux-makes-py/api-contract.mk` (+316 / -0); `shared/bijux-makes-py/api-freeze.mk` (+71 / -0); `shared/bijux-makes-py/api-live-contract.mk` (+81 / -0); `shared/bijux-makes-py/api.mk` (+48 / -0); `shared/bijux-makes-py/bijux.mk` (+51 / -0); `shared/bijux-makes-py/ci/build.mk` (+139 / -0); `shared/bijux-makes-py/ci/docs.mk` (+218 / -0); `shared/bijux-makes-py/ci/help.mk` (+54 / -0); `shared/bijux-makes-py/ci/lint.mk` (+144 / -0); `shared/bijux-makes-py/ci/quality.mk` (+125 / -0); `shared/bijux-makes-py/ci/sbom.mk` (+118 / -0); `shared/bijux-makes-py/ci/security.mk` (+92 / -0); `shared/bijux-makes-py/ci/test.mk` (+282 / -0); `shared/bijux-makes-py/ci/util.mk` (+14 / -0); `shared/bijux-makes-py/package-catalog.mk` (+102 / -0); `shared/bijux-makes-py/package.mk` (+329 / -0); `shared/bijux-makes-py/repository/config-layout.mk` (+14 / -0); `shared/bijux-makes-py/repository/env.mk` (+62 / -0); `shared/bijux-makes-py/repository/make-layout.mk` (+23 / -0); `shared/bijux-makes-py/repository/publish.mk` (+107 / -0); `shared/bijux-makes-py/repository/root.mk` (+58 / -0); `shared/bijux-makes-py/root/docs.mk` (+34 / -0); `shared/bijux-makes-py/root/env.mk` (+31 / -0); `shared/bijux-makes-py/root/lifecycle.mk` (+35 / -0); `shared/bijux-makes-py/root/package-dispatch.mk` (+81 / -0); `shared/shared-dir-sha256.txt` (+4 / -0).

   Git authored: 2026-04-16T21:52:48+02:00; committed: 2026-04-16T21:52:48+02:00.

2. [dbb6665a](https://github.com/bijux/bijux-std/commit/dbb6665a913e04306be5a9d2595edbda282059ff) — feat(std): add bijux-std sha verification script

   Change shared/bijux-makes-py/ci/check-bijux-std.sh, shared/shared-dir-sha256.txt.

   Changed paths: `shared/bijux-makes-py/ci/check-bijux-std.sh` (+119 / -0); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-16T22:04:52+02:00; committed: 2026-04-16T22:04:52+02:00.

3. [3fff4b90](https://github.com/bijux/bijux-std/commit/3fff4b909fe4e8d36216801df013406c5a505540) — refactor(standards): move bijux std verifier to shared bijux-checks

   Change shared/bijux-checks/check-bijux-std.sh, shared/bijux-makes-py/ci/check-bijux-std.sh, shared/shared-dir-sha256.txt.

   Changed paths: `shared/bijux-checks/check-bijux-std.sh` (+120 / -0); `shared/bijux-makes-py/ci/check-bijux-std.sh` (+0 / -119); `shared/shared-dir-sha256.txt` (+2 / -3).

   Git authored: 2026-04-16T22:10:31+02:00; committed: 2026-04-16T22:10:31+02:00.

4. [cf6a4f66](https://github.com/bijux/bijux-std/commit/cf6a4f66a99d5cd6e5b7e2de006e86b5f8c018ed) — feat(standards): add policy driven bijux standard checks and update flow

   Change .github/workflows/bijux-std-checks.yml, Makefile, shared/bijux-checks/bijux-std-checks.yml, shared/bijux-checks/check-bijux-std.sh and 3 additional owned paths.

   Changed paths: `.github/workflows/bijux-std-checks.yml` (+17 / -0); `Makefile` (+26 / -0); `shared/bijux-checks/bijux-std-checks.yml` (+11 / -0); `shared/bijux-checks/check-bijux-std.sh` (+35 / -15); `shared/bijux-checks/update-bijux-std.sh` (+91 / -0); `shared/bijux-checks/workflows/bijux-std-checks.yml` (+17 / -0); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-16T22:26:51+02:00; committed: 2026-04-16T22:26:51+02:00.

5. [fc1b6f77](https://github.com/bijux/bijux-std/commit/fc1b6f77588de82bc580c0635942c92ffa1ad153) — docs(standards): describe bijux standard source of truth

   Change README.md.

   Changed paths: `README.md` (+106 / -0).

   Git authored: 2026-04-16T22:47:11+02:00; committed: 2026-04-16T22:47:11+02:00.

6. [0875422f](https://github.com/bijux/bijux-std/commit/0875422fbabdd6b98b02ddb007a61212eb711f54) — fix(standards): use github repo url as canonical bijux std remote

   Change Makefile, shared/bijux-checks/bijux-std-checks.yml, shared/bijux-checks/check-bijux-std.sh, shared/shared-dir-sha256.txt.

   Changed paths: `Makefile` (+1 / -1); `shared/bijux-checks/bijux-std-checks.yml` (+1 / -1); `shared/bijux-checks/check-bijux-std.sh` (+29 / -2); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-16T22:51:04+02:00; committed: 2026-04-16T22:51:04+02:00.

7. [b4446a65](https://github.com/bijux/bijux-std/commit/b4446a650e502f078f99fe8bd7d396045bb44244) — docs(changelog): add initial repository release history

   Change CHANGELOG.md.

   Changed paths: `CHANGELOG.md` (+44 / -0).

   Git authored: 2026-04-16T22:53:27+02:00; committed: 2026-04-16T22:53:27+02:00.

8. [6129ef2e](https://github.com/bijux/bijux-std/commit/6129ef2e84946aa12ed65f3139757d7efd606ddd) — fix(nav): preserve flattened detail rows on bijux hub pages

   Change shared/bijux-docs/partials/header.html, shared/shared-dir-sha256.txt.

   Changed paths: `shared/bijux-docs/partials/header.html` (+2 / -1); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-16T23:03:31+02:00; committed: 2026-04-16T23:03:31+02:00.

9. [0545d7f5](https://github.com/bijux/bijux-std/commit/0545d7f5e3e90fa3a984daddfe974b908aff5b36) — fix(docs): restore search control and stabilize site tab row

   Change shared/bijux-docs/partials/header.html, shared/bijux-docs/styles/04-nav.css, shared/shared-dir-sha256.txt.

   Changed paths: `shared/bijux-docs/partials/header.html` (+1 / -1); `shared/bijux-docs/styles/04-nav.css` (+0 / -4); `shared/shared-dir-sha256.txt` (+3 / -3).

   Git authored: 2026-04-17T00:55:17+02:00; committed: 2026-04-17T00:55:17+02:00.

10. [217e833b](https://github.com/bijux/bijux-std/commit/217e833b6d46856c77dd36ff9bcd1c21dbca21f4) — fix(docs): always render header search control

   Change shared/bijux-docs/partials/header.html, shared/shared-dir-sha256.txt.

   Changed paths: `shared/bijux-docs/partials/header.html` (+5 / -7); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T00:57:38+02:00; committed: 2026-04-17T00:57:38+02:00.

11. [a1d0a576](https://github.com/bijux/bijux-std/commit/a1d0a576334d83932eae8d3ac6e92b3d4747f0d9) — fix(ci): pin bijux-std checks to pushed ref

   Change .github/workflows/bijux-std-checks.yml, shared/bijux-checks/workflows/bijux-std-checks.yml, shared/shared-dir-sha256.txt.

   Changed paths: `.github/workflows/bijux-std-checks.yml` (+2 / -0); `shared/bijux-checks/workflows/bijux-std-checks.yml` (+2 / -0); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T01:12:44+02:00; committed: 2026-04-17T01:12:44+02:00.

12. [69920ba1](https://github.com/bijux/bijux-std/commit/69920ba1cbe1a507bf9246eaa8a64834d31a5b66) — fix(std-checks): resolve manifest from git source

   Change .github/workflows/bijux-std-checks.yml, shared/bijux-checks/check-bijux-std.sh, shared/bijux-checks/workflows/bijux-std-checks.yml, shared/shared-dir-sha256.txt.

   Changed paths: `.github/workflows/bijux-std-checks.yml` (+0 / -2); `shared/bijux-checks/check-bijux-std.sh` (+14 / -51); `shared/bijux-checks/workflows/bijux-std-checks.yml` (+0 / -2); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T01:15:33+02:00; committed: 2026-04-17T01:15:33+02:00.

13. [d66c2a2b](https://github.com/bijux/bijux-std/commit/d66c2a2bb88cdc76ed15f3ccc1825661de823587) — fix(nav): enforce single active detail selection

   Change shared/bijux-docs/partials/header.html, shared/bijux-docs/scripts/detail-tabs.js, shared/shared-dir-sha256.txt.

   Changed paths: `shared/bijux-docs/partials/header.html` (+5 / -5); `shared/bijux-docs/scripts/detail-tabs.js` (+1 / -8); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T01:31:09+02:00; committed: 2026-04-17T01:31:09+02:00.

14. [9e86938a](https://github.com/bijux/bijux-std/commit/9e86938acd777423fec4a56f4e9974677293c7f7) — fix(nav): restore course detail row visibility on nested pages

   Change shared/bijux-docs/partials/header.html, shared/bijux-docs/scripts/detail-tabs.js, shared/shared-dir-sha256.txt.

   Changed paths: `shared/bijux-docs/partials/header.html` (+3 / -3); `shared/bijux-docs/scripts/detail-tabs.js` (+8 / -1); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T01:46:32+02:00; committed: 2026-04-17T01:46:32+02:00.

15. [091fdc5a](https://github.com/bijux/bijux-std/commit/091fdc5a23b8f80201142073f837daede96e7afe) — fix(nav): promote directory sections and suppress synthetic home rows

   Change shared/bijux-docs/partials/header.html, shared/shared-dir-sha256.txt.

   Changed paths: `shared/bijux-docs/partials/header.html` (+20 / -4); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T02:28:19+02:00; committed: 2026-04-17T02:28:19+02:00.

16. [f70eb191](https://github.com/bijux/bijux-std/commit/f70eb191ebdead9b48cb59ff349733de9cab95b1) — fix(docs-nav): include Home tab in non-flattened detail rows

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+55 / -2).

   Git authored: 2026-04-17T02:42:40+02:00; committed: 2026-04-17T02:42:40+02:00.

17. [dbe2b6dc](https://github.com/bijux/bijux-std/commit/dbe2b6dc7fbe9b7d04037eb208c930aa9d04e21f) — chore(standard-manifest): refresh shared docs tree checksum

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T02:42:42+02:00; committed: 2026-04-17T02:42:42+02:00.

18. [e7c37a9e](https://github.com/bijux/bijux-std/commit/e7c37a9e10d0ff62a16406cdb49cf844de823147) — fix(docs-nav): initialize course detail items before conditional usage

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+1 / -1).

   Git authored: 2026-04-17T02:45:02+02:00; committed: 2026-04-17T02:45:02+02:00.

19. [7c92140f](https://github.com/bijux/bijux-std/commit/7c92140f77cc350d943e93f8fa88cd076618ecf2) — chore(standard-manifest): refresh shared docs tree checksum

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T02:45:04+02:00; committed: 2026-04-17T02:45:04+02:00.

20. [6370de37](https://github.com/bijux/bijux-std/commit/6370de3738effaeb636497a85c5e6ebaa24526b9) — fix(docs-nav): include leaf pages in flattened detail rows

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+2 / -6).

   Git authored: 2026-04-17T03:08:27+02:00; committed: 2026-04-17T03:08:27+02:00.

21. [05c5c7d4](https://github.com/bijux/bijux-std/commit/05c5c7d4de5d4c82292957638ff5160ec3241c25) — chore(standard-manifest): refresh shared docs tree checksum

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T03:08:30+02:00; committed: 2026-04-17T03:08:30+02:00.

22. [2c3212e5](https://github.com/bijux/bijux-std/commit/2c3212e5e00a4c69d7130de016ec759538b4b9d7) — fix(docs-nav): normalize current path separately from nav targets

   Change shared/bijux-docs/scripts/detail-tabs.js, shared/bijux-docs/scripts/nav-state.js. Added or revised definitions: normalizeCurrentPath.

   Changed paths: `shared/bijux-docs/scripts/detail-tabs.js` (+4 / -4); `shared/bijux-docs/scripts/nav-state.js` (+8 / -2).

   Git authored: 2026-04-17T03:16:29+02:00; committed: 2026-04-17T03:16:29+02:00.

23. [a3d9a38e](https://github.com/bijux/bijux-std/commit/a3d9a38eafccd44039e49893f9165012b94fab59) — chore(standard-manifest): refresh shared docs tree checksum

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T03:16:32+02:00; committed: 2026-04-17T03:16:32+02:00.

24. [252878e3](https://github.com/bijux/bijux-std/commit/252878e367fceba509a43db09cba219ca2da4445) — refactor(docs-nav): separate phone and desktop sync controllers

   Change shared/bijux-docs/scripts/README.md, shared/bijux-docs/scripts/bootstrap.js, shared/bijux-docs/scripts/detail-tabs.js, shared/bijux-docs/scripts/nav-reveal.js. Added or revised definitions: runDesktopNavigationSync, runPhoneNavigationSync.

   Changed paths: `shared/bijux-docs/scripts/README.md` (+3 / -3); `shared/bijux-docs/scripts/bootstrap.js` (+16 / -3); `shared/bijux-docs/scripts/detail-tabs.js` (+20 / -0); `shared/bijux-docs/scripts/nav-reveal.js` (+10 / -0).

   Git authored: 2026-04-17T03:34:59+02:00; committed: 2026-04-17T03:34:59+02:00.

25. [7681ea75](https://github.com/bijux/bijux-std/commit/7681ea7566dc2b94fef853891c9864f08355e0c7) — chore(standard-manifest): refresh shared docs tree checksum

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T03:35:02+02:00; committed: 2026-04-17T03:35:02+02:00.

26. [d28bff18](https://github.com/bijux/bijux-std/commit/d28bff18c2ee5b11a4b731db82f904f84c13454d) — fix(api-test): guard schemathesis openapi-3.1 flag by CLI support

   Change shared/bijux-makes-py/api-live-contract.mk.

   Changed paths: `shared/bijux-makes-py/api-live-contract.mk` (+8 / -1).

   Git authored: 2026-04-17T03:48:02+02:00; committed: 2026-04-17T03:48:02+02:00.

27. [e80e0572](https://github.com/bijux/bijux-std/commit/e80e05722d594ed325738b6db7de17705f40ea02) — chore(standard-manifest): refresh shared directory checksums

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T03:48:02+02:00; committed: 2026-04-17T03:48:02+02:00.

28. [bf2f0aca](https://github.com/bijux/bijux-std/commit/bf2f0aca652154b549f04bd7508dbfede1ab258c) — docs(readme): clarify repository identity and scope

   Change README.md.

   Changed paths: `README.md` (+34 / -15).

   Git authored: 2026-04-17T13:21:04+02:00; committed: 2026-04-17T13:21:04+02:00.

29. [4c6ddc47](https://github.com/bijux/bijux-std/commit/4c6ddc4732f222193647ae620d971fa94c33c8c6) — docs(readme): document layout and verification workflow

   Change README.md.

   Changed paths: `README.md` (+53 / -26).

   Git authored: 2026-04-17T13:21:34+02:00; committed: 2026-04-17T13:21:34+02:00.

30. [4c02adfd](https://github.com/bijux/bijux-std/commit/4c02adfdea52ca6206394269874f69f98f909ec2) — docs(readme): finalize adoption and change policy guidance

   Change README.md.

   Changed paths: `README.md` (+38 / -13).

   Git authored: 2026-04-17T13:21:53+02:00; committed: 2026-04-17T13:21:53+02:00.

31. [b6dd6c1c](https://github.com/bijux/bijux-std/commit/b6dd6c1cfa5617d975466197c4d893cfb6f0653c) — docs(license): add MIT license file

   Change LICENSE.

   Changed paths: `LICENSE` (+21 / -0).

   Git authored: 2026-04-17T13:30:25+02:00; committed: 2026-04-17T13:30:25+02:00.

32. [b20cccc9](https://github.com/bijux/bijux-std/commit/b20cccc9e9c2b158d8545ae538ce9b28cd69d2a1) — fix(viewport): define explicit phone and normal breakpoints

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+3 / -1).

   Git authored: 2026-04-17T14:58:40+02:00; committed: 2026-04-17T14:58:40+02:00.

33. [5bc9204f](https://github.com/bijux/bijux-std/commit/5bc9204f5caecd3fc8308644ca9735d46eacd8f8) — fix(viewport): add desktop profile fallback to resolver

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+5 / -1).

   Git authored: 2026-04-17T14:58:49+02:00; committed: 2026-04-17T14:58:49+02:00.

34. [03b474a0](https://github.com/bijux/bijux-std/commit/03b474a06ce58636ad37107ce5f9b8b1745de7e7) — refactor(viewport): centralize media query checks with safe helper

   Change shared/bijux-docs/scripts/viewport-profile.js. Added or revised definitions: mediaMatches.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+7 / -3).

   Git authored: 2026-04-17T14:59:01+02:00; committed: 2026-04-17T14:59:01+02:00.

35. [27040725](https://github.com/bijux/bijux-std/commit/270407251eac547d7566c436bca8693d5c0b253c) — docs(viewport): document dual-target sync and resize frame throttling

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+2 / -0).

   Git authored: 2026-04-17T14:59:13+02:00; committed: 2026-04-17T14:59:13+02:00.

36. [71442f6b](https://github.com/bijux/bijux-std/commit/71442f6b10fb58163abbce5a3a361acabc407462) — feat(viewport): expose breakpoint diagnostics for devtools verification

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+13 / -0).

   Git authored: 2026-04-17T14:59:30+02:00; committed: 2026-04-17T14:59:30+02:00.

37. [87572d29](https://github.com/bijux/bijux-std/commit/87572d29b437da18d37072a06a9046a4fd61c2a0) — refactor(header): codify desktop-normal scope for top navigation rows

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+4 / -2).

   Git authored: 2026-04-17T15:01:00+02:00; committed: 2026-04-17T15:01:00+02:00.

38. [c748b541](https://github.com/bijux/bijux-std/commit/c748b541d7829a3c2ec90992be9351f7871bf65c) — feat(header): add stable topic hooks for phone-safe CSS hiding

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+2 / -2).

   Git authored: 2026-04-17T15:01:10+02:00; committed: 2026-04-17T15:01:10+02:00.

39. [533954d5](https://github.com/bijux/bijux-std/commit/533954d573bdd1ca180a08fbc5ee84c3fc259771) — feat(header): mark detail and course tab rows as desktop-normal scope

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+2 / -2).

   Git authored: 2026-04-17T15:01:21+02:00; committed: 2026-04-17T15:01:21+02:00.

40. [f8c68de1](https://github.com/bijux/bijux-std/commit/f8c68de112b07acc038a9d6d04b16ca38e667184) — feat(header): annotate detail select fallback as normal-tablet control

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+4 / -4).

   Git authored: 2026-04-17T15:01:33+02:00; committed: 2026-04-17T15:01:33+02:00.

41. [bf72d475](https://github.com/bijux/bijux-std/commit/bf72d47528c318fa7e8b9dc52a21731d4490077f) — docs(header): declare drawer-first phone navigation contract

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+3 / -2).

   Git authored: 2026-04-17T15:01:48+02:00; committed: 2026-04-17T15:01:48+02:00.

42. [478920e1](https://github.com/bijux/bijux-std/commit/478920e1f3f864044ae6d6e12d1f4cd85feea89e) — feat(nav): add mobile Sites block before local drawer tree

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+13 / -0).

   Git authored: 2026-04-17T15:02:56+02:00; committed: 2026-04-17T15:02:56+02:00.

43. [7813422f](https://github.com/bijux/bijux-std/commit/7813422f2b271895cb273cad6b062d65a661e25c) — feat(nav): apply active-state semantics to mobile Sites links

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+8 / -2).

   Git authored: 2026-04-17T15:03:04+02:00; committed: 2026-04-17T15:03:04+02:00.

44. [ea16af14](https://github.com/bijux/bijux-std/commit/ea16af1463b39219190d78d44f4dd7f815bfc7ff) — fix(nav): use hub-specific simplified mobile tree rendering

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+16 / -4).

   Git authored: 2026-04-17T15:03:28+02:00; committed: 2026-04-17T15:03:28+02:00.

45. [2b4a9ce6](https://github.com/bijux/bijux-std/commit/2b4a9ce634745e6c3c7f5cbbc8618c5d2e796870) — fix(nav): flatten duplicate wrapper-home nodes in non-hub mobile tree

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+11 / -1).

   Git authored: 2026-04-17T15:03:38+02:00; committed: 2026-04-17T15:03:38+02:00.

46. [125f85f0](https://github.com/bijux/bijux-std/commit/125f85f00923ceb4ec229277b442e70fafe99a91) — refactor(nav): finalize mobile tree ordering and hub-list semantics

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+8 / -4).

   Git authored: 2026-04-17T15:03:55+02:00; committed: 2026-04-17T15:03:55+02:00.

47. [645c23be](https://github.com/bijux/bijux-std/commit/645c23be590d14d2ec044969a93abe9b3038ef7f) — style(nav): strengthen mobile Sites section separation in drawer

   Change shared/bijux-docs/styles/04-nav.css.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+6 / -3).

   Git authored: 2026-04-17T15:04:46+02:00; committed: 2026-04-17T15:04:46+02:00.

48. [06239944](https://github.com/bijux/bijux-std/commit/062399440e8c32f76ece4e52cd61e2d5d1bdd62f) — style(nav): switch mobile Sites list to single-column stacked layout

   Change shared/bijux-docs/styles/04-nav.css.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+3 / -3).

   Git authored: 2026-04-17T15:04:53+02:00; committed: 2026-04-17T15:04:53+02:00.

49. [14d42fb1](https://github.com/bijux/bijux-std/commit/14d42fb1b6c270523557136abd683515c208c7f0) — style(nav): restyle mobile Sites links as full-width drawer items

   Change shared/bijux-docs/styles/04-nav.css.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+9 / -6).

   Git authored: 2026-04-17T15:05:07+02:00; committed: 2026-04-17T15:05:07+02:00.

50. [a64ae7e4](https://github.com/bijux/bijux-std/commit/a64ae7e4e59f69a9899a639c267975b3da087935) — style(nav): tighten mobile drawer title block and nested tree indentation

   Change shared/bijux-docs/styles/04-nav.css.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+10 / -5).

   Git authored: 2026-04-17T15:05:24+02:00; committed: 2026-04-17T15:05:24+02:00.

51. [d185b684](https://github.com/bijux/bijux-std/commit/d185b6841510bdbf4c6cf3060d523265bd61c4c6) — style(nav): balance mobile tap targets and section-to-tree spacing

   Change shared/bijux-docs/styles/04-nav.css. Added or revised selectors: .bijux-nav--mobile [data-bijux-mobile-order="1-sites"], .bijux-nav--mobile > .md-nav__list[data-bijux-mobile-order="2-tree"].

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+13 / -5).

   Git authored: 2026-04-17T15:05:44+02:00; committed: 2026-04-17T15:05:44+02:00.

52. [2d74eaa4](https://github.com/bijux/bijux-std/commit/2d74eaa403120f9cec631fc91ae4cda090992155) — style(responsive): add phone-only drawer-first shell and hide top ribbons

   Change shared/bijux-docs/styles/08-responsive.css. Added or revised selectors: .bijux-hub-strip, .bijux-course-tabs, .md-header__inner, .md-main__inner, .bijux-nav--mobile .md-nav__source.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+46 / -0).

   Git authored: 2026-04-17T15:06:31+02:00; committed: 2026-04-17T15:06:31+02:00.

53. [679be5f6](https://github.com/bijux/bijux-std/commit/679be5f6f48a1fc9c3e4393794c066851ccd8320) — style(responsive): mirror phone ribbon rules with viewport-state selectors

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+15 / -0).

   Git authored: 2026-04-17T15:06:41+02:00; committed: 2026-04-17T15:06:41+02:00.

54. [0db1bbe7](https://github.com/bijux/bijux-std/commit/0db1bbe75991e3bb1bdca0d71ef2c954d0eaad14) — style(responsive): add compact normal-tablet navigation mode

   Change shared/bijux-docs/styles/08-responsive.css. Added or revised selectors: .bijux-hub-strip, .bijux-detail-tabs, .bijux-detail-select-wrap[data-bijux-compact-control="normal-tablet"], .bijux-detail-tabs .bijux-tabs__list, .bijux-detail-tabs .bijux-tabs__link.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+39 / -0).

   Git authored: 2026-04-17T15:06:55+02:00; committed: 2026-04-17T15:06:55+02:00.

55. [f159c268](https://github.com/bijux/bijux-std/commit/f159c26818d5dfc16832dce8297512430796d8df) — refactor(responsive): replace mixed <=76em block with explicit normal-tablet mode

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+0 / -59).

   Git authored: 2026-04-17T15:07:42+02:00; committed: 2026-04-17T15:07:42+02:00.

56. [96d796e9](https://github.com/bijux/bijux-std/commit/96d796e92e10477279922f60b59da12664026b44) — style(responsive): enforce phone row-scope hiding and tighter narrow-screen spacing

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+9 / -1).

   Git authored: 2026-04-17T15:08:00+02:00; committed: 2026-04-17T15:08:00+02:00.

57. [85ab8ea3](https://github.com/bijux/bijux-std/commit/85ab8ea3739ae388386eeeb23138b6ecce067315) — feat(header): add explicit compact-mode markers for phone topic collapse

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+4 / -4).

   Git authored: 2026-04-17T15:12:53+02:00; committed: 2026-04-17T15:12:53+02:00.

58. [ce4941fa](https://github.com/bijux/bijux-std/commit/ce4941fa553bada9e9a88016772c534a228776f9) — style(responsive): collapse phone page-topic row using compact header markers

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+12 / -0).

   Git authored: 2026-04-17T15:13:03+02:00; committed: 2026-04-17T15:13:03+02:00.

59. [e419c680](https://github.com/bijux/bijux-std/commit/e419c6802ab35c04acb47d0d90ef58cfc8178156) — fix(nav): harden mobile tree de-dup for same-path hub and wrapper entries

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+17 / -11).

   Git authored: 2026-04-17T15:13:28+02:00; committed: 2026-04-17T15:13:28+02:00.

60. [752977b1](https://github.com/bijux/bijux-std/commit/752977b1d48eb98e219e7bbeae9287b96e73ab4c) — style(nav): improve mobile Sites hover and focus visibility

   Change shared/bijux-docs/styles/04-nav.css. Added or revised selectors: .bijux-mobile-hub__link:hover, .bijux-mobile-hub__link:focus-visible.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+14 / -0).

   Git authored: 2026-04-17T15:13:43+02:00; committed: 2026-04-17T15:13:43+02:00.

61. [19443b0a](https://github.com/bijux/bijux-std/commit/19443b0a8be0530e526e67f7b1adb99e85f6b973) — style(responsive): tighten normal-tablet header and compact control sizing

   Change shared/bijux-docs/styles/08-responsive.css. Added or revised selectors: .bijux-detail-select-wrap[data-bijux-compact-control="normal-tablet"] .bijux-detail-select, .md-main__inner.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+20 / -0).

   Git authored: 2026-04-17T15:14:18+02:00; committed: 2026-04-17T15:14:18+02:00.

62. [235da4e8](https://github.com/bijux/bijux-std/commit/235da4e8978d5ddd6a1a12ab58c6f00b5cb80c43) — chore(checks): refresh shared docs directory hash manifest

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T15:15:07+02:00; committed: 2026-04-17T15:15:07+02:00.

63. [6712a4d9](https://github.com/bijux/bijux-std/commit/6712a4d9393f05c27865ad992c0cc8b9c20961d4) — fix(nav): keep primary drawer visible when scoped nav is empty

   Change shared/bijux-docs/styles/04-nav.css.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+0 / -4).

   Git authored: 2026-04-17T16:39:24+02:00; committed: 2026-04-17T16:39:24+02:00.

64. [34eb9215](https://github.com/bijux/bijux-std/commit/34eb92151ef146304238feab63f823c8f4349250) — style(nav): reduce mobile sites block visual weight

   Change shared/bijux-docs/styles/04-nav.css.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+11 / -11).

   Git authored: 2026-04-17T16:39:49+02:00; committed: 2026-04-17T16:39:49+02:00.

65. [eff9fcae](https://github.com/bijux/bijux-std/commit/eff9fcae71d969ae8518471ab6e8bc2970d9955f) — style(nav): clarify mobile local tree and sites separation

   Change shared/bijux-docs/styles/04-nav.css.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+10 / -6).

   Git authored: 2026-04-17T16:40:13+02:00; committed: 2026-04-17T16:40:13+02:00.

66. [ee72ba41](https://github.com/bijux/bijux-std/commit/ee72ba41353538847c69841de49cc912d0b25976) — style(nav): compact mobile drawer header and nested tree spacing

   Change shared/bijux-docs/styles/04-nav.css.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+11 / -11).

   Git authored: 2026-04-17T16:40:41+02:00; committed: 2026-04-17T16:40:41+02:00.

67. [6eae6c8d](https://github.com/bijux/bijux-std/commit/6eae6c8d0ffe28e63b4cd5053dfcd3a44c385647) — style(nav): add phone-dense hub layout and drawer scroll cue

   Change shared/bijux-docs/styles/04-nav.css. Added or revised selectors: .bijux-mobile-hub__list, .bijux-nav--mobile > .md-nav__list, .bijux-nav--mobile > .md-nav__list::after.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+26 / -1).

   Git authored: 2026-04-17T16:41:12+02:00; committed: 2026-04-17T16:41:12+02:00.

68. [b7151987](https://github.com/bijux/bijux-std/commit/b71519872c8fce97796122e904b870b0db15c1e1) — refactor(nav): extract reusable mobile sites block

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+22 / -18).

   Git authored: 2026-04-17T16:44:47+02:00; committed: 2026-04-17T16:44:47+02:00.

69. [4ce6cfd7](https://github.com/bijux/bijux-std/commit/4ce6cfd79faa8169d094efca1eedb92b5bbd127b) — feat(nav): render hub mobile sections with active child level

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+76 / -20).

   Git authored: 2026-04-17T16:45:31+02:00; committed: 2026-04-17T16:45:31+02:00.

70. [0bec5a9b](https://github.com/bijux/bijux-std/commit/0bec5a9b0f34fb7573f447b670f71f73364b6cf6) — feat(nav): prioritize hub sections above mobile sites switcher

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+3 / -2).

   Git authored: 2026-04-17T16:45:43+02:00; committed: 2026-04-17T16:45:43+02:00.

71. [1e1df860](https://github.com/bijux/bijux-std/commit/1e1df860f50b17670bba3e6589296b102cc6fe80) — fix(nav): add non-hub fallback when mobile tree flattens empty

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+19 / -3).

   Git authored: 2026-04-17T16:46:03+02:00; committed: 2026-04-17T16:46:03+02:00.

72. [565c564e](https://github.com/bijux/bijux-std/commit/565c564ed2e73ac37161d615e76e97870d4894c6) — chore(nav): align mobile sites metadata with drawer order

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+2 / -1).

   Git authored: 2026-04-17T16:46:20+02:00; committed: 2026-04-17T16:46:20+02:00.

73. [00e09b30](https://github.com/bijux/bijux-std/commit/00e09b309d869f20a56e7f4db7c4513cb907e2b8) — style(responsive): tighten phone drawer spacing for local navigation

   Change shared/bijux-docs/styles/08-responsive.css. Added or revised selectors: .bijux-mobile-local, .bijux-mobile-local .md-nav > .md-nav__list, .bijux-nav--mobile .md-nav__item, .bijux-nav--mobile .md-nav__link.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+21 / -1).

   Git authored: 2026-04-17T16:47:22+02:00; committed: 2026-04-17T16:47:22+02:00.

74. [95819a53](https://github.com/bijux/bijux-std/commit/95819a5335792ab4839880aecd465326a22d4932) — style(responsive): switch phone sites list to compact two-column grid

   Change shared/bijux-docs/styles/08-responsive.css. Added or revised selectors: .bijux-mobile-hub__list, .bijux-mobile-hub__link, .bijux-mobile-hub__item--active .bijux-mobile-hub__link.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+17 / -0).

   Git authored: 2026-04-17T16:47:33+02:00; committed: 2026-04-17T16:47:33+02:00.

75. [08d2d7fd](https://github.com/bijux/bijux-std/commit/08d2d7fd4cd32bf429f6cf6a6bb6eca5bc798b16) — fix(responsive): enforce phone drawer visibility and scrolling behavior

   Change shared/bijux-docs/styles/08-responsive.css. Added or revised selectors: .md-sidebar--primary, .md-sidebar--primary .md-sidebar__inner.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+17 / -0).

   Git authored: 2026-04-17T16:47:42+02:00; committed: 2026-04-17T16:47:42+02:00.

76. [012dc4fb](https://github.com/bijux/bijux-std/commit/012dc4fbfda8eeeb329409802aae8fe9362f42f5) — style(responsive): streamline very-narrow phone header footprint

   Change shared/bijux-docs/styles/08-responsive.css. Added or revised selectors: .md-header__topic[data-md-component="header-topic"], .md-header__inner, .md-main__inner.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+12 / -0).

   Git authored: 2026-04-17T16:47:50+02:00; committed: 2026-04-17T16:47:50+02:00.

77. [60eb6416](https://github.com/bijux/bijux-std/commit/60eb64168a854dbb4e2cb3b3799fb598c25a8332) — style(responsive): keep tablet header and tabs compact without phone mode

   Change shared/bijux-docs/styles/08-responsive.css. Added or revised selectors: .md-header__inner, .bijux-course-tabs.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+11 / -2).

   Git authored: 2026-04-17T16:48:00+02:00; committed: 2026-04-17T16:48:00+02:00.

78. [e3473a5c](https://github.com/bijux/bijux-std/commit/e3473a5c2dd5d072ee47547213c03702a3066f48) — refactor(viewport): codify breakpoint profile contract

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+15 / -5).

   Git authored: 2026-04-17T16:49:05+02:00; committed: 2026-04-17T16:49:05+02:00.

79. [fc853be1](https://github.com/bijux/bijux-std/commit/fc853be1f27176bd1d39311fc5d814eb1e72c329) — fix(viewport): add width fallback when matchMedia is unavailable

   Change shared/bijux-docs/scripts/viewport-profile.js. Added or revised definitions: toPixelsFromEm, currentViewportWidth.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+32 / -0).

   Git authored: 2026-04-17T16:49:23+02:00; committed: 2026-04-17T16:49:23+02:00.

80. [93ca3a75](https://github.com/bijux/bijux-std/commit/93ca3a75aedcee3acfe658eb46fa7408a9724fed) — feat(viewport): publish profile changes while syncing html and body

   Change shared/bijux-docs/scripts/viewport-profile.js. Added or revised definitions: writeViewportAttribute.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+17 / -2).

   Git authored: 2026-04-17T16:49:39+02:00; committed: 2026-04-17T16:49:39+02:00.

81. [af810236](https://github.com/bijux/bijux-std/commit/af810236594121322822fc77363e53cd1e3a7a1f) — fix(viewport): expand resize listeners for orientation and visual viewport

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+8 / -3).

   Git authored: 2026-04-17T16:49:53+02:00; committed: 2026-04-17T16:49:53+02:00.

82. [042f3e2b](https://github.com/bijux/bijux-std/commit/042f3e2b8c0abeb5b6fa1e7ecd1327eeaa731ce4) — chore(viewport): clarify profile diagnostics with exclusive bands

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+18 / -8).

   Git authored: 2026-04-17T16:50:10+02:00; committed: 2026-04-17T16:50:10+02:00.

83. [62bc64a6](https://github.com/bijux/bijux-std/commit/62bc64a6245faad95c778f48e0010df9c016836c) — refactor(header): define repository and breakpoint scope locals

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+3 / -0).

   Git authored: 2026-04-17T16:51:07+02:00; committed: 2026-04-17T16:51:07+02:00.

84. [62900297](https://github.com/bijux/bijux-std/commit/629002977e2fbddec52f14743e6be5e8e25e1480) — fix(header): harden drawer toggle semantics for phone navigation

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+2 / -1).

   Git authored: 2026-04-17T16:51:29+02:00; committed: 2026-04-17T16:51:29+02:00.

85. [8304ec36](https://github.com/bijux/bijux-std/commit/8304ec36487abab262492b8cd088faab36079a7a) — refactor(header): centralize desktop-normal row and compact band markers

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+8 / -8).

   Git authored: 2026-04-17T16:51:48+02:00; committed: 2026-04-17T16:51:48+02:00.

86. [51d59b4b](https://github.com/bijux/bijux-std/commit/51d59b4b6853b560ca7e2ffe47160445ab84187c) — fix(header): add explicit phone hide markers to desktop navigation rows

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+4 / -4).

   Git authored: 2026-04-17T16:52:10+02:00; committed: 2026-04-17T16:52:10+02:00.

87. [eca98ac5](https://github.com/bijux/bijux-std/commit/eca98ac50fd489f6cc96f9a4c8420732d7f8fc1b) — fix(header): initialize detail-row state for deterministic rendering

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+5 / -2).

   Git authored: 2026-04-17T16:52:33+02:00; committed: 2026-04-17T16:52:33+02:00.

88. [82e47bbd](https://github.com/bijux/bijux-std/commit/82e47bbd103c109ee287dae7434c68cebb9fef90) — fix(nav-reveal): align phone fallback to sub-48em breakpoint

   Change shared/bijux-docs/scripts/nav-reveal.js.

   Changed paths: `shared/bijux-docs/scripts/nav-reveal.js` (+4 / -1).

   Git authored: 2026-04-17T16:54:40+02:00; committed: 2026-04-17T16:54:40+02:00.

89. [1bec4e76](https://github.com/bijux/bijux-std/commit/1bec4e76b37db74af49c58f426d33e8460fffcba) — feat(viewport): expose reusable width classifier for profile mapping

   Change shared/bijux-docs/scripts/viewport-profile.js. Added or revised definitions: classifyViewportWidth.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+15 / -11).

   Git authored: 2026-04-17T16:54:55+02:00; committed: 2026-04-17T16:54:55+02:00.

90. [583abf12](https://github.com/bijux/bijux-std/commit/583abf1214cfaf6a09afea4e3d563020f68f807a) — refactor(nav-reveal): consume viewport profile API and change events

   Change shared/bijux-docs/scripts/nav-reveal.js. Added or revised definitions: resolveViewportMode, revealMobileDrawerContext, bindViewportReveal.

   Changed paths: `shared/bijux-docs/scripts/nav-reveal.js` (+39 / -10).

   Git authored: 2026-04-17T16:55:16+02:00; committed: 2026-04-17T16:55:16+02:00.

91. [75c9f03f](https://github.com/bijux/bijux-std/commit/75c9f03f912698fce8f79f27ffe1905f30c3958a) — fix(responsive): expand phone drawer toggle hit area in header

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+13 / -0).

   Git authored: 2026-04-17T16:55:29+02:00; committed: 2026-04-17T16:55:29+02:00.

92. [ff536a85](https://github.com/bijux/bijux-std/commit/ff536a8556579628dbd0d7ea8b72d7d4e7d2c238) — fix(nav): flatten duplicate hub landing wrappers in phone section children

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+9 / -2).

   Git authored: 2026-04-17T16:55:46+02:00; committed: 2026-04-17T16:55:46+02:00.

93. [0736041b](https://github.com/bijux/bijux-std/commit/0736041ba355e47db9bdd939b3eb39481112b8fb) — fix(manifest): refresh shared docs hash for synced navigation updates

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T17:01:41+02:00; committed: 2026-04-17T17:01:41+02:00.

94. [b599ccb6](https://github.com/bijux/bijux-std/commit/b599ccb639a1ccef0c646f68966e11645a2c0f2d) — refactor(nav): add reusable mobile row rendering helpers

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+25 / -0).

   Git authored: 2026-04-17T17:28:32+02:00; committed: 2026-04-17T17:28:32+02:00.

95. [f2d47fb5](https://github.com/bijux/bijux-std/commit/f2d47fb575e43b224a95dcc6881310cebc582931) — feat(nav): render non-hub top-directories row before sites

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+16 / -33).

   Git authored: 2026-04-17T17:28:55+02:00; committed: 2026-04-17T17:28:55+02:00.

96. [43c66cff](https://github.com/bijux/bijux-std/commit/43c66cff8093acc9d66e1ecfe9c9398b489eb1fe) — feat(nav): add strict second and third-level directory rows

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+42 / -0).

   Git authored: 2026-04-17T17:29:15+02:00; committed: 2026-04-17T17:29:15+02:00.

97. [c2fb83bb](https://github.com/bijux/bijux-std/commit/c2fb83bb9e9392a19bae9617411d25d151dedd9f) — feat(nav): add explicit page-list fallback row by active depth

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+57 / -8).

   Git authored: 2026-04-17T17:29:54+02:00; committed: 2026-04-17T17:29:54+02:00.

98. [d06175e7](https://github.com/bijux/bijux-std/commit/d06175e702205ac69ced66418f86176af6b3f754) — fix(nav): dedupe row entries and align mobile row ordering metadata

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+18 / -2).

   Git authored: 2026-04-17T17:30:19+02:00; committed: 2026-04-17T17:30:19+02:00.

99. [f28c5a0e](https://github.com/bijux/bijux-std/commit/f28c5a0e5a5de0452fe0c6c53af5947d667cefd9) — feat(nav): add dedicated mobile row section styles for local navigation

   Change shared/bijux-docs/styles/04-nav.css. Added or revised selectors: .bijux-mobile-local, .bijux-mobile-local__label, .bijux-mobile-local > .md-nav__list, .bijux-mobile-local > .md-nav__list > .md-nav__item, .bijux-mobile-local > .md-nav__list > .md-nav__item > .md-nav__container > .md-nav__link.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+42 / -0).

   Git authored: 2026-04-17T17:31:08+02:00; committed: 2026-04-17T17:31:08+02:00.

100. [05555f41](https://github.com/bijux/bijux-std/commit/05555f41d23179862c67e908426b49576e85bf5f) — feat(nav): encode mobile row hierarchy and page-row visual cues

   Change shared/bijux-docs/styles/04-nav.css.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+28 / -0).

   Git authored: 2026-04-17T17:31:25+02:00; committed: 2026-04-17T17:31:25+02:00.

101. [0d29ea7f](https://github.com/bijux/bijux-std/commit/0d29ea7f5d1ac590a77ecfdf6c05590d788fa1f0) — style(nav): reduce drawer title and sites block vertical density

   Change shared/bijux-docs/styles/04-nav.css.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+13 / -13).

   Git authored: 2026-04-17T17:31:42+02:00; committed: 2026-04-17T17:31:42+02:00.

102. [27957d55](https://github.com/bijux/bijux-std/commit/27957d55ca1acdbaae3b8f123f8e9f99e5e8de37) — style(nav): strengthen local row active states and reduce nested indent

   Change shared/bijux-docs/styles/04-nav.css. Added or revised selectors: .bijux-mobile-local > .md-nav__list > .md-nav__item > .md-nav__container > .md-nav__link:hover, .bijux-mobile-local > .md-nav__list > .md-nav__item > .md-nav__link[aria-current="page"].

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+20 / -2).

   Git authored: 2026-04-17T17:32:00+02:00; committed: 2026-04-17T17:32:00+02:00.

103. [19892f1d](https://github.com/bijux/bijux-std/commit/19892f1d581ecf91dcf8d6cbeee5ca89c0c7d957) — style(nav): add row separators and section-aware drawer scroll cue

   Change shared/bijux-docs/styles/04-nav.css. Added or revised selectors: .bijux-nav--mobile [data-bijux-mobile-order] + [data-bijux-mobile-order], .bijux-nav--mobile [data-bijux-mobile-order] + [data-bijux-mobile-order]::before, .bijux-nav--mobile, .bijux-nav--mobile::after.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+22 / -4).

   Git authored: 2026-04-17T17:32:23+02:00; committed: 2026-04-17T17:32:23+02:00.

104. [0b108abf](https://github.com/bijux/bijux-std/commit/0b108abfc90e76151f6bd58310603a96d78ccb60) — style(responsive): tighten phone row-group spacing and label density

   Change shared/bijux-docs/styles/08-responsive.css. Added or revised selectors: .bijux-mobile-hub, .bijux-mobile-hub__label.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+12 / -5).

   Git authored: 2026-04-17T17:33:09+02:00; committed: 2026-04-17T17:33:09+02:00.

105. [e60a286d](https://github.com/bijux/bijux-std/commit/e60a286df2021e9fff9e50e39035eb04617e8fa9) — style(responsive): make phone sites row denser than local directory rows

   Change shared/bijux-docs/styles/08-responsive.css. Added or revised selectors: .bijux-mobile-local > .md-nav__list, .bijux-mobile-local > .md-nav__list > .md-nav__item > .md-nav__container > .md-nav__link.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+20 / -1).

   Git authored: 2026-04-17T17:33:22+02:00; committed: 2026-04-17T17:33:22+02:00.

106. [23b9cdbc](https://github.com/bijux/bijux-std/commit/23b9cdbca30b7d009642ddae99cf8e820368a5c9) — fix(responsive): enforce stable phone drawer width and scroll behavior

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+7 / -0).

   Git authored: 2026-04-17T17:33:33+02:00; committed: 2026-04-17T17:33:33+02:00.

107. [67ef1c4e](https://github.com/bijux/bijux-std/commit/67ef1c4e2aa5e136a21285fc063e5bcd84fa9eba) — style(responsive): bring phone drawer navigation higher above the fold

   Change shared/bijux-docs/styles/08-responsive.css. Added or revised selectors: .md-typeset h6, .md-sidebar--primary .md-sidebar__inner.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+18 / -1).

   Git authored: 2026-04-17T17:33:45+02:00; committed: 2026-04-17T17:33:45+02:00.

108. [09aeddc0](https://github.com/bijux/bijux-std/commit/09aeddc00aa90500b699a0d030c204d05a7d6a11) — fix(responsive): restrict phone row-model drawer to phone viewport only

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+13 / -4).

   Git authored: 2026-04-17T17:34:11+02:00; committed: 2026-04-17T17:34:11+02:00.

109. [236f6914](https://github.com/bijux/bijux-std/commit/236f69147307f2727af4f00398c713aaa5d5e931) — refactor(header): centralize drawer and search control wiring

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+5 / -2).

   Git authored: 2026-04-17T17:35:11+02:00; committed: 2026-04-17T17:35:11+02:00.

110. [1696e086](https://github.com/bijux/bijux-std/commit/1696e086316bc7e05d6c9e4b99177203bbf8c1b2) — fix(header): derive page-topic text from safe current-page fallback

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+9 / -5).

   Git authored: 2026-04-17T17:35:23+02:00; committed: 2026-04-17T17:35:23+02:00.

111. [75ced34a](https://github.com/bijux/bijux-std/commit/75ced34a997a73f64e1a55c452d8865eff2772b4) — fix(header): mark active hub strip link with aria-current

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+3 / -1).

   Git authored: 2026-04-17T17:35:32+02:00; committed: 2026-04-17T17:35:32+02:00.

112. [1d71e197](https://github.com/bijux/bijux-std/commit/1d71e19733399c236261666bf9fdfaf0c1f8b18d) — refactor(header): scope detail select controls to desktop-normal rows

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+4 / -4).

   Git authored: 2026-04-17T17:35:48+02:00; committed: 2026-04-17T17:35:48+02:00.

113. [cbee1764](https://github.com/bijux/bijux-std/commit/cbee1764ce10a39e15c9acdfe77fd44bc3e15439) — fix(header): improve control accessibility and header zone semantics

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+5 / -5).

   Git authored: 2026-04-17T17:36:10+02:00; committed: 2026-04-17T17:36:10+02:00.

114. [c0045385](https://github.com/bijux/bijux-std/commit/c004538579e4f08d2f369786f41ccf92bf550bbf) — feat(viewport): expose reference-width profile verification outputs

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+21 / -0).

   Git authored: 2026-04-17T17:36:54+02:00; committed: 2026-04-17T17:36:54+02:00.

115. [8651ed53](https://github.com/bijux/bijux-std/commit/8651ed53aedd78cf4e969cdbfc35c150cd36ac25) — fix(viewport): default fallback width classification to desktop on invalid values

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+9 / -3).

   Git authored: 2026-04-17T17:37:06+02:00; committed: 2026-04-17T17:37:06+02:00.

116. [30842467](https://github.com/bijux/bijux-std/commit/30842467a504c1ce4b94f3533602b08751009052) — fix(viewport): subscribe to breakpoint media query change events

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+11 / -0).

   Git authored: 2026-04-17T17:37:15+02:00; committed: 2026-04-17T17:37:15+02:00.

117. [3d6180e6](https://github.com/bijux/bijux-std/commit/3d6180e63ac02d310fd6b1359a210bd742ff16ed) — feat(viewport): include previous profile and width in change events

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+11 / -1).

   Git authored: 2026-04-17T17:37:25+02:00; committed: 2026-04-17T17:37:25+02:00.

118. [a5d700e2](https://github.com/bijux/bijux-std/commit/a5d700e2f1806092378da19e3ce410c3a51ed0ab) — fix(viewport): add init fallback when document$ is unavailable

   Change shared/bijux-docs/scripts/viewport-profile.js. Added or revised definitions: initWithFallback.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+15 / -1).

   Git authored: 2026-04-17T17:37:34+02:00; committed: 2026-04-17T17:37:34+02:00.

119. [b6aa3232](https://github.com/bijux/bijux-std/commit/b6aa323274655e36829c5f0cb0d821b33ae670fc) — fix(nav): keep hub section row focused on core top-level sections

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+1 / -1).

   Git authored: 2026-04-17T17:38:40+02:00; committed: 2026-04-17T17:38:40+02:00.

120. [1d038b1b](https://github.com/bijux/bijux-std/commit/1d038b1b6cba73f83c8bdfd8537609b7f83d2c5b) — refactor(nav): align mobile order selectors with row-model metadata

   Change shared/bijux-docs/styles/04-nav.css.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+9 / -6).

   Git authored: 2026-04-17T17:38:52+02:00; committed: 2026-04-17T17:38:52+02:00.

121. [9b613450](https://github.com/bijux/bijux-std/commit/9b613450d51dd50ac1bc35441d288fd0384ee7af) — style(responsive): tune phone row spacing using new order groups

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+15 / -0).

   Git authored: 2026-04-17T17:39:05+02:00; committed: 2026-04-17T17:39:05+02:00.

122. [3fea6a32](https://github.com/bijux/bijux-std/commit/3fea6a32538cf3919aa6ff6d16f2727d56671e45) — fix(viewport): align em-to-px fallback with media query baseline

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+9 / -2).

   Git authored: 2026-04-17T17:39:16+02:00; committed: 2026-04-17T17:39:16+02:00.

123. [0f873b69](https://github.com/bijux/bijux-std/commit/0f873b69d13701e74f5ea6d43774689ca43b625a) — docs(scripts): document full viewport profile state matrix

   Change shared/bijux-docs/scripts/README.md.

   Changed paths: `shared/bijux-docs/scripts/README.md` (+1 / -1).

   Git authored: 2026-04-17T17:39:23+02:00; committed: 2026-04-17T17:39:23+02:00.

124. [fdf63522](https://github.com/bijux/bijux-std/commit/fdf63522ab81e9769d82dbc6adeca1e993e210a8) — fix(manifest): refresh shared docs hash after responsive updates

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T17:41:49+02:00; committed: 2026-04-17T17:41:49+02:00.

125. [c99ab6a2](https://github.com/bijux/bijux-std/commit/c99ab6a29c7870a93285bcde7dc6278199683c91) — fix(nav): flatten duplicate wrapper nodes by route equivalence

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+5 / -5).

   Git authored: 2026-04-17T17:55:17+02:00; committed: 2026-04-17T17:55:17+02:00.

126. [538d29b1](https://github.com/bijux/bijux-std/commit/538d29b14b40136802ca96f8dd3768d9d0138191) — feat(nav): render hub mobile rows as sections then active section pages

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+32 / -88).

   Git authored: 2026-04-17T17:56:05+02:00; committed: 2026-04-17T17:56:05+02:00.

127. [de1204e8](https://github.com/bijux/bijux-std/commit/de1204e8a9804b1720a048258705a6faf3e0ef3f) — fix(nav): fallback to first expandable top directory on project roots

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+9 / -0).

   Git authored: 2026-04-17T17:56:27+02:00; committed: 2026-04-17T17:56:27+02:00.

128. [82f33771](https://github.com/bijux/bijux-std/commit/82f337711f77bfa71be39aeb32816286a532c7e7) — chore(nav): clarify mobile row labels for sections and directories

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+3 / -3).

   Git authored: 2026-04-17T17:56:40+02:00; committed: 2026-04-17T17:56:40+02:00.

129. [89e36e4e](https://github.com/bijux/bijux-std/commit/89e36e4edb4012e7fbd4da7d7c027c270c28a119) — fix(nav): add multi-level meaningful-child fallbacks for project rows

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+67 / -0).

   Git authored: 2026-04-17T17:57:18+02:00; committed: 2026-04-17T17:57:18+02:00.

130. [f7aa8661](https://github.com/bijux/bijux-std/commit/f7aa8661143f3cb21a75d92085a976237efde34b) — style(nav): map row-key semantics to clearer mobile row emphasis

   Change shared/bijux-docs/styles/04-nav.css. Added or revised selectors: .bijux-nav--mobile [data-bijux-mobile-order="1-top-directories"] .bijux-mobile-local__label, .bijux-nav--mobile [data-bijux-mobile-order="4-pages"] .bijux-mobile-local__label, .bijux-nav--mobile [data-bijux-mobile-order="4-pages"] > .md-nav__list > .md-nav__item > .md-nav__container > .md-nav__link.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+18 / -0).

   Git authored: 2026-04-17T17:58:16+02:00; committed: 2026-04-17T17:58:16+02:00.

131. [0d202ead](https://github.com/bijux/bijux-std/commit/0d202ead97cc650d049227a7297a4fa63535b8c8) — style(nav): reduce sites row visual weight with narrow-phone fallback

   Change shared/bijux-docs/styles/04-nav.css. Added or revised selectors: .bijux-mobile-hub__list.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+13 / -7).

   Git authored: 2026-04-17T17:58:32+02:00; committed: 2026-04-17T17:58:32+02:00.

132. [0348c7d6](https://github.com/bijux/bijux-std/commit/0348c7d6c8553a8950725a10c767348ec554fffa) — style(nav): tune subdirectory and page-row density for narrow screens

   Change shared/bijux-docs/styles/04-nav.css. Added or revised selectors: .bijux-nav--mobile [data-bijux-mobile-order="3-third-level-directories"] > .md-nav__list > .md-nav__item > .md-nav__container > .md-nav__link, .bijux-nav--mobile [data-bijux-mobile-order="4-pages"] > .md-nav__list > .md-nav__item > .md-nav__container > .md-nav__link.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+16 / -0).

   Git authored: 2026-04-17T17:58:49+02:00; committed: 2026-04-17T17:58:49+02:00.

133. [4753d981](https://github.com/bijux/bijux-std/commit/4753d98101211f5daf14f09f0319e82ac60e33ff) — style(nav): strengthen visual separation between local rows and sites row

   Change shared/bijux-docs/styles/04-nav.css.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+9 / -0).

   Git authored: 2026-04-17T17:59:03+02:00; committed: 2026-04-17T17:59:03+02:00.

134. [24b28665](https://github.com/bijux/bijux-std/commit/24b2866573729a236d1370c4876c0aba4773ac79) — style(nav): improve long-label wrapping and phone drawer scroll affordance

   Change shared/bijux-docs/styles/04-nav.css. Added or revised selectors: .md-sidebar--primary .md-sidebar__inner.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+8 / -0).

   Git authored: 2026-04-17T17:59:18+02:00; committed: 2026-04-17T17:59:18+02:00.

135. [0e7cdbd8](https://github.com/bijux/bijux-std/commit/0e7cdbd8d170f8fc797e7c581cc276b361ffaf5b) — style(responsive): enforce explicit phone row-container visibility

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+2 / -0).

   Git authored: 2026-04-17T18:00:02+02:00; committed: 2026-04-17T18:00:02+02:00.

136. [557344d9](https://github.com/bijux/bijux-std/commit/557344d97b9e8be8dcf0ec7cfce53698ac7bdc3d) — fix(responsive): make sites grid adaptive for narrow-phone labels

   Change shared/bijux-docs/styles/08-responsive.css. Added or revised selectors: .bijux-mobile-hub__list.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+7 / -1).

   Git authored: 2026-04-17T18:00:15+02:00; committed: 2026-04-17T18:00:15+02:00.

137. [d05e3e26](https://github.com/bijux/bijux-std/commit/d05e3e262a655f6ff9522c53c5d5b395f200f381) — style(responsive): pull first local row higher in phone drawer

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+4 / -0).

   Git authored: 2026-04-17T18:00:28+02:00; committed: 2026-04-17T18:00:28+02:00.

138. [dff00a02](https://github.com/bijux/bijux-std/commit/dff00a0201e7603028d45598eaff52c5a1190dba) — fix(responsive): harden phone drawer width floor and scroll momentum

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+3 / -0).

   Git authored: 2026-04-17T18:00:37+02:00; committed: 2026-04-17T18:00:37+02:00.

139. [bbe09e47](https://github.com/bijux/bijux-std/commit/bbe09e47049457f47375a76fff592e774429a58a) — fix(responsive): explicitly hide phone row UI in normal viewport state

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+6 / -0).

   Git authored: 2026-04-17T18:00:46+02:00; committed: 2026-04-17T18:00:46+02:00.

140. [311d2ff3](https://github.com/bijux/bijux-std/commit/311d2ff3526d213a9db59a9374c84449f0547f03) — refactor(viewport-profile): centralize breakpoint contract and reference mapping

   Change shared/bijux-docs/scripts/viewport-profile.js. Added or revised definitions: resolveReferenceProfiles.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+31 / -23).

   Git authored: 2026-04-17T18:03:04+02:00; committed: 2026-04-17T18:03:04+02:00.

141. [904ceddd](https://github.com/bijux/bijux-std/commit/904ceddd3a07393254c396da13b7c370451344c3) — fix(viewport-profile): stabilize width classification on mobile chrome changes

   Change shared/bijux-docs/scripts/viewport-profile.js. Added or revised definitions: normalizeViewportWidth.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+31 / -10).

   Git authored: 2026-04-17T18:03:31+02:00; committed: 2026-04-17T18:03:31+02:00.

142. [39ae0c9a](https://github.com/bijux/bijux-std/commit/39ae0c9a5f28992f04e11a766e86ed3db33005fc) — fix(viewport-profile): refresh profile after orientation settle and page restore

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+34 / -2).

   Git authored: 2026-04-17T18:03:57+02:00; committed: 2026-04-17T18:03:57+02:00.

143. [edc6f46e](https://github.com/bijux/bijux-std/commit/edc6f46e9bbf3d902d5d3e977b5f1a13cbf4c422) — feat(viewport-profile): expose and log reference contract verification

   Change shared/bijux-docs/scripts/viewport-profile.js. Added or revised definitions: verifyReferenceContract.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+26 / -0).

   Git authored: 2026-04-17T18:04:16+02:00; committed: 2026-04-17T18:04:16+02:00.

144. [9a7c4498](https://github.com/bijux/bijux-std/commit/9a7c4498d50428a197de615493ebd70d2025ca25) — chore(viewport-profile): add source metadata for shared script verification

   Change shared/bijux-docs/scripts/viewport-profile.js.

   Changed paths: `shared/bijux-docs/scripts/viewport-profile.js` (+11 / -0).

   Git authored: 2026-04-17T18:04:32+02:00; committed: 2026-04-17T18:04:32+02:00.

145. [b608db7e](https://github.com/bijux/bijux-std/commit/b608db7e28475a8b7745b05996da9aec7b6c9ea5) — refactor(header): harden control ids and title fallbacks

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+8 / -3).

   Git authored: 2026-04-17T18:06:05+02:00; committed: 2026-04-17T18:06:05+02:00.

146. [5e125478](https://github.com/bijux/bijux-std/commit/5e125478738a9af881475f68465437d419f45ea8) — fix(header): strengthen drawer and search control accessibility hooks

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+4 / -2).

   Git authored: 2026-04-17T18:06:26+02:00; committed: 2026-04-17T18:06:26+02:00.

147. [28910013](https://github.com/bijux/bijux-std/commit/28910013e60b5ec1248c6e99efd21b31288bae64) — fix(header): prevent duplicate or empty page topic from crowding header

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+5 / -4).

   Git authored: 2026-04-17T18:06:43+02:00; committed: 2026-04-17T18:06:43+02:00.

148. [b8a960c6](https://github.com/bijux/bijux-std/commit/b8a960c624a4df9ab6440bd8b50d99100f6e40a4) — chore(header): mark desktop-normal-only ribbons and detail controls

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+8 / -8).

   Git authored: 2026-04-17T18:07:17+02:00; committed: 2026-04-17T18:07:17+02:00.

149. [4c3779b7](https://github.com/bijux/bijux-std/commit/4c3779b7c0844a5ce8a9d0fd9ef35a6c683504ce) — chore(header): lock drawer target contract and expose verification metadata

   Change shared/bijux-docs/partials/header.html.

   Changed paths: `shared/bijux-docs/partials/header.html` (+4 / -2).

   Git authored: 2026-04-17T18:07:44+02:00; committed: 2026-04-17T18:07:44+02:00.

150. [6c2d6188](https://github.com/bijux/bijux-std/commit/6c2d61885a8a817a60aef2d9222fb05e35071bdf) — fix(nav-mobile): enforce directory-first rows and conditional page fallback

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+23 / -14).

   Git authored: 2026-04-17T18:09:34+02:00; committed: 2026-04-17T18:09:34+02:00.

151. [371f4623](https://github.com/bijux/bijux-std/commit/371f46230292e76b707585be1a43ba8d3c7e5645) — refactor(nav-mobile): clarify row contract and first-row key semantics

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+6 / -2).

   Git authored: 2026-04-17T18:09:53+02:00; committed: 2026-04-17T18:09:53+02:00.

152. [05615372](https://github.com/bijux/bijux-std/commit/05615372767d29c6bf47a1c20ccb332847e88fb9) — style(nav-mobile): differentiate top-page rows and strengthen nested active states

   Change shared/bijux-docs/styles/04-nav.css. Added or revised selectors: .bijux-nav--mobile [data-bijux-mobile-order="1-top-pages"], .bijux-nav--mobile [data-bijux-mobile-order="1-top-pages"] .bijux-mobile-local__label.

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+20 / -3).

   Git authored: 2026-04-17T18:10:30+02:00; committed: 2026-04-17T18:10:30+02:00.

153. [50f708fb](https://github.com/bijux/bijux-std/commit/50f708fb20215833af74cb802291b066c6286d4d) — fix(responsive): keep normal hub strip and adapt phone sites grid by width

   Change shared/bijux-docs/styles/08-responsive.css. Added or revised selectors: .bijux-hub-strip .bijux-tabs__list--hub, .bijux-hub-strip .bijux-tabs__link--hub.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+15 / -4).

   Git authored: 2026-04-17T18:10:51+02:00; committed: 2026-04-17T18:10:51+02:00.

154. [fc5f22de](https://github.com/bijux/bijux-std/commit/fc5f22de31fd2a73ba79a852cd43a3f1f86c033a) — fix(header): lock search target and protect phone drawer tap area

   Change shared/bijux-docs/partials/header.html, shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/partials/header.html` (+1 / -1); `shared/bijux-docs/styles/08-responsive.css` (+6 / -1).

   Git authored: 2026-04-17T18:11:28+02:00; committed: 2026-04-17T18:11:28+02:00.

155. [957563c1](https://github.com/bijux/bijux-std/commit/957563c1dd25d8affbe6b70c2b2163311aa37938) — chore(gitignore): ignore node modules and ui test artifacts

   Change .gitignore.

   Changed paths: `.gitignore` (+10 / -0).

   Git authored: 2026-04-17T18:42:12+02:00; committed: 2026-04-17T18:42:12+02:00.

156. [fb52294a](https://github.com/bijux/bijux-std/commit/fb52294aec607058d2765789095728ee3b9286a9) — test(ui): add playwright harness and baseline responsive shell checks

   Change Makefile, README.md, tests/README.md, tests/package-lock.json and 4 additional owned paths. Added or revised definitions: displayValue.

   Changed paths: `Makefile` (+13 / -0); `README.md` (+22 / -0); `tests/README.md` (+25 / -0); `tests/package-lock.json` (+78 / -0); `tests/package.json` (+15 / -0); `tests/playwright.config.js` (+47 / -0); `tests/ui/fixtures/responsive-shell.html` (+136 / -0); `tests/ui/specs/responsive-shell.spec.js` (+77 / -0).

   Git authored: 2026-04-17T18:42:26+02:00; committed: 2026-04-17T18:42:26+02:00.

157. [31f42523](https://github.com/bijux/bijux-std/commit/31f4252380611e96efc9577b3b6f69366286dfa6) — test(ui-fixtures): add hub and project navigation regression fixtures

   Change tests/ui/fixtures/navigation-fixture.css, tests/ui/fixtures/navigation-hub-home.html, tests/ui/fixtures/navigation-hub-platform.html, tests/ui/fixtures/navigation-project-deep.html and 2 additional owned paths. Added or revised selectors: .md-sidebar--primary, #__drawer:checked ~ .md-main .md-sidebar--primary.

   Changed paths: `tests/ui/fixtures/navigation-fixture.css` (+14 / -0); `tests/ui/fixtures/navigation-hub-home.html` (+90 / -0); `tests/ui/fixtures/navigation-hub-platform.html` (+39 / -0); `tests/ui/fixtures/navigation-project-deep.html` (+40 / -0); `tests/ui/fixtures/navigation-project-empty-scoped.html` (+39 / -0); `tests/ui/fixtures/navigation-project-root.html` (+38 / -0).

   Git authored: 2026-04-17T18:45:02+02:00; committed: 2026-04-17T18:45:02+02:00.

158. [01aa541e](https://github.com/bijux/bijux-std/commit/01aa541e3033e346f2ae476a6894035381ee0e89) — test(ui-e2e): add hub mobile navigation regression tests

   Change tests/ui/specs/navigation-regression.spec.js. Added or revised definitions: openDrawer, indexInNavOrder.

   Changed paths: `tests/ui/specs/navigation-regression.spec.js` (+83 / -0).

   Git authored: 2026-04-17T18:45:34+02:00; committed: 2026-04-17T18:45:34+02:00.

159. [9c919426](https://github.com/bijux/bijux-std/commit/9c919426c9e2122980f35a9e7efb906b4f9cecec) — test(ui-e2e): complete 10-case navigation regression suite

   Change tests/README.md, tests/ui/specs/navigation-regression.spec.js.

   Changed paths: `tests/README.md` (+2 / -0); `tests/ui/specs/navigation-regression.spec.js` (+80 / -0).

   Git authored: 2026-04-17T18:47:22+02:00; committed: 2026-04-17T18:47:22+02:00.

160. [c68a94d1](https://github.com/bijux/bijux-std/commit/c68a94d199a7944437f7a72b0ed45f7f20f5645d) — test(ui-fixtures): expand mobile sites switcher to full seven-site contract

   Change tests/ui/fixtures/navigation-hub-home.html, tests/ui/fixtures/navigation-project-deep.html, tests/ui/fixtures/navigation-project-root.html.

   Changed paths: `tests/ui/fixtures/navigation-hub-home.html` (+5 / -0); `tests/ui/fixtures/navigation-project-deep.html` (+1 / -1); `tests/ui/fixtures/navigation-project-root.html` (+1 / -1).

   Git authored: 2026-04-17T18:49:00+02:00; committed: 2026-04-17T18:49:00+02:00.

161. [95266b16](https://github.com/bijux/bijux-std/commit/95266b167fcacc4fd07c02dbc6429761418935f3) — test(ui-e2e): add seven-site switcher and cross-site continuity checks

   Change tests/ui/specs/navigation-regression.spec.js.

   Changed paths: `tests/ui/specs/navigation-regression.spec.js` (+34 / -0).

   Git authored: 2026-04-17T18:49:17+02:00; committed: 2026-04-17T18:49:17+02:00.

162. [8b6e97dd](https://github.com/bijux/bijux-std/commit/8b6e97dd4de42c72b9630bf6eb341dc0200f3590) — test(ui-e2e): guard against duplicate wrapper entries in phone drawer

   Change tests/ui/specs/navigation-regression.spec.js. Added or revised definitions: linkTexts.

   Changed paths: `tests/ui/specs/navigation-regression.spec.js` (+20 / -0).

   Git authored: 2026-04-17T18:49:35+02:00; committed: 2026-04-17T18:49:35+02:00.

163. [b1042174](https://github.com/bijux/bijux-std/commit/b1042174c35445fa8b34d66963b9f7b3597ad837) — test(ui): add tablet and desktop guards against phone-mode regressions

   Change tests/ui/specs/responsive-shell.spec.js.

   Changed paths: `tests/ui/specs/responsive-shell.spec.js` (+24 / -0).

   Git authored: 2026-04-17T18:50:08+02:00; committed: 2026-04-17T18:50:08+02:00.

164. [bba45a8d](https://github.com/bijux/bijux-std/commit/bba45a8d93583ce4ea71153867f6a62f53596450) — docs(testing): add navigation-only test target and usage

   Change Makefile, README.md, tests/README.md.

   Changed paths: `Makefile` (+4 / -0); `README.md` (+6 / -0); `tests/README.md` (+3 / -0).

   Git authored: 2026-04-17T18:51:19+02:00; committed: 2026-04-17T18:51:19+02:00.

165. [678f9764](https://github.com/bijux/bijux-std/commit/678f976418e5e08c1a69be1afe2e3c1977d46ce6) — test(ui): harden navigation specs with reusable drawer helpers

   Change tests/ui/specs/helpers/navigation.js, tests/ui/specs/navigation-regression.spec.js, tests/ui/specs/responsive-shell.spec.js. Added or revised definitions: drawerState, ensureDrawerOpen, ensureDrawerClosed, navOrderIndex, extractLinkTexts, expectUniqueLinkTexts, expectOrderedRows.

   Changed paths: `tests/ui/specs/helpers/navigation.js` (+55 / -0); `tests/ui/specs/navigation-regression.spec.js` (+66 / -92); `tests/ui/specs/responsive-shell.spec.js` (+2 / -2).

   Git authored: 2026-04-17T19:07:42+02:00; committed: 2026-04-17T19:07:42+02:00.

166. [737f6c16](https://github.com/bijux/bijux-std/commit/737f6c16b51dbac7cabdd4948e88ebf2b548fdb5) — test(ui): add release-quality phone navigation regression suite

   Change tests/ui/specs/navigation-release-quality.spec.js. Added or revised definitions: unique.

   Changed paths: `tests/ui/specs/navigation-release-quality.spec.js` (+163 / -0).

   Git authored: 2026-04-17T19:07:45+02:00; committed: 2026-04-17T19:07:45+02:00.

167. [f77e0f53](https://github.com/bijux/bijux-std/commit/f77e0f533f9533993c52da17f4ab8043202b493f) — fix(ui-fixtures): derive active project site from URL query state

   Change tests/ui/fixtures/navigation-project-root.html.

   Changed paths: `tests/ui/fixtures/navigation-project-root.html` (+128 / -13).

   Git authored: 2026-04-17T19:07:48+02:00; committed: 2026-04-17T19:07:48+02:00.

168. [e3053211](https://github.com/bijux/bijux-std/commit/e3053211e902c6c6ece056321bd0c4ad77c548bc) — build(test): add dedicated navigation release gate target

   Change Makefile.

   Changed paths: `Makefile` (+4 / -0).

   Git authored: 2026-04-17T19:07:55+02:00; committed: 2026-04-17T19:07:55+02:00.

169. [c555b36e](https://github.com/bijux/bijux-std/commit/c555b36ebc0dd65115f9515fc2d195ffae05476e) — docs(test): document release-gate navigation suite and command

   Change README.md, tests/README.md.

   Changed paths: `README.md` (+6 / -0); `tests/README.md` (+5 / -0).

   Git authored: 2026-04-17T19:08:07+02:00; committed: 2026-04-17T19:08:07+02:00.

170. [254e35cc](https://github.com/bijux/bijux-std/commit/254e35cc4e5c586d746746c1bc4f81035c73aaea) — test(ui-live): add production navigation helper primitives

   Change tests/ui/specs/helpers/live-navigation.js. Added or revised definitions: liveE2EEnabled, liveHubUrl, asAbsoluteUrl, gotoLivePage, openLiveDrawer, sitesBlock, collectSiteMap, expectCanonicalSiteEntries. Added or revised selectors: .map((node) => (.

   Changed paths: `tests/ui/specs/helpers/live-navigation.js` (+84 / -0).

   Git authored: 2026-04-17T19:09:53+02:00; committed: 2026-04-17T19:09:53+02:00.

171. [becc0122](https://github.com/bijux/bijux-std/commit/becc0122a127fbc32b1a42d814eeff0ebbcf7a63) — test(ui-live): add 10 live-site navigation release-gate tests

   Change tests/ui/specs/navigation-live-e2e.spec.js.

   Changed paths: `tests/ui/specs/navigation-live-e2e.spec.js` (+186 / -0).

   Git authored: 2026-04-17T19:10:39+02:00; committed: 2026-04-17T19:10:39+02:00.

172. [bd0cd8ec](https://github.com/bijux/bijux-std/commit/bd0cd8ec5ca50243a3d35e3360fe8f222b074b52) — build(test): add live navigation release-check commands

   Change Makefile, tests/package.json.

   Changed paths: `Makefile` (+4 / -0); `tests/package.json` (+1 / -0).

   Git authored: 2026-04-17T19:10:51+02:00; committed: 2026-04-17T19:10:51+02:00.

173. [715bd18b](https://github.com/bijux/bijux-std/commit/715bd18bbbbfa4539eea5cb1f851e22256cde51b) — docs(test): document live-site navigation release gate usage

   Change README.md, tests/README.md.

   Changed paths: `README.md` (+12 / -0); `tests/README.md` (+17 / -0).

   Git authored: 2026-04-17T19:11:07+02:00; committed: 2026-04-17T19:11:07+02:00.

174. [dff8928e](https://github.com/bijux/bijux-std/commit/dff8928e0163da1ae1cd59e87861f09b8c50b595) — test(ui-live): harden drawer interaction and live selector resilience

   Change Makefile, tests/package.json, tests/ui/specs/helpers/live-navigation.js, tests/ui/specs/helpers/navigation.js and 1 additional owned paths.

   Changed paths: `Makefile` (+1 / -1); `tests/package.json` (+1 / -1); `tests/ui/specs/helpers/live-navigation.js` (+5 / -2); `tests/ui/specs/helpers/navigation.js` (+28 / -2); `tests/ui/specs/navigation-live-e2e.spec.js` (+39 / -14).

   Git authored: 2026-04-17T19:21:58+02:00; committed: 2026-04-17T19:21:58+02:00.

175. [88880175](https://github.com/bijux/bijux-std/commit/888801752bff891dcc2a1bef611f6b1a28a7568b) — fix(manifest): refresh shared docs checksum for live nav updates

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T19:24:41+02:00; committed: 2026-04-17T19:24:41+02:00.

176. [e7e12f1f](https://github.com/bijux/bijux-std/commit/e7e12f1f3b7cd56f9046a1385b563bf50405a053) — fix(docs-shell): stabilize phone header search and viewport lock

   Change shared/bijux-docs/styles/08-responsive.css, tests/ui/fixtures/responsive-shell.html, tests/ui/specs/responsive-shell.spec.js. Added or revised selectors: #__search:not(:checked) ~ .md-header .bijux-header-tools .md-search, #__search:checked ~ .md-header .bijux-header-tools .md-search, #__search:not(:checked) ~ .md-header .bijux-header-tools .md-search__output, .md-content.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+29 / -0); `tests/ui/fixtures/responsive-shell.html` (+21 / -0); `tests/ui/specs/responsive-shell.spec.js` (+12 / -0).

   Git authored: 2026-04-17T19:48:46+02:00; committed: 2026-04-17T19:48:46+02:00.

177. [ed0184be](https://github.com/bijux/bijux-std/commit/ed0184becdd748a50af38a2f8503d53af2ad95c8) — fix(checks): align shared docs manifest hash

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T19:58:12+02:00; committed: 2026-04-17T19:58:12+02:00.

178. [a9ca2921](https://github.com/bijux/bijux-std/commit/a9ca29213d315f8b8e4ad4c9dee574f02e6bd952) — fix(phone-navigation): keep sidebar fully off-canvas when closed

   Change shared/bijux-docs/styles/08-responsive.css, shared/shared-dir-sha256.txt, tests/ui/specs/responsive-shell.spec.js. Added or revised selectors: #__drawer:not(:checked) ~ .md-main .md-sidebar--primary, #__drawer:checked ~ .md-main .md-sidebar--primary.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+25 / -0); `shared/shared-dir-sha256.txt` (+1 / -1); `tests/ui/specs/responsive-shell.spec.js` (+11 / -0).

   Git authored: 2026-04-17T20:11:15+02:00; committed: 2026-04-17T20:11:15+02:00.

179. [e13abab5](https://github.com/bijux/bijux-std/commit/e13abab56c8c632f8eaa517bbaad93b0202d3749) — fix(phone-drawer): stabilize hub sections and open-state alignment

   Change shared/bijux-docs/partials/nav.html, shared/bijux-docs/styles/08-responsive.css, shared/shared-dir-sha256.txt, tests/ui/specs/responsive-shell.spec.js. Added or revised definitions: parseTranslateX.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+28 / -6); `shared/bijux-docs/styles/08-responsive.css` (+4 / -0); `shared/shared-dir-sha256.txt` (+1 / -1); `tests/ui/specs/responsive-shell.spec.js` (+19 / -0).

   Git authored: 2026-04-17T20:23:27+02:00; committed: 2026-04-17T20:23:27+02:00.

180. [a8295b2a](https://github.com/bijux/bijux-std/commit/a8295b2a134f5f1ddca3c7c56c15414aeac06d6d) — feat(bijux-docs): add semantic kinds for mobile navigation rows

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+9 / -9).

   Git authored: 2026-04-17T20:45:47+02:00; committed: 2026-04-17T20:45:47+02:00.

181. [a2937457](https://github.com/bijux/bijux-std/commit/a2937457e30e6c31e976ec9b4da770b1628a2161) — feat(bijux-docs): elevate phone drawer navigation visuals

   Change shared/bijux-docs/styles/04-nav.css. Added or revised selectors: .bijux-mobile-hub, .bijux-nav--mobile [data-bijux-mobile-kind="directories"], .bijux-nav--mobile [data-bijux-mobile-kind="nested-directories"], .bijux-nav--mobile [data-bijux-mobile-kind="pages"], .bijux-nav--mobile [data-bijux-mobile-kind="sites"].

   Changed paths: `shared/bijux-docs/styles/04-nav.css` (+191 / -149).

   Git authored: 2026-04-17T20:49:45+02:00; committed: 2026-04-17T20:49:45+02:00.

182. [b98ee3c2](https://github.com/bijux/bijux-std/commit/b98ee3c2d45caa5fbeaa7bdf266b8f9126c38ec3) — fix(bijux-docs): refine iPhone drawer spacing and panel ergonomics

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+35 / -34).

   Git authored: 2026-04-17T20:51:34+02:00; committed: 2026-04-17T20:51:34+02:00.

183. [8aaeb721](https://github.com/bijux/bijux-std/commit/8aaeb7215c9b161acc6240139c0f114fb696492d) — test(bijux-docs): align navigation fixtures with mobile row metadata

   Change tests/ui/fixtures/navigation-hub-home.html, tests/ui/fixtures/navigation-hub-platform.html, tests/ui/fixtures/navigation-project-deep.html, tests/ui/fixtures/navigation-project-empty-scoped.html and 2 additional owned paths.

   Changed paths: `tests/ui/fixtures/navigation-hub-home.html` (+3 / -3); `tests/ui/fixtures/navigation-hub-platform.html` (+3 / -3); `tests/ui/fixtures/navigation-project-deep.html` (+5 / -5); `tests/ui/fixtures/navigation-project-empty-scoped.html` (+1 / -1); `tests/ui/fixtures/navigation-project-root.html` (+2 / -2); `tests/ui/fixtures/responsive-shell.html` (+3 / -3).

   Git authored: 2026-04-17T20:52:23+02:00; committed: 2026-04-17T20:52:23+02:00.

184. [5fef7658](https://github.com/bijux/bijux-std/commit/5fef7658b5c81b7010972637d3b2cce8b08a9788) — chore(checks): refresh shared directory SHA manifest

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T20:54:47+02:00; committed: 2026-04-17T20:54:47+02:00.

185. [a9b03e68](https://github.com/bijux/bijux-std/commit/a9b03e68d51a0ebf30295b96cb6f5a5680648f69) — fix(nav): improve iPhone drawer rows for project docs

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+17 / -1).

   Git authored: 2026-04-17T21:11:42+02:00; committed: 2026-04-17T21:11:42+02:00.

186. [5d389d18](https://github.com/bijux/bijux-std/commit/5d389d1893170f505309b144cb04a2a2c4aae4a1) — chore(shared): refresh shared directory sha manifest

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T21:12:43+02:00; committed: 2026-04-17T21:12:43+02:00.

187. [b91c8093](https://github.com/bijux/bijux-std/commit/b91c80939f6ddbeca6d8a49cb8d6b2d1cf2433dd) — refactor(nav): unify hub navigation with standard shell logic

   Change shared/bijux-docs/partials/nav.html.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+4 / -48).

   Git authored: 2026-04-17T21:29:33+02:00; committed: 2026-04-17T21:29:33+02:00.

188. [45cc76a4](https://github.com/bijux/bijux-std/commit/45cc76a4951bf5e45b20854bc51cad781b837079) — chore(shared): refresh shared directory sha manifest

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T21:29:38+02:00; committed: 2026-04-17T21:29:38+02:00.

189. [d3037011](https://github.com/bijux/bijux-std/commit/d303701195383b96e2bf4c1624d9337d913b7075) — fix(nav): simplify phone drawer and remove on-page row

   Change shared/bijux-docs/partials/nav.html, shared/bijux-docs/styles/04-nav.css, shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+0 / -14); `shared/bijux-docs/styles/04-nav.css` (+69 / -131); `shared/bijux-docs/styles/08-responsive.css` (+7 / -7).

   Git authored: 2026-04-17T21:41:59+02:00; committed: 2026-04-17T21:41:59+02:00.

190. [e8fe67de](https://github.com/bijux/bijux-std/commit/e8fe67de07f5f257da99c5f2ef5d5d5b69ab1a4d) — chore(shared): refresh shared directory sha manifest

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T21:42:04+02:00; committed: 2026-04-17T21:42:04+02:00.

191. [45759129](https://github.com/bijux/bijux-std/commit/457591296f0e178e7ca2206bb0db0861b18ec52a) — feat(nav): add dynamic drilldown drawer for phone

   Change shared/bijux-docs/partials/nav.html, shared/bijux-docs/scripts/nav-reveal.js, shared/bijux-docs/styles/04-nav.css, shared/bijux-docs/styles/08-responsive.css. Added or revised definitions: directChildren, normalizeTreePath, normalizeCurrentTreePath, readTreeNode, dedupeNodes, effectiveChildren, rootTreeNodes, findTrail. Added or revised selectors: .bijux-mobile-dynamic__header, .bijux-mobile-dynamic__label, .bijux-mobile-dynamic__control, .bijux-mobile-dynamic__control:hover, .bijux-mobile-dynamic__control:disabled.

   Changed paths: `shared/bijux-docs/partials/nav.html` (+38 / -0); `shared/bijux-docs/scripts/nav-reveal.js` (+256 / -0); `shared/bijux-docs/styles/04-nav.css` (+47 / -0); `shared/bijux-docs/styles/08-responsive.css` (+10 / -0).

   Git authored: 2026-04-17T21:52:58+02:00; committed: 2026-04-17T21:52:58+02:00.

192. [939384d5](https://github.com/bijux/bijux-std/commit/939384d55424377fb6dc8f7496d16867bf61489b) — chore(shared): refresh shared directory sha manifest

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T21:53:05+02:00; committed: 2026-04-17T21:53:05+02:00.

193. [dea42925](https://github.com/bijux/bijux-std/commit/dea429258d4f2c90e4b5f4995f226520de41e7c4) — fix(shared-docs): expand content width when scoped nav is empty

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+14 / -0).

   Git authored: 2026-04-17T22:25:40+02:00; committed: 2026-04-17T22:25:40+02:00.

194. [40508e0d](https://github.com/bijux/bijux-std/commit/40508e0d286b84eed668d4d3e9ef5e4b18044697) — chore(shared): refresh shared directory digest

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T22:25:40+02:00; committed: 2026-04-17T22:25:40+02:00.

195. [0d1ef6c6](https://github.com/bijux/bijux-std/commit/0d1ef6c6d733813b47ab7ba563170e9871b01e2b) — feat(shared-docs): add canonical mermaid initializer

   Change shared/bijux-docs/README.md, shared/bijux-docs/scripts/mermaid-init.js. Added or revised definitions: activeMermaidTheme, normalizeMermaidBlocks, prepareMermaidNodesForRerender, renderMermaidDiagrams, captureScrollPosition, restoreScrollPosition.

   Changed paths: `shared/bijux-docs/README.md` (+1 / -0); `shared/bijux-docs/scripts/mermaid-init.js` (+101 / -0).

   Git authored: 2026-04-17T22:30:33+02:00; committed: 2026-04-17T22:30:33+02:00.

196. [da897dd7](https://github.com/bijux/bijux-std/commit/da897dd7ce2f4e01415e296cc4d194554ad072a3) — feat(bijux-checks): enforce canonical mermaid initializer sync

   Change shared/bijux-checks/check-bijux-std.sh.

   Changed paths: `shared/bijux-checks/check-bijux-std.sh` (+28 / -0).

   Git authored: 2026-04-17T22:30:33+02:00; committed: 2026-04-17T22:30:33+02:00.

197. [eb6cf37d](https://github.com/bijux/bijux-std/commit/eb6cf37d5814ee3812f4dc8f77005a54780f5e8c) — chore(shared): refresh shared directory digest

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+2 / -2).

   Git authored: 2026-04-17T22:30:33+02:00; committed: 2026-04-17T22:30:33+02:00.

198. [d9e88d89](https://github.com/bijux/bijux-std/commit/d9e88d8955dc7a4a8212b9924e259198c6f62339) — docs(shared-docs): document canonical mermaid shell script

   Change shared/bijux-docs/scripts/README.md.

   Changed paths: `shared/bijux-docs/scripts/README.md` (+1 / -0).

   Git authored: 2026-04-17T22:32:53+02:00; committed: 2026-04-17T22:32:53+02:00.

199. [b04bca72](https://github.com/bijux/bijux-std/commit/b04bca72ed8706137d8303673a176d19498447b3) — chore(shared): refresh shared directory digest

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T22:32:53+02:00; committed: 2026-04-17T22:32:53+02:00.

200. [50e0452f](https://github.com/bijux/bijux-std/commit/50e0452f99939c75a172643722b99888e8f768c2) — fix(shared-docs): collapse empty scoped sidebar on desktop and wide layouts

   Change shared/bijux-docs/styles/08-responsive.css.

   Changed paths: `shared/bijux-docs/styles/08-responsive.css` (+11 / -3).

   Git authored: 2026-04-17T22:38:54+02:00; committed: 2026-04-17T22:38:54+02:00.

201. [876b8ace](https://github.com/bijux/bijux-std/commit/876b8ace9f6a97e0fd6616a003d19bf60b94ecc9) — test(bijux-checks): guard home layout without empty sidebar gutter

   Change shared/bijux-checks/check-bijux-std.sh.

   Changed paths: `shared/bijux-checks/check-bijux-std.sh` (+37 / -0).

   Git authored: 2026-04-17T22:38:54+02:00; committed: 2026-04-17T22:38:54+02:00.

202. [9bc72d2b](https://github.com/bijux/bijux-std/commit/9bc72d2be73acb95c1889d64a66ac3d9212109f4) — chore(shared): refresh shared directory digest

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+2 / -2).

   Git authored: 2026-04-17T22:38:54+02:00; committed: 2026-04-17T22:38:54+02:00.

203. [6a48ecd0](https://github.com/bijux/bijux-std/commit/6a48ecd0308e019dd10cc49cbaa5e367981ef63f) — feat(shared-gh-py): add canonical GitHub governance and bot policy pack

   Change shared/bijux-gh-py/README.md, shared/bijux-gh-py/dependabot.yml, shared/bijux-gh-py/required-status-checks.md, shared/bijux-gh-py/rulesets/main-branch-protection.json.

   Changed paths: `shared/bijux-gh-py/README.md` (+15 / -0); `shared/bijux-gh-py/dependabot.yml` (+28 / -0); `shared/bijux-gh-py/required-status-checks.md` (+13 / -0); `shared/bijux-gh-py/rulesets/main-branch-protection.json` (+43 / -0).

   Git authored: 2026-04-17T23:05:14+02:00; committed: 2026-04-17T23:05:14+02:00.

204. [fcfc3d09](https://github.com/bijux/bijux-std/commit/fcfc3d094abf68356384e110791be2af6cec36f8) — feat(shared-makes): add bijux-gh-py sync and drift-check targets

   Change shared/bijux-checks/bijux-std-checks.yml, shared/bijux-makes-py/bijux.mk.

   Changed paths: `shared/bijux-checks/bijux-std-checks.yml` (+1 / -0); `shared/bijux-makes-py/bijux.mk` (+33 / -1).

   Git authored: 2026-04-17T23:05:14+02:00; committed: 2026-04-17T23:05:14+02:00.

205. [e1ede453](https://github.com/bijux/bijux-std/commit/e1ede453193f40607a4972ad814f226724488809) — chore(shared): refresh shared directory digest

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+3 / -2).

   Git authored: 2026-04-17T23:05:14+02:00; committed: 2026-04-17T23:05:14+02:00.

206. [1f58df06](https://github.com/bijux/bijux-std/commit/1f58df06fcb578ed8336b7ac72f422882c969ac8) — feat(shared-gh-py): generate dependabot config from python manifests

   Change shared/bijux-gh-py/README.md, shared/bijux-gh-py/dependabot.yml, shared/bijux-gh-py/scripts/render-dependabot.sh.

   Changed paths: `shared/bijux-gh-py/README.md` (+4 / -2); `shared/bijux-gh-py/dependabot.yml` (+0 / -28); `shared/bijux-gh-py/scripts/render-dependabot.sh` (+70 / -0).

   Git authored: 2026-04-17T23:08:41+02:00; committed: 2026-04-17T23:08:41+02:00.

207. [78a9dd17](https://github.com/bijux/bijux-std/commit/78a9dd175f9f2f88a070362d6033784183b82e8f) — feat(shared-makes): sync and validate generated dependabot config

   Change shared/bijux-makes-py/bijux.mk.

   Changed paths: `shared/bijux-makes-py/bijux.mk` (+12 / -1).

   Git authored: 2026-04-17T23:08:44+02:00; committed: 2026-04-17T23:08:44+02:00.

208. [1340c66f](https://github.com/bijux/bijux-std/commit/1340c66f2f5e1d697339175eb923a31aa304dd05) — chore(shared): refresh manifest digests for governance pack

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+2 / -2).

   Git authored: 2026-04-17T23:08:46+02:00; committed: 2026-04-17T23:08:46+02:00.

209. [be253dc2](https://github.com/bijux/bijux-std/commit/be253dc2b2dc2399914805fcfeb0f60866ec9ae9) — chore(shared): refresh manifest after governance renderer updates

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-17T23:11:16+02:00; committed: 2026-04-17T23:11:16+02:00.

210. [39a6d367](https://github.com/bijux/bijux-std/commit/39a6d36770947a11c9c26a6052fda169426e5447) — feat(shared): add canonical internal tooling directory

   Change shared/bijux-checks/bijux-std-checks.yml, shared/internal/quality/__pycache__/markdown_table_guard.cpython-310.pyc, shared/internal/quality/__pycache__/validate_bijux_docs_contract.cpython-310.pyc, shared/internal/quality/__pycache__/validate_shell_contract.cpython-310.pyc and 8 additional owned paths. Added or revised definitions: table_columns, is_separator_row, scan_file, main, MkDocsLoader, _construct_unknown, load_yaml, require.

   Changed paths: `shared/bijux-checks/bijux-std-checks.yml` (+1 / -0); `shared/internal/quality/__pycache__/markdown_table_guard.cpython-310.pyc` (binary); `shared/internal/quality/__pycache__/validate_bijux_docs_contract.cpython-310.pyc` (binary); `shared/internal/quality/__pycache__/validate_shell_contract.cpython-310.pyc` (binary); `shared/internal/quality/markdown_table_guard.py` (+82 / -0); `shared/internal/quality/validate_bijux_docs_contract.py` (+74 / -0); `shared/internal/quality/validate_shell_contract.py` (+12 / -0); `shared/internal/scripts/sync_bijux_docs.sh` (+48 / -0); `shared/internal/scripts/sync_bijux_shell.sh` (+5 / -0); `shared/internal/scripts/verify_bijux_docs_source_of_truth.sh` (+167 / -0); `shared/internal/scripts/verify_shell_source_of_truth.sh` (+5 / -0); `shared/shared-dir-sha256.txt` (+2 / -1).

   Git authored: 2026-04-18T00:01:32+02:00; committed: 2026-04-18T00:01:32+02:00.

211. [b140e835](https://github.com/bijux/bijux-std/commit/b140e83567a59efa9916d6b51beb7da2be438435) — chore(shared): remove generated python cache files

   Change shared/internal/quality/__pycache__/markdown_table_guard.cpython-310.pyc, shared/internal/quality/__pycache__/validate_bijux_docs_contract.cpython-310.pyc, shared/internal/quality/__pycache__/validate_shell_contract.cpython-310.pyc.

   Changed paths: `shared/internal/quality/__pycache__/markdown_table_guard.cpython-310.pyc` (binary); `shared/internal/quality/__pycache__/validate_bijux_docs_contract.cpython-310.pyc` (binary); `shared/internal/quality/__pycache__/validate_shell_contract.cpython-310.pyc` (binary).

   Git authored: 2026-04-18T00:01:35+02:00; committed: 2026-04-18T00:01:35+02:00.

212. [4474f071](https://github.com/bijux/bijux-std/commit/4474f0712e5e4f22589e5604f8537ddac8116abc) — fix(shared): compare shared manifest entries by required directories

   Change shared/internal/scripts/verify_bijux_docs_source_of_truth.sh, shared/shared-dir-sha256.txt.

   Changed paths: `shared/internal/scripts/verify_bijux_docs_source_of_truth.sh` (+13 / -7); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T00:03:52+02:00; committed: 2026-04-18T00:03:52+02:00.

213. [41f8d781](https://github.com/bijux/bijux-std/commit/41f8d781e0b5b8656a4e824581590fb60e99130c) — refactor(shared): rename internal docs tooling directory

   Change shared/bijux-checks/bijux-std-checks.yml, shared/bijux-docs-tooling/quality/__pycache__/markdown_table_guard.cpython-310.pyc, shared/bijux-docs-tooling/quality/__pycache__/validate_bijux_docs_contract.cpython-310.pyc, shared/bijux-docs-tooling/quality/__pycache__/validate_shell_contract.cpython-310.pyc and 15 additional owned paths. Added or revised definitions: table_columns, is_separator_row, scan_file, main, MkDocsLoader, _construct_unknown, load_yaml, require.

   Changed paths: `shared/bijux-checks/bijux-std-checks.yml` (+1 / -1); `shared/bijux-docs-tooling/quality/__pycache__/markdown_table_guard.cpython-310.pyc` (binary); `shared/bijux-docs-tooling/quality/__pycache__/validate_bijux_docs_contract.cpython-310.pyc` (binary); `shared/bijux-docs-tooling/quality/__pycache__/validate_shell_contract.cpython-310.pyc` (binary); `shared/bijux-docs-tooling/quality/markdown_table_guard.py` (+82 / -0); `shared/bijux-docs-tooling/quality/validate_bijux_docs_contract.py` (+74 / -0); `shared/bijux-docs-tooling/quality/validate_shell_contract.py` (+12 / -0); `shared/bijux-docs-tooling/scripts/sync_bijux_docs.sh` (+48 / -0); `shared/bijux-docs-tooling/scripts/sync_bijux_shell.sh` (+5 / -0); `shared/bijux-docs-tooling/scripts/verify_bijux_docs_source_of_truth.sh` (+173 / -0); `shared/bijux-docs-tooling/scripts/verify_shell_source_of_truth.sh` (+5 / -0); `shared/internal/quality/markdown_table_guard.py` (+0 / -82); `shared/internal/quality/validate_bijux_docs_contract.py` (+0 / -74); `shared/internal/quality/validate_shell_contract.py` (+0 / -12); `shared/internal/scripts/sync_bijux_docs.sh` (+0 / -48); `shared/internal/scripts/sync_bijux_shell.sh` (+0 / -5); `shared/internal/scripts/verify_bijux_docs_source_of_truth.sh` (+0 / -173); `shared/internal/scripts/verify_shell_source_of_truth.sh` (+0 / -5); `shared/shared-dir-sha256.txt` (+2 / -2).

   Git authored: 2026-04-18T00:12:11+02:00; committed: 2026-04-18T00:12:11+02:00.

214. [e95c7d4a](https://github.com/bijux/bijux-std/commit/e95c7d4a8d7c4300baf58a59467504502ce07821) — chore(shared): remove generated python cache files

   Change shared/bijux-docs-tooling/quality/__pycache__/markdown_table_guard.cpython-310.pyc, shared/bijux-docs-tooling/quality/__pycache__/validate_bijux_docs_contract.cpython-310.pyc, shared/bijux-docs-tooling/quality/__pycache__/validate_shell_contract.cpython-310.pyc.

   Changed paths: `shared/bijux-docs-tooling/quality/__pycache__/markdown_table_guard.cpython-310.pyc` (binary); `shared/bijux-docs-tooling/quality/__pycache__/validate_bijux_docs_contract.cpython-310.pyc` (binary); `shared/bijux-docs-tooling/quality/__pycache__/validate_shell_contract.cpython-310.pyc` (binary).

   Git authored: 2026-04-18T00:12:24+02:00; committed: 2026-04-18T00:12:24+02:00.

215. [b7bd18b5](https://github.com/bijux/bijux-std/commit/b7bd18b52a0b41e6d88aee652a413739dc68dab6) — docs(readme): reflect current shared standards directories

   Change README.md.

   Changed paths: `README.md` (+14 / -2).

   Git authored: 2026-04-18T00:13:35+02:00; committed: 2026-04-18T00:13:35+02:00.

216. [21579a36](https://github.com/bijux/bijux-std/commit/21579a3634460ace1ef92116393fa64530b3d345) — fix(docs): restore canonical mermaid initializer asset

   Change docs/assets/javascripts/mermaid-init.js. Added or revised definitions: activeMermaidTheme, normalizeMermaidBlocks, prepareMermaidNodesForRerender, renderMermaidDiagrams, captureScrollPosition, restoreScrollPosition.

   Changed paths: `docs/assets/javascripts/mermaid-init.js` (+101 / -0).

   Git authored: 2026-04-18T01:36:52+02:00; committed: 2026-04-18T01:36:52+02:00.

217. [6372d5c5](https://github.com/bijux/bijux-std/commit/6372d5c539a63099e23e93eef89de5a4b49a2b46) — docs(changelog): record unreleased bookkeeping updates

   Change CHANGELOG.md.

   Changed paths: `CHANGELOG.md` (+8 / -0).

   Git authored: 2026-04-18T02:19:08+02:00; committed: 2026-04-18T02:19:08+02:00.

218. [7d20e639](https://github.com/bijux/bijux-std/commit/7d20e6394c5d07e12415a64214151c3b737113cc) — docs(changelog): extend unreleased notes from post-tag changes

   Change CHANGELOG.md.

   Changed paths: `CHANGELOG.md` (+22 / -0).

   Git authored: 2026-04-18T02:21:28+02:00; committed: 2026-04-18T02:21:28+02:00.

219. [0b56e167](https://github.com/bijux/bijux-std/commit/0b56e16789453e0f9ebb4409bcf8db740765bfb8) — refactor(standards): rename shared bijux-gh pack and bijux-standard targets

   Change CHANGELOG.md, README.md, shared/bijux-checks/bijux-std-checks.yml, shared/bijux-docs-tooling/scripts/verify_bijux_docs_source_of_truth.sh and 11 additional owned paths.

   Changed paths: `CHANGELOG.md` (+1 / -1); `README.md` (+1 / -1); `shared/bijux-checks/bijux-std-checks.yml` (+1 / -1); `shared/bijux-docs-tooling/scripts/verify_bijux_docs_source_of_truth.sh` (+2 / -2); `shared/bijux-gh-py/README.md` (+0 / -17); `shared/bijux-gh-py/required-status-checks.md` (+0 / -13); `shared/bijux-gh-py/rulesets/main-branch-protection.json` (+0 / -43); `shared/bijux-gh-py/scripts/render-dependabot.sh` (+0 / -70); `shared/bijux-gh/README.md` (+17 / -0); `shared/bijux-gh/required-status-checks.md` (+13 / -0); `shared/bijux-gh/rulesets/main-branch-protection.json` (+43 / -0); `shared/bijux-gh/scripts/render-dependabot.sh` (+70 / -0); `shared/bijux-makes-py/bijux.mk` (+26 / -19); `shared/bijux-makes-py/repository/root.mk` (+1 / -1); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T14:37:13+02:00; committed: 2026-04-18T14:37:13+02:00.

220. [87dfa1f6](https://github.com/bijux/bijux-std/commit/87dfa1f6edb704c722f0c5b8de5cfc0a6af5ba93) — refactor(standards): move docs tooling under shared bijux-docs

   Change README.md, shared/bijux-checks/bijux-std-checks.yml, shared/bijux-docs-tooling/quality/markdown_table_guard.py, shared/bijux-docs-tooling/quality/validate_bijux_docs_contract.py and 13 additional owned paths. Added or revised definitions: table_columns, is_separator_row, scan_file, main, MkDocsLoader, _construct_unknown, load_yaml, require.

   Changed paths: `README.md` (+2 / -2); `shared/bijux-checks/bijux-std-checks.yml` (+1 / -1); `shared/bijux-docs-tooling/quality/markdown_table_guard.py` (+0 / -82); `shared/bijux-docs-tooling/quality/validate_bijux_docs_contract.py` (+0 / -74); `shared/bijux-docs-tooling/quality/validate_shell_contract.py` (+0 / -12); `shared/bijux-docs-tooling/scripts/sync_bijux_docs.sh` (+0 / -48); `shared/bijux-docs-tooling/scripts/sync_bijux_shell.sh` (+0 / -5); `shared/bijux-docs-tooling/scripts/verify_bijux_docs_source_of_truth.sh` (+0 / -173); `shared/bijux-docs-tooling/scripts/verify_shell_source_of_truth.sh` (+0 / -5); `shared/bijux-docs/tooling/quality/markdown_table_guard.py` (+82 / -0); `shared/bijux-docs/tooling/quality/validate_bijux_docs_contract.py` (+74 / -0); `shared/bijux-docs/tooling/quality/validate_shell_contract.py` (+12 / -0); `shared/bijux-docs/tooling/scripts/sync_bijux_docs.sh` (+48 / -0); `shared/bijux-docs/tooling/scripts/sync_bijux_shell.sh` (+5 / -0); `shared/bijux-docs/tooling/scripts/verify_bijux_docs_source_of_truth.sh` (+173 / -0); `shared/bijux-docs/tooling/scripts/verify_shell_source_of_truth.sh` (+5 / -0); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T14:38:33+02:00; committed: 2026-04-18T14:38:33+02:00.

221. [828bf21f](https://github.com/bijux/bijux-std/commit/828bf21ffa1684f21eae3c065f47a98e2eceb2cf) — feat(checks): add registry-driven check suite artifacts

   Change shared/bijux-checks/check-bijux-std.sh, shared/bijux-checks/registry/checks.json, shared/bijux-checks/registry/owners.json, shared/bijux-checks/registry/suites.json and 3 additional owned paths.

   Changed paths: `shared/bijux-checks/check-bijux-std.sh` (+25 / -10); `shared/bijux-checks/registry/checks.json` (+55 / -0); `shared/bijux-checks/registry/owners.json` (+10 / -0); `shared/bijux-checks/registry/suites.json` (+16 / -0); `shared/bijux-checks/schema/check-report.schema.json` (+52 / -0); `shared/bijux-checks/scripts/run-bijux-check-suite.sh` (+208 / -0); `shared/shared-dir-sha256.txt` (+5 / -5).

   Git authored: 2026-04-18T14:58:57+02:00; committed: 2026-04-18T14:58:57+02:00.

222. [13bc40a8](https://github.com/bijux/bijux-std/commit/13bc40a853da55601a0843205f5e6592f0f5cc23) — feat(ci): publish bijux checks report artifact

   Change .bijux/checks.consumer.json, .github/workflows/bijux-checks-report.yml.

   Changed paths: `.bijux/checks.consumer.json` (+12 / -0); `.github/workflows/bijux-checks-report.yml` (+51 / -0).

   Git authored: 2026-04-18T14:59:04+02:00; committed: 2026-04-18T14:59:04+02:00.

223. [199ee198](https://github.com/bijux/bijux-std/commit/199ee198f16b75401de856268002432135b53b60) — refactor(docs): remove redundant mermaid mirror in bijux-std

   Change docs/assets/javascripts/mermaid-init.js, shared/bijux-checks/check-bijux-std.sh, shared/shared-dir-sha256.txt.

   Changed paths: `docs/assets/javascripts/mermaid-init.js` (+0 / -101); `shared/bijux-checks/check-bijux-std.sh` (+11 / -13); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T15:01:37+02:00; committed: 2026-04-18T15:01:37+02:00.

224. [46cf16de](https://github.com/bijux/bijux-std/commit/46cf16de6403b79b2c2996d795ba9b7150a28783) — refactor(tests): scope docs ui suite under tests/bijux-docs

   Change .gitignore, Makefile, tests/README.md, tests/bijux-docs/README.md and 32 additional owned paths. Added or revised definitions: liveE2EEnabled, liveHubUrl, asAbsoluteUrl, gotoLivePage, openLiveDrawer, sitesBlock, collectSiteMap, expectCanonicalSiteEntries. Added or revised selectors: .md-sidebar--primary, #__drawer:checked ~ .md-main .md-sidebar--primary, .map((node) => (.

   Changed paths: `.gitignore` (+5 / -0); `Makefile` (+1 / -1); `tests/README.md` (+0 / -52); `tests/bijux-docs/README.md` (+60 / -0); `tests/bijux-docs/package-lock.json` (+78 / -0); `tests/bijux-docs/package.json` (+16 / -0); `tests/bijux-docs/playwright.config.js` (+54 / -0); `tests/bijux-docs/ui/fixtures/navigation-fixture.css` (+14 / -0); `tests/bijux-docs/ui/fixtures/navigation-hub-home.html` (+95 / -0); `tests/bijux-docs/ui/fixtures/navigation-hub-platform.html` (+39 / -0); `tests/bijux-docs/ui/fixtures/navigation-project-deep.html` (+40 / -0); `tests/bijux-docs/ui/fixtures/navigation-project-empty-scoped.html` (+39 / -0); `tests/bijux-docs/ui/fixtures/navigation-project-root.html` (+153 / -0); `tests/bijux-docs/ui/fixtures/responsive-shell.html` (+157 / -0); `tests/bijux-docs/ui/specs/helpers/live-navigation.js` (+87 / -0); `tests/bijux-docs/ui/specs/helpers/navigation.js` (+81 / -0); `tests/bijux-docs/ui/specs/navigation-live-e2e.spec.js` (+211 / -0); `tests/bijux-docs/ui/specs/navigation-regression.spec.js` (+191 / -0); `tests/bijux-docs/ui/specs/navigation-release-quality.spec.js` (+163 / -0); `tests/bijux-docs/ui/specs/responsive-shell.spec.js` (+143 / -0); `tests/package-lock.json` (+0 / -78); `tests/package.json` (+0 / -16); `tests/playwright.config.js` (+0 / -47); `tests/ui/fixtures/navigation-fixture.css` (+0 / -14); `tests/ui/fixtures/navigation-hub-home.html` (+0 / -95); `tests/ui/fixtures/navigation-hub-platform.html` (+0 / -39); `tests/ui/fixtures/navigation-project-deep.html` (+0 / -40); `tests/ui/fixtures/navigation-project-empty-scoped.html` (+0 / -39); `tests/ui/fixtures/navigation-project-root.html` (+0 / -153); `tests/ui/fixtures/responsive-shell.html` (+0 / -157); `tests/ui/specs/helpers/live-navigation.js` (+0 / -87); `tests/ui/specs/helpers/navigation.js` (+0 / -81); `tests/ui/specs/navigation-live-e2e.spec.js` (+0 / -211); `tests/ui/specs/navigation-regression.spec.js` (+0 / -191); `tests/ui/specs/navigation-release-quality.spec.js` (+0 / -163); `tests/ui/specs/responsive-shell.spec.js` (+0 / -143).

   Git authored: 2026-04-18T15:04:26+02:00; committed: 2026-04-18T15:04:26+02:00.

225. [20fb0ead](https://github.com/bijux/bijux-std/commit/20fb0ead2faac12d5f3b96a2d62edda9d2e4025e) — refactor(checks): publish reports under artifacts/bijux-checks

   Change .github/workflows/bijux-checks-report.yml, shared/bijux-checks/scripts/run-bijux-check-suite.sh, shared/shared-dir-sha256.txt.

   Changed paths: `.github/workflows/bijux-checks-report.yml` (+2 / -2); `shared/bijux-checks/scripts/run-bijux-check-suite.sh` (+1 / -1); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T15:04:33+02:00; committed: 2026-04-18T15:04:33+02:00.

226. [834755b9](https://github.com/bijux/bijux-std/commit/834755b9bb1e176c73fa0b7e240d9851516895d2) — refactor(build): split make targets into modular makefiles

   Change Makefile, makes/bijux-docs.mk, makes/bijux-std.mk, makes/help.mk and 1 additional owned paths.

   Changed paths: `Makefile` (+1 / -51); `makes/bijux-docs.mk` (+25 / -0); `makes/bijux-std.mk` (+18 / -0); `makes/help.mk` (+3 / -0); `makes/root.mk` (+7 / -0).

   Git authored: 2026-04-18T15:06:21+02:00; committed: 2026-04-18T15:06:21+02:00.

227. [586344f9](https://github.com/bijux/bijux-std/commit/586344f9b64cbd05ee65eedd581e63f02afee771) — refactor(docs): run ui test runtime from artifacts directory

   Change makes/bijux-docs.mk.

   Changed paths: `makes/bijux-docs.mk` (+26 / -12).

   Git authored: 2026-04-18T15:09:50+02:00; committed: 2026-04-18T15:09:50+02:00.

228. [9120e431](https://github.com/bijux/bijux-std/commit/9120e4319803648866e4f26d11212543f75aee0c) — fix(update): prevent destructive shared directory replacement

   Change shared/bijux-checks/update-bijux-std.sh, shared/shared-dir-sha256.txt.

   Changed paths: `shared/bijux-checks/update-bijux-std.sh` (+99 / -9); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T15:16:44+02:00; committed: 2026-04-18T15:16:44+02:00.

229. [61e9f156](https://github.com/bijux/bijux-std/commit/61e9f15629edc207a03ee7863359fdb7f7236a12) — fix(docs): resolve playwright modules from artifacts runtime

   Change .gitignore, makes/bijux-docs.mk.

   Changed paths: `.gitignore` (+1 / -0); `makes/bijux-docs.mk` (+10 / -0).

   Git authored: 2026-04-18T15:19:00+02:00; committed: 2026-04-18T15:19:00+02:00.

230. [4c681100](https://github.com/bijux/bijux-std/commit/4c681100c6f1a215f2435be69b868956b3d85c98) — fix(docs): make ui gates resolve shared assets from repo root

   Change makes/bijux-docs.mk, tests/bijux-docs/ui/fixtures/navigation-hub-home.html, tests/bijux-docs/ui/fixtures/navigation-hub-platform.html, tests/bijux-docs/ui/fixtures/navigation-project-deep.html and 3 additional owned paths.

   Changed paths: `makes/bijux-docs.mk` (+1 / -1); `tests/bijux-docs/ui/fixtures/navigation-hub-home.html` (+2 / -2); `tests/bijux-docs/ui/fixtures/navigation-hub-platform.html` (+2 / -2); `tests/bijux-docs/ui/fixtures/navigation-project-deep.html` (+2 / -2); `tests/bijux-docs/ui/fixtures/navigation-project-empty-scoped.html` (+2 / -2); `tests/bijux-docs/ui/fixtures/navigation-project-root.html` (+2 / -2); `tests/bijux-docs/ui/fixtures/responsive-shell.html` (+2 / -2).

   Git authored: 2026-04-18T15:20:40+02:00; committed: 2026-04-18T15:20:40+02:00.

231. [57040cdb](https://github.com/bijux/bijux-std/commit/57040cdb1ce97dccf50e8e092ab85795645e6fac) — refactor(checks): remove nested docs tooling hash contract

   Change shared/bijux-checks/bijux-std-checks.yml, shared/shared-dir-sha256.txt.

   Changed paths: `shared/bijux-checks/bijux-std-checks.yml` (+0 / -1); `shared/shared-dir-sha256.txt` (+1 / -2).

   Git authored: 2026-04-18T15:26:52+02:00; committed: 2026-04-18T15:26:52+02:00.

232. [9f1c3f4a](https://github.com/bijux/bijux-std/commit/9f1c3f4ac2db2b0274d1f4e2c78b4236fa3339d0) — fix(checks): make bijux-std update safe in source repository

   Change shared/bijux-checks/update-bijux-std.sh, shared/shared-dir-sha256.txt.

   Changed paths: `shared/bijux-checks/update-bijux-std.sh` (+71 / -17); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T15:32:56+02:00; committed: 2026-04-18T15:32:56+02:00.

233. [cfacb05a](https://github.com/bijux/bijux-std/commit/cfacb05ae8c8a4321f192d12059a7dba7420363c) — ci(workflows): unify std and report checks in bijux-std workflow

   Change .github/workflows/bijux-checks-report.yml, .github/workflows/bijux-std-checks.yml, .github/workflows/bijux-std.yml.

   Changed paths: `.github/workflows/bijux-checks-report.yml` (+0 / -51); `.github/workflows/bijux-std-checks.yml` (+0 / -17); `.github/workflows/bijux-std.yml` (+61 / -0).

   Git authored: 2026-04-18T16:21:53+02:00; committed: 2026-04-18T16:21:53+02:00.

234. [ac14444c](https://github.com/bijux/bijux-std/commit/ac14444cf02b29dae49fff81c80dd6e25013ddfa) — ci(shared): unify standards workflow template and required checks

   Change shared/bijux-checks/workflows/bijux-std-checks.yml, shared/bijux-checks/workflows/bijux-std.yml, shared/bijux-gh/required-status-checks.md, shared/bijux-gh/rulesets/main-branch-protection.json and 1 additional owned paths.

   Changed paths: `shared/bijux-checks/workflows/bijux-std-checks.yml` (+0 / -17); `shared/bijux-checks/workflows/bijux-std.yml` (+61 / -0); `shared/bijux-gh/required-status-checks.md` (+2 / -1); `shared/bijux-gh/rulesets/main-branch-protection.json` (+4 / -1); `shared/shared-dir-sha256.txt` (+2 / -2).

   Git authored: 2026-04-18T16:25:21+02:00; committed: 2026-04-18T16:25:21+02:00.

235. [74d41d18](https://github.com/bijux/bijux-std/commit/74d41d186aef72679e67d50f7ef6c390f1f43062) — docs(standards): document unified workflow contract and side effects

   Change CHANGELOG.md, README.md.

   Changed paths: `CHANGELOG.md` (+6 / -1); `README.md` (+20 / -0).

   Git authored: 2026-04-18T16:25:24+02:00; committed: 2026-04-18T16:25:24+02:00.

236. [ca10040e](https://github.com/bijux/bijux-std/commit/ca10040e2b421334493216a5fe808b1b5d0c68c7) — docs(readme): align shared inventory and checks guidance

   Change README.md.

   Changed paths: `README.md` (+23 / -2).

   Git authored: 2026-04-18T16:28:59+02:00; committed: 2026-04-18T16:28:59+02:00.

237. [9bf96391](https://github.com/bijux/bijux-std/commit/9bf96391d534ae0c35ea182c63cefba936296835) — docs(changelog): prepare 0.1.1 release entry

   Change CHANGELOG.md.

   Changed paths: `CHANGELOG.md` (+6 / -0).

   Git authored: 2026-04-18T16:31:52+02:00; committed: 2026-04-18T16:31:52+02:00.

238. [e9dd9e51](https://github.com/bijux/bijux-std/commit/e9dd9e51a83e7b6c3616fa5f51ba80ccef93e9cf) — feat(gh): add shared deploy-docs workflow template

   Change README.md, shared/bijux-gh/README.md, shared/bijux-gh/workflows/deploy-docs.yml, shared/bijux-gh/workflows/docs-deploy.env.example.

   Changed paths: `README.md` (+2 / -0); `shared/bijux-gh/README.md` (+26 / -0); `shared/bijux-gh/workflows/deploy-docs.yml` (+260 / -0); `shared/bijux-gh/workflows/docs-deploy.env.example` (+21 / -0).

   Git authored: 2026-04-18T17:49:43+02:00; committed: 2026-04-18T17:49:43+02:00.

239. [bda11e9c](https://github.com/bijux/bijux-std/commit/bda11e9c8c56cda40902ab11f89cc185c75b3b39) — refactor(std): govern deploy-docs workflow in github sync

   Change shared/bijux-makes-py/bijux.mk.

   Changed paths: `shared/bijux-makes-py/bijux.mk` (+2 / -1).

   Git authored: 2026-04-18T17:49:47+02:00; committed: 2026-04-18T17:49:47+02:00.

240. [faa71113](https://github.com/bijux/bijux-std/commit/faa7111300e38de74168e3af4e02400f29f59de9) — fix(gh): harden deploy-docs artifact path resolution

   Change shared/bijux-gh/workflows/deploy-docs.yml.

   Changed paths: `shared/bijux-gh/workflows/deploy-docs.yml` (+39 / -4).

   Git authored: 2026-04-18T17:56:48+02:00; committed: 2026-04-18T17:56:48+02:00.

241. [812f74ff](https://github.com/bijux/bijux-std/commit/812f74ff73a401c9c888929581894c03d9426773) — docs(gh): add deploy-docs adoption matrix for bijux repos

   Change shared/bijux-gh/README.md, shared/bijux-gh/workflows/deploy-docs-adoption.md.

   Changed paths: `shared/bijux-gh/README.md` (+10 / -0); `shared/bijux-gh/workflows/deploy-docs-adoption.md` (+65 / -0).

   Git authored: 2026-04-18T17:56:53+02:00; committed: 2026-04-18T17:56:53+02:00.

242. [53c077b0](https://github.com/bijux/bijux-std/commit/53c077b033aeac624f8767ee15d88f68950b7833) — fix(std): guard skipped directory loop in updater

   Change shared/bijux-checks/update-bijux-std.sh.

   Changed paths: `shared/bijux-checks/update-bijux-std.sh` (+8 / -6).

   Git authored: 2026-04-18T18:00:26+02:00; committed: 2026-04-18T18:00:26+02:00.

243. [8ce65bca](https://github.com/bijux/bijux-std/commit/8ce65bca0e6bb5d187f600266190bec27fb77a01) — chore(std): refresh shared directory manifest hashes

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+3 / -3).

   Git authored: 2026-04-18T18:00:26+02:00; committed: 2026-04-18T18:00:26+02:00.

244. [c8a25107](https://github.com/bijux/bijux-std/commit/c8a25107e6b2616816c82dba06051952eda2acef) — fix(checks): support .bijux shared path resolution

   Change shared/bijux-checks/check-bijux-std.sh, shared/bijux-checks/update-bijux-std.sh.

   Changed paths: `shared/bijux-checks/check-bijux-std.sh` (+40 / -15); `shared/bijux-checks/update-bijux-std.sh` (+46 / -28).

   Git authored: 2026-04-18T18:05:30+02:00; committed: 2026-04-18T18:05:30+02:00.

245. [c36cfcaf](https://github.com/bijux/bijux-std/commit/c36cfcaf74d18b6aa99a3772bc225d3503c5b258) — chore(std): refresh manifest after checks path updates

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T18:05:31+02:00; committed: 2026-04-18T18:05:31+02:00.

246. [7e9c2624](https://github.com/bijux/bijux-std/commit/7e9c2624618259e59a0c2ce28f6c21bb8fec633e) — feat(gh): add canonical automation identity policy

   Change shared/bijux-gh/README.md, shared/bijux-gh/automation-identity.md, shared/bijux-makes-py/bijux.mk.

   Changed paths: `shared/bijux-gh/README.md` (+1 / -0); `shared/bijux-gh/automation-identity.md` (+42 / -0); `shared/bijux-makes-py/bijux.mk` (+1 / -0).

   Git authored: 2026-04-18T18:15:26+02:00; committed: 2026-04-18T18:15:26+02:00.

247. [51f7a68b](https://github.com/bijux/bijux-std/commit/51f7a68b08618b16306f9a3b5e050556fb5995ea) — chore(std): refresh manifest for automation identity policy

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+2 / -2).

   Git authored: 2026-04-18T18:15:26+02:00; committed: 2026-04-18T18:15:26+02:00.

248. [6e6bab05](https://github.com/bijux/bijux-std/commit/6e6bab05de408bb06fe8c2527b6865034c9bb462) — feat(gh): restrict main bypass to bijux only

   Change shared/bijux-gh/required-status-checks.md, shared/bijux-gh/rulesets/main-branch-protection.json.

   Changed paths: `shared/bijux-gh/required-status-checks.md` (+1 / -0); `shared/bijux-gh/rulesets/main-branch-protection.json` (+7 / -1).

   Git authored: 2026-04-18T18:19:07+02:00; committed: 2026-04-18T18:19:07+02:00.

249. [3a6ca3ef](https://github.com/bijux/bijux-std/commit/3a6ca3efd1c86cf201372e24dd4bfa18a4c031b2) — chore(std): refresh manifest for branch protection policy

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T18:19:07+02:00; committed: 2026-04-18T18:19:07+02:00.

250. [b4f56cfc](https://github.com/bijux/bijux-std/commit/b4f56cfcc30ed5ffac802d43395359d305d4b664) — docs(gh): define ci.yml workflow naming convention

   Change shared/bijux-gh/README.md.

   Changed paths: `shared/bijux-gh/README.md` (+7 / -0).

   Git authored: 2026-04-18T18:28:39+02:00; committed: 2026-04-18T18:28:39+02:00.

251. [a210f0da](https://github.com/bijux/bijux-std/commit/a210f0dae9be5082ba364b5c812afee61185d66f) — chore(std): refresh manifest for workflow naming note

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T18:28:39+02:00; committed: 2026-04-18T18:28:39+02:00.

252. [701d15d9](https://github.com/bijux/bijux-std/commit/701d15d9fb6b1c28f585b4bcbf805616ce139f38) — feat(gh): add shared release-github workflow template

   Change .github/workflows/release-github.yml, shared/bijux-gh/workflows/release-github.yml.

   Changed paths: `.github/workflows/release-github.yml` (+135 / -0); `shared/bijux-gh/workflows/release-github.yml` (+135 / -0).

   Git authored: 2026-04-18T18:47:21+02:00; committed: 2026-04-18T18:47:21+02:00.

253. [1d156c7b](https://github.com/bijux/bijux-std/commit/1d156c7b950892e24ee8ad494982390912e879b8) — feat(gh): add configurable release-github workflow contract

   Change .github/workflows/release-github.yml, shared/bijux-gh/workflows/release-github.yml.

   Changed paths: `.github/workflows/release-github.yml` (+260 / -35); `shared/bijux-gh/workflows/release-github.yml` (+260 / -35).

   Git authored: 2026-04-18T19:01:38+02:00; committed: 2026-04-18T19:01:38+02:00.

254. [d00bbc2d](https://github.com/bijux/bijux-std/commit/d00bbc2d2f792ac37fd40333daf7f90de3a15bd3) — feat(docs): add shared logo and site icon assets

   Change shared/bijux-docs/CONTRACT.md, shared/bijux-docs/README.md, shared/bijux-docs/assets/bijux_icon.png, shared/bijux-docs/assets/bijux_logo_hq.png and 8 additional owned paths.

   Changed paths: `shared/bijux-docs/CONTRACT.md` (+7 / -0); `shared/bijux-docs/README.md` (+4 / -0); `shared/bijux-docs/assets/bijux_icon.png` (binary); `shared/bijux-docs/assets/bijux_logo_hq.png` (binary); `shared/bijux-docs/assets/site-icons/apple-touch-icon-precomposed.png` (binary); `shared/bijux-docs/assets/site-icons/apple-touch-icon.png` (binary); `shared/bijux-docs/assets/site-icons/favicon.ico` (binary); `shared/bijux-docs/scripts/nav-sync.js` (+1 / -1); `shared/bijux-docs/scripts/viewport-profile.js` (+1 / -1); `shared/bijux-docs/tooling/scripts/sync_bijux_docs.sh` (+19 / -2); `shared/bijux-docs/tooling/scripts/verify_bijux_docs_source_of_truth.sh` (+35 / -22); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T19:13:16+02:00; committed: 2026-04-18T19:13:16+02:00.

255. [ea3d8511](https://github.com/bijux/bijux-std/commit/ea3d8511ff57cbd4c8c3303536c958e2d1f67955) — chore(std): refresh shared digest for bijux-gh

   Recompute governed checksum entries in shared/shared-dir-sha256.txt.

   Changed paths: `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T20:32:34+02:00; committed: 2026-04-18T20:32:34+02:00.

256. [7dd55e7f](https://github.com/bijux/bijux-std/commit/7dd55e7f108d32db23a8a512fbc110788591a23e) — docs(changelog): record shared digest refresh for bijux-gh

   Change CHANGELOG.md.

   Changed paths: `CHANGELOG.md` (+4 / -1).

   Git authored: 2026-04-18T20:32:39+02:00; committed: 2026-04-18T20:32:39+02:00.

257. [eab95007](https://github.com/bijux/bijux-std/commit/eab9500741de6c2f03b350c1caaf366f290666de) — feat(gh): add shared release-pypi workflow contract

   Change .github/release-pypi.env, .github/workflows/release-pypi.yml, CHANGELOG.md, README.md and 3 additional owned paths.

   Changed paths: `.github/release-pypi.env` (+6 / -0); `.github/workflows/release-pypi.yml` (+410 / -0); `CHANGELOG.md` (+4 / -0); `README.md` (+2 / -0); `shared/bijux-gh/README.md` (+39 / -0); `shared/bijux-gh/workflows/release-pypi.yml` (+410 / -0); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T20:52:07+02:00; committed: 2026-04-18T20:52:07+02:00.

258. [33987b1c](https://github.com/bijux/bijux-std/commit/33987b1c6b362e1454993c2ea43b58aba3f540fe) — fix(gh): repair release-pypi workflow yaml parsing

   Change .github/workflows/release-pypi.yml, shared/bijux-gh/workflows/release-pypi.yml, shared/shared-dir-sha256.txt.

   Changed paths: `.github/workflows/release-pypi.yml` (+14 / -14); `shared/bijux-gh/workflows/release-pypi.yml` (+14 / -14); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T20:53:46+02:00; committed: 2026-04-18T20:53:46+02:00.

259. [8b3eb13f](https://github.com/bijux/bijux-std/commit/8b3eb13f04cbd508ac5b60b6b29adf8267b40352) — feat(gh): add shared release-crates workflow contract

   Change .github/release-crates.env, .github/workflows/release-crates.yml, CHANGELOG.md, README.md and 3 additional owned paths.

   Changed paths: `.github/release-crates.env` (+7 / -0); `.github/workflows/release-crates.yml` (+224 / -0); `CHANGELOG.md` (+4 / -0); `README.md` (+2 / -0); `shared/bijux-gh/README.md` (+26 / -0); `shared/bijux-gh/workflows/release-crates.yml` (+224 / -0); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T21:01:20+02:00; committed: 2026-04-18T21:01:20+02:00.

260. [02e46dd6](https://github.com/bijux/bijux-std/commit/02e46dd6079f4007cc05a44ea268beef5bfbef7a) — feat(gh): add shared release-ghcr workflow contract

   Change .github/release-ghcr.env, .github/workflows/release-ghcr.yml, CHANGELOG.md, README.md and 3 additional owned paths.

   Changed paths: `.github/release-ghcr.env` (+7 / -0); `.github/workflows/release-ghcr.yml` (+247 / -0); `CHANGELOG.md` (+5 / -0); `README.md` (+2 / -0); `shared/bijux-gh/README.md` (+25 / -0); `shared/bijux-gh/workflows/release-ghcr.yml` (+247 / -0); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T21:13:43+02:00; committed: 2026-04-18T21:13:43+02:00.

261. [22fc8f15](https://github.com/bijux/bijux-std/commit/22fc8f15a6345e17701bf5481dc909c457b4d5af) — refactor(gh): consolidate release settings in release.env

   Change .github/release-crates.env, .github/release-ghcr.env, .github/release-pypi.env, .github/release.env and 7 additional owned paths.

   Changed paths: `.github/release-crates.env` (+0 / -7); `.github/release-ghcr.env` (+0 / -7); `.github/release-pypi.env` (+0 / -6); `.github/release.env` (+5 / -0); `CHANGELOG.md` (+3 / -3); `shared/bijux-gh/README.md` (+3 / -3); `shared/bijux-gh/workflows/release-crates.yml` (+2 / -2); `shared/bijux-gh/workflows/release-ghcr.yml` (+2 / -2); `shared/bijux-gh/workflows/release-github.yml` (+2 / -2); `shared/bijux-gh/workflows/release-pypi.yml` (+2 / -2); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T21:21:05+02:00; committed: 2026-04-18T21:21:05+02:00.

262. [c908e300](https://github.com/bijux/bijux-std/commit/c908e300d8e1341ebeb137b2e0847ddd52a9885f) — chore(gh): remove non-applicable release workflows

   Change .github/workflows/release-crates.yml, .github/workflows/release-ghcr.yml, .github/workflows/release-github.yml, .github/workflows/release-pypi.yml.

   Changed paths: `.github/workflows/release-crates.yml` (+0 / -224); `.github/workflows/release-ghcr.yml` (+0 / -247); `.github/workflows/release-github.yml` (+0 / -360); `.github/workflows/release-pypi.yml` (+0 / -410).

   Git authored: 2026-04-18T21:21:15+02:00; committed: 2026-04-18T21:21:15+02:00.

263. [0e55d211](https://github.com/bijux/bijux-std/commit/0e55d2116e9c282f43483c57c06f2c2d4d392cda) — feat(gh): enforce release package allowlists

   Change CHANGELOG.md, shared/bijux-gh/README.md, shared/bijux-gh/workflows/release-crates.yml, shared/bijux-gh/workflows/release-ghcr.yml and 2 additional owned paths.

   Changed paths: `CHANGELOG.md` (+3 / -0); `shared/bijux-gh/README.md` (+3 / -0); `shared/bijux-gh/workflows/release-crates.yml` (+29 / -1); `shared/bijux-gh/workflows/release-ghcr.yml` (+22 / -1); `shared/bijux-gh/workflows/release-pypi.yml` (+24 / -3); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T21:28:14+02:00; committed: 2026-04-18T21:28:14+02:00.

264. [3d9262ef](https://github.com/bijux/bijux-std/commit/3d9262ef9b68a784bbef2e1e750253876b3e1257) — feat(gh): add standardized release artifact orchestrator

   Change .github/release.env, CHANGELOG.md, shared/bijux-gh/README.md, shared/bijux-gh/workflows/build-release-artifacts.yml and 3 additional owned paths.

   Changed paths: `.github/release.env` (+3 / -0); `CHANGELOG.md` (+8 / -0); `shared/bijux-gh/README.md` (+29 / -0); `shared/bijux-gh/workflows/build-release-artifacts.yml` (+147 / -0); `shared/bijux-gh/workflows/release-artifacts.yml` (+285 / -0); `shared/bijux-gh/workflows/release-github.yml` (+13 / -0); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T21:39:49+02:00; committed: 2026-04-18T21:39:49+02:00.

265. [1a2b39d7](https://github.com/bijux/bijux-std/commit/1a2b39d785594929cd59aa3880c4d5819ba3f12d) — feat(gh): add unified issue and pull request templates

   Change .github/ISSUE_TEMPLATE/bug-report.yml, .github/ISSUE_TEMPLATE/config.yml, .github/ISSUE_TEMPLATE/feature-request.yml, .github/PULL_REQUEST_TEMPLATE/default.md and 9 additional owned paths.

   Changed paths: `.github/ISSUE_TEMPLATE/bug-report.yml` (+49 / -0); `.github/ISSUE_TEMPLATE/config.yml` (+5 / -0); `.github/ISSUE_TEMPLATE/feature-request.yml` (+45 / -0); `.github/PULL_REQUEST_TEMPLATE/default.md` (+21 / -0); `.github/PULL_REQUEST_TEMPLATE/release-change.md` (+20 / -0); `CHANGELOG.md` (+3 / -0); `shared/bijux-gh/ISSUE_TEMPLATE/bug-report.yml` (+49 / -0); `shared/bijux-gh/ISSUE_TEMPLATE/config.yml` (+5 / -0); `shared/bijux-gh/ISSUE_TEMPLATE/feature-request.yml` (+45 / -0); `shared/bijux-gh/PULL_REQUEST_TEMPLATE/default.md` (+21 / -0); `shared/bijux-gh/PULL_REQUEST_TEMPLATE/release-change.md` (+20 / -0); `shared/bijux-gh/README.md` (+14 / -0); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T21:43:51+02:00; committed: 2026-04-18T21:43:51+02:00.

266. [c9c6efb4](https://github.com/bijux/bijux-std/commit/c9c6efb49cd94ede99459a29d5d7c5836d6a9f6b) — chore(gh): add live rulesets directory in standards repo

   Change .github/rulesets/main-branch-protection.json.

   Changed paths: `.github/rulesets/main-branch-protection.json` (+52 / -0).

   Git authored: 2026-04-18T21:45:05+02:00; committed: 2026-04-18T21:45:05+02:00.

267. [d0d881c8](https://github.com/bijux/bijux-std/commit/d0d881c8f4dba52e35ac715998ab4bde6a5a1a60) — feat(gh): standardize reusable release scripts

   Change .github/scripts/wait_for_ci.py, CHANGELOG.md, shared/bijux-gh/README.md, shared/bijux-gh/scripts/wait_for_ci.py and 1 additional owned paths. Added or revised definitions: require_env, parse_github_time, github_get_json, format_run, latest_ci_run, run_is_current_enough, main.

   Changed paths: `.github/scripts/wait_for_ci.py` (+154 / -0); `CHANGELOG.md` (+3 / -0); `shared/bijux-gh/README.md` (+9 / -0); `shared/bijux-gh/scripts/wait_for_ci.py` (+154 / -0); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T21:47:08+02:00; committed: 2026-04-18T21:47:08+02:00.

268. [f1afa1fc](https://github.com/bijux/bijux-std/commit/f1afa1fc7ceab1f4705c18fdd86f13e3e164fc87) — refactor(gh): rename deploy docs env example template

   Change shared/bijux-gh/README.md, shared/bijux-gh/workflows/deploy-docs-adoption.md, shared/bijux-gh/workflows/deploy-docs.env.example, shared/bijux-gh/workflows/docs-deploy.env.example and 1 additional owned paths.

   Changed paths: `shared/bijux-gh/README.md` (+1 / -1); `shared/bijux-gh/workflows/deploy-docs-adoption.md` (+1 / -1); `shared/bijux-gh/workflows/deploy-docs.env.example` (+21 / -0); `shared/bijux-gh/workflows/docs-deploy.env.example` (+0 / -21); `shared/shared-dir-sha256.txt` (+1 / -1).

   Git authored: 2026-04-18T21:50:59+02:00; committed: 2026-04-18T21:50:59+02:00.

269. [8bd53de3](https://github.com/bijux/bijux-std/commit/8bd53de337485c1eda54db674c1e28d678d47019) — docs(github): add shared automation identity and status check policy templates

   Change .github/automation-identity.md, .github/required-status-checks.md.

   Changed paths: `.github/automation-identity.md` (+42 / -0); `.github/required-status-checks.md` (+15 / -0).

   Git authored: 2026-04-18T22:16:47+02:00; committed: 2026-04-18T22:16:47+02:00.

270. [8220b7b9](https://github.com/bijux/bijux-std/commit/8220b7b9f6b777999b219fdb235ec824c6172bec) — ci(github): promote shared release and docs workflows to standard templates

   Change .github/workflows/build-release-artifacts.yml, .github/workflows/deploy-docs.yml, .github/workflows/release-artifacts.yml, .github/workflows/release-github.yml.

   Changed paths: `.github/workflows/build-release-artifacts.yml` (+147 / -0); `.github/workflows/deploy-docs.yml` (+295 / -0); `.github/workflows/release-artifacts.yml` (+285 / -0); `.github/workflows/release-github.yml` (+373 / -0).

   Git authored: 2026-04-18T22:16:50+02:00; committed: 2026-04-18T22:16:50+02:00.

271. [29fcfab3](https://github.com/bijux/bijux-std/commit/29fcfab35c287114783221b9f845a314bc9050c0) — ci(github): add optional release channel workflow templates

   Change .github/workflows/release-crates.yml, .github/workflows/release-ghcr.yml, .github/workflows/release-pypi.yml.

   Changed paths: `.github/workflows/release-crates.yml` (+252 / -0); `.github/workflows/release-ghcr.yml` (+268 / -0); `.github/workflows/release-pypi.yml` (+431 / -0).

   Git authored: 2026-04-18T22:16:59+02:00; committed: 2026-04-18T22:16:59+02:00.

272. [5325d988](https://github.com/bijux/bijux-std/commit/5325d988399cfc96f1f88efa829636ee0e41eb91) — ci(github): enforce shared template checksum parity

   Change .github/bijux-std-shared.sha256, .github/workflows/bijux-std.yml.

   Changed paths: `.github/bijux-std-shared.sha256` (+14 / -0); `.github/workflows/bijux-std.yml` (+1 / -0).

   Git authored: 2026-04-18T22:19:36+02:00; committed: 2026-04-18T22:19:36+02:00.

273. [ebd0c0ff](https://github.com/bijux/bijux-std/commit/ebd0c0ffd380b402fa034a55b0c827cc573d98b8) — ci(github): add reusable workflow templates and pinned action enforcement

   Change .github/bijux-std-shared.sha256, .github/scripts/check_pinned_actions.py, .github/workflows/bijux-std.yml, .github/workflows/reusable-ci-python-packages.yml and 2 additional owned paths. Added or revised definitions: main.

   Changed paths: `.github/bijux-std-shared.sha256` (+5 / -1); `.github/scripts/check_pinned_actions.py` (+48 / -0); `.github/workflows/bijux-std.yml` (+9 / -0); `.github/workflows/reusable-ci-python-packages.yml` (+179 / -0); `.github/workflows/reusable-ci-rust-stack.yml` (+268 / -0); `.github/workflows/reusable-verify-python-packages.yml` (+86 / -0).

   Git authored: 2026-04-18T22:30:38+02:00; committed: 2026-04-18T22:30:38+02:00.

274. [1f69262f](https://github.com/bijux/bijux-std/commit/1f69262f891f11a8fb5ea49ddd4477977228e776) — chore(github): generate repository config from typed manifest

   Change .github/release.env, .github/scripts/build_repo_manifest.py, .github/scripts/render_repo_configs.py, .github/scripts/sync_github_standards.py and 1 additional owned paths. Added or revised definitions: parse_release_env, parse_dependabot, main, yaml_scalar, dump_yaml, render_release_env, find_repo_config, write_if_needed.

   Changed paths: `.github/release.env` (+0 / -1); `.github/scripts/build_repo_manifest.py` (+93 / -0); `.github/scripts/render_repo_configs.py` (+126 / -0); `.github/scripts/sync_github_standards.py` (+119 / -0); `.github/standards/repo-config.manifest.json` (+1663 / -0).

   Git authored: 2026-04-18T22:30:44+02:00; committed: 2026-04-18T22:30:44+02:00.

275. [5da4225a](https://github.com/bijux/bijux-std/commit/5da4225aedcfc2af92bb431875243fa2db2b0ce9) — feat(github): generate wrappers from manifest and enforce protected policy

   Change .github/bijux-std-shared.sha256, .github/scripts/build_repo_manifest.py, .github/scripts/check_protected_github_changes.py, .github/scripts/render_repo_configs.py and 5 additional owned paths. Added or revised definitions: parse_yaml, parse_text, main, render_yaml_document, write_std_pin, ensure_branch, create_pr, wait_for_merge.

   Changed paths: `.github/bijux-std-shared.sha256` (+7 / -1); `.github/scripts/build_repo_manifest.py` (+25 / -3); `.github/scripts/check_protected_github_changes.py` (+77 / -0); `.github/scripts/render_repo_configs.py` (+21 / -2); `.github/scripts/sync_github_standards.py` (+114 / -28); `.github/standards/bijux-std.sha` (+1 / -0); `.github/standards/repo-config.manifest.json` (+488 / -13); `.github/workflows/bijux-std.yml` (+2 / -1); `.github/workflows/github-policy.yml` (+68 / -0).

   Git authored: 2026-04-18T22:40:37+02:00; committed: 2026-04-18T22:40:37+02:00.

276. [7532d933](https://github.com/bijux/bijux-std/commit/7532d9334fb9448f5959f4eaecd21f41423487a9) — docs(github): align standards docs and advance local std pin sha

   Change .github/standards/bijux-std.sha, CHANGELOG.md, README.md, shared/bijux-gh/README.md.

   Changed paths: `.github/standards/bijux-std.sha` (+1 / -1); `CHANGELOG.md` (+10 / -0); `README.md` (+15 / -17); `shared/bijux-gh/README.md` (+27 / -10).

   Git authored: 2026-04-18T22:48:34+02:00; committed: 2026-04-18T22:48:34+02:00.

277. [5f1aeaa7](https://github.com/bijux/bijux-std/commit/5f1aeaa7a65160838a582bf4838dcb2b206b71d7) — ci(release): disable automatic tag triggers for shared release workflows

   Change .github/bijux-std-shared.sha256, .github/workflows/release-artifacts.yml, .github/workflows/release-crates.yml, .github/workflows/release-ghcr.yml and 2 additional owned paths.

   Changed paths: `.github/bijux-std-shared.sha256` (+2 / -2); `.github/workflows/release-artifacts.yml` (+1 / -3); `.github/workflows/release-crates.yml` (+0 / -3); `.github/workflows/release-ghcr.yml` (+0 / -3); `.github/workflows/release-github.yml` (+0 / -3); `.github/workflows/release-pypi.yml` (+0 / -3).

   Git authored: 2026-04-18T22:55:04+02:00; committed: 2026-04-18T22:55:04+02:00.
