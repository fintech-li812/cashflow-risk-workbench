from config import Config
from program_service import ProgramService
from program_engine import catalog, calculate_source, SOURCES
import workbench as legacy
from source_audit import read_all,audit_source,account_binding_status,cash_selection_status

def list_sources():
    out=legacy.list_sources()
    out['sources']+=catalog()
    return out

def inspect_source(source_id='manufacturing_sample_v1'):
    if source_id not in SOURCES:return read_all(source_id)
    out=calculate_source(source_id)
    return {'status':'inspected','source_id':source_id,'data_type':'SYNTHETIC',
            'source_file_sha256':out['source_file_sha256'],'input_source':out['result']['source'],
            'source_modified':False,'native_qwen_workbook':False}

def readiness(source_id='manufacturing_sample_v1'):
    if source_id in SOURCES:
        out=calculate_source(source_id)
        return {'schema_version':'mfg-program-readiness.v1','status':'ready' if out['can_save_source_result'] else 'blocked',
            'source_id':source_id,'can_save_source_result':out['can_save_source_result'],
            'can_claim_full_cashflow':True,'gate_rules_executed':True,'fixture':True,
            'issues':out['result']['risk_flags'],'native_sheet_required':False,
            'evidence_assurance':'synthetic_declared_not_audited'}
    audit=audit_source(source_id);bound=account_binding_status(source_id);selection=cash_selection_status(source_id,bound)
    issues=list(audit['issues'])
    for item in bound.get('issues',[]):
        issues.append({'code':item['code'],'category':'missing_evidence',
            'detail':item.get('detail','账户或余额证据绑定未通过；详见account_binding诊断。')})
    for item in selection.get('issues',[]):
        issues.append({'code':item['code'],'category':'mapping_review',
                       'detail':item.get('detail','现金来源选择/内转防重计尚未通过。')})
    issues.append({'code':'full_cashflow_evidence_not_bound','category':'mapping_review',
        'detail':'已生成八表字段/现金性质映射预览；账户、来源主从、实际收付凭证及筹资期间明细未齐，不合计为完整现金流。'})
    return {'schema_version':'mfg-program-readiness.v1.1','status':'blocked','source_id':source_id,
        'source_kind':'controlled_sample','source_file_sha256':audit.get('source_file_sha256'),
        'can_claim_full_cashflow':False,'can_save_source_result':False,'issues':issues,
        'issue_groups':{key:[i for i in issues if i['category']==key] for key in ('data_error','data_review','missing_evidence','mapping_review')},
        'gate_rules_executed':audit['gate_rules_executed'],'full_data_gate_executed':False,
        'executed_checks':[c['code'] for c in audit['checks'] if c['status']=='executed'],
        'pending_checks':[c for c in audit['checks'] if c['status']!='executed']+audit.get('remaining_checks',[]),
        'normal_partial_receipts_treated_as_errors':False,'native_sheet_required':False,
        'account_binding':bound,'cash_selection':selection,'audit_tool':'get_manufacturing_data_audit',
        'note':'新报告来自实际逐项读取；仅已列检查执行，不声称完整历史闸或真实来源已验证；原件未改。'}

def calculate(source_id='program_demo_v1'):
    if source_id not in SOURCES:
        if source_id!=legacy.SOURCE_ID:raise ValueError('source_id_not_registered')
        return {'status':'blocked','result':None,'readiness':readiness(source_id),'database_written':False}
    return calculate_source(source_id)

def project_status():
    out=legacy.project_status()
    loaded=ProgramService(Config.from_env()).read()
    out.update(integration_version='workbench-program.v1',architecture='qwen_entry_program_calculation',
        native_sheet_required=False,financial_result_source_is_separate_from_inspected_workbook=True)
    out['components'].update(program_calculation='implemented_fixed_synthetic_template',
        native_sheet_recalculation='not_required_user_architecture_20261026',
        excel_import_package='fixed_template_implemented_general_import_pending',
        report_exporter='json_and_text_implemented_full_export_pending')
    out['result_profile']={k:loaded['result'][k] for k in ('origin','data_type','company_id','period','source_revision','run_id')}
    out['result_profile']['fixture']=True
    out['integration_version']='workbench-program.v1.1'
    out['components'].update(original_eight_sheet_inspection='implemented',
        original_source_data_audit='implemented_listed_checks_only',
        account_balance_binding='module_connected_evidence_not_registered',
        cashflow_source_mapping='preview_implemented_full_evidence_pending',
        cash_source_selection='module_connected_pending_account_evidence')
    return out
