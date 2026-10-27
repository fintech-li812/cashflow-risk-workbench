"""Offline proposal arithmetic only. Does not approve discounts or verify bank receipts."""
from decimal import Decimal
import json

def calculate(base_yuan,rate,days_advanced):
    base=Decimal(str(base_yuan));d=Decimal(str(rate))
    if not base.is_finite() or not d.is_finite():raise ValueError('non-finite input')
    if base<=0 or d<0 or d>=1:raise ValueError('invalid discount basis or rate')
    if not isinstance(days_advanced,int) or isinstance(days_advanced,bool):raise ValueError('days must be integer')
    discount=base*d;net=base-discount
    rounding_required=(discount!=discount.quantize(Decimal('.01')) or net!=net.quantize(Decimal('.01')))
    annual=None if days_advanced<=0 else d/(1-d)*Decimal(365)/Decimal(days_advanced)
    compound=None if days_advanced<=0 else (1/(1-d))**(Decimal(365)/Decimal(days_advanced))-1
    return {'synthetic_proposal':True,'basis_yuan':str(base),'discount_yuan':str(discount),'expected_net_yuan':str(net),'day_basis':365,'simple_annualized_cost':None if annual is None else str(annual),'compound_annualized_cost':None if compound is None else str(compound),'rounding_policy_required':rounding_required,'approved':False,'bank_verified':False,'recommended':None}

def selftest():
    r=calculate('1000000','0.02',20)
    assert Decimal(r['discount_yuan'])==20000 and Decimal(r['expected_net_yuan'])==980000
    assert abs(Decimal(r['simple_annualized_cost'])-Decimal('0.3724489795918367346938775510'))<Decimal('1e-24')
    import math
    assert abs(Decimal(r['compound_annualized_cost'])-Decimal(str(math.pow(1/.98,365/20)-1)))<Decimal('1e-12')
    assert not r['approved'] and not r['bank_verified'] and r['recommended'] is None
    assert calculate('100','0',20)['simple_annualized_cost']=='0'
    assert calculate('100','.02',0)['simple_annualized_cost'] is None
    assert calculate('100','.02',-2)['simple_annualized_cost'] is None
    assert calculate('0.01','.5',2)['rounding_policy_required']
    for base,rate,days in [('0','.02',20),('100','1',20),('100','-.01',20),('NaN','.02',20),('100','Infinity',20),('100','.02',True)]:
        try:calculate(base,rate,days)
        except ValueError:pass
        else:raise AssertionError('invalid input accepted')
    print(json.dumps({'status':'offline_arithmetic_checks_passed','base_case':r,'qwen_platform_tested':False,'real_contract_validated':False},ensure_ascii=False,indent=2))

if __name__=='__main__':selftest()
