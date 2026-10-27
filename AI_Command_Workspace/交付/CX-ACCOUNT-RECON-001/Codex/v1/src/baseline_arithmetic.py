"""Controlled fixture arithmetic for v1 integration, not a platform formula adapter.
Only normalized CNY monthly totals, explicitly synthetic, no Excel import/forecast.
"""
import argparse,hashlib,json,sys
from pathlib import Path
from agent_guard import money,validate_result,CONTEXT
from finance_json import strict_result,canonical

VERSION='baseline-cashflow-arithmetic.v1'

def calculate(data,*,allow_fixture=False):
    if not allow_fixture or data.get('origin')!='offline_fixture':
        raise ValueError('only_explicit_fixture_calculation_here_use_qwen_for_production')
    if data.get('unit')!='CNY' or data.get('coverage')!='full_cashflow':
        raise ValueError('requires_normalized_yuan_full_coverage_input')
    opening=money(data['opening'])
    groups=data.get('cashflows')
    if not isinstance(groups,dict) or set(groups)!={'operating','investing','financing'}:
        raise ValueError('three_cashflow_groups_required')
    inflow=outflow=money('0.00')
    for group in groups.values():
        if not isinstance(group,dict) or set(group)!={'inflow','outflow'}:
            raise ValueError('explicit_gross_amounts_required')
        incoming,outgoing=money(group['inflow']),money(group['outflow'])
        if incoming<0 or outgoing<0:raise ValueError('gross_cashflows_must_be_nonnegative')
        inflow+=incoming;outflow+=outgoing
    net=inflow-outflow;closing=opening+net
    actual=None if data.get('actual_closing') is None else money(data['actual_closing'])
    result={k:data[k] for k in CONTEXT}
    result.update(schema_version='mfg-agent-result.v1',industry='manufacturing',status='success',
        origin='offline_fixture',unit='CNY',coverage='full_cashflow',calculation_version=VERSION,
        source=data['source'],issues=[],amounts={'opening':str(opening),'inflow':str(inflow),'outflow':str(outflow),
        'net':str(net),'closing':str(closing),'actual_closing':None if actual is None else str(actual),
        'difference':None if actual is None else str(actual-closing)})
    validate_result(result,{k:data[k] for k in CONTEXT},allow_fixture=True)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--allow-fixture',action='store_true');args=parser.parse_args()
    try:
        source=Path(args.input)
        if source.stat().st_size>500000:raise ValueError('input_too_large')
        result=calculate(strict_result(source.read_bytes()),allow_fixture=args.allow_fixture)
        with Path(args.output).open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
        print('calculated explicit synthetic result; not Qwen native; no database write')
        return 0
    except Exception as exc:
        print('calculation blocked: '+type(exc).__name__,file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
