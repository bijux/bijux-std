# Changelog

This file records notable repository-level changes for `bijux-std`.

## Pull request history

### Pending review

#### [#196](https://github.com/bijux/bijux-std/pull/196) — docs\(changelog\): record maintainer trust history

Record 12 reviewed historical PRs concerning maintainer trust.

- CODEOWNERS, trusted auto-merge author classes, eligibility retries and owner-controlled approval.
- Preserve original reviewed titles, verified merge dates and source-history distinctions while retaining all prior PR records.

#### [#195](https://github.com/bijux/bijux-std/pull/195) — docs\(changelog\): present concise pull request history

Use a concise PR-led changelog with newest review identities first and preserve historical source notes separately.

- Replace the version-organized central changelog with the simple repository header and truthful pending/merged PR sections.
- Keep all43previous material statements and verified source/tag distinctions in the foundation archive; historical PR imports and preceding main-history notices remain separately reviewed.

#### [#192](https://github.com/bijux/bijux-std/pull/192) — ci\(governance\): enforce exact pull request change records

Check actual PR records and projection in CI and document the repository author workflow.

- Add a bounded changelog job and invoke the same checker inside the existing mandatory standards gate, including standards-repository bot authors.
- Carry author instructions through shared PR templates and expose Make targets without modifying release or deployment workflows.

### Merged pull requests

#### 2026-10-08T17:41:36Z — [#193](https://github.com/bijux/bijux-std/pull/193) — test\(docs\): settle native drawer before pointer input

Sample native pointer targets after finite drawer transitions and retain the open drawer through summary activation.

- Reuse the existing passive ancestor-animation observer without forcing semantic state or cancelling animations.
- Verify ordinary no-script drawer opening, summary activation and actual destination navigation in the maintained phone/tablet/desktop journeys.

#### 2026-10-08T17:24:44Z — [#191](https://github.com/bijux/bijux-std/pull/191) — feat\(governance\): validate repository pull request change records

Validate exact PR change records and generate a reproducible history without replacing existing release notes.

- Add the offline standard-library validator and shared mirror with managed ownership and meaningful negative controls.
- Keep existing historical notes intact outside the generated section; workflow enforcement and the full historical import remain separate reviews.

#### 2026-10-08T16:47:44Z — [#189](https://github.com/bijux/bijux-std/pull/189) — fix\(docs\): preserve accessible reader controls and literal input

Keep search metadata readable, distinguish navigation landmarks, and preserve ordinary character input outside focused search.

- Use the scheme-aware foreground on search metadata and an escaped site-specific primary navigation label.
- Remove global character-only search activation while retaining named Search controls, editable typing, native result keys, modifiers, Escape and Back.
- Parse the full generated runtime before emission and require source-bound accessibility and shortcut browser groups.

#### 2026-05-01T23:11:37Z — [#86](https://github.com/bijux/bijux-std/pull/86) — fix\(github\): fallback to runner event payload path in pr approval policy

PR approval reads the actual GitHub runner event payload.

- Use GH\_EVENT\_PATH with GITHUB\_EVENT\_PATH fallback and fail clearly if neither exists.

#### 2026-05-01T21:30:22Z — [#84](https://github.com/bijux/bijux-std/pull/84) — feat\(github\): enforce owner-gated pr approval policy

PR approval is explicitly controlled by the repository owner.

- Require owner-self-signoff for bijux-authored PRs and an approving bijux review for other authors through a managed approval workflow.

#### 2026-04-21T14:03:27Z — [#45](https://github.com/bijux/bijux-std/pull/45) — chore\(github\): recognize bot author aliases in automerge

Auto-merge recognizes the managed bot author aliases.

- Treat the @dependabot\[bot\] and @github-actions\[bot\] forms consistently with the existing trusted-bot set.
- Original GitHub merge caacc0fa75d845cbbfdd27ee47ec9c5007b23f10 is distinct from rewritten main-history delivery 7f7ec7da5d1e6b1b1466dcfaadc6ca8dcc97ec11; the merge date is the verified GitHub date.

#### 2026-04-21T09:43:10Z — [#39](https://github.com/bijux/bijux-std/pull/39) — fix\(automerge\): enforce PR trust classes and merge-group readiness

Auto-merge eligibility is limited to trusted bot changes on allowed paths.

- Classify protected governance, safe bot and product changes, reject branches behind their base and use squash for the then-current auto-merge mode.
- Add merge\_group handling so required standards checks work with merge queues.
- Original GitHub merge ddcfaea4e5a15ec5905e3d82eb3e804472b9725c is distinct from rewritten main-history delivery 5fa39fc8eb0856a3c0a95617b13165f643564bb7; the merge date is the verified GitHub date.

#### 2026-04-20T22:36:17Z — [#38](https://github.com/bijux/bijux-std/pull/38) — ci\(automerge\): tighten trust gates and disable direct merge fallback

Auto-merge requires explicit opt-in and avoids privileged direct fallback merging.

- Use pull\_request events, require the automerge label, remove direct merge fallback and reduce contents permission to read.
- Original GitHub merge 10b534a32d71434d3fafe5c03ad87ea7c225441a is distinct from rewritten main-history delivery 291a08c11d7e130c793ebe3d856e3dc63cd24a7d; the merge date is the verified GitHub date.

#### 2026-04-20T01:34:05Z — [#34](https://github.com/bijux/bijux-std/pull/34) — fix\(github\): make automerge retries check-suite aware

Auto-merge enablement retries when a check suite completes.

- Resolve the PR from check\_suite pull requests so automation can act after required checks become successful.
- Original GitHub merge d35733591734dd43bc8e5286d87f3a3b48c8d472 is distinct from rewritten main-history delivery 6c84f61f9a5a915c429439c657852fd4fd2a74a4; the merge date is the verified GitHub date.

#### 2026-04-18T23:26:21Z — [#10](https://github.com/bijux/bijux-std/pull/10) — docs\(github\): document clean-status direct merge fallback

Auto-merge guidance records the historical clean-status direct merge fallback.

- Describe the then-current workflow\_run and fallback behavior; later trust-policy changes are recorded in their own PR entries.
- Original GitHub merge b09ae203a52fef4e75d01c9301598ce38bc7d298 is distinct from rewritten main-history delivery fa5862ff95b5432579916011c01d2e3b873a7f28; the merge date is the verified GitHub date.

#### 2026-04-18T23:25:34Z — [#9](https://github.com/bijux/bijux-std/pull/9) — docs\(github\): align automerge behavior with workflow\_run retry path

Auto-merge guidance identifies the workflow\_run retry path.

- Explain how completed workflow activity can retry auto-merge enablement after the initial PR event.
- Original GitHub merge 854ebf46ec9c343df4d2ff5b930b282034aae5f0 is distinct from rewritten main-history delivery 638d7f318d81811c2caea3b31b86d0fad97828fb; the merge date is the verified GitHub date.

#### 2026-04-18T23:23:14Z — [#8](https://github.com/bijux/bijux-std/pull/8) — docs\(github\): note bounded retries for unstable automerge

Auto-merge guidance records bounded retries for unstable PR state.

- Explain the retry behavior used to make enablement reliable without an unbounded waiting loop.
- Original GitHub merge 93d931ec432ae99d8d0be97c17b42bc1cd18ae9f is distinct from rewritten main-history delivery 76440a40f30ed87b26a5f07421ae861f8982b10b; the merge date is the verified GitHub date.

#### 2026-04-18T23:18:24Z — [#7](https://github.com/bijux/bijux-std/pull/7) — docs\(github\): describe stable-state wait before automerge

Auto-merge guidance covers stable-state waiting and token permissions.

- Describe the bounded wait before enabling auto-merge when GitHub has not yet settled the PR state.
- Original GitHub merge 904b249982176a51e0d88aa9893f4758e8bf78a3 is distinct from rewritten main-history delivery b24f81c3d960058350ce75c529ba314d6ace615a; the merge date is the verified GitHub date.

#### 2026-04-18T23:14:04Z — [#6](https://github.com/bijux/bijux-std/pull/6) — docs\(github\): document codeowner-author automerge policy

Auto-merge guidance describes the trusted CODEOWNER-author policy.

- Document the required-check condition for enabling auto-merge on eligible owner-authored changes.
- Original GitHub merge 128e8496069bc658bcfa56a2014fffa048889922 is distinct from rewritten main-history delivery 594401a470fdf968ed442efac46537ae75889435; the merge date is the verified GitHub date.

#### 2026-04-18T21:51:27Z — [#2](https://github.com/bijux/bijux-std/pull/2) — feat\(github\): add CODEOWNERS and align main PR gate for auto-merge

Managed CODEOWNERS participates in standards synchronization and merge policy.

- Carry ownership rules through protected-change checks and allow the configured solo-maintainer auto-merge gate to rely on required checks.
- Original GitHub merge 7b916ec99c6d67d1c9c71e3d3a09c14dc2e4b660 is distinct from rewritten main-history delivery 26ae5a7d2c3dc7e53ca5003ba2ccf592935d6902; the merge date is the verified GitHub date.
