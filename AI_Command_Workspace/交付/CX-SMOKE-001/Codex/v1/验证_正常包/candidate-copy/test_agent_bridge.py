"""Frozen Agent mapper vs new guard; synthetic descriptors, no tool calls."""
import copy
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'reference-agent'))
from runtime_adapter import Binding
from persistence import build_save_payload
from tool_call_guard import prepare, CONTEXT

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.context=dict(zip(CONTEXT,['fixture-t','fixture-c','2026-10','fixture-s','fixture-r']))
        self.binding=Binding(**self.context)
        self.result={'status':'success','unit':'CNY','amounts':{'inflow':'1.00'}}
        props={k:{'type':'string'} for k in CONTEXT}
        props.update(request_id={'type':'string'},status={'type':'string'},
                     unit={'type':'string'},amounts={'type':'object'})
        self.schema={'type':'object','required':list(props),'properties':props,'additionalProperties':False}
        self.config={'approved_name':'synthetic_agent_fixture','expected_context':self.context,
                     'context_paths':{k:'/'+k for k in CONTEXT},
                     'expected_request_id':'fixture-request','request_id_path':'/request_id'}
    def compare(self,expected):
        old=build_save_payload(self.binding,self.result,'fixture-request',self.schema)
        self.assertEqual(old.status,'ok',old)
        new=prepare({'name':'synthetic_agent_fixture','inputSchema':self.schema},old.payload,**self.config)
        self.assertEqual(new['status'],expected,new)
        self.assertFalse(new['called'])
        record={'case':self.id().split('.')[-1],'old_mapper_status':old.status,
                'new_guard_status':new['status'],'called':new['called'],'reason':new.get('reason','')}
        with (HERE/'test-output'/'bridge_observations.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(record,ensure_ascii=False)+'\n')
    def test_compatible_mapping(self):self.compare('prepared')
    def test_conditional_required_unmapped(self):
        self.schema['allOf']=[{'if':{'properties':{'status':{'const':'success'}}},
                                'then':{'required':['independent_confirmation']}}]
        self.compare('blocked')
    def test_unit_const(self):
        self.schema['properties']['unit']={'const':'USD'};self.compare('blocked')
    def test_request_pattern(self):
        self.schema['properties']['request_id']={'type':'string','pattern':'^APPROVED-'}
        self.compare('blocked')
    def test_nested_amount_type(self):
        self.schema['properties']['amounts']={'type':'object','properties':{'inflow':{'type':'number'}}}
        self.compare('blocked')
    def test_nested_amount_minimum(self):
        self.schema['properties']['amounts']={'type':'object','required':['closing']}
        self.compare('blocked')
    def test_enum_restriction(self):
        self.schema['properties']['status']={'enum':['missing_inputs']};self.compare('blocked')
    def test_schema_not_forbidden_unit(self):
        self.schema['not']={'properties':{'unit':{'const':'CNY'}}};self.compare('blocked')
    def test_oneof_ambiguous(self):
        self.schema['oneOf']=[{'required':['unit']},{'required':['status']}];self.compare('blocked')

if __name__=='__main__':unittest.main(verbosity=2)
