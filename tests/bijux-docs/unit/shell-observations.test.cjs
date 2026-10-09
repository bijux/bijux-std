const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const directory = path.resolve(__dirname, '../../../shared/bijux-docs/scripts');
const source = name => fs.readFileSync(path.join(directory, name), 'utf8');
const EventRecord = class { constructor(type, options = {}) { this.type = type; this.detail = options.detail; } };

function viewport(width = 390) {
  const calls = [], listeners = new Map(), frames = new Map(), timers = new Map();
  const makeTarget = () => ({ attributes: new Map(), getAttribute(key) { return this.attributes.get(key); }, setAttribute(key, value) { this.attributes.set(key, value); } });
  const document = { documentElement: makeTarget(), body: makeTarget(), visibilityState: 'visible', readyState: 'complete' };
  document.documentElement.clientWidth = width;
  let id = 0, mount;
  const window = { innerWidth: width, document$: { subscribe(callback) { mount = callback; callback(); } },
    dispatchEvent(event) { calls.push(event); }, addEventListener(name, callback) { if (!listeners.has(name)) listeners.set(name, []); listeners.get(name).push(callback); },
    requestAnimationFrame(callback) { frames.set(++id, callback); return id; }, cancelAnimationFrame(key) { frames.delete(key); },
    setTimeout(callback) { timers.set(++id, callback); return id; }, clearTimeout(key) { timers.delete(key); } };
  vm.runInNewContext(source('viewport-profile.js'), { window, document, document$: window.document$, CustomEvent: EventRecord, console }, { timeout: 1000 });
  return { window, document, calls, listeners, frames, timers, mount: () => mount(), resize(next) { window.innerWidth = next; document.documentElement.clientWidth = next; window.bijuxViewportProfile.apply(); } };
}

test('viewport observations contain typed initial and changed profiles without same-band duplicates', () => {
  const state = viewport();
  const initial = state.calls[0];
  assert.equal(initial.type, 'bijux:viewport-change');
  assert.deepEqual(JSON.parse(JSON.stringify(initial.detail)), { profile: 'phone', previousProfile: null, width: 390 });
  state.resize(430);
  assert.equal(state.calls.length, 1);
  for (const [width, profile] of [[768, 'normal'], [1280, 'desktop'], [1920, 'wide']]) {
    state.resize(width);
    assert.equal(state.calls.at(-1).detail.profile, profile);
    assert.equal(state.calls.at(-1).detail.width, width);
    assert.equal(state.document.documentElement.getAttribute('data-bijux-viewport'), profile);
    assert.equal(state.document.body.getAttribute('data-bijux-viewport'), profile);
  }
  assert.equal(state.calls.length, 4);
});

test('repeated document mounts keep one profile window binding and restore replacement body attributes', () => {
  const state = viewport(768);
  const resizeBindings = state.listeners.get('resize').length;
  state.document.body.attributes.clear();
  state.mount(); state.mount();
  assert.equal(state.listeners.get('resize').length, resizeBindings);
  assert.equal(resizeBindings, 1);
  assert.equal(state.calls.length, 1);
  assert.equal(state.document.body.getAttribute('data-bijux-viewport'), 'normal');
});

test('pagehide disposes scheduled profile frame and settle work without deleting public observations', () => {
  const state = viewport();
  state.listeners.get('orientationchange')[0]();
  assert.equal(state.frames.size, 1);
  assert.equal(state.timers.size, 1);
  state.listeners.get('pagehide')[0]();
  assert.equal(state.frames.size, 0);
  assert.equal(state.timers.size, 0);
  assert.equal(state.document.body.getAttribute('data-bijux-viewport'), 'phone');
});

function theme() {
  const notices = [], saved = new Map([['bijux:theme', JSON.stringify({ version: 2, mode: 'auto' })]]), bodyAttributes = new Map();
  let mount;
  const options = ['auto', 'light', 'dark'].map(mode => {
    const attributes = { 'data-md-color-media': mode === 'auto' ? '(prefers-color-scheme)' : `(prefers-color-scheme: ${mode})`, 'data-md-color-scheme': mode === 'dark' ? 'slate' : 'default', 'data-md-color-primary': 'teal', 'data-md-color-accent': 'cyan' };
    return { dataset: {}, checked: false, listeners: new Map(), getAttribute(key) { return attributes[key] ?? null; }, addEventListener(name, callback) { this.listeners.set(name, callback); } };
  });
  const window = { document$: { subscribe(callback) { mount = callback; callback(); } }, scrollX: 0, scrollY: 0, scrollTo() {}, matchMedia() { return { matches: true }; }, dispatchEvent(event) { notices.push(event); }, addEventListener() {}, __md_set(key, value) { saved.set(key, value); } };
  const article = {};
  const themeMarker = { getAttribute() { return 'bijux:theme'; } };
  const document = { body: { setAttribute(key, value) { bodyAttributes.set(key, value); }, removeAttribute(key) { bodyAttributes.delete(key); }, getAttribute(key) { return bodyAttributes.get(key); } }, querySelector(selector) { return selector === '.md-content__inner' ? article : themeMarker; }, querySelectorAll(selector) { return selector.startsWith('input[') ? options : []; } };
  vm.runInNewContext(source('theme-persistence.js'), { window, document, location: new URL('https://example.test/reader/'), localStorage: { getItem(key) { return saved.get(key) ?? null; }, setItem(key, value) { saved.set(key, value); } }, CustomEvent: EventRecord, Event: EventRecord, document$: { subscribe(callback) { mount = callback; callback(); } }, requestAnimationFrame(callback) { callback(); }, setTimeout(callback) { callback(); } }, { timeout: 1000 });
  return { notices, options, bodyAttributes, mount: () => mount() };
}

test('auto theme notification reports selected option while body records effective dark scheme', () => {
  const state = theme();
  assert.equal(state.notices[0].type, 'bijux:theme-change');
  assert.equal(state.notices[0].detail.mode, 'auto');
  assert.equal(state.notices[0].detail.scheme, 'default');
  assert.equal(state.bodyAttributes.get('data-md-color-scheme'), 'slate');
});

test('theme consumers receive repeated mount notifications and valid explicit mode changes', () => {
  const state = theme();
  state.mount();
  assert.equal(state.notices.length, 2);
  state.options[2].checked = true;
  state.options[2].listeners.get('change')();
  assert.equal(state.notices.at(-1).detail.mode, 'dark');
  assert.equal(state.notices.at(-1).detail.scheme, 'slate');
});
