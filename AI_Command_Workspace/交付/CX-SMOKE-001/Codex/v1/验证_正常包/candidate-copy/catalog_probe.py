"""Read-only compatibility audit of an explicitly supplied candidate catalog."""
import argparse
import hashlib
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from tool_call_guard import _schema_policy, strict_datetime, strict_load, Blocked

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--catalog',required=True)
    parser.add_argument('--output',required=True)
    a=parser.parse_args()
    p=Path(a.catalog)
    document=strict_load(p)
    checker=FormatChecker();checker.checks('date-time')(strict_datetime)
    rows=[]
    for tool in document['tools']:
        schema=tool.get('inputSchema')
        row={'tool_name':tool.get('name'),'schema_compatible':False,
             'real_platform_binding':False,'calls_performed':0}
        try:
            Draft202012Validator.check_schema(schema)
            _schema_policy(schema,checker)
            row.update(schema_compatible=True,top_required=schema.get('required',[]),
                       conditional_branches=len(schema.get('allOf',[])))
        except Exception as exc:
            row['reason']=str(exc) if isinstance(exc,Blocked) else type(exc).__name__
        rows.append(row)
    result={'source_file':str(p),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
            'source_status':'historical candidate, NOT authoritative tools/list',
            'meaning':'schema syntax/policy compatibility only; does NOT approve business capabilities or actual arguments',
            'tools':rows}
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'tools':len(rows),'schema_compatible':sum(r['schema_compatible'] for r in rows),
                      'platform_calls':0},ensure_ascii=False))

if __name__=='__main__':main()
