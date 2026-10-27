"""Offline pre-call guard. No transport, authentication or persistence capability."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import datetime
import re
from pathlib import Path
from typing import Any

CONTEXT = ('tenant_id', 'company_id', 'period', 'source_revision', 'run_id')
DIALECTS = {'https://json-schema.org/draft/2020-12/schema',
            'http://json-schema.org/draft-07/schema#'}
LIMIT = 1_000_000


def strict_datetime(value):
    """RFC3339 ordinary seconds; leap seconds conservatively require review."""
    if not isinstance(value, str):
        return True  # JSON Schema format applies only to strings.
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:[0-5]\d(?:\.\d+)?(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)',value,re.ASCII) is None:
        return False
    try:
        datetime.datetime.fromisoformat(value.upper().replace('Z','+00:00'))
        return True
    except ValueError:
        return False


class Blocked(ValueError):
    pass


def canonical(value: Any) -> bytes:
    """Reject non-JSON types, non-string keys and non-finite values before encoding."""
    count = 0
    def walk(x, depth=0):
        nonlocal count
        count += 1
        if depth > 64 or count > 50000:
            raise Blocked('json_resource_limit')
        if x is None or type(x) in (bool, int, str):
            return
        if type(x) is float:
            if not math.isfinite(x):
                raise Blocked('nonfinite_number')
            return
        if type(x) is list:
            for item in x:
                walk(item, depth+1)
            return
        if type(x) is dict and all(type(k) is str for k in x):
            for item in x.values():
                walk(item, depth+1)
            return
        raise Blocked('non_json_value')
    walk(value)
    data = json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(data) > LIMIT:
        raise Blocked('json_byte_limit')
    return data


def strict_load(path: str | Path):
    p = Path(path)
    if p.stat().st_size > LIMIT:
        raise Blocked('json_byte_limit')
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise Blocked('duplicate_json_key')
            result[k] = v
        return result
    def constant(_):
        raise Blocked('nonfinite_number')
    value = json.loads(p.read_text(encoding='utf-8-sig'), object_pairs_hook=pairs,
                       parse_constant=constant)
    canonical(value)
    return value


def pointer(value, path):
    if not isinstance(path, str) or not path.startswith('/'):
        raise Blocked('binding_pointer_invalid')
    for token in path[1:].split('/'):
        # Reject malformed escaping instead of silently treating it as another key.
        import re
        if re.search(r'~(?![01])', token):
            raise Blocked('binding_pointer_invalid')
        key = token.replace('~1', '/').replace('~0', '~')
        if type(value) is not dict or key not in value:
            raise Blocked('binding_path_missing')
        value = value[key]
    return value


def _schema_policy(schema, checker):
    """Walk schema positions only; data under const/examples is not executable schema."""
    maps = {'properties', 'patternProperties', '$defs', 'definitions', 'dependentSchemas'}
    singles = {'additionalProperties', 'unevaluatedProperties', 'propertyNames', 'contains',
               'additionalItems', 'unevaluatedItems', 'not', 'if', 'then', 'else', 'contentSchema'}
    arrays = {'allOf', 'anyOf', 'oneOf', 'prefixItems'}
    def visit(s):
        if type(s) is bool:
            return
        if type(s) is not dict:
            raise Blocked('schema_invalid')
        if '$schema' in s and s['$schema'] not in DIALECTS:
            raise Blocked('schema_dialect_unsupported')
        if '$vocabulary' in s:
            raise Blocked('schema_vocabulary_requires_review')
        for key in ('$ref', '$dynamicRef', '$recursiveRef'):
            if key in s and (not isinstance(s[key], str) or not s[key].startswith('#')):
                raise Blocked('external_reference_forbidden')
        if '$recursiveRef' in s or '$recursiveAnchor' in s:
            raise Blocked('schema_keyword_unsupported')
        if 'format' in s and s['format'] not in checker.checkers:
            raise Blocked('schema_format_unsupported')
        for key in maps:
            if isinstance(s.get(key), dict):
                for child in s[key].values():
                    visit(child)
        for key in singles:
            if key in s:
                visit(s[key])
        for key in arrays:
            for child in s.get(key, []):
                visit(child)
        if 'items' in s:
            children = s['items'] if isinstance(s['items'], list) else [s['items']]
            for child in children:
                visit(child)
        # Draft7 dependencies can be either a schema or an array of property names.
        for child in s.get('dependencies', {}).values():
            if type(child) is not list:
                visit(child)
    visit(schema)


def prepare(descriptor, arguments, *, approved_name, expected_context,
            context_paths, expected_request_id, request_id_path):
    """Validate supplied arguments against a supplied descriptor; never call a tool.

    prepared is a LOCAL status, not an Agent status, DB receipt or release decision.
    expected_context and pointer mappings must be supplied by the trusted caller.
    """
    try:
        canonical(descriptor)
        canonical(arguments)
        canonical(expected_context)
        canonical(context_paths)
        if type(descriptor) is not dict or type(arguments) is not dict:
            raise Blocked('tool_or_arguments_not_object')
        if type(approved_name) is not str or not approved_name.strip():
            raise Blocked('approved_tool_missing')
        if descriptor.get('name') != approved_name:
            raise Blocked('tool_name_mismatch')
        if type(expected_context) is not dict or set(expected_context) != set(CONTEXT):
            raise Blocked('context_contract_invalid')
        if type(context_paths) is not dict or set(context_paths) != set(CONTEXT):
            raise Blocked('context_mapping_incomplete')
        paths = list(context_paths.values()) + [request_id_path]
        if any(type(p) is not str for p in paths) or len(set(paths)) != 6:
            raise Blocked('binding_paths_not_distinct')
        for field in CONTEXT:
            expected = expected_context[field]
            if type(expected) is not str or not expected.strip():
                raise Blocked('context_value_invalid')
            actual = pointer(arguments, context_paths[field])
            if type(actual) is not str or actual != expected:
                raise Blocked('context_mismatch:' + field)
        import re
        if (re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', expected_context['period']) is None
                or expected_context['period'].startswith('0000-')):
            raise Blocked('period_invalid')
        if type(expected_request_id) is not str or not expected_request_id.strip():
            raise Blocked('request_id_invalid')
        actual_id = pointer(arguments, request_id_path)
        if type(actual_id) is not str or actual_id != expected_request_id:
            raise Blocked('request_id_mismatch')
        schema = descriptor.get('inputSchema')
        if type(schema) is not dict or schema.get('type') != 'object':
            raise Blocked('object_input_schema_required')
        dialect = schema.get('$schema', 'https://json-schema.org/draft/2020-12/schema')
        if dialect not in DIALECTS:
            raise Blocked('schema_dialect_unsupported')
        try:
            from jsonschema import Draft202012Validator, Draft7Validator, FormatChecker
            from referencing import Registry
            from referencing.exceptions import NoSuchResource
        except ImportError:
            raise Blocked('validation_dependency_unavailable') from None
        checker = FormatChecker()
        # jsonschema's date-time checker requires optional dependencies absent in
        # the existing pinned runtime. Register a deterministic standard-library
        # checker instead of silently accepting timestamps or installing extras.
        checker.checks('date-time')(strict_datetime)
        _schema_policy(schema, checker)
        def no_retrieve(uri):
            raise NoSuchResource(ref=uri)
        cls = Draft7Validator if 'draft-07' in dialect else Draft202012Validator
        cls.check_schema(schema)
        validator = cls(schema, format_checker=checker, registry=Registry(retrieve=no_retrieve))
        # Return only the keyword, never the rejected value, schema enum or full payload.
        first = next(validator.iter_errors(arguments), None)
        if first is not None:
            raise Blocked('input_schema_violation:' + str(first.validator))
        body = {'name': approved_name, 'arguments': copy.deepcopy(arguments)}
        digest = hashlib.sha256(canonical(body)).hexdigest()
        return {'status': 'prepared', 'called': False, 'schema_dialect': dialect,
                'call_sha256': digest, 'call': body,
                'descriptor_sha256': hashlib.sha256(canonical(descriptor)).hexdigest(),
                'notice': 'offline validation only; descriptor provenance/authentication unverified'}
    except Blocked as exc:
        return {'status': 'blocked', 'called': False, 'reason': str(exc)}
    except Exception as exc:
        # Schema/reference/runtime errors fail closed; error text may contain secrets.
        return {'status': 'blocked', 'called': False,
                'reason': 'validation_error:' + type(exc).__name__}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descriptor', required=True)
    parser.add_argument('--arguments', required=True)
    parser.add_argument('--binding', required=True,
                        help='approved_name, expected_context, context_paths, expected_request_id, request_id_path')
    options = parser.parse_args(argv)
    try:
        result = prepare(strict_load(options.descriptor), strict_load(options.arguments),
                         **strict_load(options.binding))
    except Exception as exc:
        result = {'status': 'blocked', 'called': False, 'reason': 'input_error:' + type(exc).__name__}
    # CLI never prints a prepared call payload: avoid leaking business data in logs.
    print(json.dumps({k:v for k,v in result.items() if k != 'call'}, ensure_ascii=False))
    return 0 if result['status'] == 'prepared' else 2


if __name__ == '__main__':
    raise SystemExit(main())
