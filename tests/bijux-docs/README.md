# Generated navigation qualification

The navigation gate renders canonical `shared/bijux-docs` through real MkDocs
1.6.1 and Material 9.7.7, including the native layout, index, worker, configured
imports and shell runtime. Its acceptance uses ordinary pointer and keyboard
input. It never forces a click or mutates a checkbox to produce acceptance.

## Setup and required gate

Use the CI-admitted Node 24.21.0 and the exact Playwright 1.58.2 lock. Renderer
dependencies are locked in `generated/requirements.lock.txt`. Python environments,
Node dependencies, package caches, browser binaries, builds and reports live
under root `artifacts/bijux-docs/`.

```bash
make ui-test-install
make ui-test-install-docs
make ui-test-install-browsers
make ui-test-navigation
```

On Linux CI, Playwright installation also needs `--with-deps` for the three
engines. The repository CI owns that operating-system setup.

`ui-test-navigation` runs strict fixture rendering, runtime/reporting contracts,
actual consumer-copy contracts, and two explicitly bounded browser matrices:

- Fourteen shell journeys in all nine Chromium/Firefox/WebKit phone, compact
  and desktop projects: 126 cases in `playwright/qualification.json`.
- Three additional drawer interaction journeys in each engine's phone project:
  nine cases in `drawer-playwright/qualification.json`.

Both matrices require exact nonzero planned/executed counts, all declared
projects, zero failures and zero skips. A filtered suite cannot satisfy a
complete declared matrix. Receipts name their scope, source digests, generated
manifest digest, browser versions and verification limits. Firefox phone means a
viewport/touch profile, not unsupported mobile browser emulation.

## Production rendering and delivery evidence

The builder renders nine canonical ecosystem identities plus sparse-navigation
and expanded-label fixtures. It records registry URL adaptation to the local
server, original source hashes, Git revision, dirty-candidate classification,
renderer versions and generated file hashes. Changing source during a build
rejects that incoherent candidate. Per-scenario strict build logs remain beside
the manifest. The server exclusively serves the selected output and refuses to
reuse another existing server.

`generated/test_navigation_projection.py` separately executes the actual
production consumer synchronization script. Only repository-root discovery is
substituted, so it needs no synthetic Git repository. It proves that every owned
partial, style and shell dependency reaches the real explicit copier output,
with byte identity and repeatability. Removing required navigation source must
fail before consumer configuration or documents are written. Broad fixture copy
behavior alone cannot certify downstream delivery.

The navigation matrix covers responsive boundaries from 320 to 1440 pixels,
semantic hidden state, bounded mastheads, narrow phone title space, tablet
pointer input, Space/Enter drawer opening, Escape/focus restoration, actual
parent overview links, all ecosystem destinations, truthful current-page state,
resize/history behavior, genuine native search results, sparse/growth trees,
no-script ordinary links and native disclosure keyboard behavior. The extra
matrix covers deterministic Tab containment, inert background/restoration,
backdrop dismissal, enlarged text/spacing at 320 pixels, and ten ordinary instant
history journeys while holding explicit drawer intent beyond Material's admitted
125ms delayed toggle reset.

## Separate scopes and limits

The larger shell command `make ui-test` retains all sixteen generated shell
journeys. The bounded navigation gate explicitly excludes the diagram/rich-content
journey and the broader all-consumer search-index inventory. Their separate
qualification must be reported independently; this navigation gate does not
claim repaired diagram rendering, security, publication provenance, CSP, missing
search-index recovery or production content correctness. Native successful search
interaction remains required in every navigation profile.

Headless checks do not establish physical iOS/Android behavior, actual browser
zoom, native IME, screen-reader usability, full WCAG conformance, complete real
consumer extension compatibility or deployed-byte identity. Text enlargement
and spacing are engineering reflow fixtures.

## Focused and read-only checks

```bash
BIJUX_UI_ARTIFACT_ROOT="$PWD/artifacts/bijux-docs/focused" \
PLAYWRIGHT_BROWSERS_PATH="$PWD/artifacts/bijux-docs/playwright/browsers" \
artifacts/bijux-docs/node-runtime/node_modules/.bin/playwright test \
  --config tests/bijux-docs/playwright.navigation.config.js \
  --project chromium-compact
```

A focused selection is diagnosis rather than the complete declared matrix.
`BIJUX_GENERATED_ROOT` selects retained rendered output. Always use another report
location when checking an existing receipt.

```bash
BIJUX_LIVE_E2E=1 make ui-test-live-navigation
```

Live checks are ordinary read-only published journeys. They require explicit
enablement, and `BIJUX_LIVE_HUB_URL` can select another deployment. Their receipt
cannot certify candidate-to-publication equivalence without independently
verified publication identity. No check publishes the website.
