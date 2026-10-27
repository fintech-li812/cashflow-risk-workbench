from pathlib import Path
import copy,json,hashlib,tempfile,shutil,sys,unittest,subprocess
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import cash_selection as c
FIX=ROOT/'fixtures';EXP=json.loads((ROOT/'expected/independent_values.json').read_text(encoding='utf-8'))
WORK=Path(tempfile.mkdtemp(prefix='selection_tests_',dir=ROOT/'evidence'))
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class SelectionTests(unittest.TestCase):
    def fixture(self):
        work=Path(tempfile.mkdtemp(prefix='case_',dir=WORK));bundle=work/'bundle';shutil.copytree(FIX/'complete_bundle',bundle);trust=work/'trust.json';shutil.copyfile(FIX/'trusted_selection.json',trust);return work,bundle,trust
    def approve(self,b,t):
        v=read(t);v['approved_inputs']={name:digest(b/name) for name in c.FILES};write(t,v)
    def change(self,b,t,file,fn):
        v=read(b/file);fn(v);write(b/file,v);self.approve(b,t)
    def event(self,b,t,rid,fn):
        self.change(b,t,'events.json',lambda v:fn(next(x for x in v['records'] if x['record_id']==rid)))
    def plan(self,b,t):return c.plan(b,t,allow_fixture=True)
    def code(self,r,code):self.assertIn(code,[x['code'] for x in r['issues']])
    def add_duplicate(self,b,t):
        def duplicate(v):
            row=copy.deepcopy(v['records'][0]);row['record_id']='duplicate-sale';row['source_record_key']=hashlib.sha256(b'duplicate-row').hexdigest();v['records'].append(row)
        self.change(b,t,'events.json',duplicate)
    def test_complete(self):
        _,b,t=self.fixture();r=self.plan(b,t);self.assertEqual(r['status'],EXP['complete']['status']);self.assertEqual([x['record_id'] for x in r['selected_records']],EXP['complete']['selected_ids'])
        for key in ['input_records','selected_actual_records','eliminated_transfer_records','corroborating_only_records','noncash_records']:self.assertEqual(r['counts'][key],EXP['complete'][key])
        self.assertIsNone(r['cashflow_totals']);self.assertFalse(r['can_save_source_result']);self.assertFalse(r['can_claim_full_cashflow'])
    def test_partial_receipt_invoice_is_not_amount_error(self):
        _,b,t=self.fixture();r=self.plan(b,t);self.assertEqual(r['status'],'ready');invoice=next(x for x in r['record_decisions'] if x['record_id']=='invoice');self.assertEqual(invoice['action'],'noncash_excluded');self.assertEqual(invoice['linked_primary_records'],['bank-sale'])
    def test_bank_and_business_cash_counted_once(self):
        _,b,t=self.fixture();r=self.plan(b,t);ids=[x['record_id'] for x in r['selected_records']];self.assertIn('bank-sale',ids);self.assertNotIn('business-sale',ids)
    def test_depreciation_and_credit_limit_not_cash(self):
        _,b,t=self.fixture();r=self.plan(b,t);self.assertFalse({'depreciation','unused-credit'}&{x['record_id'] for x in r['selected_records']})
    def test_transfer_raw_records_preserved(self):
        _,b,t=self.fixture();r=self.plan(b,t);self.assertEqual(len(r['record_decisions']),9);self.assertEqual(len(r['approved_transfer_pairs']),1)
    def test_transfer_pair_no_classification_needed(self):
        _,b,t=self.fixture();r=self.plan(b,t);self.assertEqual(r['status'],'ready')
    def test_missing_transfer_approval_blocks(self):
        _,b,t=self.fixture();self.change(b,t,'decisions.json',lambda v:v.update(transfers=[]));r=self.plan(b,t);self.assertEqual(r['status'],'blocked');self.code(r,'INTERNAL_TRANSFER_NOT_PAIRED')
    def test_transfer_amount_mismatch_not_net_zero(self):
        _,b,t=self.fixture();self.event(b,t,'transfer-in',lambda x:x.update(amount='199.99'));r=self.plan(b,t);self.assertEqual(r['status'],'blocked');self.code(r,'TRANSFER_PAIR_NOT_MATCHED');self.assertEqual(r['approved_transfer_pairs'],[])
    def test_transfer_account_same_blocked(self):
        _,b,t=self.fixture();self.event(b,t,'transfer-in',lambda x:x.update(account_id='fixture-account-A',source_id='bank-A'));r=self.plan(b,t);self.code(r,'TRANSFER_PAIR_NOT_MATCHED')
    def test_cross_day_transfer_requires_manual_resolution(self):
        _,b,t=self.fixture();self.event(b,t,'transfer-in',lambda x:x.update(settlement_date='2026-08-16'));self.code(self.plan(b,t),'TRANSFER_PAIR_NOT_MATCHED')
    def test_transfer_reused_rejected(self):
        _,b,t=self.fixture()
        def duplicate(v):row=copy.deepcopy(v['transfers'][0]);row['pair_id']='PAIR-OTHER';v['transfers'].append(row)
        self.change(b,t,'decisions.json',duplicate);self.code(self.plan(b,t),'TRANSFER_RECORD_REUSED')
    def test_missing_transfer_reference(self):
        _,b,t=self.fixture();self.change(b,t,'decisions.json',lambda v:v['transfers'][0].update(evidence_ref=''));self.code(self.plan(b,t),'TRANSFER_APPROVAL_REQUIRED')
    def test_unresolved_duplicate_blocks_without_deleting(self):
        _,b,t=self.fixture();self.add_duplicate(b,t);r=self.plan(b,t);self.assertEqual(r['status'],'blocked');self.code(r,'UNRESOLVED_DUPLICATE_TRANSACTION');self.assertEqual(r['counts']['input_records'],10)
    def test_explicit_duplicate_retains_trace(self):
        _,b,t=self.fixture();self.add_duplicate(b,t);self.change(b,t,'decisions.json',lambda v:v['duplicates'].append({'keep_record_id':'bank-sale','duplicate_record_ids':['duplicate-sale'],'evidence_ref':'SYNTHETIC'}));r=self.plan(b,t);self.assertEqual(r['status'],'ready');self.assertEqual(r['counts']['approved_duplicate_records'],1);self.assertEqual(r['counts']['input_records'],10);self.assertEqual(r['counts']['selected_actual_records'],3)
    def test_not_identical_duplicate_refused(self):
        _,b,t=self.fixture();self.add_duplicate(b,t);self.event(b,t,'duplicate-sale',lambda x:x.update(amount='400.01'));self.change(b,t,'decisions.json',lambda v:v['duplicates'].append({'keep_record_id':'bank-sale','duplicate_record_ids':['duplicate-sale'],'evidence_ref':'SYNTHETIC'}));self.code(self.plan(b,t),'DUPLICATE_RECORDS_NOT_IDENTICAL')
    def test_same_amount_different_transactions_not_deduplicated(self):
        _,b,t=self.fixture();self.add_duplicate(b,t);self.event(b,t,'duplicate-sale',lambda x:x.update(transaction_id='LEGIT-OTHER'));r=self.plan(b,t);self.assertEqual(r['status'],'ready');self.assertEqual(r['counts']['selected_actual_records'],4)
    def test_double_primary_source_blocks(self):
        _,b,t=self.fixture();self.change(b,t,'source_registry.json',lambda v:v['sources'].append({'source_id':'other-primary','role':'primary_actual','account_ids':['fixture-account-A'],'period':'2026-08','complete':True,'declared_zero':True}));self.code(self.plan(b,t),'PRIMARY_SOURCE_AMBIGUOUS')
    def test_no_primary_source_blocks(self):
        _,b,t=self.fixture();self.change(b,t,'source_registry.json',lambda v:v['sources'][0].update(role='corroborating'));self.change(b,t,'decisions.json',lambda v:v.update(links=[],transfers=[]));r=self.plan(b,t);self.code(r,'PRIMARY_SOURCE_MISSING')
    def test_incomplete_primary_blocks(self):
        _,b,t=self.fixture();self.change(b,t,'source_registry.json',lambda v:v['sources'][0].update(complete=False));self.code(self.plan(b,t),'PRIMARY_SOURCE_INCOMPLETE')
    def test_empty_feed_not_assumed_zero(self):
        _,b,t=self.fixture();self.change(b,t,'events.json',lambda v:v.update(records=[x for x in v['records'] if x['source_id']!='bank-B']));self.change(b,t,'decisions.json',lambda v:v.update(transfers=[]));self.code(self.plan(b,t),'EMPTY_PRIMARY_NOT_CONFIRMED_ZERO')
    def test_zero_declaration_contradiction(self):
        _,b,t=self.fixture();self.change(b,t,'source_registry.json',lambda v:v['sources'][0].update(declared_zero=True));self.code(self.plan(b,t),'ZERO_DECLARATION_CONTRADICTS_RECORDS')
    def test_unknown_category_blocks(self):
        _,b,t=self.fixture();self.event(b,t,'bank-loan',lambda x:x.update(category='interest_unknown'));self.code(self.plan(b,t),'CASH_CATEGORY_UNCONFIRMED')
    def test_negative_net_not_computed_or_hidden(self):
        _,b,t=self.fixture();self.event(b,t,'bank-expense',lambda x:x.update(amount='99999.99'));r=self.plan(b,t);self.assertEqual(r['status'],'ready');self.assertIn('99999.99',[x['amount'] for x in r['selected_records']])
    def test_negative_gross_amount_rejected(self):
        _,b,t=self.fixture();self.event(b,t,'bank-expense',lambda x:x.update(amount='-1.00'));self.code(self.plan(b,t),'GROSS_CASH_NEGATIVE')
    def test_float_amount_rejected(self):
        _,b,t=self.fixture();self.event(b,t,'bank-loan',lambda x:x.update(amount=1000.0));self.code(self.plan(b,t),'BALANCE_AMOUNT_INVALID')
    def test_wrong_unit(self):
        _,b,t=self.fixture();self.event(b,t,'bank-loan',lambda x:x.update(unit='万元'));self.code(self.plan(b,t),'CASH_UNIT_INVALID')
    def test_bad_date(self):
        _,b,t=self.fixture();self.event(b,t,'bank-loan',lambda x:x.update(settlement_date='2026-02-30'));self.code(self.plan(b,t),'CASH_DATE_INVALID')
    def test_other_period_cash(self):
        _,b,t=self.fixture();self.event(b,t,'bank-loan',lambda x:x.update(settlement_date='2026-09-01'));self.code(self.plan(b,t),'CASH_DATE_OUT_OF_PERIOD')
    def test_unknown_account(self):
        _,b,t=self.fixture();self.event(b,t,'bank-loan',lambda x:x.update(account_id='outside'));self.code(self.plan(b,t),'EVENT_ACCOUNT_OUT_OF_SCOPE')
    def test_unregistered_source(self):
        _,b,t=self.fixture();self.event(b,t,'bank-loan',lambda x:x.update(source_id='outside'));self.code(self.plan(b,t),'EVENT_SOURCE_NOT_REGISTERED')
    def test_duplicate_record_id(self):
        _,b,t=self.fixture();self.change(b,t,'events.json',lambda v:v['records'].append(v['records'][0]));self.code(self.plan(b,t),'EVENT_RECORD_ID_DUPLICATE_OR_INVALID')
    def test_duplicate_source_key_same_fact(self):
        _,b,t=self.fixture();self.add_duplicate(b,t);key=read(b/'events.json')['records'][0]['source_record_key'];self.event(b,t,'duplicate-sale',lambda x:x.update(source_record_key=key));self.code(self.plan(b,t),'SOURCE_RECORD_KEY_DUPLICATED')
    def test_invoice_and_receipt_can_share_original_row_key(self):
        _,b,t=self.fixture();events=read(b/'events.json');key=next(x for x in events['records'] if x['record_id']=='business-sale')['source_record_key'];self.event(b,t,'invoice',lambda x:x.update(source_record_key=key));self.assertEqual(self.plan(b,t)['status'],'ready')
    def test_cash_corroboration_mismatch(self):
        _,b,t=self.fixture();self.event(b,t,'business-sale',lambda x:x.update(amount='400.01'));self.code(self.plan(b,t),'TRANSACTION_LINK_VALUE_MISMATCH')
    def test_document_link_never_requires_invoice_equal_receipt(self):
        _,b,t=self.fixture();self.event(b,t,'invoice',lambda x:x.update(amount='100000000.00'));self.assertEqual(self.plan(b,t)['status'],'ready')
    def test_invoice_not_cash_identity_link(self):
        _,b,t=self.fixture();self.change(b,t,'decisions.json',lambda v:v['links'][1].update(link_type='transaction_evidence'));self.code(self.plan(b,t),'TRANSACTION_LINK_REUSED_OR_NONCASH')
    def test_link_missing_reference(self):
        _,b,t=self.fixture();self.change(b,t,'decisions.json',lambda v:v['links'][0].update(evidence_ref=''));self.code(self.plan(b,t),'LINK_APPROVAL_REQUIRED')
    def test_foreign_context(self):
        _,b,t=self.fixture();self.change(b,t,'events.json',lambda v:v.update(tenant_id='other'));self.code(self.plan(b,t),'CONTEXT_MISMATCH')
    def test_scope_not_ready(self):
        _,b,t=self.fixture();self.change(b,t,'scope_binding.json',lambda v:v.update(scope_ready=False));r=self.plan(b,t);self.assertEqual(r['status'],'blocked');self.code(r,'ACCOUNT_SCOPE_NOT_READY')
    def test_scope_count_inconsistent(self):
        _,b,t=self.fixture();self.change(b,t,'scope_binding.json',lambda v:v['scope_summary'].update(included_accounts=3));self.code(self.plan(b,t),'ACCOUNT_SCOPE_COUNT_MISMATCH')
    def test_scope_context_changed(self):
        _,b,t=self.fixture();self.change(b,t,'scope_binding.json',lambda v:v['context'].update(source_revision='other'));self.code(self.plan(b,t),'CONTEXT_MISMATCH')
    def test_default_fixture_rejected(self):
        _,b,t=self.fixture();self.code(c.plan(b,t),'FIXTURE_NOT_EXPLICITLY_ALLOWED')
    def test_external_trust_required(self):
        _,b,t=self.fixture();shutil.copyfile(t,b/'trust.json');self.code(self.plan(b,b/'trust.json'),'TRUST_MUST_BE_EXTERNAL')
    def test_input_hash_change_not_approved(self):
        _,b,t=self.fixture();f=b/'events.json';f.write_bytes(f.read_bytes()+b' ');self.code(self.plan(b,t),'INPUT_APPROVAL_HASH_MISMATCH')
    def test_read_change_detected(self):
        _,b,t=self.fixture();original=c.small_file;seen={}
        def mutate(p,limit=1_000_000):
            k=str(p);seen[k]=seen.get(k,0)+1;raw=original(p,limit)
            return raw+b' ' if Path(p).name=='events.json' and seen[k]>1 else raw
        with patch('cash_selection.small_file',side_effect=mutate):r=self.plan(b,t)
        self.code(r,'INPUT_CHANGED_DURING_SELECTION');self.assertEqual(r['selected_records'],[])
    def test_original_inputs_and_expected_unchanged(self):
        _,b,t=self.fixture();before={p.name:digest(p) for p in b.iterdir()};expected=digest(ROOT/'expected/independent_values.json');self.plan(b,t);self.assertEqual(before,{p.name:digest(p) for p in b.iterdir()});self.assertEqual(expected,digest(ROOT/'expected/independent_values.json'))
    def test_deterministic_plan_hash(self):
        _,b,t=self.fixture();self.assertEqual(self.plan(b,t)['selection_sha256'],self.plan(b,t)['selection_sha256'])
    def test_cli_success_and_collision(self):
        work,b,t=self.fixture();out=work/'output';cmd=[sys.executable,'-B',str(ROOT/'src/selection_cli.py'),'plan','--bundle',str(b),'--trust',str(t),'--output-dir',str(out),'--allow-fixture'];p=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stdout+p.stderr);h=digest(out/'selection.json');p=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(p.returncode,3);self.assertEqual(h,digest(out/'selection.json'))

if __name__=='__main__':unittest.main(verbosity=2)
