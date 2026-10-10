const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { test } = require('node:test');
const { Subject, debounceTime, VirtualTimeScheduler } = require('rxjs');
const source = fs.readFileSync(path.resolve(__dirname, '../../../shared/bijux-docs/tooling/material/viewport-history.js'), 'utf8');

function fixture({ navigation = true, state = { owner: 'retained', x: 0, y: 0 } } = {}) {
  const handlers = new Map(), viewport = new Subject(), scheduler = new VirtualTimeScheduler();
  const writes = [], microtasks = [];
  const listen = owner => ({ addEventListener(name, callback) { handlers.set(owner + ':' + name, callback); } });
  const window = listen('window'), document = listen('document');
  if (navigation) window.navigation = listen('navigation');
  const history = { state, replaceState(value, title) { this.state = value; writes.push({ value: JSON.parse(JSON.stringify(value)), title }); } };
  const context = vm.createContext({ window, document, history, URL,
    location: { href: 'https://example.test/reader/', origin: 'https://example.test', pathname: '/reader/', search: '' },
    queueMicrotask(callback) { microtasks.push(callback); } });
  vm.runInContext(source, context);
  context.__bijuxWatchViewportHistory(() => viewport.pipe(debounceTime(100, scheduler)));
  return { writes, viewport, history, scheduler,
    emit(offset) { viewport.next({ offset }); },
    advance(time) { scheduler.maxFrames = time; scheduler.flush(); },
    event(owner, name, fields = {}) { handlers.get(owner + ':' + name)?.({ isTrusted: true, ...fields }); },
    flushMicrotasks() { for (const callback of microtasks.splice(0)) callback(); } };
}

test('native debounce retains latest actual x/y and foreign reader state', () => {
  const f = fixture(); f.emit({ x: 1, y: 2 }); f.emit({ x: 3, y: 4 }); f.advance(99);
  assert.deepEqual(f.writes, []); f.advance(100);
  assert.deepEqual(f.writes, [{ value: { owner: 'retained', x: 3, y: 4 }, title: '' }]);
});
test('cross-document native departure cancels actual pending RxJS timer', () => {
  const f = fixture(); f.emit({ x: 1, y: 2 });
  f.event('navigation', 'navigate', { destination: { sameDocument: false } }); f.advance(1000);
  assert.deepEqual(f.writes, []); assert.equal(f.viewport.observed, false);
});
test('same-document instant and hash navigation retains the native subscription', () => {
  const f = fixture(); f.emit({ x: 1, y: 2 });
  f.event('navigation', 'navigate', { destination: { sameDocument: true } }); f.advance(100);
  assert.equal(f.writes.length, 1); assert.equal(f.viewport.observed, true);
});
test('trusted cached lifecycle cancels the old generation and resumes only fresh offsets', () => {
  const f = fixture(); f.emit({ x: 1, y: 2 }); f.event('window', 'pagehide', { persisted: true });
  f.advance(100); assert.deepEqual(f.writes, []);
  f.event('window', 'pageshow', { persisted: true }); f.emit({ x: 5, y: 6 }); f.advance(200);
  assert.deepEqual(f.writes[0].value, { owner: 'retained', x: 5, y: 6 });
});
test('final or synthetic pageshow cannot reactivate a retired document', () => {
  const f = fixture(); f.event('window', 'pagehide', { persisted: false });
  f.event('window', 'pageshow', { persisted: false }); f.event('window', 'pageshow', { persisted: true, isTrusted: false });
  f.emit({ x: 1, y: 2 }); f.advance(1000); assert.deepEqual(f.writes, []);
});
test('duplicate persisted pageshow never duplicates the viewport subscription', () => {
  const f = fixture(); f.event('window', 'pagehide', { persisted: true });
  f.event('window', 'pageshow', { persisted: true }); f.event('window', 'pageshow', { persisted: true });
  f.emit({ x: 1, y: 2 }); f.advance(100); assert.equal(f.writes.length, 1);
});
test('cancelled native departure resumes the active document without retired work', () => {
  const f = fixture(); f.emit({ x: 1, y: 2 });
  f.event('navigation', 'navigate', { destination: { sameDocument: false }, defaultPrevented: true });
  f.flushMicrotasks(); f.emit({ x: 5, y: 6 }); f.advance(100);
  assert.deepEqual(f.writes[0].value, { owner: 'retained', x: 5, y: 6 });
});
test('asynchronously aborted native navigation restores the still active document', () => {
  const f = fixture(), controller = new AbortController(); f.emit({ x: 1, y: 2 });
  f.event('navigation', 'navigate', { destination: { sameDocument: false }, signal: controller.signal });
  f.flushMicrotasks(); f.advance(100); assert.deepEqual(f.writes, []);
  controller.abort(); f.emit({ x: 5, y: 6 }); f.advance(200); assert.equal(f.writes[0].value.y, 6);
});
test('superseded or cached departure cannot be resumed by an older navigation abort', () => {
  for (const boundary of ['new-departure', 'pagehide']) {
    const f = fixture(), controller = new AbortController();
    f.event('navigation', 'navigate', { destination: { sameDocument: false }, signal: controller.signal });
    f.flushMicrotasks();
    if (boundary === 'pagehide') f.event('window', 'pagehide', { persisted: true });
    else f.event('navigation', 'navigate', { destination: { sameDocument: false }, signal: new AbortController().signal });
    controller.abort(); f.emit({ x: 1, y: 2 }); f.advance(1000); assert.deepEqual(f.writes, []);
    assert.equal(f.viewport.observed, false);
  }
});
test('native explicit same-window link cancels work without Navigation API', () => {
  const f = fixture({ navigation: false }); f.emit({ x: 1, y: 2 });
  f.event('document', 'click', { button: 0, target: { closest() { return { href: 'https://example.test/table/', hasAttribute() { return false; } }; } } });
  f.advance(100); assert.deepEqual(f.writes, []);
});
test('same-document fallback link and modifier defaults preserve current offset work', () => {
  for (const fields of [{ href: 'https://example.test/reader/#source' }, { href: 'https://example.test/table/', ctrlKey: true }]) {
    const f = fixture({ navigation: false }); f.emit({ x: 1, y: 2 });
    f.event('document', 'click', { button: 0, ctrlKey: fields.ctrlKey, target: { closest() { return { href: fields.href, hasAttribute() { return false; } }; } } });
    f.advance(100); assert.equal(f.writes.length, 1);
  }
});
test('foreign non-object history state is never replaced by viewport ownership', () => {
  for (const state of ['authored', [1], 3]) {
    const f = fixture({ state }); f.emit({ x: 1, y: 2 }); f.advance(100);
    assert.deepEqual(f.writes, []); assert.equal(f.history.state, state);
  }
});
test('malformed fallback href preserves ordinary native viewport work', () => {
  const f = fixture({ navigation: false }); f.emit({ x: 1, y: 2 });
  f.event('document', 'click', { button: 0, target: { closest() { return { href: 'https://[invalid', hasAttribute() { return false; } }; } } });
  f.advance(100); assert.equal(f.writes.length, 1);
});
