# Bijux shell JavaScript ownership

The scripts implement one shared shell over server-rendered MkDocs navigation.
`config/mkdocs-baseline.json` declares their execution order. Product scripts are
retained as authored additions; they do not replace a shared controller.

| Source | Responsibility | Lifetime |
| --- | --- | --- |
| `theme-persistence.js` | Fixed cross-project palette choice, bounded storage fallback, admitted Material palette index and theme notifications. | Window storage binding; palette options bind when mounted. |
| `viewport-profile.js` | CSS-viewport classification and read-only viewport observations. | Once per window; emits on profile changes. |
| `nav-state.js` | Current product/site path normalization and active-link state. | Reads current server-rendered document on coordinated mounts. |
| `detail-tabs.js` | Header detail-strip visibility and active state from authored destinations. | Coordinated document mount; course-strip selectors are retained compatibility. |
| `nav-reveal.js` | Local scroll reveal for active navigation, using logical geometry. | Coordinated mount; `runPhoneNavigationSync` delegates to the same reveal function and `bindMobileDrawerReveal` remains a compatibility no-op. |
| `search-recovery.js` | Named failure/loading feedback, keyboard Retry, native result visibility and query preservation. | Document signal owns listeners and temporary hidden/inert state. Index-ready never overrides worker failure. |
| `bootstrap.js` | Native-label enhancement, compact modal drawer/search interaction, current-document binding and focus intent. | One window coordinator; new `AbortController` per document, previous mount aborted before rebinding. |
| `mermaid-init.js` | Sole strict diagram owner with lazy admitted vendor, preserved source and useful retry. | Serialized render ownership; stale document results cannot commit; theme changes request fresh rendering. |
| `nav-sync.js` | Compatibility entrypoint projected as `assets/javascripts/navigation-sync.js`. | Delegates to the coordinator; contains no second navigation model. |

The admitted Material index/worker adapters live in `tooling/material/`. They own
abortable transport, bounded failure and latest-query scheduling. Native worker
text, ranking, options, and results stay native. Their state/events are a private
protocol with `search-recovery.js`, not a consumer service API.

Bindings apply only to their owned markup. A Material-native header is not a
Bijux drawer mount and must retain its native component behavior without a
Bijux readiness flag. Enhancement readiness is a private successful-mount
result; abort or failed enhancement restores temporary state. Window-level
JavaScript availability is not proof that a specific owner mounted.

Native `<details>/<summary>` and destination anchors are produced by templates.
No script maintains a duplicated phone, scoped, or desktop navigation tree.
Compact drawer modality owns focus containment and temporary background inertness;
close/dispose restores previous state. Window profile/storage listeners bind once.
Material `document$` and ordinary document loading feed the same coordinator;
pagehide/bfcache handling belongs to that coordinator and transport owners.

The [shell contract](../CONTRACT.md) defines public observations, private selectors,
consumer extension points and compatibility retirement requirements. Prefixed
globals, attributes and helper functions do not become public merely by existing.
Never remove a compatibility entrypoint without verified consumer source analysis.
