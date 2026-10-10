'use strict';
const {createHash} = require('node:crypto');

const digest = body => createHash('sha256').update(body).digest('hex');
function byteObservation(value, basis) {
  if (value !== null && (!Number.isSafeInteger(value) || value < 0)) throw new Error('Byte observation requires a nonnegative integer or unknown');
  return {value, unit:'bytes', availability:value === null ? 'unobserved' : 'reported', basis};
}

function qualifyJourney(report, expected) {
  const errors=[];
  const fail=message=>errors.push(message);
  if(report.state!=='complete' || report.browserClosed!==true || report.serverClosed!==true) fail('Journey and owned browser/server must actually complete');
  if (report.source?.sha !== expected.sha || report.source?.tree !== expected.tree) fail('Source identity differs from selected committed producer');
  if (report.origin !== expected.origin) fail('Observed origin differs from selected controlled origin');
  if(!report.assets || Object.keys(report.assets).length!==Object.keys(expected.assets).length || Object.entries(expected.assets).some(([name,item])=>{
    const actual=report.assets[name];return !actual || actual.sha256!==item.sha256 || actual.bytes!==item.bytes || actual.source!==item.source;
  })) fail('Reported asset inventory differs from selected committed bytes');
  if (!Array.isArray(report.stages)) return {result:'fail',errors:[...errors,'Missing actual journey stages']};
  const stage=name=>{
    const matches=report.stages.filter(item=>item.name === name);
    if(matches.length !== 1) {fail(`Missing or ambiguous stage: ${name}`);return null;}
    const value=matches[0];
    const paths={'plain-cold':'/plain/','diagram-cold':'/diagram/','diagram-warm':'/diagram/?warm=1','diagram-theme':'/diagram/?warm=1'};
    if(value.url !== expected.origin + paths[name]) fail(`Wrong actual route URL: ${name}`);
    if(!Array.isArray(value.requests) || !Array.isArray(value.responses) || !Array.isArray(value.resources) || !Array.isArray(value.serverResponses)) {fail(`Unavailable actual observations: ${name}`);return null;}
    if(value.pageErrors?.length) fail(`Actual browser errors: ${name}`);
    if(value.actionError) fail(`Ordinary journey action failed: ${name}`);
    return value;
  };
  const plain=stage('plain-cold'), cold=stage('diagram-cold'), warm=stage('diagram-warm'), theme=stage('diagram-theme');
  for(const [name,s] of [['plain-cold',plain],['diagram-cold',cold],['diagram-warm',warm],['diagram-theme',theme]]) {
    if(!s) continue;
    for(const response of s.responses) {
      if(new URL(response.url).origin !== expected.origin) fail(`Unexpected response origin: ${name}`);
      const asset=expected.assets[new URL(response.url).pathname];
      if(asset && (response.decodedBodySha256 !== asset.sha256 || response.decodedBodyBytes !== asset.bytes || response.status !== 200)) fail(`Observed decoded response differs from committed bytes: ${name}`);
    }
    for(const record of s.serverResponses) {
      const asset=expected.assets[record.path];
      if(asset && (record.rawSha256 !== asset.sha256 || record.rawBytes !== asset.bytes || record.status !== 200)) fail(`Actual server response differs from committed bytes: ${name}`);
    }
  }
  const vendorUrl=expected.origin+expected.vendorPath;
  if(plain && (plain.requests.some(r=>r.url===vendorUrl) || plain.resources.some(r=>r.name===vendorUrl) || plain.serverResponses.some(r=>r.path===expected.vendorPath) || plain.rendererPresent !== false)) fail('Plain document eagerly requested or published the diagram library');
  function vendorWitness(s,name) {
    if(!s) return null;
    const matches=s.resources.filter(r=>r.name===vendorUrl);
    if(matches.length!==1) {fail(`Missing or ambiguous exact vendor ResourceTiming URL: ${name}`);return null;}
    const response=s.responses.filter(r=>r.url===vendorUrl);
    if(response.length!==1) fail(`Missing or ambiguous exact decoded vendor response: ${name}`);
    if(s.rendered !== true || s.authoredSource !== expected.authoredSource) fail(`Actual diagram rendering/source unavailable: ${name}`);
    const resource=matches[0];
    for(const field of ['transferSize','encodedBodySize','decodedBodySize']) {
      if(!Number.isSafeInteger(resource[field]) || resource[field]<0) fail(`Unavailable ${field}: ${name}`);
    }
    if(resource.decodedBodySize!==expected.assets[expected.vendorPath].bytes) fail(`Decoded timing size differs from observed source: ${name}`);
    return resource;
  }
  const cr=vendorWitness(cold,'diagram-cold'), wr=vendorWitness(warm,'diagram-warm');
  if(cold) {
    const requests=cold.serverResponses.filter(r=>r.path===expected.vendorPath);
    if(cold.contextSetup!=='fresh-isolated-context' || cold.priorAssetRequests !== 0 || requests.length!==1) fail('Cold declaration does not prove a fresh vendor transfer');
    if(!cold.contextIdentity || !plain || cold.contextIdentity===plain.contextIdentity) fail('Cold diagram must use its own fresh isolated context');
    if(cr && (!(cr.transferSize>0) || !(cr.encodedBodySize>0))) fail('Cold vendor timing does not report a nonzero network representation');
    if(cr && requests.length===1 && cr.encodedBodySize!==requests[0].encodedBodyBytes) fail('Encoded browser timing differs from actual server body');
  }
  if(warm) {
    if(warm.contextSetup!=='same-context-new-document' || warm.primedBy!=='diagram-cold') fail('Warm declaration lacks same-context priming evidence');
    if(!cold || warm.contextIdentity!==cold.contextIdentity) fail('Warm diagram changed its primed browser context');
    if(warm.serverResponses.some(r=>r.path===expected.vendorPath) || !wr || wr.transferSize!==0 || !cold || warm.timeOrigin===cold.timeOrigin) fail('Warm HTTP cache reuse requires a new document, zero reported transfer and no server vendor response');
    if(wr && !(wr.encodedBodySize>0)) fail('Warm encoded representation is unavailable; zero cannot substitute for unknown');
  }
  if(theme && (theme.contextSetup!=='same-document-library-reuse' || !warm || theme.contextIdentity!==warm.contextIdentity || theme.timeOrigin!==warm.timeOrigin || theme.requests.some(r=>r.url===vendorUrl) || theme.resources.some(r=>r.name===vendorUrl) || theme.serverResponses.some(r=>r.path===expected.vendorPath) || theme.rendered!==true || theme.authoredSource!==expected.authoredSource || !theme.svgIdentityChanged)) fail('Theme rerender must retain authored source and reuse the already admitted library without a new transfer');
  return {result:errors.length?'fail':'pass',errors};
}

module.exports={digest,byteObservation,qualifyJourney};
