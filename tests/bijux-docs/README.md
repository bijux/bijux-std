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
- live built-site release checks in `ui/specs/navigation-live-e2e.spec.js`:
  - 10 production-focused tests on real synced sites, not fixture HTML
  - phone-first drawer behavior plus tablet/desktop regression guards

## Run

```bash
make ui-test-install
make ui-test-install-browsers
make ui-test
make ui-test-navigation
make ui-test-release-gate
make ui-test-live-navigation
```

Or directly:

```bash
npm --prefix tests/bijux-docs run test:ui
```

## Artifacts

Playwright outputs are written under:

- `artifacts/bijux-docs/playwright/test-results/`
- `artifacts/bijux-docs/playwright/html-report/`
- `artifacts/bijux-docs/playwright/junit.xml`

## Live E2E Environment

Live checks are disabled unless enabled explicitly.

- `BIJUX_LIVE_E2E=1` enables `navigation-live-e2e.spec.js`
- `BIJUX_LIVE_HUB_URL` overrides the hub URL (default: `https://bijux.io/`)

Example:

```bash
BIJUX_LIVE_E2E=1 BIJUX_LIVE_HUB_URL=https://bijux.io/ make ui-test-live-navigation
```
