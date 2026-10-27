"""Official MCP clients, two transports, isolated real MySQL, independent readback."""
import asyncio,copy,hashlib,json,os,sys,uuid
from contextlib import asynccontextmanager
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from qa_entry import environment
from config import Config
from service import Service,canonical

def unpack(response):
    if response.isError:raise AssertionError(str(response.content))
    return response.structuredContent if response.structuredContent is not None else json.loads(response.content[0].text)

@asynccontextmanager
async def connect(kind,log):
    if kind=='http':
        async with streamable_http_client('http://127.0.0.1:18765/mcp/') as (read,write,_):
            async with ClientSession(read,write) as session:yield session
    else:
        # Exactly the command entered in Qwen, not a different test-only server.
        params=StdioServerParameters(command=sys.executable,args=['-B','-u',str(ROOT/'qa_entry.py'),'stdio'],env=os.environ.copy())
        async with stdio_client(params,errlog=log) as (read,write):
            async with ClientSession(read,write) as session:yield session

async def roundtrip(kind):
    request='v2-'+kind+'-'+uuid.uuid4().hex
    record={'transport':kind,'request_id':request,'fixture':True,'qwen_agent_called':False}
    (ROOT/'evidence'/('请求开始_'+kind+'.json')).write_text(json.dumps(record,indent=2),encoding='utf-8')
    with (ROOT/'evidence'/('工具过程_'+kind+'.txt')).open('w',encoding='utf-8') as log:
        async with connect(kind,log) as session:
            initialized=await session.initialize()
            tools=await session.list_tools()
            assert {x.name for x in tools.tools}=={'read_cashflow_result','save_cashflow_result','query_cashflow_result'}
            read=unpack(await session.call_tool('read_cashflow_result',{}))
            assert read['fixture'] is True and read['platform_native_verified'] is False
            result=read['result'];assert result['amounts']['net']=='40000.00'
            assert result['calculation_version']=='baseline-cashflow-arithmetic.v1'
            saved=unpack(await session.call_tool('save_cashflow_result',{'result':result,'request_id':request}))
            assert saved['status']=='committed',saved
            repeated=unpack(await session.call_tool('save_cashflow_result',{'result':result,'request_id':request}))
            assert repeated['receipt']==saved['receipt']
            args={k:result[k] for k in ('period','source_revision','run_id')};args['request_id']=request
            queried=unpack(await session.call_tool('query_cashflow_result',args))
            assert queried['result']==result and queried['receipt']==saved['receipt']
            conflict=unpack(await session.call_tool('query_cashflow_result',{**args,'source_revision':'different-revision'}))
            assert conflict['status']=='conflict'
            forged=copy.deepcopy(result);forged['amounts'].update(inflow='140000.00',net='50000.00',closing='150000.00',difference='-10000.00')
            rejected=await session.call_tool('save_cashflow_result',{'result':forged,'request_id':request+'-forged'})
            assert rejected.isError
            record.update(receipt=saved['receipt'],tools=[x.name for x in tools.tools],
                server=initialized.serverInfo.model_dump(mode='json'),replay_same_receipt=True,
                forged_amounts_rejected=True,version_conflict_rejected=True)
        async with connect(kind,log) as session:
            await session.initialize()
            reopened=unpack(await session.call_tool('query_cashflow_result',args))
            assert reopened['receipt']==saved['receipt']
            record['new_client_readback']=True
    env=environment();os.environ.update(env)
    config=Config.from_env()
    with Service(config).connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT record_id,payload_sha256,payload FROM mfg_cashflow_runs_v1 WHERE tenant_id=%s AND company_id=%s AND request_id=%s',
                (config.tenant,config.company,request))
            rows=cursor.fetchall();assert len(rows)==1
            row=rows[0];assert row['record_id']==saved['receipt']['record_id']
            assert row['payload_sha256']==hashlib.sha256(canonical(result)).hexdigest()
            assert json.loads(row['payload'])==result
            cursor.execute('SELECT COUNT(*) n FROM mfg_cashflow_runs_v1 WHERE request_id=%s',(request+'-forged',))
            assert cursor.fetchone()['n']==0
    record.update(status='passed',independent_sql_readback=True,production_deployed=False)
    (ROOT/'evidence'/('真实数据库闭环_'+kind+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2))

async def main():
    for kind in ('stdio','http'):await roundtrip(kind)

if __name__=='__main__':asyncio.run(main())
