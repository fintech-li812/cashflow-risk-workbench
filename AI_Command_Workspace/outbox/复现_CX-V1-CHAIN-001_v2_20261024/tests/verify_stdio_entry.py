"""Read-only probe of the exact stdio entry configured in Qwen. No saves/DDL."""
import asyncio,hashlib,json,os,sys
from datetime import timedelta,datetime,timezone
from importlib.metadata import version
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from qa_entry import environment
from config import Config
from service import Service

def unpack(response):
    if response.isError:raise AssertionError('MCP tool rejected the probe')
    return response.structuredContent if response.structuredContent is not None else json.loads(response.content[0].text)

async def main():
    params=StdioServerParameters(command=sys.executable,args=['-B','-u',str(ROOT/'qa_entry.py'),'stdio'],env=os.environ.copy())
    runtime=ROOT.parent/'_runtime_v2';runtime.mkdir(exist_ok=True)
    with (runtime/'stdio_entry_probe_stderr.txt').open('a',encoding='utf-8') as log:
        async with stdio_client(params,errlog=log) as (read,write):
            async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=30)) as session:
                initialized=await session.initialize();listing=await session.list_tools()
                names=[tool.name for tool in listing.tools]
                assert set(names)=={'read_cashflow_result','save_cashflow_result','query_cashflow_result'}
                result=unpack(await session.call_tool('read_cashflow_result',{}))
                assert result['fixture'] is True and result['platform_native_verified'] is False
                assert result['result']['amounts']['net']=='40000.00'
                assert result['source_file_sha256']=='e6470f7adeba00804b178be5dc17a3087a88758178b9482cfd64b8cf81cf36d7'
    os.environ.update(environment());service=Service(Config.from_env())
    with service.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) n FROM mfg_cashflow_runs_v1 WHERE tenant_id=%s AND company_id=%s AND request_id=%s',
                ('fixture-tenant','fixture-manufacturing','qwen-v2-native-20261024-01'))
            native_rows=cursor.fetchone()['n']
    report={'status':'passed','checked_at':datetime.now(timezone.utc).isoformat(),'read_only':True,
        'python':sys.executable,'mcp':version('mcp'),'PyMySQL':version('PyMySQL'),
        'tools':names,'fixture':True,'platform_native_verified':False,
        'qwen_request_existing_rows':native_rows,'qwen_agent_called_by_this_probe':False,
        'source_file_sha256':result['source_file_sha256'],'production_deployed':False}
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':asyncio.run(main())
