const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const {documentFixture, turn} = require('./helpers/diagram-document.cjs');
const source = readFileSync(path.resolve(__dirname, '../../../shared/bijux-docs/scripts/mermaid-init.js'), 'utf8');

function figureParts(fixture) {
  const figure = fixture.figure;
  return {preview: figure.children[0], status: figure.children[1], retry: figure.children[2], details: figure.children[3]};
}

test('rapid theme requests serialize renders, retain authored source and apply only latest theme', async () => {
  const f = documentFixture(source); f.publish(); await turn();
  f.theme('slate'); f.theme('default'); f.theme('slate');
  assert.equal(f.maximum(), 1); assert.equal(f.runs.length, 1);
  const parts = figureParts(f);
  assert.equal(parts.details.querySelector('code').textContent, 'graph TD; A-->B');
  f.runs[0].resolve('<svg>stale default</svg>'); await turn();
  assert.equal(f.runs.length, 2); assert.equal(f.configurations.at(-1).theme, 'dark');
  assert.equal(parts.preview.children.length, 0);
  assert.equal(f.runs[1].source, 'graph TD; A-->B');
  f.runs[1].resolve('<svg>current dark</svg>'); await turn();
  assert.equal(parts.preview.textContent, '<svg>current dark</svg>');
  assert.equal(parts.details.open, false); assert.equal(f.maximum(), 1);
  assert.equal(f.configurations.at(-1).securityLevel, 'strict');
});

test('a replaced document cannot receive a stale render and preserves the new authored source', async () => {
  const f = documentFixture(source); f.publish(); await turn();
  const old = figureParts(f);
  f.replaceDocument(); f.publish();
  f.runs[0].resolve('<svg>stale article</svg>'); await turn();
  assert.equal(old.preview.children.length, 0);
  assert.equal(f.runs.length, 2); assert.equal(f.runs[1].source, 'graph TD; C-->D');
  f.runs[1].resolve(); await turn();
  assert.equal(figureParts(f).details.querySelector('code').textContent, 'graph TD; C-->D');
  assert.equal(f.scripts.length, 1);
});

test('renderer rejection retains readable source and an ordinary retry releases the render lane', async () => {
  const f = documentFixture(source); f.publish(); await turn();
  f.runs[0].reject(); await turn();
  const parts = figureParts(f);
  assert.match(parts.status.textContent, /preview unavailable/);
  assert.equal(parts.details.open, true); assert.equal(parts.retry.hidden, false);
  assert.equal(parts.details.querySelector('code').textContent, 'graph TD; A-->B');
  parts.retry.click(); await turn();
  assert.equal(f.runs.length, 2); assert.equal(f.maximum(), 1);
  f.runs[1].resolve(); await turn();
  assert.equal(parts.details.open, false); assert.equal(parts.retry.hidden, true);
});

test('an empty page never requests the vendor or calls its renderer', async () => {
  const f = documentFixture(source, {empty: true}); f.publish(); await turn();
  assert.equal(f.scripts.length, 0); assert.equal(f.runs.length, 0);
});

test('missing vendor leaves readable source and a retry reloads the admitted asset', async () => {
  const f = documentFixture(source, {vendor: false}); f.publish(); await turn();
  const parts = figureParts(f);
  assert.equal(f.runs.length, 0); assert.equal(parts.details.open, true);
  assert.match(parts.status.textContent, /preview unavailable/);
  f.vendorAvailable = true; parts.retry.click(); await turn();
  assert.equal(f.scripts.length, 2); assert.equal(f.runs.length, 1);
  f.runs[0].resolve(); await turn(); assert.equal(parts.details.open, false);
});

test('theme rerender never uses rendered SVG text as source and pagehide invalidates late completion', async () => {
  const f = documentFixture(source); f.publish(); await turn();
  f.runs[0].resolve('<svg>renderer-owned labels</svg>'); await turn();
  const parts = figureParts(f);
  f.theme('slate'); await turn();
  assert.equal(f.runs[1].source, 'graph TD; A-->B');
  f.pagehide(); f.runs[1].resolve('<svg>late result</svg>'); await turn();
  assert.equal(parts.preview.textContent, '<svg>renderer-owned labels</svg>');
  assert.equal(parts.details.querySelector('code').textContent, 'graph TD; A-->B');
});
