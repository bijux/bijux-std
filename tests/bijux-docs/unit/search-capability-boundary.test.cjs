const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const source = fs.readFileSync(path.join(__dirname,'../../../shared/bijux-docs/tooling/material/search-capability-boundary.js'),'utf8');
const parent = 'a'.repeat(64), report = 'b'.repeat(64);
const base = 'https://bijux.io/bijux-pollenomics/';
const table = [['public/nordic-atlas/index.html',parent],['report/regions/nordic/nordic_map.html',report]];
function payload(route='index.html',partition='ordinary') {return {schema:1,site_url:base,document_route:route,document_partition:partition,route_partitions:table,table_sha256:'c'.repeat(64)};}
function setup(value=payload(),route='',nodes=1,raw=false) {
 const node = {content:raw ? value : JSON.stringify(value)};
 const location = new URL(base+route);
 const context = vm.createContext({URL,location,document:{querySelectorAll:()=>Array.from({length:nodes},()=>node)}});
 const target = vm.runInContext(source+'\n__bijuxSearchCapabilityTarget',context);
 return {target,context,node};
}
const check = test;
check('absent capability metadata preserves ordinary native attributes',()=>assert.equal(setup(payload(),'',0).target(base+'ordinary/'),undefined));
check('ordinary same partition result omits target',()=>assert.equal(setup().target(base+'ordinary/?h=term#heading'),undefined));
check('owned result query/hash remains unmodified and selects native document navigation',()=>{const s=setup();const url=new URL(base+'public/nordic-atlas/?h=term#heading');assert.equal(s.target(url),'_self');assert.equal(url.href,base+'public/nordic-atlas/?h=term#heading');});
check('directory and explicit index mount normalize to the same partition',()=>{assert.equal(setup().target(base+'public/nordic-atlas/index.html'),'_self');assert.equal(setup(payload('reader/index.html'),'reader/').target(base+'ordinary/'),undefined);});
check('parent-to-ordinary search restores a new document',()=>assert.equal(setup(payload('public/nordic-atlas/index.html',parent),'public/nordic-atlas/').target(base),'_self'));
check('parent same partition fragment retains native instant semantics',()=>assert.equal(setup(payload('public/nordic-atlas/index.html',parent),'public/nordic-atlas/').target(base+'public/nordic-atlas/?h=term#heading'),undefined));
check('parent-to-report is a separate exact capability',()=>assert.equal(setup(payload('public/nordic-atlas/index.html',parent),'public/nordic-atlas/').target(base+'report/regions/nordic/nordic_map.html'),'_self'));
check('foreign origin and peer product keep native eligibility behavior',()=>{const s=setup();assert.equal(s.target('https://example.com/public/nordic-atlas/'),undefined);assert.equal(s.target('https://bijux.io/bijux-core/'),undefined);});
check('initial policy capture survives ordinary instant location and meta replacement',()=>{const s=setup();s.context.location=new URL(base+'public/nordic-atlas/');s.node.content=JSON.stringify(payload('public/nordic-atlas/index.html',parent));assert.equal(s.target(base+'public/nordic-atlas/'),'_self');assert.equal(s.target(base+'ordinary/'),undefined);});
check('metadata with extra keys cannot grant an instant exception',()=>assert.equal(setup({...payload(),trusted:true}).target(base),'_self'));
check('duplicate metadata cannot grant an instant exception',()=>assert.equal(setup(payload(),'',2).target(base),'_self'));
check('wrong origin or document partition fails conservatively',()=>{assert.equal(setup({...payload(),site_url:'https://example.com/'}).target(base),'_self');assert.equal(setup({...payload(),document_partition:parent}).target(base),'_self');});
check('duplicate or escaped partition routes fail conservatively',()=>{assert.equal(setup({...payload(),route_partitions:[...table,table[0]]}).target(base),'_self');assert.equal(setup({...payload(),route_partitions:[['../escape.html',parent]]}).target(base),'_self');});
check('malformed JSON and excessive route metadata cannot grant an exception',()=>{assert.equal(setup('{bad','',1,true).target(base),'_self');assert.equal(setup({...payload(),route_partitions:Array.from({length:2049},(_,i)=>[i+'.html',parent])}).target(base),'_self');});
