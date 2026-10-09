const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../../..');
const themeSource = fs.readFileSync(process.env.BIJUX_THEME_READER_SOURCE || path.join(root, 'shared/bijux-docs/scripts/theme-persistence.js'), 'utf8');
const diagramSource = fs.readFileSync(path.join(root, 'shared/bijux-docs/scripts/mermaid-init.js'), 'utf8');
const href = 'https://example.test/reader/';
const savedY = 8840;
const nativeY = 8074.58349609375;

function reader({ type = 'back_forward', saved = { version: 2, mode: 'light' } } = {}) {
  const frames = [], timers = [], scrolls = [], subscriptions = [], events = new Map();
  const attributes = new Map([['data-md-color-scheme', 'default']]);
  const stored = new Map([['bijux:theme', typeof saved === 'string' ? saved : JSON.stringify(saved)]]);
  const listen = (owner, name, handler) => {
    const key = owner + ':' + name;
    events.set(key, [...(events.get(key) || []), handler]);
  };
  let options = [];
  options = ['auto', 'light', 'dark'].map(mode => {
    const values = new Map([['data-md-color-media', mode === 'auto' ? '(prefers-color-scheme)' : `(prefers-color-scheme: ${mode})`],
      ['data-md-color-scheme', mode === 'dark' ? 'slate' : 'default'], ['data-md-color-primary', 'teal'], ['data-md-color-accent', 'cyan']]);
    const handlers = new Map();
    const option = { dataset: {}, selected: false, getAttribute: name => values.get(name) ?? null,
      addEventListener: (name, handler) => handlers.set(name, handler), dispatchEvent: event => handlers.get(event.type)?.(event) };
    Object.defineProperty(option, 'checked', {get: () => option.selected, set: value => {
      if (value) options.forEach(other => {other.selected = false;}); option.selected = value;
    }});
    return option;
  });
  const history = { state: { author: 'retained', bijuxDiagramReaderPosition: {owner:'bijux-docs',version:1,href,x:0,y:savedY}},
    replaceState(value) {this.state = value;} };
  const document = { readyState: 'loading', currentScript: {src:'https://example.test/assets/mermaid-init.js'},
    body: {getAttribute: name => attributes.get(name) ?? null, setAttribute: (name,value) => attributes.set(name,value), removeAttribute: name => attributes.delete(name)},
    querySelector: selector => selector.includes('bijux-diagram') ? {} : null,
    querySelectorAll: selector => selector.startsWith('input[') ? options : [],
    addEventListener: (name, handler) => listen('document',name,handler) };
  const window = {scrollX:0,scrollY:nativeY,document$:{subscribe:callback=>subscriptions.push(callback)},
    addEventListener:(name,handler)=>listen('window',name,handler),
    dispatchEvent:event=>{for(const handler of events.get('window:'+event.type)||[])handler(event);},
    scrollTo(...args) {const value=args[0];this.scrollX=typeof value==='object'?value.left:args[0];this.scrollY=typeof value==='object'?value.top:args[1];scrolls.push({x:this.scrollX,y:this.scrollY});} };
  const context=vm.createContext({window,document,history,location:new URL(href),URL,WeakMap,Promise,
    performance:{getEntriesByType:()=>[{type}]},localStorage:{getItem:name=>stored.get(name)??null,setItem:(name,value)=>stored.set(name,value)},
    CustomEvent:class {constructor(type,details){this.type=type;this.detail=details.detail;}},Event:class {constructor(type){this.type=type;}},
    requestAnimationFrame:callback=>frames.push(callback),setTimeout:callback=>{timers.push(callback);return timers.length;},clearTimeout(){} });
  // Complete the actual owned diagram callback at a controlled scheduling boundary,
  // using the same source seam as the maintained native-history unit contracts.
  const observed=diagramSource.replace(/\}\)\(\);\s*$/,'window.completeOwnedDiagramLayout = () => restoreReaderPosition(generation);})();');
  vm.runInContext(observed,context);vm.runInContext(themeSource,context);
  // These palette controls observe layout completion after initial pageshow.
  window.dispatchEvent({type:'pageshow',persisted:false});
  return {window,history,scrolls,options,attributes,
    init:()=>subscriptions[1](),completeDiagram:()=>window.completeOwnedDiagramLayout(),
    flushFrames(){while(frames.length)frames.shift()();},flushTimers(){while(timers.length)timers.shift()();},
    fire(name,event){for(const handler of events.get('window:'+name)||[])handler(event);},
    theme(mode){const option=options[['auto','light','dark'].indexOf(mode)];option.checked=true;option.dispatchEvent({type:'change'});} };
}

test('late startup palette callbacks cannot overwrite completed native Back restoration', () => {
  const page=reader();page.init();page.completeDiagram();page.flushFrames();
  assert.equal(page.window.scrollY,savedY,'Actual owned layout callback reaches saved native reader position');
  page.flushTimers();
  assert.equal(page.window.scrollY,savedY,'Startup preference callbacks must not move an already restored reader');
  const departureLinkDocumentY=savedY+579.13330078125;
  assert.ok(departureLinkDocumentY-page.window.scrollY<900,'Actual departure link stays within the original viewport');
  assert.equal(page.history.state.author,'retained');
});

test('startup palette work cannot reclaim position after trusted reader wheel input', () => {
  const page=reader();page.init();page.completeDiagram();page.fire('wheel',{isTrusted:true});page.window.scrollY=650;
  page.flushFrames();page.flushTimers();assert.equal(page.window.scrollY,650);
});

for (const [name,saved] of [['mode',{version:2,mode:'light'}],['signature',{version:2,mode:'light',signature:{media:'(prefers-color-scheme: light)',scheme:'default',primary:'teal',accent:'cyan'}}],['legacy','slate']]) {
  test(`startup ${name} preference applies palette without becoming scroll owner`,()=>{
    const page=reader({saved});page.init();page.flushFrames();page.flushTimers();
    assert.equal(page.scrolls.length,0);assert.equal(page.attributes.get('data-md-color-scheme'),name==='legacy'?'slate':'default');
  });
}

test('ordinary palette activation still preserves the current reader through layout callbacks',()=>{
  const page=reader();page.init();page.flushFrames();page.flushTimers();page.window.scrollY=650;page.theme('dark');
  assert.equal(page.window.scrollY,650);page.window.scrollY=750;page.flushFrames();assert.equal(page.window.scrollY,650);
  page.window.scrollY=900;page.flushTimers();assert.equal(page.window.scrollY,650);assert.equal(page.attributes.get('data-md-color-scheme'),'slate');
});

test('cross-tab palette activation preserves the current reader independently of startup',()=>{
  const page=reader();page.init();page.flushFrames();page.flushTimers();page.window.scrollY=650;
  page.fire('storage',{key:'bijux:theme',newValue:JSON.stringify({version:2,mode:'dark'})});page.window.scrollY=900;
  page.flushFrames();page.flushTimers();assert.equal(page.window.scrollY,650);assert.equal(page.attributes.get('data-md-color-scheme'),'slate');
});

test('ordinary first-view and native fragment position stay outside startup palette ownership',()=>{
  const page=reader({type:'navigate'});page.init();page.completeDiagram();page.window.scrollY=650;
  page.flushFrames();page.flushTimers();assert.equal(page.window.scrollY,650);
});
