"""Official SDK client -> real stdio MCP server -> isolated cloud MySQL."""
import asyncio,hashlib,json,os,sys,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from config import Config
from service import Service,canonical

def environment():
    runtime=json.loads((ROOT/'evidence'/'qa_runtime.json').read_text(encoding='utf-8'))
    fixture=Path(os.environ.get('CF_QA_RESULT_FILE',str(ROOT/'fixtures'/'approved_result.json'))).resolve()
    if fixture.parent!=(ROOT/'fixtures').resolve():raise ValueError('QA fixture must be in package fixtures directory')
    env=os.environ.copy()
    env.update(CF_TENANT_ID='fixture-tenant',CF_COMPANY_ID='fixture-manufacturing',
      CF_RESULT_FILE=str(fixture),CF_RESULT_SHA256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
      CF_DB_NAME=runtime['database'],CF_DB_HOST='127.0.0.1',CF_DB_PORT=str(runtime['port']),
      CF_DB_USER='root',CF_QA_MODE='1',CF_ALLOW_FIXTURE='1',PYTHONUTF8='1')
    env.pop('CF_DB_PASSWORD',None)
    return env

def unpack(response):
    if response.isError:raise AssertionError('MCP tool returned error: '+str(response.content))
    if response.structuredContent is not None:return response.structuredContent
    return json.loads(response.content[0].text)

async def main():
    env=environment();request='mcp-e2e-'+uuid.uuid4().hex
    record={'scope':'synthetic fixture; isolated real MySQL; not Qwen native',
            'request_id':request,'calls':[],'protocol':'official mcp SDK 1.30.0 stdio'}
    params=StdioServerParameters(command=sys.executable,args=['-B',str(ROOT/'src'/'app.py')],env=env)
    label=os.environ.get('CF_QA_RUN_LABEL','')
    if label not in ('','_含基础计算','_含基础计算_复测'):raise ValueError('invalid test label')
    (ROOT/'evidence'/('MCP请求开始'+label+'.json')).write_text(json.dumps({'request_id':request,'fixture_file':env['CF_RESULT_FILE']},ensure_ascii=False,indent=2),encoding='utf-8')
    with (ROOT/'evidence'/('MCP服务日志'+label+'.txt')).open('w',encoding='utf-8') as log:
        async with stdio_client(params,errlog=log) as (read,write):
            async with ClientSession(read,write) as session:
                initialized=await session.initialize()
                listing=await session.list_tools()
                record['server']=initialized.serverInfo.model_dump(mode='json')
                record['tools']=[t.model_dump(mode='json') for t in listing.tools]
                assert set(t.name for t in listing.tools)=={'read_cashflow_result','save_cashflow_result','query_cashflow_result'}
                read_result=unpack(await session.call_tool('read_cashflow_result',{}))
                assert read_result['fixture'] and not read_result['platform_native_verified']
                result=read_result['result']
                assert result['amounts']=={'opening':'100000.00','inflow':'130000.00','outflow':'90000.00',
                    'net':'40000.00','closing':'140000.00','actual_closing':'140000.00','difference':'0.00'}
                record['calls'].append({'tool':'read_cashflow_result','status':read_result['status']})
                save=unpack(await session.call_tool('save_cashflow_result',{'result':result,'request_id':request}))
                assert save['status']=='committed',save
                record['calls'].append({'tool':'save_cashflow_result','status':save['status'],'receipt':save['receipt']})
                query_args={k:result[k] for k in ['period','source_revision','run_id']};query_args['request_id']=request
                queried=unpack(await session.call_tool('query_cashflow_result',query_args))
                assert queried['receipt']==save['receipt'] and queried['result']==result
                record['calls'].append({'tool':'query_cashflow_result','status':queried['status']})
        # Start a genuinely new server process. Persistence must survive process exit.
        async with stdio_client(params,errlog=log) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                reopened=unpack(await session.call_tool('query_cashflow_result',query_args))
                assert reopened['receipt']==save['receipt']
                record['restart_readback']=True
    config=Config(env['CF_TENANT_ID'],env['CF_COMPANY_ID'],Path(env['CF_RESULT_FILE']),env['CF_RESULT_SHA256'],
                  env['CF_DB_NAME'],port=int(env['CF_DB_PORT']),user='root',qa=True,allow_fixture=True)
    # Independent DB query, separate from MCP response formatting.
    with Service(config).connect() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT record_id,payload_sha256,COUNT(*) OVER() n FROM mfg_cashflow_runs_v1 WHERE tenant_id=%s AND company_id=%s AND request_id=%s',
                        (config.tenant,config.company,request))
            row=cur.fetchone()
            assert row['n']==1 and row['record_id']==save['receipt']['record_id']
            assert row['payload_sha256']==hashlib.sha256(canonical(result)).hexdigest()
    record.update(status='passed',independent_database_readback=True,qwen_platform=False,production_deployed=False)
    record['fixture_file']=env['CF_RESULT_FILE']
    (ROOT/'evidence'/('MCP真实MySQL闭环'+label+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k not in ['tools','calls']},ensure_ascii=False,indent=2))

if __name__=='__main__':asyncio.run(main())
