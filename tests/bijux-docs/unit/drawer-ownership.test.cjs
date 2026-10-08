'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.env.BOOTSTRAP_SOURCE||path.resolve(__dirname,'../../../shared/bijux-docs/scripts/bootstrap.js'),'utf8');
const begin=source.indexOf('  function bindDrawer(signal) {'),end=source.indexOf('  function bindSearch(signal) {',begin),fn=source.slice(begin,end),helper=source.slice(source.indexOf('  function bindPopupIdentity('),begin);
class Element extends EventTarget {
 constructor(){super();this.inert=false;this.checked=false;this.attrs={};this.dataset={};}
 getAttribute(k){return this.attrs[k]??null;}setAttribute(k,v){this.attrs[k]=String(v);}removeAttribute(k){delete this.attrs[k];}
 querySelectorAll(){return [];}contains(n){return n===this;}getClientRects(){return [{}];}focus(){this.focusCount=(this.focusCount||0)+1;}
}
function fixture({owned=true,missing=false,initialInert=false,nativeControls=[],backgroundNodes=[]}={}){
 const document=new EventTarget(),toggle=new Element(),sidebar=new Element(),navigation=new Element(),opener=new Element(),compact=new EventTarget(),signal=new AbortController();compact.matches=false;sidebar.inert=initialInert;
 sidebar.attrs={role:'navigation','aria-label':'Authored navigation'};opener.attrs={'aria-controls':'authored-tree'};document.body={dataset:{}};document.querySelectorAll=selector=>selector==='[id]'?[sidebar,navigation].filter(node=>node.getAttribute('id')):selector.includes('data-bijux-control-close')?nativeControls:backgroundNodes.filter(node=>selector.split(',').map(value=>value.trim()).includes(node.surface));document.getElementById=id=>id==='__drawer'?(missing?null:toggle):id==='bijux-navigation'?navigation:sidebar.getAttribute('id')===id?sidebar:null;
 document.querySelector=selector=>selector==='header[data-bijux-drawer-target]'?(owned?new Element():null):selector.includes('sidebar')?sidebar:opener;
 const nativeDrawerLabels=new WeakMap();const scope={document,compact,nativeDrawerLabels,signal:signal.signal,Event,getComputedStyle:()=>({visibility:'visible'})};
 return {document,toggle,sidebar,navigation,opener,compact,signal,nativeDrawerLabels,bind:()=>vm.runInNewContext('let closeDrawer;let readingIntent=false;'+helper+fn+'bindDrawer(signal);',scope)};
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
