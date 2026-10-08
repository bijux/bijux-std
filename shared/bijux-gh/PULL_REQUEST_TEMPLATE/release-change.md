## Release Change Checklist

Use this template for release workflow, package publication, or artifact pipeline updates.

## Summary
- What release surface changed and why.

## Release Surface
- [ ] `release.env` keys added/changed are documented.
- [ ] Workflow templates and active workflows stay aligned.
- [ ] Allowed package/crate lists are explicitly scoped.

## Validation
- [ ] Workflow YAML parsed successfully.
- [ ] Hash parity against canonical `bijux-std` templates is verified.
- [ ] A dry-run or equivalent validation evidence is attached.

## Risk
- [ ] Duplicate publication risk checked.
- [ ] On/off gates and fallback behavior verified.

## Pull request change record

- [ ] Describe the resulting behavior in the repository-owned changelog fragment.
- [ ] Bind its number and title to this actual PR after creation; keep it pending until a verified merge.
- [ ] Reconcile all base records, regenerate the central projection and attach strict local validation.

Adopted repositories use `python3 .github/scripts/changelog.py validate`,
`check-pr --number <actual-pr> --base <actual-full-base-sha> --title <actual-title>`
and `render --check`. Before PR creation, `validate --draft` permits an unknown
number and does not qualify a merge. See the repository's `changelog/README.md`.
Consumers adopt explicitly; a missing config is not a completed history check.
