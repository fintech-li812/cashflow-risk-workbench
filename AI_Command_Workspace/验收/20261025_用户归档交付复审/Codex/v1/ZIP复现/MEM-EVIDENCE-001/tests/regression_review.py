import sys,json,copy
from pathlib import Path
root,work=map(Path,sys.argv[1:3]);work.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(root/'src'))
from evidence_store import Store,StoreError
from result_guard import load_result_json
result=json.loads((root/'fixtures/synthetic_success.json').read_text(encoding='utf-8'))
context=json.loads((root/'fixtures/trusted_context.json').read_text(encoding='utf-8'))
rows=[]
def record(name, rejected):rows.append({'case':name,'expected':'reject','actual':'reject' if rejected else 'accepted','passed':rejected})
try:load_result_json('{"status":"success","status":"unavailable"}');record('duplicate_json_keys',False)
except ValueError:record('duplicate_json_keys',True)
s=Store.open(str(work/'operation.sqlite3'))
try:s.save(result,context,'bad-operation',allow_fixture=True,operation='invented_operation');record('operation_closed_set',False)
except StoreError:record('operation_closed_set',True)
finally:s.close()
for mode in ['wrong_context_version','get_link','history_link','replay_link','verify_flag']:
    s=Store.open(str(work/(mode+'.sqlite3')))
    saved=s.save(result,context,'probe-'+mode,allow_fixture=True)
    rid=saved['receipt']['record_id']
    ctx=copy.deepcopy(context)
    if mode=='wrong_context_version':ctx['run_id']='another-run'
    else:
        s.conn.execute('DROP TRIGGER trg_evidence_no_update')
        if mode=='verify_flag':s.conn.execute('UPDATE evidence_record SET reconciliation_state=?',('not_performed',))
        else:s.conn.execute('UPDATE evidence_record SET run_id=?',('tampered-run',))
    try:
        if mode in ('wrong_context_version','get_link'):s.get(ctx,rid)
        elif mode=='history_link':s.history(context,context['period'])
        elif mode=='replay_link':s.save(result,context,'probe-'+mode,allow_fixture=True)
        else:
            report=s.verify()
            if report['problems']:raise ValueError('detected')
        record(mode,False)
    except (StoreError,ValueError):record(mode,True)
    finally:s.close()
s=Store.open(str(work/'normal.sqlite3'))
a=s.save(result,context,'normal',allow_fixture=True)
b=s.save(result,context,'normal',allow_fixture=True)
normal=s.get(context,a['receipt']['record_id'])
rows.append({'case':'normal_idempotency_readback','passed':a['receipt']==b['receipt'] and normal['payload']==result and not s.verify()['problems']})
s.close()
print(json.dumps({'cases':rows,'passed':sum(r['passed'] for r in rows),'total':len(rows)},ensure_ascii=False))

raise SystemExit(0 if all(r["passed"] for r in rows) else 1)
