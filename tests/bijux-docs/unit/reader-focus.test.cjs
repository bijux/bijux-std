const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
const source=fs.readFileSync(path.resolve(__dirname,'../../../shared/bijux-docs/scripts/bootstrap.js'),'utf8');
function page(){
 const events=new Map(),windowEvents=new Map(),tasks=[];let emit;
 const document={title:'Current documentation',body:{dataset:{}}};document.activeElement=document.body;
 function node(tag,reader=false){
  const attributes=new Map();const n={tagName:tag.toUpperCase(),isConnected:true,
   closest:()=>reader?{}:null,matches:s=>s==='main'&&tag==='main',hasAttribute:k=>attributes.has(k),getAttribute:k=>attributes.get(k)??null,setAttribute:(k,v)=>attributes.set(k,v),
   focus(){document.activeElement=n;fire('focusin',n);},attributes};return n;
 }
 let heading=node('h1',true),main=node('main');
 function fire(type,target){for(const callback of events.get(type)||[])callback({target});}
 document.querySelector=s=>s==='.md-content h1'?heading:s==='main'?main:null;
 document.querySelectorAll=()=>[];document.getElementById=()=>null;
 document.addEventListener=(type,callback)=>{if(!events.has(type))events.set(type,[]);events.get(type).push(callback);};
 const window={bijuxShell:{},matchMedia:()=>({matches:true}),document$:{subscribe(callback){emit=callback;}},addEventListener:(name,callback)=>windowEvents.set(name,callback),dispatchEvent(){}};
 vm.runInNewContext(source,{window,document,AbortController,Event,queueMicrotask:callback=>tasks.push(callback)}, {timeout:1000});
 const state={document,window,node,emit:()=>emit(),flush(){while(tasks.length)tasks.shift()();},focus:n=>n.focus(),blur(n){document.activeElement=document.body;fire('focusout',n);},replace(){const old=heading;old.isConnected=false;document.activeElement=document.body;heading=node('h1',true);return old;},get heading(){return heading;},get main(){return main;},noHeading(){heading=null;},fireWindow:type=>windowEvents.get(type)?.({persisted:true})};return state;
}

test('document replacement restores disconnected reader focus to current heading',()=>{const p=page();p.focus(p.heading);p.replace();p.emit();assert.equal(p.document.activeElement,p.heading);assert.equal(p.heading.getAttribute('tabindex'),'-1');});
test('repeated Back and Forward replacements retain current reader focus',()=>{const p=page();p.focus(p.heading);for(let i=0;i<3;i++){p.replace();p.emit();assert.equal(p.document.activeElement,p.heading);}});
test('connected header focus is preserved across an unrelated document emission',()=>{const p=page();p.focus(p.heading);p.replace();const header=p.node('button');p.focus(header);p.emit();assert.equal(p.document.activeElement,header);});
test('initial deep route and same-document fragment do not manufacture reader focus',()=>{const p=page();p.emit();assert.equal(p.document.activeElement,p.document.body);p.focus(p.heading);p.emit();assert.equal(p.document.activeElement,p.heading);assert.equal(p.heading.getAttribute('tabindex'),null);});
test('intentional blur of a surviving reader clears stale focus intent',()=>{const p=page();const old=p.heading;p.focus(old);p.blur(old);p.flush();p.replace();p.emit();assert.equal(p.document.activeElement,p.document.body);});
test('removal blur preserves the actual disconnected reader until replacement',()=>{const p=page();const old=p.heading;p.focus(old);p.blur(old);p.replace();p.flush();p.emit();assert.equal(p.document.activeElement,p.heading);});
test('missing heading restores a named main without replacing authored names',()=>{for(const authored of [false,true]){const p=page();p.focus(p.heading);p.replace();p.noHeading();if(authored)p.main.setAttribute('aria-label','Authored reader');p.emit();assert.equal(p.document.activeElement,p.main);assert.equal(p.main.getAttribute('aria-label'),authored?'Authored reader':'Current documentation');}});
test('pagehide releases focus intent before persisted lifecycle remount',()=>{const p=page();p.focus(p.heading);p.fireWindow('pagehide');p.replace();p.fireWindow('pageshow');p.emit();assert.equal(p.document.activeElement,p.document.body);});
