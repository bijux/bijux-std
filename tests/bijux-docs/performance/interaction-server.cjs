'use strict';
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const {gzipSync}=require('node:zlib');
const {execFileSync}=require('node:child_process');
const {isDeepStrictEqual}=require('node:util');
const {digest}=require('./transport-evidence.cjs');

const PREFIX='fixtures/long-registry/';
const relevant=name=>['partials/','styles/','scripts/','tooling/material/','tooling/configuration/'].some(prefix=>name.startsWith(prefix)) || ['config/mkdocs-baseline.json','config/hub-links.json'].includes(name);
function inventory(root) {
  const result={};
  function visit(directory) {
    for(const entry of fs.readdirSync(directory,{withFileTypes:true})) {
      const absolute=path.join(directory,entry.name);
      if(entry.isSymbolicLink()) throw new Error('Fixture symlink authority is not admitted');
      if(entry.isDirectory()) visit(absolute);
      else if(entry.isFile()) {const bytes=fs.readFileSync(absolute);result[path.relative(root,absolute).split(path.sep).join('/')]={bytes:bytes.length,sha256:digest(bytes)};}
      else throw new Error('Unsupported fixture file kind');
    }
  }
  visit(root);return Object.fromEntries(Object.entries(result).sort(([a],[b])=>a<b?-1:a>b?1:0));
}
function selectFixture({sourceRoot,sourceSha,fixtureDir,fixtureManifest,fixtureManifestSha256}) {
  if(!/^[0-9a-f]{40}$/.test(sourceSha||'')||!/^[0-9a-f]{64}$/.test(fixtureManifestSha256||'')) throw new Error('Select full committed source and externally pinned fixture manifest digest');
  const manifestBytes=fs.readFileSync(fixtureManifest);
  if(digest(manifestBytes)!==fixtureManifestSha256) throw new Error('Pinned fixture manifest differs');
  const manifest=JSON.parse(manifestBytes),root=fs.realpathSync(sourceRoot),directory=fs.realpathSync(fixtureDir);
  if(!directory.startsWith(path.join(root,'artifacts')+path.sep)||!fs.realpathSync(fixtureManifest).startsWith(path.join(root,'artifacts')+path.sep)) throw new Error('Fixture inputs must belong to owning artifacts');
  const generatorPath=path.resolve(path.dirname(fixtureManifest),manifest.generator.path);
  if(!generatorPath.startsWith(path.dirname(fs.realpathSync(fixtureManifest))+path.sep)) throw new Error('Generator manifest escapes owning packet');
  const generatorBytes=fs.readFileSync(generatorPath);
  if(digest(generatorBytes)!==manifest.generator.sha256) throw new Error('Frozen generator manifest differs');
  const generator=JSON.parse(generatorBytes),scenario=generator.scenarios.find(item=>item.route==='/'+PREFIX&&item.kind==='long');
  if(manifest.schema!==1||generator.source_sha!==manifest.accepted.sha||generator.source_tree_dirty!==false||!scenario||!isDeepStrictEqual(scenario.configuration,manifest.configuration.assertion)||manifest.configuration.physicalReread!==false) throw new Error('Accepted source/configuration assertion differs');
  if(!/^[0-9a-f]{40}$/.test(manifest.accepted.tree)||manifest.accepted.origin!=='https://github.com/bijux/bijux-std.git') throw new Error('Exact accepted standard provenance is required');
  const names=Object.keys(generator.source_files).filter(relevant).sort();
  if(names.length!==53||JSON.stringify(names)!==JSON.stringify(Object.keys(manifest.sourceInputs).sort())) throw new Error('Complete selected shell source ownership is required');
  const git=(args)=>execFileSync('git',['-C',root,...args],{maxBuffer:8*1024*1024});
  if(git(['rev-parse','HEAD']).toString().trim()!==sourceSha) throw new Error('Selected source differs from current head');
  if(git(['rev-parse',manifest.accepted.sha+'^{tree}']).toString().trim()!==manifest.accepted.tree) throw new Error('Accepted tree differs from retained committed identity');
  const origin=git(['remote','get-url','origin']).toString().trim();
  if(!/^(https:\/\/github\.com\/bijux\/bijux-std(?:\.git)?|git@github\.com:bijux\/bijux-std\.git)$/.test(origin)) throw new Error('Selected source origin is not bijux-std GitHub');
  const assetNames=Object.keys(generator.source_files).filter(name=>name.startsWith('assets/')).sort();
  if(!isDeepStrictEqual(assetNames,Object.keys(manifest.assetSourceInputs||{}).sort())) throw new Error('Owned static asset source inputs are incomplete');
  for(const name of [...names,...assetNames]) {
    const relative='shared/bijux-docs/'+name,bytes=git(['show',sourceSha+':'+relative]);
    if(digest(bytes)!==generator.source_files[name]||(manifest.sourceInputs[name]||manifest.assetSourceInputs[name])!==digest(bytes)||!bytes.equals(fs.readFileSync(path.join(root,relative)))) throw new Error('Shared shell source continuity differs: '+name);
  }
  const actual=inventory(directory),expectedKeys=Object.keys(generator.site_files).filter(name=>name.startsWith(PREFIX)).map(name=>name.slice(PREFIX.length)).sort();
  if(JSON.stringify(Object.keys(actual).sort())!==JSON.stringify(expectedKeys)||!isDeepStrictEqual(actual,manifest.siteFiles)) throw new Error('Full finite fixture inventory differs');
  for(const name of expectedKeys) if(actual[name].sha256!==generator.site_files[PREFIX+name]) throw new Error('Served fixture differs from frozen canonical bundle: '+name);
  if(expectedKeys.filter(name=>name.endsWith('.html')).length!==32) throw new Error('All finite canonical routes including authored 404 must remain');
  return {directory,manifest,manifestSha256:fixtureManifestSha256,source:{sha:sourceSha,tree:git(['rev-parse',sourceSha+'^{tree}']).toString().trim(),origin},inventory:actual,
    limits:['Physical generated configuration was not retained for reread; its exact producer-manifest assertion is retained.','Material and MkDocs generated bytes/toolchain remain bound to historical accepted source; all53 selected shared shell inputs equal current committed source.']};
}
async function startFixtureServer(selected) {
  const responses=[],mime={'.html':'text/html; charset=utf-8','.js':'application/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon','.woff2':'font/woff2','.txt':'text/plain'};
  const server=http.createServer((req,res)=>{
    let pathname;try {pathname=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname);} catch {res.writeHead(400);res.end();return;}
    let relative=pathname.startsWith('/'+PREFIX)?pathname.slice(PREFIX.length+1):null;
    if(relative!==null&&(relative===''||relative.endsWith('/'))) relative+='index.html';
    const safe=relative!==null&&!relative.includes('\\')&&!relative.split('/').includes('..')&&Object.hasOwn(selected.inventory,relative);
    let body=safe?fs.readFileSync(path.join(selected.directory,relative)):Buffer.alloc(0),status=safe?200:404;
    if(safe&&(digest(body)!==selected.inventory[relative].sha256||body.length!==selected.inventory[relative].bytes)) {status=409;body=Buffer.alloc(0);}
    const type=mime[path.extname(relative||'')]||'application/octet-stream';
    const compressed=body.length>0&&/(?:^|[, ])gzip(?:[, ;]|$)/.test(req.headers['accept-encoding']||'');
    const encoded=compressed?gzipSync(body):body,headers={'Content-Type':type,'Content-Length':String(encoded.length),'Cache-Control':type.startsWith('text/html')?'no-store':'public, max-age=3600','Vary':'Accept-Encoding'};
    if(compressed) headers['Content-Encoding']='gzip';res.writeHead(status,headers);
    res.on('finish',()=>responses.push({path:pathname,status,method:req.method,rawBytes:body.length,rawSha256:digest(body),encodedBodyBytes:encoded.length,encodedBodySha256:digest(encoded),headers,scope:'controlled encoded response body; packet/header wire bytes unobserved'}));
    res.end(req.method==='HEAD'?undefined:encoded);
  });
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  return {origin:'http://127.0.0.1:'+server.address().port,responses,async close(){await new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()));}};
}
module.exports={PREFIX,relevant,inventory,selectFixture,startFixtureServer};
