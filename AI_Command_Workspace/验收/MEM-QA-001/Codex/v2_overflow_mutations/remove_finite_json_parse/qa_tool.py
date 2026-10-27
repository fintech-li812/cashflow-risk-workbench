"""Manufacturing cashflow artifact QA. Standard library, offline, no target execution."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from decimal import Decimal, localcontext, ROUND_HALF_UP
import hashlib
import html
import io
import json
import math
import ntpath
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import sys
import xml.etree.ElementTree as ET
import zipfile

VERSION = 'mfg-qa.v1'
CONTEXT = ('tenant_id', 'company_id', 'period', 'source_revision', 'run_id')
MONEY = re.compile(r'-?(?:0|[1-9][0-9]{0,17})\.[0-9]{2}\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')
ADDR = re.compile(r'[A-Z]{1,3}[1-9][0-9]{0,6}\Z')
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024


class InputError(ValueError):
    pass


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pairs_hook(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise InputError('JSON_DUPLICATE_KEY')
        obj[key] = value
    return obj


def parse_json(data):
    if len(data) > MAX_FILE:
        raise InputError('FILE_TOO_LARGE')
    try:
        return json.loads(data.decode('utf-8-sig'), object_pairs_hook=pairs_hook, 
                          parse_constant=lambda _: (_ for _ in ()).throw(InputError('JSON_NONFINITE')))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InputError('JSON_INVALID') from exc


def finite_json_number(text):
    value = float(text)
    if not math.isfinite(value):
        raise InputError('JSON_NONFINITE')
    return value


def read_bytes(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE:
        raise InputError('FILE_UNSAFE_OR_TOO_LARGE')
    return path.read_bytes()


def read_json(path):
    return parse_json(read_bytes(path))


def safe_name(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or any(ord(c) < 32 for c in name):
        raise InputError('PATH_UNSAFE')
    path = PurePosixPath(name)
    parts = name.split('/')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{v}{i}' for v in ('COM', 'LPT') for i in range(1, 10)}
    if path.is_absolute() or ntpath.isabs(name) or any(p in ('', '.', '..') or p[-1:] in (' ', '.') or p.split('.')[0].upper() in reserved for p in parts):
        raise InputError('PATH_UNSAFE')
    return name


def inside(root, name):
    safe_name(name)
    root = Path(root)
    if root.is_symlink():
        raise InputError('PATH_LINK')
    candidate = root / name
    node = root
    for part in name.split('/'):
        node = node / part
        if node.is_symlink():
            raise InputError('PATH_LINK')
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise InputError('PATH_ESCAPE')
    return candidate


class Report:
    def __init__(self, operation):
        self.operation = operation
        self.issues = []
        self.checks = 0
        self.notes = ['离线工件检查；没有执行主算法、平台操作或数据库提交。']

    def check(self, ok, code, location, expected, action):
        self.checks += 1
        if not ok:
            self.add('失败', code, location, expected, action)
        return bool(ok)

    def add(self, state, code, location, expected, action):
        self.issues.append(dict(state=state, code=code, location=str(location),
                                expected=expected, actual='检查未满足；见定位及原始工件', action=action))

    def block(self, code, location, expected, action):
        self.add('阻塞', code, location, expected, action)

    @property
    def status(self):
        return '失败' if any(x['state'] == '失败' for x in self.issues) else ('阻塞' if self.issues else '通过')

    @property
    def exit_code(self):
        return {'通过': 0, '失败': 1, '阻塞': 2}[self.status]

    def as_dict(self):
        return dict(schema_version=VERSION, operation=self.operation, status=self.status,
                    exit_code=self.exit_code, check_count=self.checks, issues=self.issues, notes=self.notes)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def valid_address(value, row):
    if not isinstance(value, str) or not ADDR.fullmatch(value):
        return False
    match = re.fullmatch(r'([A-Z]+)([0-9]+)', value)
    column = 0
    for ch in match[1]:
        column = column * 26 + ord(ch) - 64
    return int(match[2]) == row and 1 <= row <= 1048576 and column <= 16384


def check_context(obj, report, loc):
    if not report.check(isinstance(obj, dict), 'OBJECT_REQUIRED', loc, 'JSON对象', '修正对象类型'):
        return False
    valid = True
    for key in CONTEXT:
        valid &= report.check(nonempty(obj.get(key)), 'CONTEXT_MISSING', f'{loc}.{key}', '非空字符串', '补可信上下文，不从公司名猜身份')
    period = obj.get('period')
    valid &= report.check(bool(re.fullmatch(r'[0-9]{4}-(?:0[1-9]|1[0-2])', period)) and int(period[:4]) >= 1 if isinstance(period, str) else False,
                          'PERIOD_INVALID', f'{loc}.period', 'YYYY-MM合法月份', '修正期间')
    return bool(valid)


def money(value, report, loc, nullable=False):
    if value is None and nullable:
        return None
    if not report.check(isinstance(value, str) and bool(MONEY.fullmatch(value)), 'MONEY_INVALID', loc,
                        '元，两位小数十进制字符串；非浮点/NaN/Infinity', '核原单位和精度，禁止补0'):
        return None
    return Decimal(value)


def verify_result(obj, context, receipt=None, allow_fixture=False, expected_request=None):
    r = Report('verify-result')
    if not check_context(obj, r, 'result') or not check_context(context, r, 'context'):
        return r
    try:
        canonical(obj); canonical(context)
        if receipt is not None:
            canonical(receipt)
    except (ValueError, TypeError, OverflowError, RecursionError):
        r.check(False, 'JSON_UNSAFE', 'result/context/receipt', '所有字段均为可规范序列化的有限JSON值', '不要在额外字段藏NaN/Infinity或非JSON对象')
        return r
    for key in CONTEXT:
        r.check(obj[key] == context[key], 'CONTEXT_MISMATCH', f'result.{key}', '与可信context逐项相同', '重新绑定身份、期间与来源版本')
    r.check(obj.get('schema_version') == 'mfg-agent-result.v1', 'RESULT_SCHEMA', 'result.schema_version', 'mfg-agent-result.v1', '使用批准接口')
    r.check(obj.get('industry') == 'manufacturing', 'INDUSTRY', 'result.industry', 'manufacturing', '只接制造业')
    state = obj.get('status')
    r.check(state in ('success', 'missing_inputs', 'formula_error', 'unavailable'), 'RESULT_STATUS', 'result.status', '批准闭集', '不要新增业务状态')
    issues = obj.get('issues')
    r.check(isinstance(issues, list) and all(nonempty(x) for x in issues), 'ISSUES_TYPE', 'result.issues', '非空原因字符串列表；success可空列表', '原因不能为null/对象/空字符串')
    if state != 'success':
        if 'unit' in obj:
            r.check(obj.get('unit') == 'CNY', 'UNIT', 'result.unit', '声明单位时必须CNY', '不要混用万元')
        r.check(obj.get('amounts') is None and 'amounts' in obj, 'FAILED_WITH_AMOUNTS', 'result.amounts', '非success必须null', '移除伪完整金额')
        r.check(isinstance(issues, list) and bool(issues), 'MISSING_REASON', 'result.issues', '非success有缺项/错误说明', '列具体原因')
        if receipt is not None:
            r.check(False, 'RECEIPT_FOR_FAILURE', 'receipt', '失败/未就绪不生成成功回执', '只保留诊断记录')
        return r
    r.check(obj.get('unit') == 'CNY', 'UNIT', 'result.unit', 'CNY元', '源单位核实后按原精度换元一次')
    r.check(issues == [], 'SUCCESS_WITH_ISSUES', 'result.issues', 'success为[]', '缺项时返回正确状态')
    r.check(obj.get('coverage') == 'full_cashflow', 'COVERAGE', 'result.coverage', '完整结果接口要求full_cashflow', '经营部分单独说明，不伪造完整成功')
    r.check(nonempty(obj.get('calculation_version')), 'CALCULATION_VERSION', 'result.calculation_version', '非空计算版本', '记录批准公式版本')
    source = obj.get('source')
    if r.check(isinstance(source, dict), 'SOURCE', 'result.source', '四项来源引用', '补真实来源'):
        for key in ('workbook_ref', 'sheet', 'range', 'snapshot_ref'):
            r.check(nonempty(source.get(key)), 'SOURCE', f'result.source.{key}', '非空来源引用', '补真实取数定位')
    origin = obj.get('origin')
    if origin == 'offline_fixture':
        r.check(allow_fixture is True, 'FIXTURE_IN_PRODUCTION', 'result.origin', '测试夹具显式allow_fixture', '生产路径拒绝夹具')
        r.notes.append('当前为显式合成测试；通过仅证明格式与算术，不代表真实企业/平台。')
    elif origin == 'qwen_sheet':
        r.block('PLATFORM_PROVENANCE_UNVERIFIED', 'result.origin', '有独立平台取数与重算证据', 'origin标签不是认证；提交平台证据人工核验')
    else:
        r.check(False, 'ORIGIN', 'result.origin', 'qwen_sheet或显式offline_fixture', '不能冒称平台来源')
    values = obj.get('amounts')
    if r.check(isinstance(values, dict), 'AMOUNTS', 'result.amounts', '七项金额对象', '按共同合同输出'):
        names = ('opening', 'inflow', 'outflow', 'net', 'closing', 'actual_closing', 'difference')
        r.check(set(values) == set(names), 'AMOUNT_FIELDS', 'result.amounts', '共同结果七个金额键，不塞预测/评级字段', '清理未批准金额字段')
        for key in names:
            r.check(key in values, 'AMOUNT_MISSING', f'result.amounts.{key}', '七键齐全', '缺独立余额时明确null，不漏键')
        amounts = {k: money(values.get(k), r, 'result.amounts.' + k, k in ('actual_closing', 'difference')) for k in names}
        with localcontext() as ctx:
            ctx.prec = 50
            if all(amounts[k] is not None for k in ('inflow', 'outflow', 'net')):
                r.check(amounts['inflow'] - amounts['outflow'] == amounts['net'], 'NET_MISMATCH', 'result.amounts.net', '流入-流出', '核公式和单位')
                r.check(amounts['inflow'] >= 0 and amounts['outflow'] >= 0, 'SIGNED_TOTAL', 'result.amounts', '收付合计为非负；负余额允许', '源冲销先按批准映射处理')
            if all(amounts[k] is not None for k in ('opening', 'net', 'closing')):
                r.check(amounts['opening'] + amounts['net'] == amounts['closing'], 'CLOSING_MISMATCH', 'result.amounts.closing', '期初+净额', '核余额承接')
            actual, diff = amounts['actual_closing'], amounts['difference']
            r.check((values.get('actual_closing') is None) == (values.get('difference') is None), 'RECONCILIATION_NULL_PAIR', 'result.amounts', '独立余额与差异同时缺失', '不以0伪造已核对')
            if actual is not None and diff is not None and amounts['closing'] is not None:
                r.check(actual - amounts['closing'] == diff, 'DIFFERENCE_MISMATCH', 'result.amounts.difference', '实际期末-计算期末', '纠正差异方向与金额')
            if context.get('actual_balance_provided') is False:
                r.check(values.get('actual_closing') is None and values.get('difference') is None, 'INVENTED_ACTUAL_BALANCE', 'result.amounts.actual_closing', '可信测试上下文说明未提供独立余额', '移除伪实际余额与差异0')
            if 'independent_actual_closing' in context and context['independent_actual_closing'] is not None:
                r.check(values.get('actual_closing') == context['independent_actual_closing'], 'ACTUAL_EVIDENCE_MISMATCH', 'result.amounts.actual_closing', '与独立提供值相同', '核独立余额来源')
            if actual is None:
                r.notes.append('未提供独立实际余额，余额勾稽未完成。')
    if receipt is not None:
        verify_receipt(receipt, obj, context, r, expected_request)
    return r


def verify_receipt(receipt, result, context, r, expected_request):
    if not check_context(receipt, r, 'receipt'):
        return
    for key in CONTEXT:
        r.check(receipt[key] == context[key], 'RECEIPT_CONTEXT', f'receipt.{key}', '与结果/context相同', '精确回查同企业/期间/版本/run')
    for key, value in {'schema_version': 'mfg-evidence.v1', 'kind': 'receipt', 'operation': 'save_cashflow_result', 'status': 'committed'}.items():
        r.check(receipt.get(key) == value, 'RECEIPT_FIELD', f'receipt.{key}', value, '使用真实提交回执')
    for key in ('request_id', 'record_id'):
        r.check(nonempty(receipt.get(key)), 'RECEIPT_FIELD', f'receipt.{key}', '非空标识', '返回精确提交标识')
    if not nonempty(expected_request):
        r.block('EXPECTED_REQUEST_REQUIRED', 'receipt.request_id', '可信调用方提供本次逻辑request_id', '通过--request-id或可信context.expected_request_id提供')
    else:
        r.check(receipt.get('request_id') == expected_request, 'RECEIPT_REQUEST', 'receipt.request_id', '与本次逻辑保存请求相同', '不用另一条最新记录代替')
    r.check(receipt.get('payload_sha256') == digest(canonical(result)), 'RECEIPT_HASH', 'receipt.payload_sha256', '完整结果规范JSON摘要', '核内容与精确回查，不仅看committed')
    try:
        stamp = receipt.get('stored_at')
        parsed = datetime.fromisoformat(stamp.replace('Z', '+00:00')) if isinstance(stamp, str) else None
        valid = parsed is not None and parsed.utcoffset() is not None
    except ValueError:
        valid = False
    r.check(valid, 'RECEIPT_TIME', 'receipt.stored_at', '带时区的真实时间', '不要填无时区时间')
    r.notes.append('回执仅核内容一致性；未连接存储，不能证明事务已提交或MySQL入库。')


def json_lines(data):
    try:
        return [parse_json(line.encode('utf-8')) for line in data.decode('utf-8-sig').splitlines() if line.strip()]
    except UnicodeError as exc:
        raise InputError('JSONL_ENCODING') from exc


def ooxml_cells(path, sheet):
    """Return XML-level cell evidence; never execute or calculate formulas."""
    main = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    rel = '{http://schemas.openxmlformats.org/package/2006/relationships}'
    rid = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    with zipfile.ZipFile(io.BytesIO(read_bytes(path))) as z:
        infos = z.infolist()
        if len(infos) > 2000 or sum(x.file_size for x in infos) > MAX_TOTAL:
            raise InputError('XLSX_LIMIT')
        names = set()
        for info in infos:
            name = safe_name(info.filename.rstrip('/'))
            if name.casefold() in names or info.flag_bits & 1 or stat.S_ISLNK(info.external_attr >> 16):
                raise InputError('XLSX_AMBIGUOUS_OR_UNSAFE')
            names.add(name.casefold())
        def xml(name):
            info = z.getinfo(name)
            if info.file_size > MAX_FILE:
                raise InputError('XML_LIMIT')
            data = z.read(name)
            normalized = data.replace(b'\x00', b'').upper()
            if b'<!DOCTYPE' in normalized or b'<!ENTITY' in normalized:
                raise InputError('XML_ENTITY')
            return ET.fromstring(data)
        book = xml('xl/workbook.xml')
        relationships = {x.attrib['Id']: x.attrib for x in xml('xl/_rels/workbook.xml.rels').findall(rel + 'Relationship')}
        entry = next((x for x in book.findall('.//' + main + 'sheet') if x.attrib.get('name') == sheet), None)
        if entry is None:
            raise InputError('SHEET_NOT_FOUND')
        relation = relationships[entry.attrib[rid]]
        if relation.get('TargetMode') == 'External':
            raise InputError('EXTERNAL_SHEET')
        target = relation['Target']
        target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
        safe_name(target)
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            shared = [''.join(v.text or '' for v in si.findall(main + 't') + si.findall(main + 'r/' + main + 't')) for si in xml('xl/sharedStrings.xml').findall(main + 'si')]
        cells = {}
        for c in xml(target).findall('.//' + main + 'sheetData/' + main + 'row/' + main + 'c'):
            address = c.attrib['r']
            if address in cells:
                raise InputError('CELL_DUPLICATE')
            v, f = c.find(main + 'v'), c.find(main + 'f')
            kind = c.attrib.get('t', 'n')
            raw = v.text if v is not None else None
            value = raw
            if kind == 's':
                index = int(raw)
                if index < 0 or index >= len(shared):
                    raise InputError('SHARED_STRING_INDEX')
                value = shared[index]
            elif kind == 'inlineStr':
                value = ''.join(x.text or '' for x in c.iter(main + 't'))
            cells[address] = {'cell_present': True, 'raw_type': kind, 'raw_value': raw, 'value': value,
                              'formula': f.text if f is not None else None,
                              'formula_present': f is not None, 'cache_present': v is not None, 'cache_raw': raw}
        return cells


def verify_package(root, source_root=None, profile=None, mapping=None):
    """Common contract checks + optional explicitly selected OOXML evidence adapter."""
    r = Report('verify-package')
    root = Path(root)
    manifest = read_json(inside(root, 'manifest.json'))
    if not check_context(manifest, r, 'manifest'):
        return r
    r.check(manifest.get('schema_version') == 'mfg-import.v1', 'IMPORT_SCHEMA', 'manifest.schema_version', 'mfg-import.v1', '使用共同导入接口')
    r.check(manifest.get('kind') == 'import_package' and manifest.get('unit') == 'CNY', 'IMPORT_KIND_UNIT', 'manifest', 'import_package/CNY', '区分规范金额与源单位')
    for key in ('tool_version', 'mapping_version'):
        r.check(nonempty(manifest.get(key)), 'IMPORT_VERSION', 'manifest.' + key, '非空版本', '固定解析和映射版本')
    entries = manifest.get('files')
    if not r.check(isinstance(entries, list) and bool(entries), 'FILES', 'manifest.files', '非空文件列表', '补路径/哈希/记录数'):
        return r
    content, names, total = {}, set(), 0
    for i, entry in enumerate(entries):
        if not r.check(isinstance(entry, dict), 'FILE_ENTRY', f'manifest.files[{i}]', '文件对象', '修清单'):
            continue
        name = safe_name(entry.get('path'))
        r.check(name.casefold() not in names and name != 'manifest.json', 'FILE_DUPLICATE', f'manifest.files[{i}]', '路径唯一，不包含自身', '去掉歧义清单')
        names.add(name.casefold())
        data = read_bytes(inside(root, name)); total += len(data)
        if total > MAX_TOTAL:
            raise InputError('PACKAGE_LIMIT')
        r.check(entry.get('sha256') == digest(data), 'FILE_HASH', name, '文件与固定清单相同', '检查版本或篡改')
        count = entry.get('record_count')
        r.check(type(count) is int and count >= 0, 'RECORD_COUNT_TYPE', name, '非负整数record_count', '修清单记录数')
        if name.endswith('.jsonl'):
            values = json_lines(data)
            r.check(count == len(values), 'RECORD_COUNT', name, '真实JSONL记录数', '重新核清单，不改预期')
            content[name] = values
        elif name.endswith('.json'):
            content[name] = parse_json(data)
    for name in ('inventory.json', 'records.jsonl', 'issues.jsonl', 'report.html'):
        r.check(name.casefold() in names, 'IMPORT_FILE_MISSING', name, '共同导入包产物齐全', '补必交文件')
    records = content.get('records.jsonl', [])
    issue_ids = set()
    for issue in content.get('issues.jsonl', []):
        if r.check(isinstance(issue, dict), 'ISSUE_OBJECT', 'issues.jsonl', '问题对象', '修类型'):
            ident = issue.get('issue_id')
            r.check(nonempty(ident) and ident not in issue_ids, 'ISSUE_ID', 'issues.jsonl', '唯一非空issue_id', '修问题引用')
            if isinstance(ident, str):
                issue_ids.add(ident)
            r.check(nonempty(issue.get('code')), 'ISSUE_CODE', 'issues.jsonl', '非空导入问题code', '不能冒充gate_结果')
    keys = set()
    for i, record in enumerate(records):
        loc = f'records.jsonl[{i}]'
        if not r.check(isinstance(record, dict), 'RECORD_OBJECT', loc, '记录对象', '修记录'):
            continue
        sha, sheet, row = record.get('source_file_sha256'), record.get('sheet'), record.get('row')
        valid = isinstance(sha, str) and bool(SHA.fullmatch(sha)) and nonempty(sheet) and type(row) is int and row > 0
        r.check(valid, 'RECORD_SOURCE', loc, '源SHA256/Sheet/正整数row', '保留真实定位')
        r.check(nonempty(record.get('record_type')), 'RECORD_TYPE', loc, '非空record_type', '说明业务来源类型')
        if valid:
            expected = digest(canonical({'source_file_sha256': sha, 'sheet': sheet, 'row': row}))
            r.check(record.get('source_record_key') == expected and expected not in keys, 'RECORD_KEY', loc, '同源定位稳定唯一键', '修键或重复结构；不删除源重复业务行')
            keys.add(expected)
        cells, norm = record.get('cells'), record.get('normalized')
        r.check(isinstance(cells, dict) and bool(cells), 'CELLS', loc + '.cells', 'A1地址证据对象', '保留真实原始值/类型')
        if isinstance(cells, dict):
            for address in cells:
                r.check(valid_address(address, row), 'CELL_ADDRESS', loc + '.cells', '真实本行Excel网格内A1地址', '核地址与row')
        r.check(isinstance(norm, dict), 'NORMALIZED', loc + '.normalized', '规范字段对象', '未知值null且有来源转换依据')
        refs = record.get('issues')
        r.check(isinstance(refs, list) and all(isinstance(v, str) and v in issue_ids for v in refs), 'ISSUE_REFERENCE', loc + '.issues', '引用现有issue_id', '修问题定位')
    if source_root is None:
        r.block('SOURCE_NOT_PROVIDED', 'package', '可信真实源目录', '当前只能核包内一致性，补源后核字段')
    if profile != {'schema_version': 'mfg-qa-ooxml-profile.v1'}:
        r.block('SOURCE_ADAPTER_NOT_SELECTED', 'profile', '显式选择并确认源证据适配形状', '提供本工具候选profile，未知字段形状不可宣称源值已核')
        return r
    inventory = content.get('inventory.json')
    if not r.check(isinstance(inventory, dict) and isinstance(inventory.get('sources'), list), 'PROFILE_INVENTORY', 'inventory.sources', '本地适配profile的源列表', '按文档映射；未批准不得修改共享接口'):
        return r
    sources = inventory['sources']; source_names = set(); source_files = {}
    valid_sources = []
    for item in sources:
        if not r.check(isinstance(item, dict) and nonempty(item.get('logical_name')) and isinstance(item.get('sha256'), str) and bool(SHA.fullmatch(item['sha256'])), 'PROFILE_SOURCE', 'inventory.sources', 'logical_name/sha256', '补固定源摘要'):
            continue
        name = safe_name(item['logical_name'])
        r.check(name.casefold() not in source_names, 'SOURCE_DUPLICATE', name, '逻辑文件名唯一', '消除源歧义')
        source_names.add(name.casefold()); valid_sources.append({'logical_name': name, 'sha256': item['sha256']})
        if source_root is not None:
            file = inside(source_root, name)
            r.check(digest(read_bytes(file)) == item['sha256'], 'SOURCE_HASH', name, '真实源匹配可信摘要', '确认源版本')
            source_files[item['sha256']] = file
    mapping_sha = inventory.get('mapping_sha256')
    r.check(isinstance(mapping_sha, str) and bool(SHA.fullmatch(mapping_sha)), 'MAPPING_HASH', 'inventory.mapping_sha256', '固定映射SHA256', '补映射摘要')
    expected_revision = digest(canonical({'sources': sorted(valid_sources, key=lambda x: x['logical_name']), 'mapping_sha256': mapping_sha}))
    r.check(manifest.get('source_revision') == expected_revision, 'SOURCE_REVISION', 'manifest.source_revision', '共同规范JSON源摘要+映射摘要', '来源/映射变化必须换版本')
    mapping_data = None
    if mapping is None:
        r.block('MAPPING_NOT_PROVIDED', 'mapping', '独立映射文件', '补--mapping后验证映射原件摘要')
    else:
        r.check(digest(read_bytes(mapping)) == mapping_sha, 'MAPPING_HASH', 'mapping', '映射原件摘要一致', '确认映射版本')
        mapping_data = read_json(mapping)
        if not isinstance(mapping_data, dict) or mapping_data.get('schema_version') != 'mfg-qa-map.v1' or not isinstance(mapping_data.get('fields'), dict):
            r.block('MAPPING_ADAPTER', 'mapping', '显式候选mfg-qa-map.v1适配', '未知映射形状只核摘要，不宣称单位依据已验证')
            mapping_data = None
    cache = {}
    for i, record in enumerate(records):
        if not isinstance(record, dict) or record.get('source_file_sha256') not in source_files:
            if source_root is not None:
                r.check(False, 'SOURCE_REFERENCE', f'records[{i}]', '记录源摘要存在且可定位', '补真实源')
            continue
        file, sheet = source_files[record['source_file_sha256']], record.get('sheet')
        if not nonempty(sheet) or not isinstance(record.get('cells'), dict):
            continue
        cache_key = (str(file), sheet)
        if cache_key not in cache:
            cache[cache_key] = ooxml_cells(file, sheet)
        raw_cells = cache[cache_key]
        for address, observed in record['cells'].items():
            if not isinstance(observed, dict):
                r.check(False, 'PROFILE_CELL', f'records[{i}].cells.{address}', 'profile证据对象', '补适配字段')
                continue
            actual = raw_cells.get(address, {'cell_present': False, 'raw_type': None, 'raw_value': None, 'value': None, 'formula': None, 'formula_present': False, 'cache_present': False, 'cache_raw': None})
            for key in actual:
                r.check(key in observed and observed[key] == actual[key], 'SOURCE_CELL_MISMATCH', f'records[{i}].cells.{address}.{key}', '与真实OOXML原格逐字段一致', '核源格，不用重算包哈希掩盖内容篡改')
        normalized = record.get('normalized')
        if not isinstance(normalized, dict):
            continue
        for field, evidence in normalized.items():
            loc = f'records[{i}].normalized.{field}'
            if not isinstance(evidence, dict):
                r.block('NORMALIZATION_ADAPTER', loc, 'profile内value/source_address/transform', '映射未确定，不能宣称转换已核')
                continue
            address = evidence.get('source_address')
            cell = raw_cells.get(address) if isinstance(address, str) else None
            if not r.check(cell is not None and address in record['cells'], 'NORMALIZED_SOURCE', loc, '本记录已列出的真实源地址', '补字段定位'):
                continue
            value = evidence.get('value')
            rule = mapping_data['fields'].get(sheet + '!' + address) if mapping_data is not None else None
            known_uncertain = record.get('source_file_sha256') == '7e32b1eca8cfe892bd0ee96dfe257b03965018e607fc0e8cbaface33c13d0a3b' and sheet == '现金流水' and address == 'D8'
            blocked_amount = known_uncertain or (isinstance(rule, dict) and rule.get('blocked') is True)
            if blocked_amount:
                r.check(value is None, 'UNIT_UNRESOLVED', loc, '源哈希/地址绑定单位疑点必须null', '待业务核实，不自动放大')
            if value is None:
                r.check(bool(record.get('issues')), 'NULL_WITHOUT_ISSUE', loc, '未知值有问题引用', '记录为何不能规范化')
                continue
            if evidence.get('transform') == 'yuan_half_up':
                parsed = money(value, r, loc)
                unit = evidence.get('source_unit')
                if not isinstance(rule, dict):
                    r.block('UNIT_MAPPING_NOT_VALIDATED', loc, '独立映射文件含该源格单位与转换规则', '补候选映射适配，不能仅信规范字段自报单位')
                else:
                    r.check(rule.get('source_unit') == unit and rule.get('unit') == evidence.get('unit') and rule.get('transform') == 'yuan_half_up',
                            'UNIT_MAPPING_MISMATCH', loc, '独立映射单位及转换相同', '核真实源单位，元万元不混淆')
                r.check(evidence.get('unit') == 'CNY' and unit in ('万元', '元'), 'NORMALIZATION_UNIT', loc, '明确源元/万元→CNY', '不猜单位')
                try:
                    with localcontext() as ctx:
                        ctx.prec = 60
                        raw_amount = Decimal(cell['value'])
                        expected = (raw_amount * (10000 if unit == '万元' else 1)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
                    r.check(cell['raw_type'] in ('n',) and not cell['formula_present'] and raw_amount.is_finite() and parsed == expected,
                            'NORMALIZATION_VALUE', loc, '保留原精度换元后落分', '不要万元先截两位或重复换算')
                except (ValueError, TypeError, ArithmeticError):
                    r.check(False, 'NORMALIZATION_VALUE', loc, '可核实有限数值', '保留疑点null')
            else:
                r.block('NORMALIZATION_ADAPTER', loc, '已审查的转换规则', '本候选只核元/万元金额转换，日期等转换待适配')
    r.notes.append('OOXML profile为本工具候选适配，不是共享接口新增字段；未证明源真实性或所有应抽行都已抽齐。')
    return r


def delivery_files(path):
    path = Path(path)
    values = {}
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            if len(infos) > 2000 or sum(x.file_size for x in infos) > MAX_TOTAL:
                raise InputError('ZIP_LIMIT')
            for item in infos:
                name = item.filename.rstrip('/')
                safe_name(name)
                if stat.S_ISLNK(item.external_attr >> 16):
                    raise InputError('ZIP_SYMLINK')
                if item.flag_bits & 1:
                    raise InputError('ZIP_ENCRYPTED')
                if item.is_dir():
                    continue
                if item.file_size > MAX_FILE or name.casefold() in {x.casefold() for x in values}:
                    raise InputError('ZIP_SIZE_OR_DUPLICATE')
                values[name] = z.read(item)
    else:
        if path.is_symlink():
            raise InputError('PATH_LINK')
        total = 0
        for f in sorted(path.rglob('*')):
            name = f.relative_to(path).as_posix(); safe_name(name)
            inside(path, name)
            if f.is_file():
                values[name] = read_bytes(f); total += len(values[name])
                if total > MAX_TOTAL or len(values) > 2000:
                    raise InputError('DELIVERY_LIMIT')
    return values


def verify_delivery(path):
    r = Report('verify-delivery'); files = delivery_files(path)
    for name in ('README.md', 'manifest.json', 'SHA256SUMS.txt'):
        r.check(name in files, 'DELIVERY_FILE', name, '根目录必交文件', '补交付文件')
    if 'manifest.json' in files:
        manifest = parse_json(files['manifest.json'])
        if not r.check(isinstance(manifest, dict), 'DELIVERY_MANIFEST', 'manifest', '对象', '修清单'):
            return r
        for key in ('task_id', 'package_version', 'author', 'status'):
            r.check(nonempty(manifest.get(key)), 'DELIVERY_METADATA', 'manifest.' + key, '非空元数据', '如实标候选与作者')
        listed = manifest.get('files')
        if r.check(isinstance(listed, list) and bool(listed), 'DELIVERY_MANIFEST_FILES', 'manifest.files', '完整交付文件清单', '按候选交付profile补清单'):
            declared = set()
            for entry in listed:
                if not r.check(isinstance(entry, dict), 'DELIVERY_MANIFEST_FILES', 'manifest.files', 'path/sha256对象', '修清单'):
                    continue
                name = safe_name(entry.get('path'))
                r.check(name.casefold() not in declared and name not in ('manifest.json', 'SHA256SUMS.txt'), 'DELIVERY_MANIFEST_DUPLICATE', name, '不循环、不重复', '修文件列表')
                declared.add(name.casefold())
                r.check(name in files and digest(files[name]) == entry.get('sha256'), 'DELIVERY_MANIFEST_HASH', name, 'manifest与实际文件一致', '核版本和文件')
            for name in files:
                if name not in ('manifest.json', 'SHA256SUMS.txt'):
                    r.check(name.casefold() in declared, 'DELIVERY_MANIFEST_UNLISTED', name, '所有业务文件列入manifest', '补文件清单')
    if 'SHA256SUMS.txt' in files:
        entries = {}
        try:
            for line in files['SHA256SUMS.txt'].decode('utf-8-sig').splitlines():
                if not line.strip() or line.startswith('#'):
                    continue
                match = re.fullmatch(r'([a-fA-F0-9]{64})\s+\*?(.+)', line)
                if not match:
                    raise InputError('HASH_LIST_SYNTAX')
                name = safe_name(match[2])
                if name.casefold() in {x.casefold() for x in entries} or name == 'SHA256SUMS.txt':
                    raise InputError('HASH_LIST_DUPLICATE')
                entries[name] = match[1].lower()
            for name in files:
                if name != 'SHA256SUMS.txt':
                    r.check(name in entries and digest(files[name]) == entries.get(name), 'DELIVERY_HASH', name, '全部文件列入且摘要一致', '核文件版本')
            for name in entries:
                r.check(name in files, 'DELIVERY_HASH_MISSING', name, '哈希所列文件存在', '补缺失文件')
        except UnicodeError as exc:
            raise InputError('HASH_ENCODING') from exc
    for prefix in ('tests/', 'expected/', 'test-output/'):
        r.check(any(name.startswith(prefix) for name in files), 'DELIVERY_EVIDENCE', prefix, '独立用例/预期/实际输出', '补可复现证据')
    if r.status == '通过':
        r.block('EXECUTION_NOT_OBSERVED', 'delivery', '独立执行验证', '工件齐备不等于代码执行正确或平台通过')
    r.notes.append('不运行交付中的代码、shell或ZIP；仅检查文件和哈希，未做代码安全背书。')
    return r


def write_reports(report, output):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise InputError('OUTPUT_EXISTS')
    output.mkdir(parents=True, exist_ok=False)
    obj = report.as_dict()
    (output / 'results.json').write_bytes(canonical(obj))
    cols = ('state', 'code', 'location', 'expected', 'actual', 'action')
    stream = io.StringIO(newline=''); writer = csv.DictWriter(stream, fieldnames=cols); writer.writeheader()
    for issue in report.issues:
        writer.writerow({k: ("'" + str(issue[k]) if str(issue[k]).lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else str(issue[k])) for k in cols})
    (output / 'issues.csv').write_text(stream.getvalue(), encoding='utf-8-sig', newline='')
    details = ''.join('<tr>' + ''.join('<td>' + html.escape(str(item[k]), quote=True) + '</td>' for k in cols) + '</tr>' for item in report.issues)
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>离线工件验收</title><style>body{font:16px sans-serif;margin:32px;color:#182438}table{border-collapse:collapse}td,th{border:1px solid #bcc8d8;padding:8px;text-align:left}p{max-width:1000px}</style><h1>离线工件验收：' + html.escape(report.status) + '</h1><p>不是平台或数据库上线验收。</p><p>' + html.escape('；'.join(report.notes)) + '</p><table><tr>' + ''.join('<th>' + html.escape(k) + '</th>' for k in cols) + '</tr>' + details + '</table></html>'
    (output / 'report.html').write_text(page, encoding='utf-8')
    (output / 'summary.md').write_text('# 离线工件验收\n\n状态：' + report.status + '\n\n' + '\n\n'.join(report.notes) + '\n\n详见results.json与issues.csv。未执行的平台33项不能据此自动填通过。\n', encoding='utf-8')


def replay(case_dir, expected_sha):
    root = Path(case_dir); plan_bytes = read_bytes(inside(root, 'cases.json'))
    r = Report('replay')
    if not r.check(bool(isinstance(expected_sha, str) and SHA.fullmatch(expected_sha)) and digest(plan_bytes) == expected_sha, 'PLAN_HASH', 'cases.json', '外部固定的预期计划SHA256', '提供--plan-sha256，不重写预期'):
        return r
    plan = parse_json(plan_bytes)
    if not r.check(isinstance(plan, dict) and plan.get('schema_version') == 'mfg-qa-replay.v1' and isinstance(plan.get('cases'), list), 'REPLAY_PLAN', 'cases.json', '显式回放计划', '修计划形状'):
        return r
    seen, actuals, idempotence, pinned = set(), [], {}, {}
    if not r.check(bool(plan['cases']), 'REPLAY_EMPTY', 'cases.json', '至少一个独立用例', '不能空计划报通过'):
        return r
    for item in plan['cases']:
        if not isinstance(item, dict) or not nonempty(item.get('id')) or item['id'] in seen:
            raise InputError('REPLAY_CASE_ID')
        seen.add(item['id'])
        hashes = item.get('files')
        if not isinstance(hashes, dict):
            raise InputError('REPLAY_FILES')
        blobs = {}
        for name, sha in hashes.items():
            data = read_bytes(inside(root, name))
            if digest(data) != sha:
                raise InputError('REPLAY_FILE_HASH')
            blobs[name] = data
            if name in pinned and pinned[name] != sha:
                raise InputError('REPLAY_CONFLICTING_HASH')
            pinned[name] = sha
        def load_ref(key):
            name = item.get(key)
            if name not in blobs:
                raise InputError('REPLAY_REF_UNPINNED')
            return parse_json(blobs[name])
        if item.get('operation') != 'verify-result':
            raise InputError('REPLAY_OPERATION_UNSUPPORTED')
        payload, context = load_ref('result'), load_ref('context')
        receipt = load_ref('receipt') if 'receipt' in item else None
        current = verify_result(payload, context, receipt, item.get('allow_fixture') is True, context.get('expected_request_id'))
        if receipt is not None and isinstance(receipt, dict):
            key = tuple(receipt.get(k) for k in ('tenant_id', 'company_id', 'operation', 'request_id'))
            if all(isinstance(k, str) for k in key):
                val = (receipt.get('payload_sha256'), receipt.get('record_id'))
                if key in idempotence and idempotence[key] != val:
                    current.check(False, 'IDEMPOTENCE_CONFLICT', item['id'], '同一逻辑请求同一payload/record', '精确回查，不覆盖或改ID掩盖')
                idempotence[key] = val
        expected = item.get('expected', {})
        codes = {x['code'] for x in current.issues}
        ok = current.status == expected.get('status') and set(expected.get('codes', [])) <= codes
        r.check(ok, 'REPLAY_EXPECTATION', item['id'], '实际状态与独立固定预期及必需错误码一致', '核实现或预期来源，不改预期迎合程序')
        actuals.append({'id': item['id'], 'matched': ok, 'actual': current.as_dict(), 'expected': expected})
    r.check(digest(read_bytes(inside(root, 'cases.json'))) == expected_sha, 'EXPECTED_CHANGED', 'cases.json', '运行前后固定预期未变', '禁止运行时写预期')
    for name, sha in pinned.items():
        r.check(digest(read_bytes(inside(root, name))) == sha, 'REPLAY_INPUT_CHANGED', name, '运行前后输入/预期关联文件不变', '核不应有的写入')
    r.notes.append(f'回放{len(actuals)}项；匹配预期只证明验收器按该用例判定，不证明被测系统全部通过。')
    r.case_results = actuals
    return r


def execute(args):
    if args.command == 'verify-result':
        context = read_json(args.context)
        return verify_result(read_json(args.result), context, read_json(args.receipt) if args.receipt else None,
                             args.allow_fixture, args.request_id or (context.get('expected_request_id') if isinstance(context, dict) else None))
    if args.command == 'verify-package':
        return verify_package(args.package, args.source, read_json(args.profile) if args.profile else None, args.mapping)
    if args.command == 'verify-delivery':
        return verify_delivery(args.input)
    if args.command == 'replay':
        return replay(args.case_dir, args.plan_sha256)
    if args.command == 'selftest':
        from selftest import run
        return run(args.workdir)
    raise InputError('COMMAND_UNKNOWN')


def main(argv=None):
    parser = argparse.ArgumentParser(description='离线现金流工件验收；不执行被测代码或平台动作')
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('verify-result'); p.add_argument('--result', required=True); p.add_argument('--context', required=True)
    p.add_argument('--receipt'); p.add_argument('--request-id'); p.add_argument('--allow-fixture', action='store_true')
    p = subs.add_parser('verify-package'); p.add_argument('--package', required=True); p.add_argument('--source'); p.add_argument('--profile'); p.add_argument('--mapping')
    p = subs.add_parser('verify-delivery'); p.add_argument('--input', required=True)
    p = subs.add_parser('replay'); p.add_argument('--case-dir', required=True); p.add_argument('--plan-sha256', required=True)
    p = subs.add_parser('selftest'); p.add_argument('--workdir', required=True)
    for p in subs.choices.values():
        p.add_argument('--output', help='全新输出目录；不填则只输出JSON摘要')
    args = parser.parse_args(argv)
    try:
        if args.output:
            dest = Path(args.output)
            for field in ('result', 'context', 'receipt', 'package', 'source', 'input', 'case_dir', 'mapping', 'profile'):
                value = getattr(args, field, None)
                if value:
                    src = Path(value).resolve()
                    boundary = src if src.is_dir() else src.parent
                    if dest.resolve().is_relative_to(boundary):
                        raise InputError('OUTPUT_INSIDE_SOURCE')
            if dest.exists():
                raise InputError('OUTPUT_EXISTS')
        report = execute(args)
        if args.output:
            write_reports(report, args.output)
            if hasattr(report, 'case_results'):
                (Path(args.output) / 'case-results.json').write_bytes(canonical(report.case_results))
        print(json.dumps(report.as_dict(), ensure_ascii=True))
        return report.exit_code
    except (InputError, OSError, KeyError, ValueError, TypeError, OverflowError, zipfile.BadZipFile, ET.ParseError) as exc:
        report = Report(args.command)
        code = str(exc) if isinstance(exc, InputError) else 'INPUT_INVALID_OR_UNSUPPORTED'
        report.add('失败', code, 'input', '有效可读取、未越界工件', '核格式/路径/大小；错误不是业务BLOCKED')
        print(json.dumps(report.as_dict(), ensure_ascii=True))
        return 1


if __name__ == '__main__':
    sys.exit(main())
