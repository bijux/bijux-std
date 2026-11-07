# Node workspace Make contract

The `node` capability supplies `workspace.mk`; `common` continues to own generic
Make, checks and GitHub governance. Set `BIJUX_MAKE_COMPONENTS := node` before
including `.bijux/shared/bijux-makes/bijux.mk` in the consumer's Make entry point. The private root must use an npm workspace array,
a committed lockfile and Node 22 or later.

`node-install` uses `npm ci`. `node-build` and `node-test` invoke repository-owned
npm scripts. `node-check` requires `check:workspace` and `check:types`; those
scripts own package ordering, dependency/public-export validation and declaration
checks. Product semantics and supported runtime matrices remain product-owned.
These targets do not publish, deploy, refresh a lockfile or reserve npm names.

All default caches, logs and temporary files live under root `artifacts/`.
Selected capabilities are synchronized from an exact accepted GitHub source;
consumer copies must not be hand-edited.
