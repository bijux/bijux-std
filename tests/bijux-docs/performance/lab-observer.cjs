'use strict';

function installLabObserver() {
  const types=['largest-contentful-paint','layout-shift','longtask'];
  const supported=typeof PerformanceObserver==='function' ? Array.from(PerformanceObserver.supportedEntryTypes||[]) : [];
  const entries=Object.fromEntries(types.map(type=>[type,[]]));
  const errors=[],observers=[];
  let droppedEntries=0;
  const serialize=entry=>{
    const value={entryType:entry.entryType,startTime:entry.startTime,duration:entry.duration};
    if(entry.entryType==='largest-contentful-paint') Object.assign(value,{renderTime:entry.renderTime,loadTime:entry.loadTime,size:entry.size,url:entry.url,
      element:entry.element ? {tag:entry.element.tagName,id:entry.element.id,text:entry.element.textContent?.slice(0,100)} : null});
    if(entry.entryType==='layout-shift') Object.assign(value,{value:entry.value,hadRecentInput:entry.hadRecentInput,
      sources:Array.from(entry.sources||[]).map(source=>({node:source.node?{tag:source.node.tagName,id:source.node.id}:null,previousRect:source.previousRect.toJSON(),currentRect:source.currentRect.toJSON()}))});
    if(entry.entryType==='longtask') Object.assign(value,{name:entry.name,attribution:Array.from(entry.attribution||[]).map(item=>({name:item.name,containerType:item.containerType,containerId:item.containerId,containerSrc:item.containerSrc}))});
    return value;
  };
  const append=(type,values)=>entries[type].push(...values.map(serialize));
  for(const type of types) {
    if(!supported.includes(type)) continue;
    try {
      const observer=new PerformanceObserver((list,owned,options)=>{
        append(type,list.getEntries());
        if(options?.droppedEntriesCount) droppedEntries+=options.droppedEntriesCount;
      });
      observer.observe({type,buffered:true});observers.push({type,observer});
    } catch(error) {errors.push({type,message:error.message});}
  }
  window.__bijuxLab={snapshot(){
    for(const {type,observer} of observers) append(type,observer.takeRecords());
    return {supported,entries,errors,droppedEntries,observationEndMs:performance.now(),timeOrigin:performance.timeOrigin,
      visibility:document.visibilityState,readyState:document.readyState,viewport:{width:innerWidth,height:innerHeight,deviceScaleFactor:devicePixelRatio},
      navigator:{onLine:navigator.onLine,userAgent:navigator.userAgent,maxTouchPoints:navigator.maxTouchPoints},
      scope:'navigation-start through this bounded snapshot; not full page lifetime or field metrics'};
  },disconnect(){for(const {observer} of observers) observer.disconnect();}};
}
module.exports={installLabObserver};
