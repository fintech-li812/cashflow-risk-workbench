(function(root){'use strict';
function normalizeAmount(raw){
  if(typeof raw!=='string')return {value:null,valid:false};
  if(raw==='')return {value:null,valid:true};
  if(!/^-?(?:0|[1-9][0-9]{0,17})(?:\.[0-9]{1,2})?$/.test(raw))return {value:null,valid:false};
  const parts=raw.split('.');return {value:parts[0]+'.'+(parts[1]||'').padEnd(2,'0'),valid:true};
}
function cutoffs(period){
  if(typeof period!=='string'||!/^\d{4}-(?:0[1-9]|1[0-2])$/.test(period))return null;
  const year=Number(period.slice(0,4)),month=Number(period.slice(5));if(year<1900||year>9999)return null;
  function fmt(d){return d.getUTCFullYear()+'-'+String(d.getUTCMonth()+1).padStart(2,'0')+'-'+String(d.getUTCDate()).padStart(2,'0');}
  return {opening:fmt(new Date(Date.UTC(year,month-1,0))),closing:fmt(new Date(Date.UTC(year,month,0)))};
}
function validate(state){
  const gaps=[],add=(field,message)=>gaps.push({field,message});
  if(!state.company_name.trim())add('companyName','填写企业名称');
  const dates=cutoffs(state.period);if(!dates)add('period','选择核对月份');
  if(!state.preparer.trim())add('preparer','填写资料提交人');
  if(!state.scope_note.trim())add('scopeNote','说明本次纳入的主体与账户范围');
  const accounts=state.accounts.filter(a=>a.included);if(!accounts.length)add('accounts','至少纳入一个账户');
  const aliases=new Set();
  for(const a of state.accounts){
    const title=a.alias.trim()||'未命名账户';
    if(!a.alias.trim())add(a.id,'填写账户别名');
    else if(aliases.has(a.alias.trim()))add(a.id,'账户别名重复：'+title);
    aliases.add(a.alias.trim());
    if(/\d{8,}/.test(a.alias))add(a.id,'账户别名不要填写完整账号');
    if(!a.included){if(!a.exclusion_reason.trim())add(a.id,title+'：说明排除原因');continue;}
    for(const kind of ['opening','closing']){
      const name=kind==='opening'?'期初':'期末',value=normalizeAmount(a[kind+'_raw']);
      if(!value.valid)add(a.id,title+'：'+name+'金额填写元，最多两位小数');
      else if(value.value===null)add(a.id,title+'：缺少'+name+'余额');
      const doc=state.documents.find(d=>d.id===a[kind+'_document']);
      if(!doc||!doc.available_in_session)add(a.id,title+'：添加并关联'+name+'凭证文件');
      if(!a[kind+'_location'].trim())add(a.id,title+'：注明'+name+'凭证页码或位置');
    }
  }
  return {status:gaps.length?'incomplete':'ready_for_review',gaps,cutoffs:dates};
}
function buildDraft(state){
  const check=validate(state);
  return {schema_version:'mfg-business-intake-draft.v1',draft_id:state.draft_id,
    origin:state.is_fixture?'offline_fixture':'user_entered_draft',industry:'manufacturing',unit:'CNY',
    company_name:state.company_name,period:state.period,preparer:state.preparer,scope_note:state.scope_note,
    tenant_id:null,company_id:null,internal_identity_binding_required:true,
    scope_confirmed:false,approval:{status:'not_submitted',approver:null},source_authenticity_verified:false,
    native_sheet_verified:false,can_save_source_result:false,preparation_status:check.status,cutoffs:check.cutoffs,
    accounts:state.accounts.map(a=>({draft_account_id:a.id,account_id:null,alias:a.alias,included:a.included,
      exclusion_reason:a.exclusion_reason,opening:{raw:a.opening_raw,amount:normalizeAmount(a.opening_raw).value,document_id:a.opening_document||null,location:a.opening_location},
      closing:{raw:a.closing_raw,amount:normalizeAmount(a.closing_raw).value,document_id:a.closing_document||null,location:a.closing_location}})),
    documents:state.documents.map(d=>({id:d.id,name:d.name,size:d.size,sha256:d.sha256,available_in_session:!!d.available_in_session})),
    missing_items:check.gaps};
}
function strictJSON(text){
  if(typeof text!=='string'||text.length>2000000)throw Error('草稿文件过大');let i=0;
  const ws=()=>{while(/\s/.test(text[i]||'')&&i<text.length)i++;};
  function str(){const start=i++;while(i<text.length){if(text[i]==='\\'){i+=2;continue;}if(text[i++]==='"')return JSON.parse(text.slice(start,i));}throw Error('JSON字符串未结束');}
  function value(depth){if(depth>64)throw Error('草稿层级过深');ws();const ch=text[i];
    if(ch==='"')return str();
    if(ch==='{'){i++;ws();const out=Object.create(null);if(text[i]==='}'){i++;return out;}for(;;){ws();if(text[i]!=='"')throw Error('JSON对象字段无效');const key=str();ws();if(text[i++]!==':')throw Error('JSON缺少分隔符');if(Object.prototype.hasOwnProperty.call(out,key))throw Error('JSON字段重复');out[key]=value(depth+1);ws();const end=text[i++];if(end==='}')return out;if(end!==',')throw Error('JSON对象分隔无效');}}
    if(ch==='['){i++;ws();const out=[];if(text[i]===']'){i++;return out;}for(;;){out.push(value(depth+1));ws();const end=text[i++];if(end===']')return out;if(end!==',')throw Error('JSON数组分隔无效');}}
    for(const [token,result] of [['true',true],['false',false],['null',null]])if(text.slice(i,i+token.length)===token){i+=token.length;return result;}
    const match=text.slice(i).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);if(match){i+=match[0].length;const n=Number(match[0]);if(!Number.isFinite(n))throw Error('非有限数字');return n;}
    throw Error('JSON内容无效');}
  const obj=value(0);ws();if(i!==text.length)throw Error('JSON尾部有多余内容');return obj;
}
function importDraft(text){
  const d=strictJSON(text);if(!d||d.schema_version!=='mfg-business-intake-draft.v1')throw Error('不是本页导出的资料草稿');
  if(!['offline_fixture','user_entered_draft'].includes(d.origin)||d.scope_confirmed!==false||d.approval?.status!=='not_submitted'||d.can_save_source_result!==false||d.source_authenticity_verified!==false)throw Error('不能导入带批准或保存声明的草稿');
  if(d.tenant_id!==null||d.company_id!==null||d.native_sheet_verified!==false||d.approval.approver!==null||d.internal_identity_binding_required!==true)throw Error('草稿不能提供已认证身份或平台验证声明');
  for(const key of ['draft_id','company_name','period','preparer','scope_note'])if(typeof d[key]!=='string'||d[key].length>1000)throw Error('草稿字段不完整');
  if(!Array.isArray(d.accounts)||d.accounts.length>100||!Array.isArray(d.documents)||d.documents.length>100)throw Error('草稿账户或文件数量不符');
  const ids=new Set(),documents=[];
  for(const f of d.documents){if(!f||typeof f.id!=='string'||ids.has(f.id)||typeof f.name!=='string'||f.name.length>255||!Number.isSafeInteger(f.size)||f.size<0||typeof f.sha256!=='string'||!/^[0-9a-f]{64}$/.test(f.sha256))throw Error('草稿凭证信息无效');ids.add(f.id);documents.push({id:f.id,name:f.name,size:f.size,sha256:f.sha256,available_in_session:false});}
  const accountIds=new Set(),accounts=d.accounts.map(a=>{
    if(!a||typeof a.draft_account_id!=='string'||accountIds.has(a.draft_account_id)||typeof a.alias!=='string'||a.alias.length>128||typeof a.included!=='boolean'||typeof a.exclusion_reason!=='string'||!a.opening||!a.closing)throw Error('草稿账户信息无效');accountIds.add(a.draft_account_id);
    const row={id:a.draft_account_id,alias:a.alias,included:a.included,exclusion_reason:a.exclusion_reason};
    for(const kind of ['opening','closing']){const v=a[kind];if(typeof v.raw!=='string'||v.raw.length>100||typeof v.location!=='string'||v.location.length>300||!(v.document_id===null||typeof v.document_id==='string'))throw Error('草稿余额信息无效');row[kind+'_raw']=v.raw;row[kind+'_document']=v.document_id||'';row[kind+'_location']=v.location;}
    return row;});
  return {draft_id:d.draft_id,is_fixture:d.origin==='offline_fixture',company_name:d.company_name,period:d.period,preparer:d.preparer,scope_note:d.scope_note,accounts,documents};
}
function allowedFile(name,size){return typeof name==='string'&&/\.(pdf|xlsx|csv|json|png|jpe?g|docx)$/i.test(name)&&Number.isSafeInteger(size)&&size>=0&&size<=20*1024*1024;}
const api={normalizeAmount,cutoffs,validate,buildDraft,strictJSON,importDraft,allowedFile};if(typeof module==='object'&&module.exports)module.exports=api;else root.IntakeCore=api;
})(typeof window==='undefined'?globalThis:window);
