from pathlib import Path
import hashlib,json,subprocess,shutil

candidate=Path(r'D:\AI_Command_Workspace\交付\MEM-QA-001\Codex\v1')
audit=Path(r'D:\AI_Command_Workspace\验收\MEM-QA-001\Codex\mutation_round1')
assert not audit.exists()
audit.mkdir(parents=True)
py=r'C:\Users\33847\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
original=(candidate/'qa_tool.py').read_text(encoding='utf-8')
tests=(candidate/'test_qa_tool.py').read_bytes()
mutations=[
('ignore_context',"obj[key] == context[key]",'True','test_each_context_dimension'),
('ignore_net',"amounts['inflow'] - amounts['outflow'] == amounts['net']",'True','test_one_cent_net_error'),
('ignore_closing',"amounts['opening'] + amounts['net'] == amounts['closing']",'True','test_closing_error'),
('ignore_difference',"actual - amounts['closing'] == diff",'True','test_difference_direction'),
('allow_fixture_in_production','allow_fixture is True','True','test_fixture_default_rejected'),
('ignore_receipt_hash',"receipt.get('payload_sha256') == digest(canonical(result))",'True','test_committed_receipt_wrong_payload'),
('ignore_receipt_request',"receipt.get('request_id') == expected_request",'True','test_receipt_other_request'),
('ignore_source_cell',"key in observed and observed[key] == actual[key]",'True','test_package_tamper_and_rehash_still_found'),
('ignore_unit_mapping',"rule.get('source_unit') == unit and rule.get('unit') == evidence.get('unit') and rule.get('transform') == 'yuan_half_up'",'True','test_package_unit_lie_rejected_by_mapping'),
('ignore_money_conversion',"cell['raw_type'] in ('n',) and not cell['formula_present'] and raw_amount.is_finite() and parsed == expected",'True','test_package_conversion_rounding_loses_precision'),
('accept_duplicate_json','if key in obj:','if False:','test_strict_json_duplicate_and_nonfinite'),
('ignore_package_hash',"entry.get('sha256') == digest(data)",'True','test_package_hash_tamper'),
('allow_invented_actual',"if context.get('actual_balance_provided') is False:",'if False:','test_fake_zero_actual_when_not_supplied'),
('ignore_replay_expected',"r.check(ok, 'REPLAY_EXPECTATION'","r.check(True, 'REPLAY_EXPECTATION'",'test_replay_cannot_turn_wrong_outcome_into_match'),
('ignore_reason_type',"isinstance(issues, list) and all(nonempty(x) for x in issues)",'True','test_non_success_reason_must_be_nonempty_text'),
]
results=[]
for name,old,new,test in mutations:
    assert old in original,name
    target=audit/name;target.mkdir()
    (target/'qa_tool.py').write_text(original.replace(old,new,1),encoding='utf-8')
    (target/'test_qa_tool.py').write_bytes(tests)
    run=subprocess.run([py,'-B','-m','unittest','-v','test_qa_tool.QA.'+test],cwd=target,capture_output=True,timeout=20)
    (target/'mutation-test-output.txt').write_bytes(run.stdout+run.stderr)
    results.append({'mutation':name,'target_test':test,'exit_code':run.returncode,'caught':run.returncode!=0,'stdout_sha256':hashlib.sha256(run.stdout+run.stderr).hexdigest()})
assert (candidate/'qa_tool.py').read_text(encoding='utf-8')==original
assert (candidate/'test_qa_tool.py').read_bytes()==tests
summary={'mutation_count':len(results),'caught':sum(x['caught'] for x in results),'survived':sum(not x['caught'] for x in results),'nature':'15 deliberately different mutations, sequential controlled negative tests; no production code changed','results':results}
(audit/'mutation-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True,indent=2))
if summary['survived']:raise SystemExit(1)
