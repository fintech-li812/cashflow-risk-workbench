from config import Config
from program_service import ProgramService
from program_engine import catalog, calculate_source, SOURCES
import workbench as legacy

def list_sources():
    out=legacy.list_sources()
    out['sources']+=catalog()
    return out

def inspect_source(source_id='manufacturing_sample_v1'):
    if source_id not in SOURCES:return legacy.inspect_source(source_id)
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
    out=legacy.readiness(source_id)
    out['issues']=[i for i in out['issues'] if i['code']!='native_recalculation_not_bound']
    out['issues'].append({'code':'program_input_mapping_not_bound',
        'detail':'旧8表样例仍未绑定程序计算的全口径映射；禁止自动修正、补零或套用合成结果。'})
    out['note']='程序计算已获用户批准；本源的单位、重复、账户及余额来源问题仍需解决。'
    out['native_sheet_required']=False
    return out

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
    return out
