const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(process.env.BOOTSTRAP_SOURCE || path.resolve(__dirname, '../../../shared/bijux-docs/scripts/bootstrap.js'), 'utf8');

function nativeHeader() {
  const window = new EventTarget(), document = new EventTarget(), input = new EventTarget(), form = new EventTarget();
  const jobs = new Map(), values = [];
  let job = 0;
  input.value = '';
  input.form = form;
  input.addEventListener('keyup', event => values.push({value: input.value, key: event.key}));
  // The source-default header deliberately has no Bijux custom control selectors.
  document.body = {dataset: {}};
  document.getElementById = () => null;
  document.querySelectorAll = () => [];
  document.querySelector = selector => selector === "[data-md-component='search-query']" ? input : null;
  document.readyState = 'loading';
  window.matchMedia = () => Object.assign(new EventTarget(), {matches: false});
  class KeyboardEvent extends Event { constructor(name, options) { super(name, options); this.key = options.key; } }
  vm.runInNewContext(source, {window, document, AbortController, Event, KeyboardEvent,
    setTimeout(handler) { jobs.set(++job, handler); return job; }, clearTimeout(id) { jobs.delete(id); },
  });
  const bind = () => window.bijuxShell.bootstrap.runShellNavigationSync();
  const drain = () => { for (const [id, handler] of jobs) { jobs.delete(id); handler(); } };
  return {window, document, input, form, jobs, values, bind, drain};
}

test('native header paste/input reaches the unchanged Material keyup observer without custom chrome', () => {
  const f = nativeHeader(); f.bind(); assert.equal(f.document.body.dataset.bijuxDrawerReady, undefined); f.input.value = 'resilient navigation'; f.input.dispatchEvent(new Event('input'));
  assert.deepEqual(f.values, [{value: 'resilient navigation', key: 'Unidentified'}]);
});

test('composition input waits for completion and forwards only the final native query value', () => {
  const f = nativeHeader(); f.bind(); f.input.value = 'resilient';
  const composing = new Event('input'); Object.defineProperty(composing, 'isComposing', {value: true});
  f.input.dispatchEvent(composing); assert.deepEqual(f.values, []);
  f.input.value = 'resilient navigation'; f.input.dispatchEvent(new Event('compositionend'));
  assert.deepEqual(f.values, [{value: 'resilient navigation', key: 'Unidentified'}]);
});

test('native form reset forwards the cleared value in the following task', () => {
  const f = nativeHeader(); f.bind(); f.input.value = 'old query'; f.form.dispatchEvent(new Event('reset'));
  assert.deepEqual(f.values, []); f.input.value = ''; f.drain();
  assert.deepEqual(f.values, [{value: '', key: 'Unidentified'}]);
});

test('document rebinding has one input owner and suspension cancels pending reset work', () => {
  const f = nativeHeader(); f.bind(); f.bind(); f.input.value = 'current'; f.input.dispatchEvent(new Event('input'));
  assert.equal(f.values.length, 1); f.form.dispatchEvent(new Event('reset')); assert.equal(f.jobs.size, 1);
  f.window.dispatchEvent(new Event('pagehide')); assert.equal(f.jobs.size, 0); f.input.dispatchEvent(new Event('input'));
  assert.equal(f.values.length, 1);
});
