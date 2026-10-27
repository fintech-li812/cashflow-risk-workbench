"""Reuse existing QA persistence; approved result is recomputed, never Agent-authored."""
from service import Service, canonical, binding
from agent_guard import render_result
from program_engine import calculate_source

class ProgramService(Service):
    def read(self):
        out=calculate_source('program_demo_v1')
        self.validate(out['result'])
        out.update(status='ok',explanation=render_result(out['result'],binding(out['result']),allow_fixture=True))
        return out

    def save(self,result,request_id):
        if not isinstance(result,dict):raise ValueError('result_object_required')
        if result.get('origin')=='program_calculation' and result.get('reconciliation_state')!='matched':
            raise ValueError('independent_balance_difference_blocks_save')
        out=super().save(result,request_id)
        if out.get('result',{}).get('origin')=='program_calculation':out['fixture']=True
        return out

    def query(self,*args,**kwargs):
        out=super().query(*args,**kwargs)
        if out.get('result',{}).get('origin')=='program_calculation':out['fixture']=True
        return out
