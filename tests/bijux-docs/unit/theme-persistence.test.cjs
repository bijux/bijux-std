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
  const window = { scrollX: 23, scrollY: 127, scrollTo() {}, dispatchEvent() {},
    addEventListener: (name, callback) => events.set(name, callback) };
  if (material) window.__md_set = (key, value) => { writes.push({ key, value }); saved.set(key, value); };
  const document = { body,
    querySelector: () => ({ getAttribute: () => 'bijux:theme' }),
    querySelectorAll: selector => selector.startsWith('input[') ? options : [button] };
  const context = { window, document, localStorage: { getItem: key => saved.get(key) ?? null, setItem: (key, value) => saved.set(key, value) },
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
