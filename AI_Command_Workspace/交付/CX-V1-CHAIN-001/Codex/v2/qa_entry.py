"""Entry point for the provisioned QA fixture. No installation, SSH, DDL or credentials.

stdout is reserved for MCP protocol in stdio mode. This is NOT a production launcher.
"""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys

ROOT=Path(__file__).resolve().parent
APPROVED_SHA256='e6470f7adeba00804b178be5dc17a3087a88758178b9482cfd64b8cf81cf36d7'

def environment():
    qa=json.loads((ROOT/'evidence'/'qa_runtime.json').read_text(encoding='utf-8'))
    database,port=qa['database'],qa['port']
    if not isinstance(database,str) or not re.fullmatch(r'cfqa_[a-z0-9_]{1,58}',database):
        raise ValueError('isolated_qa_database_required')
    if type(port) is not int or not 1024<=port<=65535:raise ValueError('qa_tunnel_port_invalid')
    fixture=ROOT/'fixtures'/'calculated_result_v1.json'
    if hashlib.sha256(fixture.read_bytes()).hexdigest()!=APPROVED_SHA256:
        raise ValueError('approved_fixture_changed')
    env=os.environ.copy()
    # Override inherited project settings. Never inherit a production password/binding.
    env.update(CF_TENANT_ID='fixture-tenant',CF_COMPANY_ID='fixture-manufacturing',
        CF_RESULT_FILE=str(fixture),CF_RESULT_SHA256=APPROVED_SHA256,
        CF_DB_NAME=database,CF_DB_HOST='127.0.0.1',CF_DB_PORT=str(port),CF_DB_USER='root',
        CF_QA_MODE='1',CF_ALLOW_FIXTURE='1',CF_QWEN_BOUND='0',CF_WEB_PORT='18765',
        CF_RUNTIME_DIR=str(ROOT.parent/'_runtime_v2'),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
    env.pop('CF_DB_PASSWORD',None)
    return env

def main():
    mode=sys.argv[1] if len(sys.argv)==2 else None
    if mode not in ('stdio','web','check'):
        raise SystemExit('usage: qa_entry.py stdio|web|check')
    env=environment()
    if mode=='check':
        os.environ.update(env)
        sys.path.insert(0,str(ROOT/'src'))
        from config import Config
        from service import Service
        from importlib.metadata import version
        service=Service(Config.from_env());loaded=service.read()
        with service.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='mfg_cashflow_runs_v1'")
                if cursor.fetchone()['n']!=1:raise ValueError('required_table_missing')
        print(json.dumps({'status':'ready','fixture':loaded['fixture'],
            'source_file_sha256':loaded['source_file_sha256'],'database':env['CF_DB_NAME'],
            'mcp_version':version('mcp'),'pymysql_version':version('PyMySQL'),
            'qwen_platform_verified':False,'production_deployed':False},ensure_ascii=False,indent=2))
        return
    script=ROOT/'src'/('app.py' if mode=='stdio' else 'web_server.py')
    raise SystemExit(subprocess.call([sys.executable,'-B','-u',str(script)],env=env,cwd=ROOT))

if __name__=='__main__':main()
