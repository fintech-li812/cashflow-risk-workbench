"""Launch the already-provisioned isolated QA preview; no install/DDL/key access."""
from pathlib import Path
import hashlib,json,os,subprocess,sys

ROOT=Path(__file__).resolve().parent
def main():
    qa=json.loads((ROOT/'evidence'/'qa_runtime.json').read_text(encoding='utf-8'))
    if not qa['database'].startswith('cfqa_'):raise SystemExit('isolated QA database required')
    fixture=ROOT/'fixtures'/'calculated_result_v1.json'
    env=os.environ.copy()
    runtime_dir=ROOT.parent/'_runtime'
    env.update(CF_TENANT_ID='fixture-tenant',CF_COMPANY_ID='fixture-manufacturing',
        CF_RESULT_FILE=str(fixture),CF_RESULT_SHA256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
        CF_DB_NAME=qa['database'],CF_DB_HOST='127.0.0.1',CF_DB_PORT=str(qa['port']),CF_DB_USER='root',
        CF_QA_MODE='1',CF_ALLOW_FIXTURE='1',CF_WEB_PORT='18765',CF_RUNTIME_DIR=str(runtime_dir),PYTHONUTF8='1')
    env.pop('CF_DB_PASSWORD',None)
    print('Temporary local fixture QA preview: http://127.0.0.1:18765/ . Requires existing authorized QA tunnel.')
    raise SystemExit(subprocess.call([sys.executable,'-B',str(ROOT/'src'/'web_server.py')],env=env))

if __name__=='__main__':main()
