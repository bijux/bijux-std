# Browser qualification shards

Unselected configs retain the complete engine matrix. `BIJUX_UI_BROWSER_ENGINE`
selects one of `chromium`, `firefox`, or `webkit`. `BIJUX_UI_PROJECTS` selects an
exact comma-separated set of configured project names. They are mutually
exclusive. A selection remains an assigned shard, never a complete qualification.
Keep `BIJUX_UI_FULL_GATE=1` for each shard. Playwright `--project` alone is a
diagnostic filter and does not replace the explicit assigned contract.

Produce an independent canonical inventory before splitting a suite:

```sh
node tests/bijux-docs/reporting/inventory.js \
  --config tests/bijux-docs/playwright.navigation.config.js \
  --output artifacts/bijux-docs/inventory/navigation.json
```

The inventory records actual collected case IDs, canonical project counts,
producer source digests, and the verified rendered fixture manifest. Point
`BIJUX_GENERATED_ROOT` to the suite's generated fixtures. Contrast uses its
explicit contrast fixture manifest; its bundle need not equal other suites.

Run each engine against the same source and fixture with a separate
`BIJUX_UI_ARTIFACT_ROOT`. Each shard must execute all its assigned cases with zero
skips, failures and retries. Every case records the actual engine version. After
all reporters finish, the strict receipt binds the actual Playwright JUnit file
and checks source and fixture stability. A runner success alone is insufficient;
the aggregate gate must also succeed:

```sh
python3 tests/bijux-docs/reporting/aggregate.py \
  --inventory artifacts/bijux-docs/inventory/navigation.json \
  --report artifacts/bijux-docs/chromium/qualification.json \
  --report artifacts/bijux-docs/firefox/qualification.json \
  --report artifacts/bijux-docs/webkit/qualification.json \
  --output artifacts/bijux-docs/qualification.json
```

Repeat `--inventory` for every required suite and `--report` for every assigned
shard. The caller owns the required suite set: omitting an inventory does not
prove that suite. The aggregate rejects incomplete coverage, unknown or duplicate
cases/projects, incompatible source or scope-specific bundles, ambiguous engine
versions, and missing, changed or inconsistent JUnit evidence. It uses Python's
standard XML parser, requiring no extra package. Retain inventory contracts,
receipts, JUnit files and the aggregate output together when transferring CI
artifacts; JUnit paths must still resolve at aggregation time.

Headless browser evidence does not replace physical mobile, actual zoom or human
assistive review, and live URL inventories retain an unverified deployment claim.
