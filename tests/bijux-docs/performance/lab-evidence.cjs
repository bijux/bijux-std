'use strict';
const {digest}=require('./transport-evidence.cjs');

const PROFILE=Object.freeze({name:'constrained-phone-viewport',engine:'chromium',viewport:Object.freeze({width:390,height:844}),deviceScaleFactor:1,
  isMobile:false,hasTouch:true,cpuSlowdown:4,network:Object.freeze({offline:false,latency:150,downloadThroughput:200000,uploadThroughput:93750}),
  encoding:'gzip',cachePolicy:'public, max-age=3600',observationHoldMs:1000,
  scope:'desktop Chromium engine with an explicit phone-shaped viewport; not a physical or named mobile device'});

function distribution(values) {
  if(!Array.isArray(values) || !values.length || values.some(v=>typeof v!=='number'||!Number.isFinite(v)||v<0)) throw new Error('Distribution requires actual finite nonnegative observations');
  const sorted=[...values].sort((a,b)=>a-b),mean=sorted.reduce((a,b)=>a+b,0)/sorted.length;
  const middle=Math.floor(sorted.length/2);
  return {samples:values.length,values:[...values],minimum:sorted[0],maximum:sorted.at(-1),median:sorted.length%2?sorted[middle]:(sorted[middle-1]+sorted[middle])/2,
    mean,p75NearestRank:sorted[Math.ceil(sorted.length*0.75)-1],populationStddev:Math.sqrt(sorted.reduce((sum,v)=>sum+(v-mean)**2,0)/sorted.length),
    scope:'repeated controlled lab samples; nearest-rank p75 is not population field p75'};
}

function cumulativeLayoutShift(entries) {
  if(!Array.isArray(entries)) throw new Error('Layout-shift entries must be observed');
  const eligible=entries.filter(entry=>{
    if(typeof entry.startTime!=='number'||!Number.isFinite(entry.startTime)||entry.startTime<0||typeof entry.value!=='number'||!Number.isFinite(entry.value)||entry.value<0||typeof entry.hadRecentInput!=='boolean') throw new Error('Invalid layout-shift observation');
    return !entry.hadRecentInput;
  }).sort((a,b)=>a.startTime-b.startTime);
  let maximum=0,current=0,start=null,previous=null;
  for(const entry of eligible) {
    if(start===null || entry.startTime-previous>=1000 || entry.startTime-start>=5000) {start=entry.startTime;current=0;}
    current+=entry.value;maximum=Math.max(maximum,current);previous=entry.startTime;
  }
  return maximum;
}

function metricSnapshot(snapshot) {
  const unknown=(type,reason)=>({availability:'unobserved',value:null,reason,type});
  const available=type=>snapshot?.supported?.includes(type)&&Array.isArray(snapshot.entries?.[type])&&!snapshot.errors?.some(item=>item.type===type)&&snapshot.droppedEntries===0;
  const lcp=snapshot?.entries?.['largest-contentful-paint'];
  const latest=Array.isArray(lcp)&&lcp.length?[...lcp].sort((a,b)=>a.startTime-b.startTime).at(-1):null;
  const largest=available('largest-contentful-paint')&&latest&&typeof latest.startTime==='number'&&Number.isFinite(latest.startTime)&&latest.startTime>0?
    {availability:'observed',value:latest.startTime,unit:'ms',candidate:latest,scope:'latest candidate at bounded observation end'}:unknown('largest-contentful-paint','API unsupported, missing candidate or dropped/failed observation');
  const cls=available('layout-shift')?{availability:'observed',value:cumulativeLayoutShift(snapshot.entries['layout-shift']),unit:'score',scope:'maximum observed unexpected-shift session window'}:unknown('layout-shift','API unsupported or dropped/failed observation');
  const tasks=snapshot?.entries?.longtask;
  const validTasks=available('longtask')&&tasks.every(item=>typeof item.duration==='number'&&Number.isFinite(item.duration)&&item.duration>=50&&typeof item.startTime==='number'&&Number.isFinite(item.startTime)&&item.startTime>=0);
  const longTasks=validTasks?{availability:'observed',value:tasks.reduce((sum,item)=>sum+item.duration,0),unit:'ms',count:tasks.length,maximumMs:tasks.length?Math.max(...tasks.map(item=>item.duration)):0,
    scope:'observed long-task durations, not total CPU or field interaction latency'}:unknown('longtask','API unsupported, invalid or dropped/failed observation');
  return {lcp:largest,cls,longTasks};
}

function commandsForProfile(profile=PROFILE) {
  return [
    {method:'Network.enable',params:{}},
    {method:'Network.setCacheDisabled',params:{cacheDisabled:false}},
    {method:'Network.setBypassServiceWorker',params:{bypass:true}},
    {method:'Emulation.setCPUThrottlingRate',params:{rate:profile.cpuSlowdown}},
    {method:'Network.emulateNetworkConditionsByRule',params:{offline:profile.network.offline,matchedNetworkConditions:[{urlPattern:'',latency:profile.network.latency,downloadThroughput:profile.network.downloadThroughput,uploadThroughput:profile.network.uploadThroughput}]}},
    {method:'Network.overrideNetworkState',params:{...profile.network}},
    {method:'Network.clearBrowserCache',params:{}}
  ];
}

function qualifyLab(report,expected) {
  const errors=[],fail=message=>errors.push(message);
  if(report.state!=='complete'||report.browserClosed!==true||report.serverClosed!==true||report.harnessUnchanged!==true) fail('Lab browser/server/harness must reach actual qualified terminal closure');
  if(report.source?.sha!==expected.source.sha||report.source?.tree!==expected.source.tree||report.source?.origin!==expected.source.origin) fail('Lab source differs from selected committed producer');
  if(JSON.stringify(report.fixtureProducer)!==JSON.stringify(expected.fixtureProducer)) fail('Owned lab fixture producer differs from selected committed source');
  if(JSON.stringify(report.documents)!==JSON.stringify(expected.documents)) fail('Lab document/config inventory differs from exact fixture');
  if(report.profileSha256!==digest(JSON.stringify(PROFILE))) fail('Declared lab profile fingerprint differs');
  if(JSON.stringify(report.assets)!==JSON.stringify(expected.assets)) fail('Lab asset inventory differs from selected committed bytes');
  if(JSON.stringify(report.profile)!==JSON.stringify(PROFILE)) fail('Lab conditions differ from the declared comparable profile');
  if(!Number.isInteger(report.requestedSamples)||report.requestedSamples<3) fail('Repeated baseline requires at least three independent samples per route');
  if(!Array.isArray(report.samples)) return {result:'fail',errors:[...errors,'Missing actual lab samples']};
  const contextIds=new Set();
  for(const route of ['/plain/','/diagram/']) {
    const samples=report.samples.filter(sample=>sample.route===route);
    if(samples.length!==report.requestedSamples) fail('Incomplete requested route samples: '+route);
    for(const sample of samples) {
      if(!sample.contextId||contextIds.has(sample.contextId)||sample.contextClosed!==true) fail('Sample lacks a distinct closed cold context');
      contextIds.add(sample.contextId);
      const wanted=commandsForProfile();
      if(!Array.isArray(sample.commands)||sample.commands.length!==wanted.length||sample.commands.some((command,i)=>command.method!==wanted[i].method||JSON.stringify(command.params)!==JSON.stringify(wanted[i].params)||command.accepted!==true)) fail('CPU/network/cache commands were missing, changed or rejected');
      for(const command of sample.commands||[]) if(command.method==='Network.emulateNetworkConditionsByRule'&&(!Array.isArray(command.response?.ruleIds)||command.response.ruleIds.length!==1)) fail('Network throttle rule acknowledgement unavailable');
      const stages=sample.stages;
      if(!Array.isArray(stages)||stages.length!==2) {fail('Missing cold/warm stage pair');continue;}
      for(const [index,stage] of stages.entries()) {
        const state=index===0?'cold':'warm';
        if(stage.cacheState!==state||stage.url!==report.origin+route||stage.actionError||stage.pageErrors?.length) fail('Actual route/action/error differs from lab declaration');
        if(!stage.snapshot||stage.snapshot.visibility!=='visible'||stage.snapshot.readyState!=='complete'||JSON.stringify(stage.snapshot.viewport)!==JSON.stringify({...PROFILE.viewport,deviceScaleFactor:PROFILE.deviceScaleFactor})||stage.snapshot.navigator.onLine!==true||typeof stage.snapshot.timeOrigin!=='number'||!Number.isFinite(stage.snapshot.timeOrigin)||stage.snapshot.timeOrigin<0) fail('Visible loaded document or actual viewport/network state unavailable');
        if(stage.observationHoldMs!==PROFILE.observationHoldMs||stage.metrics?.lcp?.availability!=='observed'||stage.metrics?.cls?.availability!=='observed'||stage.metrics?.longTasks?.availability!=='observed') fail('Required bounded metric observations unavailable');
        if(stage.snapshot&&JSON.stringify(stage.metrics)!==JSON.stringify(metricSnapshot(stage.snapshot))) fail('Reported metrics differ from actual buffered observations');
        if(stage.snapshot?.observationEndMs<PROFILE.observationHoldMs) fail('Observation horizon shorter than declared');
        const documentResponse=stage.responses?.filter(value=>value.url===report.origin+route);
        if(documentResponse?.length!==1||documentResponse[0].status!==200||documentResponse[0].decodedBodySha256!==expected.documents[route].sha256||documentResponse[0].decodedBodyBytes!==expected.documents[route].bytes) fail('Observed document/config differs from exact owned fixture');
        for(const response of stage.responses||[]) {
          const asset=expected.assets[new URL(response.url).pathname];
          if(asset&&(response.status!==200||response.decodedBodyBytes!==asset.bytes||response.decodedBodySha256!==asset.sha256)) fail('Observed lab asset differs from exact source');
        }
        const vendor=report.origin+expected.vendorPath;
        const vendorRequests=stage.serverResponses?.filter(value=>value.path===expected.vendorPath)||[];
        const vendorTiming=stage.resources?.filter(value=>value.name===vendor)||[];
        if(route==='/plain/'&&(vendorRequests.length||vendorTiming.length||stage.rendererPresent!==false)) fail('Plain lab reading eagerly requested optional library');
        if(route==='/diagram/') {
          if(stage.rendered!==true||stage.authoredSource!==expected.authoredSource||vendorTiming.length!==1||vendorTiming[0].decodedBodySize!==expected.assets[expected.vendorPath].bytes) fail('Real diagram/source/timing evidence unavailable');
          if(index===0&&(vendorRequests.length!==1||!(vendorTiming[0]?.transferSize>0))) fail('Cold diagram does not prove actual vendor transfer');
          if(index===1&&(vendorRequests.length!==0||vendorTiming[0]?.transferSize!==0)) fail('Warm diagram does not prove primed HTTP cache reuse');
        }
      }
      if(stages[0]?.snapshot?.timeOrigin===stages[1]?.snapshot?.timeOrigin||stages[1]?.primedBy!=='cold') fail('Warm sample is not a fresh document primed by its cold pair');
    }
  }
  if(report.samples.length!==report.requestedSamples*2) fail('Unknown or extra sample route');
  return {result:errors.length?'fail':'pass',errors};
}
module.exports={PROFILE,distribution,cumulativeLayoutShift,metricSnapshot,commandsForProfile,qualifyLab,digest};
