'use strict';
const {isDeepStrictEqual:same}=require('node:util');
const {PROFILE,digest,distribution,qualifyLab}=require('./lab-evidence.cjs');
const {TRANSITIONS,qualifyInteraction}=require('./interaction-evidence.cjs');
const {VENDOR_PATH,AUTHORED_SOURCE}=require('./transport.cjs');
const unknown=reason=>({availability:'unavailable',value:null,reason});
const finite=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0;
function runtimeIdentity(report,proof) {
  const r=report.runtime;
  if(!r||!r.node||!r.playwright||!r.browserVersion||!r.host||!r.nodeExecutable||!r.browserExecutable||!r.nodeExecutableSha256||!r.playwrightPackageSha256) throw new Error('Exact recorded measurement runtime is unavailable');
  if(!/^[0-9a-f]{64}$/.test(r.nodeExecutableSha256)||!/^[0-9a-f]{64}$/.test(r.playwrightPackageSha256)) throw new Error('Recorded executable/package digests are not full fingerprints');
  const browserSha256=r.browserExecutableSha256||proof?.[r.browserExecutable]?.sha256;
  if(!/^[0-9a-f]{64}$/.test(browserSha256||'')) throw new Error('Selected browser executable fingerprint unavailable; pinned retained runtime proof is required');
  if(proof&&proof[r.nodeExecutable]?.sha256!==r.nodeExecutableSha256) throw new Error('Supplemental physical runtime proof differs from recorded Node executable');
  if(proof&&proof[r.browserExecutable]?.sha256!==browserSha256) throw new Error('Supplemental physical runtime proof differs from recorded browser executable');
  return {node:r.node,nodeExecutableSha256:r.nodeExecutableSha256,playwright:r.playwright,playwrightPackageSha256:r.playwrightPackageSha256,browserVersion:r.browserVersion,browserExecutableSha256:browserSha256,host:r.host,
    scope:'recorded selected executable/package and host fingerprints; no broader browser installation census'};
}
function prepareEvidence({family,report,expected,runtimeProof,artifactSha256}) {
  if(!/^[0-9a-f]{64}$/.test(artifactSha256||'')) throw new Error('Externally pinned raw measurement artifact required');
  if(report.qualification?.result!=='pass') throw new Error('Prior failed/incomplete measurement remains unavailable: '+(report.qualification?.errors||[]).join('; '));
  if(!expected) throw new Error('Independent source/configuration ownership inputs are required');
  let qualification,semantics,fixture,cache,populations;
  if(family==='lab') {
    qualification=qualifyLab(report,{...expected,vendorPath:VENDOR_PATH,authoredSource:AUTHORED_SOURCE});
    if(qualification.result!=='pass') throw new Error('Raw lab observations fail independent qualification: '+qualification.errors.join('; '));
    semantics={lcp:'latest observed candidate at bounded observation end',cls:'maximum unexpected-shift session window',longTasks:'sum of observed durations; not total CPU'};
    fixture={assets:report.assets,documents:report.documents,producer:report.fixtureProducer};cache={encoding:report.profile.encoding,policy:report.profile.cachePolicy,cold:'fresh isolated context cleared enabled cache',warm:'new document in same cold-primed context'};
    populations=[];
    for(const route of ['/plain/','/diagram/']) for(const stage of ['cold','warm']) for(const metric of ['lcp','cls','longTasks']) {
      const values=report.samples.filter(sample=>sample.route===route).map(sample=>({sample:sample.sample,contextId:sample.contextId,stage:sample.stages.find(item=>item.cacheState===stage)}));
      populations.push({key:route+'|'+stage+'|'+metric,route,stage,metric,unit:values[0]?.stage.metrics[metric].unit,values:values.map(value=>value.stage.metrics[metric].value),
        ids:values.map(value=>({sample:value.sample,contextId:value.contextId,timeOrigin:value.stage.snapshot.timeOrigin})),observed:values.every(value=>value.stage.metrics[metric].availability==='observed'&&finite(value.stage.metrics[metric].value)),
        horizon:report.profile.observationHoldMs,scope:semantics[metric]});
    }
  } else if(family==='interaction') {
    qualification=qualifyInteraction(report,expected);
    if(qualification.result!=='pass') throw new Error('Raw interaction observations fail independent qualification: '+[...qualification.errors,...(qualification.eventTiming?.missing||[]).map(value=>value.reason)].join('; '));
    semantics={renderingOpportunity:'trusted input timestamp to first RAF-observed required state; not pixel paint',eventTiming:'single correlated EventTiming estimated next update rounded8ms threshold16ms; not field INP'};
    fixture={accepted:report.accepted,manifestSha256:report.fixtureManifestSha256,site:report.siteFiles,sourceInputs:report.sourceInputs,assets:report.assetSourceInputs,configuration:report.configuration,toolchain:report.toolchain};cache=report.cacheState;
    populations=TRANSITIONS.flatMap(name=>['renderingOpportunity','eventTiming'].map(metric=>{
      const selected=report.transitions.filter(value=>value.name===name);
      return {key:name+'|'+metric,name,metric,unit:'ms',values:selected.map(value=>value.metrics[metric].value),ids:selected.map(value=>({cycle:value.cycle,timeOrigin:report.document.timeOrigin})),
        observed:selected.every(value=>value.metrics[metric].availability==='observed'&&finite(value.metrics[metric].value)),horizon:'named transition to two matching RAF states plus100ms retained observation',scope:semantics[metric]};
    }));
  } else throw new Error('Unsupported measurement family; transport/static/field values are not repeated lab or interaction populations');
  if(qualification.result!=='pass') throw new Error('Raw observations fail independent qualification: '+qualification.errors.join('; '));
  const source={sha:report.source.sha,tree:report.source.tree,origin:report.source.origin};
  if(!/^[0-9a-f]{40}$/.test(source.sha||'')||!/^[0-9a-f]{40}$/.test(source.tree||'')) throw new Error('Full exact measurement source identity unavailable');
  const excluded=new Set(['README.md','lab.test.cjs','interaction.test.cjs']);
  const harness=Object.fromEntries(Object.entries(report.harness||{}).filter(([name])=>!excluded.has(name)));
  if(!Object.keys(harness).length) throw new Error('Measurement owner/observer fingerprints unavailable');
  const signature={family,source,fixture,profile:report.profile,profileSha256:report.profileSha256,runtime:runtimeIdentity(report,runtimeProof),cache,harness,semantics,
    population:populations.map(value=>({key:value.key,unit:value.unit,samples:value.values.length,horizon:value.horizon,scope:value.scope}))};
  return {family,artifactSha256,signature,populations,qualification,scope:report.scope};
}
function arithmetic(left,right) {
  if(!Array.isArray(left)||!Array.isArray(right)||!left.length||left.length!==right.length||[...left,...right].some(value=>!finite(value))) return unknown('Incomplete, unknown or mismatched measured populations');
  const baseline=distribution(left),candidate=distribution(right),difference=candidate.median-baseline.median;
  return {availability:'observed',baseline,candidate,medianDifference:difference,medianRelativePercentage:baseline.median===0?null:100*difference/baseline.median,
    relativePercentage:baseline.median===0?unknown('Zero baseline has no defined relative percentage'):{availability:'observed',value:100*difference/baseline.median,unit:'percent'},
    scope:'finite measured arithmetic; no budget, optimization, statistical significance or field-population claim'};
}
function compareRepeated(left,right) {
  if(left.artifactSha256===right.artifactSha256) return {result:'unavailable',comparisons:[],reason:'Duplicate artifact cannot certify independent repeated executions'};
  if(!same(left.signature,right.signature)) return {result:'unavailable',comparisons:[],reason:'Source/fixture/profile/runtime/cache/owner/metric population or observation scope differs'};
  // A recurring sample/context label is compatible only with a fresh actual document.
  // Reused observations cannot become independent by relabelling the other samples.
  const identity=id=>id.contextId!==undefined?{contextId:id.contextId,timeOrigin:id.timeOrigin}:{cycle:id.cycle,timeOrigin:id.timeOrigin};
  if(left.populations.some((population,index)=>population.ids.some(baselineId=>right.populations[index].ids.some(candidateId=>same(identity(baselineId),identity(candidateId)))))) {
    return {result:'unavailable',comparisons:[],reason:'Repeated execution populations overlap in retained context/document/cycle identity'};
  }
  const comparisons=left.populations.map((population,index)=>({key:population.key,unit:population.unit,scope:population.scope,...(population.observed&&right.populations[index].observed?arithmetic(population.values,right.populations[index].values):unknown('Partial or unknown metric population'))}));
  return {result:comparisons.some(value=>value.availability!=='observed')?'unavailable':'observed',mode:'repeated-run',comparisons};
}
function comparePairedCache(evidence) {
  if(evidence.family!=='lab') return {result:'unavailable',comparisons:[],reason:'Paired cache contrast is defined only for actual controlled lab cold/warm new documents'};
  const comparisons=[];
  for(const route of ['/plain/','/diagram/']) for(const metric of ['lcp','cls','longTasks']) {
    const cold=evidence.populations.find(value=>value.key===route+'|cold|'+metric),warm=evidence.populations.find(value=>value.key===route+'|warm|'+metric);
    if(!cold||!warm||cold.ids.length<3||cold.ids.length!==warm.ids.length||cold.ids.some((value,i)=>value.sample!==warm.ids[i].sample||value.contextId!==warm.ids[i].contextId||value.timeOrigin===warm.ids[i].timeOrigin)) return {result:'unavailable',comparisons:[],reason:'Actual cold/warm context/document pairs are missing or mismatched'};
    comparisons.push({key:route+'|'+metric,unit:cold.unit,scope:cold.scope,intentionalAxis:'cold versus cold-primed new-document warm cache state',
      ...(cold.observed&&warm.observed?arithmetic(cold.values,warm.values):unknown('Partial or unknown cache population')),
      absolutePairedDifferences:cold.observed&&warm.observed?distribution(cold.values.map((value,i)=>Math.abs(warm.values[i]-value))):null,
      signedPairedDifferences:cold.observed&&warm.observed?cold.values.map((value,i)=>warm.values[i]-value):null});
  }
  return {result:comparisons.some(value=>value.availability!=='observed')?'unavailable':'observed',mode:'paired-cache',comparisons,
    scope:'observational contrast within one qualified execution; cache state is the declared intentional axis, not an implementation speedup'};
}
module.exports={runtimeIdentity,prepareEvidence,arithmetic,compareRepeated,comparePairedCache};
