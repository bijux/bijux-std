'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {PROFILE,commandsForProfile,metricSnapshot,digest}=require('./lab-evidence.cjs');
const {VENDOR_PATH,AUTHORED_SOURCE}=require('./transport.cjs');
const {runtimeIdentity,prepareEvidence,arithmetic,compareRepeated,comparePairedCache}=require('./comparison-evidence.cjs');
const {pinnedJSON,sourceIdentity,compareMeasurementFiles}=require('./comparison.cjs');
function rawVector() {
  const source={origin:'https://github.com/bijux/bijux-std.git',sha:'a'.repeat(40),tree:'b'.repeat(40)},origin='http://127.0.0.1:12345';
  const assets={[VENDOR_PATH]:{sha256:'c'.repeat(64),bytes:1000}},documents={'/plain/':{sha256:'d'.repeat(64),bytes:100},'/diagram/':{sha256:'e'.repeat(64),bytes:200}},fixtureProducer={owned:{sha256:'f'.repeat(64),bytes:10}};
  const expected={source,assets,documents,fixtureProducer};
  const report={source,assets,documents,fixtureProducer,origin,state:'complete',browserClosed:true,serverClosed:true,harnessUnchanged:true,profile:PROFILE,profileSha256:digest(JSON.stringify(PROFILE)),requestedSamples:3,samples:[],qualification:{result:'pass'},scope:'unit metadata only, no browser observation',harness:{'lab.cjs':{sha256:'1'.repeat(64),bytes:100}},
    runtime:{node:'v24.21.0',nodeExecutable:'/node',nodeExecutableSha256:'2'.repeat(64),playwright:'1.58.2',playwrightPackageSha256:'3'.repeat(64),browserVersion:'145.0.7632.6',browserExecutable:'/browser',browserExecutableSha256:'4'.repeat(64),host:{platform:'unit',cpuModel:'unit'}}};
  for(const route of ['/plain/','/diagram/']) for(let i=0;i<3;i++) {
    const sample={route,sample:i+1,contextId:route+i,contextClosed:true,commands:commandsForProfile().map(value=>({...value,accepted:true,response:value.method==='Network.emulateNetworkConditionsByRule'?{ruleIds:['unit']}:{}})),stages:[]};
    for(const cacheState of ['cold','warm']) {
      const snapshot={supported:['largest-contentful-paint','layout-shift','longtask'],entries:{'largest-contentful-paint':[{startTime:cacheState==='cold'?100+i:80+i}], 'layout-shift':[],longtask:[]},errors:[],droppedEntries:0,
        observationEndMs:1500,timeOrigin:100+i*2+(cacheState==='warm'?1:0),visibility:'visible',readyState:'complete',viewport:{width:390,height:844,deviceScaleFactor:1},navigator:{onLine:true}};
      sample.stages.push({cacheState,url:origin+route,actionError:null,pageErrors:[],snapshot,metrics:metricSnapshot(snapshot),observationHoldMs:1000,primedBy:cacheState==='warm'?'cold':null,
        responses:[{url:origin+route,status:200,decodedBodySha256:documents[route].sha256,decodedBodyBytes:documents[route].bytes}],serverResponses:route==='/diagram/'&&cacheState==='cold'?[{path:VENDOR_PATH}]:[],
        resources:route==='/diagram/'?[{name:origin+VENDOR_PATH,decodedBodySize:1000,transferSize:cacheState==='cold'?500:0}]:[],rendererPresent:route==='/diagram/',rendered:route==='/diagram/',authoredSource:route==='/diagram/'?AUTHORED_SOURCE:null});
    }
    report.samples.push(sample);
  }
  return {report,expected};
}
function prepared(pin='5'.repeat(64)) {const value=rawVector();return structuredClone(prepareEvidence({family:'lab',...value,artifactSha256:pin}));}
function independentPair() {
  const left=prepared(),right=prepared('6'.repeat(64));for(const population of right.populations) for(const id of population.ids) {id.contextId+='-independent';id.timeOrigin+=10000;}
  return {left,right};
}
test('paired lab contrast derives actual raw unit-vector arithmetic, not saved distributions (no browser claim)',()=>{
  const {report,expected}=rawVector();report.distributions={fabricated:1000000};const evidence=prepareEvidence({family:'lab',report,expected,artifactSha256:'5'.repeat(64)});
  const result=comparePairedCache(evidence);assert.equal(result.result,'observed');assert.equal(result.comparisons.length,6);assert.equal(result.comparisons[0].medianDifference,-20);assert.deepEqual(result.comparisons[0].signedPairedDifferences,[-20,-20,-20]);
});
test('independent compatible unit populations retain zero measured arithmetic without improvement claim',()=>{const {left,right}=independentPair();const result=compareRepeated(left,right);assert.equal(result.result,'observed');assert.equal(result.comparisons[0].medianDifference,0);});
const differences={
  'source':value=>value.signature.source.sha='7'.repeat(40),
  'source-tree':value=>value.signature.source.tree='7'.repeat(40),
  'fixture-assets':value=>value.signature.fixture.assets={},
  'fixture-documents':value=>value.signature.fixture.documents={},
  'fixture-recipe':value=>value.signature.fixture.producer={},
  'viewport':value=>value.signature.profile.viewport.width=320,
  'physical-mobile-claim':value=>value.signature.profile.isMobile=true,
  'cpu-profile':value=>value.signature.profile.cpuSlowdown=1,
  'network-profile':value=>value.signature.profile.network.latency=0,
  'cache-policy':value=>value.signature.cache.policy='no-store',
  'browser-runtime':value=>value.signature.runtime.browserVersion='other',
  'browser-executable':value=>value.signature.runtime.browserExecutableSha256='0'.repeat(64),
  'node-runtime':value=>value.signature.runtime.node='other',
  'package-runtime':value=>value.signature.runtime.playwrightPackageSha256='0'.repeat(64),
  'host':value=>value.signature.runtime.host.cpuModel='other',
  'observer-owner':value=>value.signature.harness={},
  'measurement-family':value=>value.signature.family='interaction',
  'metric-kind':value=>value.signature.semantics.lcp='not LCP',
  'observation-horizon':value=>value.signature.population[0].horizon=10,
  'population-count':value=>value.signature.population[0].samples=1,
  'metric-unit':value=>value.signature.population[0].unit='bytes'
};
for(const [name,mutate] of Object.entries(differences)) test('repeated comparison refuses incompatible '+name,()=>{const {left,right}=independentPair();mutate(right);assert.equal(compareRepeated(left,right).result,'unavailable');});
test('duplicate artifact does not certify a distinct execution',()=>{const left=prepared();assert.equal(compareRepeated(left,structuredClone(left)).result,'unavailable');});
test('different artifact digest with identical execution IDs remains duplicate evidence',()=>{const left=prepared(),right=structuredClone(left);right.artifactSha256='6'.repeat(64);assert.equal(compareRepeated(left,right).result,'unavailable');});
test('cold/warm contrast refuses unprimed same-document or wrong context pairing',()=>{
  for(const mutate of [value=>value.populations.find(item=>item.stage==='warm'&&item.metric==='lcp').ids[0].contextId='other',value=>value.populations.find(item=>item.stage==='warm'&&item.metric==='lcp').ids[0].timeOrigin=value.populations[0].ids[0].timeOrigin]) {
    const value=prepared();mutate(value);assert.equal(comparePairedCache(value).result,'unavailable');
  }
});
test('cold/warm contrast is not defined for ordinary same-document interaction cycles',()=>{const value=prepared();value.family='interaction';assert.equal(comparePairedCache(value).result,'unavailable');});
test('zero measured baseline preserves arithmetic but percentage remains unavailable',()=>{
  const value=arithmetic([0,0,0],[0,0,0]);assert.equal(value.medianDifference,0);assert.equal(value.medianRelativePercentage,null);assert.equal(value.relativePercentage.availability,'unavailable');
});
test('unknown/nonfinite/negative/partial values cannot become measured zero',()=>{
  for(const value of [null,undefined,NaN,Infinity,-1]) assert.equal(arithmetic([value],[0]).availability,'unavailable');
  assert.equal(arithmetic([0,1],[0]).availability,'unavailable');assert.equal(arithmetic([],[]).availability,'unavailable');
});
test('partial normalized observations remain unavailable',()=>{const {left,right}=independentPair();right.populations[0].observed=false;assert.equal(compareRepeated(left,right).result,'unavailable');});
test('prior failed packet remains failed despite plausible metric values',()=>{const value=rawVector();value.report.qualification.result='fail';assert.throws(()=>prepareEvidence({family:'lab',...value,artifactSha256:'5'.repeat(64)}),/Prior failed/);});
test('raw invalid metric is independently refused despite saved passing result',()=>{const value=rawVector();value.report.samples[0].stages[0].metrics.lcp.value=0;assert.throws(()=>prepareEvidence({family:'lab',...value,artifactSha256:'5'.repeat(64)}),/Raw lab/);});
test('unsupported raw API is independently refused rather than comparing a saved distribution',()=>{const value=rawVector();value.report.samples[0].stages[0].snapshot.supported=[];assert.throws(()=>prepareEvidence({family:'lab',...value,artifactSha256:'5'.repeat(64)}),/Raw lab/);});
test('source/config authority is mandatory rather than trusted from the report itself',()=>{const value=rawVector();assert.throws(()=>prepareEvidence({family:'lab',report:value.report,artifactSha256:'5'.repeat(64)}),/Independent source/);});
test('missing browser fingerprint refuses cross-execution runtime compatibility',()=>{const {report}=rawVector();delete report.runtime.browserExecutableSha256;assert.throws(()=>runtimeIdentity(report),/fingerprint unavailable/);});
test('pinned supplemental physical proof binds matching selected runtime only',()=>{
  const {report}=rawVector();delete report.runtime.browserExecutableSha256;const proof={'/node':{sha256:'2'.repeat(64)},'/browser':{sha256:'4'.repeat(64)}};
  assert.equal(runtimeIdentity(report,proof).browserExecutableSha256,'4'.repeat(64));proof['/node'].sha256='0'.repeat(64);assert.throws(()=>runtimeIdentity(report,proof),/differs/);
});
test('unreviewed report input cannot certify a measured population',()=>{assert.throws(()=>prepareEvidence({family:'lab',...rawVector()}),/Externally pinned/);});
test('actual file pin detects modified observation bytes before parsing',()=>{
  const root=path.resolve(__dirname,'../../..'),dir=path.join(root,'artifacts/qualification/payload-measurement-comparison/unit-files');fs.mkdirSync(dir,{recursive:true});const file=path.join(dir,'owned.json');fs.writeFileSync(file,'{"value":1}\n');const pin=digest(fs.readFileSync(file));assert.equal(pinnedJSON(file,pin,root).value.value,1);fs.writeFileSync(file,'{"value":0}\n');assert.throws(()=>pinnedJSON(file,pin,root),/input changed/);
});
test('comparison refuses floating or foreign selected source before artifact processing',()=>{const root=path.resolve(__dirname,'../../..');assert.throws(()=>sourceIdentity(root,'main'),/full committed/);assert.throws(()=>sourceIdentity(root,'0'.repeat(40)),/current root\/head/);});

test('comparison cannot overwrite an existing owned observation or snapshot',()=>{
  const root=path.resolve(__dirname,'../../..'),file=path.join(root,'artifacts/qualification/payload-measurement-comparison/unit-files/retained.json');fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,'{\"retained\":true}\n');
  const sourceSha=require('node:child_process').execFileSync('git',['-C',root,'rev-parse','HEAD']).toString().trim();
  assert.throws(()=>compareMeasurementFiles({sourceRoot:root,sourceSha,output:file}),/output already exists/);assert.equal(fs.readFileSync(file,'utf8'),'{\"retained\":true}\n');
});

test('one reused source execution among otherwise changed samples refuses independent comparison',()=>{
  const {left,right}=independentPair();right.populations[0].ids[0]=structuredClone(left.populations[0].ids[0]);
  assert.equal(compareRepeated(left,right).result,'unavailable');
});
test('partial identity reuse remains refused when sample order differs',()=>{
  const {left,right}=independentPair();right.populations[0].ids[2]=structuredClone(left.populations[0].ids[0]);
  assert.equal(compareRepeated(left,right).result,'unavailable');
});
test('shared deterministic context/sample labels with new actual documents are compatible',()=>{
  const {left,right}=independentPair();for(const [index,population] of right.populations.entries()) for(const [i,id] of population.ids.entries()) id.contextId=left.populations[index].ids[i].contextId;
  assert.equal(compareRepeated(left,right).result,'observed');
});
test('changing a sample label cannot hide reuse of its actual context/document observation',()=>{
  const {left,right}=independentPair();right.populations[0].ids[0]={...left.populations[0].ids[0],sample:99};
  assert.equal(compareRepeated(left,right).result,'unavailable');
});
test('partial repeated interaction cycle/document overlap is refused',()=>{
  const {left,right}=independentPair();for(const value of [left,right]) for(const population of value.populations) population.ids=population.ids.map((id,i)=>({cycle:i+1,timeOrigin:id.timeOrigin}));
  right.populations[0].ids[1]=structuredClone(left.populations[0].ids[0]);assert.equal(compareRepeated(left,right).result,'unavailable');
});
