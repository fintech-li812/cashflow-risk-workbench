import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from tool_call_guard import prepare, strict_load, canonical, Blocked, CONTEXT

HERE=Path(__file__).resolve().parent
OUT=HERE/'test-output'
OUT.mkdir(exist_ok=True)


def fixture():
    context=dict(zip(CONTEXT, ['fixture-tenant','fixture-company','2026-10','fixture-revision','fixture-run']))
    arguments={'context':context.copy(),'request_id':'fixture-request',
               'event':'fixture-test','occurred_at':'2026-10-23T23:00:00+08:00',
               'payload':{'amount':'1.00'}}
    schema={'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object',
            'required':['context','request_id','event','occurred_at','payload'],
            'additionalProperties':False,
            'properties':{'context':{'type':'object','required':list(CONTEXT),
                                     'properties':{k:{'type':'string','minLength':1} for k in CONTEXT},
                                     'additionalProperties':False},
                          'request_id':{'type':'string','minLength':1},
                          'event':{'enum':['fixture-test','fixture-review']},
                          'occurred_at':{'type':'string','format':'date-time'},
                          'payload':{'$ref':'#/$defs/payload'},
                          'review_reason':{'type':'string','minLength':1}},
            '$defs':{'payload':{'type':'object','required':['amount'],
                               'properties':{'amount':{'type':'string','pattern':r'^\d+\.\d{2}$'}},
                               'additionalProperties':False}},
            'allOf':[{'if':{'properties':{'event':{'const':'fixture-review'}}},
                      'then':{'required':['review_reason']}}]}
    descriptor={'name':'synthetic_fixture_save','inputSchema':schema}
    binding={'approved_name':'synthetic_fixture_save','expected_context':context,
             'context_paths':{k:'/context/'+k for k in CONTEXT},
             'expected_request_id':'fixture-request','request_id_path':'/request_id'}
    return descriptor,arguments,binding


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.d,self.a,self.b=fixture()
    def run_guard(self):
        return prepare(self.d,self.a,**self.b)
    def assertBlocked(self,reason=None):
        r=self.run_guard()
        self.assertEqual(r['status'],'blocked',r)
        self.assertFalse(r['called'])
        self.assertNotIn('call',r)
        if reason:
            self.assertIn(reason,r['reason'])
        return r
    def test_valid_local_ref(self):
        r=self.run_guard(); self.assertEqual(r['status'],'prepared',r)
        self.assertFalse(r['called']); self.assertEqual(len(r['call_sha256']),64)
    def test_prepared_cannot_alias_input(self):
        r=self.run_guard(); self.a['payload']['amount']='2.00'
        self.assertEqual(r['call']['arguments']['payload']['amount'],'1.00')
    def test_digest_changes_for_business_payload(self):
        first=self.run_guard()['call_sha256']; self.a['payload']['amount']='2.00'
        self.assertNotEqual(first,self.run_guard()['call_sha256'])
    def test_digest_ignores_object_key_order(self):
        first=self.run_guard()['call_sha256']; self.a=dict(reversed(list(self.a.items())))
        self.assertEqual(first,self.run_guard()['call_sha256'])
    def test_all_of_conditional_required(self):
        self.a['event']='fixture-review'; self.assertBlocked('required')
    def test_all_of_condition_complete(self):
        self.a.update(event='fixture-review',review_reason='fixture-only')
        self.assertEqual(self.run_guard()['status'],'prepared')
    def test_unknown_top_level_argument(self):
        self.a['surprise']=True; self.assertBlocked('additionalProperties')
    def test_nested_extra_argument(self):
        self.a['payload']['surprise']=True; self.assertBlocked('additionalProperties')
    def test_nested_required(self):
        self.a['payload']={}; self.assertBlocked('required')
    def test_nested_type(self):
        self.a['payload']['amount']=1; self.assertBlocked('type')
    def test_nested_pattern(self):
        self.a['payload']['amount']='1.000'; self.assertBlocked('pattern')
    def test_enum(self):
        self.a['event']='unapproved'; self.assertBlocked('enum')
    def test_datetime_format(self):
        self.a['occurred_at']='2026-13-05'; self.assertBlocked('format')
    def test_datetime_timezone_required(self):
        self.a['occurred_at']='2026-10-23T23:00:00'; self.assertBlocked('format')
    def test_datetime_invalid_calendar(self):
        self.a['occurred_at']='2026-02-30T23:00:00Z';self.assertBlocked('format')
    def test_datetime_leap_second_requires_review(self):
        self.a['occurred_at']='2016-12-31T23:59:60Z';self.assertBlocked('format')
    def test_datetime_lowercase_and_fraction(self):
        self.a['occurred_at']='2026-10-23t23:00:00.123z'
        self.assertEqual(self.run_guard()['status'],'prepared')
    def test_datetime_offset_minutes_not_normalized(self):
        self.a['occurred_at']='2026-10-23T23:00:00+00:60';self.assertBlocked('format')
    def test_datetime_offset_hours_invalid(self):
        self.a['occurred_at']='2026-10-23T23:00:00+24:00';self.assertBlocked('format')
    def test_unknown_format_is_blocked(self):
        self.d['inputSchema']['properties']['occurred_at']['format']='my-made-up-format'
        self.assertBlocked('schema_format_unsupported')
    def test_no_network_external_ref(self):
        self.d['inputSchema']['$defs']['payload']={'$ref':'https://example.invalid/schema'}
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            self.assertBlocked('external_reference_forbidden')
    def test_unused_external_ref_blocked(self):
        self.d['inputSchema']['$defs']['unused']={'$dynamicRef':'file:///not-allowed'}
        self.assertBlocked('external_reference_forbidden')
    def test_const_object_ref_is_data(self):
        self.d['inputSchema']['properties']['payload']={'const':{'$ref':'https://data-only.invalid'}}
        self.a['payload']={'$ref':'https://data-only.invalid'}
        self.assertEqual(self.run_guard()['status'],'prepared')
    def test_missing_local_ref_fails_closed(self):
        self.d['inputSchema']['properties']['payload']={'$ref':'#/$defs/absent'}
        self.assertBlocked('validation_error')
    def test_dialect_unsupported(self):
        self.d['inputSchema']['$schema']='https://example.invalid/draft-future'
        self.assertBlocked('schema_dialect_unsupported')
    def test_no_schema_dialect_explicit_default(self):
        del self.d['inputSchema']['$schema']
        self.assertIn('2020-12',self.run_guard()['schema_dialect'])
    def test_draft7(self):
        s=self.d['inputSchema'];s['$schema']='http://json-schema.org/draft-07/schema#'
        s['definitions']=s.pop('$defs');s['properties']['payload']['$ref']='#/definitions/payload'
        self.assertEqual(self.run_guard()['status'],'prepared')
    def test_vocabulary_not_silently_ignored(self):
        self.d['inputSchema']['$vocabulary']={'https://example.invalid/vocab':True}
        self.assertBlocked('schema_vocabulary_requires_review')
    def test_schema_invalid(self):
        self.d['inputSchema']['required']=42; self.assertBlocked('validation_error')
    def test_nonobject_schema(self):
        self.d['inputSchema']=True; self.assertBlocked('object_input_schema_required')
    def test_tool_name_mismatch(self):
        self.d['name']='other'; self.assertBlocked('tool_name_mismatch')
    def test_blank_approved_tool(self):
        self.b['approved_name']=' '; self.assertBlocked('approved_tool_missing')
    def test_every_context_field_compared(self):
        for k in CONTEXT:
            with self.subTest(field=k):
                original=self.a['context'][k];self.a['context'][k]='wrong'
                self.assertBlocked('context_mismatch:'+k);self.a['context'][k]=original
    def test_context_mapping_incomplete(self):
        del self.b['context_paths']['company_id'];self.assertBlocked('context_mapping_incomplete')
    def test_context_extra(self):
        self.b['expected_context']['extra']='x';self.assertBlocked('context_contract_invalid')
    def test_missing_context_path(self):
        self.b['context_paths']['company_id']='/context/absent';self.assertBlocked('binding_path_missing')
    def test_aliased_binding_paths(self):
        self.b['context_paths']['company_id']='/context/tenant_id'
        self.assertBlocked('binding_paths_not_distinct')
    def test_empty_context(self):
        self.b['expected_context']['company_id']=' ';self.assertBlocked('context_value_invalid')
    def test_bad_period(self):
        self.b['expected_context']['period']=self.a['context']['period']='2026-13'
        self.assertBlocked('period_invalid')
    def test_year_zero(self):
        self.b['expected_context']['period']=self.a['context']['period']='0000-10'
        self.assertBlocked('period_invalid')
    def test_request_mismatch(self):
        self.a['request_id']='old-request';self.assertBlocked('request_id_mismatch')
    def test_empty_request(self):
        self.b['expected_request_id']=' ';self.assertBlocked('request_id_invalid')
    def test_invalid_pointer_escape(self):
        self.b['request_id_path']='/request~9id';self.assertBlocked('binding_pointer_invalid')
    def test_non_json_key(self):
        self.a[3]='hidden';self.assertBlocked('non_json_value')
    def test_nonfinite(self):
        for v in (float('nan'),float('inf'),float('-inf')):
            self.a['payload']['amount']=v;self.assertBlocked('nonfinite_number')
    def test_resource_depth(self):
        x={};self.a['payload']=x
        for _ in range(70):
            x['nested']={};x=x['nested']
        self.assertBlocked('json_resource_limit')
    def test_resource_bytes(self):
        self.a['payload']['amount']='x'*1_000_001;self.assertBlocked('json_byte_limit')
    def test_error_redaction(self):
        secret='fixture-secret-never-real'
        self.a['payload']['amount']=secret
        self.assertNotIn(secret,json.dumps(self.assertBlocked('pattern')))
    def test_duplicate_json_key(self):
        p=OUT/'duplicate.json';p.write_text('{"x":1,"x":2}',encoding='utf-8')
        with self.assertRaisesRegex(Blocked,'duplicate_json_key'):strict_load(p)
    def test_exponent_overflow(self):
        p=OUT/'overflow.json';p.write_text('{"x":1e999}',encoding='utf-8')
        with self.assertRaisesRegex(Blocked,'nonfinite_number'):strict_load(p)
    def test_dependency_missing_fails_closed(self):
        import builtins
        real=builtins.__import__
        def importer(name,*args,**kwargs):
            if name=='jsonschema':raise ImportError('fixture missing')
            return real(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=importer):
            self.assertBlocked('validation_dependency_unavailable')
    def test_cli_prepared_and_blocked_exit_codes(self):
        for name,obj in [('descriptor',self.d),('arguments',self.a),('binding',self.b)]:
            (OUT/(name+'.json')).write_text(json.dumps(obj),encoding='utf-8')
        cmd=[sys.executable,str(HERE/'tool_call_guard.py'),'--descriptor',str(OUT/'descriptor.json'),
             '--arguments',str(OUT/'arguments.json'),'--binding',str(OUT/'binding.json')]
        first=subprocess.run(cmd,capture_output=True,text=True)
        (OUT/'cli_prepared.txt').write_text(first.stdout+first.stderr,encoding='utf-8')
        self.assertEqual(first.returncode,0,first.stdout+first.stderr)
        self.assertNotIn('fixture-company',first.stdout)
        self.a['event']='fixture-review'
        (OUT/'arguments.json').write_text(json.dumps(self.a),encoding='utf-8')
        second=subprocess.run(cmd,capture_output=True,text=True)
        (OUT/'cli_blocked.txt').write_text(second.stdout+second.stderr,encoding='utf-8')
        self.assertEqual(second.returncode,2,second.stdout+second.stderr)
        self.assertEqual(json.loads(second.stdout)['status'],'blocked')


if __name__=='__main__':unittest.main(verbosity=2)
