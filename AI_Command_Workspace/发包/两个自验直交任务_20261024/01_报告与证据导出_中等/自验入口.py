"""Frozen external acceptance entry. Uses only stdlib, never starts a server."""
from pathlib import Path
import argparse,copy,csv,hashlib,json,shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parent
def load(p):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('duplicate_json_key')
            out[k]=v
        return out
    return json.loads(Path(p).read_text(encoding='utf-8'),object_pairs_hook=pairs,
        parse_constant=lambda value:(_ for _ in ()).throw(ValueError('nonfinite_json')))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def save(p,obj):Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def run(command,log,expected=0):
    p=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
    save(log,{'arguments':command,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'expected_exit':expected})
    assert p.returncode==expected,('exit mismatch',p.returncode,expected,str(log))
    return p

def report_checks(sub,out):
    base=load(ROOT/'fixtures'/'result.json');receipt=load(ROOT/'fixtures'/'receipt.json')
    context=load(ROOT/'fixtures'/'context.json');entry=sub/'src'/'report_cli.py'
    records=[]
    def case(name,result,rcpt,expected=0,allow=True,raw=None):
        folder=out/name;folder.mkdir();rp=folder/'input.json';cp=folder/'context.json'
        if raw is None:save(rp,result)
        else:rp.write_text(raw,encoding='utf-8')
        save(cp,context);target=folder/'export'
        cmd=[sys.executable,'-B',str(entry),'export','--result',str(rp),'--context',str(cp),'--output-dir',str(target)]
        if allow:cmd+=['--allow-fixture']
        if rcpt is not None:save(folder/'receipt.json',rcpt);cmd+=['--receipt',str(folder/'receipt.json')]
        run(cmd,folder/'process.json',expected)
        if expected:
            assert not target.exists(),'invalid input created a misleading output';records.append(name);return None
        assert load(target/'result.json')==result
        manifest=load(target/'manifest.json');assert manifest['schema_version']=='mfg-report-export.v1'
        for item in manifest['files']:
            rel=Path(item['path']);assert not rel.is_absolute() and '..' not in rel.parts
            assert sha(target/rel)==item['sha256']
        html=(target/'report.html').read_text(encoding='utf-8')
        assert '<script' not in html.lower() and 'http://' not in html and 'https://' not in html
        assert '合成数据' in html
        if rcpt is None:assert '未提供入库凭据' in html and not (target/'receipt.json').exists()
        else:assert '未在线复核' in html and load(target/'receipt.json')==rcpt
        assert (target/'report.csv').exists();records.append(name);return target,html,cmd
    happy=case('B01_valid_receipt',base,receipt);case('B02_no_receipt',base,None)
    altered=copy.deepcopy(base);altered['amounts']['actual_closing']=altered['amounts']['difference']=None
    target,html,_=case('B03_missing_actual',altered,None);assert '尚未完成余额核对' in html
    for field in ('company_id','source_revision','run_id'):
        wrong=copy.deepcopy(receipt);wrong[field]='wrong'
        case('B04_wrong_'+field,base,wrong,2)
    wrong=copy.deepcopy(receipt);wrong['payload_sha256']='0'*64;case('B05_wrong_hash',base,wrong,2)
    wrong=copy.deepcopy(base);wrong['amounts']['net']='0.00';case('B06_wrong_arithmetic',wrong,None,2)
    wrong=copy.deepcopy(base);wrong['amounts']['inflow']=130000.0;case('B07_float_money',wrong,None,2)
    raw=json.dumps(base,ensure_ascii=False).replace('"unit": "CNY"','"unit": "CNY", "unit": "CNY"')
    case('B08_duplicate_key',base,None,2,raw=raw)
    case('B09_fixture_default_block',base,None,2,allow=False)
    wrong=copy.deepcopy(base);wrong['source']['workbook_ref']='<script>alert(1)</script>'
    _,html,_=case('B10_html_escape',wrong,None);assert '&lt;script&gt;' in html
    wrong=copy.deepcopy(base);wrong['source']['workbook_ref']='=SUM(1,1)'
    target,_,_=case('B11_csv_injection',wrong,None)
    with (target/'report.csv').open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream));row=next(x for x in rows if x['key']=='source.workbook_ref')
        assert row['value'].startswith("'="),'CSV formula injection not neutralized'
    target,html,cmd=happy;before={p.name:sha(p) for p in target.iterdir() if p.is_file()}
    run(cmd,out/'B12_existing_output.json',3)
    assert before=={p.name:sha(p) for p in target.iterdir() if p.is_file()};records.append('B12_existing_output')
    return records

def import_checks(sub,out):
    entry=sub/'src'/'import_cli.py';original=ROOT/'source'/'制造业_样例数据.xlsx'
    inputs=out/'source';inputs.mkdir();source=inputs/original.name;shutil.copy2(original,source)
    mapping=ROOT/'fixtures'/'mapping.json';original_sha=sha(source)
    args=['--mapping',str(mapping),'--tenant-id','fixture-tenant','--company-id','fixture-manufacturing',
        '--period','2026-08','--run-id','fixture-import-run']
    package=out/'scan';run([sys.executable,'-B',str(entry),'scan','--input',str(inputs),'--output',str(package),*args],out/'I_scan.json')
    manifest=load(package/'manifest.json');assert manifest['schema_version']=='mfg-import.v1' and manifest['kind']=='import_package'
    assert manifest['unit']=='CNY' and manifest['tenant_id']=='fixture-tenant' and manifest['company_id']=='fixture-manufacturing'
    assert manifest['period']=='2026-08' and manifest['run_id']=='fixture-import-run'
    revision=hashlib.sha256(canonical({'sources':[{'logical_name':source.name,'sha256':original_sha}],
        'mapping_sha256':sha(mapping)})).hexdigest();assert manifest['source_revision']==revision
    assert all((package/name).exists() for name in ['inventory.json','records.jsonl','issues.jsonl','report.html'])
    for item in manifest['files']:
        rel=Path(item['path']);assert not rel.is_absolute() and '..' not in rel.parts
        assert sha(package/rel)==item['sha256']
    records=[json.loads(line) for line in (package/'records.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    cash=[r for r in records if r['sheet']=='现金流水'];by_row={r['row']:r for r in cash}
    assert 8 in by_row and 12 in by_row and 15 in by_row
    assert by_row[8]['normalized']['operating_inflow']['value'] is None
    assert by_row[8]['normalized']['operating_inflow']['source_cell']=='D8'
    for rec in cash:
        key=hashlib.sha256(canonical({'source_file_sha256':original_sha,'sheet':'现金流水','row':rec['row']})).hexdigest()
        assert rec['source_record_key']==key
    assert by_row[12]['source_record_key']!=by_row[15]['source_record_key']
    run([sys.executable,'-B',str(entry),'verify','--package',str(package),'--source',str(inputs),'--report',str(out/'verify.json')],out/'I_verify.json')
    assert load(out/'verify.json')['status']=='passed'
    # Forge normalized values and then rehash the package, retaining the trusted original source.
    forged=out/'forged';shutil.copytree(package,forged)
    copied=copy.deepcopy(records)
    selected=next(r for r in copied if r['sheet']=='现金流水' and r['row']==3)
    field=selected['normalized']['operating_inflow'];field['value']='99999999.99'
    (forged/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in copied),encoding='utf-8')
    forged_manifest=load(forged/'manifest.json')
    for item in forged_manifest['files']:item['sha256']=sha(forged/item['path'])
    save(forged/'manifest.json',forged_manifest)
    run([sys.executable,'-B',str(entry),'verify','--package',str(forged),'--source',str(inputs),'--report',str(out/'forged_verify.json')],out/'I_forged.json',2)
    assert load(out/'forged_verify.json')['status']=='failed'
    marker=package/'do_not_touch.txt';marker.write_text('keep',encoding='utf-8')
    run([sys.executable,'-B',str(entry),'scan','--input',str(inputs),'--output',str(package),*args],out/'I_collision.json',3)
    assert marker.read_text(encoding='utf-8')=='keep' and sha(source)==original_sha==sha(original)
    return ['actual_sample_scan','source_revision','source_record_key','unit_exception_bound',
        'duplicates_preserved','source_verify','forged_rehash_detected','output_not_overwritten','source_unchanged']

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--submission',required=True);parser.add_argument('--output-dir',required=True)
    args=parser.parse_args();sub=Path(args.submission).resolve();out=Path(args.output_dir).resolve()
    if out.exists():raise ValueError('acceptance output must be new')
    out.mkdir(parents=True);kit=load(ROOT/'task.json');result={'task_id':kit['task_id'],'status':'failed','human_review_required':False}
    try:
        manifest=load(ROOT/'manifest.json')
        for item in manifest['files']:assert sha(ROOT/item['path'])==item['sha256'],'task kit changed'
        protected={item['path']:item['sha256'] for item in manifest['files']}
        run([sys.executable,'-B',str(sub/'src'/'selftest.py'),'--workdir',str(out/'selftest-work'),
            '--report',str(out/'selftest_result.json')],out/'selftest_process.json')
        own=load(out/'selftest_result.json');tests=own['tests'];ids=[x['case_id'] for x in tests]
        assert len(ids)==len(set(ids)) and set(kit['mandatory_cases']).issubset(ids)
        assert all(t['status']=='passed' and 'expected' in t and 'actual' in t and 'evidence' in t for t in tests)
        assert own['total']==len(tests)==own['passed'] and all(own[k]==0 for k in ('failed','blocked','not_run'))
        checks=report_checks(sub,out) if kit['kind']=='report' else import_checks(sub,out)
        assert all(sha(ROOT/name)==digest for name,digest in protected.items()),'fixed baseline modified'
        assert all((sub/name).exists() for name in ['README.md','requirements.lock.txt','实现与需求映射.json','未实现与限制.md'])
        result.update(status='passed',selftest_count=len(tests),external_checks=checks,
            submission_files=[{'path':p.relative_to(sub).as_posix(),'sha256':sha(p)} for p in sorted(sub.rglob('*'))
                if p.is_file() and '__pycache__' not in p.parts and '.venv' not in p.parts and p.suffix!='.pyc'],
            directly_submittable=True,production_deployed=False)
    except Exception as exc:
        result.update(error=type(exc).__name__,detail=str(exc),directly_submittable=False)
    save(out/'admission.json',result);print(json.dumps({'task_id':kit['task_id'],'status':result['status'],'admission':str(out/'admission.json')},ensure_ascii=False))
    return 0 if result['status']=='passed' else 2
if __name__=='__main__':raise SystemExit(main())
