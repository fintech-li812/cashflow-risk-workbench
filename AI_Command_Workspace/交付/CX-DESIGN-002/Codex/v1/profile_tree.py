"""Offline, explainable onboarding draft. No credit scoring or financial calculation."""
import argparse,itertools,json,sys
from pathlib import Path

OPTIONS={
 'business':['产品制造','商品销售','工程项目','技术服务','其他'],
 'cost':['原材料','采购成本','人力成本','设备折旧','外包费用'],
 'collection':['即时','15天以内','15~60天','60天以上','按项目进度'],
 'funding':['自有资金','银行贷款','股权融资','政府补贴','预收款'],
 'seasonality':['没有','有']}
TEMPLATES={'产品制造':'制造业','商品销售':'零售业','工程项目':'建筑业','技术服务':'科技服务业'}
COMMON=['货币资金','经营活动现金流量净额','应收账款','短期借款','一年内到期的非流动负债']
EXTRA={'产品制造':['存货','应付账款'],'商品销售':['存货','合同负债'],'工程项目':['合同资产','合同负债'],'技术服务':['应付职工薪酬','研发支出']}

def initialize(data):
 source=data.get('source_kind')
 if source not in ('operating_records','listed_disclosure'):
  raise ValueError('source_kind must be operating_records or listed_disclosure')
 answers=data.get('answers',{})
 if not isinstance(answers,dict):raise ValueError('answers must be an object')
 unexpected=set(answers)-set(OPTIONS)
 if unexpected:raise ValueError('Unknown answer keys: '+','.join(sorted(unexpected)))
 missing=[]; trace=[]
 for key,options in OPTIONS.items():
  value=answers.get(key)
  if value is None or value=='':missing.append(key);continue
  if value not in options:raise ValueError(f'Invalid choice for {key}: {value}')
  trace.append({'question':key,'answer':value,'origin':'user-reported; not independently verified'})
 business=answers.get('business'); template=TEMPLATES.get(business)
 if template is None:missing.append('主营业务需人工确认，不能强行归入四行业')
 credit_customer=None if answers.get('collection') in (None,'') else answers['collection']!='即时'
 credit_borrower=None if answers.get('funding') in (None,'') else answers['funding']=='银行贷款'
 # This only selects what to inspect. It never produces a grade or empirical coefficient.
 return {
  'rule_version':'profile-tree-draft-v1','source_kind':source,'template_candidate':template,
  'status':'draft_requires_confirmation','trace':trace,'missing_or_confirmation':missing,
  'candidate_fields':COMMON+EXTRA.get(business,[]),
  'checks':{'customer_credit_review_priority':credit_customer,'borrower_credit_review_priority':credit_borrower,
            'seasonality_data_review':None if answers.get('seasonality') in (None,'') else answers['seasonality']=='有'},
  'numerical_initial_parameters':{'K_yellow':None,'K_red':None,'collection_probability':None,'financing_availability_factor':None},
  'credit_rating':None,'inspection_policy':{'requested':True,'runtime_configured':False,'sampling_rate':None,'timing_policy':None},
  'data_requirements':['逐笔流水、应收与还款计划须企业实际授权提供' if source=='operating_records' else '披露原件、页码/表名、公告日期、报告期、币种单位、合并/母公司口径；不推造逐笔或周度明细'],
  'ready_for_financial_risk_assessment':False,
  'limits':['不是训练得到的决策树，不输出准确率','推荐字段不是已取得数据，不等同已批准公式','未取得实际财务数据及批准参数，不输出风险灯或信用等级']}

def selftest():
 mapped=unmapped=0
 for combo in itertools.product(*OPTIONS.values()):
  answers=dict(zip(OPTIONS,combo))
  r=initialize({'source_kind':'operating_records','answers':answers})
  assert r==initialize({'source_kind':'operating_records','answers':answers})
  assert all(v is None for v in r['numerical_initial_parameters'].values())
  assert r['credit_rating'] is None and not r['ready_for_financial_risk_assessment']
  assert len(r['trace'])==5
  if answers['business']=='其他':assert r['template_candidate'] is None;unmapped+=1
  else:assert r['template_candidate']==TEMPLATES[answers['business']];mapped+=1
 assert mapped==1000 and unmapped==250
 assert len(initialize({'source_kind':'listed_disclosure','answers':{}})['missing_or_confirmation'])==6
 assert initialize({'source_kind':'listed_disclosure','answers':{'collection':'','funding':'','seasonality':''}})['checks']=={'customer_credit_review_priority':None,'borrower_credit_review_priority':None,'seasonality_data_review':None}
 for bad in [{'source_kind':'invented','answers':{}},{'source_kind':'listed_disclosure','answers':{'business':'随便猜'}},{'source_kind':'operating_records','answers':{'K_yellow':1.5}}]:
  try:initialize(bad)
  except ValueError:pass
  else:raise AssertionError('invalid input accepted')
 print(json.dumps({'enumerated_questionnaire_combinations':1250,'template_candidates':mapped,'manual_review':unmapped,'missing_data_and_three_invalid_inputs_checked':True,'real_companies_validated':0,'qwen_platform_tested':False},ensure_ascii=False,indent=2))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--input');parser.add_argument('--selftest',action='store_true');args=parser.parse_args()
 if args.selftest:selftest()
 elif args.input:
  try:print(json.dumps(initialize(json.loads(Path(args.input).read_text(encoding='utf-8-sig'))),ensure_ascii=False,indent=2))
  except (ValueError,OSError) as exc:print(str(exc),file=sys.stderr);sys.exit(2)
 else:parser.error('choose --selftest or --input')
