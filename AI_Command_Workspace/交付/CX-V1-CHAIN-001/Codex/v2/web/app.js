'use strict';
const $=selector=>document.querySelector(selector);
let current='',fingerprint='',metadata=null,ready=false;
const names={opening:'期初现金',inflow:'实际流入合计',outflow:'实际流出合计',net:'净现金流',closing:'计算期末现金',actual_closing:'独立实际期末余额',difference:'余额差异'};
function row(label,value){
  const box=document.createElement('div');box.className='pair';
  const a=document.createElement('span'),b=document.createElement('b');
  a.textContent=label;b.textContent=value;box.append(a,b);return box;
}
function busy(value){
  $('#run').disabled=$('#query').disabled=value||!ready;
  $('#reconnect').disabled=value;
}
function resetView(message){
  const tr=document.createElement('tr'),td=document.createElement('td');
  td.colSpan=2;td.className='empty';td.textContent='尚未取得本次核对结果';tr.append(td);
  $('#amounts').replaceChildren(tr);
  $('#explanation').textContent='等待本次已核对结果。';$('#explanation').className='empty';
  $('#receipt').replaceChildren(row('本次状态',message));
}
async function fetchJson(url,options={},timeout=12000){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeout);
  try{const response=await fetch(url,{...options,signal:controller.signal});
    return {response,data:await response.json()};
  }finally{clearTimeout(timer);}
}
function paint(data){
  if(data.status!=='committed'){
    const labels={pending:'提交结果尚未确认，请保留原编号回查。',unavailable:'目前无法确认数据库结果，请稍后按原编号回查。',
      not_found:'当前版本下尚未找到该编号的记录。',conflict:'请求与来源版本冲突，请重新检查连接和来源。'};
    $('#receipt').replaceChildren(row('本次状态',labels[data.status]||'尚未取得可核实的提交回执。'));
    $('#status').textContent=labels[data.status]||'本次结果尚未确认。';
    if(data.status==='conflict')ready=false;
    return;
  }
  const receipt=data.receipt,read=data.read;
  if(!data.readback_verified||!receipt||!read||!data.fixture||data.store!=='isolated_mysql'||
      data.metadata?.workflow_fingerprint!==fingerprint||receipt.status!=='committed'||
      receipt.request_id!==current||!['tenant_id','company_id','period','source_revision','run_id'].every(k=>receipt[k]===metadata[k])||
      !/^[0-9a-f]{64}$/.test(receipt.payload_sha256))throw new Error('receipt_context_invalid');
  $('#amounts').replaceChildren();
  for(const [key,value] of Object.entries(read.result.amounts)){
    const tr=document.createElement('tr'),a=document.createElement('td'),b=document.createElement('td');
    if(key==='closing')tr.className='total';a.textContent=names[key]||key;b.textContent=value===null?'尚未提供':value;
    tr.append(a,b);$('#amounts').append(tr);
  }
  $('#explanation').textContent=read.explanation.replace('此结果不代表已入库或已通知。','这段说明只解释计算结果；是否已保存，以右侧数据库回执为准。');
  $('#explanation').className='';
  $('#receipt').replaceChildren(row('数据库状态','已提交，回查一致'),row('记录ID',receipt.record_id),
    row('请求编号',receipt.request_id),row('期间 / 来源版本',receipt.period+' / '+receipt.source_revision),
    row('运行版本',receipt.run_id),row('保存时间',receipt.stored_at),row('内容摘要',receipt.payload_sha256));
  $('#status').textContent='已完成：读取 → 核对 → MySQL提交 → 精确回查一致。';$('#status').className='ok';
}
async function boot(){
  ready=false;fingerprint='';metadata=null;busy(true);
  resetView('连接和来源正在重新确认；历史记录请按原编号回查。');
  $('#sourceLine').textContent='来源版本尚未重新确认';$('#status').className='';
  $('#status').textContent='正在检查真实数据库连接和来源版本…';
  try{
    const health=await fetchJson('/api/health');
    if(!health.response.ok||health.data.status!=='ready')throw new Error('database_unavailable');
    const source=await fetchJson('/api/source');
    if(!source.response.ok||!/^[0-9a-f]{64}$/.test(source.data.workflow_fingerprint||''))throw new Error('source_unavailable');
    metadata=source.data;fingerprint=metadata.workflow_fingerprint;
    const key='cf-v2-request:'+fingerprint;
    try{current=localStorage.getItem(key)||('web-'+crypto.randomUUID());localStorage.setItem(key,current);}
    catch(error){throw new Error('request_storage_unavailable');}
    $('#request').value=current;
    $('#sourceLine').textContent='期间：'+metadata.period+'　·　单位：元　·　来源：'+metadata.source_revision+'　·　'+metadata.calculation_version;
    $('#status').textContent='连接与来源检查通过。相同来源版本重试会沿用同一请求编号。';ready=true;
  }catch(error){
    const messages={database_unavailable:'数据库尚未连通，请恢复授权隧道后再检查连接。',
      source_unavailable:'来源快照未通过检查，请核实文件及批准摘要。',
      request_storage_unavailable:'浏览器无法保存请求编号。请恢复本地存储后再操作，避免重试产生重复编号。'};
    $('#status').textContent=messages[error.message]||'连接检查未完成，请确认本地服务后重试。原请求编号仍保留。';
    fingerprint='';metadata=null;
  }finally{busy(false);}
}
async function act(kind){
  if(!ready||!current||!fingerprint)return;
  busy(true);resetView('正在按本次编号实际核对数据库；提交结果尚未确认。');
  $('#status').className='';$('#status').textContent='正在实际调用MCP服务与数据库，请稍候…';
  try{
    const {data}=await fetchJson('/api/'+kind,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({request_id:current,workflow_fingerprint:fingerprint})},90000);
    paint(data);
  }catch(error){
    resetView('连接或回执核对未完成，提交结果尚未确认。');
    $('#status').textContent='结果尚未确认。保留同一请求编号，稍后点击回查。';
  }finally{busy(false);}
}
$('#run').onclick=()=>act('run');$('#query').onclick=()=>act('query');$('#reconnect').onclick=boot;boot();
