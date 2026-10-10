'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {execFileSync}=require('node:child_process');
const {gzipSync}=require('node:zlib');
const {byteObservation,digest,qualifyJourney}=require('./transport-evidence.cjs');
const {startServer}=require('./transport-server.cjs');
const {sourceAssets,VENDOR_PATH,AUTHORED_SOURCE}=require('./transport.cjs');

function contractVector() {
  const origin='http://127.0.0.1:43871',body=Buffer.from('owned contract-vector bytes');
  const asset={source:'shared/bijux-docs/assets/vendor.js',bytes:body.length,sha256:digest(body)};
  const expected={origin,sha:'ab'.repeat(20),tree:'cd'.repeat(20),assets:{[VENDOR_PATH]:asset},vendorPath:VENDOR_PATH,authoredSource:AUTHORED_SOURCE};
  const response={url:origin+VENDOR_PATH,status:200,decodedBodyBytes:body.length,decodedBodySha256:digest(body)};
  const resource={name:origin+VENDOR_PATH,transferSize:310,encodedBodySize:10,decodedBodySize:body.length};
  const server={path:VENDOR_PATH,status:200,rawBytes:body.length,rawSha256:digest(body),encodedBodyBytes:10};
  const stage=(name,url,contextSetup,contextIdentity,timeOrigin)=>({name,url:origin+url,contextSetup,contextIdentity,timeOrigin,requests:[],responses:[],resources:[],serverResponses:[],pageErrors:[],actionError:null});
  const plain=stage('plain-cold','/plain/','fresh-isolated-context','plain-context',1000);plain.rendererPresent=false;
  const cold=stage('diagram-cold','/diagram/','fresh-isolated-context','diagram-context',2000);
  Object.assign(cold,{priorAssetRequests:0,rendered:true,authoredSource:AUTHORED_SOURCE,responses:[response],resources:[resource],serverResponses:[server]});
  const warm=stage('diagram-warm','/diagram/?warm=1','same-context-new-document','diagram-context',3000);
  Object.assign(warm,{primedBy:'diagram-cold',rendered:true,authoredSource:AUTHORED_SOURCE,responses:[structuredClone(response)],resources:[{...resource,transferSize:0}]});
  const theme=stage('diagram-theme','/diagram/?warm=1','same-document-library-reuse','diagram-context',3000);
  Object.assign(theme,{rendered:true,authoredSource:AUTHORED_SOURCE,svgIdentityChanged:true});
  return {report:{state:'complete',browserClosed:true,serverClosed:true,source:{sha:expected.sha,tree:expected.tree},origin,assets:structuredClone(expected.assets),stages:[plain,cold,warm,theme]},expected};
}

test('complete compatible contract vector qualifies while preserving separate cache mechanisms',()=>{
  const {report,expected}=contractVector();assert.deepEqual(qualifyJourney(report,expected),{result:'pass',errors:[]});
});

const mutants={
  'missing timing entry refuses actual-size qualification': r=>r.stages[1].resources=[],
  'wrong vendor timing URL cannot qualify another response':r=>r.stages[1].resources[0].name+='/wrong',
  'wrong actual document URL cannot redefine expected route':r=>{r.stages[1].url+='/wrong';r.stages[1].expectedPath='/diagram//wrong';},
  'foreign observation origin cannot reuse same body':r=>r.origin='http://foreign.invalid',
  'stale committed source refuses byte-identical observations':r=>r.source.sha='ef'.repeat(20),
  'stale committed tree refuses':r=>r.source.tree='ef'.repeat(20),
  'stale inventory refuses even unchanged body observations':r=>r.assets[VENDOR_PATH].sha256='0'.repeat(64),
  'missing body observation does not become unknown successful transfer':r=>r.stages[1].responses=[],
  'different decoded actual bytes refuse':r=>r.stages[1].responses[0].decodedBodySha256='0'.repeat(64),
  'changed actual encoded server representation refuses timing mismatch':r=>r.stages[1].serverResponses[0].encodedBodyBytes=11,
  'cold warming cannot masquerade as first fresh transfer':r=>r.stages[1].priorAssetRequests=1,
  'cold shared context cannot masquerade as isolated context':r=>r.stages[1].contextIdentity='plain-context',
  'cached zero cannot masquerade as cold transfer':r=>r.stages[1].resources[0].transferSize=0,
  'zero encoded body is not a missing-value substitute':r=>r.stages[1].resources[0].encodedBodySize=0,
  'null encoded body remains unavailable':r=>r.stages[1].resources[0].encodedBodySize=null,
  'masked decoded zero cannot certify a nonempty source':r=>r.stages[1].resources[0].decodedBodySize=0,
  'missing warm cache priming refuses':r=>r.stages[2].primedBy=null,
  'warm changed context cannot reuse a different cache proof':r=>r.stages[2].contextIdentity='other-context',
  'same realm library reuse is not a new-document HTTP cache observation':r=>r.stages[2].timeOrigin=r.stages[1].timeOrigin,
  'warm server retransmission refuses even with reported zero':r=>r.stages[2].serverResponses=structuredClone(r.stages[1].serverResponses),
  'nonzero warm transfer cannot qualify local HTTP cache':r=>r.stages[2].resources[0].transferSize=310,
  'plain request exposes eager diagram delivery':r=>r.stages[0].requests=[{url:r.origin+VENDOR_PATH}],
  'plain ResourceTiming exposes eager diagram delivery':r=>r.stages[0].resources=structuredClone(r.stages[1].resources),
  'plain server observation exposes eager delivery':r=>r.stages[0].serverResponses=structuredClone(r.stages[1].serverResponses),
  'plain renderer global cannot substitute for zero request count':r=>r.stages[0].rendererPresent=true,
  'theme library network request refuses memoized reuse':r=>r.stages[3].requests=[{url:r.origin+VENDOR_PATH}],
  'theme authored source drift refuses successful-looking SVG':r=>r.stages[3].authoredSource='changed graph',
  'theme unchanged SVG identity refuses stale render':r=>r.stages[3].svgIdentityChanged=false,
  'ordinary action failure stays failed with complete-looking metadata':r=>r.stages[2].actionError='Native input timed out',
  'cancelled journey cannot qualify partial observations':r=>r.state='running',
  'active server cannot qualify terminal result':r=>r.serverClosed=false,
  'active browser cannot qualify terminal result':r=>r.browserClosed=false
};
for(const [name,mutate] of Object.entries(mutants)) test(name,()=>{
  const {report,expected}=contractVector();mutate(report);const result=qualifyJourney(report,expected);assert.equal(result.result,'fail');assert.ok(result.errors.length);
});

test('actual observed zero and unavailable byte values remain distinct',()=>{
  assert.deepEqual(byteObservation(0,'same-origin API'),{value:0,unit:'bytes',availability:'reported',basis:'same-origin API'});
  assert.equal(byteObservation(null,'no packet capture').availability,'unobserved');
  for(const value of [undefined,false,-1,0.2,'0']) assert.throws(()=>byteObservation(value,'API'));
});

test('source selection reads actual committed large vendor without default subprocess truncation',()=>{
  const root=path.resolve(__dirname,'../../..'),sha=execFileSync('git',['-C',root,'rev-parse','HEAD']).toString().trim();
  const result=sourceAssets(root,sha);
  assert.ok(result.assets[VENDOR_PATH].length>1024*1024);assert.equal(result.manifest[VENDOR_PATH].sha256,digest(result.assets[VENDOR_PATH]));
  assert.equal(result.identity.sha,sha);
  for(const abbreviated of ['main',sha.slice(0,12),'AB'.repeat(20)]) assert.throws(()=>sourceAssets(root,abbreviated),/exact full/);
});

test('actual controlled gzip response records encoded body separately from decoded fetch bytes',async()=>{
  const body=Buffer.from('owned source representation '.repeat(100));
  const server=await startServer({assets:{[VENDOR_PATH]:body},vendorPath:VENDOR_PATH,authoredSource:AUTHORED_SOURCE});
  try {
    const response=await fetch(server.origin+VENDOR_PATH);const decoded=Buffer.from(await response.arrayBuffer());
    assert.equal(response.headers.get('content-encoding'),'gzip');assert.equal(response.headers.get('cache-control'),'public, max-age=3600');
    assert.deepEqual(decoded,body);
    const observed=server.responses.find(r=>r.path===VENDOR_PATH);assert.equal(observed.rawBytes,body.length);assert.equal(observed.encodedBodyBytes,gzipSync(body).length);assert.ok(observed.encodedBodyBytes<observed.rawBytes);
  } finally {await server.close();}
});

test('actual controlled no-store identity responses retain fresh server replies',async()=>{
  const body=Buffer.from('uncached owned source');
  const server=await startServer({assets:{[VENDOR_PATH]:body},vendorPath:VENDOR_PATH,authoredSource:AUTHORED_SOURCE,encoding:'identity',cacheControl:'no-store'});
  try {
    for(let i=0;i<2;i++) {const response=await fetch(server.origin+VENDOR_PATH);assert.equal(response.headers.get('content-encoding'),null);assert.equal(response.headers.get('cache-control'),'no-store');await response.arrayBuffer();}
    assert.equal(server.responses.filter(r=>r.path===VENDOR_PATH).length,2);
    assert.ok(server.responses.every(r=>r.encodedBodyBytes===body.length));
  } finally {await server.close();}
});

test('actual controlled missing vendor refuses without silently serving another asset',async()=>{
  const server=await startServer({assets:{[VENDOR_PATH]:Buffer.from('owned')},vendorPath:VENDOR_PATH,authoredSource:AUTHORED_SOURCE,vendorFault:'missing'});
  try {const response=await fetch(server.origin+VENDOR_PATH);assert.equal(response.status,404);assert.equal((await response.arrayBuffer()).byteLength,0);} finally {await server.close();}
});

test('server rejects undeclared cache and response mutation boundaries before listening',async()=>{
  for(const options of [{cacheControl:'unknown'},{encoding:'unknown'},{vendorFault:'unknown'}]) await assert.rejects(startServer({assets:{},vendorPath:VENDOR_PATH,authoredSource:AUTHORED_SOURCE,...options}));
});
