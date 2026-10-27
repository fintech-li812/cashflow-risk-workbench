"""Loopback fixture-only QA web + actual MCP HTTP endpoint; no public deployment."""
import asyncio,hashlib,json,os,sys
from contextlib import asynccontextmanager
from pathlib import Path
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse,FileResponse
from starlette.routing import Route,Mount
import uvicorn
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from config import Config
from service import Service,canonical,strict_result
from app import build_mcp

ROOT=Path(__file__).resolve().parents[1]
PORT=int(os.getenv('CF_WEB_PORT','18765'))
ORIGIN=f'http://127.0.0.1:{PORT}'

def qa_service():
    config=Config.from_env()
    if not(config.qa and config.allow_fixture):raise ValueError('qa_web_only')
    return Service(config)

def source_metadata(loaded):
    result=loaded['result']
    fields={k:result[k] for k in ['tenant_id','company_id','period','source_revision','run_id','calculation_version']}
    fields['source_file_sha256']=loaded['source_file_sha256']
    return {**fields,'workflow_fingerprint':hashlib.sha256(canonical(fields)).hexdigest(),
        'source':result['source'],'fixture':True,'platform_native_verified':False}

def unpack(response):
    if response.isError:raise ValueError('mcp_tool_rejected_request')
    return response.structuredContent if response.structuredContent is not None else json.loads(response.content[0].text)

async def invoke(action,request_id,fingerprint):
    qa_service()
    params=StdioServerParameters(command=sys.executable,args=['-B',str(ROOT/'src'/'app.py')],env=os.environ.copy())
    runtime_dir=Path(os.getenv('CF_RUNTIME_DIR',str(ROOT.parent/'_runtime_v2')))
    runtime_dir.mkdir(parents=True,exist_ok=True)
    with (runtime_dir/'web_mcp_stderr.log').open('a',encoding='utf-8') as log:
        async with stdio_client(params,errlog=log) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                loaded=unpack(await session.call_tool('read_cashflow_result',{}))
                metadata=source_metadata(loaded)
                if metadata['workflow_fingerprint']!=fingerprint:
                    return {'status':'conflict','detail':'来源或版本已变化。请刷新页面，为新版本建立新请求；旧请求保持原编号。'}
                result=loaded['result']
                args={'request_id':request_id,**{k:result[k] for k in ['period','source_revision','run_id']}}
                if action=='run':
                    saved=unpack(await session.call_tool('save_cashflow_result',{'result':result,'request_id':request_id}))
                    if saved['status']!='committed':return {'status':saved['status'],'detail':saved.get('reason',''),'read':loaded}
                queried=unpack(await session.call_tool('query_cashflow_result',args))
                if queried['status']!='committed':return {'status':queried['status'],'read':loaded}
                if queried['result']!=result:raise ValueError('readback_payload_mismatch')
                return {'status':'committed','read':loaded,'receipt':queried['receipt'],'readback_verified':True,
                    'qwen_platform':False,'fixture':True,'store':'isolated_mysql','metadata':metadata}

async def home(request):return FileResponse(ROOT/'web'/'index.html')
async def browser_script(request):return FileResponse(ROOT/'web'/'app.js',media_type='text/javascript')
async def health(request):
    try:
        service=qa_service()
        def database_check():
            with service.connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='mfg_cashflow_runs_v1'")
                    if cursor.fetchone()['n']!=1:raise ValueError('required_table_missing')
        await asyncio.to_thread(database_check)
        return JSONResponse({'status':'ready','mode':'合成数据工程联调','database':'已连通隔离测试库',
            'platform':'千问尚未接入','mcp_http':f'{ORIGIN}/mcp/','release_authorized':False})
    except Exception as exc:
        return JSONResponse({'status':'unavailable','database':'尚未确认连接','error':type(exc).__name__,
            'platform':'千问尚未接入','release_authorized':False},status_code=503)

async def metadata(request):
    try:return JSONResponse(source_metadata(qa_service().read()))
    except Exception as exc:return JSONResponse({'status':'unavailable','error':type(exc).__name__},status_code=503)

async def api(request:Request):
    if request.headers.get('host')!=f'127.0.0.1:{PORT}':return JSONResponse({'error':'host_rejected'},status_code=403)
    if request.headers.get('origin')!=ORIGIN:return JSONResponse({'error':'origin_rejected'},status_code=403)
    if request.headers.get('content-type','').split(';',1)[0].strip().lower()!='application/json':
        return JSONResponse({'error':'json_required'},status_code=415)
    raw=bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw)>4096:return JSONResponse({'error':'request_too_large'},status_code=413)
    try:body=strict_result(bytes(raw))
    except Exception:return JSONResponse({'error':'invalid_json'},status_code=400)
    if not isinstance(body,dict) or set(body)!={'request_id','workflow_fingerprint'}:
        return JSONResponse({'error':'request_contract_invalid'},status_code=400)
    request_id,fingerprint=body['request_id'],body['workflow_fingerprint']
    if not isinstance(request_id,str) or not request_id.strip() or len(request_id)>128:
        return JSONResponse({'error':'request_id_invalid'},status_code=400)
    import re
    if not isinstance(fingerprint,str) or not re.fullmatch('[0-9a-f]{64}',fingerprint):
        return JSONResponse({'error':'workflow_fingerprint_invalid'},status_code=400)
    action=request.url.path.rsplit('/',1)[-1]
    try:
        result=await asyncio.wait_for(invoke(action,request_id,fingerprint),timeout=70)
        return JSONResponse(result)
    except Exception as exc:
        # A run may have reached commit before the response was lost. Never label
        # that outcome failed/not_found or create a replacement request id.
        return JSONResponse({'status':'pending' if action=='run' else 'unavailable','error':type(exc).__name__,
            'detail':'本次结果未确认，请保留同一请求编号回查。没有生成新编号。'},status_code=503)

def create_app():
    mcp=build_mcp(PORT)
    mcp_http=mcp.streamable_http_app()
    @asynccontextmanager
    async def lifespan(app):
        qa_service()
        async with mcp.session_manager.run():yield
    return Starlette(lifespan=lifespan,routes=[Route('/',home),Route('/app.js',browser_script),Route('/api/health',health),Route('/api/source',metadata),
        Route('/api/run',api,methods=['POST']),Route('/api/query',api,methods=['POST']),Mount('/mcp',app=mcp_http)])

app=create_app()
if __name__=='__main__':
    qa_service()
    uvicorn.run(app,host='127.0.0.1',port=PORT,access_log=False)
