# Pull request change records

`bijux-std` records each PR's impact in `changelog/fragments/<scope>/<intent>.json`.
Use stable domain and behavior names, such as `docs/search-query-focus.json`.
One fragment owns one actual PR identity; its details can explain several related
commits. Reviews should describe the resulting behavior and relevant limits,
including dependency, maintenance and automation changes.

The offline checker is canonical under `.github/scripts/changelog.py`, with a
byte-identical shared distribution under `shared/bijux-gh/scripts/`. No GitHub
client, API credentials, package release tags or network requests are required.
The contract validates structure and identity, not the editorial truth of an
impact statement or the authenticity of an asserted historical merge date.

## Author workflow

1. Create a fragment using the schema below. Before opening a PR, keep `pr: null`
   and use `validate --draft`. That is preparation, not merge qualification.
2. Open the actual draft PR. Read its assigned number, then bind that exact number
   with `assign`. Never predict an ID or copy another PR's number.
3. Keep `title` exactly equal to the actual Conventional PR title. New pending
   records require `type(scope): subject`; `!` must agree with `breaking`.
4. Reconcile all current base fragments, run `render --write`, and stage the
   fragment and central projection. Resolve projection conflicts by regenerating
   from the union of records; never select one side and discard another PR.
5. Run strict validation and exact review checks, then include the fragment and
   validation command in the PR description. CI applies this to every author,
   including bots; there is no empty-entry or actor exemption.

```sh
python3 .github/scripts/changelog.py validate --draft
python3 .github/scripts/changelog.py assign \
  --fragment changelog/fragments/docs/search-query-focus.json --pr "$actual_pr"
python3 .github/scripts/changelog.py render --write
python3 .github/scripts/changelog.py validate
python3 .github/scripts/changelog.py check-pr \
  --number "$actual_pr" --base "$actual_full_base_sha" --title "$actual_pr_title"
python3 .github/scripts/changelog.py render --check
```

The changed fragment must be tracked in Git. The base is the actual full review
base SHA, not a guessed branch position. CI reads the actual event's number,
title and base SHA directly from its JSON payload. It rejects a missing, stale,
wrong-number, duplicate or removed prior PR record. An unrelated successful
release workflow does not satisfy this gate.

The default PR workflow runs on opened, synchronized and reopened reviews. It
checks the event's exact title at that invocation; an edited title or
ready-for-review transition alone does not establish a fresh identity check.
After changing a title, update the fragment and push that correction to trigger
synchronized verification. Reviewers must compare the current title and recorded
identity before merging. This offline gate does not claim continuous observation
of mutable GitHub metadata or replace live branch-protection administration.

## Record schema

```json
{
  "schema": 1,
  "pr": null,
  "title": "fix(docs): restore keyboard access to search results",
  "type": "fix",
  "scope": "docs",
  "summary": "Readers can move from the query to a result and return safely.",
  "details": ["Describe the affected reader journey and relevant validation."],
  "status": "pending",
  "merged_at": null,
  "breaking": false
}
```

Every key is required; additional keys and duplicate JSON keys fail. Types are
`feat`, `fix`, `perf`, `docs`, `ci`, `build`, `test`, `refactor`, `chore` and
`revert`. Scope must match the directory. Text is plain, trimmed, nonempty and
single-line; multiple details use multiple array entries. Draft validation alone
admits a null number. Strict projection never admits an unidentified PR.

After verified merge observation, a reviewed change may set `status: "merged"`
and the actual UTC `merged_at`, such as `2026-10-08T14:30:00Z`. Pending entries
cannot claim a date. Preserve original historical titles even when they predate
the Conventional title rule. If merge status is known but its date cannot be
verified, retain null and use the section for unverified dates. Every section
orders entries by descending PR number; recorded merge timestamps remain actual
observations and are not changed to manufacture that order.
Merge into a topic branch is not an independent publication to main; describe
its main delivery ownership honestly in the record.

## Projection and adoption

`changelog/config.json` has exactly `schema: 1`, the actual `owner/repository`,
and `mode`. `pr-history` projects the entire central `CHANGELOG.md`; it replaces
standard-repository version headings with actual PR history. `bijux-std` uses
this mode with a short repository header and separate pending, merged and
unverified-date sections, each ordered by descending actual PR number. Historical imports
must come from reviewed source identities and API evidence, not inferred IDs or
dates. `render --check` detects any drift. The default `render` writes a preview
to `artifacts/changelog/CHANGELOG.md`; `--write` intentionally updates the governed
central file.

Other repositories adopt explicitly by adding their own configuration and records.
Their package release behavior is unchanged. `append` mode preserves all existing
content outside one `<!-- bijux:pr-history:start -->` /
`<!-- bijux:pr-history:end -->` marker pair. Add those markers deliberately before
the first projection; missing or repeated markers fail. No consumer config or
release history is generated by standards synchronization.

The [foundation archive](FOUNDATION.md) preserves 43 audited legacy facts, actual
tags and source distinctions which cannot truthfully become independent PR entries.
The central changelog contains PR history; this author guide provides the archive
link without adding an archive introduction to that projection.
Changing these notes does not authorize inventing PR identities or merge dates.

The shared CI gate explicitly reports unadopted consumers; it does not claim they
passed PR-history qualification. `bijux-std` cannot omit its config to bypass the
gate. Adopted repositories must keep their own config and use the mandatory
gate; repository protection remains an administrator-owned setting. This change
does not manufacture branch protection, merge evidence or a release.
