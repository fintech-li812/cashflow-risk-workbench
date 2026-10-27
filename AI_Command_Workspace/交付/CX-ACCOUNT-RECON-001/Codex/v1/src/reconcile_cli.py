from pathlib import Path
import argparse,json,sys
from reconciliation import reconcile
from account_binding import sha
def main():
    p=argparse.ArgumentParser();p.add_argument('--account-bundle',required=True);p.add_argument('--account-trust',required=True);p.add_argument('--cash-bundle',required=True);p.add_argument('--cash-trust',required=True);p.add_argument('--output-dir',required=True);p.add_argument('--allow-fixture',action='store_true');a=p.parse_args();out=Path(a.output_dir)
    if out.exists() or out.is_symlink():print('output_exists',file=sys.stderr);return 3
    result=reconcile(a.account_bundle,a.account_trust,a.cash_bundle,a.cash_trust,allow_fixture=a.allow_fixture)
    try:
        out.mkdir(exist_ok=False)
        files={"reconciliation.json":result}
        for key in ['account_binding','selection','normalized_fixture_input','cashflow_result']:
            if result.get(key) is not None:files[key+'.json']=result[key]
        manifest=[]
        for name,value in files.items():
            data=json.dumps(value,ensure_ascii=False,indent=2).encode('utf-8')
            with (out/name).open('xb') as f:f.write(data)
            manifest.append({'path':name,'sha256':sha(data)})
        with (out/'manifest.json').open('x',encoding='utf-8') as f:json.dump({'schema_version':'mfg-per-account-reconciliation-package.v1','files':manifest},f,ensure_ascii=False,indent=2)
    except OSError:print('output_incomplete_io_failure',file=sys.stderr);return 3
    print(json.dumps({'status':result['status'],'reconciliation_state':result['reconciliation_state'],'issues':result['issues'],'can_save_source_result':False},ensure_ascii=False));return {'ready':0,'blocked':2,'invalid':3}[result['status']]
if __name__=='__main__':raise SystemExit(main())
