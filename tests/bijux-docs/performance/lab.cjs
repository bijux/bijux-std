#!/usr/bin/env node
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const {parseArgs}=require('node:util');
const {randomUUID}=require('node:crypto');
const {execFileSync}=require('node:child_process');
const {sourceAssets,observe,AUTHORED_SOURCE,VENDOR_PATH}=require('./transport.cjs');
const {startServer,documentHtml}=require('./transport-server.cjs');
const {installLabObserver}=require('./lab-observer.cjs');
const {PROFILE,digest,commandsForProfile,metricSnapshot,distribution,qualifyLab}=require('./lab-evidence.cjs');

function harnessIdentity() {
  const names=['lab.cjs','lab-observer.cjs','lab-evidence.cjs','lab.test.cjs','README.md','transport.cjs','transport-server.cjs','transport-evidence.cjs'];
  return Object.fromEntries(names.map(name=>{const bytes=fs.readFileSync(path.join(__dirname,name));return [name,{bytes:bytes.length,sha256:digest(bytes)}];}));
}

function fixtureProducer(sourceRoot,sourceSha) {
  return Object.fromEntries(['transport.cjs','transport-server.cjs','transport-evidence.cjs'].map(name=>{
    const relative='tests/bijux-docs/performance/'+name;
    const committed=execFileSync('git',['-C',sourceRoot,'show',sourceSha+':'+relative],{maxBuffer:1024*1024});
    const actual=fs.readFileSync(path.join(__dirname,name));
    if(!actual.equals(committed)) throw new Error('Owned fixture producer differs from selected committed source: '+relative);
    return [relative,{bytes:committed.length,sha256:digest(committed)}];
  }));
}

async function applyProfile(session,commands) {
  for(const wanted of commandsForProfile()) {
    const record={...wanted,accepted:false};commands.push(record);
    try {record.response=await session.send(wanted.method,wanted.params);record.accepted=true;}
    catch(error) {record.error=error.message;throw new Error('Declared lab emulation unavailable: '+wanted.method+' '+error.message);}
  }
}

function distributions(samples) {
  const result={};
  for(const route of ['/plain/','/diagram/']) {
    result[route]={};
    for(const cache of ['cold','warm']) {
      const stages=samples.filter(sample=>sample.route===route).flatMap(sample=>sample.stages||[]).filter(stage=>stage.cacheState===cache);
      result[route][cache]=Object.fromEntries(['lcp','cls','longTasks'].map(name=>{
        const values=stages.filter(stage=>stage.metrics?.[name]?.availability==='observed').map(stage=>stage.metrics[name].value);
        return [name,values.length===stages.length&&values.length?{availability:'observed',...distribution(values)}:
          {availability:'unobserved',value:null,observed:values.length,executed:stages.length,reason:'Required sample metric unavailable'}];
      }));
    }
  }
  return result;
}

async function measureLab({sourceRoot,sourceSha,samples=3,engine='chromium',output}) {
  if(engine!=='chromium') throw new Error('Declared CPU/network lab emulation is supported only by Chromium CDP; other engines remain unqualified');
  if(!Number.isInteger(samples)||samples<3||samples>10) throw new Error('Select three to ten independent route samples');
  const selected=sourceAssets(sourceRoot,sourceSha);
  const producer=fixtureProducer(sourceRoot,sourceSha);
  const {chromium}=require('playwright');
  const server=await startServer({assets:selected.assets,vendorPath:VENDOR_PATH,authoredSource:AUTHORED_SOURCE,encoding:PROFILE.encoding,cacheControl:PROFILE.cachePolicy});
  const documents=Object.fromEntries(['/plain/','/diagram/'].map(route=>{const bytes=Buffer.from(documentHtml(route==='/diagram/',{vendorPath:VENDOR_PATH,authoredSource:AUTHORED_SOURCE}));return [route,{sha256:digest(bytes),bytes:bytes.length}];}));
  const expected={source:selected.identity,assets:selected.manifest,documents,fixtureProducer:producer,vendorPath:VENDOR_PATH,authoredSource:AUTHORED_SOURCE};
  const report={schema:1,state:'running',scope:'controlled source-owned repeated cold/warm lab; not actual Material/production route or field qualification',source:selected.identity,assets:selected.manifest,
    origin:server.origin,fixtureProducer:producer,profile:PROFILE,profileSha256:digest(JSON.stringify(PROFILE)),documents,requestedSamples:samples,samples:[],harness:harnessIdentity(),
    runtime:{node:process.version,nodeExecutable:process.execPath,nodeExecutableSha256:digest(fs.readFileSync(process.execPath)),playwright:require('playwright/package.json').version,
      playwrightPackageSha256:digest(fs.readFileSync(require.resolve('playwright/package.json'))),browserExecutable:chromium.executablePath(),host:{platform:os.platform(),release:os.release(),architecture:os.arch(),logicalCPUs:os.cpus().length,cpuModel:os.cpus()[0]?.model}},
    field:{lcp:null,cls:null,inp:null,reason:'No valid field population or telemetry collected'},
    limits:['Phone-shaped desktop Chromium emulation is not a physical mobile device.','Observations end1000ms after actual load/render readiness; not full page lifetime.',
      'No timing ceiling or optimization threshold is invented.','Long-task observations are not total CPU or field INP.','HTTP cache reuse and encoded server bodies remain distinct from estimated ResourceTiming and unobserved actual header/wire bytes.']};
  const save=()=>{if(output) fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');};
  let browser;
  try {
    browser=await chromium.launch({executablePath:report.runtime.browserExecutable});report.runtime.browserVersion=browser.version();save();
    for(const route of ['/plain/','/diagram/']) for(let index=0;index<samples;index++) {
      const sample={route,sample:index+1,contextId:randomUUID(),commands:[],stages:[],contextClosed:false};report.samples.push(sample);save();
      const context=await browser.newContext({viewport:PROFILE.viewport,deviceScaleFactor:PROFILE.deviceScaleFactor,isMobile:PROFILE.isMobile,hasTouch:PROFILE.hasTouch});
      try {
        await context.addInitScript(installLabObserver);
        const page=await context.newPage();page.setDefaultTimeout(10000);
        const session=await context.newCDPSession(page);
        await applyProfile(session,sample.commands);save();
        for(const cache of ['cold','warm']) {
          let snapshot;
          const stage=await observe(page,server,cache,cache==='cold'?'fresh-isolated-context':'same-context-new-document',sample.contextId,async()=>{
            if(cache==='cold') await page.goto(server.origin+route,{waitUntil:'load',timeout:10000});
            else await page.reload({waitUntil:'load',timeout:10000});
            if(route==='/diagram/') await page.waitForFunction(()=>{
              const svg=document.querySelector('.bijux-diagram-preview > svg');const bounds=svg?.getBoundingClientRect();
              return bounds?.width>0&&bounds.height>0&&!document.querySelector('.bijux-diagram-source')?.open;
            },{},{timeout:10000});
            await page.waitForTimeout(PROFILE.observationHoldMs);
            snapshot=await page.evaluate(()=>window.__bijuxLab.snapshot());
          });
          Object.assign(stage,{cacheState:cache,snapshot,observationHoldMs:PROFILE.observationHoldMs,primedBy:cache==='warm'?'cold':null});
          if(snapshot) stage.metrics=metricSnapshot(snapshot);
          sample.stages.push(stage);save();
          if(stage.actionError) throw new Error(stage.actionError);
        }
        await session.detach();
      } finally {await context.close();sample.contextClosed=true;save();}
    }
    report.state='complete';
  } catch(error) {report.state='failed';report.qualification={result:'fail',errors:[error.stack||error.message]};}
  finally {
    try {if(browser) await browser.close();report.browserClosed=true;} catch(error) {report.browserClosed=false;report.qualification={result:'fail',errors:['Browser closure failed: '+error.message]};}
    try {await server.close();report.serverClosed=true;} catch(error) {report.serverClosed=false;report.qualification={result:'fail',errors:[...(report.qualification?.errors||[]),'Server closure failed: '+error.message]};}
    report.harnessUnchanged=JSON.stringify(harnessIdentity())===JSON.stringify(report.harness);
    if(!report.qualification) report.qualification=qualifyLab(report,expected);
    if(!report.harnessUnchanged) report.qualification={result:'fail',errors:[...(report.qualification?.errors||[]),'Owned lab source changed during measurement']};
    report.distributions=distributions(report.samples);report.serverResponses=server.responses;save();
  }
  return {report,expected};
}

async function main() {
  const {values}=parseArgs({options:{'source-root':{type:'string'},'source-sha':{type:'string'},samples:{type:'string',default:'3'},engine:{type:'string',default:'chromium'},output:{type:'string'}}});
  if(!values['source-root']||!values['source-sha']||!values.output) throw new Error('Select exact source and owning lab --output');
  const root=fs.realpathSync(values['source-root']),output=path.resolve(root,values.output);
  if(!output.startsWith(path.join(root,'artifacts')+path.sep)) throw new Error('Lab output must remain under owning artifacts/');
  fs.mkdirSync(path.dirname(output),{recursive:true});process.env.TMPDIR=path.join(path.dirname(output),'browser-scratch');fs.mkdirSync(process.env.TMPDIR,{recursive:true});
  const {report}=await measureLab({sourceRoot:root,sourceSha:values['source-sha'],samples:Number(values.samples),engine:values.engine,output});
  process.stdout.write(JSON.stringify({result:report.qualification.result,state:report.state,samples:report.samples.length,errors:report.qualification.errors,output})+'\n');
  process.exitCode=report.qualification.result==='pass'?0:1;
}
module.exports={measureLab,applyProfile,distributions,harnessIdentity,fixtureProducer};
if(require.main===module) main().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;});
