const {test} = require('node:test');
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../../../shared/bijux-docs/tooling/material/element-resize-delivery.js'),'utf8');
function harness(deliver) {
 let native, next=0;const frames=new Map();const cancelled=[];
 class Native {
  constructor(callback){this.callback=callback;this.observed=[];this.retired=[];this.disconnected=0;native=this;}
  observe(target,options){this.observed.push({target,options});}
  unobserve(target){this.retired.push(target);}
  disconnect(){this.disconnected++;}
 }
 const context=vm.createContext({ResizeObserver:Native,requestAnimationFrame:callback=>{frames.set(++next,callback);return next;},cancelAnimationFrame:id=>{cancelled.push(id);frames.delete(id);}});
 const factory=vm.runInContext(source+'\n__bijuxElementResizeObserver',context);
 const observer=factory(deliver);
 const flush=()=>{const batch=[...frames];frames.clear();for(const[,callback]of batch)callback();};
 return {observer,emit:entries=>native.callback(entries),frames,cancelled,flush,native,Native};
}
const check = test;
check('delivery leaves native observer notification before measuring native subscribers',()=>{const seen=[];const h=harness(entry=>seen.push(entry));const target={};h.observer.observe(target);h.emit([{target,value:1}]);assert.equal(seen.length,0);assert.equal(h.frames.size,1);h.flush();assert.equal(seen[0].value,1);});
check('coalesce latest actual entry per observed target into one frame',()=>{const seen=[];const h=harness(entry=>seen.push(entry));const a={},b={};h.observer.observe(a);h.observer.observe(b);h.emit([{target:a,value:1},{target:b,value:2}]);h.emit([{target:a,value:3}]);assert.equal(h.frames.size,1);h.flush();assert.deepEqual(seen.map(x=>x.value),[3,2]);});
check('unobserve cancels obsolete queued entry and empty frame',()=>{const seen=[];const h=harness(e=>seen.push(e));const target={};h.observer.observe(target);h.emit([{target}]);h.observer.unobserve(target);assert.equal(h.frames.size,0);assert.equal(h.cancelled.length,1);h.flush();assert.equal(seen.length,0);assert.equal(h.native.retired[0],target);});
check('native synchronous resubscription cannot receive the old generation batch',()=>{const a={},b={},seen=[];let h;h=harness(e=>{seen.push(e.value);if(e.target===a){h.observer.unobserve(b);h.observer.observe(b);}});h.observer.observe(a);h.observer.observe(b);h.emit([{target:a,value:'a'},{target:b,value:'old-b'}]);h.flush();assert.deepEqual(seen,['a']);h.emit([{target:b,value:'new-b'}]);h.flush();assert.deepEqual(seen,['a','new-b']);});
check('disconnect retires all pending work without swallowing future valid observation',()=>{const seen=[];const h=harness(e=>seen.push(e));const target={};h.observer.observe(target);h.emit([{target,value:'old'}]);h.observer.disconnect();assert.equal(h.frames.size,0);assert.equal(h.native.disconnected,1);h.flush();assert.equal(seen.length,0);h.observer.observe(target);h.emit([{target,value:'fresh'}]);h.flush();assert.equal(seen[0].value,'fresh');});
check('unobserved late native entries cannot retain a pending element',()=>{const seen=[];const h=harness(e=>seen.push(e));h.emit([{target:{}}]);assert.equal(h.frames.size,0);assert.equal(seen.length,0);});
check('native identity and options remain per-instance without replacing global observer',()=>{const h=harness(()=>{}),target={},options={box:'border-box'};h.observer.observe(target,options);assert(h.observer instanceof h.Native);assert.equal(h.native.observed[0].options,options);});
check('subscriber exceptions remain observable rather than globally suppressed',()=>{const h=harness(()=>{throw Error('real subscriber failure');});const target={};h.observer.observe(target);h.emit([{target}]);assert.throws(()=>h.flush(),/real subscriber failure/);});
