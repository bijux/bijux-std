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
renderer versions and generated file hashes. Each scenario also records the exact
effective MkDocs configuration digest and byte count, with one aggregate identity
carried through fixture transport and browser reports. Private configuration
inputs stay with the producer. Changing source or configuration during a build
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

`make ui-test-navigation-destinations` gives the authored fixture graph its own
phone qualification in Chromium, Firefox and WebKit. Root documents, section
destinations and nested destinations have disjoint ownership, with at most ten
routes per test. Every route retains ordinary activation, accessible names,
current-page truth, expanded ancestry, Escape/invoker focus, retained-document
reader focus and native Back assertions. The source graph oracle rejects stale
destinations, and ownership validation rejects omissions and overlap. The
original parent-overview case independently keeps its single overview journey.
This separation keeps the thirty-second test and three-minute job limits intact.

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

## Rendered contrast and primary targets

`make ui-test-contrast` builds the actual thirteen Material fixtures at the same
origin as its browser server, then requires all 39 cases in nine engine/profile
projects. The cases measure visible text against rendered backgrounds, meaningful
icons, opaque focus rings, primary 44px hit areas, light/dark and forced-color
responses, and actual Previous reader navigation with browser Back. The three
phone projects additionally exercise native Navigation with JavaScript disabled.
Desktop cases require the compact drawer control to be hidden.

The reader-direction negative fixture loads 06-components.css with its exact authored
preimage from 56730b993878c0f6d0ba3f4ed1ff9d60c6bb1d92, whose digest is checked
by the measurement unit test. It must detect hidden phone reader directions or
insufficient visible direction contrast. Diagnostic glyph-paint removal is used
only to sample backgrounds; behavior always uses ordinary input.

The same negative case also loads the exact 07-utilities.css preimage from
9bb8ed253f3b3eea9084b48abb97a4b99bdf3ccb, checks its digest, and proves that
ordinary keyboard focus reaches a control whose external ring is clipped.

Receipts and traces live under artifacts/bijux-docs/contrast-playwright; the
immutable fixture manifest lives under artifacts/bijux-docs/contrast-generated.
This bounded gate does not certify all components, every consumer, axe findings,
manual assistive testing or physical operating-system high contrast. WebKit
forced-color emulation is qualified as source response only.

The same cases also qualify disclosure and repository focus at scroll and
masthead boundaries. Ordinary Tab/Shift+Tab traverses the controls; the outline
must fit every clipping ancestor and contrast with actual adjacent screenshot
paint. Auto changes and returns the OS color scheme while the control remains
focused. Forced-colors uses unmodified paint, because hiding an outline can
change or retain UA-forced paint. These measurements do not certify physical
system palettes or assistive-technology usability.

## Parallel CI qualification

`std / navigation fixtures` installs the admitted renderer, runs the isolated
contracts, renders both fixture origins once and collects each complete suite
inventory without launching a browser. Its compressed, digest-bound fixture
archive belongs to the current workflow run and Git candidate.

Each registered journey group has a separate job in Chromium, Firefox and
WebKit. Each job downloads that archive and installs
only the locked Node test runtime. It executes its explicitly assigned projects
without rebuilding fixtures or repeating renderer tests. Each job has a
three-minute limit; failed attempts retain their receipts and diagnostics.

The required `std / navigation` check aggregates every assigned receipt. It
rejects missing, duplicated, skipped, failed or retried cases, source/bundle
changes, absent or inconsistent actual engine versions and mismatched JUnit
case identities. Explicit shards cannot independently claim complete matrix
qualification. Ordinary `--project` diagnosis still fails the complete gate
when another required project is absent. Existing local Make targets remain
available for complete or focused diagnosis.

`make ui-test-link-policy` builds canonical authored-link fixtures and runs nine
cases in each of nine engine/profile projects (81 total).
`BIJUX_LINK_POLICY_ORIGIN` selects the loopback fixture origin (default port 4173).
The cases preserve authored targets, relations, names/descriptions and downloads;
use ordinary same-window/Back, new-tab/opener and fragment/history journeys;
verify actual delivered download bytes; exercise coordinated document replacement
and an explicit dynamic-extension fixture; and replay exact reviewed consumer
source as the blanket-target counterfactual. Controlled outside replies prove
browser semantics, not provider availability or production CSP.

## Native reader history

`playwright.history.config.js` declares 27 ordinary journeys: three cases in each
Chromium, Firefox and WebKit phone, compact and desktop profile. They exercise
authored fragment Back/Forward, direct product fragments, actual Next reader
destinations and JavaScript-disabled links. Each restoration samples the exact
URL for at least 1500ms without writing history, forcing input, finishing
animations or changing scroll position. The interval exceeds the admitted
Material scroll tracking debounce/delay and the observed hosted pointer
settlement window. It verifies sampled stability, not every possible schedule.

The shared default omits automatic `navigation.tracking` while retaining native
anchors, instant navigation and `toc.follow`. An authored tracking opt-in has its
own compatibility duty. The hosted historical WebKit failure remains evidence
of a real fragment resurrection; passing default journeys do not claim that
tracking opt-in was repaired or reproduce that Linux schedule on another host.

Produce the canonical inventory with `reporting/inventory.js`, execute the full
config or explicit assigned engine shards, and retain strict receipts and their
complete aggregate as described in [shard reporting](reporting/README.md).

Native history qualification retains exact Back/Forward and authored-fragment routes throughout passive restoration windows. It has its own bounded browser group in every engine. Automatic `navigation.tracking` is excluded from the default shell; an explicitly authored opt-in remains a consumer decision.

Renderer command qualification owns a separate three-minute job. It executes exactly three source-bound Make journeys and retains before/after public bytes, per-case command output and installed lock identity. The final navigation aggregate independently rehashes every command receipt and requires its job success. Unsupported runtime profiles prove rejection before public mutation and keep positive qualification pending; they grant no publication approval.

Native search reflow qualification observes opening and closing geometry across phone, tablet and desktop boundaries, including real JavaScript-disabled navigation. Each size group has an independent bounded job in every engine.

Diagram rendering and contrast/target journeys run in separate engine jobs. Their independently assigned receipts are both mandatory in the final navigation aggregate. The three-minute budget includes cold browser-image setup, artifact transport and job finalization.

Popup relationships, product-local search scope and native drawer dismissal are qualified together through ordinary generated Material journeys. Exact engine/case inventories remain required in separate bounded groups; grouped source remains qualified against main before acceptance.

Immutable fixture transport stores each identical rendered payload once and reconstructs the exact manifest/site bytes without links. Diagnostic build logs remain intact; damaged, extra, missing and escaped payloads fail before admission. Native query and invoker journeys have separate bounded engine jobs, with both mandatory in the complete source-bound aggregate.

`make ui-test-reader-accessibility` exercises short-screen drawer traversal, RTL destinations, reader focus and fragment history. The required browser gate assigns its five cases independently to each engine.

`make ui-test-diagram-trust` qualifies scientific labels and descriptions, rejected resource/configuration inputs, and malformed/oversized isolation. Its three cases are independently assigned to every engine; the existing diagram lifecycle gate remains mandatory.

## Automated accessibility states

`make ui-test-accessibility-state` runs three cases in each engine, with nine
actual scan states per engine: root/deep documents, modal phone drawers and
empty/known-answer search. Ordinary pointer, keyboard and theme requests qualify
the inspected state. An Auto theme request uses an explicitly simulated dark
system preference; it is not physical operating-system qualification.

The development dependency `@axe-core/playwright` is pinned to 4.13.0 with its
locked axe-core bytes. Every scan runs the full default rule set with resource
preloading disabled, no excluded targets and no explicit disabled rules. Raw
violations, incomplete findings, computed metadata foreground/background chains
and trusted-input observations are attached to each case. Confirmed violations
fail the gate; incomplete findings remain reviewer-owned limitations and do not
become passes. A zero-violation scan does not certify full WCAG conformance,
assistive reading, physical devices, actual zoom or deployed consumers.

The independent `accessibility-state` engine group is mandatory in the existing
source/fixture/JUnit aggregate. It does not replace the reader, popup, contrast or
native navigation groups. The gate and publication verifier retain their own
required inventory; missing engine or case receipts cannot qualify a release.

Global character-only `/`, `f` and `s` no longer activate search. The independent
`search-shortcut-modality` engine group and `make ui-test-search-shortcut-modality`
retain ordinary named-button Tab/Space invocation, literal editable typing,
native query/result keys, modifiers, Escape and instant Back across owned and
native headers. Its six cases per engine supplement the unchanged search and
invoker inventories. Native browser character defaults are observed rather than
replaced with scripted focus or state changes. Material runtime emission parses
the entire final generated script before writing assets; malformed output cannot
replace the previous valid bundle.

## Desktop registry overflow

`make ui-test-registry-overflow` runs three bounded desktop cases in each admitted
engine, nine cases total: every expanded registry destination at 1220px using
named pointer controls; current and last destinations at 1440px using native
Tab/Enter; and current and last destinations using trusted touch. The latter
two cases retain focused native scrolling controls, disabled/enabled Space
behavior, endpoint ownership and phone focus handoff.

The original 126 shell case identities and predicates are restored unchanged.
These desktop journeys have their own group rather than extending the expensive
expanded-registry shell case. Original 30-second case and three-minute whole-job
limits remain required, with no retries or omitted coverage. Hosted cold-job
duration, physical touch and production consumer qualification require separate
evidence.

## Native diagram reader restoration

`make ui-test-native-reader-history` exercises three cases in each Chromium,
Firefox and WebKit phone profile, nine cases total. The generated long diagram
reader authors an internal `target="_self"` link: Material preserves this native
same-window navigation while the ordinary link to the same destination retains
instant navigation. Back/Forward must preserve the full URL, exact source and
visible departure link after diagram layout. A delayed owned renderer response
permits real wheel input to cancel deferred position restoration. Its passive
scroll-call observer delegates every original call and never assigns position.

The existing 27 history and 36 diagram cases remain required. The independent
`native-reader-history` group retains the strict three-minute whole-job limit;
actual hosted job metadata qualifies that limit separately from local case
timing. These browser cases do not qualify manual devices, OS keyboard access,
all authored opt-ins, accepted publication profiles or production URLs.

Renderer unit controls run independently of the immutable browser fixture producer.
The three-minute `std / renderer controls / <group>` jobs retain disjoint
source-derived controls. Renderer owns all native Node units and the remaining
installed Python controls. Passive-reader owns the installed passive-reader
reconstruction control; interactive-reports owns the interactive report adapter,
source authority and actual selected/reference reconstruction controls.
Interactive-make-dispatch owns literal argument and prepare/cleanup boundaries;
interactive-make-refusal owns source, configuration and provider refusal controls.
Interactive-make-docs and interactive-make-docs-check each own their actual target's
selected/reference reconstruction, including retained source and public bytes.
Both target-owned cases execute the same complete reconstruction assertions
in separate fixtures.
Each group retains its exact dependency locks, physical runtime before/after
identities, source and workflow. The navigation aggregate independently rederives
the complete disjoint union; failed, skipped, missing or substituted controls
cannot green the report.

For local full qualification after the normal locked runtime installers:

```sh
python3 tests/bijux-docs/execution/renderer_controls.py run \
  --python artifacts/bijux-docs/python/bin/python --node "$(command -v node)" \
  --output artifacts/bijux-docs/renderer-controls
python3 tests/bijux-docs/execution/renderer_controls.py verify \
  --output artifacts/bijux-docs/renderer-controls
```

CI uses `--group` and a unique group output subtree. All three jobs remain required;
the strict aggregate rejects full local evidence in place of group receipts,
missing or duplicated groups, unknown owners and changed artifacts. A successful
test step inside a cancelled workflow job is never a passing programme gate.
Actual whole-job timing includes setup, execution, upload and cleanup.

These runtime observations confer no publication-profile approval. Browser
fixture, catalogue, fault and publication command gates remain independently
required.
