"""Offline fixture per-account reconciliation. Native production formula execution is separate."""
from pathlib import Path
from decimal import Decimal,localcontext
import json
import account_binding as binding
from cash_selection import plan
from baseline_arithmetic import calculate

VERSION='mfg-per-account-reconciliation.v1'
def reconcile(account_bundle,account_trust,cash_bundle,cash_trust,*,allow_fixture=False):
    out={'schema_version':VERSION,'status':'invalid','context':None,'origin':'offline_fixture',
         'cashflow_result':None,'per_account':[],'account_binding':None,'selection':None,
         'reconciliation_state':'not_performed','issues':[],
         'can_save_source_result':False,'native_sheet_verified':False,'production_deployed':False}
    def fail(code,state='invalid'):
        out.update(status=state,cashflow_result=None,per_account=[],reconciliation_state='not_performed');out['issues'].append(code);return out
    try:
        if not allow_fixture:return fail('EXPLICIT_OFFLINE_FIXTURE_MODE_REQUIRED')
        account_trust_raw=binding.small_file(Path(account_trust))
        cash_trust_raw=binding.small_file(Path(cash_trust))
        bound=binding.assess(account_bundle,account_trust,allow_fixture=True)
        out['account_binding']=bound;out['context']=bound['context']
        if bound['status']!='ready':return fail('ACCOUNT_AND_BALANCE_BINDING_NOT_READY','blocked' if bound['status']=='blocked' else 'invalid')
        if not bound.get('fixture'):return fail('REAL_RESULTS_REQUIRE_QWEN_NATIVE_FORMULAS','blocked')
        chosen=plan(cash_bundle,cash_trust,allow_fixture=True);out['selection']=chosen
        if chosen['status']!='ready':return fail('CASH_SELECTION_NOT_READY','blocked' if chosen['status']=='blocked' else 'invalid')
        if not chosen.get('fixture'):return fail('REAL_RESULTS_REQUIRE_QWEN_NATIVE_FORMULAS','blocked')
        if chosen['context']!=bound['context']:return fail('CONTEXT_BETWEEN_MODULES_MISMATCH')
        snapshot=binding.parse(binding.small_file(Path(cash_bundle)/'scope_binding.json'))
        if snapshot!=bound:return fail('ACCOUNT_BINDING_SNAPSHOT_STALE')
        cash_raw=binding.small_file(Path(cash_bundle)/'events.json')
        binding.require(binding.sha(cash_raw)==binding.parse(cash_trust_raw)['approved_inputs']['events.json'],'CASH_APPROVED_HASH_CHANGED')
        cash_data=binding.parse(cash_raw)
        events={r['record_id']:r for r in cash_data['records']}
        scope_raw=binding.small_file(Path(account_bundle)/'scope.json')
        binding.require(binding.sha(scope_raw)==binding.parse(account_trust_raw)['approved_inputs']['scope.json'],'SCOPE_APPROVED_HASH_CHANGED')
        accounts={row['account_id']:row for row in bound['accounts']}
        movement={key:{'inflow':Decimal('0.00'),'outflow':Decimal('0.00'),'record_ids':[]} for key in accounts}
        with localcontext() as ctx:
            ctx.prec=40
            for action in chosen['record_decisions']:
                if action['action'] not in ('count_external_actual','eliminated_internal_transfer'):continue
                record=events[action['record_id']];bucket=movement[record['account_id']]
                field='inflow' if record['kind']=='cash_in' else 'outflow'
                bucket[field]+=binding.money(record['amount']);bucket['record_ids'].append(record['record_id'])
            for account_id,row in accounts.items():
                values=movement[account_id];opening=binding.money(row['opening']);actual=binding.money(row['independent_closing'])
                net=values['inflow']-values['outflow'];closing=opening+net;difference=actual-closing
                for amount in [values['inflow'],values['outflow'],net,closing,difference]:binding.money(format(amount,'.2f'))
                out['per_account'].append({'account_id':account_id,'opening':format(opening,'.2f'),'inflow':format(values['inflow'],'.2f'),'outflow':format(values['outflow'],'.2f'),'net':format(net,'.2f'),'calculated_closing':format(closing,'.2f'),'independent_closing':format(actual,'.2f'),'difference':format(difference,'.2f'),'record_ids':values['record_ids'],'internal_transfers_included_in_individual_account':True})
            groups={name:{'inflow':Decimal('0.00'),'outflow':Decimal('0.00')} for name in ['operating','investing','financing']}
            for record in chosen['selected_records']:
                groups[record['category']]['inflow' if record['kind']=='cash_in' else 'outflow']+=binding.money(record['amount'])
            groups={group:{k:format(value,'.2f') for k,value in totals.items()} for group,totals in groups.items()}
            normalized={**bound['context'],'origin':'offline_fixture','unit':'CNY','coverage':'full_cashflow','opening':bound['balance_totals']['opening'],'actual_closing':bound['balance_totals']['independent_closing'],'cashflows':groups,
                        'source':{'workbook_ref':'synthetic-account-evidence','sheet':'offline-normalized','range':'selected_records','snapshot_ref':binding.sha(binding.canonical({'binding':bound['binding_sha256'],'selection':chosen['selection_sha256']}))}}
            result=calculate(normalized,allow_fixture=True)
            total_net=sum((Decimal(row['net']) for row in out['per_account']),Decimal('0.00'))
            total_diff=sum((Decimal(row['difference']) for row in out['per_account']),Decimal('0.00'))
            binding.require(total_net==Decimal(result['amounts']['net']),'INDIVIDUAL_AND_CONSOLIDATED_NET_DISAGREE')
            binding.require(total_diff==Decimal(result['amounts']['difference']),'INDIVIDUAL_AND_CONSOLIDATED_DIFFERENCE_DISAGREE')
        binding.require(binding.small_file(Path(cash_bundle)/'events.json')==cash_raw,'CASH_INPUT_CHANGED_DURING_RECONCILIATION')
        binding.require(binding.small_file(Path(account_bundle)/'scope.json')==scope_raw,'SCOPE_CHANGED_DURING_RECONCILIATION')
        binding.require(binding.small_file(Path(account_trust))==account_trust_raw and binding.small_file(Path(cash_trust))==cash_trust_raw,'TRUST_CHANGED_DURING_RECONCILIATION')
        for root,traw in [(Path(account_bundle),account_trust_raw),(Path(cash_bundle),cash_trust_raw)]:
            for name,digest in binding.parse(traw)['approved_inputs'].items():binding.require(binding.sha(binding.small_file(binding.safe_file(root,name)))==digest,'APPROVED_INPUT_CHANGED_DURING_RECONCILIATION')
        for source in binding.parse(binding.small_file(Path(account_bundle)/'evidence_manifest.json'))['sources']:
            binding.require(binding.sha(binding.small_file(binding.safe_file(Path(account_bundle),source['path']),binding.MAX_SOURCE))==source['sha256'],'BALANCE_SOURCE_CHANGED_DURING_RECONCILIATION')
        out.update(status='ready',cashflow_result=result,normalized_fixture_input=normalized,
                   reconciliation_state='matched' if Decimal(result['amounts']['difference'])==0 else 'difference_pending_review',
                   invariants={'individual_and_consolidated_net_equal':True,'individual_and_consolidated_difference_equal':True},
                   original_records_preserved=True)
        return out
    except (binding.BindingError,ValueError,KeyError,TypeError,OSError,ArithmeticError):return fail('RECONCILIATION_INPUT_INVALID')
