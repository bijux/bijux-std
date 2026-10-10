#!/usr/bin/env node
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const {parseArgs}=require('node:util');
const {PROFILE,digest}=require('./lab-evidence.cjs');
const {applyProfile}=require('./lab.cjs');
const {inventory,selectFixture,startFixtureServer}=require('./interaction-server.cjs');
const {installInteractionObserver}=require('./interaction-observer.cjs');
const {metrics,qualifyInteraction,distributions}=require('./interaction-evidence.cjs');
function harnessIdentity() {
  const names=['interaction.cjs','interaction-server.cjs','interaction-observer.cjs','interaction-evidence.cjs','interaction.test.cjs','README.md','lab.cjs','lab-evidence.cjs','transport.cjs','transport-evidence.cjs','../ui/generated-specs/helpers/search.js','../ui/generated-specs/helpers/document.js'];
  return Object.fromEntries(names.map(name=>{const bytes=fs.readFileSync(path.join(__dirname,name));return [name,{bytes:bytes.length,sha256:digest(bytes)}];}));
}
async function measureInteraction(options) {
  const {sourceRoot,sourceSha,cycles=3,output}=options;
  if(!Number.isInteger(cycles)||cycles<3||cycles>10) throw new Error('Select three to ten repeated actual reader cycles');
  const selected=selectFixture(options);
  const {execFileSync}=require('node:child_process');
  for(const name of ['lab.cjs','lab-evidence.cjs']) {
    const committed=execFileSync('git',['-C',sourceRoot,'show',sourceSha+':tests/bijux-docs/performance/'+name]);
    if(!committed.equals(fs.readFileSync(path.join(__dirname,name)))) throw new Error('Declared emulation producer differs from selected source: '+name);
  }
  const {chromium}=require('playwright'),server=await startFixtureServer(selected);
  const expected={source:selected.source,accepted:selected.manifest.accepted,fixtureManifestSha256:selected.manifestSha256,siteFiles:selected.inventory,
    sourceInputs:selected.manifest.sourceInputs,assetSourceInputs:selected.manifest.assetSourceInputs,configuration:selected.manifest.configuration,toolchain:selected.manifest.toolchain};
  const report={schema:1,state:'running',scope:'source-equal retained shared Material fixture drawer/search/disclosure; bounded repeated lab interactions, not field INP/physical device/whole production qualification',
    ...expected,origin:server.origin,profile:PROFILE,profileSha256:digest(JSON.stringify(PROFILE)),cycles,commands:[],transitions:[],responses:[],pageErrors:[],failedRequests:[],harness:harnessIdentity(),
    cacheState:{initial:'cold isolated context with cleared enabled cache',cycles:'same loaded document; no new-document warm transport claim'},limits:[...selected.limits,
      'RAF records required geometry at rendering opportunities, not actual pixel paint.','Missing or below-threshold EventTiming entries remain unknown; functional qualification does not certify complete EventTiming coverage.',
      'Phone-shaped Chromium emulation is not physical mobile evidence.','Asynchronous search result readiness is distinct from EventTiming next-update latency.'],
    runtime:{node:process.version,nodeExecutable:process.execPath,nodeExecutableSha256:digest(fs.readFileSync(process.execPath)),playwright:require('playwright/package.json').version,
      playwrightPackageSha256:digest(fs.readFileSync(require.resolve('playwright/package.json'))),browserExecutable:chromium.executablePath(),browserExecutableSha256:digest(fs.readFileSync(chromium.executablePath())),host:{platform:os.platform(),release:os.release(),architecture:os.arch(),logicalCPUs:os.cpus().length,cpuModel:os.cpus()[0]?.model}}};
  const save=()=>{if(output) fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');};
  let browser,context;const pending=[];
  try {
    browser=await chromium.launch({executablePath:report.runtime.browserExecutable});report.runtime.browserVersion=browser.version();
    context=await browser.newContext({viewport:PROFILE.viewport,deviceScaleFactor:PROFILE.deviceScaleFactor,isMobile:PROFILE.isMobile,hasTouch:PROFILE.hasTouch});
    await context.addInitScript(installInteractionObserver);const page=await context.newPage();page.setDefaultTimeout(10000);
    page.on('response',response=>pending.push((async()=>{
      const value={url:response.url(),status:response.status()};report.responses.push(value);
      try {const body=await response.body();Object.assign(value,{decodedBodyBytes:body.length,decodedBodySha256:digest(body)});} catch(error) {value.bodyError=error.message;}
    })()));
    page.on('pageerror',error=>report.pageErrors.push(error.message));page.on('requestfailed',request=>report.failedRequests.push({url:request.url(),failure:request.failure()}));
    const session=await context.newCDPSession(page);await applyProfile(session,report.commands);save();
    await page.goto(server.origin+'/fixtures/long-registry/',{waitUntil:'load',timeout:10000});
    await page.waitForFunction(()=>/phone|normal|desktop|wide/.test(document.documentElement.getAttribute('data-bijux-viewport')||''),{},{timeout:10000});
    report.document=await page.evaluate(()=>({url:location.href,visibility:document.visibilityState,viewport:{width:innerWidth,height:innerHeight,deviceScaleFactor:devicePixelRatio},timeOrigin:performance.timeOrigin}));
    const drawer='[data-bijux-header-control="drawer-toggle"]',search='[data-bijux-header-control="search-toggle"]',summary='#bijux-node-3',query='[data-md-component="search-query"]',clear='.md-search__options > button[type="reset"]';
    const {nativeAnswer}=require('../ui/generated-specs/helpers/search.js');
    async function transition(cycle,name,wanted,target,action) {
      // Input begins when the real control owns its visible target after native transitions.
      await page.waitForFunction(selector=>{
        const node=document.querySelector(selector);if(!node) return false;
        const r=node.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
        return r.width>0&&r.height>0&&r.x>=0&&r.y>=0&&r.right<=innerWidth&&r.bottom<=innerHeight&&(hit===node||node.contains(hit));
      },target,{timeout:10000});
      await page.evaluate(({name,wanted,target})=>window.__bijuxInteraction.arm(name,wanted,target),{name,wanted,target});
      let error;
      try {await action();await page.waitForFunction(()=>window.__bijuxInteraction.ready(),{},{timeout:10000});await page.waitForTimeout(100);}
      catch(value) {error=value.stack||value.message;}
      const value=await page.evaluate(()=>window.__bijuxInteraction.finish());Object.assign(value,{cycle,actionError:error||null});value.metrics=metrics(value);report.transitions.push(value);save();
      if(error) throw new Error(error);
    }
    async function focusSummary() {
      for(let count=0;count<60;count++) {if(await page.locator(summary).evaluate(node=>node===document.activeElement)) return;await page.keyboard.press('Tab');}
      throw new Error('Ordinary Tab traversal did not reach owned disclosure');
    }
    for(let cycle=1;cycle<=cycles;cycle++) {
      await transition(cycle,'drawer-open',{drawer:true,mainInert:true,focusWithinDrawer:true},drawer,()=>page.locator(drawer).click());
      await focusSummary();
      await transition(cycle,'disclosure-open',{details:true,focusedId:'bijux-node-3'},summary,()=>page.keyboard.press('Enter'));
      await transition(cycle,'disclosure-close',{details:false,focusedId:'bijux-node-3'},summary,()=>page.keyboard.press('Space'));
      await transition(cycle,'drawer-close',{drawer:false,mainInert:false,focusedControl:'drawer-toggle'},summary,()=>page.keyboard.press('Escape'));
      await transition(cycle,'search-open',{search:true,focusQuery:true},search,()=>page.locator(search).click());
      await transition(cycle,'search-answer',{query:'resilient navigation',knownAnswer:true},query,async()=>{await page.keyboard.type('resilient navigation',{delay:25});await nativeAnswer(page);});
      await transition(cycle,'search-clear',{query:'',focusQuery:true,resultCount:0,meta:'Type to start searching'},clear,()=>page.locator(clear).click({position:{x:4,y:4}}));
      await transition(cycle,'search-close',{search:false,focusedControl:'search-toggle'},query,()=>page.keyboard.press('Escape'));
    }
    await Promise.all(pending);await session.detach();report.state='complete';
  } catch(error) {report.state='failed';report.failure=error.stack||error.message;}
  finally {
    if(context) {await context.close();report.contextClosed=true;}
    if(browser) {await browser.close();report.browserClosed=true;}
    await Promise.all(pending);await server.close();report.serverClosed=true;report.serverResponses=server.responses;
    report.harnessUnchanged=JSON.stringify(harnessIdentity())===JSON.stringify(report.harness);
    report.fixtureUnchanged=JSON.stringify(inventory(selected.directory))===JSON.stringify(selected.inventory);
    try {selectFixture(options);report.sourceUnchanged=true;} catch(error) {report.sourceUnchanged=false;report.sourceFenceError=error.message;}
    report.qualification=qualifyInteraction(report,expected);
    if(report.failure||!report.sourceUnchanged) {report.qualification.result='fail';report.qualification.errors.push(report.failure||report.sourceFenceError);}
    report.distributions=distributions(report.transitions);save();
  }
  return {report,expected};
}
async function main() {
  const {values}=parseArgs({options:{'source-root':{type:'string'},'source-sha':{type:'string'},'fixture-dir':{type:'string'},'fixture-manifest':{type:'string'},'fixture-manifest-sha256':{type:'string'},cycles:{type:'string',default:'3'},output:{type:'string'}}});
  const root=fs.realpathSync(values['source-root']),output=path.resolve(root,values.output||'');
  if(!output.startsWith(path.join(root,'artifacts')+path.sep)) throw new Error('Interaction output must remain under owning artifacts');
  fs.mkdirSync(path.dirname(output),{recursive:true});process.env.TMPDIR=path.join(path.dirname(output),'browser-scratch');fs.mkdirSync(process.env.TMPDIR,{recursive:true});
  const {report}=await measureInteraction({sourceRoot:root,sourceSha:values['source-sha'],fixtureDir:values['fixture-dir'],fixtureManifest:values['fixture-manifest'],fixtureManifestSha256:values['fixture-manifest-sha256'],cycles:Number(values.cycles),output});
  process.stdout.write(JSON.stringify({result:report.qualification.result,state:report.state,transitions:report.transitions.length,eventTiming:report.qualification.eventTiming,output})+'\n');
  process.exitCode=report.qualification.result==='pass'?0:1;
}
module.exports={measureInteraction,harnessIdentity};
if(require.main===module) main().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;});
