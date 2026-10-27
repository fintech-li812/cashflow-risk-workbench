"""Deliberately break guard copies in memory; retain all observations."""
import contextlib
import importlib.metadata
import io
import json
from pathlib import Path
import sys
import types
import unittest
import test_tool_call_guard as cases

HERE=Path(__file__).resolve().parent
source=(HERE/'tool_call_guard.py').read_text(encoding='utf-8')
mutations=[
    ('skip_schema_validation','first = next(validator.iter_errors(arguments), None)','first = None',
     'test_all_of_conditional_required'),
    ('skip_tool_name','if descriptor.get(\'name\') != approved_name:', 'if False:',
     'test_tool_name_mismatch'),
    ('skip_context_comparison','if type(actual) is not str or actual != expected:', 'if False:',
     'test_every_context_field_compared'),
    ('skip_request_comparison','if type(actual_id) is not str or actual_id != expected_request_id:', 'if False:',
     'test_request_mismatch'),
    ('skip_reference_policy','        _schema_policy(schema, checker)','        pass  # mutant skips reference policy',
     'test_unused_external_ref_blocked'),
    ('skip_format_check','format_checker=checker, registry=', 'format_checker=None, registry=',
     'test_datetime_format'),
]
records=[]
original=cases.prepare
for name,old,new,test in mutations:
    assert source.count(old)==1,(name,'replacement not unique')
    module=types.ModuleType('mutation_'+name)
    exec(compile(source.replace(old,new),'mutation_'+name,'exec'),module.__dict__)
    cases.prepare=module.prepare
    sink=io.StringIO()
    result=unittest.TextTestRunner(stream=sink,verbosity=2).run(unittest.TestSuite([cases.GuardTests(test)]))
    records.append({'mutation':name,'selected_test':test,'caught':not result.wasSuccessful(),
                    'testsRun':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)})
    (HERE/'test-output'/('mutation_'+name+'.txt')).write_text(sink.getvalue(),encoding='utf-8')
cases.prepare=original
report={'mutations':records,'caught':sum(r['caught'] for r in records),'total':len(records),
        'runtime':sys.version,'packages':{name:importlib.metadata.version(name) for name in
                    ['jsonschema','referencing','attrs','rpds-py','jsonschema-specifications']}}
(HERE/'test-output'/'mutation_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
raise SystemExit(0 if all(r['caught'] and not r['errors'] for r in records) else 1)
