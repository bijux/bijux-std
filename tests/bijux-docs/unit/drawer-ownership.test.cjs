'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.env.BOOTSTRAP_SOURCE||path.resolve(__dirname,'../../../shared/bijux-docs/scripts/bootstrap.js'),'utf8');
const begin=source.indexOf('  function bindDrawer(signal) {'),end=source.indexOf('  function bindSearch(signal) {',begin),fn=source.slice(begin,end);
class Element extends EventTarget {
 constructor(){super();this.inert=false;this.checked=false;this.attrs={};this.dataset={};}
 getAttribute(k){return this.attrs[k]??null;}setAttribute(k,v){this.attrs[k]=String(v);}removeAttribute(k){delete this.attrs[k];}
 querySelectorAll(){return [];}contains(n){return n===this;}getClientRects(){return [{}];}focus(){}
}
function fixture({owned=true,missing=false,initialInert=false}={}){
 const document=new EventTarget(),toggle=new Element(),sidebar=new Element(),navigation=new Element(),opener=new Element(),compact=new EventTarget(),signal=new AbortController();compact.matches=false;sidebar.inert=initialInert;
 sidebar.attrs={role:'navigation','aria-label':'Authored navigation'};opener.attrs={'aria-controls':'authored-tree'};document.body={dataset:{}};document.querySelectorAll=()=>[];document.getElementById=id=>id==='__drawer'?(missing?null:toggle):navigation;
 document.querySelector=selector=>selector==='header[data-bijux-drawer-target]'?(owned?new Element():null):selector.includes('sidebar')?sidebar:opener;
 const scope={document,compact,signal:signal.signal,Event,getComputedStyle:()=>({visibility:'visible'})};
 return {document,toggle,sidebar,navigation,opener,signal,bind:()=>vm.runInNewContext('let closeDrawer;let readingIntent=false;'+fn+'bindDrawer(signal);',scope)};
}
test('native header skips unrelated drawer requirements instead of blocking independent search',()=>{const f=fixture({owned:false,missing:true});assert.equal(f.bind(),false);assert.equal(f.document.body.dataset.bijuxDrawerReady,undefined);f.signal.abort();});
test('server-owned drawer with missing required native control fails before readiness',()=>{const f=fixture({missing:true});assert.throws(()=>f.bind(),/requires its native control/);assert.equal(f.document.body.dataset.bijuxDrawerReady,undefined);f.signal.abort();});
test('complete server-owned drawer returns an ownership claim without premature lifecycle readiness',()=>{const f=fixture();assert.equal(f.bind(),true);assert.equal(f.document.body.dataset.bijuxDrawerReady,undefined);assert.equal(f.opener.getAttribute('aria-controls'),'bijux-navigation');f.signal.abort();});
test('abort restores authored semantics and pre-existing inert state after owned mutation',()=>{const f=fixture({initialInert:true});f.bind();assert.equal(f.sidebar.inert,false);f.document.body.dataset.bijuxDrawerReady='true';f.document.body.dataset.bijuxDrawerOpen='true';f.signal.abort();assert.equal(f.sidebar.inert,true);assert.equal(f.sidebar.getAttribute('role'),'navigation');assert.equal(f.sidebar.getAttribute('aria-label'),'Authored navigation');assert.equal(f.opener.getAttribute('aria-controls'),'authored-tree');assert.equal(f.document.body.dataset.bijuxDrawerReady,undefined);assert.equal(f.document.body.dataset.bijuxDrawerOpen,undefined);});
