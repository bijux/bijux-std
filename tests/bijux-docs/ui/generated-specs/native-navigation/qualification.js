"use strict";
const fs = require("node:fs"), path = require("node:path"), crypto = require("node:crypto");
module.exports = async function qualifyNativeNavigation(browser, engine, definition, info, expect, manifest) {
  const origin = info.project.use.baseURL;
  const output = info.outputPath("native-navigation");
  fs.mkdirSync(output, { recursive: true });
  const fixture = { bundle_sha256: crypto.createHash("sha256").update(JSON.stringify(Object.fromEntries(Object.entries(manifest.site_files).sort(([a], [b]) => a.localeCompare(b))))).digest("hex") };
  const source = { base_candidate_commit: manifest.source_sha, patch_sha256: null, candidate_source_files: manifest.source_files };
function demand(condition,code,message){if(!condition){const e=new Error(message);e.name='NativeControlOracleError';e.code=code;throw e;}}
async function observation(page){return page.evaluate(()=>{
 const box=n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return{tag:n.tagName,id:n.id,x:r.x,y:r.y,width:r.width,height:r.height,rects:n.getClientRects().length,display:s.display,visibility:s.visibility,outline:s.outline,tabIndex:n.tabIndex};};
 const checkbox=document.querySelector('#__drawer'),nav=document.querySelector('#bijux-navigation'),label=document.querySelector('.bijux-native-drawer-label');
 return{url:location.href,htmlClass:document.documentElement.className,dir:document.body.dir,width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,checkbox:{...box(checkbox),type:checkbox.type,checked:checkbox.checked},label:{...box(label),text:label.textContent.trim(),for:label.htmlFor},drawerControls:[...document.querySelectorAll('[data-bijux-header-control="drawer-toggle"],[data-bijux-header-control="search-toggle"],[data-bijux-control-close]')].map(box),header:box(document.querySelector('header')),nav:{...box(nav),variant:nav.dataset.bijuxNavVariant,trees:nav.querySelectorAll('.bijux-tree').length,registry:[...nav.querySelectorAll('.bijux-mobile-hub__link')].map(a=>({name:a.textContent.trim(),url:a.href}))},focus:{tag:document.activeElement.tagName,id:document.activeElement.id,href:document.activeElement.href||null,name:document.activeElement.textContent.trim().slice(0,100)},hiddenSurfaces:[...document.querySelectorAll('[data-bijux-detail-strip][hidden],[data-bijux-course-strip][hidden]')].map(box)};
 });}
async function tabTo(page,record,match,maximum=128,reverse=false){
 for(let i=0;i<maximum;i++){
  const focus=await page.evaluate(()=>{const n=document.activeElement;return{tag:n.tagName,id:n.id,href:n.href||null,name:n.textContent.trim().slice(0,100),faux:n.matches('[data-bijux-header-control],[data-bijux-control-close]')};});record.tabStops.push(focus);
  if(match(focus))return focus;const key=(record.engine==='webkit'?'Alt+':'')+(reverse?'Shift+':'')+'Tab';record.keys.push(key);await page.keyboard.press(key);
 }
 throw new Error('Ordinary Tab never reached required native control/destination');
}
async function startLink(page,record){
 const summary=page.locator('#bijux-node-2');await tabTo(page,record,n=>n.id==='bijux-node-2');
 if(!await summary.evaluate(n=>n.parentElement.open)){await page.keyboard.press('Space');await expect.poll(()=>summary.evaluate(n=>n.parentElement.open)).toBe(true);}
 const link=page.locator('#bijux-navigation .bijux-tree a[href]').filter({hasText:/^\s*Getting started\s*$/}).first(),expectedURL=await link.evaluate(n=>n.href);
 await tabTo(page,record,n=>n.href===expectedURL);await page.keyboard.press('Enter');await expect(page).toHaveURL(expectedURL);await expect(page.locator('h1')).toBeVisible();record.destination={expectedURL,finalURL:page.url(),heading:await page.locator('h1').textContent()};
}
async function nativePointerCycle(page,record){
 for(const expected of[true,false]){
  const hit=await page.locator('#__drawer').evaluate(n=>{const r=n.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return{x,y,width:r.width,height:r.height,unoccluded:document.elementFromPoint(x,y)===n,checked:n.checked}});
  (record.native_pointer||=[]).push(hit);demand(hit.unoccluded&&hit.width>=24&&hit.height>=24,'native-pointer-occluded','Native input lacks an actual unoccluded pointer target');
  await page.mouse.click(hit.x,hit.y);if(expected){await expect(page.locator('#__drawer')).toBeChecked();await verifyNativePanel(page,record,'pointer-native-open');}else await expect(page.locator('#__drawer')).not.toBeChecked();
 }
}
async function verifyNativePanel(page,record,phase){
 const geometry=await page.evaluate(()=>{const box=n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,position:s.position,transform:s.transform}};return{width:innerWidth,scrollWidth:document.documentElement.scrollWidth,ready:document.body.dataset.bijuxDrawerReady||null,sidebar:box(document.querySelector('.md-sidebar--primary')),nav:box(document.querySelector('#bijux-navigation')),mainLayout:getComputedStyle(document.querySelector('.md-main__inner')).display}});
 (record.native_panels||=[]).push({phase,...geometry});
 demand(geometry.ready===null,'premature-enhancement-marker','Native fallback was hidden before successful ownership');
 demand(geometry.sidebar.position==='static'&&geometry.sidebar.transform==='none'&&geometry.mainLayout==='block','inherited-modal-position','Default fallback inherited modal/slide or flex-row layout');
 demand(geometry.nav.x>=-1&&geometry.nav.right<=geometry.width+1&&geometry.sidebar.x>=-1&&geometry.sidebar.right<=geometry.width+1,'native-panel-offscreen','Open native navigation exceeds viewport bounds');
 demand(geometry.scrollWidth<=geometry.width+1,'open-native-overflow','Native open panel causes whole-document horizontal overflow');
 if(!['delayed-native','throw-mounted-native'].includes(record.kind)||phase==='failed-mount-restored-open'){
  const name=record.engine+'-'+record.kind+'-'+record.width+'-'+phase+'.png';await page.screenshot({path:path.join(output,name),timeout:1500});record.screenshots.push(name);
 }
}
async function verifyNativeFocus(page, record) {
 for (const scheme of ["light", "dark"]) {
  await page.emulateMedia({ colorScheme: scheme, forcedColors: "none" });
  if (!record.kind.startsWith("no-js")) await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", scheme === "dark" ? "slate" : "default");
  const state = await page.locator("#__drawer").evaluate(node => {
   const outline = getComputedStyle(node), header = document.querySelector("header[data-bijux-drawer-target]"), backdrop = getComputedStyle(header);
   const box = node.getBoundingClientRect(), area = header.getBoundingClientRect();
   return { focused: node === document.activeElement, focusVisible: node.matches(":focus-visible"), outline: outline.outlineColor,
    style: outline.outlineStyle, width: parseFloat(outline.outlineWidth), opacity: outline.opacity,
    background: backdrop.backgroundColor, backgroundImage: backdrop.backgroundImage, headerOpacity: backdrop.opacity,
    box: { left: box.left, right: box.right, top: box.top, bottom: box.bottom },
    header: { left: area.left, right: area.right, top: area.top, bottom: area.bottom },
    hitOwners: [[box.left + 1, box.top + 1], [box.right - 1, box.top + 1], [box.left + 1, box.bottom - 1], [box.right - 1, box.bottom - 1]].map(([x,y]) => document.elementFromPoint(x,y) === node),
    bodyScheme: document.body.getAttribute("data-md-color-scheme"), prefersDark: matchMedia("(prefers-color-scheme: dark)").matches };
  });
  const rgb = color => { const channels = color.match(/[\d.]+/g)?.map(Number); demand(channels?.length >= 3 && (channels.length < 4 || channels[3] === 1), "nonopaque-focus-sample", "Focus/backdrop must be an opaque computed RGB sample"); return channels.slice(0, 3); };
  const luminance = color => rgb(color).map(v => { v /= 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
  const light = luminance(state.outline), dark = luminance(state.background); state.contrast = (Math.max(light, dark) + .05) / (Math.min(light, dark) + .05);
  (record.native_focus ||= []).push({ requestedScheme: scheme, ...state });
  demand(state.focused && state.focusVisible && state.style === "solid" && state.width >= 2 && Number(state.opacity) === 1, "native-focus-not-visible", "Ordinary native keyboard focus lacks a visible opaque solid outline");
  demand(state.backgroundImage === "none" && Number(state.headerOpacity) === 1 && state.box.left - 5 >= state.header.left && state.box.right + 5 <= state.header.right && state.box.top - 5 >= state.header.top && state.box.bottom + 5 <= state.header.bottom, "unqualified-focus-backdrop", "Measured focus must stay within the actual opaque flat header backdrop");
  demand(state.box.right - state.box.left >= 44 && state.box.bottom - state.box.top >= 44 && state.hitOwners.every(Boolean), "native-primary-target-size", "Native primary navigation requires an unoccluded 44 by 44 CSS pixel hit area");
  demand(state.contrast >= 3, "native-focus-low-contrast", "Native keyboard focus contrast is below 3:1");
 }
}
async function nativeFlow(page,record,desktop=false){
 const checkbox=page.locator('#__drawer'),before=await observation(page);record.observations.push(before);
 demand(before.nav.variant==='complete'&&before.nav.trees===1&&before.nav.registry.length===9,'wrong-static-tree','Expected one unchanged complete native tree and nine sites');
 demand(before.hiddenSurfaces.every(b=>b.rects===0),'hidden-strip-painted','Inactive strips paint in degraded mode');
 if(!desktop){
  await expect(checkbox).toBeVisible();await expect(checkbox).toHaveAccessibleName('Navigation');record.native_accessibility=await checkbox.ariaSnapshot();
  demand(before.checkbox.width>=24&&before.checkbox.height>=24,'native-target-too-small','Native control lacks24px dimensions');
  demand(before.label.for==='__drawer'&&before.label.width>0&&before.label.text==='Navigation','invalid-native-label','Native checkbox lacks its visible associated readable label');
  demand(before.drawerControls.every(b=>b.rects===0),'faux-control-focus','JavaScript-only labels remain visible/focusable in degraded mode');
  demand(before.scrollWidth-before.width<=1,'degraded-horizontal-overflow','Readable native control causes horizontal page overflow');
  if(await checkbox.evaluate(n=>n===document.activeElement&&!n.matches(':focus-visible'))){const advance=record.engine==='webkit'?'Alt+Tab':'Tab';record.keys.push(advance);await page.keyboard.press(advance);await tabTo(page,record,n=>n.id==='__drawer',128,true);}else await tabTo(page,record,n=>n.id==='__drawer');await verifyNativeFocus(page,record);await page.keyboard.press('Space');await expect(checkbox).toBeChecked();await expect(page.locator('#bijux-navigation')).toBeVisible();await verifyNativePanel(page,record,'native-open');record.observations.push(await observation(page));
  const advance=record.engine==='webkit'?'Alt+Tab':'Tab';record.keys.push(advance);await page.keyboard.press(advance);await tabTo(page,record,n=>n.id==='__drawer',128,true);await page.keyboard.press('Space');await expect(checkbox).not.toBeChecked();await expect(page.locator('#bijux-navigation')).toBeHidden();record.observations.push(await observation(page));
  await page.keyboard.press('Space');await expect(checkbox).toBeChecked();
 }else{await expect(checkbox).toBeHidden();await expect(page.locator('#bijux-navigation')).toBeVisible();}
 await startLink(page,record);
}
async function run(browser,engine,definition){
 const label=definition.route==='/'?'hub':definition.route==='/fixtures/rtl/'?'rtl':'core-deep',prefix=engine+'-'+definition.kind+'-'+label+'-'+definition.width;
 const record={engine,version:browser.version(),...definition,classification:'Generated native fallback source/bundle qualification; no publication authority',base_candidate_sha:source.base_candidate_commit,candidate_patch_sha256:source.patch_sha256,bundle_sha256:fixture.bundle_sha256,started_at:new Date().toISOString(),keyboard_protocol:engine==='webkit'?'Option-Tab forward / Option-Shift-Tab backward':'Tab forward / Shift-Tab backward',keys:[],tabStops:[],observations:[],page_errors:[],console:[],requests:[],responses:[],screenshots:[]};
 let context,page,releaseDelay;
 let held=false;const delayed=new Promise(resolve=>releaseDelay=resolve);
 try{
  context=await browser.newContext({javaScriptEnabled:!definition.kind.startsWith('no-js'),viewport:{width:definition.width,height:900}});context.setDefaultTimeout(4000);
  await context.route('**/*',async handler=>{const url=new URL(handler.request().url());record.requests.push({url:url.href,type:handler.request().resourceType(),external:url.origin!==origin});if(url.origin!==origin)await handler.abort('blockedbyclient');
   else if(url.pathname.endsWith('/shell/bootstrap.js')&&definition.kind==='delayed-native'&&!held){held=true;record.held_bootstrap=url.href;await delayed;await handler.continue();}
   else if(url.pathname.endsWith('/shell/bootstrap.js')&&definition.kind.startsWith('throw-')){
    if(definition.kind==='throw-mounted-native'&&!held){held=true;record.held_bootstrap=url.href;await delayed;}
    const response=await handler.fetch(),body=await response.text();
    const injected=definition.kind==='throw-before-native'?'throw new Error("bijux qualification before bootstrap");\n'+body:body.replace('      shell.detailTabs?.runDetailTabsSync?.();','      throw new Error("bijux qualification failed mount");');
    demand(injected!==body,'missing-fault-site','Exact reviewed bootstrap fault site absent');
    const sha=body=>require('crypto').createHash('sha256').update(body).digest('hex');demand(sha(body)===source.candidate_source_files['scripts/bootstrap.js'],'wrong-original-fault-source','Injected fault did not start from the selected source');record.fault_injection={url:url.href,original_sha256:sha(body),injected_sha256:sha(injected),mechanism:definition.kind,expected_error:definition.kind==='throw-before-native'?'bijux qualification before bootstrap':'bijux qualification failed mount'};await handler.fulfill({response,body:injected});
   }else await handler.continue();});
  page=await context.newPage();page.on('pageerror',e=>record.page_errors.push({name:e.name,message:e.message,stack:e.stack}));page.on('console',m=>{if(['error','warning'].includes(m.type()))record.console.push({type:m.type(),message:m.text()});});page.on('response',p=>record.responses.push({url:p.url(),status:p.status()}));
  await page.goto(origin+definition.route,{waitUntil:['delayed-native','throw-mounted-native'].includes(definition.kind)?'commit':'load'});await expect(page.locator('main')).toBeVisible();
  if(!['delayed-native','throw-mounted-native'].includes(definition.kind)){const initial=prefix+'-initial.png';await page.screenshot({path:path.join(output,initial)});record.screenshots.push(initial);}
  if(definition.kind==='delayed-native'){
   await expect(page.locator('html')).toHaveClass(/\bjs\b/);await expect(page.locator('body')).not.toHaveAttribute('data-bijux-drawer-ready','true');
   const checkbox=page.locator('#__drawer');await expect(checkbox).toBeVisible();await tabTo(page,record,n=>n.id==='__drawer');await verifyNativeFocus(page,record);await page.keyboard.press('Space');await expect(checkbox).toBeChecked();await expect(page.locator('#bijux-navigation')).toBeVisible();await verifyNativePanel(page,record,'native-open');record.observations.push(await observation(page));
   await page.keyboard.press('Space');await expect(checkbox).not.toBeChecked();await page.keyboard.press('Space');await expect(checkbox).toBeChecked();releaseDelay();await expect(page.locator('body')).toHaveAttribute('data-bijux-drawer-ready','true');await expect(checkbox).toBeHidden();
   const trigger=page.locator('[data-bijux-header-control="drawer-toggle"]');await expect(checkbox).toBeChecked();await page.keyboard.press('Escape');await expect(trigger).toBeFocused();await trigger.click();await expect(checkbox).toBeChecked();await page.keyboard.press('Escape');await expect(trigger).toBeFocused();record.result_transition='Native fallback while real bootstrap response held; owned successful mount enables enhanced drawer';
  }else if(definition.kind.startsWith('throw-')){
   if(definition.kind==='throw-mounted-native'){const checkbox=page.locator('#__drawer');await expect(checkbox).toBeVisible();await tabTo(page,record,n=>n.id==='__drawer');await verifyNativeFocus(page,record);await page.keyboard.press('Space');await expect(checkbox).toBeChecked();await verifyNativePanel(page,record,'held-before-mount');record.observations.push(await observation(page));releaseDelay();await expect.poll(()=>record.page_errors.map(e=>e.message)).toContain('bijux qualification failed mount');}
   await expect(page.locator('html')).toHaveClass(/\bjs\b/);await expect(page.locator('body')).not.toHaveAttribute('data-bijux-drawer-ready','true');
   record.cleanup=await page.evaluate(()=>({ready:document.body.hasAttribute('data-bijux-drawer-ready'),open:document.body.hasAttribute('data-bijux-drawer-open'),sidebarInert:document.querySelector('.md-sidebar--primary').inert,background:[...document.querySelectorAll('.md-content,.md-sidebar--secondary,.md-footer')].map(n=>n.inert),role:document.querySelector('.md-sidebar--primary').getAttribute('role'),modal:document.querySelector('.md-sidebar--primary').getAttribute('aria-modal')}));
   demand(!record.cleanup.ready&&!record.cleanup.open&&!record.cleanup.sidebarInert&&record.cleanup.background.every(v=>!v)&&!record.cleanup.role&&!record.cleanup.modal,'failed-mount-leaked-owned-state','Failed mount retained readiness, inert, modal or owned open state');
   if(definition.kind==='throw-mounted-native'){const checkbox=page.locator('#__drawer');await expect(checkbox).toBeChecked();await verifyNativePanel(page,record,'failed-mount-restored-open');await tabTo(page,record,n=>n.id==='__drawer',128,true);await page.keyboard.press('Space');await expect(checkbox).not.toBeChecked();}
   if(definition.kind==='throw-before-native')await nativePointerCycle(page,record);
   await nativeFlow(page,record);
  }else if(definition.kind==='js-preservation'){
   await expect(page.locator('html')).toHaveClass(/\bjs\b/);await expect(page.locator('body')).toHaveAttribute('data-bijux-drawer-ready','true');await expect(page.locator('.bijux-native-drawer-label')).toBeHidden();await expect(page.locator('#__drawer')).toBeHidden();demand(await page.locator('#__drawer').count()===1&&await page.locator('#bijux-navigation .bijux-tree').count()===1,'duplicated-tree-or-control','Proposal duplicated native tree/input');
   if(definition.width<1220){const trigger=page.locator('[data-bijux-header-control="drawer-toggle"]');await expect(trigger).toHaveJSProperty('tagName','BUTTON');await trigger.click();await expect(page.locator('#__drawer')).toBeChecked();await page.keyboard.press('Escape');await expect(trigger).toBeFocused();await page.keyboard.press('Space');await expect(page.locator('#__drawer')).toBeChecked();await page.keyboard.press('Escape');await expect(trigger).toBeFocused();await trigger.click();}
   const core=page.locator('#bijux-navigation .bijux-mobile-hub__link').filter({hasText:/^Core$/});await core.click();await expect(page).toHaveURL(origin+'/bijux-core/');await expect(page.locator('h1')).toHaveText(/^Product overview(?:¶)?$/);record.destination={finalURL:page.url(),heading:await page.locator('h1').textContent()};
  }else if(definition.kind==='no-js-resize'){
   for(const width of[767,768,1219,1220,767]){await page.setViewportSize({width,height:900});const seen=await observation(page);record.observations.push(seen);demand(seen.hiddenSurfaces.every(b=>b.rects===0),'resize-hidden-paint','Inactive strips paint at boundary');demand((seen.checkbox.rects>0)===(width<1220),'wrong-native-breakpoint','Native checkbox availability mismatches drawer breakpoint');demand(seen.scrollWidth-width<=1,'resize-overflow','Native control overflows viewport');}
   await nativeFlow(page,record);
  }else{if(definition.kind==='no-js-pointer')await nativePointerCycle(page,record);if(definition.kind==='no-js-rtl')demand((await observation(page)).dir==='rtl','missing-actual-rtl','Fixture did not render admitted Material direction=rtl');await nativeFlow(page,record,definition.kind==='no-js-desktop');}
  record.observations.push(await observation(page));const ending=prefix+'-destination.png';await page.screenshot({path:path.join(output,ending)});record.screenshots.push(ending);
  demand(record.page_errors.every(e=>definition.kind.startsWith('throw-')&&e.message===record.fault_injection?.expected_error),'uncaught-page-error','Unexpected browser page errors');if(definition.kind.startsWith('throw-'))demand(record.page_errors.length>=1,'missing-actual-fault','Declared initialization fault was not actually observed');demand(record.responses.every(p=>p.status<400),'local-asset-failure','Required local candidate artifact request failed');record.result='pass';
 }catch(e){record.result='fail';record.failure={name:e.name,code:e.code||null,message:e.message,stack:e.stack};if(page){try{record.observations.push(await observation(page));const name=prefix+'-failure.png';await page.screenshot({path:path.join(output,name),timeout:1500});record.screenshots.push(name);}catch(e){record.snapshot_failure=e.message;}}}
 finally{releaseDelay();if(context)await context.close();record.closed_at=new Date().toISOString();fs.writeFileSync(path.join(output,prefix+'.json'),JSON.stringify(record,null,2)+'\n');}
 return record;
}
  const record = await run(browser, engine, definition);
  await info.attach("native-navigation-evidence", { body: Buffer.from(JSON.stringify(record, null, 2)), contentType: "application/json" });
  expect(record.result, JSON.stringify(record.failure)).toBe("pass");
};
