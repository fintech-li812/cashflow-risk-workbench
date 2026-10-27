from pathlib import Path
import argparse,json,sys
from account_binding import assess,canonical,sha

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['check']);p.add_argument('--bundle',required=True);p.add_argument('--trust',required=True);p.add_argument('--output-dir',required=True);p.add_argument('--allow-fixture',action='store_true');a=p.parse_args()
    out=Path(a.output_dir)
    if out.exists() or out.is_symlink():print('output_directory_exists',file=sys.stderr);return 3
    report=assess(a.bundle,a.trust,allow_fixture=a.allow_fixture)
    try:
        out.mkdir(parents=False,exist_ok=False)
        data=json.dumps(report,ensure_ascii=False,indent=2).encode('utf-8')
        with (out/'binding_result.json').open('xb') as f:f.write(data)
        manifest={'schema_version':'mfg-account-binding-report.v1','files':[{'path':'binding_result.json','sha256':sha(data)}]}
        with (out/'manifest.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
    except OSError:print('output_write_failed_incomplete',file=sys.stderr);return 3
    print(json.dumps({'status':report['status'],'scope_ready':report['scope_ready'],'balance_binding_ready':report['balance_binding_ready'],'can_save_source_result':False,'issues':report['issues']},ensure_ascii=False))
    return {'ready':0,'blocked':2,'invalid':3}[report['status']]
if __name__=='__main__':raise SystemExit(main())
