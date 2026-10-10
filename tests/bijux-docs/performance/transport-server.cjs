'use strict';
const http=require('node:http');
const {gzipSync}=require('node:zlib');
const {digest}=require('./transport-evidence.cjs');

function documentHtml(diagram, {vendorPath, eagerPlain=false, authoredSource}) {
  return `<!doctype html><html><head><meta charset="utf-8"><title>Owned diagram transport</title></head><body data-md-color-scheme="default">
<header><img src="/assets/bijux_logo.png" width="48" height="48" alt="Bijux"></header>
<main class="md-typeset"><h1>${diagram?'Diagram reading':'Plain reading'}</h1>
<a href="${diagram?'/plain/':'/diagram/?warm=1'}">${diagram?'Read plain page':'Read diagram'}</a>
<button type="button" id="theme">Change theme</button>
${diagram?'<pre class="bijux-diagram"><code>'+authoredSource+'</code></pre>':'<p>Plain content remains readable without the optional renderer.</p>'}</main>
<script>document.querySelector('#theme').addEventListener('click',()=>{document.body.dataset.mdColorScheme=document.body.dataset.mdColorScheme==='default'?'slate':'default';dispatchEvent(new CustomEvent('bijux:theme-change'));});</script>
<script src="/assets/javascripts/mermaid-init.js"></script>${!diagram&&eagerPlain?'<script src="'+vendorPath+'"></script>':''}
</body></html>`;
}

async function startServer({assets,vendorPath,authoredSource,encoding='gzip',cacheControl='public, max-age=3600',eagerPlain=false,vendorFault=null}) {
  if(!['gzip','identity'].includes(encoding)) throw new Error('Select a declared gzip or identity representation');
  if(!['public, max-age=3600','no-store'].includes(cacheControl)) throw new Error('Select a finite declared controlled cache policy');
  if(![null,'missing','changed'].includes(vendorFault)) throw new Error('Unknown controlled vendor fault');
  const responses=[];
  const server=http.createServer((req,res)=>{
    const path=new URL(req.url,'http://127.0.0.1').pathname;
    let body=assets[path],type=path.endsWith('.png')?'image/png':'application/javascript';
    if(path===vendorPath && vendorFault==='missing') body=null;
    if(path===vendorPath && vendorFault==='changed') body=Buffer.concat([body,Buffer.from('\n/* changed controlled response */')]);
    if(path==='/plain/' || path==='/diagram/') {body=Buffer.from(documentHtml(path==='/diagram/',{vendorPath,eagerPlain,authoredSource}));type='text/html; charset=utf-8';}
    const status=body?200:path==='/favicon.ico'?204:404;
    body=body||Buffer.alloc(0);
    const compress=encoding==='gzip' && /(?:^|[, ])gzip(?:[, ;]|$)/.test(req.headers['accept-encoding']||'') && body.length>0;
    const encoded=compress?gzipSync(body):body;
    const headers={'Content-Type':type,'Content-Length':String(encoded.length),'Cache-Control':type.startsWith('text/html')?'no-store':cacheControl,'Vary':'Accept-Encoding'};
    if(compress) headers['Content-Encoding']='gzip';
    res.writeHead(status,headers);
    res.on('finish',()=>responses.push({sequence:responses.length,url:req.url,path,status,requestMethod:req.method,requestHeaders:req.headers,responseHeaders:headers,rawBytes:body.length,rawSha256:digest(body),encodedBodyBytes:encoded.length,encodedBodySha256:digest(encoded),observedAt:new Date().toISOString(),scope:'server body and declared headers; actual packet/header wire size unobserved'}));
    res.end(encoded);
  });
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  const origin=`http://127.0.0.1:${server.address().port}`;
  return {origin,responses,async close(){await new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()));}};
}
module.exports={documentHtml,startServer};
