# UI Regression Tests

This test workspace validates responsive UI/UX behavior for
`shared/bijux-docs` before release.

## Coverage

- phone viewport behavior (`390px`)
- normal/tablet behavior (`1024px`)
- wide desktop behavior (`1920px`)
- viewport profile contract in `scripts/viewport-profile.js`
- navigation regression flows in `ui/specs/navigation-regression.spec.js`:
  - 10 responsive navigation contract tests from `TODO.md`
  - 5 additional regression guards for switcher completeness, cross-site continuity,
    wrapper duplication protection, and tablet/desktop mode isolation
- release-quality phone navigation regressions in
  `ui/specs/navigation-release-quality.spec.js`:
  - 10 deeper drawer, active-state, row-order, and cross-site continuity checks
  - stricter assertions for href integrity and navigation state recovery after toggles

## Run

```bash
make ui-test-install
make ui-test-install-browsers
make ui-test
make ui-test-navigation
make ui-test-release-gate
```

Or directly:

```bash
npm --prefix tests run test:ui
```
