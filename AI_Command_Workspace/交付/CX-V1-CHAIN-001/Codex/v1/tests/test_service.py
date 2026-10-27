import copy,hashlib,json,sys,unittest,uuid
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
import pymysql

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from config import Config
from service import Service,canonical

class MySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime=json.loads((ROOT/'evidence'/'qa_runtime.json').read_text(encoding='utf-8'))
        file=ROOT/'fixtures'/'approved_result.json'
        cls.config=Config('fixture-tenant','fixture-manufacturing',file,hashlib.sha256(file.read_bytes()).hexdigest(),
                          runtime['database'],port=runtime['port'],user='root',qa=True,allow_fixture=True)
        cls.out=ROOT/'evidence'/'mysql-test-files';cls.out.mkdir(exist_ok=True)
    def setUp(self):
        self.service=Service(self.config);self.result=self.service.read()['result']
        self.request='test-'+uuid.uuid4().hex
    def query(self,service=None):
        return (service or self.service).query(self.request,self.result['period'],self.result['source_revision'],self.result['run_id'])
    def test_01_commit_and_exact_query(self):
        saved=self.service.save(self.result,self.request)
        self.assertEqual(saved['status'],'committed',saved)
        self.assertEqual(self.query()['receipt'],saved['receipt'])
    def test_02_idempotent_replay_one_row(self):
        a=self.service.save(self.result,self.request);b=self.service.save(self.result,self.request)
        self.assertEqual(a['receipt']['record_id'],b['receipt']['record_id'])
        with self.service.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) n FROM mfg_cashflow_runs_v1 WHERE request_id=%s',(self.request,))
                self.assertEqual(cursor.fetchone()['n'],1)
    def test_03_process_state_not_required(self):
        a=self.service.save(self.result,self.request)
        b=self.query(Service(self.config))
        self.assertEqual(a['receipt']['record_id'],b['receipt']['record_id'])
    def test_04_context_revision_conflict(self):
        self.service.save(self.result,self.request)
        r=self.service.query(self.request,self.result['period'],'other-version',self.result['run_id'])
        self.assertEqual(r['status'],'conflict')
    def test_05_different_approved_payload_conflict(self):
        self.service.save(self.result,self.request)
        changed=copy.deepcopy(self.result);changed['run_id']='changed-run'
        file=self.out/(self.request+'.json');file.write_bytes(canonical(changed))
        other=Service(replace(self.config,result_file=file,result_sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
        self.assertEqual(other.save(changed,self.request)['status'],'conflict')
        self.assertEqual(self.query()['result']['run_id'],self.result['run_id'])
    def test_06_hallucinated_amounts_rejected(self):
        changed=copy.deepcopy(self.result);changed['amounts'].update(inflow='140000.00',net='50000.00',closing='150000.00',difference='-10000.00')
        with self.assertRaisesRegex(ValueError,'approved_snapshot'):self.service.save(changed,self.request)
    def test_07_trusted_company_rejected(self):
        self.result['company_id']='other-company'
        with self.assertRaisesRegex(ValueError,'trusted_identity'):self.service.save(self.result,self.request)
    def test_08_default_fixture_rejected(self):
        with self.assertRaises(ValueError):Service(replace(self.config,allow_fixture=False)).read()
    def test_09_missing_db_is_pending_not_success(self):
        unavailable=Service(replace(self.config,port=19999))
        self.assertEqual(unavailable.save(self.result,self.request)['status'],'pending')
    def test_10_query_failure_is_not_notfound(self):
        with self.assertRaises(pymysql.err.OperationalError):self.query(Service(replace(self.config,port=19999)))
    def test_11_corrupt_stored_hash_detected(self):
        self.service.save(self.result,self.request)
        with self.service.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute('UPDATE mfg_cashflow_runs_v1 SET payload_sha256=%s WHERE request_id=%s',('0'*64,self.request))
            conn.commit()
        with self.assertRaisesRegex(ValueError,'digest_mismatch'):self.query()
    def test_12_request_sql_characters_parameterized(self):
        self.request="fixture-' OR 1=1 -- "+uuid.uuid4().hex
        saved=self.service.save(self.result,self.request)
        self.assertEqual(saved['receipt']['request_id'],self.request)
    def test_13_invalid_request(self):
        with self.assertRaisesRegex(ValueError,'request_id_invalid'):self.service.save(self.result,' ')
    def test_14_root_production_rejected(self):
        with self.assertRaisesRegex(ValueError,'root_only'):Service(replace(self.config,database='cf_workbench'))
    def test_15_changed_snapshot_stops_read(self):
        with self.assertRaisesRegex(ValueError,'snapshot_file_changed'):Service(replace(self.config,result_sha256='0'*64)).read()
    def test_16_before_commit_failure_no_row(self):
        class Fault:
            def __init__(self,conn):self.conn=conn
            def __getattr__(self,k):return getattr(self.conn,k)
            def commit(self):raise pymysql.err.OperationalError(2013,'fixture before commit')
        connection=self.service.connect()
        with patch.object(self.service,'connect',return_value=Fault(connection)):
            result=self.service.save(self.result,self.request)
        self.assertEqual(result['status'],'pending');self.assertEqual(self.query()['status'],'not_found')
    def test_17_after_commit_receipt_loss_then_replay(self):
        class Fault:
            def __init__(self,conn):self.conn=conn
            def __getattr__(self,k):return getattr(self.conn,k)
            def commit(self):
                self.conn.commit();raise pymysql.err.OperationalError(2013,'fixture response lost')
        connection=self.service.connect()
        with patch.object(self.service,'connect',return_value=Fault(connection)):
            result=self.service.save(self.result,self.request)
        self.assertEqual(result['status'],'pending')
        found=self.query();self.assertEqual(found['status'],'committed')
        replay=self.service.save(self.result,self.request)
        self.assertEqual(replay['receipt']['record_id'],found['receipt']['record_id'])

if __name__=='__main__':unittest.main(verbosity=2)
