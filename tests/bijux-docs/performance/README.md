# Owned payload transport

Run the finite controlled two-document journey using an exact committed standard
and the existing admitted Node/Playwright/browser runtime:

```sh
node tests/bijux-docs/performance/transport.cjs \
  --source-root "$PWD" --source-sha "$(git rev-parse HEAD)" \
  --engine chromium --encoding gzip \
  --output artifacts/qualification/payload-transport/chromium.json
node --test tests/bijux-docs/performance/transport.test.cjs
```

The runner also accepts Firefox/WebKit and an identity response encoding. Its
finite cache policies are `public, max-age=3600` and `no-store`; a no-store
journey records retransmission and refuses local HTTP cache qualification. The
output and browser scratch directory remain under the selected repository's
`artifacts/`. Reuse installed admitted runtimes; this command installs nothing.

The actual committed logo, Mermaid initializer and Mermaid library are served
by the owned HTTP fixture. Fresh isolated contexts measure plain reading and
first diagram delivery. Ordinary links leave the diagram document and return
to a new document in the primed context. An ordinary theme button rerenders
through the real initializer and verifies source-preserving library reuse.
No Playwright route interception or fake renderer participates. The fixture
does not simulate Material instant navigation, BFCache or production routes;
the existing diagram and native-history suites retain those obligations.

Browser response bodies and digests, Resource Timing entries, HTTP response
headers and controlled server body observations are retained separately.
[Resource Timing](https://www.w3.org/TR/resource-timing/#dom-performanceresourcetiming-transfersize)
defines decoded/encoded body sizes and a reported transfer size with estimated
header overhead (the current draft uses 300 bytes). It does not expose actual
header or packet wire bytes. Those remain unobserved here. Masked, missing or
inconsistent body-size observations do not become successful zero-byte payloads.
Local cache reuse requires a new document, a matching decoded response, a zero
reported transfer and no corresponding server response; a zero field alone
does not qualify it. Same-document promise reuse is a separate mechanism.
Memory-versus-disk cache location and revalidation are not certified.

[Playwright routing disables HTTP caching](https://playwright.dev/docs/api/class-browsercontext#browser-context-route),
so positive measurements use request/response observation instead of routes.
[Response body observation](https://playwright.dev/docs/api/class-response#response-body)
and [browser executable selection](https://playwright.dev/docs/api/class-browsertype#browser-type-executable-path)
use the installed admitted Playwright runtime; exact engine/version and selected
executable path are recorded. The no-diagram horizon ends after document load
plus 350 ms. Native rendering waits retain 10-second bounds and the producer's
own timeout/fallback behavior.

`transport-evidence.cjs` owns finite observation qualification,
`transport-server.cjs` owns cache/encoding responses and deliberate fault
controls, and `transport.cjs` owns browser lifetime and the callable/CLI journey.
`transport.test.cjs` exercises refusals and real controlled HTTP responses.
Failed actions retain browser/server observations before closure. No result
passes while the browser or server remains active. These measurements introduce
no mobile throttle preset, timing ceiling, field certification or optimization.

## Repeated constrained viewport lab

```sh
node tests/bijux-docs/performance/lab.cjs \
  --source-root "$PWD" --source-sha "$(git rev-parse HEAD)" --samples 3 \
  --output artifacts/qualification/payload-mobile-lab/chromium.json
node --test tests/bijux-docs/performance/lab.test.cjs
```

The named `constrained-phone-viewport` profile uses Chromium at 390×844 CSS
pixels, DPR 1, touch enabled and **`isMobile:false`**. It is a desktop engine with
a phone-shaped viewport, not a physical or named mobile device. The unchanged
owned fixture has no mobile viewport metadata. CPU slowdown is 4; network
latency is 150 ms, download 200,000 B/s and upload 93,750 B/s. Exact source assets,
served document bytes, profile, installed browser/version and host are recorded.
Every sample starts an independent context, clears its cache, then retains a
cold load and warm new-document reload. Cache remains enabled for warm reuse.

[Chromium CDP](https://chromedevtools.github.io/devtools-protocol/) supplies
`Emulation.setCPUThrottlingRate`, `Network.emulateNetworkConditionsByRule` and
`Network.overrideNetworkState`; each requested setting and acknowledgement is
retained. Unsupported commands fail with evidence. [Playwright CDP sessions](https://playwright.dev/docs/api/class-browsercontext#browser-context-new-cdp-session)
are Chromium-specific; this profile does not certify Firefox/WebKit emulation.

Observers are installed before document scripts. [LCP](https://www.w3.org/TR/largest-contentful-paint/)
retains candidate timing and element attribution; the reported lab value is the
latest observed candidate. [Unexpected layout shifts](https://wicg.github.io/layout-instability/)
retain raw values and recent-input flags. The bounded [CLS session-window value](https://web.dev/articles/cls)
uses the maximum window with gaps under one second and duration under five
seconds, excluding recent-input shifts. [Long tasks](https://www.w3.org/TR/longtasks-1/)
retain durations/attribution, count, maximum and sum. These are observed task
costs, not total CPU or field interaction latency. Unsupported, dropped or
missing required observations remain unknown and fail qualification.

The observation ends 1,000 ms after actual load/render readiness. Three to ten
independent sample pairs per route retain individual values, minimum/maximum,
mean/median, standard deviation and explicitly labelled nearest-rank lab p75.
These distributions are not field populations or field INP. No timing ceiling
is invented. The real plain/diagram fixture has the same limited production,
Material and native-history scope as transport accounting. Its initial render
bounds and producer fallback remain unchanged.

## Shared reader interaction observations

```sh
node tests/bijux-docs/performance/interaction.cjs \
  --source-root "$PWD" --source-sha "$(git rev-parse HEAD)" \
  --fixture-dir artifacts/qualification/payload-reader-interaction/site \
  --fixture-manifest artifacts/qualification/payload-reader-interaction/fixture.json \
  --fixture-manifest-sha256 '<externally verified full manifest digest>' --cycles 3 \
  --output artifacts/qualification/payload-reader-interaction/chromium.json
node --test tests/bijux-docs/performance/interaction.test.cjs
```

This runner selects a retained canonical long-registry slice, serves its exact
112 files and 32 HTML routes, and binds all 53 selected shared shell source
inputs to the committed standard. The pinned fixture manifest retains accepted
source/tree/origin, complete site bytes/digests, original generator manifest,
configuration assertion and MkDocs/Material toolchain. When the physical
configuration is unavailable, the report says it was not reread; the original
producer assertion does not become a new physical verification. Current tool
source and historical accepted fixture provenance remain separate.

The same declared Chromium profile applies to an initially cold isolated
context. Three to ten cycles use ordinary clicks, Tab traversal, Enter/Space,
typing, Clear and Escape on the real shared drawer, disclosure and search.
Search must produce the latest full known-answer query and authored destination.
The existing drawer/search, diagram and native-history suites retain their
broader obligations; this runner changes none of their inputs or assertions.
Later cycles use the same loaded document, without claiming warm HTTP delivery.

[Event Timing](https://www.w3.org/TR/event-timing/) entries correlate with
captured trusted inputs and retain input delay, processing time, interaction
identity and estimated next-rendering-update duration. Browser durations are
rounded to 8 ms; the observer requests the minimum 16 ms threshold. Missing,
unsupported, dropped, invalid or below-threshold observations remain unknown.
Functional state/geometry qualification is separate from complete EventTiming
coverage. Incomplete required timing coverage produces an incomplete result
and a nonzero CLI exit, retaining partial distributions without fabricating
zeros. These finite lab samples do not measure field INP.

The observer records the first two matching animation-frame states, focus,
inert ownership, rectangles and pointer-center ownership. The elapsed time from
trusted input to the first matching frame is a **rendering opportunity**, not
actual pixel paint. [Paint Timing](https://www.w3.org/TR/paint-timing/) describes
rendering updates; an animation-frame callback alone does not prove pixels were
presented. Asynchronous native-search result readiness also remains distinct
from an EventTiming entry's next-update duration. No latency ceiling is added.

`interaction-server.cjs` owns finite source/bundle selection and unchanged
HTTP bodies; `interaction-observer.cjs` owns passive capture and rendering
opportunity observations; `interaction-evidence.cjs` owns exact named
transition qualification and partial distributions. `interaction.cjs` owns
ordinary browser input, emulation and terminal lifetime. No positive request
routing, source rewriting, fake renderer or production publication participates.
