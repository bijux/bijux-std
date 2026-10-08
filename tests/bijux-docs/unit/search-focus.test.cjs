const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict'), test = require('node:test');
const proposed = path.resolve(__dirname, '../../../shared/bijux-docs/scripts/bootstrap.js');
const source = fs.readFileSync(process.env.BOOTSTRAP_SOURCE || proposed,'utf8');
const begin = source.indexOf('  function bindSearch(signal) {');
const fn = source.slice(begin, source.indexOf('  function runShellNavigationSync() {',begin));
class Node extends EventTarget {
 constructor(tag='DIV'){super();this.tagName=tag;this.attributes=[];this.inert=false;this.children=[];this.parentElement=null;this.checked=false;this.hidden=false;this.tabIndex=0;this.attrs={};}
 setAttribute(name,value){this.attrs[name]=value;}
 removeAttribute(name){delete this.attrs[name];}
 getClientRects(){return this.hidden?[]:[{}];}
 contains(node){return node===this||this.children.includes(node);}
 closest(selector){return selector==='a[href]'&&this.tagName==='A'?this:null;}
 click(){if(this.tagName==='INPUT'){const prior=this.checked;this.checked=!this.checked;const e=new Event('click',{cancelable:true});this.dispatchEvent(e);if(e.defaultPrevented)this.checked=prior;else this.dispatchEvent(new Event('change',{bubbles:true}));return e;}const e=new Event('click',{cancelable:true});this.dispatchEvent(e);return e;}
}
function fixture({inline=false,modal=false}={}){
 const document=new EventTarget(),toggle=new Node('INPUT'),control=new Node('BUTTON'),query=new Node('INPUT'),dialog=new Node(),back=new Node('BUTTON'),background=new Node();
 query.focus=()=>{document.activeElement=query;query.dispatchEvent(new Event("focus"));};control.focus=()=>{document.activeElement=control;};back.focus=()=>{document.activeElement=back;};
 dialog.children=[query,back];dialog.querySelector=selector=>selector.includes('__search')?back:query;dialog.querySelectorAll=()=>[query,back];
 document.getElementById=()=>toggle;document.querySelector=selector=>selector.includes('search-toggle')?control:(selector.includes('search__input')||selector.includes('search-query'))?query:dialog;document.querySelectorAll=()=>[background];
 control.hidden=inline;query.hidden=modal;
 const lifetime=new AbortController();vm.runInNewContext('let closeDrawer; let readingIntent=false;'+fn+'bindSearch(signal);',{document,signal:lifetime.signal,Event,getComputedStyle:()=>({visibility:'visible'})});
 return{document,toggle,control,query,dialog,back,background,lifetime};
}
test('a newer explicit open survives the old native setToggle synthetic click default action',()=>{const f=fixture();f.control.click();assert.equal(f.toggle.checked,true);assert.equal(f.document.activeElement,f.query);const close=f.toggle.click();assert.equal(close.defaultPrevented,true);assert.equal(f.toggle.checked,true);f.lifetime.abort();});
test('a subsequent explicit control close retains its ordinary close behavior',()=>{const f=fixture();f.control.click();f.control.click();assert.equal(f.toggle.checked,false);f.lifetime.abort();});
test('ordinary Escape closes search and returns focus to its opener',()=>{const f=fixture();f.control.click();const e=new Event('keydown',{cancelable:true});Object.defineProperty(e,'key',{value:'Escape'});f.document.dispatchEvent(e);assert.equal(f.toggle.checked,false);assert.equal(f.document.activeElement,f.control);f.lifetime.abort();});
test('ordinary native answer selection still closes despite synthetic-toggle guarding',()=>{const f=fixture();f.control.click();const link=new Node('A'),e=new Event('click',{cancelable:true});for(const[name,value]of Object.entries({target:link,button:0,ctrlKey:false,metaKey:false,shiftKey:false,altKey:false}))Object.defineProperty(e,name,{value});f.dialog.dispatchEvent(e);assert.equal(f.toggle.checked,false);f.lifetime.abort();});
test('ordinary explicit close button closes search',()=>{const f=fixture();f.control.click();f.back.click();assert.equal(f.toggle.checked,false);f.lifetime.abort();});
test('disposal restores authored inert state and removes obsolete open handler',()=>{const f=fixture();f.control.click();assert.equal(f.background.inert,true);f.lifetime.abort();assert.equal(f.background.inert,false);f.toggle.checked=false;f.control.click();assert.equal(f.toggle.checked,false);});

function escapeInline(f){f.control.click();const answer=new Node('A');f.document.activeElement=answer;const e=new Event('keydown',{cancelable:true});Object.defineProperty(e,'key',{value:'Escape'});f.document.dispatchEvent(e);assert.equal(f.toggle.checked,false);assert.equal(f.document.activeElement,f.query);return f;}
test('closed inline focus persists through the later native focus-open callback',()=>{const f=escapeInline(fixture({inline:true}));const callback=f.toggle.click();assert.equal(callback.defaultPrevented,true);assert.equal(f.toggle.checked,false);assert.equal(f.document.activeElement,f.query);f.lifetime.abort();});
test('ordinary click on the already focused inline invoker establishes fresh open intent',()=>{const f=escapeInline(fixture({inline:true}));f.query.click();assert.equal(f.toggle.checked,true);f.lifetime.abort();});
test('ordinary Space editing reopens without claiming the native keyboard event',()=>{const f=escapeInline(fixture({inline:true}));const e=new Event('keydown',{cancelable:true});Object.defineProperty(e,'key',{value:' '});f.query.dispatchEvent(e);assert.equal(e.defaultPrevented,false);assert.equal(f.toggle.checked,true);f.lifetime.abort();});
test('copy/select/browser shortcuts preserve closed focus and their native defaults',()=>{const f=escapeInline(fixture({inline:true}));for(const [key,modifier] of [['c','ctrlKey'],['a','metaKey'],['f','ctrlKey'],['p','metaKey'],['x','altKey']]){const e=new Event('keydown',{cancelable:true});Object.defineProperty(e,'key',{value:key});Object.defineProperty(e,modifier,{value:true});f.query.dispatchEvent(e);assert.equal(e.defaultPrevented,false);assert.equal(f.toggle.checked,false);}f.lifetime.abort();});
test('plain and Shift text and navigation editing keys establish fresh intent',()=>{for(const key of ['a','A','Backspace','Delete','Enter','ArrowUp','ArrowDown']){const f=escapeInline(fixture({inline:true}));const e=new Event('keydown',{cancelable:true});Object.defineProperty(e,'key',{value:key});Object.defineProperty(e,'shiftKey',{value:key==='A'});f.query.dispatchEvent(e);assert.equal(e.defaultPrevented,false);assert.equal(f.toggle.checked,true);f.lifetime.abort();}});
test('composition input establishes intent without blocking the composition event',()=>{const f=escapeInline(fixture({inline:true}));const e=new Event('input',{cancelable:true});Object.defineProperty(e,'isComposing',{value:true});f.query.dispatchEvent(e);assert.equal(e.defaultPrevented,false);assert.equal(f.toggle.checked,true);f.lifetime.abort();});
test('ordinary blur ends closed inline focus ownership before later native open',()=>{const f=escapeInline(fixture({inline:true}));f.query.dispatchEvent(new Event('blur'));const native=f.toggle.click();assert.equal(native.defaultPrevented,false);assert.equal(f.toggle.checked,true);f.lifetime.abort();});
test('disposed inline intent listeners cannot reopen or retain background inert state',()=>{const f=escapeInline(fixture({inline:true}));f.lifetime.abort();f.query.click();f.query.dispatchEvent(new Event('input'));assert.equal(f.toggle.checked,false);assert.equal(f.background.inert,false);});

test('native focus after ordinary blur opens without relying on coalesced upstream focus observations',()=>{const f=escapeInline(fixture({inline:true}));f.query.dispatchEvent(new Event('blur'));f.query.focus();assert.equal(f.toggle.checked,true);assert.equal(f.document.activeElement,f.query);f.lifetime.abort();});

function shortcut(f, modifiers = {}, target) {
  const event = new Event("keydown", { cancelable: true });
  for (const [name, value] of Object.entries({
    key: "/",
    ...modifiers,
    ...(target ? { target } : {}),
  }))
    Object.defineProperty(event, name, { value });
  f.document.dispatchEvent(event);
  return event;
}
test("modal shortcut opens before focusing its hidden query", () => {
  for (const key of ["/", "f", "s"]) {
    const f = fixture({ modal: true });
    const event = shortcut(f, { key });
    assert.equal(event.defaultPrevented, true);
    assert.equal(f.toggle.checked, true);
    assert.equal(f.document.activeElement, f.query);
    f.lifetime.abort();
  }
});
test("modified modal shortcuts retain closed state and their native defaults", () => {
  for (const modifier of ["ctrlKey", "metaKey", "altKey"]) {
    const f = fixture({ modal: true });
    assert.equal(shortcut(f, { [modifier]: true }).defaultPrevented, false);
    assert.equal(f.toggle.checked, false);
    f.lifetime.abort();
  }
});
test("editable fields retain the literal slash without opening modal search", () => {
  const f = fixture({ modal: true });
  const editable = new Node("TEXTAREA");
  editable.closest = () => editable;
  assert.equal(shortcut(f, {}, editable).defaultPrevented, false);
  assert.equal(f.toggle.checked, false);
  f.lifetime.abort();
});
test("inline desktop shortcut remains owned by native Material", () => {
  const f = fixture({ inline: true });
  assert.equal(shortcut(f).defaultPrevented, false);
  assert.equal(f.toggle.checked, false);
  f.lifetime.abort();
});
test("disposed modal shortcut cannot establish open intent", () => {
  const f = fixture({ modal: true });
  f.lifetime.abort();
  assert.equal(shortcut(f).defaultPrevented, false);
  assert.equal(f.toggle.checked, false);
});

test("modal sequential traversal excludes authored negative tabindex buttons", () => {
  const f = fixture();
  const excluded = new Node("BUTTON");
  excluded.tabIndex = -1;
  excluded.focus = () => {
    f.document.activeElement = excluded;
  };
  f.dialog.querySelectorAll = () => [f.query, f.back, excluded];
  f.control.click();
  f.document.activeElement = f.back;
  const event = new Event("keydown", { cancelable: true });
  Object.defineProperty(event, "key", { value: "Tab" });
  f.document.dispatchEvent(event);
  assert.equal(event.defaultPrevented, true);
  assert.equal(f.document.activeElement, f.query);
  f.lifetime.abort();
});
