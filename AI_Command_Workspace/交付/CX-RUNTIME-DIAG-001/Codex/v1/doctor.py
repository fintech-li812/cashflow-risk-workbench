"""Read-only preflight for an explicitly bound local QA launcher. Not a server."""
from pathlib import Path
import argparse,ast,hashlib,json,os,re,socket,subprocess,sys

SCHEMA='mfg-local-runtime-diagnostic.v1'
REQUIRED={'qa_entry.py','src/app.py','src/config.py','src/service.py','src/workbench.py','fixtures/calculated_result_v1.json','requirements.lock.txt'}
SECRET_KEYS={'password','token','secret','private_key','connection_string'}
SAFE_REASONS={'configuration_too_large','duplicate_json_key','nonfinite_json','unsafe_binding_path','symlink_binding_path','binding_schema_invalid','secret_fields_not_allowed','project_missing_or_symlink','required_bindings_incomplete','binding_hash_invalid','bound_project_file_changed','launcher_fixture_pin_invalid','runtime_contains_secret_fields','isolated_database_required','tunnel_port_invalid','manufacturing_source_missing_or_changed','requirements_not_fully_pinned','duplicate_locked_dependency','core_dependencies_missing_from_lock'}
def load(path):
    if Path(path).stat().st_size>1_000_000:raise ValueError('configuration_too_large')
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('duplicate_json_key')
            d[k]=v
        return d
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=pairs,
        parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite_json')))
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def secret_fields(obj):
    if isinstance(obj,dict):
        for k,v in obj.items():
            if any(word in k.lower() for word in SECRET_KEYS):return True
            if secret_fields(v):return True
    elif isinstance(obj,list):return any(secret_fields(v) for v in obj)
    return False
def local_file(root,rel):
    if not isinstance(rel,str) or ':' in rel or '\\' in rel:raise ValueError('unsafe_binding_path')
    p=Path(rel)
    if p.is_absolute() or not p.parts or any(s in ('.','..') for s in p.parts):raise ValueError('unsafe_binding_path')
    target=root/p
    if not target.resolve().is_relative_to(root.resolve()) or any(a.is_symlink() for a in [target,*target.parents] if a.is_relative_to(root)):raise ValueError('symlink_binding_path')
    return target
def runtime_versions(python,packages):
    # Do not inherit CF_* credentials, PYTHONPATH or interpreter injection variables.
    allowed={'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','USERPROFILE','LOCALAPPDATA'}
    env={k:v for k,v in os.environ.items() if k.upper() in allowed}
    code='import json,sys,importlib.metadata as m; names=json.loads(sys.argv[1]); out={};\nfor n in names:\n try: out[n]=m.version(n)\n except m.PackageNotFoundError: out[n]=None\nprint(json.dumps(out))'
    proc=subprocess.run([str(python),'-I','-B','-c',code,json.dumps(packages)],env=env,capture_output=True,text=True,encoding='utf-8',timeout=20)
    if proc.returncode:raise RuntimeError('runtime_probe_failed')
    return json.loads(proc.stdout)
def tcp_probe(port):
    with socket.create_connection(('127.0.0.1',port),timeout=2):return True
def diagnose(binding,*,probe_tunnel=False,version_probe=runtime_versions,network_probe=tcp_probe):
    checks=[]
    def add(name,status,reason):checks.append({'check':name,'status':status,'reason':reason})
    def final():
        outcome='failed' if any(c['status']=='failed' for c in checks) else 'blocked' if any(c['status']=='blocked' for c in checks) else 'passed'
        return {'schema_version':SCHEMA,'status':outcome,'checks':checks,'scope':'local_QA_launch_preflight_only','database_authenticated':False,'native_sheet_verified':False,'production_deployed':False,'mutations_performed':False}
    try:
        if not isinstance(binding,dict) or binding.get('schema_version')!='mfg-launch-diagnostic-binding.v1':raise ValueError('binding_schema_invalid')
        if secret_fields(binding):raise ValueError('secret_fields_not_allowed')
        root=Path(binding['project_root']);python=Path(binding['python_executable'])
        if not root.is_dir() or root.is_symlink():raise ValueError('project_missing_or_symlink')
        files=binding['files'];names=[x['path'] for x in files]
        if len(names)!=len(set(names)) or set(names)!=REQUIRED:raise ValueError('required_bindings_incomplete')
        for item in files:
            if not re.fullmatch('[0-9a-f]{64}',item['sha256']):raise ValueError('binding_hash_invalid')
            fp=local_file(root,item['path'])
            if not fp.is_file() or sha(fp)!=item['sha256']:raise ValueError('bound_project_file_changed')
        add('bound_project_integrity','passed','all_seven_bound_files_match')
        tree=ast.parse((root/'qa_entry.py').read_text(encoding='utf-8-sig'))
        pins=[n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='APPROVED_SHA256' for t in n.targets) and isinstance(n.value,ast.Constant)]
        if len(pins)!=1 or pins[0]!=sha(root/'fixtures/calculated_result_v1.json'):raise ValueError('launcher_fixture_pin_invalid')
        add('launcher_fixture_pin','passed','approved_fixture_unchanged_not_source_workbook')
        config=load(root/'evidence/qa_runtime.json')
        if not isinstance(config,dict):raise ValueError('binding_schema_invalid')
        if secret_fields(config):raise ValueError('runtime_contains_secret_fields')
        database,port=config.get('database'),config.get('port')
        if not isinstance(database,str) or re.fullmatch('cfqa_[a-z0-9_]{1,58}',database) is None:raise ValueError('isolated_database_required')
        if type(port) is not int or not 1024<=port<=65535:raise ValueError('tunnel_port_invalid')
        add('isolated_QA_configuration','passed','isolated_database_and_valid_loopback_port')
        source=Path(binding['source_file'])
        if source.is_symlink() or not source.is_file() or sha(source)!=binding['source_sha256']:raise ValueError('manufacturing_source_missing_or_changed')
        add('manufacturing_source_integrity','passed','registered_source_hash_matches_no_cell_edits')
        locked={}
        for line in (root/'requirements.lock.txt').read_text(encoding='utf-8-sig').splitlines():
            line=line.strip()
            if not line or line.startswith('#'):continue
            if not re.fullmatch('[A-Za-z0-9_.-]+==[A-Za-z0-9_.+!-]+',line):raise ValueError('requirements_not_fully_pinned')
            name,value=line.split('==');key=re.sub('[-_.]+','-',name).lower()
            if key in locked:raise ValueError('duplicate_locked_dependency')
            locked[key]=value
        if not locked or 'mcp' not in locked or 'pymysql' not in locked:raise ValueError('core_dependencies_missing_from_lock')
        if not python.is_file():
            add('runtime_dependencies','blocked','python_executable_missing');return final()
        try:
            versions=version_probe(python,list(locked))
            if not isinstance(versions,dict) or set(versions)!=set(locked):raise ValueError('dependency_probe_output_invalid')
        except (OSError,subprocess.SubprocessError,RuntimeError,ValueError):
            add('runtime_dependencies','blocked','runtime_probe_failed_no_secret_output');return final()
        bad=[name for name,version in locked.items() if versions[name]!=version]
        add('runtime_dependencies','failed' if bad else 'passed','dependency_version_mismatch:'+','.join(bad) if bad else 'all_locked_versions_match')
        if probe_tunnel:
            if bad:
                add('tunnel_TCP_reachability','blocked','not_probed_due_to_dependency_failure')
            else:
                try:
                    reachable=network_probe(port)
                    add('tunnel_TCP_reachability','passed' if reachable else 'blocked','loopback_tcp_reachable_not_database_authentication' if reachable else 'loopback_tcp_unreachable')
                except OSError:add('tunnel_TCP_reachability','blocked','loopback_tcp_unreachable')
        else:add('tunnel_TCP_reachability','not_run','use_explicit_probe_tunnel_to_check_tcp_only')
    except (OSError,ValueError,KeyError,TypeError,SyntaxError) as exc:
        # Do not echo untrusted field values or exception messages which could contain secrets.
        reason=str(exc) if isinstance(exc,ValueError) and str(exc) in SAFE_REASONS else 'configuration_or_integrity_invalid'
        add('configuration_or_integrity','failed',reason)
    return final()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--binding',default=str(Path(__file__).with_name('binding.json')));parser.add_argument('--output',required=True);parser.add_argument('--probe-tunnel',action='store_true');args=parser.parse_args()
    target=Path(args.output)
    if target.exists():print('diagnostic_output_exists',file=sys.stderr);return 2
    try:result=diagnose(load(args.binding),probe_tunnel=args.probe_tunnel)
    except (OSError,ValueError,TypeError):result={'schema_version':SCHEMA,'status':'failed','reason':'binding_unreadable_or_invalid','mutations_performed':False,'production_deployed':False}
    try:
        with target.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    except OSError:print('diagnostic_output_not_writable',file=sys.stderr);return 2
    print(json.dumps(result,ensure_ascii=False))
    return {'passed':0,'failed':2,'blocked':3}[result['status']]
if __name__=='__main__':raise SystemExit(main())
