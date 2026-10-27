"""Frozen acceptance entry. Run from task kit; never edits task sources or opens ports."""
from pathlib import Path
import argparse,copy,hashlib,json,subprocess,sys,shutil
ROOT=Path(__file__).resolve().parent
def load(p):
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise ValueError('duplicate_json_key')
            d[k]=v
        return d
    return json.loads(Path(p).read_text(encoding='utf-8-sig'),object_pairs_hook=unique,
                      parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite_json')))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,data):Path(p).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def run(cmd,path,expected=0):
    p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
    dump(path,{'command':cmd,'expected_exit':expected,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    assert p.returncode==expected,(p.returncode,expected,str(path))
    return p
def relpath(value):
    p=Path(value)
    assert not p.is_absolute() and '..' not in p.parts and ':' not in value and '\\' not in value
    return p
def native_checks(sub,out):
    entry=sub/'src/native_cli.py';binding=load(ROOT/'fixtures/native_binding.json')
    capture=load(ROOT/'fixtures/native_capture.json');context=load(ROOT/'fixtures/context.json')
    done=[]
    def case(name,b,c,ctx,expected=0,allow=True):
        folder=out/name;folder.mkdir();dump(folder/'binding.json',b);dump(folder/'capture.json',c);dump(folder/'context.json',ctx)
        cmd=[sys.executable,'-B',str(entry),'probe','--binding',str(folder/'binding.json'),'--capture',str(folder/'capture.json'),'--context',str(folder/'context.json'),'--output-dir',str(folder/'output')]
        if allow:cmd+=['--allow-fixture']
        run(cmd,folder/'process.json',expected)
        if expected==0:
            value=load(folder/'output/native_check.json')
            assert value['schema_version']=='mfg-native-check.v1'
            assert value['native_execution_verified'] is False and value['can_save_source_result'] is False
            assert value['transport_mode']=='replay'
        done.append(name)
        return folder
    good=case('N_B01_fixture_replay',binding,capture,context)
    value=load(good/'output/native_check.json');assert value['validation_status']=='passed' and value['platform_status']=='blocked'
    case('N_B02_fixture_default_reject',binding,capture,context,2,False)
    bad=copy.deepcopy(context);bad['company_id']='wrong';case('N_B03_company',binding,capture,bad,2)
    bad=copy.deepcopy(capture);bad['source_revision']='wrong';case('N_B04_revision',binding,bad,context,2)
    bad=copy.deepcopy(capture);bad['phases']['after']['cells']['B5']['value']='10000.00';case('N_B05_stale_cache',binding,bad,context,2)
    bad=copy.deepcopy(capture);bad['phases']['reopened']['cells']['B6']['formula']='=B2-B5';case('N_B06_wrong_formula',binding,bad,context,2)
    bad=copy.deepcopy(capture);bad['native_execution_verified']=True;case('N_B07_forged_native_claim',binding,bad,context,2)
    missing=copy.deepcopy(binding);missing['capabilities']={'read_cells':False,'request_recalculation':False}
    blocked=case('N_B08_missing_capability',missing,capture,context)
    assert load(blocked/'output/native_check.json')['validation_status']=='blocked'
    bad=copy.deepcopy(capture);bad['phases']['after']['sequence']=0;case('N_B09_phase_order',binding,bad,context,2)
    bad=copy.deepcopy(capture);bad['phases']['after']['cells']['B5']['value']=5000.0;case('N_B10_float',binding,bad,context,2)
    cmd=load(good/'process.json')['command'];run(cmd,out/'N_collision.json',3);done.append('N_B11_no_overwrite')
    assert load(good/'output/native_check.json')==value
    return done
def release_checks(sub,out):
    entry=sub/'src/release_cli.py';done=[]
    def case(name,modify=None,expected=0):
        folder=out/name;folder.mkdir();bundle=folder/'bundle';shutil.copytree(ROOT/'fixtures/release_bundle',bundle)
        if modify:modify(bundle)
        cmd=[sys.executable,'-B',str(entry),'assess','--bundle',str(bundle),'--output-dir',str(folder/'assessment'),'--allow-fixture']
        run(cmd,folder/'process.json',expected)
        if expected==0:
            result=load(folder/'assessment/assessment.json')
            assert result['schema_version']=='mfg-release-assessment.v1'
            assert result['offline_status']=='passed' and result['platform_status']=='blocked'
            assert result['production_deployed'] is False and result['can_claim_end_to_end'] is False
        done.append(name);return folder
    def edit(bundle,file,fn,rehash=False):
        d=load(bundle/file);fn(d);dump(bundle/file,d)
        if rehash:
            m=load(bundle/'manifest.json')
            for item in m['files']:item['sha256']=sha(bundle/relpath(item['path']))
            dump(bundle/'manifest.json',m)
    good=case('G_B01_candidate_not_live')
    case('G_B02_bad_file_hash',lambda b:edit(b,'result.json',lambda d:d['amounts'].update(net='0.00')),2)
    case('G_B03_bad_arithmetic_rehashed',lambda b:edit(b,'result.json',lambda d:d['amounts'].update(net='0.00'),True),2)
    case('G_B04_wrong_receipt_company',lambda b:edit(b,'receipt.json',lambda d:d.update(company_id='wrong'),True),2)
    case('G_B05_wrong_receipt_digest',lambda b:edit(b,'receipt.json',lambda d:d.update(payload_sha256='0'*64),True),2)
    case('G_B06_forged_release',lambda b:edit(b,'manifest.json',lambda d:d.update(production_deployed=True)),2)
    case('G_B07_traversal',lambda b:edit(b,'manifest.json',lambda d:d['files'][0].update(path='../result.json')),2)
    case('G_B08_native_flag_from_replay',lambda b:edit(b,'native_check.json',lambda d:d.update(native_execution_verified=True),True),2)
    case('G_B09_unknown_context',lambda b:edit(b,'context.json',lambda d:d.update(run_id='wrong'),True),2)
    cmd=load(good/'process.json')['command'];run(cmd,out/'G_collision.json',3);done.append('G_B10_no_overwrite')
    return done
def main():
    p=argparse.ArgumentParser();p.add_argument('--submission',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args()
    sub=Path(a.submission).resolve();out=Path(a.output_dir).resolve()
    if out.exists():raise ValueError('output must be new')
    out.mkdir(parents=True);task=load(ROOT/'task.json');result={'task_id':task['task_id'],'engineering_admission':'failed','production_deployed':False,'human_review_required_for_this_delivery':False}
    try:
        protected=load(ROOT/'manifest.json')['files']
        for f in protected:assert sha(ROOT/relpath(f['path']))==f['sha256'],'task kit changed'
        for required in ['README.md','requirements.lock.txt','实现与需求映射.json','未实现与限制.md','交付回执.json','src/selftest.py']:
            assert (sub/required).is_file(),'missing '+required
        cmd=[sys.executable,'-B',str(sub/'src/selftest.py'),'--workdir',str(out/'selftest-work'),'--report',str(out/'selftest_result.json')]
        run(cmd,out/'selftest_process.json')
        own=load(out/'selftest_result.json');tests=own['tests'];ids=[t['case_id'] for t in tests]
        assert len(ids)==len(set(ids)) and set(task['mandatory_cases']).issubset(ids)
        assert own['total']==len(tests)==own['passed'] and all(own[k]==0 for k in ['failed','blocked','not_run'])
        for t in tests:
            assert t['status']=='passed' and 'expected' in t and 'actual' in t
            assert isinstance(t['evidence'],list) and t['evidence'],'missing real per-case evidence'
            for ev in t['evidence']:assert sha(out/'selftest-work'/relpath(ev['path']))==ev['sha256']
        if task['kind'] in ['import','report']:
            fixed=ROOT/'冻结基线验收/自验入口.py'
            run([sys.executable,'-B',str(fixed),'--submission',str(sub),'--output-dir',str(out/'baseline_checks')],out/'baseline_process.json')
            independent=load(out/'baseline_checks/admission.json')
            assert independent['status']=='passed'
            checks=independent['external_checks']
        else:checks=native_checks(sub,out) if task['kind']=='native' else release_checks(sub,out)
        for f in protected:assert sha(ROOT/relpath(f['path']))==f['sha256'],'task kit modified during run'
        result.update(engineering_admission='passed',directly_submittable=True,selftest_count=len(tests),external_checks=checks,
                      platform_acceptance='blocked' if task['kind'] in ['native','release'] else 'not_in_scope',
                      submission_files=[{'path':p.relative_to(sub).as_posix(),'sha256':sha(p)} for p in sorted(sub.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and '.venv' not in p.parts])
    except Exception as exc:result.update(detail=str(exc),error=type(exc).__name__,directly_submittable=False)
    dump(out/'admission.json',result);print(json.dumps(result,ensure_ascii=False))
    return 0 if result['engineering_admission']=='passed' else 2
if __name__=='__main__':raise SystemExit(main())
