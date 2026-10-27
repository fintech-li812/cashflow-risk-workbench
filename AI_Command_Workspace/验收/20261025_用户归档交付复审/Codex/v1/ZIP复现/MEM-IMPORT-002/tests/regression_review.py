import sys,shutil,json,contextlib,io
from pathlib import Path
root,work=map(Path,sys.argv[1:3]);work.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(root/'src'))
from mfg_import.scanner import scan
from mfg_import.verifier import verify
from mfg_import.convert import serial_to_date
rows=[]
for n,want in [('1','1900-01-01'),('59','1900-02-28'),('61','1900-03-01')]:
    actual=serial_to_date(n,False).isoformat()
    rows.append({'case':'serial_'+n,'expected':want,'actual':actual,'passed':actual==want})
source=work/'source';source.mkdir()
shutil.copyfile(str(root/'fixtures/controlled_sample.xlsx'),source/'制造业_样例数据.xlsx')
pkg=work/'scan'
with contextlib.redirect_stdout(io.StringIO()):
    rc=scan(str(source),str(pkg),str(root/'mapping/mfg_sample_mapping.json'),'probe-tenant','probe-company','2026-09','probe-run',exceptions_path=str(root/'unit_exceptions.json'))
inventory=json.loads((pkg/'inventory.json').read_text(encoding='utf-8'))
records=[json.loads(x) for x in (pkg/'records.jsonl').read_text(encoding='utf-8').splitlines()]
d8=next(r for r in records if r['sheet']=='现金流水' and r['row']==8)['normalized']['经营性流入（万元）']['value']
rows.append({'case':'sample_D8_null_and_duplicates_preserved','passed':d8 is None and len([r for r in records if r['sheet']=='现金流水' and r['row'] in (12,15)])==2,'sample_counts':inventory['counts']})
with contextlib.redirect_stdout(io.StringIO()):rc=verify(str(pkg),str(source))
rows.append({'case':'clean_verify','passed':rc==0,'exit_code':rc})
tampered=work/'omitted_manifest';shutil.copytree(pkg,tampered)
mp=tampered/'manifest.json';m=json.loads(mp.read_text(encoding='utf-8'));m['files']=[x for x in m['files'] if x['path']=='mapping.snapshot.json'];mp.write_text(json.dumps(m,ensure_ascii=False),encoding='utf-8')
log=io.StringIO()
with contextlib.redirect_stdout(log):rc=verify(str(tampered),str(source))
rows.append({'case':'manifest_omits_required_files','expected':'nonzero','exit_code':rc,'passed':rc!=0,'output':log.getvalue()[-1600:]})
print(json.dumps({'cases':rows,'passed':sum(r['passed'] for r in rows),'total':len(rows)},ensure_ascii=False))

raise SystemExit(0 if all(r["passed"] for r in rows) else 1)
