(function(){'use strict';
const C=window.IntakeCore,$=id=>document.getElementById(id);
const uid=()=>crypto.randomUUID();let generation=0,pending=false;
const account=()=>({id:uid(),alias:'',included:true,exclusion_reason:'',opening_raw:'',closing_raw:'',opening_document:'',closing_document:'',opening_location:'',closing_location:''});
const blank=()=>({draft_id:uid(),is_fixture:false,company_name:'',period:'',preparer:'',scope_note:'',accounts:[account()],documents:[]});
let state=blank();
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function notify(text){$('notice').textContent=text;}
function review(){
  const report=C.validate(state);$('readiness').textContent=report.status==='ready_for_review'?'可交业务确认':report.gaps.length+' 项资料待补';$('readiness').classList.toggle('ready',report.status==='ready_for_review');
  $('cutoffs').textContent=report.cutoffs?'期初：'+report.cutoffs.opening+'；期末：'+report.cutoffs.closing:'选定月份后，会显示应提供的余额日期。';
  $('gaps').replaceChildren(...(report.gaps.length?report.gaps.map(g=>node('li',g.message)):[node('li','填写项已齐，仍须业务负责人核对原始凭证。')]));
  $('fixtureBanner').hidden=!state.is_fixture;$('exportDraft').disabled=pending;$('sample').disabled=pending;
}
function textField(label,value,onchange,opts={}){
  const wrap=node('label',label),input=node('input');input.type='text';input.value=value;input.maxLength=opts.max||128;input.placeholder=opts.placeholder||'';input.setAttribute('aria-label',opts.aria||label);if(opts.decimal)input.inputMode='decimal';input.addEventListener('input',()=>{onchange(input.value);review();});wrap.append(input);return wrap;
}
function renderDocuments(){
  $('documentList').replaceChildren(...state.documents.map(d=>{const li=node('li'),name=node('span',d.name),status=node('span',d.available_in_session?'已在本页登记':'请重新添加','proof-state');li.append(name,status);return li;}));
}
function renderAccounts(){
  const dates=C.cutoffs(state.period);$('accounts').replaceChildren(...state.accounts.map((a,index)=>{
    const card=node('div',undefined,'account');card.dataset.included=String(a.included);card.id='account-'+a.id;
    const top=node('div',undefined,'account-top'),alias=textField('账户 '+(index+1)+' 别名',a.alias,v=>a.alias=v,{placeholder:'例如：基本户（尾号1234）',aria:'账户'+(index+1)+'别名'});alias.classList.add('account-title');
    const include=node('label','本次范围'),select=node('select');select.setAttribute('aria-label','账户'+(index+1)+'是否纳入');for(const [value,text]of [['yes','纳入核对'],['no','本次排除']]){const op=node('option',text);op.value=value;op.selected=(value==='yes')===a.included;select.append(op);}select.addEventListener('change',()=>{a.included=select.value==='yes';renderAccounts();review();});include.append(select);top.append(alias,include);card.append(top);
    if(!a.included){const ex=textField('排除原因',a.exclusion_reason,v=>a.exclusion_reason=v,{placeholder:'说明为什么不属于本次范围',max:300,aria:'账户'+(index+1)+'排除原因'});ex.classList.add('exclusion');card.append(ex);return card;}
    const cols=node('div',undefined,'balance-columns');for(const kind of ['opening','closing']){
      const title=kind==='opening'?'期初':'期末',side=node('div',undefined,'balance-side'),h=node('h3',title+'余额');h.append(node('small',dates?(kind==='opening'?dates.opening:dates.closing):'请先选定核对月份'));side.append(h);
      side.append(textField('金额（元）',a[kind+'_raw'],v=>a[kind+'_raw']=v,{placeholder:'缺资料留空；真实零可填0',decimal:true,aria:'账户'+(index+1)+title+'余额'}));
      const proof=node('label',title+'凭证文件'),pick=node('select');pick.setAttribute('aria-label','账户'+(index+1)+title+'凭证');const none=node('option','选择上方添加的凭证');none.value='';pick.append(none);for(const doc of state.documents){const op=node('option',doc.name+(doc.available_in_session?'':'（需重新添加）'));op.value=doc.id;op.selected=a[kind+'_document']===doc.id;pick.append(op);}pick.addEventListener('change',()=>{a[kind+'_document']=pick.value;review();});proof.append(pick);side.append(proof);
      side.append(textField('页码或位置',a[kind+'_location'],v=>a[kind+'_location']=v,{placeholder:'例如：第1页期初余额栏',max:300,aria:'账户'+(index+1)+title+'凭证位置'}));cols.append(side);
    }card.append(cols);return card;
  }));
}
function renderAll(){
  for(const [id,key]of [['companyName','company_name'],['period','period'],['preparer','preparer'],['scopeNote','scope_note']])$(id).value=state[key];renderDocuments();renderAccounts();review();
}
for(const [id,key]of [['companyName','company_name'],['period','period'],['preparer','preparer'],['scopeNote','scope_note']])$(id).addEventListener('input',()=>{state[key]=$(id).value;if(key==='period')renderAccounts();review();});
$('addAccount').addEventListener('click',()=>{if(state.accounts.length>=100){notify('每份草稿最多登记100个账户。');return;}state.accounts.push(account());renderAccounts();review();});
async function registerFiles(files){
  const version=generation;pending=true;review();let added=0;const errors=[];
  try{for(const file of files){
    if(!C.allowedFile(file.name,file.size)){errors.push('文件格式或大小不支持：'+file.name);continue;}
    if(state.documents.length>=100){errors.push('每份草稿最多100个凭证文件');break;}
    const bytes=await file.arrayBuffer(),digest=await crypto.subtle.digest('SHA-256',bytes),hash=Array.from(new Uint8Array(digest),v=>v.toString(16).padStart(2,'0')).join('');
    if(version!==generation)return;
    const existing=state.documents.find(d=>d.name===file.name&&d.size===file.size&&d.sha256===hash);
    if(existing)existing.available_in_session=true;else state.documents.push({id:uid(),name:file.name,size:file.size,sha256:hash,available_in_session:true});added++;
  }if(version===generation){renderDocuments();renderAccounts();notify(errors.length?errors.join('；'):'已在本页登记 '+added+' 个凭证。文件内容未上传。');}}
  catch(e){if(version===generation)notify('文件登记未完成，请检查文件是否可读取；尚未验证的凭证不会计为齐全。');}
  finally{if(version===generation){pending=false;review();}}
}
$('documents').addEventListener('change',async()=>{await registerFiles(Array.from($('documents').files));$('documents').value='';});
$('sample').addEventListener('click',async()=>{
  generation++;const sampleGeneration=generation;state=blank();state.is_fixture=true;state.company_name='合成制造企业（非真实业务）';state.period='2026-08';state.preparer='合成资料提交人';state.scope_note='合成示例：两个人民币账户';state.accounts=[account(),account()];renderAll();
  const files=['A','B'].map((name,i)=>new File([JSON.stringify({synthetic:true,account:name,opening:i?'40000.00':'60000.00',closing:i?'50000.00':'90000.00'})],'合成账户'+name+'余额.json',{type:'application/json'}));
  await registerFiles(files);if(sampleGeneration!==generation)return;state.accounts.forEach((a,i)=>{a.alias='合成账户'+['A','B'][i];a.opening_raw=i?'40000':'60000';a.closing_raw=i?'50000':'90000';a.opening_document=a.closing_document=state.documents[i]?.id||'';a.opening_location='合成期初余额栏';a.closing_location='合成期末余额栏';});renderAll();notify('已载入合成示例。导出文件会明确保留合成标记。');
});
$('fresh').addEventListener('click',()=>{generation++;pending=false;state=blank();renderAll();notify('已新建空白草稿；已下载的文件不会被修改。');});
$('importDraft').addEventListener('change',async()=>{
  const file=$('importDraft').files[0];if(!file)return;const importGeneration=generation;
  try{if(file.size>2000000)throw Error('草稿文件过大');const imported=C.importDraft(await file.text());if(importGeneration!==generation)return;generation++;pending=false;state=imported;renderAll();notify('草稿已打开。凭证文件需重新添加，同名且内容一致后才能重新标为齐全。');}
  catch(e){notify('无法打开草稿：'+e.message);}finally{$('importDraft').value='';}
});
$('exportDraft').addEventListener('click',()=>{
  if(pending)return;const draft=C.buildDraft(state),blob=new Blob([JSON.stringify(draft,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='制造业资料草稿_'+(state.period||'未选期间')+'_'+state.draft_id.slice(0,8)+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify(draft.preparation_status==='ready_for_review'?'已导出待确认草稿，请交业务负责人核对。':'已导出含缺项的草稿，缺少资料已一并列出。');
});
window.IntakeApp={getDraft:()=>C.buildDraft(state),getPending:()=>pending};renderAll();
})();
