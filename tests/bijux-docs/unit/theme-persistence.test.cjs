const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = readFileSync(path.resolve(__dirname, '../../../shared/bijux-docs/scripts/theme-persistence.js'), 'utf8');

function shell(mode = 'auto', order = ['auto', 'light', 'dark'], material = true) {
  const saved = new Map([['bijux:theme', JSON.stringify({ version: 2, mode })]]);
  const writes = [];
  const events = new Map();
  const bodyAttributes = new Map([['data-md-color-scheme', 'default']]);
  let options = [];
  options = order.map(name => {
    const attrs = new Map([
      ['data-md-color-media', name === 'auto' ? '(prefers-color-scheme)' : `(prefers-color-scheme: ${name})`],
      ['data-md-color-scheme', name === 'dark' ? 'slate' : 'default'],
      ['data-md-color-primary', 'teal'], ['data-md-color-accent', 'cyan'],
    ]);
    const option = { dataset: {}, listeners: new Map(), selected: false,
      getAttribute: key => attrs.get(key) ?? null,
      addEventListener: (name, callback) => option.listeners.set(name, callback),
      dispatchEvent: event => option.listeners.get(event.type)?.(event),
    };
    Object.defineProperty(option, 'checked', {
      get: () => option.selected,
      set(value) { if (value) options.forEach(other => { other.selected = false; }); option.selected = value; },
    });
    return option;
  });
  const button = { dataset: {}, hidden: true, attributes: new Map(), listeners: new Map(),
    setAttribute: (key, value) => button.attributes.set(key, value),
    addEventListener: (name, callback) => button.listeners.set(name, callback),
  };
  const body = { getAttribute: key => bodyAttributes.get(key) ?? null,
    setAttribute: (key, value) => bodyAttributes.set(key, value), removeAttribute: key => bodyAttributes.delete(key) };
  const window = { document$: { subscribe(callback) { callback(); } }, scrollX: 23, scrollY: 127, scrollTo() {}, dispatchEvent() {},
    addEventListener: (name, callback) => events.set(name, callback) };
  if (material) window.__md_set = (key, value) => { writes.push({ key, value }); saved.set(key, value); };
  const article = {};
  const themeMarker = { getAttribute: () => 'bijux:theme' };
  const document = { body,
    querySelector: selector => selector === '.md-content__inner' ? article : themeMarker,
    querySelectorAll: selector => selector.startsWith('input[') ? options : selector === '[data-bijux-theme-toggle]' ? [button] : [] };
  const context = { window, document, location: new URL('https://example.test/reader/'), localStorage: { getItem: key => saved.get(key) ?? null, setItem: (key, value) => saved.set(key, value) },
    Event: class { constructor(type) { this.type = type; } },
    CustomEvent: class { constructor(type, details) { this.type = type; this.detail = details.detail; } },
    requestAnimationFrame: callback => callback(), setTimeout: callback => callback(),
    document$: { subscribe(callback) { callback(); } } };
  vm.runInNewContext(source, context, { timeout: 1000 });
  return { saved, writes, options, button, events, bodyAttributes };
}

function materialSelection(result, index) {
  const record = result.saved.get('__palette');
  assert.equal(record.index, index);
  assert.equal(Number.isInteger(record.index), true);
  // Material initializes its palette by indexing these same current radios.
  const selected = result.options[Math.max(0, Math.min(record.index, result.options.length - 1))];
  assert.ok(selected);
  assert.equal(record.color.media, selected.getAttribute('data-md-color-media'));
  assert.equal(record.color.scheme, selected.getAttribute('data-md-color-scheme'));
  assert.equal(record.color.primary, selected.getAttribute('data-md-color-primary'));
  assert.equal(record.color.accent, selected.getAttribute('data-md-color-accent'));
}

for (const [mode, index] of [['auto', 0], ['light', 1], ['dark', 2]]) {
  test(`restoring ${mode} writes Material index and color together`, () => {
    const result = shell(mode);
    materialSelection(result, index);
    assert.equal(result.writes[0].key, '__palette');
  });
}

test('index follows the current radio order across repositories', () => {
  materialSelection(shell('light', ['dark', 'auto', 'light']), 2);
});

test('theme toggle preserves every persisted mode and index through a cycle', () => {
  const result = shell('auto');
  for (const [index, mode] of [[1, 'light'], [2, 'dark'], [0, 'auto']]) {
    result.button.listeners.get('click')();
    materialSelection(result, index);
    assert.equal(JSON.parse(result.saved.get('bijux:theme')).mode, mode);
  }
});

test('radio changes preserve Material and cross-project signatures', () => {
  const result = shell('auto');
  result.options[2].checked = true;
  result.options[2].listeners.get('change')();
  materialSelection(result, 2);
  const shared = JSON.parse(result.saved.get('bijux:theme'));
  assert.equal(shared.version, 2);
  assert.equal(shared.mode, 'dark');
  assert.equal(shared.signature.scheme, 'slate');
});

test('cross-tab restore uses the local palette index', () => {
  const result = shell('auto', ['dark', 'light', 'auto']);
  result.events.get('storage')({ key: 'bijux:theme', newValue: JSON.stringify({ version: 2, mode: 'dark' }) });
  materialSelection(result, 0);
});

test('missing Material writer leaves the shared toggle usable', () => {
  const result = shell('dark', ['auto', 'light', 'dark'], false);
  assert.equal(result.writes.length, 0);
  result.button.listeners.get('click')();
  assert.equal(JSON.parse(result.saved.get('bijux:theme')).mode, 'auto');
});

test('empty palette never writes an invalid Material record', () => {
  assert.equal(shell('dark', []).writes.length, 0);
});

function scopedPreferences(storage) {
  const template = readFileSync(path.resolve(__dirname, '../../../shared/bijux-docs/partials/javascripts/base.html'), 'utf8');
  const script = template.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/\{\{[^}]+\}\}/, '"/"');
  const context = { URL, location: 'https://bijux.io/', window: { localStorage: storage } };
  vm.runInNewContext(script, context, { timeout: 1000 });
  return context;
}

test('denied scoped storage uses bounded memory without breaking Material callers', () => {
  const denied = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } };
  const api = scopedPreferences(denied);
  api.__md_set('__palette', { index: 2, color: { scheme: 'slate' } });
  assert.equal(api.__md_get('__palette').index, 2);
  assert.equal(api.__md_get('missing'), null);
});

test('malformed and oversized scoped records produce an absent preference', () => {
  for (const raw of ['{broken', 'x'.repeat(16385)]) {
    assert.equal(scopedPreferences({ getItem: () => raw }).__md_get('__palette'), null);
  }
  for (const value of [null, { index: -1, color: {} }, { index: 999, color: {} }, { index: 1.5, color: {} }, { index: 1 }]) {
    assert.equal(scopedPreferences({ getItem: () => JSON.stringify(value) }).__md_get('__palette'), null);
  }
});

test('scoped memory evicts old keys and rejects oversized writes', () => {
  const api = scopedPreferences({ getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } });
  for (let index = 0; index < 33; index++) api.__md_set('key' + index, index);
  assert.equal(api.__md_get('key0'), null);
  assert.equal(api.__md_get('key32'), 32);
  api.__md_set('oversized', 'x'.repeat(16385));
  assert.equal(api.__md_get('oversized'), null);
  assert.equal(api.__bijux_memory.size, 32);
});

test('accessible storage removal takes precedence over retained fallback memory', () => {
  const values = new Map();
  const api = scopedPreferences({ getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) });
  api.__md_set('preference', 'stored');
  assert.equal(api.__md_get('preference'), 'stored');
  values.clear();
  assert.equal(api.__md_get('preference'), null);
});

test('explicit storage and scope remain separate from the default Material scope', () => {
  const values = new Map();
  const storage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
  const api = scopedPreferences(storage);
  const scope = new URL('https://bijux.io/product/');
  api.__md_set('preference', 'product', storage, scope);
  assert.equal(values.get('/product/.' + 'preference'), '"product"');
  assert.equal(api.__md_get('preference', storage, scope), 'product');
  assert.equal(api.__md_get('preference'), null);
});
