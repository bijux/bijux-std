# Catalogue source renderer controls

The recipe fixtures retain reviewed source bytes from
`bijux/bijux-masterclass` commit `030558cec92e95905609bb1d11270651a83f23fc`.
Production always captures the consumer's committed originals and matches its
reviewed generator digests; these fixtures are controlled test inputs.

Run recipe/source checkpoint controls with a MkDocs/PyYAML environment:

```sh
"$DOCS_PYTHON" -B -m unittest discover -s tests/bijux-docs/catalogue -p test_recipe_sources.py -v
"$DOCS_PYTHON" -B -m unittest discover -s tests/bijux-docs/catalogue -p test_source_checkpoint.py -v
```

The native and renderer controls additionally require the retained revision-date
plugin and authored extensions:

```sh
"$DOCS_PYTHON" -B -m unittest discover -s tests/bijux-docs/catalogue -p test_native_sources.py -v
"$DOCS_PYTHON" -B -m unittest discover -s tests/bijux-docs/catalogue -p test_renderer_authority.py -v
```

The native Git fixtures use intentionally different author and committer dates.
Checkpoint tests replace only provider acceptance with a declared unit fixture;
they never create an actual accepted standard or publication profile. Renderer
entrypoint and actual consumer reconstruction receipts remain separate evidence.


The required catalogue CI jobs use an independent hash-locked CPython 3.14.4
verification environment. They cover 37 source/checkpoint, 19 native/renderer,
and two complete renderer-entrypoint cases in four bounded groups. The normal
32-package browser renderer and retained historical recipes stay independent.

```sh
make ui-test-install-catalogue ui-test-install-catalogue-default
make ui-test-catalogue
```

Use `UI_CATALOGUE_GROUP=source`, `renderer`, `typed-entrypoint` or
`tracked-entrypoint` for one declared group. Existing catalogue environments
are preserved; select a fresh `UI_CATALOGUE_PYTHON_DIR` under `artifacts/` when
installing another dependency candidate. Receipts retain exact test IDs, source,
physical runtime and lock identity. Any failed, skipped, missing, duplicate or
changed-source execution fails the required report.

The entrypoint fixtures bind their observed physical test runtime to a committed,
explicitly verification-only profile inside their isolated synthetic source.
They assert that publication remains rejected. This exercises the production
entrypoints; it does not add or approve a production/Linux publication profile.

The hosted catalogue jobs select an artifact-owned standalone CPython 3.14.4
through pinned uv 0.11.17. This is a distinct verification runtime; its recipe,
interpreter digest and full physical source/cache checks remain recorded. The
installer preserves existing destinations and rejects alternate download
authorities. It does not delete caches or exempt installed bytecode from the
normal renderer checks. The default32 and historical Canon locks remain unchanged.

```sh
make ui-test-install-catalogue-interpreter
interpreter="$(cat artifacts/bijux-docs/catalogue/interpreter/python-path.txt)"
make ui-test-install-catalogue ui-test-install-catalogue-default UI_CATALOGUE_BASE_PYTHON="$interpreter"
make ui-test-catalogue
```

Actual hosted job durations qualify the recipe; local timings do not prove the
Linux job budget or grant a production publication profile.
