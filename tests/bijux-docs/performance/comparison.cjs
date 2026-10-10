#!/usr/bin/env node
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {parseArgs,isDeepStrictEqual:same}=require('node:util');
const {execFileSync}=require('node:child_process');
const {digest}=require('./lab-evidence.cjs');
const {sourceAssets,VENDOR_PATH,AUTHORED_SOURCE}=require('./transport.cjs');
const {documentHtml}=require('./transport-server.cjs');
const {prepareEvidence,compareRepeated,comparePairedCache}=require('./comparison-evidence.cjs');
function pinnedJSON(file,pin,root) {
  if(!/^[0-9a-f]{64}$/.test(pin||'')) throw new Error('Select externally reviewed full input SHA256');
  const absolute=fs.realpathSync(file);
  if(!absolute.startsWith(path.join(root,'artifacts')+path.sep)) throw new Error('Comparison inputs must belong to owning artifacts');
  const bytes=fs.readFileSync(absolute);if(digest(bytes)!==pin) throw new Error('Pinned measurement input changed: '+file);
  return {path:absolute,sha256:pin,bytes:bytes.length,value:JSON.parse(bytes)};
}
function git(root,args) {return execFileSync('git',['-C',root,...args],{maxBuffer:8*1024*1024});}
function sourceIdentity(root,sha) {
  if(!/^[0-9a-f]{40}$/.test(sha||'')) throw new Error('Select full committed comparator source');
  if(fs.realpathSync(git(root,['rev-parse','--show-toplevel']).toString().trim())!==root||git(root,['rev-parse','HEAD']).toString().trim()!==sha) throw new Error('Comparator source differs from selected current root/head');
  const origin=git(root,['remote','get-url','origin']).toString().trim();
  if(!['https://github.com/bijux/bijux-std.git','git@github.com:bijux/bijux-std.git'].includes(origin)) throw new Error('Comparator source must be bijux-std GitHub');
  return {sha,tree:git(root,['rev-parse',sha+'^{tree}']).toString().trim(),origin};
}
function independentOwner(root,family,report,owner) {
  if(report.qualification?.result!=='pass') throw new Error('Prior failed/incomplete measurement remains unavailable: '+(report.qualification?.errors||[]).join('; '));
  const recorded=report.source;
  if(!recorded||!/^[0-9a-f]{40}$/.test(recorded.sha||'')||git(root,['rev-parse',recorded.sha+'^{tree}']).toString().trim()!==recorded.tree) throw new Error('Recorded measurement source differs from actual committed identity');
  if(!['https://github.com/bijux/bijux-std.git','git@github.com:bijux/bijux-std.git'].includes(recorded.origin)) throw new Error('Recorded measurement origin unavailable');
  const ownerNames=Object.keys(report.harness||{}).filter(name=>!['README.md','lab.test.cjs','interaction.test.cjs'].includes(name));
  if(!ownerNames.length) throw new Error('Measured source owner fingerprints missing');
  for(const name of ownerNames) {
    const absolute=path.resolve(__dirname,name);
    if(!absolute.startsWith(path.join(root,'tests/bijux-docs')+path.sep)) throw new Error('Measured harness owner escapes test domain');
    const relative=path.relative(root,absolute),bytes=git(root,['show','HEAD:'+relative]);
    if(digest(bytes)!==report.harness[name].sha256||bytes.length!==report.harness[name].bytes||!bytes.equals(fs.readFileSync(absolute))) throw new Error('Measured source owner/observer differs from current admitted adapter: '+name);
  }
  if(family==='lab') {
    const selected=sourceAssets(root,recorded.sha),fixtureProducer={};
    for(const name of ['transport.cjs','transport-server.cjs','transport-evidence.cjs']) {
      const relative='tests/bijux-docs/performance/'+name,bytes=git(root,['show',recorded.sha+':'+relative]);fixtureProducer[relative]={bytes:bytes.length,sha256:digest(bytes)};
      if(!bytes.equals(fs.readFileSync(path.join(root,relative)))) throw new Error('Historical finite fixture producer differs from admitted recipe');
    }
    const documents=Object.fromEntries(['/plain/','/diagram/'].map(route=>{const bytes=Buffer.from(documentHtml(route==='/diagram/',{vendorPath:VENDOR_PATH,authoredSource:AUTHORED_SOURCE}));return [route,{sha256:digest(bytes),bytes:bytes.length}];}));
    return {source:selected.identity,assets:selected.manifest,documents,fixtureProducer};
  }
  if(family==='interaction') {
    if(!owner||owner.sha256!==report.fixtureManifestSha256) throw new Error('Externally pinned interaction fixture owner is required');
    const fixture=owner.value;
    for(const [name,pin] of Object.entries({...fixture.sourceInputs,...fixture.assetSourceInputs})) if(digest(git(root,['show',recorded.sha+':shared/bijux-docs/'+name]))!==pin) throw new Error('Exact interaction source input differs: '+name);
    return {source:recorded,accepted:fixture.accepted,fixtureManifestSha256:owner.sha256,siteFiles:fixture.siteFiles,sourceInputs:fixture.sourceInputs,assetSourceInputs:fixture.assetSourceInputs,configuration:fixture.configuration,toolchain:fixture.toolchain};
  }
  throw new Error('Unsupported measurement family; retained transport/field gaps stay unavailable');
}
function harnessIdentity() {
  return Object.fromEntries(['comparison.cjs','comparison-evidence.cjs','comparison.test.cjs','README.md'].map(name=>{const bytes=fs.readFileSync(path.join(__dirname,name));return [name,{bytes:bytes.length,sha256:digest(bytes)}];}));
}
function compareMeasurementFiles({sourceRoot,sourceSha,family,mode,baseline,baselineSha256,candidate,candidateSha256,baselineRuntimeProof,baselineRuntimeProofSha256,candidateRuntimeProof,candidateRuntimeProofSha256,baselineOwner,baselineOwnerSha256,candidateOwner,candidateOwnerSha256,output}) {
  const root=fs.realpathSync(sourceRoot),source=sourceIdentity(root,sourceSha),harness=harnessIdentity();
  let target=null;
  if(output) {
    target=path.resolve(root,output);
    if(!target.startsWith(path.join(root,'artifacts')+path.sep)) throw new Error('Comparison output must remain under owning artifacts');
    if(fs.existsSync(target)) throw new Error('Comparison output already exists; preserve retained evidence and choose a fresh destination');
  }
  const result={schema:1,state:'running',source,scope:'offline comparison of pinned independently requalified finite measured populations; no new browser or build',family,mode,inputs:[],harness,
    fieldINP:{availability:'unavailable',value:null,reason:'No field population measured'},budget:{availability:'unavailable',value:null,reason:'No measurement budget or optimization threshold invented'}};
  const rawInputs=[];
  function load(file,pin,runtimeFile,runtimePin,ownerFile,ownerPin) {
    const raw=pinnedJSON(file,pin,root),proof=runtimeFile?pinnedJSON(runtimeFile,runtimePin,root):null,owner=ownerFile?pinnedJSON(ownerFile,ownerPin,root):null;
    rawInputs.push(raw,...(proof?[proof]:[]),...(owner?[owner]:[]));
    result.inputs.push({path:raw.path,sha256:raw.sha256,bytes:raw.bytes,measurementSource:raw.value.source,acceptedFixture:raw.value.accepted||null,
      historicalRelativeToCurrentTool:raw.value.source?.sha!==source.sha,runtimeProof:proof?{path:proof.path,sha256:proof.sha256}:null,owner:owner?{path:owner.path,sha256:owner.sha256}:null});
    const expected=independentOwner(root,family,raw.value,owner);
    return prepareEvidence({family,report:raw.value,expected,runtimeProof:proof?.value,artifactSha256:raw.sha256});
  }
  try {
    const left=load(baseline,baselineSha256,baselineRuntimeProof,baselineRuntimeProofSha256,baselineOwner,baselineOwnerSha256);
    if(mode==='paired-cache') {
      if(candidate) throw new Error('Paired-cache uses one actual qualified execution, not a second candidate');
      result.comparison=comparePairedCache(left);
    } else if(mode==='repeated-run') {
      if(!candidate) throw new Error('Repeated-run requires a distinct independently pinned candidate execution');
      const right=load(candidate,candidateSha256,candidateRuntimeProof,candidateRuntimeProofSha256,candidateOwner,candidateOwnerSha256);result.comparison=compareRepeated(left,right);
    } else throw new Error('Select explicit paired-cache or repeated-run comparison mode');
    result.state='complete';result.result=result.comparison.result;
  } catch(error) {result.state='refused';result.result='unavailable';result.comparison={result:'unavailable',comparisons:[],reason:error.message};}
  result.inputsUnchanged=rawInputs.every(raw=>digest(fs.readFileSync(raw.path))===raw.sha256);result.harnessUnchanged=same(harness,harnessIdentity());result.sourceUnchanged=same(source,sourceIdentity(root,sourceSha));
  if(!result.inputsUnchanged||!result.harnessUnchanged||!result.sourceUnchanged) {result.result='unavailable';result.comparison={result:'unavailable',comparisons:[],reason:'Input/source/harness changed during offline comparison'};}
  if(output) {
    fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,JSON.stringify(result,null,2)+'\n');
  }
  return result;
}
function main() {
  const names=['source-root','source-sha','family','mode','baseline','baseline-sha256','candidate','candidate-sha256','baseline-runtime-proof','baseline-runtime-proof-sha256','candidate-runtime-proof','candidate-runtime-proof-sha256','baseline-owner','baseline-owner-sha256','candidate-owner','candidate-owner-sha256','output'];
  const {values}=parseArgs({options:Object.fromEntries(names.map(name=>[name,{type:'string'}]))});
  if(!values.output) throw new Error('Select owning --output');
  const options=Object.fromEntries(Object.entries(values).map(([name,value])=>[name.replace(/-([a-z])/g,(_,letter)=>letter.toUpperCase()),value]));
  const result=compareMeasurementFiles(options);process.stdout.write(JSON.stringify({result:result.result,state:result.state,mode:result.mode,comparisons:result.comparison.comparisons.length,reason:result.comparison.reason||null,output:values.output})+'\n');process.exitCode=result.result==='observed'?0:1;
}
module.exports={pinnedJSON,sourceIdentity,independentOwner,harnessIdentity,compareMeasurementFiles};
if(require.main===module) {try {main();} catch(error) {process.stderr.write(error.stack+'\n');process.exitCode=1;}}
