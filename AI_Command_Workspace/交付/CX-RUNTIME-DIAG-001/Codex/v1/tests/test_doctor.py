from pathlib import Path
import json,hashlib,tempfile,unittest,sys,os,subprocess
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import doctor

ROOT=Path(__file__).resolve().parents[1]
WORK=Path(tempfile.mkdtemp(prefix='doctor_tests_',dir=ROOT/'evidence'))

class DoctorTests(unittest.TestCase):
    def fixture(self):
        root=Path(tempfile.mkdtemp(prefix='case_',dir=WORK));(root/'evidence').mkdir()
        for name in doctor.REQUIRED:
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('test reference',encoding='utf-8')
        fixture=root/'fixtures/calculated_result_v1.json';fixture.write_text('{}',encoding='utf-8')
        (root/'qa_entry.py').write_text('APPROVED_SHA256='+repr(doctor.sha(fixture)),encoding='utf-8')
        (root/'requirements.lock.txt').write_text('mcp==1.30.0\nPyMySQL==1.1.2\n',encoding='utf-8')
        (root/'evidence/qa_runtime.json').write_text(json.dumps({'database':'cfqa_test','port':13317}),encoding='utf-8')
        source=root/'sample.bin';source.write_bytes(b'controlled source hash only')
        python=root/'python.exe';python.write_bytes(b'never execute in unit tests')
        binding={'schema_version':'mfg-launch-diagnostic-binding.v1','project_root':str(root),'python_executable':str(python),'source_file':str(source),'source_sha256':doctor.sha(source),'files':[{'path':name,'sha256':doctor.sha(root/name)} for name in sorted(doctor.REQUIRED)]}
        return root,binding
    def check(self,b,**kw):return doctor.diagnose(b,version_probe=lambda p,n:{'mcp':'1.30.0','pymysql':'1.1.2'},**kw)
    def test_valid_offline_does_not_probe_network(self):
        _,b=self.fixture()
        r=self.check(b,network_probe=lambda p:self.fail('network should be opt-in'))
        self.assertEqual(r['status'],'passed');self.assertFalse(r['database_authenticated']);self.assertFalse(r['native_sheet_verified'])
        self.assertEqual(r['checks'][-1]['status'],'not_run')
    def test_bound_code_changed(self):
        root,b=self.fixture();(root/'src/app.py').write_text('changed',encoding='utf-8')
        self.assertEqual(self.check(b)['status'],'failed')
    def test_missing_required_binding(self):
        _,b=self.fixture();b['files'].pop();self.assertEqual(self.check(b)['status'],'failed')
    def test_duplicate_binding(self):
        _,b=self.fixture();b['files'].append(b['files'][0]);self.assertEqual(self.check(b)['status'],'failed')
    def test_invalid_hash(self):
        _,b=self.fixture();b['files'][0]['sha256']='bad';self.assertEqual(self.check(b)['status'],'failed')
    def test_traversal_path(self):
        root,b=self.fixture()
        with self.assertRaises(ValueError):doctor.local_file(root,'../outside')
    def test_absolute_path(self):
        root,b=self.fixture()
        with self.assertRaises(ValueError):doctor.local_file(root,'C:/outside')
    def test_pin_changed_even_if_outer_binding_rehashed(self):
        root,b=self.fixture();(root/'qa_entry.py').write_text("APPROVED_SHA256='"+'0'*64+"'",encoding='utf-8')
        next(x for x in b['files'] if x['path']=='qa_entry.py')['sha256']=doctor.sha(root/'qa_entry.py')
        self.assertEqual(self.check(b)['checks'][-1]['reason'],'launcher_fixture_pin_invalid')
    def test_formal_database_blocked(self):
        root,b=self.fixture();(root/'evidence/qa_runtime.json').write_text(json.dumps({'database':'cf_workbench','port':13317}),encoding='utf-8')
        self.assertEqual(self.check(b)['checks'][-1]['reason'],'isolated_database_required')
    def test_boolean_port_blocked(self):
        root,b=self.fixture();(root/'evidence/qa_runtime.json').write_text(json.dumps({'database':'cfqa_test','port':True}),encoding='utf-8')
        self.assertEqual(self.check(b)['status'],'failed')
    def test_bad_port_blocked(self):
        root,b=self.fixture();(root/'evidence/qa_runtime.json').write_text(json.dumps({'database':'cfqa_test','port':70000}),encoding='utf-8')
        self.assertEqual(self.check(b)['status'],'failed')
    def test_source_changed(self):
        root,b=self.fixture();(root/'sample.bin').write_bytes(b'changed');self.assertEqual(self.check(b)['status'],'failed')
    def test_python_missing(self):
        root,b=self.fixture();b['python_executable']=str(root/'missing.exe');self.assertEqual(self.check(b)['status'],'blocked')
    def test_dependency_mismatch(self):
        _,b=self.fixture();r=doctor.diagnose(b,version_probe=lambda p,n:{'mcp':'0.0','pymysql':'1.1.2'})
        self.assertEqual(r['status'],'failed')
    def test_probe_timeout_redacted(self):
        _,b=self.fixture()
        def fail(p,n):raise subprocess.TimeoutExpired('do-not-echo',20)
        r=doctor.diagnose(b,version_probe=fail);self.assertEqual(r['status'],'blocked');self.assertNotIn('do-not-echo',json.dumps(r))
    def test_tcp_reachable_is_not_database_auth(self):
        _,b=self.fixture();r=self.check(b,probe_tunnel=True,network_probe=lambda p:True)
        self.assertEqual(r['status'],'passed');self.assertFalse(r['database_authenticated'])
    def test_tunnel_refusal(self):
        _,b=self.fixture()
        def fail(p):raise ConnectionRefusedError()
        r=self.check(b,probe_tunnel=True,network_probe=fail);self.assertEqual(r['status'],'blocked')
    def test_password_in_config_not_echoed(self):
        root,b=self.fixture();(root/'evidence/qa_runtime.json').write_text(json.dumps({'database':'cfqa_test','port':13317,'password':'synthetic-sensitive-marker'}),encoding='utf-8')
        r=self.check(b);self.assertEqual(r['status'],'failed');self.assertNotIn('synthetic-sensitive-marker',json.dumps(r))
    def test_duplicate_json_keys(self):
        root,b=self.fixture();p=root/'duplicate.json';p.write_text('{"port":1,"port":2}',encoding='utf-8')
        with self.assertRaises(ValueError):doctor.load(p)
    def test_nonfinite_json(self):
        root,b=self.fixture();p=root/'nonfinite.json';p.write_text('{"port":NaN}',encoding='utf-8')
        with self.assertRaises(ValueError):doctor.load(p)
    def test_child_environment_excludes_project_credentials(self):
        with patch.dict(os.environ,{'CF_DB_PASSWORD':'synthetic-sensitive-marker','PYTHONPATH':'untrusted'}):
            with patch('doctor.subprocess.run') as call:
                call.return_value=subprocess.CompletedProcess([],0,'{"mcp":"1.30.0"}','')
                self.assertEqual(doctor.runtime_versions('python',['mcp']),{'mcp':'1.30.0'})
                child=call.call_args.kwargs['env'];self.assertNotIn('CF_DB_PASSWORD',child);self.assertNotIn('PYTHONPATH',child)
                self.assertIn('-I',call.call_args.args[0])
    def test_nonpinned_lock(self):
        root,b=self.fixture();p=root/'requirements.lock.txt';p.write_text('mcp>=1.0\n',encoding='utf-8')
        next(x for x in b['files'] if x['path']=='requirements.lock.txt')['sha256']=doctor.sha(p)
        self.assertEqual(self.check(b)['checks'][-1]['reason'],'requirements_not_fully_pinned')
    def test_runtime_config_not_object(self):
        root,b=self.fixture();(root/'evidence/qa_runtime.json').write_text('[]',encoding='utf-8')
        self.assertEqual(self.check(b)['status'],'failed')
    def test_main_exit_codes(self):
        root,b=self.fixture();binding=root/'binding.json';binding.write_text(json.dumps(b),encoding='utf-8')
        for status,expected in [('passed',0),('failed',2),('blocked',3)]:
            output=root/(status+'.json')
            with patch('doctor.diagnose',return_value={'status':status,'schema_version':doctor.SCHEMA}):
                with patch.object(sys,'argv',['doctor.py','--binding',str(binding),'--output',str(output)]):
                    self.assertEqual(doctor.main(),expected)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['status'],status)
    def test_main_preserves_existing_output(self):
        root,b=self.fixture();output=root/'existing.json';output.write_text('keep',encoding='utf-8')
        with patch.object(sys,'argv',['doctor.py','--output',str(output)]):self.assertEqual(doctor.main(),2)
        self.assertEqual(output.read_text(encoding='utf-8'),'keep')

if __name__=='__main__':unittest.main(verbosity=2)
