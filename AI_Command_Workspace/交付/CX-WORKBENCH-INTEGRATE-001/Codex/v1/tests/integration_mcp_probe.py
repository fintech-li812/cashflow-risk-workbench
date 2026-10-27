import asyncio,json,os,sys
from pathlib import Path
from datetime import timedelta
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[1]
def unpack(response):
    if response.isError:raise AssertionError('tool failed')
    return response.structuredContent if response.structuredContent is not None else json.loads(response.content[0].text)
async def main():
    params=StdioServerParameters(command=sys.executable,args=['-B','-u',str(ROOT/'qa_entry.py'),'stdio'],env=os.environ.copy())
    report={'protocol':'official MCP SDK stdio','scope':'QA integration, read-only probe','qwen_native_call':False}
    with (ROOT/'evidence'/'MCP只读探测_stderr_恢复后.txt').open('x',encoding='utf-8') as log:
        async with stdio_client(params,errlog=log) as (read,write):
            async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=30)) as session:
                await session.initialize();listing=await session.list_tools()
                names={t.name for t in listing.tools}
                assert names=={'read_cashflow_result','save_cashflow_result','query_cashflow_result',
                    'get_workbench_status','list_manufacturing_sources','inspect_manufacturing_source','get_manufacturing_readiness'}
                status=unpack(await session.call_tool('get_workbench_status',{}))
                assert status['components']['database']=='connected' and status['result_profile']['fixture']
                sources=unpack(await session.call_tool('list_manufacturing_sources',{}))
                assert len(sources['sources'])==1 and sources['sources'][0]['status']=='available'
                inspected=unpack(await session.call_tool('inspect_manufacturing_source',{'source_id':'manufacturing_sample_v1'}))
                assert inspected['blocks']['现金流水']['cells']['D8']['raw_xml_value']=='1631300'
                ready=unpack(await session.call_tool('get_manufacturing_readiness',{}))
                assert ready['status']=='blocked' and not ready['can_save_source_result'] and 'amounts' not in ready
                bad=await session.call_tool('inspect_manufacturing_source',{'source_id':'../../secret'})
                assert bad.isError
                old=unpack(await session.call_tool('read_cashflow_result',{}))
                assert old['fixture'] and old['result']['source']['workbook_ref']=='synthetic-manufacturing-v1'
                report.update(status='passed',tools=sorted(names),project_status=status,readiness=ready,
                    source_sha256=inspected['source_file_sha256'],original_values_preserved=True,
                    invalid_source_rejected=True,no_save_invoked=True)
    (ROOT/'evidence'/'标准MCP整合探测.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['status','tools','source_sha256','original_values_preserved','invalid_source_rejected','no_save_invoked']},ensure_ascii=False,indent=2))
if __name__=='__main__':asyncio.run(main())
