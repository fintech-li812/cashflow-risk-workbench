from pathlib import Path
import tempfile,shutil,json,sys,hashlib,copy,unittest,subprocess
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import reconciliation as r
import account_binding as a
import cash_selection as c
from agent_guard import validate_result
FIX=ROOT/'fixtures';EXP=json.loads((ROOT/'expected/independent_values.json').read_text(encoding='utf-8'))
WORK=Path(tempfile.mkdtemp(prefix='reconciliation_tests_',dir=ROOT/'evidence'))
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class ReconciliationTests(unittest.TestCase):
    def fixture(self):
        work=Path(tempfile.mkdtemp(prefix='case_',dir=WORK));shutil.copytree(FIX,work/'inputs');f=work/'inputs';return work,f/'account_bundle',f/'account_trust.json',f/'cash_bundle',f/'cash_trust.json'
    def run_case(self,paths):return r.reconcile(*paths[1:],allow_fixture=True)
    def approve(self,b,t):
        v=read(t);v['approved_inputs']={name:digest(b/name) for name in v['approved_inputs']};write(t,v)
    def update_scope_snapshot(self,ab,at,cb,ct):
        value=a.assess(ab,at,allow_fixture=True);write(cb/'scope_binding.json',value);self.approve(cb,ct)
    def cash_event(self,cb,ct,rid,fn):
        data=read(cb/'events.json');fn(next(row for row in data['records'] if row['record_id']==rid));write(cb/'events.json',data);self.approve(cb,ct)
    def balance(self,ab,at,aid,kind,value):
        data=read(ab/'balances.json');next(x for x in data['records'] if x['account_id']==aid and x['kind']==kind)['amount']=value;write(ab/'balances.json',data)
        for f in (ab/'sources').glob('*.json'):
            src=read(f)
            for row in src['records']:
                if row['account_id']==aid and row['kind']==kind:row['amount']=value
            write(f,src)
        m=read(ab/'evidence_manifest.json')
        for src in m['sources']:src['sha256']=digest(ab/src['path'])
        write(ab/'evidence_manifest.json',m);self.approve(ab,at)
    def test_exact_consolidated_independent_expected(self):
        p=self.fixture();result=self.run_case(p);self.assertEqual(result['status'],'ready');self.assertEqual(result['cashflow_result']['amounts'],EXP['consolidated'])
    def test_exact_account_A(self):
        p=self.fixture();result=self.run_case(p);row=next(x for x in result['per_account'] if x['account_id']=='fixture-account-A')
        for key,want in EXP['per_account']['fixture-account-A'].items():self.assertEqual(row[key],want)
    def test_exact_account_B(self):
        p=self.fixture();result=self.run_case(p);row=next(x for x in result['per_account'] if x['account_id']=='fixture-account-B')
        for key,want in EXP['per_account']['fixture-account-B'].items():self.assertEqual(row[key],want)
    def test_internal_transfers_count_for_individual_not_consolidated(self):
        p=self.fixture();result=self.run_case(p);acct={x['account_id']:x for x in result['per_account']}
        self.assertIn('transfer-out',acct['fixture-account-A']['record_ids']);self.assertIn('transfer-in',acct['fixture-account-B']['record_ids'])
        self.assertEqual(result['cashflow_result']['amounts']['outflow'],'100.00');self.assertEqual(acct['fixture-account-A']['outflow'],'300.00')
    def test_invoice_and_business_corroboration_not_added(self):
        p=self.fixture();result=self.run_case(p);self.assertEqual(result['cashflow_result']['amounts']['inflow'],'1400.00')
    def test_difference_not_automatically_balanced(self):
        p=self.fixture();result=self.run_case(p);self.assertEqual(result['reconciliation_state'],'difference_pending_review');self.assertEqual(result['cashflow_result']['amounts']['difference'],'38700.00')
    def test_exact_guarded_fixture_result(self):
        p=self.fixture();result=self.run_case(p);validate_result(result['cashflow_result'],result['context'],allow_fixture=True);self.assertEqual(result['cashflow_result']['origin'],'offline_fixture');self.assertFalse(result['can_save_source_result']);self.assertFalse(result['native_sheet_verified'])
    def test_default_fixture_mode_refused(self):
        p=self.fixture();result=r.reconcile(*p[1:]);self.assertEqual(result['status'],'invalid');self.assertIsNone(result['cashflow_result'])
    def test_missing_actual_closing_hard_block(self):
        p=self.fixture();_,ab,at,cb,ct=p;data=read(ab/'balances.json');data['records']=[x for x in data['records'] if x['kind']!='closing'];write(ab/'balances.json',data);self.approve(ab,at)
        result=self.run_case(p);self.assertEqual(result['status'],'blocked');self.assertIsNone(result['cashflow_result']);self.assertEqual(result['per_account'],[])
    def test_missing_opening_hard_block(self):
        p=self.fixture();_,ab,at,cb,ct=p;data=read(ab/'balances.json');data['records']=[x for x in data['records'] if x['kind']!='opening'];write(ab/'balances.json',data);self.approve(ab,at);self.assertEqual(self.run_case(p)['status'],'blocked')
    def test_unconfirmed_scope_blocks(self):
        p=self.fixture();_,ab,at,cb,ct=p;data=read(ab/'scope.json');data['scope_confirmed']=False;write(ab/'scope.json',data);self.approve(ab,at);self.assertEqual(self.run_case(p)['status'],'blocked')
    def test_category_pending_blocks(self):
        p=self.fixture();_,ab,at,cb,ct=p;self.cash_event(cb,ct,'bank-loan',lambda row:row.update(category='unconfirmed'));result=self.run_case(p);self.assertEqual(result['status'],'blocked');self.assertIsNone(result['cashflow_result'])
    def test_missing_transfer_approval_blocks(self):
        p=self.fixture();_,ab,at,cb,ct=p;data=read(cb/'decisions.json');data['transfers']=[];write(cb/'decisions.json',data);self.approve(cb,ct);self.assertEqual(self.run_case(p)['status'],'blocked')
    def test_stale_balance_binding_snapshot_rejected(self):
        p=self.fixture();_,ab,at,cb,ct=p;self.balance(ab,at,'fixture-account-A','closing','90000.01');result=self.run_case(p);self.assertEqual(result['status'],'invalid');self.assertIn('ACCOUNT_BINDING_SNAPSHOT_STALE',result['issues'])
    def test_one_cent_difference_preserved_after_snapshot_refresh(self):
        p=self.fixture();_,ab,at,cb,ct=p;self.balance(ab,at,'fixture-account-A','closing','90000.01');self.update_scope_snapshot(ab,at,cb,ct);result=self.run_case(p);self.assertEqual(result['cashflow_result']['amounts']['difference'],'38700.01')
    def test_matching_independent_balances(self):
        p=self.fixture();_,ab,at,cb,ct=p;self.balance(ab,at,'fixture-account-A','closing','61100.00');self.balance(ab,at,'fixture-account-B','closing','40200.00');self.update_scope_snapshot(ab,at,cb,ct);result=self.run_case(p);self.assertEqual(result['reconciliation_state'],'matched');self.assertEqual(result['cashflow_result']['amounts']['difference'],'0.00')
    def test_negative_account_balance_preserved(self):
        p=self.fixture();_,ab,at,cb,ct=p;self.balance(ab,at,'fixture-account-A','opening','-10000.00');self.update_scope_snapshot(ab,at,cb,ct);result=self.run_case(p);self.assertEqual(result['status'],'ready');self.assertEqual(next(x for x in result['per_account'] if x['account_id']=='fixture-account-A')['calculated_closing'],'-8900.00')
    def test_large_payment_creates_negative_net_without_correction(self):
        p=self.fixture();_,ab,at,cb,ct=p;self.cash_event(cb,ct,'bank-expense',lambda row:row.update(amount='99999.99'));result=self.run_case(p);self.assertEqual(result['status'],'ready');self.assertEqual(result['cashflow_result']['amounts']['net'],'-98599.99')
    def test_cross_context_failure(self):
        p=self.fixture();_,ab,at,cb,ct=p;data=read(cb/'scope_binding.json');data['context']['run_id']='other';write(cb/'scope_binding.json',data);self.approve(cb,ct);self.assertEqual(self.run_case(p)['status'],'invalid')
    def test_reapproved_duplicate_excluded_from_account_and_consolidation(self):
        p=self.fixture();_,ab,at,cb,ct=p;events=read(cb/'events.json');row=copy.deepcopy(events['records'][0]);row.update(record_id='approved-duplicate',source_record_key=hashlib.sha256(b'new-row').hexdigest());events['records'].append(row);write(cb/'events.json',events);dec=read(cb/'decisions.json');dec['duplicates']=[{'keep_record_id':'bank-sale','duplicate_record_ids':['approved-duplicate'],'evidence_ref':'SYNTHETIC'}];write(cb/'decisions.json',dec);self.approve(cb,ct)
        result=self.run_case(p);self.assertEqual(result['cashflow_result']['amounts'],EXP['consolidated']);self.assertNotIn('approved-duplicate',[rid for a in result['per_account'] for rid in a['record_ids']])
    def test_transfer_input_mutation_between_checks_rejected(self):
        p=self.fixture();_,ab,at,cb,ct=p;original=r.plan
        def change(*args,**kwargs):
            result=original(*args,**kwargs);data=read(cb/'events.json')
            for row in data['records']:
                if row['record_id'] in ('transfer-in','transfer-out'):row['amount']='300.00'
            write(cb/'events.json',data);return result
        with patch('reconciliation.plan',side_effect=change):result=self.run_case(p)
        self.assertEqual(result['status'],'invalid');self.assertIsNone(result['cashflow_result'])
    def test_no_real_business_calculation(self):
        p=self.fixture();_,ab,at,cb,ct=p
        for name in ['scope.json','balances.json','evidence_manifest.json']:
            v=read(ab/name);v['origin']='operator_registered_evidence';write(ab/name,v)
        for f in (ab/'sources').glob('*.json'):
            v=read(f);v['origin']='operator_registered_evidence';write(f,v)
        self.balance(ab,at,'fixture-account-A','opening','60000.00');result=self.run_case(p)
        self.assertEqual(result['status'],'blocked');self.assertIn('REAL_RESULTS_REQUIRE_QWEN_NATIVE_FORMULAS',result['issues']);self.assertIsNone(result['cashflow_result'])
    def test_per_account_and_consolidated_invariants(self):
        p=self.fixture();result=self.run_case(p);self.assertTrue(result['invariants']['individual_and_consolidated_net_equal']);self.assertTrue(result['invariants']['individual_and_consolidated_difference_equal'])
    def test_originals_expected_unchanged(self):
        p=self.fixture();work=p[0];before={str(f.relative_to(work)):digest(f) for f in work.rglob('*') if f.is_file()};e=digest(ROOT/'expected/independent_values.json');self.run_case(p);self.assertEqual(before,{str(f.relative_to(work)):digest(f) for f in work.rglob('*') if f.is_file()});self.assertEqual(e,digest(ROOT/'expected/independent_values.json'))
    def test_cli_result_bundle_and_collision(self):
        p=self.fixture();work,ab,at,cb,ct=p;out=work/'output';cmd=[sys.executable,'-B',str(ROOT/'src/reconcile_cli.py'),'--account-bundle',str(ab),'--account-trust',str(at),'--cash-bundle',str(cb),'--cash-trust',str(ct),'--output-dir',str(out),'--allow-fixture'];proc=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        for item in read(out/'manifest.json')['files']:self.assertEqual(digest(out/item['path']),item['sha256'])
        before=digest(out/'reconciliation.json');proc=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(proc.returncode,3);self.assertEqual(before,digest(out/'reconciliation.json'))

if __name__=='__main__':unittest.main(verbosity=2)
