"""Known candidate ZIP self-check. Run with the pinned jsonschema Python runtime.
Usage: python check_candidate.py --package KNOWN.zip --output NEW_DIRECTORY
Only this frozen package is executable here; no arbitrary supplied code is run.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

EXPECTED='eaa5acc7bf0d79a3bd6c2da90d2cd8a163fcf3d5a04714b5512fe32c66fdd5a8'
DEPENDENCIES={'jsonschema':'4.26.0','referencing':'0.37.0','attrs':'26.1.0',
              'rpds-py':'2026.9.1','jsonschema-specifications':'2025.9.1'}

def run(package, output):
    output=Path(output).resolve()
    # Never overwrite a previous run or execute directly in the frozen source.
    output.mkdir(parents=True,exist_ok=False)
    report={'status':'blocked','release_authorized':False,'steps':[],
            'platform_calls':0,'database_operations':0}
    try:
        package=Path(package).resolve()
        if package.stat().st_size>2_000_000:
            raise ValueError('package_size_limit')
        digest=hashlib.sha256(package.read_bytes()).hexdigest()
        if digest!=EXPECTED:
            raise ValueError('package_sha256_mismatch_no_code_executed')
        report['package_sha256']=digest
        for name,expected in DEPENDENCIES.items():
            if importlib.metadata.version(name)!=expected:
                raise ValueError('dependency_version_mismatch:'+name)
        unpack=output/'candidate-copy'
        with zipfile.ZipFile(package) as archive:
            names=archive.namelist()
            if len(names)!=len(set(names)) or sum(i.file_size for i in archive.infolist())>5_000_000:
                raise ValueError('archive_limits')
            for name in names:
                path=PurePosixPath(name)
                if path.is_absolute() or '..' in path.parts or ':' in name or '\\' in name:
                    raise ValueError('archive_path_invalid')
            manifest=json.loads(archive.read('manifest.json'))
            for entry in manifest['files']:
                if hashlib.sha256(archive.read(entry['path'])).hexdigest()!=entry['sha256']:
                    raise ValueError('manifest_mismatch')
            archive.extractall(unpack)
        report['manifest_files']=len(manifest['files'])
        commands=[('unit',[sys.executable,'-B','-m','unittest','-v','test_tool_call_guard','test_agent_bridge']),
                  ('mutations',[sys.executable,'-B','mutation_check.py'])]
        for label,command in commands:
            # Subprocess is bounded; all code belongs to the fixed known ZIP.
            with (output/(label+'.log')).open('w',encoding='utf-8') as stream:
                completed=subprocess.run(command,cwd=unpack,stdout=stream,stderr=subprocess.STDOUT,
                                         timeout=45,encoding='utf-8')
            report['steps'].append({'name':label,'exit_code':completed.returncode})
            if completed.returncode!=0:
                raise ValueError('test_failed:'+label)
        report['status']='passed_offline_only'
    except Exception as exc:
        report['reason']=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
    (output/'自检结果.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status']=='passed_offline_only' else 2

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',required=True)
    parser.add_argument('--output',required=True,help='Must be a new directory')
    options=parser.parse_args()
    try:
        code=run(options.package,options.output)
    except FileExistsError:
        print('Output already exists; choose a new directory. Nothing overwritten.')
        code=2
    raise SystemExit(code)
