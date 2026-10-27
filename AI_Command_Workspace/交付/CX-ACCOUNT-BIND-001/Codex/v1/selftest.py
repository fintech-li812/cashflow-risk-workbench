from pathlib import Path
import argparse,hashlib,json,sys,unittest,time

ROOT=Path(__file__).resolve().parent
def hashes():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['fixtures','expected'] for p in (ROOT/folder).rglob('*') if p.is_file()}
def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',required=True);a=p.parse_args();out=Path(a.output_dir)
    if out.exists():return 3
    out.mkdir();before=hashes();suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    with (out/'unittest.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    after=hashes();passed=result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped)
    report={'task_id':'CX-ACCOUNT-BIND-001','total':result.testsRun,'passed':passed,'failed':len(result.failures)+len(result.errors),'blocked':0,'not_run':len(result.skipped),'independent_inputs_and_expected_unchanged':before==after,'failures':[test.id() for test,_ in result.failures+result.errors],'origin':'offline_fixture','native_sheet_verified':False}
    (out/'selftest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False));return 0 if result.wasSuccessful() and before==after and not result.skipped else 2
if __name__=='__main__':raise SystemExit(main())
