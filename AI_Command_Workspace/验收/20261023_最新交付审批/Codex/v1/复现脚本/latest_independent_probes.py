from pathlib import Path
import json,runpy,io,contextlib,subprocess,importlib.util,hashlib,re,zipfile,xml.etree.ElementTree as ET
from decimal import Decimal as D
root=Path(r'D:\AI_Command_Workspace\验收\20261023_最新交付审批\Codex\v1');frozen=root/'冻结候选'
py=r'C:\Users\33847\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
results={}
# Financial rerun and independent counterexamples: only frozen copy is executed/written.
fin=frozen/'WB-FIN-001-v2';ns=runpy.run_path(str(fin/'verify_financial_formulas.py'))
b=io.StringIO()
with contextlib.redirect_stdout(b):rc=ns['main']()
(root/'FIN_v2_实际复跑.txt').write_text(b.getvalue(),encoding='utf-8')
p=[]
def probe(name,fn):
 try:v=fn()
 except Exception as e:v=type(e).__name__+': '+str(e)
 p.append({'id':name,'actual':str(v)})
probe('FIN-R01_conversion',lambda:ns['f24_unit']('1.234567'))
probe('FIN-R02_invalid',lambda:ns['f01_monthly_outflow'](['90','bad','110']))
probe('FIN-R02_nonfinite',lambda:[str(ns['d'](x)) for x in [D('NaN'),D('Infinity'),'+Infinity']])
probe('FIN-R04_red_rounding',lambda:ns['f09_static_lamp'](ns['f08_ratio']('149.999','100')[0],'2.5','1.5'))
probe('FIN-R04_yellow_rounding',lambda:ns['f09_static_lamp'](ns['f08_ratio']('249.999','100')[0],'2.5','1.5'))
probe('FIN-R05_window',lambda:ns['f02_business_scale'](['100','100']))
g=ns['main'].__globals__;orig=g['CASES'];c=orig[0].copy();c.update(id='AUDIT_FAIL',expected='EXPECTED',compute=lambda:'WRONG',expect_status='PASS');g['CASES']=[c];b=io.StringIO()
with contextlib.redirect_stdout(b):frc=ns['main']()
(root/'FIN_v2_注入失败退出码.txt').write_text(b.getvalue(),encoding='utf-8');p.append({'id':'FIN-R03_failure_exit','actual':{'exit':frc,'FAIL_1':'FAIL 1' in b.getvalue()}})
c.update(id='AUDIT_BLOCKED',expected='待确认',compute=lambda:1/0,expect_status='BLOCKED');b=io.StringIO()
with contextlib.redirect_stdout(b):brc=ns['main']()
(root/'FIN_v2_异常被阻塞掩盖.txt').write_text(b.getvalue(),encoding='utf-8');p.append({'id':'FIN-R03_exception_blocked','actual':{'exit':brc,'error':'ZeroDivisionError' in b.getvalue(),'blocked':'[BLOCKED]' in b.getvalue()}});g['CASES']=orig
results['FIN']={'rerun_exit':rc,'probes':p}
# Engineering candidate: schema validator is a trusted bundled dependency, candidate stays frozen.
eng=frozen/'WB-ENG-001-v2';doc=json.loads((eng/'candidate/docs/千问办公_MySQL_MCP工具定义_v1.1.json').read_text(encoding='utf-8-sig'));tools={t['name']:t for t in doc['tools']}
if importlib.util.find_spec('jsonschema'):
 import jsonschema
 schema=tools['log_feedback']['inputSchema'];validator=jsonschema.Draft202012Validator(schema)
 required=schema.get('required',[])
 print('FEEDBACK_REQUIRED='+json.dumps(required));print('FEEDBACK_PROPERTIES='+json.dumps(schema,ensure_ascii=True)[:6500])
 # Reuse only independent concrete scalar fixture, fill actual required fields from schema.
 values={'tenant_id':'audit-tenant','request_id':'audit-null-final','source_ref':'synthetic-test','occurred_at':'2026-10-23T00:00:00Z','actor_id':'audit-only','forecast_id':'forecast-1','metric_code':'cashflow','predicted_value':'1.00','actual_value':None,'accuracy_label':'accurate','evaluation_version':'audit.v1','actual_source_ref':'synthetic-actual','forecast_start_at':'2026-10-01T00:00:00Z','forecast_end_at':'2026-10-20T00:00:00Z'}
 fixture={k:values[k] for k in required if k in values};fixture.update(predicted_value='1.00',actual_value=None,accuracy_label='accurate')
 errors=list(validator.iter_errors(fixture))
 results['ENG']={'accurate_null_fixture':fixture,'accurate_null_accepted':len(errors)==0,'validation_errors':[e.message for e in errors]}
 r=subprocess.run([py,str(eng/'tools/validate_contract.py')],cwd=eng,capture_output=True,timeout=30)
 (root/'ENG_v2_实际复跑.txt').write_text((r.stdout+r.stderr).decode('utf-8',errors='replace'),encoding='utf-8');results['ENG']['rerun_exit']=r.returncode;results['ENG']['rerun_tail']=(r.stdout+r.stderr).decode('utf-8',errors='replace')[-700:]
else:results['ENG']={'schema_validation':'BLOCKED: bundled jsonschema missing'}
# Qwen: independently compare raw XML values, not parsed display dates.
q=json.loads((frozen/'QWC-002/只读取数证据.json').read_text(encoding='utf-8'));src=Path(q['meta']['源文件']);sha=hashlib.sha256(src.read_bytes()).hexdigest();n={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(src) as z:
 sheets={}
 for title,part in [('企业基本信息','xl/worksheets/sheet1.xml'),('现金流水','xl/worksheets/sheet2.xml')]:
  tree=ET.fromstring(z.read(part));cells={}
  for cell in tree.findall('.//m:sheetData/m:row/m:c',n):
   addr=cell.attrib['r'];typ=cell.attrib.get('t','n');v=cell.find('m:v',n);f=cell.find('m:f',n)
   txt=''.join(t.text or '' for t in cell.findall('.//m:is//m:t',n)) if typ=='inlineStr' else (v.text if v is not None else None)
   cells[addr]={'value':txt,'has_formula':f is not None,'raw':v.text if v is not None else None,'type':typ}
  sheets[title]=cells
 comparisons=[]
 for row,vals in q['企业基本信息_A1C10']['字段行'].items():
  for col,val in zip('ABC',vals):
   addr=col+row;actual=sheets['企业基本信息'].get(addr,{}).get('value');comparisons.append({'cell':'企业基本信息!'+addr,'ok':actual==val,'actual':actual,'reported':val})
 for entry in q['现金流水_A1I15']['F_G_公式或固定值']:
  actual=sheets['现金流水'][entry['ref']];comparisons.append({'cell':'现金流水!'+entry['ref'],'ok':actual['value']==entry['value'] and actual['has_formula']==entry['has_formula']})
 for entry in q['现金流水_A1I15']['行12_行15_逐格对比']:
  col=entry['列'];a=sheets['现金流水'].get(col+'12',{}).get('value');b=sheets['现金流水'].get(col+'15',{}).get('value')
  comparisons.append({'cell':'现金流水!'+col+'12/'+col+'15','ok':a==entry['行12值'] and b==entry['行15值'] and (a==b)==entry['值相同']})
 d8=sheets['现金流水']['D8']['value'];check_d8=d8==q['现金流水_A1I15']['D8']['value']
 expected_yi=D(d8)*D(10000)/D(100000000)
results['QWC']={'source_hash_match':sha==q['meta']['sha256_before']==q['meta']['sha256_after'],'reported_source_changed':q['meta']['原件是否变化'],'D8_match':check_d8,'D8_declared_wanyuan_converts_to_yiyuan':str(expected_yi),'reported_text':q['现金流水_A1I15']['D8']['单位疑点']['疑点描述'],'checked_cell_entries':len(comparisons),'mismatches':[x for x in comparisons if not x['ok']],'raw_observations':comparisons,'evidence_has_complete_cashflow_rows':False}
(root/'独立复核结果.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('AUDIT_RESULTS='+json.dumps({k:({a:b for a,b in v.items() if a not in ['raw_observations','accurate_null_fixture']} ) for k,v in results.items()},ensure_ascii=True,default=str))
