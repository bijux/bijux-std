# UI Regression Tests

This test workspace validates responsive UI/UX behavior for
`shared/bijux-docs` before release.

## Coverage

- phone viewport behavior (`390px`)
- normal/tablet behavior (`1024px`)
- wide desktop behavior (`1920px`)
- viewport profile contract in `scripts/viewport-profile.js`

## Run

```bash
make ui-test-install
make ui-test-install-browsers
make ui-test
```

Or directly:

```bash
npm --prefix tests run test:ui
```
