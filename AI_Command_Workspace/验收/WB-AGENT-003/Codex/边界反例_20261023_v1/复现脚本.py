from pathlib import Path
import copy,json,hashlib,sys,shutil,re

source=Path(r'D:\AI_Command_Workspace\交付\WB-AGENT-003\WorkBuddy\v1')
audit=Path(r'D:\AI_Command_Workspace\验收\WB-AGENT-003\Codex\边界反例_20261023_v1')
assert not audit.exists();audit.mkdir(parents=True)
frozen=audit/'冻结代码';frozen.mkdir()
hashes={}
for f in (source/'candidate').glob('*.py'):
    data=f.read_bytes();hashes[f.name]=hashlib.sha256(data).hexdigest();(frozen/f.name).write_bytes(data)
sys.path.insert(0,str(frozen))
from runtime_adapter import Binding,Outcome,COMMITTED,PENDING,save_result,canonical_sha256
from adapters import OfflineFixtureBackend,FIXTURE_RESULT,FIXTURE_SNAPSHOT,with_binding
from request_flow import RequestFlow,FlowBlocked
from persistence import MemoryEvidenceStore,retry_after_timeout,build_save_payload

b=Binding('probe-tenant','probe-company','2026-08','probe-rev','probe-run-1')
base=with_binding(copy.deepcopy(FIXTURE_RESULT),b)
results=[]
def record(ident,title,expected,actual,reproduced,files):
    results.append(dict(id=ident,title=title,expected=expected,actual=actual,reproduced=reproduced,files=files))

backend=OfflineFixtureBackend(allow_fixture=True);flow=RequestFlow(backend)
first=flow.run(b,allow_fixture=True)
b2=Binding(b.tenant_id,b.company_id,b.period,b.source_revision,'probe-run-2')
try:
    second=flow.run(b2,allow_fixture=True);obs={'ok':second.ok,'result_run_id':second.result['run_id']}
except FlowBlocked as e:obs={'blocked_stage':e.stage,'reason':e.outcome.reason}
record('AG-P01','同源版本的新run误复用旧缓存','新run重新读结果或安全复用重新绑定，不因旧run卡死',obs,'context mismatch: run_id' in str(obs),['request_flow.py'])

bad=copy.deepcopy(FIXTURE_RESULT);bad['amounts']['net']='40000.01'
backend=OfflineFixtureBackend(result=bad,allow_fixture=True);flow=RequestFlow(backend)
try:flow.run(b,allow_fixture=True)
except FlowBlocked:pass
backend.result=copy.deepcopy(FIXTURE_RESULT)
try:
    corrected=flow.run(b,allow_fixture=True);obs={'ok':corrected.ok}
except FlowBlocked as e:obs={'blocked_stage':e.stage,'reason':e.outcome.reason,'cached_net':flow.cache[(b.tenant_id,b.company_id,b.period)][1]['amounts']['net']}
record('AG-P02','未过守卫的坏响应先进入缓存','坏响应不得缓存，下次可重新取得已修正响应',obs,obs.get('cached_net')=='40000.01',['request_flow.py'])

snap=copy.deepcopy(FIXTURE_SNAPSHOT);snap['snapshot_ref']='new-observed-snapshot'
backend=OfflineFixtureBackend(snapshot=snap,allow_fixture=True)
out=RequestFlow(backend).run(b,allow_fixture=True)
obs={'ok':out.ok,'read_snapshot_ref':snap['snapshot_ref'],'result_snapshot_ref':out.result['source']['snapshot_ref']}
record('AG-P03','结果来源未与本次实际快照绑定','不匹配的source.snapshot_ref必须阻断',obs,out.ok and obs['read_snapshot_ref']!=obs['result_snapshot_ref'],['request_flow.py','runtime_adapter.py'])

store=MemoryEvidenceStore();store.commit(b,base,'logical-1')
changed=copy.deepcopy(base);changed['amounts']['actual_closing']='139000.00';changed['amounts']['difference']='-1000.00'
out=retry_after_timeout(store,b,changed,'logical-1','logical-1')
obs={'status':out.status,'returned_payload_hash':out.payload['payload_sha256'],'submitted_payload_hash':canonical_sha256(changed),'same_content':out.payload['payload_sha256']==canonical_sha256(changed)}
record('AG-P04','超时回查不核载荷就宣称当前请求已提交','同ID异载荷冲突，不可用旧内容回执确认新内容',obs,out.status==COMMITTED and not obs['same_content'],['persistence.py'])

backend=OfflineFixtureBackend(allow_fixture=True);foreign=copy.deepcopy(base);foreign['company_id']='other-company'
out=save_result(backend,b,foreign,'foreign-result')
obs={'status':out.status,'receipt_company':out.payload['company_id'],'submitted_company':foreign['company_id'],'stored_count':len(backend.store.list_scope(b))}
record('AG-P05','保存边界只查success未核结果身份及金额','保存前按可信binding验证完整结果与身份',obs,out.status==COMMITTED and obs['receipt_company']!=foreign['company_id'],['runtime_adapter.py','persistence.py'])

schema={'type':'object','required':['request_id'],'properties':{'request_id':{'type':'string','minLength':1}}}
out=build_save_payload(b,base,'logical-2',schema)
obs={'mapping_status':out.status,'payload':out.payload,'network_or_store_called':False}
record('AG-P06','仅构造保存参数就标committed','映射成功与真正提交成功分离，不产生已提交语义',obs,out.status==COMMITTED,['persistence.py'])

class PendingReadBackend(OfflineFixtureBackend):
    def read_snapshot(self,binding):
        out=super().read_snapshot(binding);out.status=PENDING;return out
    def read_calculated_result(self,binding,snapshot):
        out=super().read_calculated_result(binding,snapshot);out.status=PENDING;return out
out=RequestFlow(PendingReadBackend(allow_fixture=True)).run(b,allow_fixture=True)
obs={'flow_ok':out.ok,'snapshot_outcome':'pending','result_outcome':'pending'}
record('AG-P07','读取处于pending却继续成完整成功','读取状态只有显式成功方可进入下一步，pending阻断',obs,out.ok,['runtime_adapter.py','request_flow.py'])

for name,sha in hashes.items():assert hashlib.sha256((source/'candidate'/name).read_bytes()).hexdigest()==sha
(audit/'代码源哈希.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
(audit/'独立边界反例结果.json').write_text(json.dumps({'scope':'offline synthetic boundary probes, no platform/DB; not full DeepSeek review','results':results,'source_unchanged':True},ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(Path(__file__),audit/'复现脚本.py')
print(json.dumps({'reproduced':sum(v['reproduced'] for v in results),'total':len(results),'results':results},ensure_ascii=True,indent=2))
