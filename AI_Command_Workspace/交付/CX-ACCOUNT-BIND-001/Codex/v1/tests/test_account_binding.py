from pathlib import Path
import copy,json,hashlib,tempfile,shutil,sys,unittest,subprocess,os
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import account_binding as a
FIX=ROOT/'fixtures'
EXPECTED=json.loads((ROOT/'expected/independent_values.json').read_text(encoding='utf-8'))
WORK=Path(tempfile.mkdtemp(prefix='binding_tests_',dir=ROOT/'evidence'))
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class BindingTests(unittest.TestCase):
    def fixture(self):
        work=Path(tempfile.mkdtemp(prefix='case_',dir=WORK));bundle=work/'bundle';shutil.copytree(FIX/'complete_bundle',bundle)
        trust=work/'trust.json';shutil.copyfile(FIX/'trusted_binding.json',trust)
        return work,bundle,trust
    def approve(self,b,t):
        trust=read(t);trust['approved_inputs']={name:digest(b/name) for name in a.FILES};write(t,trust)
    def source_approve(self,b,t):
        m=read(b/'evidence_manifest.json')
        for s in m['sources']:s['sha256']=digest(b/s['path'])
        write(b/'evidence_manifest.json',m);self.approve(b,t)
    def change(self,b,t,name,fn,reapprove=True):
        value=read(b/name);fn(value);write(b/name,value)
        if reapprove:self.approve(b,t)
    def assess(self,b,t,**kw):return a.assess(b,t,allow_fixture=True,**kw)
    def assertCode(self,r,code):self.assertIn(code,[i['code'] for i in r['issues']])
    def test_complete_two_account_binding(self):
        _,b,t=self.fixture();r=self.assess(b,t)
        self.assertEqual(r['status'],EXPECTED['complete']['status']);self.assertEqual(r['balance_totals']['opening'],EXPECTED['complete']['opening']);self.assertEqual(r['balance_totals']['independent_closing'],EXPECTED['complete']['independent_closing'])
        self.assertFalse(r['can_claim_full_cashflow']);self.assertFalse(r['can_save_source_result']);self.assertFalse(r['source_authenticity_verified'])
    def test_default_fixture_rejected(self):
        _,b,t=self.fixture();self.assertCode(a.assess(b,t),'FIXTURE_NOT_EXPLICITLY_ALLOWED')
    def test_trust_fixture_flag_required(self):
        _,b,t=self.fixture();v=read(t);v['allow_fixture']=False;write(t,v);self.assertCode(self.assess(b,t),'FIXTURE_NOT_EXPLICITLY_ALLOWED')
    def test_trust_must_be_outside_upload(self):
        _,b,t=self.fixture();shutil.copyfile(t,b/'trust.json');self.assertCode(self.assess(b,b/'trust.json'),'TRUST_MUST_BE_EXTERNAL')
    def test_context_company_mismatch(self):
        _,b,t=self.fixture();self.change(b,t,'scope.json',lambda v:v.update(company_id='wrong'));self.assertCode(self.assess(b,t),'CONTEXT_MISMATCH')
    def test_run_mismatch(self):
        _,b,t=self.fixture();self.change(b,t,'balances.json',lambda v:v.update(run_id='wrong'));self.assertCode(self.assess(b,t),'CONTEXT_MISMATCH')
    def test_period_invalid(self):
        _,b,t=self.fixture();v=read(t);v['period']='2026-13';write(t,v);self.assertCode(self.assess(b,t),'PERIOD_INVALID')
    def test_scope_unconfirmed(self):
        _,b,t=self.fixture();self.change(b,t,'scope.json',lambda v:v.update(scope_confirmed=False));r=self.assess(b,t);self.assertEqual(r['status'],'blocked');self.assertIsNone(r['balance_totals']);self.assertCode(r,'ACCOUNT_SCOPE_NOT_CONFIRMED')
    def test_empty_scope(self):
        _,b,t=self.fixture();self.change(b,t,'scope.json',lambda v:v.update(accounts=[]));self.change(b,t,'balances.json',lambda v:v.update(records=[]));r=self.assess(b,t);self.assertEqual(r['status'],'blocked');self.assertCode(r,'NO_INCLUDED_ACCOUNTS')
    def test_duplicate_account(self):
        _,b,t=self.fixture();self.change(b,t,'scope.json',lambda v:v['accounts'].append(v['accounts'][0]));self.assertCode(self.assess(b,t),'ACCOUNT_ID_DUPLICATE_OR_INVALID')
    def test_other_entity_account(self):
        _,b,t=self.fixture();self.change(b,t,'scope.json',lambda v:v['accounts'][0].update(reporting_entity_id='other'));self.assertCode(self.assess(b,t),'ACCOUNT_ENTITY_MISMATCH')
    def test_foreign_currency_not_converted(self):
        _,b,t=self.fixture();self.change(b,t,'scope.json',lambda v:v['accounts'][0].update(currency='USD'));r=self.assess(b,t);self.assertEqual(r['status'],'blocked');self.assertIsNone(r['balance_totals']);self.assertCode(r,'ACCOUNT_CURRENCY_UNSUPPORTED')
    def test_excluded_account_not_aggregated(self):
        _,b,t=self.fixture()
        self.change(b,t,'scope.json',lambda v:v['accounts'][1].update(included=False,exclusion_reason='outside operator scope'))
        r=self.assess(b,t);self.assertEqual(r['status'],'ready');self.assertEqual(r['balance_totals']['opening'],'60000.00');self.assertEqual(r['scope_summary']['excluded_accounts'],1)
    def test_exclusion_requires_reason(self):
        _,b,t=self.fixture();self.change(b,t,'scope.json',lambda v:v['accounts'][0].update(included=False));self.assertCode(self.assess(b,t),'EXCLUDED_ACCOUNT_REASON_REQUIRED')
    def test_raw_account_number_not_exported(self):
        _,b,t=self.fixture();self.change(b,t,'scope.json',lambda v:v['accounts'][0].update(account_number='synthetic-number-marker'));r=self.assess(b,t);self.assertCode(r,'RAW_ACCOUNT_NUMBER_NOT_ALLOWED');self.assertNotIn('synthetic-number-marker',json.dumps(r))
    def test_missing_opening(self):
        _,b,t=self.fixture();self.change(b,t,'balances.json',lambda v:v.update(records=v['records'][1:]));r=self.assess(b,t);self.assertCode(r,'OPENING_BALANCE_MISSING');self.assertIsNone(r['balance_totals'])
    def test_missing_closing(self):
        _,b,t=self.fixture();self.change(b,t,'balances.json',lambda v:v.update(records=[x for x in v['records'] if x['kind']!='closing']));r=self.assess(b,t);self.assertEqual(r['status'],EXPECTED['missing_closing']['status']);self.assertIsNone(r['balance_totals'])
    def test_null_is_not_zero(self):
        _,b,t=self.fixture();self.change(b,t,'balances.json',lambda v:v['records'][0].update(amount=None));r=self.assess(b,t);self.assertEqual(r['status'],'blocked');self.assertCode(r,'BALANCE_VALUE_MISSING')
    def test_true_zero_balances(self):
        _,b,t=self.fixture();self.change(b,t,'balances.json',lambda v:[x.update(amount='0.00') for x in v['records']])
        for f in (b/'sources').glob('*.json'):
            v=read(f)
            for row in v['records']:row['amount']='0.00'
            write(f,v)
        self.source_approve(b,t);r=self.assess(b,t);self.assertEqual(r['status'],'ready');self.assertEqual(r['balance_totals']['opening'],EXPECTED['zero']['opening'])
    def test_negative_balance_preserved(self):
        _,b,t=self.fixture();self.change(b,t,'scope.json',lambda v:v['accounts'][1].update(included=False,exclusion_reason='excluded'))
        def change(v):
            for row in v['records']:
                if row['account_id']=='fixture-account-A':row['amount']='-100.00' if row['kind']=='opening' else '-50.00'
        self.change(b,t,'balances.json',change)
        f=b/'sources/statement-A.json';v=read(f);change(v);write(f,v);self.source_approve(b,t)
        r=self.assess(b,t);self.assertEqual(r['status'],'ready');self.assertEqual(r['balance_totals']['opening'],EXPECTED['negative']['opening']);self.assertEqual(r['balance_totals']['independent_closing'],EXPECTED['negative']['independent_closing'])
    def test_float_amount_rejected(self):
        _,b,t=self.fixture();self.change(b,t,'balances.json',lambda v:v['records'][0].update(amount=60000.0));self.assertCode(self.assess(b,t),'BALANCE_AMOUNT_INVALID')
    def test_exponent_amount_rejected(self):
        _,b,t=self.fixture();self.change(b,t,'balances.json',lambda v:v['records'][0].update(amount='6e4'));self.assertCode(self.assess(b,t),'BALANCE_AMOUNT_INVALID')
    def test_duplicate_balance(self):
        _,b,t=self.fixture()
        def mutate(v):row=copy.deepcopy(v['records'][0]);row['record_id']='new-id';v['records'].append(row)
        self.change(b,t,'balances.json',mutate);self.assertCode(self.assess(b,t),'DUPLICATE_ACCOUNT_BALANCE')
    def test_duplicate_record_id(self):
        _,b,t=self.fixture();self.change(b,t,'balances.json',lambda v:v['records'].append(v['records'][0]));self.assertCode(self.assess(b,t),'BALANCE_RECORD_ID_DUPLICATE_OR_INVALID')
    def test_unknown_account(self):
        _,b,t=self.fixture();self.change(b,t,'balances.json',lambda v:v['records'][0].update(account_id='not-registered'));self.assertCode(self.assess(b,t),'BALANCE_ACCOUNT_NOT_REGISTERED')
    def test_wrong_month_cutoff(self):
        _,b,t=self.fixture();self.change(b,t,'scope.json',lambda v:v.update(closing_as_of='2026-08-30'));self.assertCode(self.assess(b,t),'PERIOD_BALANCE_CUTOFF_MISMATCH')
    def test_wrong_balance_date(self):
        _,b,t=self.fixture();self.change(b,t,'balances.json',lambda v:v['records'][0].update(as_of='2026-08-01'));self.assertCode(self.assess(b,t),'BALANCE_DATE_MISMATCH')
    def test_wrong_unit(self):
        _,b,t=self.fixture();self.change(b,t,'balances.json',lambda v:v['records'][0].update(unit='万元'));self.assertCode(self.assess(b,t),'BALANCE_UNIT_INVALID')
    def test_missing_evidence_reference(self):
        _,b,t=self.fixture();self.change(b,t,'balances.json',lambda v:v['records'][0].update(evidence_id='missing'));self.assertCode(self.assess(b,t),'BALANCE_EVIDENCE_REFERENCE_MISSING')
    def test_computed_source_class_rejected(self):
        _,b,t=self.fixture();self.change(b,t,'evidence_manifest.json',lambda v:v['sources'][0].update(source_class='computed_cashflow'));self.assertCode(self.assess(b,t),'INDEPENDENT_SOURCE_CLASS_REQUIRED')
    def test_computed_derivation_rejected(self):
        _,b,t=self.fixture();f=b/'sources/statement-A.json';v=read(f);v['derivation']='opening_plus_net';write(f,v);self.source_approve(b,t);self.assertCode(self.assess(b,t),'COMPUTED_BALANCE_NOT_INDEPENDENT')
    def test_no_independent_registration(self):
        _,b,t=self.fixture();self.change(b,t,'evidence_manifest.json',lambda v:v['sources'][0].update(independence='self_claimed'));self.assertCode(self.assess(b,t),'INDEPENDENCE_APPROVAL_REQUIRED')
    def test_evidence_hash_tampered(self):
        _,b,t=self.fixture();f=b/'sources/statement-A.json';f.write_text('{}',encoding='utf-8');self.assertCode(self.assess(b,t),'EVIDENCE_HASH_MISMATCH')
    def test_amount_rehash_still_differs_from_source(self):
        _,b,t=self.fixture();self.change(b,t,'balances.json',lambda v:v['records'][0].update(amount='999999.00'));self.assertCode(self.assess(b,t),'BALANCE_SOURCE_VALUE_MISMATCH')
    def test_wrong_source_record_context(self):
        _,b,t=self.fixture();f=b/'sources/statement-A.json';v=read(f);v['tenant_id']='other';write(f,v);self.source_approve(b,t);self.assertCode(self.assess(b,t),'CONTEXT_MISMATCH')
    def test_source_path_escape(self):
        _,b,t=self.fixture();self.change(b,t,'evidence_manifest.json',lambda v:v['sources'][0].update(path='../outside.json'));self.assertCode(self.assess(b,t),'UNSAFE_SOURCE_PATH')
    def test_source_absolute_path(self):
        _,b,t=self.fixture();self.change(b,t,'evidence_manifest.json',lambda v:v['sources'][0].update(path='C:/outside.json'));self.assertCode(self.assess(b,t),'UNSAFE_SOURCE_PATH')
    def test_approval_hash_not_recomputed_by_tool(self):
        _,b,t=self.fixture();self.change(b,t,'scope.json',lambda v:v.update(scope_confirmed=False),reapprove=False);self.assertCode(self.assess(b,t),'INPUT_APPROVAL_HASH_MISMATCH')
    def test_source_location_missing(self):
        _,b,t=self.fixture();f=b/'sources/statement-A.json';v=read(f);v['records'][0]['source_location']='';write(f,v);self.source_approve(b,t);self.assertCode(self.assess(b,t),'SOURCE_LOCATION_MISSING')
    def test_duplicate_json_key(self):
        with self.assertRaises(a.BindingError):a.parse(b'{"x":1,"x":2}')
    def test_nonfinite_json(self):
        with self.assertRaises(a.BindingError):a.parse(b'{"x":NaN}')
    def test_file_size_limit(self):
        work,b,t=self.fixture();f=work/'oversize';f.write_bytes(b'x'*100)
        with self.assertRaises(a.BindingError):a.small_file(f,10)
    def test_aggregate_overflow(self):
        with self.assertRaises(a.BindingError):a.sum_money(['999999999999999999.99','0.01'])
    def test_leap_and_year_cutoffs(self):
        for period,pair in EXPECTED['cutoffs'].items():self.assertEqual(list(a.period_dates(period)),pair)
    def test_source_and_expected_preserved(self):
        _,b,t=self.fixture();before={p.relative_to(b).as_posix():digest(p) for p in b.rglob('*') if p.is_file()};expected=digest(ROOT/'expected/independent_values.json')
        self.assess(b,t);self.assertEqual(before,{p.relative_to(b).as_posix():digest(p) for p in b.rglob('*') if p.is_file()});self.assertEqual(expected,digest(ROOT/'expected/independent_values.json'))
    def test_binding_hash_stable(self):
        _,b,t=self.fixture();self.assertEqual(self.assess(b,t)['binding_sha256'],self.assess(b,t)['binding_sha256'])
    def test_detect_input_changed_during_check(self):
        _,b,t=self.fixture();original=a.small_file;calls={}
        def changed(path,limit=a.MAX_INPUT):
            key=str(path);calls[key]=calls.get(key,0)+1;raw=original(path,limit)
            return raw+b' ' if Path(path).name=='scope.json' and calls[key]>1 else raw
        with patch('account_binding.small_file',side_effect=changed):r=self.assess(b,t)
        self.assertCode(r,'INPUT_CHANGED_DURING_CHECK');self.assertIsNone(r['balance_totals'])
    def test_operator_registered_mode_does_not_claim_authenticity(self):
        _,b,t=self.fixture()
        for name in ['scope.json','balances.json','evidence_manifest.json']:
            self.change(b,t,name,lambda v:v.update(origin='operator_registered_evidence'))
        for f in (b/'sources').glob('*.json'):
            v=read(f);v['origin']='operator_registered_evidence';write(f,v)
        self.source_approve(b,t);r=a.assess(b,t);self.assertEqual(r['status'],'ready');self.assertFalse(r['source_authenticity_verified']);self.assertFalse(r['native_sheet_verified'])
    def test_cli_success_and_collision(self):
        work,b,t=self.fixture();out=work/'report'
        cmd=[sys.executable,'-B',str(ROOT/'src/binding_cli.py'),'check','--bundle',str(b),'--trust',str(t),'--output-dir',str(out),'--allow-fixture']
        p=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        before=digest(out/'binding_result.json');p=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(p.returncode,3);self.assertEqual(before,digest(out/'binding_result.json'))
    def test_cli_blocked_exit_nonzero(self):
        work,b,t=self.fixture();self.change(b,t,'scope.json',lambda v:v.update(scope_confirmed=False))
        p=subprocess.run([sys.executable,'-B',str(ROOT/'src/binding_cli.py'),'check','--bundle',str(b),'--trust',str(t),'--output-dir',str(work/'blocked'),'--allow-fixture'],capture_output=True,text=True)
        self.assertEqual(p.returncode,2);self.assertEqual(read(work/'blocked/binding_result.json')['status'],'blocked')

if __name__=='__main__':unittest.main(verbosity=2)
