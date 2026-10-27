"""Loopback QA UI -> official MCP stdio -> isolated real MySQL.
Not a public/authenticated production web service. Production configuration refused.
"""
import asyncio,json,os,sys
from contextlib import asynccontextmanager
from pathlib import Path
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse,FileResponse
from starlette.routing import Route
import uvicorn
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from config import Config

ROOT=Path(__file__).resolve().parents[1]
PORT=int(os.getenv('CF_WEB_PORT','18765'))
ORIGIN=f'http://127.0.0.1:{PORT}'

def unpack(response):
    if response.isError:raise ValueError('mcp_tool_rejected_request')
    return response.structuredContent if response.structuredContent is not None else json.loads(response.content[0].text)

async def invoke(action,request_id):
    config=Config.from_env()
    if not config.qa or not config.allow_fixture:raise ValueError('qa_web_only')
    params=StdioServerParameters(command=sys.executable,args=['-B',str(ROOT/'src'/'app.py')],env=os.environ.copy())
    # File logs stay in the explicitly configured QA output directory.
    runtime_dir=Path(os.getenv('CF_RUNTIME_DIR',str(ROOT.parent/'_runtime')))
    runtime_dir.mkdir(parents=True,exist_ok=True)
    with (runtime_dir/'web_mcp_stderr.log').open('a',encoding='utf-8') as log:
        async with stdio_client(params,errlog=log) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                loaded=unpack(await session.call_tool('read_cashflow_result',{}))
                result=loaded['result']
                args={'request_id':request_id,**{k:result[k] for k in ['period','source_revision','run_id']}}
                if action=='run':
                    saved=unpack(await session.call_tool('save_cashflow_result',{'result':result,'request_id':request_id}))
                    if saved['status']!='committed':return {'status':saved['status'],'detail':saved.get('reason',''),'read':loaded}
                queried=unpack(await session.call_tool('query_cashflow_result',args))
                if queried['status']!='committed':return {'status':queried['status'],'read':loaded}
                if queried['result']!=result:raise ValueError('readback_payload_mismatch')
                return {'status':'committed','read':loaded,'receipt':queried['receipt'],'readback_verified':True,
                        'qwen_platform':False,'fixture':True,'store':'isolated_mysql'}

async def home(request):return FileResponse(ROOT/'web'/'index.html')
async def health(request):
    return JSONResponse({'mode':'合成数据工程联调','platform':'千问尚未接入','store':'真实MySQL隔离测试库',
                         'release_authorized':False})
async def api(request:Request):
    if request.headers.get('host')!=f'127.0.0.1:{PORT}':return JSONResponse({'error':'host_rejected'},status_code=403)
    if request.headers.get('origin')!=ORIGIN:return JSONResponse({'error':'origin_rejected'},status_code=403)
    if not request.headers.get('content-type','').startswith('application/json'):
        return JSONResponse({'error':'json_required'},status_code=415)
    raw=await request.body()
    if len(raw)>4096:return JSONResponse({'error':'request_too_large'},status_code=413)
    try:
        try:body=json.loads(raw)
        except (json.JSONDecodeError,UnicodeDecodeError):return JSONResponse({'error':'invalid_json'},status_code=400)
        if not isinstance(body,dict) or set(body)!={'request_id'} or not isinstance(body['request_id'],str) or not body['request_id'].strip() or len(body['request_id'])>128:
            return JSONResponse({'error':'request_id_invalid'},status_code=400)
        result=await asyncio.wait_for(invoke(request.url.path.rsplit('/',1)[-1],body['request_id']),timeout=70)
        return JSONResponse(result)
    except Exception as exc:
        # Do not return raw DB errors, local configuration or credentials.
        return JSONResponse({'status':'unavailable','error':type(exc).__name__,
                             'detail':'本次未确认完成，请使用同一请求编号回查，勿重复创建请求。'},status_code=503)

app=Starlette(routes=[Route('/',home),Route('/api/health',health),Route('/api/run',api,methods=['POST']),Route('/api/query',api,methods=['POST'])])

if __name__=='__main__':
    config=Config.from_env()
    if not (config.qa and config.allow_fixture):raise SystemExit('This candidate UI only runs in isolated fixture QA mode')
    uvicorn.run(app,host='127.0.0.1',port=PORT,access_log=False)
