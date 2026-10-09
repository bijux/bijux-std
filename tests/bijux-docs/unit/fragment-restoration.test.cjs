const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.resolve(__dirname, '../../../shared/bijux-docs/tooling/material/fragment-restoration.js'), 'utf8');

function fixture({ href = 'https://example.test/docs/#target', id = 'target', named = false, focusable = false, authoredTabIndex = null } = {}) {
  const calls = [];
  const document = { activeElement: null };
  const attributes = new Map();
  const listeners = new Map();
  if (authoredTabIndex !== null) attributes.set('tabindex', authoredTabIndex);
  const target = {
    tagName: 'A', isConnected: true, parentElement: null,
    getAttribute(name) { return attributes.get(name) ?? null; },
    setAttribute(name, value) { attributes.set(name, value); calls.push(['set', name, value]); },
    removeAttribute(name) { attributes.delete(name); calls.push(['remove', name]); },
    scrollIntoView() { calls.push(['scroll']); },
    focus(options) { calls.push(['focus', options.preventScroll]); if (focusable || attributes.has('tabindex')) document.activeElement = this; },
    addEventListener(name, handler) { listeners.set(name, handler); },
    removeEventListener(name, handler) { if (listeners.get(name) === handler) listeners.delete(name); },
    blur() { calls.push(['blur']); document.activeElement = null; listeners.get('blur')?.(); },
  };
  document.getElementById = value => !named && value === id ? target : null;
  document.getElementsByName = value => named && value === id ? [target] : [];
  const context = vm.createContext({ URL, Event, location: { href }, document });
  vm.runInContext(source, context);
  return { context, document, target, attributes, calls, restore: hash => context.__bijuxScrollCurrentFragment(hash) };
}

for (const [name, id, hash] of [
  ['ordinary ID', 'target', '#target'],
  ['encoded nonASCII ID', 'target-α', '#target-%CE%B1'],
  ['malformed encoded literal', '%Q', '#%Q'],
]) test(name, () => {
  const f = fixture({ href: 'https://example.test/docs/' + hash, id });
  f.restore(hash);
  assert.equal(f.calls.filter(call => call[0] === 'scroll').length, 1);
  assert.equal(f.context.location.href, 'https://example.test/docs/' + hash);
});

test('native named anchor fallback', () => { const f = fixture({ named: true }); f.restore('#target'); assert.equal(f.calls[0][0], 'scroll'); });
test('named input is not a legacy fragment target', () => { const f = fixture({ named: true }); f.target.tagName = 'INPUT'; f.restore('#target'); assert.deepEqual(f.calls, []); });
test('Back has revoked the obsolete fragment', () => { const f = fixture({ href: 'https://example.test/docs/' }); f.restore('#target'); assert.deepEqual(f.calls, []); });
test('another current fragment is not replaced', () => { const f = fixture({ href: 'https://example.test/docs/#other' }); f.restore('#target'); assert.deepEqual(f.calls, []); });
test('missing current target performs no action', () => { const f = fixture(); f.document.getElementById = () => null; f.restore('#target'); assert.deepEqual(f.calls, []); });
test('focusable target receives native focus without attributes', () => { const f = fixture({ focusable: true }); f.restore('#target'); assert.equal(f.document.activeElement, f.target); assert.equal(f.attributes.size, 0); assert.ok(!f.calls.some(call => call[0] === 'set')); });
test('nonfocusable target retains only a negative focus lease until blur', () => { const f = fixture(); f.restore('#target'); assert.equal(f.document.activeElement, f.target); assert.equal(f.attributes.get('tabindex'), '-1'); f.target.blur(); assert.equal(f.attributes.size, 0); assert.equal(f.document.activeElement, null); });
test('authored negative tabindex remains unchanged', () => { const f = fixture({ authoredTabIndex: '-1' }); f.restore('#target'); assert.equal(f.attributes.get('tabindex'), '-1'); assert.equal(f.document.activeElement, f.target); assert.ok(!f.calls.some(call => call[0] === 'remove')); });
test('until-found reveals only after beforematch', () => { const f = fixture(); let hidden = 'until-found'; const seen = []; f.target.parentElement = { tagName: 'DIV', parentElement: null, getAttribute() { return hidden; }, dispatchEvent(event) { seen.push([event.type, event.bubbles, hidden]); }, removeAttribute(name) { seen.push(['remove', name]); hidden = null; } }; f.restore('#target'); assert.deepEqual(seen, [['beforematch', true, 'until-found'], ['remove', 'hidden']]); });
test('beforematch route change revokes focus and scrolling', () => { const f = fixture(); f.target.parentElement = { tagName: 'DIV', parentElement: null, getAttribute() { return 'until-found'; }, dispatchEvent() { f.context.location.href = 'https://example.test/other/'; }, removeAttribute() {} }; f.restore('#target'); assert.deepEqual(f.calls, []); });
test('closed nested disclosures open before target focus', () => { const f = fixture(); const outer = { tagName: 'DETAILS', open: false, children: [], parentElement: null, getAttribute() { return null; } }; const inner = { tagName: 'DETAILS', open: false, children: [], parentElement: outer, getAttribute() { return null; } }; f.target.parentElement = inner; f.restore('#target'); assert.equal(inner.open, true); assert.equal(outer.open, true); });
test('visible first summary does not expand its disclosure', () => { const f = fixture(); f.target.parentElement = { tagName: 'DETAILS', open: false, parentElement: null, children: [{ tagName: 'SUMMARY', contains(node) { return node === f.target; } }], getAttribute() { return null; } }; f.restore('#target'); assert.equal(f.target.parentElement.open, false); });
test('plain hidden content is not changed to until-found', () => { const f = fixture(); f.target.parentElement = { tagName: 'DIV', parentElement: null, getAttribute() { return 'hidden'; }, removeAttribute() { throw Error('ordinary hidden must remain owned'); } }; f.restore('#target'); assert.equal(f.target.parentElement.getAttribute('hidden'), 'hidden'); });
test('disconnected target is not scrolled or focused', () => { const f = fixture(); f.target.isConnected = false; f.restore('#target'); assert.deepEqual(f.calls, []); });
test('authored focus callback can retain its own tabindex', () => {
  const f = fixture();
  const focus = f.target.focus.bind(f.target);
  f.target.focus = options => { focus(options); if (f.document.activeElement === f.target) f.target.setAttribute('tabindex', '0'); };
  f.restore('#target');
  assert.equal(f.attributes.get('tabindex'), '0');
  assert.equal(f.document.activeElement, f.target);
});
test('blur does not erase an authored successor tabindex', () => { const f = fixture(); f.restore('#target'); f.target.setAttribute('tabindex', '0'); f.target.blur(); assert.equal(f.attributes.get('tabindex'), '0'); });
test('failed focus immediately releases its listener and attribute', () => { const f = fixture(); f.target.focus = () => {}; f.restore('#target'); assert.equal(f.attributes.size, 0); assert.equal(f.document.activeElement, null); });
test('empty or nonfragment restoration cannot select a target', () => { const f = fixture(); f.restore(''); f.restore('target'); assert.deepEqual(f.calls, []); });
