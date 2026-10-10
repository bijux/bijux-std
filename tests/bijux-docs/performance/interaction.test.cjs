'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {PROFILE,commandsForProfile,digest}=require('./lab-evidence.cjs');
const {TRANSITIONS,EXPECTATIONS,metrics,qualifyTransition,qualifyInteraction,distributions}=require('./interaction-evidence.cjs');
const {installInteractionObserver}=require('./interaction-observer.cjs');
const {inventory,selectFixture,startFixtureServer}=require('./interaction-server.cjs');
const {measureInteraction}=require('./interaction.cjs');
function transition(name='drawer-open') {
  const state=structuredClone(EXPECTATIONS[name]),target={tag:'BUTTON',id:'owned',control:'drawer-toggle'};
  const first={at:130,state},second={at:146,state};
  const value={name,expected:state,armedAt:100,finishedAt:200,after:state,targetBefore:{x:0,y:0,width:44,height:44,inViewport:true,centerOwned:true},
    inputs:[{type:'click',isTrusted:true,eventTimeStamp:110,capturedAt:111,target}],frames:[first,second],firstMatch:first,secondMatch:second,
    supported:['event'],observerErrors:[],droppedEntries:0,eventEntries:[{name:'click',entryType:'event',startTime:110,duration:32,processingStart:112,processingEnd:118,interactionId:7,target:structuredClone(target)}],actionError:null};
  value.metrics=metrics(value);return value;
}
function vector() {
  const expected={source:{sha:'a'.repeat(40),tree:'b'.repeat(40),origin:'https://github.com/bijux/bijux-std.git'},accepted:{sha:'c'.repeat(40)},fixtureManifestSha256:'d'.repeat(64),siteFiles:{'index.html':{bytes:10,sha256:'e'.repeat(64)}},sourceInputs:{owned:'f'.repeat(64)},configuration:{physicalReread:false},toolchain:{material:'actual'}};
  const report={...structuredClone(expected),state:'complete',browserClosed:true,serverClosed:true,contextClosed:true,harnessUnchanged:true,fixtureUnchanged:true,sourceUnchanged:true,
    profile:PROFILE,profileSha256:digest(JSON.stringify(PROFILE)),commands:commandsForProfile().map(value=>({...value,accepted:true,response:value.method==='Network.emulateNetworkConditionsByRule'?{ruleIds:['actual-rule']}:{}})),
    origin:'http://127.0.0.1:12345',cycles:3,transitions:[],pageErrors:[],failedRequests:[]};
  report.document={url:report.origin+'/fixtures/long-registry/',visibility:'visible',viewport:{...PROFILE.viewport,deviceScaleFactor:1}};
  report.responses=[{url:report.document.url,status:200,decodedBodySha256:'e'.repeat(64),decodedBodyBytes:10}];
  for(let cycle=1;cycle<=3;cycle++) for(const name of TRANSITIONS) report.transitions.push({...transition(name),cycle});
  return {report,expected};
}
test('complete named finite observation vector qualifies (unit metadata, no browser claim)',()=>{const {report,expected}=vector();assert.equal(qualifyInteraction(report,expected).result,'pass');});
const mutations={
  'untrusted-input':value=>value.inputs[0].isTrusted=false,
  'wrong-hit-owner':value=>value.targetBefore.centerOwned=false,
  'offscreen-input-target':value=>value.targetBefore.inViewport=false,
  'zero-input-geometry':value=>value.targetBefore.width=0,
  'missing-second-frame':value=>value.secondMatch=null,
  'fabricated-frame-not-observed':value=>value.firstMatch={at:131,state:value.after},
  'wrong-required-focus':value=>value.after.focusWithinDrawer=false,
  'self-weakened-expectation':value=>value.expected={},
  'invalid-timeline':value=>value.finishedAt=99,
  'failed-action':value=>value.actionError='ordinary input failed',
  'fabricated-derived-latency':value=>value.metrics.renderingOpportunity.value=0
};
for(const [name,mutate] of Object.entries(mutations)) test('transition refuses '+name,()=>{const value=transition();mutate(value);assert.ok(qualifyTransition(value).length);});
const reportMutations={
  'stale-source':report=>report.source.sha='0'.repeat(40),
  'wrong-accepted-fixture':report=>report.accepted.sha='0'.repeat(40),
  'stale-config':report=>report.configuration={},
  'missing-owned-route':report=>report.siteFiles={},
  'changed-source-ownership':report=>report.sourceInputs={},
  'changed-profile':report=>report.profile={...PROFILE,isMobile:true},
  'missing-emulation':report=>report.commands.pop(),
  'rejected-network-emulation':report=>report.commands[4].accepted=false,
  'missing-rule-ack':report=>report.commands[4].response={},
  'wrong-served-url':report=>report.document.url=report.origin+'/outside/',
  'missing-document-response':report=>report.responses=[],
  'changed-response-body':report=>report.responses[0].decodedBodySha256='0'.repeat(64),
  'external-response':report=>report.responses[0].url='https://external.example/asset.js',
  'wrong-actual-viewport':report=>report.document.viewport.width=980,
  'hidden-document':report=>report.document.visibility='hidden',
  'missing-cycle':report=>report.transitions.splice(0,8),
  'reordered-transition':report=>report.transitions.reverse(),
  'active-context':report=>report.contextClosed=false,
  'changed-harness':report=>report.harnessUnchanged=false,
  'changed-fixture':report=>report.fixtureUnchanged=false,
  'runtime-error':report=>report.pageErrors.push('actual runtime error'),
  'request-failure':report=>report.failedRequests.push({url:'owned',failure:'failed'})
};
for(const [name,mutate] of Object.entries(reportMutations)) test('interaction qualification refuses '+name,()=>{const {report,expected}=vector();mutate(report);assert.equal(qualifyInteraction(report,expected).result,'fail');});
test('missing EventTiming is unknown and complete measurement remains incomplete, while functional evidence stays separate',()=>{
  const {report,expected}=vector();for(const value of report.transitions) {value.eventEntries=[];value.metrics=metrics(value);assert.equal(value.metrics.eventTiming.value,null);}
  const result=qualifyInteraction(report,expected);assert.equal(result.result,'incomplete');assert.equal(result.functional.result,'pass');assert.equal(result.eventTiming.missing.length,24);
  assert.equal(distributions(report.transitions)['drawer-open'].eventTiming.value,null);
});
test('unsupported/dropped/invalid/uncorrelated EventTiming never becomes zero',()=>{
  for(const mutate of [v=>v.supported=[],v=>v.droppedEntries=1,v=>v.eventEntries[0].duration=0,v=>v.eventEntries[0].target.id='other',v=>v.eventEntries[0].startTime=1,v=>v.observerErrors=['observer failure']]) {
    const value=transition();mutate(value);assert.equal(metrics(value).eventTiming.value,null);
  }
});
test('EventTiming and async required-state readiness are separate measured quantities',()=>{
  const value=transition();value.firstMatch.at=400;value.secondMatch.at=416;value.finishedAt=500;
  const result=metrics(value);assert.equal(result.eventTiming.value,32);assert.equal(result.eventTiming.inputDelayMs,2);assert.equal(result.renderingOpportunity.value,290);
});
test('partial distributions keep actual values and missing counts',()=>{
  const first=transition(),second=transition();second.eventEntries=[];second.metrics=metrics(second);
  const result=distributions([first,second])['drawer-open'];assert.equal(result.eventTiming.availability,'partial');assert.equal(result.eventTiming.samples,1);assert.equal(result.eventTiming.missing,1);
});
test('fixture selector rejects unpinned source before any browser launch',()=>{assert.throws(()=>selectFixture({sourceSha:'main'}),/full committed source/);});
test('insufficient repeated cycles refuse before fixture or browser launch',async()=>{await assert.rejects(measureInteraction({cycles:2}),/three to ten/);});
function scratch() {
  const root=path.resolve(process.env.BIJUX_PERFORMANCE_TEST_ARTIFACTS||'artifacts/qualification/payload-reader-interaction/unit-files');fs.mkdirSync(root,{recursive:true});return fs.mkdtempSync(path.join(root,'http-owned-'));
}
test('real finite HTTP server serves exact gzip bytes, all selected routes and rejects outside authority',async()=>{
  const root=scratch(),html=Buffer.from('<!doctype html><p>Owned α route</p>');fs.writeFileSync(path.join(root,'index.html'),html);fs.writeFileSync(path.join(root,'404.html'),html);
  const selected={directory:root,inventory:inventory(root)},server=await startFixtureServer(selected);
  try {
    const response=await fetch(server.origin+'/fixtures/long-registry/',{headers:{'Accept-Encoding':'gzip'}});assert.equal(response.status,200);assert.equal(response.headers.get('Content-Encoding'),'gzip');assert.deepEqual(Buffer.from(await response.arrayBuffer()),html);
    assert.equal((await fetch(server.origin+'/fixtures/long-registry/404.html')).status,200);assert.equal((await fetch(server.origin+'/outside/')).status,404);
    fs.writeFileSync(path.join(root,'index.html'),'<p>Changed source</p>');assert.equal((await fetch(server.origin+'/fixtures/long-registry/')).status,409);
  } finally {await server.close();}
  assert.ok(server.responses.some(value=>value.status===409));assert.ok(server.responses.some(value=>value.rawSha256===digest(html)));
});
test('finite fixture inventory refuses symlinked input authority',()=>{const root=scratch();fs.symlinkSync('/etc/hosts',path.join(root,'foreign'));assert.throws(()=>inventory(root),/symlink/);});
test('passive observer retains trusted input and blocks stale RAF callbacks after a new transition (VM control, no browser claim)',()=>{
  let now=100,frames=[],callback,listeners={};
  const node={tagName:'BUTTON',id:'owned',contains:other=>other===node,closest:()=>null,getBoundingClientRect:()=>({x:0,y:0,width:44,height:44,right:44,bottom:44})};
  const doc={activeElement:node,visibilityState:'visible',querySelector:()=>null,querySelectorAll:()=>[],elementFromPoint:()=>node};
  class Observer {static supportedEntryTypes=['event'];constructor(cb){callback=cb;}observe(options){assert.equal(options.durationThreshold,16);}takeRecords(){return [];}}
  const context={window:{},document:doc,PerformanceObserver:Observer,performance:{now:()=>now,timeOrigin:10},innerWidth:390,innerHeight:844,devicePixelRatio:1,
    addEventListener:(type,listener,options)=>{assert.equal(options.passive,true);listeners[type]=listener;},requestAnimationFrame:fn=>frames.push(fn),URL};
  vm.runInNewContext('('+installInteractionObserver.toString()+')()',context);
  const observer=context.window.__bijuxInteraction;observer.arm('owned',{},'button');listeners.click({isTrusted:true,timeStamp:110,target:node});now=130;frames.shift()(120);now=146;frames.shift()(140);
  assert.equal(observer.ready(),true);const first=observer.finish();assert.equal(first.inputs[0].isTrusted,true);assert.equal(first.secondMatch.at,146);assert.equal(first.firstMatch.frameTime,120);assert.equal(first.firstMatch.at,130);
  observer.arm('successor',{},'button');const old=frames.shift();old(160);assert.equal(observer.snapshot().active.frames.length,0);frames.shift()(170);assert.equal(observer.snapshot().active.frames.length,1);
  callback({getEntries:()=>[]},null,{droppedEntriesCount:2});assert.equal(observer.finish().droppedEntries,2);
});
module.exports={vector,transition,mutations,reportMutations};
