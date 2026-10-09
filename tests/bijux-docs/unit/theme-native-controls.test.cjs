const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../../shared/bijux-docs/scripts/theme-persistence.js'), 'utf8');

function nativePalette() {
  let init;
  const changes = [];
  const document = { activeElement: null };
  function element(tag, attributes = {}) {
    const values = new Map(Object.entries(attributes));
    const handlers = new Map();
    const node = { tagName: tag.toUpperCase(), dataset: {}, childNodes: ['svg'], textContent: '',
      get id() { return values.get('id'); },
      get attributes() { return [...values].map(([name, value]) => ({name, value})); },
      get hidden() { return values.has('hidden'); },
      set hidden(value) { if(value) values.set('hidden', ''); else values.delete('hidden'); },
      getAttribute: name => values.get(name) ?? null,
      setAttribute: (name, value) => values.set(name, String(value)),
      hasAttribute: name => values.has(name), removeAttribute: name => values.delete(name),
      addEventListener(name, handler) { handlers.set(name, handler); },
      dispatchEvent(event) { handlers.get(event.type)?.(event); },
      replaceChildren(...children) { node.childNodes = children; },
      closest() { return palette; },
      replaceWith(button) { controls[controls.indexOf(node)] = button; },
      focus(options) { document.activeElement = node; node.focusOptions = options; },
    };
    return node;
  }
  const options = ['auto', 'light', 'dark'].map((mode, i) => {
    const node = element('input', { id: '__palette_' + i,
      'data-md-color-media': mode === 'auto' ? '(prefers-color-scheme)' : `(prefers-color-scheme: ${mode})`,
      'data-md-color-scheme': mode === 'dark' ? 'slate' : 'default' });
    let checked = i === 0;
    Object.defineProperty(node, 'checked', { get: () => checked, set(value) {
      if(value) options.forEach(other => { if(other !== node) other.checked = false; }); checked = value;
    }});
    const dispatch = node.dispatchEvent;
    node.dispatchEvent = event => {
      if(event.type === 'change') { changes.push(node.id); controls.forEach((control, index) => { control.hidden = index !== options.indexOf(node); }); }
      dispatch(event);
    };
    return node;
  });
  const controls = options.map((_, i) => element('label', { 'class': 'md-header__button md-icon',
    'title': ['Switch to light mode', 'Switch to dark mode', 'Switch to system mode'][i],
    'for': '__palette_' + ((i + 1) % 3), ...(i ? {hidden: ''} : {}) }));
  const palette = { contains: node => options.includes(node), querySelectorAll: () => controls };
  document.body = element('body');
  document.querySelector = () => null;
  document.querySelectorAll = selector => selector.startsWith('input[') ? options
    : selector.includes('label.md-header__button') ? controls.filter(node => node.tagName === 'LABEL') : [];
  document.createElement = element;
  const stored = new Map();
  const context = { document, location: new URL('https://example.test/reader/'), window: { document$: { subscribe(callback) {init = callback; callback();} },
    dispatchEvent() {}, addEventListener() {}, scrollTo() {}, matchMedia() {return {matches:false};} },
    localStorage: {getItem:key => stored.get(key) ?? null,setItem:(key,value) => stored.set(key,value)},
    Event: class { constructor(type) {this.type = type;} },
    CustomEvent: class { constructor(type, data) {this.type = type;this.detail = data.detail;} },
    requestAnimationFrame: callback => callback(),setTimeout: callback => callback() };
  vm.runInNewContext(source, context, {timeout:1000});
  return {controls, options, changes, document, stored, init: () => init()};
}

test('native palette upgrades preserve targets, labels, visibility and idempotence', () => {
  const page = nativePalette();
  assert.deepEqual(page.controls.map(node => node.tagName), ['BUTTON','BUTTON','BUTTON']);
  for(const [i, button] of page.controls.entries()) {
    assert.equal(button.type, 'button');
    assert.equal(button.getAttribute('for'), '__palette_' + ((i + 1) % 3));
    assert.equal(button.getAttribute('aria-controls'), button.getAttribute('for'));
    assert.equal(button.getAttribute('aria-label'), button.getAttribute('title'));
    assert.equal(button.hidden, i !== 0);
    assert.deepEqual(button.childNodes, ['svg']);
  }
  const identities = [...page.controls];page.init();
  assert.deepEqual(page.controls, identities);
});

test('activation selects existing radio and retains focus on next visible control through all modes', () => {
  const page = nativePalette();
  for(const [index, mode] of [[1,'light'],[2,'dark'],[0,'auto']]) {
    const button = page.controls.find(node => !node.hidden);button.focus();
    button.dispatchEvent({type:'click'});
    assert.equal(page.options[index].checked,true);
    assert.equal(page.document.activeElement,page.controls[index]);
    assert.equal(page.document.activeElement.hidden,false);
    assert.equal(JSON.parse(page.stored.get('bijux:theme')).mode,mode);
  }
  assert.deepEqual(page.changes,['__palette_1','__palette_2','__palette_0']);
});

test('native Enter activation blocks only the competing Material hidden-radio key handler', () => {
  const page = nativePalette();let stopped = 0;
  page.controls[0].dispatchEvent({type:'keydown',key:'Enter',stopPropagation(){stopped++;}});
  page.controls[0].dispatchEvent({type:'keydown',key:' ',stopPropagation(){stopped++;}});
  assert.equal(stopped,1);assert.deepEqual(page.changes,[]);
});

test('detached radio cannot mutate preferences or steal focus', () => {
  const page = nativePalette();const button = page.controls[0];button.focus();
  page.options.splice(1,1);const before = page.stored.get('bijux:theme');
  button.dispatchEvent({type:'click'});
  assert.deepEqual(page.changes,[]);assert.equal(page.stored.get('bijux:theme'),before);
  assert.equal(page.document.activeElement,button);
});

test('pointer activation preserves focus outside the palette', () => {
  const page = nativePalette();const reader = {};page.document.activeElement = reader;
  page.controls[0].dispatchEvent({type:'click'});
  assert.equal(page.options[1].checked,true);assert.equal(page.document.activeElement,reader);
});


test('pointer activation continues prior control focus when native mousedown blurs it', () => {
  const page = nativePalette();const button = page.controls[0];button.focus();
  button.dispatchEvent({type:'pointerdown'});page.document.activeElement = page.document.body;
  button.dispatchEvent({type:'click',detail:1});
  assert.equal(page.document.activeElement,page.controls[1]);
  assert.equal(page.document.activeElement.hidden,false);
});

test('pointer continuation never takes focus from a different reader control', () => {
  const page = nativePalette();const button = page.controls[0];button.focus();
  button.dispatchEvent({type:'pointerdown'});const reader = {};page.document.activeElement = reader;
  button.dispatchEvent({type:'click',detail:1});
  assert.equal(page.document.activeElement,reader);assert.equal(page.options[1].checked,true);
});

test('cancelled or non-pointer activation cannot reuse a prior pointer focus intent', () => {
  for(const cancelled of [true,false]) {
    const page = nativePalette();const button = page.controls[0];button.focus();
    button.dispatchEvent({type:'pointerdown'});
    if(cancelled) button.dispatchEvent({type:'pointercancel'});
    page.document.activeElement = page.document.body;
    button.dispatchEvent({type:'click',detail:cancelled ? 1 : 0});
    assert.equal(page.document.activeElement,page.document.body);
  }
});


test('detached pointer target cannot change preference or restore stale focus', () => {
  const page = nativePalette();const button = page.controls[0];button.focus();
  button.dispatchEvent({type:'pointerdown'});page.document.activeElement = page.document.body;
  page.options.splice(1,1);const before = page.stored.get('bijux:theme');
  button.dispatchEvent({type:'click',detail:1});
  assert.deepEqual(page.changes,[]);assert.equal(page.stored.get('bijux:theme'),before);
  assert.equal(page.document.activeElement,page.document.body);
});
