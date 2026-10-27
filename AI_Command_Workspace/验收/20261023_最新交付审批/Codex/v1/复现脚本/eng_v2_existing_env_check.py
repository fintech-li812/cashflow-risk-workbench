from pathlib import Path
import json,io,contextlib,runpy,sys
import jsonschema
root=Path(r'D:\AI_Command_Workspace\验收\20261023_最新交付审批\Codex\v1');eng=root/'冻结候选/WB-ENG-001-v2'
d=json.loads((eng/'candidate/docs/千问办公_MySQL_MCP工具定义_v1.1.json').read_text(encoding='utf-8-sig'));schema=next(x['inputSchema'] for x in d['tools'] if x['name']=='log_feedback')
base={'request_id':'audit-r','source_ref':'synthetic-test','occurred_at':'2026-10-23T00:00:00Z','metric_code':'cashflow','actual_source_ref':'synthetic-actual','evaluation_version':'audit.v1','currency':'CNY','accuracy_label':'accurate','forecast_start_at':'2026-10-01T00:00:00Z','forecast_end_at':'2026-10-20T00:00:00Z','forecast_id':'f1'}
v=jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker());checks=[]
for label,pred,act in [('accurate','1.00','2.00'),('accurate','1.00',None),('inaccurate',None,None),('pending',None,None)]:
 q=dict(base,accuracy_label=label,predicted_value=pred,actual_value=act);es=list(v.iter_errors(q));checks.append({'label':label,'predicted_value':pred,'actual_value':act,'accepted':not es,'errors':[e.message for e in es]})
ns=runpy.run_path(str(eng/'tools/validate_contract.py'));buf=io.StringIO()
with contextlib.redirect_stdout(buf):
 try:ns['main']()
 except SystemExit as ex:rc=ex.code
(root/'ENG_v2_实际复跑.txt').write_text(buf.getvalue(),encoding='utf-8');r=json.loads((root/'独立复核结果.json').read_text(encoding='utf-8'));r['ENG']={'runtime':sys.version,'dependency':'existing author CPython venv jsonschema; no dependency installation','rerun_exit':rc,'rerun_tail':buf.getvalue()[-450:],'null_probes':checks,'base_fixture':base};(root/'独立复核结果.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(r['ENG'],ensure_ascii=True,indent=2))
