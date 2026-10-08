## Summary
- Describe the user-facing or operator-facing outcome.
- Link the owning issue, incident, or decision record.

## Scope
- List key files or surfaces changed.
- Call out non-goals and intentionally untouched areas.

## Validation
- [ ] Fast local checks passed.
- [ ] Relevant targeted tests passed.
- [ ] CI run link is attached.

## Contracts and Docs
- [ ] Contract or schema updates are included where behavior changed.
- [ ] Generated artifacts are refreshed.
- [ ] User-facing documentation is updated.

## Release and Risk
- [ ] Breaking change impact is documented.
- [ ] Rollback path is documented when operational risk exists.

## Pull request change record

- [ ] Describe the resulting behavior in the repository-owned changelog fragment.
- [ ] Bind its number and title to this actual PR after creation; keep it pending until a verified merge.
- [ ] Reconcile all base records, regenerate the central projection and attach strict local validation.

Adopted repositories use `python3 .github/scripts/changelog.py validate`,
`check-pr --number <actual-pr> --base <actual-full-base-sha> --title <actual-title>`
and `render --check`. Before PR creation, `validate --draft` permits an unknown
number and does not qualify a merge. See the repository's `changelog/README.md`.
Consumers adopt explicitly; a missing config is not a completed history check.
