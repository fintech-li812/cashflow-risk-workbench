/* Contract tests for user sequences. VM DOM/backend substitutes are NOT a browser or DB result. */
const {readFileSync}=require('node:fs');
const {join}=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const code=readFileSync(join(__dirname,'../web/app.js'),'utf8');
class Element{
  constructor(){this.children=[];this.own='';this.value='';this.disabled=false;}
  set textContent(value){this.own=String(value);this.children=[];}
  get textContent(){return this.own+this.children.map(x=>x.textContent).join(' ');}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.own='';this.children=items;}
}
function source(revision='one'){
  return {tenant_id:'fixture-tenant',company_id:'fixture-manufacturing',period:'2026-08',
    source_revision:revision,run_id:'run-'+revision,calculation_version:'baseline-v1',
    workflow_fingerprint:(revision==='one'?'a':'b').repeat(64)};
}
const settle=()=>new Promise(setImmediate);
async function page(){
  const elements=Object.fromEntries(['run','query','reconnect','amounts','explanation','receipt','status','sourceLine','request'].map(k=>['#'+k,new Element()]));
  const store=new Map(),state={source:source(),health:true,action:'commit',calls:[],counter:0,storageFailure:false};
  const context=vm.createContext({document:{querySelector:s=>elements[s],createElement:()=>new Element()},
    localStorage:{getItem:k=>{if(state.storageFailure)throw Error('storage denied');return store.get(k)||null;},
      setItem:(k,v)=>{if(state.storageFailure)throw Error('storage denied');store.set(k,v);}},
    crypto:{randomUUID:()=>String(++state.counter)},AbortController,setTimeout,clearTimeout,
    fetch:async(url,options)=>{
      if(url==='/api/health')return {ok:state.health,json:async()=>({status:state.health?'ready':'unavailable'})};
      if(url==='/api/source')return {ok:true,json:async()=>({...state.source})};
      const body=JSON.parse(options.body);state.calls.push({url,body});
      if(state.action==='throw')throw Error('transport lost');
      if(state.action!=='commit')return {ok:false,json:async()=>({status:state.action})};
      const receipt={...state.source,request_id:body.request_id,record_id:'fixture-record',
        payload_sha256:'c'.repeat(64),status:'committed',stored_at:'2026-10-24T00:00:00Z'};
      if(state.forge==='request')receipt.request_id='someone-else';
      if(state.forge==='revision')receipt.source_revision='other-revision';
      return {ok:true,json:async()=>({status:'committed',fixture:true,store:'isolated_mysql',
        readback_verified:true,metadata:{...state.source},receipt,
        read:{result:{amounts:{net:'40000.00'}},explanation:'已核对。此结果不代表已入库或已通知。'}})};
    }});
  vm.runInContext(code,context);await settle();
  return {elements,store,state,click:async name=>{await elements['#'+name].onclick();await settle();},
    text:name=>elements['#'+name].textContent,id:()=>elements['#request'].value};
}
const cases=[];const test=(name,run)=>cases.push({name,run});
test('initial connection permits actions with source-scoped request',async()=>{
  const p=await page();assert.equal(p.elements['#run'].disabled,false);assert.equal(p.id(),'web-1');
});
test('committed receipt displays amounts and exact request',async()=>{
  const p=await page();await p.click('run');assert.match(p.text('receipt'),/已提交，回查一致/);assert.match(p.text('amounts'),/40000.00/);
  assert.equal(p.state.calls[0].body.request_id,p.id());
});
test('real check failure clears old receipt and disables actions',async()=>{
  const p=await page();await p.click('run');const id=p.id();p.state.health=false;await p.click('reconnect');
  assert.doesNotMatch(p.text('receipt'),/已提交|fixture-record/);assert.doesNotMatch(p.text('amounts'),/40000.00/);
  assert.equal(p.id(),id);assert.equal(p.elements['#run'].disabled,true);assert.equal(p.elements['#reconnect'].disabled,false);
});
test('recovery preserves original request and requires explicit query',async()=>{
  const p=await page();await p.click('run');const id=p.id();p.state.health=false;await p.click('reconnect');
  p.state.health=true;await p.click('reconnect');assert.equal(p.id(),id);assert.doesNotMatch(p.text('receipt'),/已提交/);
  await p.click('query');assert.equal(p.state.calls.at(-1).body.request_id,id);assert.match(p.text('receipt'),/已提交/);
});
test('new source gets distinct request and never displays previous result',async()=>{
  const p=await page();await p.click('run');const id=p.id();p.state.source=source('two');await p.click('reconnect');
  assert.notEqual(p.id(),id);assert.doesNotMatch(p.text('receipt'),/已提交/);assert.doesNotMatch(p.text('amounts'),/40000.00/);
  assert.equal(p.store.size,2);
});
test('returning to original source restores original request',async()=>{
  const p=await page();const id=p.id();p.state.source=source('two');await p.click('reconnect');
  p.state.source=source();await p.click('reconnect');assert.equal(p.id(),id);
});
test('pending preserves request without showing committed or amounts',async()=>{
  const p=await page();await p.click('run');const id=p.id();p.state.action='pending';await p.click('run');
  assert.equal(p.id(),id);assert.doesNotMatch(p.text('receipt'),/已提交/);assert.doesNotMatch(p.text('amounts'),/40000.00/);
  assert.match(p.text('status'),/尚未确认/);assert.equal(p.elements['#query'].disabled,false);
});
test('query outage never becomes not_found',async()=>{
  const p=await page();p.state.action='unavailable';await p.click('query');assert.match(p.text('status'),/无法确认/);
  assert.doesNotMatch(p.text('status'),/尚未找到/);
});
test('exact not_found is clearly distinct from outage',async()=>{
  const p=await page();p.state.action='not_found';await p.click('query');assert.match(p.text('status'),/尚未找到/);
});
test('source conflict blocks more writes until recheck',async()=>{
  const p=await page();p.state.action='conflict';await p.click('run');assert.equal(p.elements['#run'].disabled,true);
  assert.equal(p.elements['#reconnect'].disabled,false);
});
for(const forge of ['request','revision'])test('mismatched '+forge+' receipt is never painted successful',async()=>{
  const p=await page();p.state.forge=forge;await p.click('run');assert.doesNotMatch(p.text('receipt'),/已提交/);
  assert.doesNotMatch(p.text('amounts'),/40000.00/);assert.match(p.text('status'),/尚未确认/);
});
test('lost response preserves id and removes stale receipt',async()=>{
  const p=await page();await p.click('run');const id=p.id();p.state.action='throw';await p.click('run');
  assert.equal(p.id(),id);assert.doesNotMatch(p.text('receipt'),/已提交/);assert.match(p.text('status'),/保留同一请求编号/);
});
test('storage denied blocks actions instead of issuing unpersisted replacement',async()=>{
  const p=await page();p.state.storageFailure=true;await p.click('reconnect');assert.equal(p.elements['#run'].disabled,true);
  assert.match(p.text('status'),/无法保存请求编号/);
});
test('invalid source fingerprint cannot enable actions',async()=>{
  const p=await page();p.state.source.workflow_fingerprint='bad';await p.click('reconnect');
  assert.equal(p.elements['#run'].disabled,true);assert.match(p.text('status'),/来源快照未通过/);
});
(async()=>{for(const item of cases){await item.run();console.log('PASS '+item.name);}console.log(JSON.stringify({passed:cases.length,scope:'VM DOM/backend substitutes; not live browser, Qwen or MySQL'}));})().catch(error=>{console.error(error);process.exitCode=1;});
