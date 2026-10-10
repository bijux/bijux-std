'use strict';
const {PROFILE,distribution,commandsForProfile,digest}=require('./lab-evidence.cjs');
const TRANSITIONS=Object.freeze(['drawer-open','disclosure-open','disclosure-close','drawer-close','search-open','search-answer','search-clear','search-close']);
const EXPECTATIONS=Object.freeze({
  'drawer-open':{drawer:true,mainInert:true,focusWithinDrawer:true},'disclosure-open':{details:true,focusedId:'bijux-node-3'},
  'disclosure-close':{details:false,focusedId:'bijux-node-3'},'drawer-close':{drawer:false,mainInert:false,focusedControl:'drawer-toggle'},
  'search-open':{search:true,focusQuery:true},'search-answer':{query:'resilient navigation',knownAnswer:true},
  'search-clear':{query:'',focusQuery:true,resultCount:0,meta:'Type to start searching'},'search-close':{search:false,focusedControl:'search-toggle'}
});
const unknown=reason=>({availability:'unobserved',value:null,reason});
const finite=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0;
function metrics(transition) {
  const input=transition.inputs?.find(value=>value.isTrusted===true&&['click','keydown'].includes(value.type));
  const match=transition.eventEntries?.find(entry=>input&&entry.name===input.type&&Math.abs(entry.startTime-input.eventTimeStamp)<=8&&
    entry.target&&(entry.target.tag===input.target?.tag&&entry.target.id===input.target?.id&&entry.target.control===input.target?.control));
  const available=transition.supported?.includes('event')&&!transition.observerErrors?.length&&transition.droppedEntries===0&&match&&finite(match.startTime)&&finite(match.processingStart)&&finite(match.processingEnd)&&match.processingStart>=match.startTime&&match.processingEnd>=match.processingStart&&finite(match.duration)&&match.duration>=16;
  return {
    renderingOpportunity:input&&finite(transition.firstMatch?.at)&&transition.firstMatch.at>=input.eventTimeStamp?
      {availability:'observed',value:transition.firstMatch.at-input.eventTimeStamp,unit:'ms',scope:'trusted input timestamp to first RAF-observed required state; rendering opportunity, not actual paint',input}:
      unknown('No trusted input or matching RAF state observed'),
    eventTiming:available?{availability:'observed',value:match.duration,unit:'ms',inputDelayMs:match.processingStart-match.startTime,processingMs:match.processingEnd-match.processingStart,
      interactionId:match.interactionId,entry:match,scope:'single correlated browser EventTiming entry; estimated next rendering update rounded to8ms, threshold16ms; not field INP'}:
      unknown('EventTiming unsupported, missing below-threshold correlated entry, invalid, dropped or failed observation')
  };
}
function qualifyTransition(value) {
  const errors=[];
  if(!TRANSITIONS.includes(value.name)) errors.push('Unknown shared reader transition');
  if(JSON.stringify(value.expected)!==JSON.stringify(EXPECTATIONS[value.name])) errors.push('Required named reader transition expectation differs');
  if(value.actionError) errors.push('Ordinary reader action failed');
  if(!value.inputs?.some(input=>input.isTrusted===true&&['click','keydown'].includes(input.type))) errors.push('Ordinary trusted input unavailable');
  if(!value.targetBefore||value.targetBefore.width<=0||value.targetBefore.height<=0||value.targetBefore.centerOwned!==true||value.targetBefore.inViewport!==true) errors.push('Actual input target geometry/hit ownership unavailable');
  if(!value.firstMatch||!value.secondMatch||value.secondMatch.at<=value.firstMatch.at||!Array.isArray(value.frames)||!value.frames.some(frame=>JSON.stringify(frame)===JSON.stringify(value.firstMatch))||!value.frames.some(frame=>JSON.stringify(frame)===JSON.stringify(value.secondMatch))) errors.push('Two actual matching rendering opportunities unavailable');
  for(const observed of [value.firstMatch?.state,value.secondMatch?.state,value.after]) if(!observed||!Object.entries(value.expected||{}).every(([key,wanted])=>observed[key]===wanted)) errors.push('Actual geometry/focus/state differs from required reader transition');
  if(!finite(value.armedAt)||!finite(value.finishedAt)||value.finishedAt<=value.armedAt||value.firstMatch?.at<value.armedAt||value.finishedAt<value.secondMatch?.at) errors.push('Actual transition timeline inconsistent');
  if(metrics(value).renderingOpportunity.availability!=='observed') errors.push('Input-to-required-state rendering opportunity unavailable');
  if(JSON.stringify(value.metrics)!==JSON.stringify(metrics(value))) errors.push('Derived interaction metrics differ from actual observations');
  return errors;
}
function qualifyInteraction(report,expected) {
  const errors=[];
  if(report.state!=='complete'||report.browserClosed!==true||report.serverClosed!==true||report.contextClosed!==true||report.harnessUnchanged!==true||report.fixtureUnchanged!==true) errors.push('Reader/browser/server/source must reach actual terminal unchanged closure');
  for(const name of ['source','accepted','fixtureManifestSha256','siteFiles','sourceInputs','assetSourceInputs','configuration','toolchain']) if(JSON.stringify(report[name])!==JSON.stringify(expected[name])) errors.push('Selected source/fixture/configuration ownership differs: '+name);
  if(JSON.stringify(report.profile)!==JSON.stringify(PROFILE)||report.profileSha256!==digest(JSON.stringify(PROFILE))) errors.push('Declared lab profile differs');
  const wanted=commandsForProfile();
  if(!Array.isArray(report.commands)||report.commands.length!==wanted.length||report.commands.some((value,i)=>value.method!==wanted[i].method||JSON.stringify(value.params)!==JSON.stringify(wanted[i].params)||value.accepted!==true)) errors.push('Actual declared CPU/network/cache acknowledgement unavailable');
  if(!report.commands?.find(value=>value.method==='Network.emulateNetworkConditionsByRule')?.response?.ruleIds?.length) errors.push('Actual network rule acknowledgement unavailable');
  if(report.document?.url!==report.origin+'/fixtures/long-registry/'||report.document.visibility!=='visible'||JSON.stringify(report.document.viewport)!==JSON.stringify({...PROFILE.viewport,deviceScaleFactor:PROFILE.deviceScaleFactor})) errors.push('Actual source-owned document/viewport differs');
  if(!Number.isInteger(report.cycles)||report.cycles<3||report.cycles>10||report.transitions?.length!==report.cycles*TRANSITIONS.length) errors.push('Incomplete repeated ordinary-input cycles');
  for(let cycle=1;cycle<=report.cycles;cycle++) {
    const values=(report.transitions||[]).filter(value=>value.cycle===cycle);
    if(JSON.stringify(values.map(value=>value.name))!==JSON.stringify(TRANSITIONS)) errors.push('Actual transition sequence differs: cycle'+cycle);
    for(const value of values) errors.push(...qualifyTransition(value).map(message=>value.name+': '+message));
  }
  for(const response of report.responses||[]) {
    const url=new URL(response.url),relative=url.pathname.slice('/fixtures/long-registry/'.length),owned=expected.siteFiles[relative||'index.html'];
    if(url.origin!==report.origin||!url.pathname.startsWith('/fixtures/long-registry/')||!owned||response.status!==200||response.decodedBodySha256!==owned.sha256||response.decodedBodyBytes!==owned.bytes) errors.push('Observed served body differs from exact finite owned fixture');
  }
  if(!report.responses?.some(value=>value.url===report.document?.url)) errors.push('Observed exact document response unavailable');
  if(report.pageErrors?.length||report.failedRequests?.length) errors.push('Actual document runtime/request failure retained');
  const missing=(report.transitions||[]).filter(value=>value.metrics?.eventTiming.availability!=='observed').map(value=>({cycle:value.cycle,name:value.name,reason:value.metrics?.eventTiming.reason||'Missing observed metric'}));
  return {result:errors.length?'fail':missing.length?'incomplete':'pass',functional:{result:errors.length?'fail':'pass'},errors,eventTiming:{result:missing.length?'incomplete':'observed',missing,scope:'Missing required sample latency remains unknown; functional/RAF qualification is separate from full EventTiming coverage'},fieldINP:{availability:'unobserved',value:null,reason:'No valid field interaction population collected'}};
}
function distributions(transitions) {
  return Object.fromEntries(TRANSITIONS.map(name=>[name,Object.fromEntries(['renderingOpportunity','eventTiming'].map(metric=>{
    const selected=transitions.filter(value=>value.name===name),values=selected.filter(value=>value.metrics?.[metric]?.availability==='observed').map(value=>value.metrics[metric].value);
    return [metric,values.length?{availability:values.length===selected.length?'observed':'partial',...distribution(values),executed:selected.length,missing:selected.length-values.length}:
      {...unknown('No observed metric'),executed:selected.length,missing:selected.length}];
  }))]));
}
module.exports={TRANSITIONS,EXPECTATIONS,metrics,qualifyTransition,qualifyInteraction,distributions};
