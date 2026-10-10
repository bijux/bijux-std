#!/usr/bin/env node
'use strict';
const {execFileSync}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const {parseArgs}=require('node:util');
const {randomUUID}=require('node:crypto');
const {startServer}=require('./transport-server.cjs');
const {digest,byteObservation,qualifyJourney}=require('./transport-evidence.cjs');

const AUTHORED_SOURCE='flowchart LR\n  accTitle: Owned reader diagram\n  accDescr: Plain and diagram reading remain distinct\n  Overview --> Detail';
const VENDOR_PATH='/assets/javascripts/vendor/mermaid-11.17.2.min.js';
const INPUTS={
  '/assets/bijux_logo.png':'shared/bijux-docs/assets/bijux_logo.png',
  '/assets/javascripts/mermaid-init.js':'shared/bijux-docs/scripts/mermaid-init.js',
  [VENDOR_PATH]:'shared/bijux-docs/assets/javascripts/vendor/mermaid-11.17.2.min.js'
};

function sourceAssets(root,sha) {
  if(!/^[a-f0-9]{40}$/.test(sha)) throw new Error('Select an exact full committed standard SHA');
  const git=(...args)=>execFileSync('git',['-C',root,...args],{maxBuffer:8*1024*1024});
  if(fs.realpathSync(git('rev-parse','--show-toplevel').toString().trim())!==fs.realpathSync(root)) throw new Error('Select the actual standard repository root');
  const origin=git('remote','get-url','origin').toString().trim();
  if(!['https://github.com/bijux/bijux-std.git','git@github.com:bijux/bijux-std.git'].includes(origin)) throw new Error('Standard source must retain the Bijux GitHub origin');
  if(git('rev-parse',sha+'^{commit}').toString().trim()!==sha) throw new Error('Selected committed source differs');
  const assets={},manifest={};
  for(const [url,input] of Object.entries(INPUTS)) {
    assets[url]=git('show',sha+':'+input);
    manifest[url]={source:input,sha256:digest(assets[url]),bytes:assets[url].length};
  }
  return {assets,manifest,identity:{origin:'https://github.com/bijux/bijux-std.git',sha,tree:git('rev-parse',sha+'^{tree}').toString().trim(),scope:'exact selected committed producer; remote acceptance is separate'}};
}

async function observe(page,server,name,contextSetup,contextIdentity,action) {
  const requests=[],responses=[],pending=[],pageErrors=[];
  const start=server.responses.length;
  const onRequest=r=>requests.push({url:r.url(),resourceType:r.resourceType(),navigation:r.isNavigationRequest()});
  const onResponse=r=>{
    pending.push((async()=>{
      const body=await r.body();
      responses.push({url:r.url(),status:r.status(),headers:await r.allHeaders(),decodedBodyBytes:body.length,decodedBodySha256:digest(body)});
    })().catch(error=>pageErrors.push('Response observation unavailable: '+error.message)));
  };
  const onError=e=>pageErrors.push(e.message);
  page.on('request',onRequest);page.on('response',onResponse);page.on('pageerror',onError);
  try {
    let actionError=null;
    try {await action();} catch(error) {actionError=error.stack||error.message;}
    await Promise.all(pending);
    const browser=await page.evaluate(()=>({url:location.href,timeOrigin:performance.timeOrigin,
      resources:performance.getEntriesByType('resource').map(e=>({name:e.name,initiatorType:e.initiatorType,startTime:e.startTime,responseEnd:e.responseEnd,
        transferSize:'transferSize' in e?e.transferSize:null,encodedBodySize:'encodedBodySize' in e?e.encodedBodySize:null,decodedBodySize:'decodedBodySize' in e?e.decodedBodySize:null,
        deliveryType:'deliveryType' in e?e.deliveryType:null})),
      rendererPresent:typeof window.mermaid !== 'undefined',
      rendered:!!document.querySelector('.bijux-diagram-preview > svg'),
      authoredSource:document.querySelector('.bijux-diagram-source code')?.textContent??null,
      svgIdentity:document.querySelector('.bijux-diagram-preview > svg')?.id??null}));
    return {name,contextSetup,contextIdentity,...browser,requests,responses,pageErrors,actionError,serverResponses:server.responses.slice(start),observationEnd:new Date().toISOString(),
      actualWireBytes:byteObservation(null,'No packet/header wire measurement; ResourceTiming is reported separately')};
  } finally {
    page.off('request',onRequest);page.off('response',onResponse);page.off('pageerror',onError);
  }
}

async function rendered(page) {
  await page.waitForFunction(()=>{
    const svg=document.querySelector('.bijux-diagram-preview > svg');
    if(!svg) return false;
    const bounds=svg.getBoundingClientRect();
    return bounds.width>0 && bounds.height>0 && !document.querySelector('.bijux-diagram-source')?.open;
  },{},{timeout:10000});
}

async function measureJourney({sourceRoot,sourceSha,engine='chromium',encoding='gzip',cacheControl='public, max-age=3600',eagerPlain=false,vendorFault=null,output}) {
  const selected=sourceAssets(sourceRoot,sourceSha);
  if(!['chromium','firefox','webkit'].includes(engine)) throw new Error('Select an admitted Playwright engine');
  const {chromium,firefox,webkit}=require('playwright');
  const browserType={chromium,firefox,webkit}[engine];
  const server=await startServer({assets:selected.assets,vendorPath:VENDOR_PATH,authoredSource:AUTHORED_SOURCE,encoding,cacheControl,eagerPlain,vendorFault});
  const expected={sha:sourceSha,tree:selected.identity.tree,origin:server.origin,assets:selected.manifest,vendorPath:VENDOR_PATH,authoredSource:AUTHORED_SOURCE};
  const report={schema:1,scope:'controlled shared producer transport; not Material instant/BFCache/production routes or lab/field qualification',source:selected.identity,assets:selected.manifest,
    origin:server.origin,engine,encoding,cacheControl,eagerPlain,vendorFault,stages:[],state:'running',node:process.version,playwright:require('playwright/package.json').version,
    producerFixture:{kind:'two owned authored test documents with real committed Mermaid initializer/vendor and ordinary controls',authoredSource:AUTHORED_SOURCE},
    measurementLimits:['ResourceTiming transferSize reports an estimated header allowance, not actual wire/header bytes.','HTTP cache reuse is scoped to this controlled process/context; memory versus disk is unobserved.','A zero field alone never certifies a cache hit.','The no-diagram observation is bounded through load plus350ms.','No throttled mobile preset, performance limit, consumer or live qualification.']};
  report.harness={};
  for(const name of ['transport.cjs','transport-evidence.cjs','transport-server.cjs','transport.test.cjs','README.md']) {
    const file=path.join(__dirname,name);
    if(fs.existsSync(file)) {const bytes=fs.readFileSync(file);report.harness[name]={bytes:bytes.length,sha256:digest(bytes)};}
  }
  report.runtime={nodeExecutable:process.execPath,nodeExecutableSha256:digest(fs.readFileSync(process.execPath)),playwrightPackageSha256:digest(fs.readFileSync(require.resolve('playwright/package.json'))),browserExecutable:browserType.executablePath()};
  const save=()=>{if(output) fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');};
  let browser;
  try {
    browser=await browserType.launch({executablePath:report.runtime.browserExecutable});report.browserVersion=browser.version();save();
    const plainContext=await browser.newContext({viewport:{width:390,height:844}});
    const plain=await plainContext.newPage();plain.setDefaultTimeout(10000);
    try {
      const stage=await observe(plain,server,'plain-cold','fresh-isolated-context',randomUUID(),async()=>{
        await plain.goto(server.origin+'/plain/',{waitUntil:'load',timeout:10000});
        await plain.waitForTimeout(350);
      });report.stages.push(stage);save();if(stage.actionError) throw new Error(stage.actionError);
    } finally {await plainContext.close();}
    const context=await browser.newContext({viewport:{width:390,height:844}}),contextIdentity=randomUUID();
    const page=await context.newPage();page.setDefaultTimeout(10000);
    try {
      const prior=server.responses.filter(r=>r.path===VENDOR_PATH).length;
      const cold=await observe(page,server,'diagram-cold','fresh-isolated-context',contextIdentity,async()=>{
        await page.goto(server.origin+'/diagram/',{waitUntil:'load',timeout:10000});await rendered(page);
      });cold.priorAssetRequests=prior;report.stages.push(cold);save();if(cold.actionError) throw new Error(cold.actionError);
      await page.getByRole('link',{name:'Read plain page',exact:true}).click();
      await page.waitForURL(server.origin+'/plain/',{waitUntil:'load',timeout:10000});
      const warm=await observe(page,server,'diagram-warm','same-context-new-document',contextIdentity,async()=>{
        await page.getByRole('link',{name:'Read diagram',exact:true}).click();
        await page.waitForURL(server.origin+'/diagram/?warm=1',{waitUntil:'load',timeout:10000});await rendered(page);
      });warm.primedBy='diagram-cold';report.stages.push(warm);save();if(warm.actionError) throw new Error(warm.actionError);
      const priorSvg=warm.svgIdentity;
      await page.evaluate(()=>performance.clearResourceTimings());
      const theme=await observe(page,server,'diagram-theme','same-document-library-reuse',contextIdentity,async()=>{
        await page.getByRole('button',{name:'Change theme',exact:true}).click();
        await page.waitForFunction(id=>document.querySelector('.bijux-diagram-preview > svg')?.id!==id,priorSvg,{timeout:10000});await rendered(page);
      });theme.svgIdentityChanged=theme.svgIdentity!==priorSvg;report.stages.push(theme);save();if(theme.actionError) throw new Error(theme.actionError);
    } finally {await context.close();}
    report.state='complete';
  } catch(error) {
    report.state='failed';report.qualification={result:'fail',errors:[error.stack||error.message]};
  } finally {
    try {if(browser) await browser.close();report.browserClosed=true;} catch(error) {report.browserClosed=false;report.state='failed';report.qualification={result:'fail',errors:['Browser closure failed: '+error.message]};}
    try {await server.close();report.serverClosed=true;} catch(error) {report.serverClosed=false;report.state='failed';report.qualification={result:'fail',errors:[...(report.qualification?.errors||[]),'Server closure failed: '+error.message]};}
    report.serverResponses=server.responses;
    if(!report.qualification) report.qualification=qualifyJourney(report,expected);
    report.harnessUnchanged=Object.entries(report.harness).every(([name,value])=>digest(fs.readFileSync(path.join(__dirname,name)))===value.sha256);
    if(!report.harnessUnchanged) {report.state='failed';report.qualification={result:'fail',errors:[...(report.qualification.errors||[]),'Transport harness changed during actual observation']};}
    save();
  }
  return {report,expected};
}

async function main() {
  const {values}=parseArgs({options:{'source-root':{type:'string'},'source-sha':{type:'string'},output:{type:'string'},engine:{type:'string',default:'chromium'},encoding:{type:'string',default:'gzip'},'cache-control':{type:'string',default:'public, max-age=3600'}}});
  if(!values['source-root']||!values['source-sha']||!values.output) throw new Error('Select --source-root, --source-sha and owning --output');
  const root=fs.realpathSync(values['source-root']),output=path.resolve(root,values.output);
  if(!output.startsWith(path.join(root,'artifacts')+path.sep)) throw new Error('Transport output must remain in owning artifacts/');
  fs.mkdirSync(path.dirname(output),{recursive:true});
  process.env.TMPDIR=path.join(path.dirname(output),'browser-scratch');fs.mkdirSync(process.env.TMPDIR,{recursive:true});
  const {report}=await measureJourney({sourceRoot:root,sourceSha:values['source-sha'],engine:values.engine,encoding:values.encoding,cacheControl:values['cache-control'],output});
  process.stdout.write(JSON.stringify({result:report.qualification.result,engine:report.engine,version:report.browserVersion,state:report.state,errors:report.qualification.errors,output})+'\n');
  process.exitCode=report.qualification.result==='pass'?0:1;
}
module.exports={sourceAssets,measureJourney,observe,AUTHORED_SOURCE,VENDOR_PATH};
if(require.main===module) main().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;});
