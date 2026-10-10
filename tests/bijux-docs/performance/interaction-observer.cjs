'use strict';

function installInteractionObserver() {
  const supported=Array.from(PerformanceObserver.supportedEntryTypes||[]),entries=[],errors=[],observers=[];
  let active=null,droppedEntries=0,sequence=0;
  function owner(node) {return node?{tag:node.tagName,id:node.id,control:node.closest?.('[data-bijux-header-control]')?.getAttribute('data-bijux-header-control')||null}:null;}
  function rectangle(node) {
    if(!node) return null;
    const r=node.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
    return {x:r.x,y:r.y,width:r.width,height:r.height,inViewport:r.x>=0&&r.y>=0&&r.right<=innerWidth&&r.bottom<=innerHeight,centerOwned:hit===node||node.contains(hit)};
  }
  function state() {
    const query=document.querySelector('[data-md-component="search-query"]'),focus=document.activeElement;
    const visibleLinks=Array.from(document.querySelectorAll('.md-search-result__link')).filter(link=>link.getClientRects().length);
    const knownAnswer=visibleLinks.some(link=>{const url=new URL(link.href,location.href);return /\/details\/leaf\/$/.test(url.pathname)&&url.searchParams.get('h')===query?.value&&query.value==='resilient navigation';});
    return {drawer:document.querySelector('#__drawer')?.checked===true,search:document.querySelector('#__search')?.checked===true,
      mainInert:document.querySelector('.md-content')?.inert===true,focusWithinDrawer:!!document.querySelector('#bijux-navigation')?.contains(focus),
      focusedControl:focus?.closest?.('[data-bijux-header-control]')?.getAttribute('data-bijux-header-control')||null,focusedId:focus?.id||null,
      focusQuery:focus===query,query:query?.value||'',knownAnswer:knownAnswer&&window.bijuxSearchWorker?.state.stage==='worker-ready',resultCount:visibleLinks.length,
      meta:document.querySelector('.md-search-result__meta')?.textContent.trim()||'',details:document.querySelector('#bijux-node-3')?.parentElement.open===true,
      focus:owner(focus),focusRectangle:rectangle(focus),drawerRectangle:rectangle(document.querySelector('#bijux-navigation'))};
  }
  const serialize=entry=>({name:entry.name,entryType:entry.entryType,startTime:entry.startTime,duration:entry.duration,processingStart:entry.processingStart,
    processingEnd:entry.processingEnd,interactionId:entry.interactionId,cancelable:entry.cancelable,target:owner(entry.target)});
  if(supported.includes('event')) try {
    const observer=new PerformanceObserver((list,owned,options)=>{entries.push(...list.getEntries().map(serialize));droppedEntries+=options?.droppedEntriesCount||0;});
    observer.observe({type:'event',buffered:true,durationThreshold:16});observers.push(observer);
  } catch(error) {errors.push(error.message);}
  for(const type of ['click','keydown','input']) addEventListener(type,event=>{
    if(active) active.inputs.push({type,key:event.key||null,isTrusted:event.isTrusted,eventTimeStamp:event.timeStamp,capturedAt:performance.now(),target:owner(event.target)});
  },{capture:true,passive:true});
  const matches=(actual,wanted)=>Object.entries(wanted).every(([key,value])=>actual[key]===value);
  function frame(at,id) {
    if(!active||active.id!==id) return;
    const actual=state(),value={at:performance.now(),frameTime:at,state:actual};active.frames.push(value);
    if(matches(actual,active.expected)) {if(!active.firstMatch) active.firstMatch=value;else if(!active.secondMatch) active.secondMatch=value;}
    requestAnimationFrame(at=>frame(at,id));
  }
  window.__bijuxInteraction={
    arm(name,expected,targetSelector) {
      if(active) throw new Error('A reader transition is already active');
      active={id:++sequence,name,expected,armedAt:performance.now(),before:state(),targetBefore:rectangle(document.querySelector(targetSelector)),inputs:[],frames:[],firstMatch:null,secondMatch:null};
      const id=active.id;requestAnimationFrame(at=>frame(at,id));return id;
    },
    ready(){return !!active?.secondMatch;},
    finish() {
      if(!active) throw new Error('No armed reader transition');
      for(const observer of observers) entries.push(...observer.takeRecords().map(serialize));
      const value={...active,finishedAt:performance.now(),after:state(),supported,observerErrors:[...errors],droppedEntries,
        eventEntries:entries.filter(entry=>entry.startTime>=active.armedAt&&entry.startTime<=performance.now())};
      active=null;return value;
    },
    snapshot(){return {active,supported,errors,droppedEntries,entries,timeOrigin:performance.timeOrigin,visibility:document.visibilityState,viewport:{width:innerWidth,height:innerHeight,deviceScaleFactor:devicePixelRatio}};}
  };
}
module.exports={installInteractionObserver};
