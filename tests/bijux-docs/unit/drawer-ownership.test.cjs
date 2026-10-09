'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.env.BOOTSTRAP_SOURCE||path.resolve(__dirname,'../../../shared/bijux-docs/scripts/bootstrap.js'),'utf8');
const begin=source.indexOf('  function bindDrawer(signal) {'),end=source.indexOf('  function bindSearch(signal) {',begin),fn=source.slice(begin,end),helper=source.slice(source.indexOf('  function bindPopupIdentity('),begin);
class Element extends EventTarget {
 constructor(){super();this.isConnected=true;this.disabled=false;this.inert=false;this.checked=false;this.attrs={};this.dataset={};}
 closest(){return this.inertAncestor || null;}matches(selector){return selector.toUpperCase()===this.tagName;}hasAttribute(k){return Object.hasOwn(this.attrs,k);}
 getAttribute(k){return this.attrs[k]??null;}setAttribute(k,v){this.attrs[k]=String(v);}removeAttribute(k){delete this.attrs[k];}
 querySelectorAll(){return [];}contains(n){return n===this;}getClientRects(){return [{}];}focus(options){this.focusCount=(this.focusCount||0)+1;this.focusOptions=options;}
}
function fixture({owned=true,missing=false,initialInert=false,nativeControls=[],backgroundNodes=[],drawerControls=[],location='https://docs.example/reference/'}={}){
 const document=new EventTarget(),toggle=new Element(),sidebar=new Element(),navigation=new Element(),opener=new Element(),compact=new EventTarget(),signal=new AbortController();compact.matches=false;sidebar.inert=initialInert;
 sidebar.attrs={role:'navigation','aria-label':'Authored navigation'};opener.attrs={'aria-controls':'authored-tree'};document.body={dataset:{}};document.querySelectorAll=selector=>selector==='[id]'?[sidebar,navigation].filter(node=>node.getAttribute('id')):selector.includes('data-bijux-control-close')?nativeControls:selector==='[data-bijux-control-target="__drawer"]'?drawerControls:backgroundNodes.filter(node=>selector.split(',').map(value=>value.trim()).includes(node.surface));document.getElementById=id=>id==='__drawer'?(missing?null:toggle):id==='bijux-navigation'?navigation:sidebar.getAttribute('id')===id?sidebar:null;
 document.querySelector=selector=>selector==='header[data-bijux-drawer-target]'?(owned?new Element():null):selector.includes('sidebar')?sidebar:opener;
 const nativeDrawerLabels=new WeakMap();const scope={document,compact,nativeDrawerLabels,signal:signal.signal,Event,URL,queueMicrotask,window:{location:{href:location}},getComputedStyle:()=>({visibility:'visible'})};
 let state;
 const consumer=source.slice((source.includes('      const focusReading =') ? source.indexOf('      const focusReading =') : source.indexOf('      if (readingIntent) {')),source.indexOf('      if (drawerBound)'));
 return {scope,drawerControls,readIntent:()=>state.intent(),consume:()=>state.consume(),document,toggle,sidebar,navigation,opener,compact,signal,nativeDrawerLabels,bind:()=>{state=vm.runInNewContext('let closeDrawer;let readingIntent=false;const disconnectedReader=false;'+helper+fn+'({bind:()=>bindDrawer(signal),intent:()=>readingIntent,consume:()=>{'+consumer+'}});',scope);return state.bind();}};
}
test('native header skips unrelated drawer requirements instead of blocking independent search',()=>{const f=fixture({owned:false,missing:true});assert.equal(f.bind(),false);assert.equal(f.document.body.dataset.bijuxDrawerReady,undefined);f.signal.abort();});
test('server-owned drawer with missing required native control fails before readiness',()=>{const f=fixture({missing:true});assert.throws(()=>f.bind(),/requires its native control/);assert.equal(f.document.body.dataset.bijuxDrawerReady,undefined);f.signal.abort();});
test('complete server-owned drawer returns an ownership claim without premature lifecycle readiness',()=>{const f=fixture();assert.equal(f.bind(),true);assert.equal(f.document.body.dataset.bijuxDrawerReady,undefined);assert.equal(f.opener.getAttribute('aria-controls'),f.sidebar.getAttribute('id'));assert.notEqual(f.sidebar.getAttribute('id'),'bijux-navigation');f.signal.abort();});
test('abort restores authored semantics and pre-existing inert state after owned mutation',()=>{const f=fixture({initialInert:true});f.bind();assert.equal(f.sidebar.inert,false);f.document.body.dataset.bijuxDrawerReady='true';f.document.body.dataset.bijuxDrawerOpen='true';f.signal.abort();assert.equal(f.sidebar.inert,true);assert.equal(f.sidebar.getAttribute('role'),'navigation');assert.equal(f.sidebar.getAttribute('aria-label'),'Authored navigation');assert.equal(f.opener.getAttribute('aria-controls'),'authored-tree');assert.equal(f.document.body.dataset.bijuxDrawerReady,undefined);assert.equal(f.document.body.dataset.bijuxDrawerOpen,undefined);});

test('native opener activates its existing checkbox without claiming modal ownership',()=>{
 const close=new Element(),f=fixture({owned:false,nativeControls:[close]});let changes=0;f.toggle.addEventListener('change',()=>changes++);
 assert.equal(f.bind(),false);f.opener.dispatchEvent(new Event('click'));assert.equal(f.toggle.checked,true);assert.equal(changes,1);assert.equal(f.opener.getAttribute('aria-expanded'),'true');
 f.opener.dispatchEvent(new Event('click'));assert.equal(f.toggle.checked,false);assert.equal(changes,2);assert.equal(f.opener.getAttribute('aria-expanded'),'false');
 assert.equal(f.sidebar.inert,false);assert.equal(f.sidebar.getAttribute('role'),'navigation');assert.deepEqual(f.document.body.dataset,{});f.signal.abort();
});
test('native close clears an open checkbox and restores the visible real opener',()=>{
 const close=new Element(),f=fixture({owned:false,nativeControls:[close]});let changes=0;f.toggle.addEventListener('change',()=>changes++);f.bind();f.toggle.checked=true;
 close.dispatchEvent(new Event('click'));assert.equal(f.toggle.checked,false);assert.equal(changes,1);assert.equal(f.opener.focusCount,1);
 close.dispatchEvent(new Event('click'));assert.equal(f.toggle.checked,false);assert.equal(f.opener.focusCount,1);f.signal.abort();
});
test('native dismissal never focuses an opener hidden at desktop',()=>{
 const close=new Element(),f=fixture({owned:false,nativeControls:[close]});f.opener.getClientRects=()=>[];f.bind();f.toggle.checked=true;
 close.dispatchEvent(new Event('click'));assert.equal(f.toggle.checked,false);assert.equal(f.opener.focusCount,undefined);f.signal.abort();
});
test('native lifetime abort removes both handlers without mutating authored sidebar state',()=>{
 const close=new Element(),f=fixture({owned:false,nativeControls:[close],initialInert:true});let changes=0;f.toggle.addEventListener('change',()=>changes++);
 f.bind();f.signal.abort();f.toggle.checked=true;close.dispatchEvent(new Event('click'));assert.equal(f.toggle.checked,true);f.opener.dispatchEvent(new Event('click'));assert.equal(f.toggle.checked,true);assert.equal(changes,0);
 assert.equal(f.sidebar.inert,true);assert.equal(f.sidebar.getAttribute('aria-label'),'Authored navigation');assert.deepEqual(f.document.body.dataset,{});
});

test('native abort restores the original opener and close labels with their live children',()=>{
 const close=new Element(),f=fixture({owned:false,nativeControls:[close]}),restored=[];
 for (const [control,name] of [[f.opener,'opener'],[close,'close']]) {
   control.childNodes=[{name:name+'-icon'}];
   const label={replaceChildren(...children){this.children=children;}};
   control.replaceWith=replacement=>restored.push({name,replacement});f.nativeDrawerLabels.set(control,label);
 }
 f.bind();f.signal.abort();assert.equal(restored.length,2);
 assert.equal(restored[0].replacement.children[0].name,'opener-icon');assert.equal(restored[1].replacement.children[0].name,'close-icon');
 assert.equal(f.nativeDrawerLabels.has(f.opener),false);assert.equal(f.nativeDrawerLabels.has(close),false);
});
test('native abort leaves authored button controls intact when no label was leased',()=>{
 const close=new Element(),f=fixture({owned:false,nativeControls:[close]});
 f.opener.replaceWith=()=>{throw new Error('Authored button must not be replaced');};close.replaceWith=f.opener.replaceWith;
 f.opener.setAttribute('aria-expanded','authored');f.bind();assert.equal(f.opener.getAttribute('aria-expanded'),'false');f.signal.abort();assert.equal(f.opener.getAttribute('aria-expanded'),'authored');assert.deepEqual(f.document.body.dataset,{});
});

function headerBackground() {
  return [".bijux-site-tabs", ".bijux-hub-strip", ".bijux-detail-tabs", ".bijux-course-tabs"].map((surface, index) => {
    const node = new Element();
    node.surface = surface;
    node.inert = index % 2 === 1;
    return node;
  });
}
for (const restoration of ["close", "abort", "resize"]) {
  test(`owned modal leases every header navigation background and restores prior state on ${restoration}`, () => {
    const nodes = headerBackground();
    const previous = nodes.map(node => node.inert);
    const f = fixture({ backgroundNodes: nodes });
    f.compact.matches = true;
    f.bind();
    f.toggle.checked = true;
    f.toggle.dispatchEvent(new Event("change"));
    assert.equal(f.sidebar.getAttribute("aria-modal"), "true");
    assert.deepEqual(nodes.map(node => node.inert), [true, true, true, true]);
    if (restoration === "abort") f.signal.abort();
    else if (restoration === "resize") {
      f.compact.matches = false;
      f.compact.dispatchEvent(new Event("change"));
    } else {
      f.toggle.checked = false;
      f.toggle.dispatchEvent(new Event("change"));
    }
    assert.deepEqual(nodes.map(node => node.inert), previous);
    f.signal.abort();
    assert.deepEqual(nodes.map(node => node.inert), previous);
  });
}
test("native sidebar controls do not lease header navigation background", () => {
  const nodes = headerBackground(), previous = nodes.map(node => node.inert);
  const f = fixture({ owned: false, backgroundNodes: nodes });
  f.compact.matches = true;
  f.bind();
  f.opener.dispatchEvent(new Event("click"));
  assert.deepEqual(nodes.map(node => node.inert), previous);
  f.signal.abort();
  assert.deepEqual(nodes.map(node => node.inert), previous);
});

function activate(f, { target, download, href = "https://docs.example/product/", ...keys } = {}) {
  const link = new Element();
  link.href = href;
  if (target !== undefined) link.setAttribute("target", target);
  if (download) link.setAttribute("download", "guide.txt");
  f.navigation.closest = () => link;
  const event = new Event("click", { bubbles: true, cancelable: true });
  Object.assign(event, { button: 0, ...keys });
  f.navigation.dispatchEvent(event);
  return event;
}
function opened() {
  const f = fixture();
  f.compact.matches = true;
  f.bind();
  f.toggle.checked = true;
  f.toggle.dispatchEvent(new Event("change"));
  return f;
}
test("navigation preserves a visible fallback while a pending destination owns reading intent", async () => {
  const f = opened();
  activate(f);
  assert.equal(f.toggle.checked, false);
  assert.equal(f.opener.focusCount, 1);
  assert.equal(f.readIntent().href, "https://docs.example/product/");
  await Promise.resolve();
  assert.equal(f.readIntent().href, "https://docs.example/product/");
  f.signal.abort();
});
for (const action of [
  { target: "_blank" }, { target: "named-reader" }, { target: "_parent" },
  { download: true }, { href: "mailto:reader@example.org" },
  { ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 },
]) {
  test(`non-current-document navigation preserves browser action ${JSON.stringify(action)}`, async () => {
    const f = opened();
    const event = activate(f, action);
    assert.equal(f.toggle.checked, true);
    assert.equal(f.opener.focusCount, undefined);
    assert.equal(f.readIntent(), false);
    assert.equal(event.defaultPrevented, false);
    await Promise.resolve();
    assert.equal(f.readIntent(), false);
    f.signal.abort();
  });
}
for (const state of ["disconnected", "hidden", "disabled", "inert-ancestor"]) {
  test(`navigation does not restore an unavailable opener: ${state}`, async () => {
    const f = opened();
    if (state === "disconnected") f.opener.isConnected = false;
    if (state === "hidden") f.opener.getClientRects = () => [];
    if (state === "disabled") f.opener.disabled = true;
    if (state === "inert-ancestor") f.opener.inertAncestor = new Element();
    activate(f);
    assert.equal(f.opener.focusCount, undefined);
    await Promise.resolve();
    f.signal.abort();
  });
}
test("an admitted instant emission owns heading focus only at its actual destination", async () => {
  const f = opened(), heading = new Element(); heading.tagName = "H1";
  const event = activate(f);
  event.preventDefault();
  await Promise.resolve();
  f.scope.window.location.href = "https://docs.example/product/";
  f.document.querySelector = selector => selector === ".md-content h1" ? heading : null;
  f.consume();
  assert.equal(heading.focusCount, 1);
  assert.equal(heading.getAttribute("tabindex"), "-1");
  assert.equal(f.readIntent(), false);
  f.consume();
  assert.equal(heading.focusCount, 1);
  f.signal.abort();
});
test("a mismatched instant emission consumes stale intent without redirecting reader focus", async () => {
  const f = opened(), heading = new Element(); heading.tagName = "H1";
  activate(f).preventDefault();
  await Promise.resolve();
  f.document.querySelector = selector => selector === ".md-content h1" ? heading : null;
  f.consume();
  assert.equal(heading.focusCount, undefined);
  assert.equal(f.readIntent(), false);
  f.signal.abort();
});
test("current-route native handoff does not leave a heading intent for later lifecycle rebind", async () => {
  const f = opened(), heading = new Element(); heading.tagName = "H1";
  activate(f, { target: "_self", href: f.scope.window.location.href });
  await Promise.resolve();
  f.document.querySelector = selector => selector === ".md-content h1" ? heading : null;
  f.consume();
  assert.equal(heading.focusCount, undefined);
  assert.equal(f.readIntent(), false);
  f.signal.abort();
});
test("lifetime abort removes navigation fallback and intent mutation", () => {
  const f = opened();
  f.signal.abort();
  activate(f);
  assert.equal(f.toggle.checked, true);
  assert.equal(f.readIntent(), false);
  assert.equal(f.opener.focusCount, undefined);
});

test("a new ordinary drawer activation revokes an older pending reader destination", () => {
  const f = fixture();
  f.drawerControls.push(f.opener);
  f.compact.matches = true;
  f.bind();
  f.opener.dispatchEvent(new Event("click"));
  activate(f);
  assert.equal(f.readIntent().href, "https://docs.example/product/");
  f.opener.dispatchEvent(new Event("click"));
  assert.equal(f.toggle.checked, true);
  assert.equal(f.readIntent(), false);
  f.signal.abort();
});
test("same-page fragment actions preserve browser ownership without heading handoff state", () => {
  const f = opened();
  const event = activate(f, { href: f.scope.window.location.href + "#reader-section" });
  assert.equal(event.defaultPrevented, false);
  assert.equal(f.readIntent(), false);
  assert.equal(f.toggle.checked, false);
  assert.ok(f.opener.focusCount > 0);
  f.signal.abort();
});

test("reopened drawer permits scrolling its focus target into the panel viewport", () => {
  const f = opened();
  assert.equal(f.navigation.focusOptions.preventScroll, false);
  f.signal.abort();
});
