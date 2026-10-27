"""Existing QA recovery verification: SELECT only, plus readonly official MCP calls."""
from pathlib import Path
import asyncio,json,hashlib,os,sys
from datetime import timedelta

HERE=Path(__file__).resolve().parent
TARGET=Path('D:/AI_Command_Workspace/交付/CX-WORKBENCH-INTEGRATE-001/Codex/v1')
sys.path.insert(0,str(TARGET));sys.path.insert(0,str(TARGET/'src'))
import qa_entry
from config import Config
from service import Service,canonical
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

REQUEST='qwen-v2-native-20261024-01'
RECORD='d7f97377-2fd2-45ff-8046-49297bf15c61'
EXPECTED={'get_workbench_status','list_manufacturing_sources','inspect_manufacturing_source','get_manufacturing_readiness','read_cashflow_result','save_cashflow_result','query_cashflow_result'}
def dump(name,data):
    with (HERE/'evidence'/name).open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
def unwrap(r):
    if r.isError:raise AssertionError('unexpected_tool_error')
    return r.structuredContent if r.structuredContent is not None else json.loads(r.content[0].text)
def verify_sql():
    os.environ.update(qa_entry.environment())
    service=Service(Config.from_env());snapshot=service.read()['result']
    with service.connect() as conn:
        with conn.cursor() as cur:
            cur.execute('START TRANSACTION READ ONLY')
            cur.execute('SELECT VERSION() version,DATABASE() db');info=cur.fetchone()
            cur.execute('SELECT COUNT(*) n FROM mfg_cashflow_runs_v1');total_before=cur.fetchone()['n']
            cur.execute('SELECT * FROM mfg_cashflow_runs_v1 WHERE tenant_id=%s AND company_id=%s AND request_id=%s',('fixture-tenant','fixture-manufacturing',REQUEST))
            rows=cur.fetchall();assert len(rows)==1
            checked=service._checked_row(rows[0]);assert checked['receipt']['record_id']==RECORD
            assert checked['result']==snapshot
            assert checked['receipt']['payload_sha256']==hashlib.sha256(canonical(snapshot)).hexdigest()
            cur.execute('SELECT COUNT(*) n FROM mfg_cashflow_runs_v1');assert total_before==cur.fetchone()['n']
        conn.rollback()
    report={'status':'passed','transaction':'START TRANSACTION READ ONLY','database':info['db'],'mysql_version':info['version'],'request_id':REQUEST,'record_id':RECORD,'matched_request_rows':1,'qa_total_rows_before':total_before,'qa_total_rows_after':total_before,'payload_sha256':checked['receipt']['payload_sha256'],'approved_fixture_matches':True,'writes_performed':False,'production_database_accessed':False}
    dump('独立SQL只读核验.json',report);return snapshot,total_before
async def verify_mcp(snapshot,total_before):
    params=StdioServerParameters(command=sys.executable,args=['-B','-u',str(TARGET/'qa_entry.py'),'stdio'],env=qa_entry.environment())
    calls=[]
    async def call(session,name,args):
        data=unwrap(await session.call_tool(name,args));calls.append({'tool':name,'arguments':args,'result':data});return data
    with (HERE/'evidence/MCP_stderr.txt').open('x',encoding='utf-8') as log:
        async with stdio_client(params,errlog=log) as (read,write):
            async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=30)) as session:
                await session.initialize();listing=await session.list_tools();names={t.name for t in listing.tools};assert names==EXPECTED
                status=await call(session,'get_workbench_status',{});assert status['components']['database']=='connected'
                catalog=await call(session,'list_manufacturing_sources',{});assert len(catalog['sources'])==1
                inspected=await call(session,'inspect_manufacturing_source',{'source_id':'manufacturing_sample_v1'});assert inspected['blocks']['现金流水']['cells']['D8']['raw_xml_value']=='1631300'
                ready=await call(session,'get_manufacturing_readiness',{});assert ready['status']=='blocked' and ready['can_save_source_result'] is False
                readback=await call(session,'read_cashflow_result',{});assert readback['result']==snapshot and readback['fixture']
                result=await call(session,'query_cashflow_result',{'request_id':REQUEST,'period':snapshot['period'],'source_revision':snapshot['source_revision'],'run_id':snapshot['run_id']})
                assert result['receipt']['record_id']==RECORD and result['result']==snapshot
                invalid=await session.call_tool('inspect_manufacturing_source',{'source_id':'../../not-registered'})
                assert invalid.isError
    service=Service(Config.from_env())
    with service.connect() as conn:
        with conn.cursor() as cur:
            cur.execute('START TRANSACTION READ ONLY');cur.execute('SELECT COUNT(*) n FROM mfg_cashflow_runs_v1');after=cur.fetchone()['n'];assert after==total_before
        conn.rollback()
    report={'status':'passed','transport':'official_MCP_SDK_stdio','seven_tools_listed':sorted(names),'readonly_successful_calls':len(calls),'negative_source_rejected':True,'save_tool_invoked':False,'qa_row_count_unchanged':after==total_before,'qwen_native_call':False,'native_sheet_recalculation_verified':False,'calls':calls}
    dump('七工具契约与六次只读调用.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='calls'},ensure_ascii=False))
if __name__=='__main__':
    snapshot,total=verify_sql()
    asyncio.run(verify_mcp(snapshot,total))
