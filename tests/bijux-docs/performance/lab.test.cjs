'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const {PROFILE,distribution,cumulativeLayoutShift,metricSnapshot,commandsForProfile,qualifyLab,digest}=require('./lab-evidence.cjs');
const {installLabObserver}=require('./lab-observer.cjs');
const {applyProfile,distributions,measureLab,fixtureProducer}=require('./lab.cjs');

function snapshot(timeOrigin=1) {
  return {supported:['largest-contentful-paint','layout-shift','longtask'],entries:{'largest-contentful-paint':[{entryType:'largest-contentful-paint',startTime:120,duration:0,size:100}], 'layout-shift':[],longtask:[]},errors:[],droppedEntries:0,
    observationEndMs:1500,timeOrigin,visibility:'visible',readyState:'complete',viewport:{width:390,height:844,deviceScaleFactor:1},navigator:{onLine:true}};
}
function fixture() {
  const origin='http://127.0.0.1:12345',vendorPath='/vendor.js',source={origin:'https://github.com/bijux/bijux-std.git',sha:'a'.repeat(40),tree:'b'.repeat(40)};
  const assets={'/vendor.js':{sha256:'c'.repeat(64),bytes:1000}},documents={'/plain/':{sha256:'d'.repeat(64),bytes:100},'/diagram/':{sha256:'e'.repeat(64),bytes:200}};
  const expected={source,assets,documents,vendorPath,authoredSource:'flowchart LR\nA-->B'};
  const report={state:'complete',browserClosed:true,serverClosed:true,harnessUnchanged:true,source,assets,documents,origin,profile:PROFILE,profileSha256:digest(JSON.stringify(PROFILE)),requestedSamples:3,samples:[]};
  for(const route of ['/plain/','/diagram/']) for(let i=0;i<3;i++) {
    const sample={route,contextId:route+i,contextClosed:true,commands:commandsForProfile().map(c=>({...c,accepted:true,response:c.method==='Network.emulateNetworkConditionsByRule'?{ruleIds:['owned-rule']}:{}})),stages:[]};
    for(const cache of ['cold','warm']) {
      const snap=snapshot(i*2+(cache==='cold'?1:2));
      sample.stages.push({cacheState:cache,url:origin+route,actionError:null,pageErrors:[],snapshot:snap,metrics:metricSnapshot(snap),observationHoldMs:1000,primedBy:cache==='warm'?'cold':null,
        responses:[{url:origin+route,status:200,decodedBodySha256:documents[route].sha256,decodedBodyBytes:documents[route].bytes}],
        serverResponses:route==='/diagram/'&&cache==='cold'?[{path:vendorPath}]:[],
        resources:route==='/diagram/'?[{name:origin+vendorPath,decodedBodySize:1000,transferSize:cache==='cold'?500:0}]:[],
        rendererPresent:route==='/diagram/',rendered:route==='/diagram/',authoredSource:route==='/diagram/'?expected.authoredSource:null});
    }
    report.samples.push(sample);
  }
  return {report,expected};
}
const mutants={
  'active-browser':r=>r.browserClosed=false,
  'active-server':r=>r.serverClosed=false,
  'changed-owned-harness':r=>r.harnessUnchanged=false,
  'stale-source':r=>r.source={...r.source,sha:'0'.repeat(40)},
  'stale-assets':r=>r.assets={},
  'stale-documents':r=>r.documents={},
  'undeclared-profile':r=>r.profile={...PROFILE,cpuSlowdown:1},
  'stale-profile-fingerprint':r=>r.profileSha256='0'.repeat(64),
  'insufficient-repeats':r=>r.requestedSamples=2,
  'missing-sample':r=>r.samples.pop(),
  'duplicate-context':r=>r.samples[1].contextId=r.samples[0].contextId,
  'unclosed-context':r=>r.samples[0].contextClosed=false,
  'missing-cpu-command':r=>r.samples[0].commands.splice(3,1),
  'changed-cpu-command':r=>r.samples[0].commands[3].params={rate:1},
  'unaccepted-network-command':r=>r.samples[0].commands[4].accepted=false,
  'missing-rule-acknowledgement':r=>r.samples[0].commands[4].response={},
  'wrong-document-url':r=>r.samples[0].stages[0].url=r.origin+'/other/',
  'missing-document-time-origin':r=>delete r.samples[0].stages[0].snapshot.timeOrigin,
  'hidden-document':r=>r.samples[0].stages[0].snapshot.visibility='hidden',
  'wrong-actual-viewport':r=>r.samples[0].stages[0].snapshot.viewport.width=980,
  'offline-navigator':r=>r.samples[0].stages[0].snapshot.navigator.onLine=false,
  'unsupported-lcp':r=>r.samples[0].stages[0].snapshot.supported=['layout-shift','longtask'],
  'missing-lcp-candidate':r=>r.samples[0].stages[0].snapshot.entries['largest-contentful-paint']=[],
  'dropped-observer-records':r=>r.samples[0].stages[0].snapshot.droppedEntries=1,
  'fabricated-metric-value':r=>r.samples[0].stages[0].metrics.lcp.value=1,
  'short-observation-hold':r=>r.samples[0].stages[0].observationHoldMs=10,
  'short-observation-window':r=>r.samples[0].stages[0].snapshot.observationEndMs=10,
  'changed-served-document':r=>r.samples[0].stages[0].responses[0].decodedBodySha256='0'.repeat(64),
  'eager-plain-vendor':r=>r.samples[0].stages[0].rendererPresent=true,
  'cold-vendor-not-transferred':r=>r.samples[3].stages[0].resources[0].transferSize=0,
  'warm-vendor-retransmitted':r=>r.samples[3].stages[1].serverResponses=[{path:'/vendor.js'}],
  'warm-same-document':r=>r.samples[3].stages[1].snapshot.timeOrigin=r.samples[3].stages[0].snapshot.timeOrigin,
  'unprimed-warm':r=>r.samples[3].stages[1].primedBy=null,
  'missing-authored-diagram':r=>r.samples[3].stages[1].authoredSource='other',
  'unknown-route-sample':r=>r.samples[0].route='/other/'
};
test('complete finite source-bound repeated lab vector passes (unit metadata only)',()=>{const {report,expected}=fixture();assert.equal(qualifyLab(report,expected).result,'pass');});
for(const [name,mutate] of Object.entries(mutants)) test('lab qualification refuses '+name,()=>{const {report,expected}=fixture();mutate(report);assert.equal(qualifyLab(report,expected).result,'fail');});

test('observed zero shift/tasks differs from unsupported unknown',()=>{
  const known=metricSnapshot(snapshot());assert.equal(known.cls.value,0);assert.equal(known.longTasks.value,0);
  const value=snapshot();value.supported=[];const missing=metricSnapshot(value);
  assert.equal(missing.cls.value,null);assert.equal(missing.longTasks.value,null);assert.equal(missing.lcp.value,null);
});
test('LCP is latest observed candidate rather than first paint or average',()=>{
  const value=snapshot();value.entries['largest-contentful-paint'].push({startTime:420,size:120});assert.equal(metricSnapshot(value).lcp.value,420);
});
test('layout shift session windows separate one-second gaps and five-second durations',()=>{
  const values=[0,900,1800,2700,3600,4500,5000].map(startTime=>({startTime,value:0.1,hadRecentInput:false}));
  assert.ok(Math.abs(cumulativeLayoutShift(values)-0.6)<1e-9);
  assert.equal(cumulativeLayoutShift([{startTime:0,value:0.1,hadRecentInput:false},{startTime:1000,value:0.2,hadRecentInput:false}]),0.2);
});
test('recent ordinary input shifts are excluded without suppressing retained raw entries',()=>{
  assert.equal(cumulativeLayoutShift([{startTime:1,value:0.9,hadRecentInput:true},{startTime:10,value:0.1,hadRecentInput:false}]),0.1);
});
test('invalid shift values and missing recent-input identity are refused',()=>{
  for(const entry of [{startTime:1,value:-1,hadRecentInput:false},{startTime:1,value:0.1},{startTime:NaN,value:0.1,hadRecentInput:false}]) assert.throws(()=>cumulativeLayoutShift([entry]));
});
test('long tasks retain duration count and maximum without claiming total CPU',()=>{
  const value=snapshot();value.entries.longtask=[{startTime:1,duration:60},{startTime:80,duration:120}];const result=metricSnapshot(value).longTasks;
  assert.equal(result.value,180);assert.equal(result.count,2);assert.equal(result.maximumMs,120);
});
test('invalid long-task durations remain unknown',()=>{const value=snapshot();value.entries.longtask=[{startTime:1,duration:-1}];assert.equal(metricSnapshot(value).longTasks.value,null);});
test('run distribution includes spread and explicit nearest-rank lab percentile',()=>{
  const value=distribution([300,100,200]);assert.equal(value.median,200);assert.equal(value.mean,200);assert.equal(value.p75NearestRank,300);assert.equal(value.minimum,100);assert.equal(value.maximum,300);assert.ok(value.populationStddev>0);
});
test('distribution rejects unknown zero-coercion or empty observations',()=>{for(const value of [[],[null],[undefined],[NaN],[Infinity],[-1],['0']]) assert.throws(()=>distribution(value));});
test('incomplete metric groups are not silently given zero distributions',()=>{const {report}=fixture();report.samples[0].stages[0].metrics.lcp={availability:'unobserved',value:null};assert.equal(distributions(report.samples)['/plain/'].cold.lcp.value,null);});
test('CDP acknowledgement records every exact requested profile setting',async()=>{const records=[];await applyProfile({send:async method=>method==='Network.emulateNetworkConditionsByRule'?{ruleIds:['actual-ack']} :{}},records);assert.equal(records.length,7);assert.ok(records.every(r=>r.accepted));assert.equal(records[3].params.rate,4);});
test('unsupported CDP command retains refusal and does not fall back to unthrottled measurement',async()=>{const records=[];await assert.rejects(applyProfile({send:async method=>{if(method==='Emulation.setCPUThrottlingRate')throw new Error('unsupported');return {};}},records),/unavailable/);assert.equal(records.at(-1).accepted,false);assert.match(records.at(-1).error,/unsupported/);});
test('unsupported engine and insufficient runs refuse before opening a browser',async()=>{await assert.rejects(measureLab({engine:'webkit'}),/only by Chromium/);await assert.rejects(measureLab({samples:1}),/three to ten/);});

function observerRealm(supported) {
  const observers=[];
  class Observer {
    static supportedEntryTypes=supported;
    constructor(callback){this.callback=callback;this.records=[];this.disconnected=false;observers.push(this);}
    observe(options){this.options=options;}
    takeRecords(){const values=this.records;this.records=[];return values;}
    disconnect(){this.disconnected=true;}
  }
  const context={PerformanceObserver:Observer,window:{},performance:{now:()=>1500,timeOrigin:1},document:{visibilityState:'visible',readyState:'complete'},innerWidth:390,innerHeight:844,devicePixelRatio:1,navigator:{onLine:true,userAgent:'unit',maxTouchPoints:1}};
  vm.runInNewContext('('+installLabObserver.toString()+')()',context);return {context,observers};
}
test('observer installs buffered entry-type subscriptions before collection',()=>{const {observers}=observerRealm(['largest-contentful-paint','layout-shift','longtask']);assert.equal(observers.length,3);assert.ok(observers.every(o=>o.options.buffered===true));});
test('observer drains pending records once and preserves candidate element attribution',()=>{
  const {context,observers}=observerRealm(['largest-contentful-paint']);observers[0].records=[{entryType:'largest-contentful-paint',startTime:100,duration:0,renderTime:100,loadTime:90,size:100,url:'',element:{tagName:'H1',id:'title',textContent:'Owned text'}}];
  assert.equal(context.window.__bijuxLab.snapshot().entries['largest-contentful-paint'].length,1);assert.equal(context.window.__bijuxLab.snapshot().entries['largest-contentful-paint'].length,1);assert.equal(context.window.__bijuxLab.snapshot().entries['largest-contentful-paint'][0].element.tag,'H1');
});
test('observer missing API types remains explicit and owned observers disconnect',()=>{const {context,observers}=observerRealm(['layout-shift']);assert.equal(context.window.__bijuxLab.snapshot().supported.length,1);context.window.__bijuxLab.disconnect();assert.ok(observers.every(o=>o.disconnected));});
test('observer reports dropped buffered entries rather than certifying complete measurements',()=>{const {context,observers}=observerRealm(['longtask']);observers[0].callback({getEntries:()=>[]},observers[0],{droppedEntriesCount:2});assert.equal(context.window.__bijuxLab.snapshot().droppedEntries,2);});

test('reused transport producer matches actual selected committed source before lab launch',()=>{const path=require('node:path');const {execFileSync}=require('node:child_process');const root=path.resolve(__dirname,'../../..');const sha=execFileSync('git',['-C',root,'rev-parse','HEAD']).toString().trim();assert.equal(Object.keys(fixtureProducer(root,sha)).length,3);});
