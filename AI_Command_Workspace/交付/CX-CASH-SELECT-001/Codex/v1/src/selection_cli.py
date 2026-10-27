from pathlib import Path
import argparse,json,sys
from cash_selection import plan
from account_binding import sha
def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['plan']);p.add_argument('--bundle',required=True);p.add_argument('--trust',required=True);p.add_argument('--output-dir',required=True);p.add_argument('--allow-fixture',action='store_true');a=p.parse_args();out=Path(a.output_dir)
    if out.exists() or out.is_symlink():print('output_exists',file=sys.stderr);return 3
    report=plan(a.bundle,a.trust,allow_fixture=a.allow_fixture)
    try:
        out.mkdir(exist_ok=False)
        text=json.dumps(report,ensure_ascii=False,indent=2).encode('utf-8')
        with (out/'selection.json').open('xb') as f:f.write(text)
        with (out/'manifest.json').open('x',encoding='utf-8') as f:json.dump({'schema_version':'mfg-cash-selection-report.v1','files':[{'path':'selection.json','sha256':sha(text)}]},f,ensure_ascii=False,indent=2)
    except OSError:print('output_incomplete_io_failure',file=sys.stderr);return 3
    print(json.dumps({'status':report['status'],'counts':report['counts'],'issues':report['issues']},ensure_ascii=False));return {'ready':0,'blocked':2,'invalid':3}[report['status']]
if __name__=='__main__':raise SystemExit(main())
