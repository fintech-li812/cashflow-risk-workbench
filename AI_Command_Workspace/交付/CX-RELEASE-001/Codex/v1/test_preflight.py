import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
import preflight as p


AUDIT=Path(os.environ.get('MFG_PREFLIGHT_TEST_WORKDIR', str(Path(__file__).parent / 'test-output' / 'selftest-workspaces')))


def package(path,task='candidate-test'):
    content={'README.md':b'offline candidate','runme.py':b'raise RuntimeError("must never execute")'}
    manifest={'task_id':task,'package_version':'v1','status':'candidate','files':[{'path':name,'sha256':hashlib.sha256(data).hexdigest()} for name,data in content.items()]}
    with zipfile.ZipFile(path,'w') as z:
        for name,data in content.items():z.writestr(name,data)
        z.writestr('manifest.json',json.dumps(manifest))


class Preflight(unittest.TestCase):
    def setUp(self):
        AUDIT.mkdir(parents=True,exist_ok=True)
        self.root=Path(tempfile.mkdtemp(prefix=self._testMethodName+'-',dir=AUDIT))
        self.project=self.root/'project';self.project.mkdir()
        self.workspace=self.root/'workspace';self.workspace.mkdir()
        self.roots={'project':self.project,'workspace':self.workspace}
        self.plan={'schema_version':'mfg-release-preflight.v1','target':'qwen_office','artifacts':[],'manual_gates':[]}
        for ident in p.ARTIFACTS:
            f=self.project/(ident+'.txt');f.write_text('placeholder only, not executable')
            self.plan['artifacts'].append({'id':ident,'root':'project','path':f.name,'kind':'file'})

    def test_nonempty_files_never_authorize_release(self):
        r=p.run(self.plan,self.roots)
        self.assertEqual(r['status'],'阻塞');self.assertFalse(r['release_authorized'])

    def test_empty_server_file_is_real_blocker(self):
        (self.project/'server_app.txt').write_bytes(b'')
        r=p.run(self.plan,self.roots)
        self.assertEqual(r['status'],'失败');self.assertEqual(r['counts']['失败'],1)

    def test_missing_file_is_failure(self):
        self.plan['artifacts'][0]['path']='not-provided.py'
        self.assertEqual(p.run(self.plan,self.roots)['status'],'失败')

    def test_cannot_remove_mandatory_artifacts_from_plan(self):
        self.plan['artifacts']=[]
        r=p.run(self.plan,self.roots)
        self.assertEqual(r['counts']['失败'],len(p.ARTIFACTS))

    def test_self_declared_approval_cannot_bypass_real_observation(self):
        self.plan['manual_gates']=[{'id':key,'declared_status':'通过'} for key in p.GATES]
        r=p.run(self.plan,self.roots)
        self.assertEqual(r['status'],'阻塞');self.assertFalse(r['release_authorized']);self.assertEqual(r['counts']['阻塞'],9)

    def test_explicit_failed_manual_gate_stays_failure(self):
        self.plan['manual_gates']=[{'id':'independent_review','declared_status':'失败'}]
        r=p.run(self.plan,self.roots)
        self.assertEqual(r['status'],'失败')

    def test_paths_may_not_escape_configured_roots(self):
        for value in ['../secret','/absolute','D:/x','a\\b','a//b','NUL.txt']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                p.locate(self.roots,'project',value)

    def test_fixed_artifact_digest_detects_change(self):
        self.plan['artifacts'][0]['sha256']='0'*64
        self.assertEqual(p.run(self.plan,self.roots)['status'],'失败')

    def test_package_reads_metadata_without_executing_candidate(self):
        archive=self.project/'candidate.zip';package(archive)
        self.plan['artifacts'][3].update(kind='candidate_zip',path=archive.name,task_id='candidate-test')
        r=p.run(self.plan,self.roots)
        self.assertEqual(r['status'],'阻塞')

    def test_package_task_id_must_match_plan(self):
        archive=self.project/'candidate.zip';package(archive)
        self.plan['artifacts'][3].update(kind='candidate_zip',path=archive.name,task_id='wrong-task')
        r=p.run(self.plan,self.roots)
        self.assertEqual(r['status'],'失败')

    def test_invalid_zip_path_rejected_not_extracted(self):
        archive=self.project/'escape.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('../outside.txt','data')
        with self.assertRaises(ValueError):p.package_metadata(archive)
        self.assertFalse((self.root/'outside.txt').exists())

    def test_duplicate_gate_not_counted_as_all_complete(self):
        gate={'id':'independent_review','declared_status':'通过'};self.plan['manual_gates']=[gate,gate]
        with self.assertRaises(ValueError):p.run(self.plan,self.roots)

    def test_bad_plan_target_rejected(self):
        self.plan['target']='other-platform'
        with self.assertRaises(ValueError):p.run(self.plan,self.roots)

    def test_unknown_check_kind_not_silently_passed(self):
        self.plan['artifacts'][0]['kind']='guess-success'
        self.assertEqual(p.run(self.plan,self.roots)['status'],'失败')

    def test_existing_output_is_not_overwritten(self):
        plan=self.root/'plan.json';plan.write_text(json.dumps(self.plan))
        output=self.root/'existing';output.mkdir();(output/'keep.txt').write_text('original')
        with contextlib.redirect_stdout(io.StringIO()):
            code=p.main(['--plan',str(plan),'--project-root',str(self.project),'--workspace-root',str(self.workspace),'--output',str(output)])
        self.assertEqual(code,1);self.assertEqual((output/'keep.txt').read_text(),'original')

    def test_output_inside_source_project_rejected(self):
        plan=self.root/'plan.json';plan.write_text(json.dumps(self.plan));output=self.project/'output'
        with contextlib.redirect_stdout(io.StringIO()):
            code=p.main(['--plan',str(plan),'--project-root',str(self.project),'--workspace-root',str(self.workspace),'--output',str(output)])
        self.assertEqual(code,1);self.assertFalse(output.exists())


if __name__=='__main__':unittest.main(verbosity=2)
