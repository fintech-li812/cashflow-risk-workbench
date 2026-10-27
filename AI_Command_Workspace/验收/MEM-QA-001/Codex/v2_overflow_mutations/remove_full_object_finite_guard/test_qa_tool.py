"""Independent concrete fixtures and negative tests; never import author financial guards."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import qa_tool as q


def enc(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fixture():
    context = dict(tenant_id='test-tenant', company_id='test-company', period='2026-08',
                   source_revision='test-revision', run_id='test-run', expected_request_id='save-1',
                   actual_balance_provided=True, independent_actual_closing='140000.00')
    obj = {k: context[k] for k in q.CONTEXT}
    obj.update(schema_version='mfg-agent-result.v1', industry='manufacturing', status='success',
               origin='offline_fixture', unit='CNY', coverage='full_cashflow', calculation_version='test-only.v1',
               issues=[], source={'workbook_ref': 'synthetic', 'sheet': 'test', 'range': 'A1:H2', 'snapshot_ref': 's1'},
               amounts={'opening': '100000.00', 'inflow': '130000.00', 'outflow': '90000.00', 'net': '40000.00',
                        'closing': '140000.00', 'actual_closing': '140000.00', 'difference': '0.00'})
    receipt = {k: context[k] for k in q.CONTEXT}
    receipt.update(schema_version='mfg-evidence.v1', kind='receipt', operation='save_cashflow_result',
                   request_id='save-1', record_id='test-local-1', status='committed',
                   stored_at='2026-10-23T22:00:00+08:00', payload_sha256=sha(enc(obj)))
    return obj, context, receipt


def make_package(root):
    """Literal micro OOXML, not produced by the verifier's reader."""
    root.mkdir(); sources = root.parent / (root.name + '-sources'); sources.mkdir()
    file = sources / 'source.xlsx'
    with zipfile.ZipFile(file, 'w') as z:
        z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="现金流水" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="3"><c r="D3"><v>1.234567</v></c></row></sheetData></worksheet>')
    file_sha = sha(file.read_bytes())
    mapping = root.parent / (root.name + '-mapping.json')
    mapping.write_bytes(enc({'schema_version': 'mfg-qa-map.v1', 'fields': {'现金流水!D3': {'source_unit': '万元', 'unit': 'CNY', 'transform': 'yuan_half_up'}}}))
    inv = {'sources': [{'logical_name': 'source.xlsx', 'sha256': file_sha}], 'mapping_sha256': sha(mapping.read_bytes())}
    record = {'source_record_key': sha(enc({'source_file_sha256': file_sha, 'sheet': '现金流水', 'row': 3})),
              'record_type': 'cashflow', 'source_file_sha256': file_sha, 'sheet': '现金流水', 'row': 3,
              'cells': {'D3': {'cell_present': True, 'raw_type': 'n', 'raw_value': '1.234567', 'value': '1.234567', 'formula': None, 'formula_present': False, 'cache_present': True, 'cache_raw': '1.234567'}},
              'normalized': {'inflow': {'value': '12345.67', 'source_address': 'D3', 'source_unit': '万元', 'unit': 'CNY', 'transform': 'yuan_half_up'}}, 'issues': []}
    (root / 'inventory.json').write_bytes(enc(inv))
    (root / 'records.jsonl').write_bytes(enc(record) + b'\n')
    (root / 'issues.jsonl').write_bytes(b'')
    (root / 'report.html').write_text('<!doctype html><p>synthetic</p>', encoding='utf-8')
    manifest = dict(tenant_id='t', company_id='c', period='2026-08', run_id='r', source_revision=sha(enc(inv)),
                    schema_version='mfg-import.v1', kind='import_package', unit='CNY', tool_version='test.1', mapping_version='test.1')
    rewrite_manifest(root, manifest)
    return sources, mapping, record


def rewrite_manifest(root, manifest=None):
    if manifest is None:
        manifest = json.loads((root / 'manifest.json').read_bytes())
    manifest['files'] = []
    for name in ('inventory.json', 'records.jsonl', 'issues.jsonl', 'report.html'):
        data = (root / name).read_bytes()
        manifest['files'].append({'path': name, 'sha256': sha(data), 'record_count': len(data.splitlines()) if name.endswith('.jsonl') else 0})
    (root / 'manifest.json').write_bytes(enc(manifest))


def replay_plan(root, cases):
    root.mkdir()
    plan = {'schema_version': 'mfg-qa-replay.v1', 'cases': []}
    for case_id, obj, ctx, receipt, status, codes in cases:
        item = {'id': case_id, 'operation': 'verify-result', 'allow_fixture': True, 'files': {}, 'expected': {'status': status, 'codes': codes}}
        for kind, value in [('result', obj), ('context', ctx), ('receipt', receipt)]:
            if value is None:
                continue
            name = case_id + '-' + kind + '.json'; data = enc(value)
            (root / name).write_bytes(data); item[kind] = name; item['files'][name] = sha(data)
        plan['cases'].append(item)
    data = enc(plan); (root / 'cases.json').write_bytes(data)
    return sha(data)


def make_delivery(root):
    root.mkdir()
    for name, data in [('README.md', b'Candidate offline QA'), ('tests/test.txt', b'independent case'), ('expected/golden.json', b'{"net":"40000.00"}'), ('test-output/actual.json', b'{"net":"40000.00"}')]:
        p = root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    manifest = dict(task_id='test', package_version='v1', author='synthetic', status='candidate', files=[])
    for f in root.rglob('*'):
        if f.is_file():
            manifest['files'].append({'path': f.relative_to(root).as_posix(), 'sha256': sha(f.read_bytes())})
    (root / 'manifest.json').write_bytes(enc(manifest))
    lines = [sha(f.read_bytes()) + '  ' + f.relative_to(root).as_posix() for f in sorted(root.rglob('*')) if f.is_file()]
    (root / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def replace_sheet(file, data):
    # Keep original generated micro-XLSX evidence and write only a new synthetic file.
    target = file.with_name('modified-source.xlsx')
    with zipfile.ZipFile(file) as old, zipfile.ZipFile(target, 'w') as new:
        for item in old.infolist():
            new.writestr(item.filename, data if item.filename == 'xl/worksheets/sheet1.xml' else old.read(item.filename))
    return target


class QA(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName + '-', dir=TEST_ROOT if TEST_ROOT else Path(__file__).parent))
        self.obj, self.context, self.receipt = fixture()

    def tearDown(self):
        # Preserve synthetic failure evidence; no permanent-delete cleanup logic.
        pass

    def check_result(self, code=None, **kw):
        report = q.verify_result(self.obj, self.context, kw.pop('receipt', None), kw.pop('allow_fixture', True), self.context.get('expected_request_id'))
        if code is None:
            self.assertEqual(report.status, '通过', report.as_dict())
        else:
            self.assertEqual(report.status, '失败', report.as_dict())
            self.assertIn(code, {x['code'] for x in report.issues})
        return report

    def test_result_valid_synthetic(self):
        self.check_result()

    def test_fixture_default_rejected(self):
        self.check_result('FIXTURE_IN_PRODUCTION', allow_fixture=False)

    def test_claimed_platform_is_not_attested(self):
        self.obj['origin'] = 'qwen_sheet'
        report = q.verify_result(self.obj, self.context)
        self.assertEqual(report.status, '阻塞')
        self.assertIn('PLATFORM_PROVENANCE_UNVERIFIED', {v['code'] for v in report.issues})

    def test_each_context_dimension(self):
        for name in q.CONTEXT:
            with self.subTest(name=name):
                obj = copy.deepcopy(self.obj); obj[name] = '2026-09' if name == 'period' else 'other'
                report = q.verify_result(obj, self.context, allow_fixture=True)
                self.assertEqual(report.status, '失败')
                self.assertIn('CONTEXT_MISMATCH', {v['code'] for v in report.issues})

    def test_empty_context_and_invalid_period(self):
        self.obj['period'] = '2026-13'
        self.check_result('PERIOD_INVALID')

    def test_one_cent_net_error(self):
        self.obj['amounts']['net'] = '40000.01'
        self.check_result('NET_MISMATCH')

    def test_closing_error(self):
        self.obj['amounts']['closing'] = '140000.01'
        self.check_result('CLOSING_MISMATCH')

    def test_difference_direction(self):
        self.obj['amounts']['actual_closing'] = '139000.00'; self.obj['amounts']['difference'] = '1000.00'
        self.context['independent_actual_closing'] = '139000.00'
        self.check_result('DIFFERENCE_MISMATCH')

    def test_each_nonfinite_or_invalid_money(self):
        for value in ['NaN', 'Infinity', '+Infinity', '-Infinity', '', 'bad', 1.0, True, '12345.678', '01.00', None, '9' * 19 + '.00']:
            with self.subTest(value=value):
                obj = copy.deepcopy(self.obj); obj['amounts']['opening'] = value
                r = q.verify_result(obj, self.context, allow_fixture=True)
                self.assertEqual(r.status, '失败')
                self.assertIn('MONEY_INVALID', {v['code'] for v in r.issues})

    def test_true_zero_is_valid(self):
        self.obj['amounts'] = {k: '0.00' for k in self.obj['amounts']}
        self.context['independent_actual_closing'] = '0.00'
        self.check_result()

    def test_missing_actual_balance_is_not_zero(self):
        self.obj['amounts']['actual_closing'] = None; self.obj['amounts']['difference'] = None
        self.context['actual_balance_provided'] = False; self.context.pop('independent_actual_closing')
        report = self.check_result()
        self.assertTrue(any('未完成' in n for n in report.notes))

    def test_fake_zero_actual_when_not_supplied(self):
        self.obj['amounts'] = {k: '0.00' for k in self.obj['amounts']}
        self.context['actual_balance_provided'] = False; self.context.pop('independent_actual_closing')
        self.check_result('INVENTED_ACTUAL_BALANCE')

    def test_null_pair_mismatch(self):
        self.obj['amounts']['actual_closing'] = None
        self.check_result('RECONCILIATION_NULL_PAIR')

    def test_missing_actual_key_not_silently_nullable(self):
        self.obj['amounts'].pop('actual_closing')
        self.check_result('AMOUNT_MISSING')

    def test_operating_only_not_full_success(self):
        self.obj['coverage'] = 'operating_only'
        self.check_result('COVERAGE')

    def test_missing_formula_version(self):
        self.obj['calculation_version'] = ''
        self.check_result('CALCULATION_VERSION')

    def test_unavailable_with_fake_amounts(self):
        self.obj['status'] = 'unavailable'; self.obj['issues'] = ['not-bound']
        self.check_result('FAILED_WITH_AMOUNTS')

    def test_valid_unavailable_has_no_amounts(self):
        self.obj['status'] = 'unavailable'; self.obj['issues'] = ['not-bound']; self.obj['amounts'] = None
        self.check_result()

    def test_unavailable_without_success_only_unit(self):
        self.obj['status'] = 'unavailable'; self.obj['issues'] = ['not-bound']; self.obj['amounts'] = None; self.obj.pop('unit')
        self.check_result()

    def test_non_success_reason_must_be_nonempty_text(self):
        self.obj['status'] = 'unavailable'; self.obj['issues'] = [None]; self.obj['amounts'] = None
        self.check_result('ISSUES_TYPE')

    def test_extra_prediction_amount_not_accepted_as_cashflow(self):
        self.obj['amounts']['forecast'] = '1.00'
        self.check_result('AMOUNT_FIELDS')

    def test_receipt_for_failure_is_rejected(self):
        self.obj['status'] = 'formula_error'; self.obj['issues'] = ['error']; self.obj['amounts'] = None
        self.check_result('RECEIPT_FOR_FAILURE', receipt=self.receipt)

    def test_unit_mixed(self):
        self.obj['unit'] = '万元'; self.check_result('UNIT')

    def test_valid_receipt(self):
        self.check_result(receipt=self.receipt)

    def test_committed_receipt_wrong_payload(self):
        self.receipt['payload_sha256'] = '0' * 64
        self.check_result('RECEIPT_HASH', receipt=self.receipt)

    def test_receipt_other_company(self):
        self.receipt['company_id'] = 'other'
        self.check_result('RECEIPT_CONTEXT', receipt=self.receipt)

    def test_receipt_other_request(self):
        self.receipt['request_id'] = 'other'
        self.check_result('RECEIPT_REQUEST', receipt=self.receipt)

    def test_receipt_requires_independent_request(self):
        r = q.verify_result(self.obj, self.context, self.receipt, True)
        self.assertEqual(r.status, '阻塞')

    def test_receipt_timestamp_requires_zone(self):
        self.receipt['stored_at'] = '2026-10-23T22:00:00'
        self.check_result('RECEIPT_TIME', receipt=self.receipt)

    def test_negative_closing_valid(self):
        self.obj['amounts'] = dict(opening='10000.00', inflow='0.00', outflow='15000.00', net='-15000.00', closing='-5000.00', actual_closing=None, difference=None)
        self.context.pop('independent_actual_closing')
        self.check_result()

    def test_strict_json_duplicate_and_nonfinite(self):
        for raw in [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}']:
            with self.subTest(raw=raw), self.assertRaises(q.InputError):
                q.parse_json(raw)

    def test_json_exponent_overflow_rejected_in_extra_field(self):
        for raw in (b'{"extra":1e999}', b'{"extra":-1e999}'):
            with self.subTest(raw=raw), self.assertRaises(q.InputError):
                q.parse_json(raw)
        self.assertEqual(q.parse_json(b'{"finite_metadata":1.25}'), {'finite_metadata': 1.25})
        rp, cp = self.root / 'r.json', self.root / 'c.json'
        rp.write_bytes(enc(self.obj)[:-1] + b',"extra":1e999}')
        cp.write_bytes(enc(self.context))
        with contextlib.redirect_stdout(io.StringIO()):
            code = q.main(['verify-result', '--result', str(rp), '--context', str(cp), '--allow-fixture'])
        self.assertEqual(code, 1)

    def test_direct_library_api_cannot_hide_nonfinite_extras(self):
        for target in ('result', 'context', 'receipt'):
            with self.subTest(target=target):
                obj, context, receipt = fixture()
                {'result': obj, 'context': context, 'receipt': receipt}[target]['hidden'] = float('inf')
                report = q.verify_result(obj, context, receipt, True, 'save-1')
                self.assertEqual(report.status, '失败')
                self.assertIn('JSON_UNSAFE', {v['code'] for v in report.issues})

    def test_path_traversal_windows_aliases(self):
        for name in ['../x', '/x', 'D:/x', 'a\\x', 'a//x', './x', 'a/../x', 'NUL.txt', 'a./b', 'a /b', 'x:stream', 'a\x00b']:
            with self.subTest(name=name), self.assertRaises(q.InputError):
                q.inside(self.root, name)

    def test_package_positive_source_and_conversion(self):
        source, mapping, _ = make_package(self.root / 'package')
        r = q.verify_package(self.root / 'package', source, {'schema_version': 'mfg-qa-ooxml-profile.v1'}, mapping)
        self.assertEqual(r.status, '通过', r.as_dict())

    def test_package_no_source_cannot_authenticate(self):
        make_package(self.root / 'package')
        r = q.verify_package(self.root / 'package')
        self.assertEqual(r.status, '阻塞')

    def test_package_tamper_and_rehash_still_found(self):
        package = self.root / 'package'; source, mapping, record = make_package(package)
        record['cells']['D3']['value'] = '2.000000'
        (package / 'records.jsonl').write_bytes(enc(record) + b'\n'); rewrite_manifest(package)
        r = q.verify_package(package, source, {'schema_version': 'mfg-qa-ooxml-profile.v1'}, mapping)
        self.assertEqual(r.status, '失败'); self.assertIn('SOURCE_CELL_MISMATCH', {v['code'] for v in r.issues})

    def test_package_unit_lie_rejected_by_mapping(self):
        package = self.root / 'package'; source, mapping, record = make_package(package)
        record['normalized']['inflow'].update(source_unit='元', value='1.23')
        (package / 'records.jsonl').write_bytes(enc(record) + b'\n'); rewrite_manifest(package)
        r = q.verify_package(package, source, {'schema_version': 'mfg-qa-ooxml-profile.v1'}, mapping)
        self.assertIn('UNIT_MAPPING_MISMATCH', {v['code'] for v in r.issues}); self.assertEqual(r.status, '失败')

    def test_package_conversion_rounding_loses_precision(self):
        package = self.root / 'package'; source, mapping, record = make_package(package)
        record['normalized']['inflow']['value'] = '12300.00'
        (package / 'records.jsonl').write_bytes(enc(record) + b'\n'); rewrite_manifest(package)
        r = q.verify_package(package, source, {'schema_version': 'mfg-qa-ooxml-profile.v1'}, mapping)
        self.assertIn('NORMALIZATION_VALUE', {v['code'] for v in r.issues})

    def test_package_hash_tamper(self):
        package = self.root / 'package'; make_package(package)
        (package / 'report.html').write_text('changed', encoding='utf-8')
        r = q.verify_package(package)
        self.assertEqual(r.status, '失败'); self.assertIn('FILE_HASH', {v['code'] for v in r.issues})

    def test_package_path_escape(self):
        package = self.root / 'package'; make_package(package)
        obj = json.loads((package / 'manifest.json').read_bytes()); obj['files'][0]['path'] = '../outside.json'
        (package / 'manifest.json').write_bytes(enc(obj))
        with self.assertRaises(q.InputError):
            q.verify_package(package)

    def test_package_record_count(self):
        package = self.root / 'package'; make_package(package)
        obj = json.loads((package / 'manifest.json').read_bytes()); obj['files'][1]['record_count'] = 2
        (package / 'manifest.json').write_bytes(enc(obj)); r = q.verify_package(package)
        self.assertIn('RECORD_COUNT', {v['code'] for v in r.issues})

    def test_excel_grid_address_limits(self):
        self.assertTrue(q.valid_address('XFD1048576', 1048576))
        for address, row in [('XFE1', 1), ('A1048577', 1048577), ('A0', 0), ('D3', 4)]:
            with self.subTest(address=address):
                self.assertFalse(q.valid_address(address, row))

    def test_year_zero_rejected(self):
        self.obj['period'] = '0000-01'
        self.check_result('PERIOD_INVALID')

    def test_zip_escape_is_not_extracted(self):
        path = self.root / 'escape.zip'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('../escaped.txt', 'evil')
        with self.assertRaises(q.InputError):
            q.verify_delivery(path)
        self.assertFalse((self.root.parent / 'escaped.txt').exists())

    def test_zip_duplicate_alias_rejected(self):
        path = self.root / 'duplicate.zip'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('README.md', 'a'); z.writestr('readme.md', 'b')
        with self.assertRaises(q.InputError):
            q.verify_delivery(path)

    def test_report_html_csv_injection(self):
        r = q.Report('synthetic'); r.add('失败', 'TEST', '=HYPERLINK("x")<script>alert(1)</script>', '<img src=x onerror=x>', 'fix')
        out = self.root / 'report'; q.write_reports(r, out)
        page = (out / 'report.html').read_text(encoding='utf-8')
        self.assertNotIn('<script>', page); self.assertIn('&lt;script&gt;', page)
        parsed = list(__import__('csv').DictReader(io.StringIO((out / 'issues.csv').read_text(encoding='utf-8-sig'))))
        self.assertTrue(parsed[0]['location'].startswith("'="))
        self.assertIn('default-src', page)

    def test_existing_output_is_not_overwritten(self):
        out = self.root / 'out'; out.mkdir(); (out / 'keep').write_text('original')
        with self.assertRaises(q.InputError):
            q.write_reports(q.Report('test'), out)
        self.assertEqual((out / 'keep').read_text(), 'original')

    def test_cli_failed_result_has_nonzero_exit(self):
        self.obj['amounts']['net'] = '40000.01'
        rp, cp = self.root / 'r.json', self.root / 'c.json'; rp.write_bytes(enc(self.obj)); cp.write_bytes(enc(self.context))
        with contextlib.redirect_stdout(io.StringIO()):
            code = q.main(['verify-result', '--result', str(rp), '--context', str(cp), '--allow-fixture'])
        self.assertEqual(code, 1)

    def test_cli_output_inside_source_is_rejected(self):
        rp, cp = self.root / 'r.json', self.root / 'c.json'; rp.write_bytes(enc(self.obj)); cp.write_bytes(enc(self.context))
        with contextlib.redirect_stdout(io.StringIO()):
            code = q.main(['verify-result', '--result', str(rp), '--context', str(cp), '--allow-fixture', '--output', str(self.root / 'inside')])
        self.assertEqual(code, 1); self.assertFalse((self.root / 'inside').exists())

    def test_replay_matches_frozen_positive_negative(self):
        bad = copy.deepcopy(self.obj); bad['amounts']['net'] = '40000.01'
        case_dir = self.root / 'cases'; sha_plan = replay_plan(case_dir, [('ok', self.obj, self.context, None, '通过', []), ('bad', bad, self.context, None, '失败', ['NET_MISMATCH'])])
        before = {p.name: sha(p.read_bytes()) for p in case_dir.iterdir()}
        r = q.replay(case_dir, sha_plan)
        self.assertEqual(r.status, '通过', r.as_dict()); self.assertEqual(len(r.case_results), 2)
        self.assertEqual(before, {p.name: sha(p.read_bytes()) for p in case_dir.iterdir()})

    def test_replay_wrong_plan_hash_rejected(self):
        cases = self.root / 'cases'; replay_plan(cases, [('ok', self.obj, self.context, None, '通过', [])])
        r = q.replay(cases, '0' * 64)
        self.assertEqual(r.status, '失败')

    def test_replay_input_tamper_is_not_blocked(self):
        cases = self.root / 'cases'; sha_plan = replay_plan(cases, [('ok', self.obj, self.context, None, '通过', [])])
        (cases / 'ok-result.json').write_text('{}')
        with self.assertRaises(q.InputError):
            q.replay(cases, sha_plan)

    def test_replay_same_request_different_payload(self):
        other = copy.deepcopy(self.obj); other['amounts']['actual_closing'] = '139000.00'; other['amounts']['difference'] = '-1000.00'
        ctx2 = copy.deepcopy(self.context); ctx2['independent_actual_closing'] = '139000.00'
        rc2 = copy.deepcopy(self.receipt); rc2['payload_sha256'] = sha(enc(other)); rc2['record_id'] = 'test-local-2'
        cases = self.root / 'cases'; pinned = replay_plan(cases, [('first', self.obj, self.context, self.receipt, '通过', []), ('second', other, ctx2, rc2, '失败', ['IDEMPOTENCE_CONFLICT'])])
        r = q.replay(cases, pinned)
        self.assertEqual(r.status, '通过', r.as_dict())

    def test_replay_detects_runtime_mutation(self):
        cases = self.root / 'cases'; pinned = replay_plan(cases, [('ok', self.obj, self.context, None, '通过', [])])
        original = q.verify_result
        def mutation(*args, **kwargs):
            (cases / 'ok-result.json').write_text('{}')
            return original(*args, **kwargs)
        with patch.object(q, 'verify_result', mutation):
            r = q.replay(cases, pinned)
        self.assertEqual(r.status, '失败'); self.assertIn('REPLAY_INPUT_CHANGED', {v['code'] for v in r.issues})

    def test_delivery_missing_evidence_not_pass(self):
        path = self.root / 'delivery'; path.mkdir(); (path / 'README.md').write_text('test')
        r = q.verify_delivery(path)
        self.assertEqual(r.status, '失败')

    def test_complete_delivery_only_blocks_execution_not_falsely_pass(self):
        path = self.root / 'delivery'; make_delivery(path)
        r = q.verify_delivery(path)
        self.assertEqual(r.status, '阻塞', r.as_dict())
        self.assertEqual({v['code'] for v in r.issues}, {'EXECUTION_NOT_OBSERVED'})

    def test_delivery_manifest_mismatch_not_hidden_by_correct_hash_list(self):
        path = self.root / 'delivery'; make_delivery(path)
        doc = json.loads((path / 'manifest.json').read_bytes()); doc['files'][0]['sha256'] = '0' * 64
        (path / 'manifest.json').write_bytes(enc(doc))
        lines = [sha(f.read_bytes()) + '  ' + f.relative_to(path).as_posix() for f in sorted(path.rglob('*')) if f.is_file() and f.name != 'SHA256SUMS.txt']
        (path / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        r = q.verify_delivery(path)
        self.assertEqual(r.status, '失败'); self.assertIn('DELIVERY_MANIFEST_HASH', {v['code'] for v in r.issues})

    def test_delivery_zip_profile_checks(self):
        path = self.root / 'delivery'; make_delivery(path); archive = self.root / 'candidate.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for f in path.rglob('*'):
                if f.is_file():
                    z.write(f, f.relative_to(path).as_posix())
        self.assertEqual(q.verify_delivery(archive).status, '阻塞')

    def test_zip_symlink_entry_rejected_without_extraction(self):
        archive = self.root / 'links.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            info = zipfile.ZipInfo('link'); info.create_system = 3; info.external_attr = (0o120777 << 16)
            z.writestr(info, '../outside')
        with self.assertRaises(q.InputError):
            q.verify_delivery(archive)

    def test_package_wrong_source_revision(self):
        package = self.root / 'package'; source, mapping, _ = make_package(package)
        doc = json.loads((package / 'manifest.json').read_bytes()); doc['source_revision'] = 'old-version'
        (package / 'manifest.json').write_bytes(enc(doc))
        r = q.verify_package(package, source, {'schema_version': 'mfg-qa-ooxml-profile.v1'}, mapping)
        self.assertIn('SOURCE_REVISION', {v['code'] for v in r.issues})

    def test_package_issue_reference_must_exist(self):
        package = self.root / 'package'; source, mapping, row = make_package(package)
        row['issues'] = ['missing-issue']; (package / 'records.jsonl').write_bytes(enc(row) + b'\n'); rewrite_manifest(package)
        r = q.verify_package(package, source, {'schema_version': 'mfg-qa-ooxml-profile.v1'}, mapping)
        self.assertIn('ISSUE_REFERENCE', {v['code'] for v in r.issues})

    def test_package_record_stable_key_must_match_source(self):
        package = self.root / 'package'; source, mapping, row = make_package(package)
        row['source_record_key'] = '0' * 64; (package / 'records.jsonl').write_bytes(enc(row) + b'\n'); rewrite_manifest(package)
        r = q.verify_package(package, source, {'schema_version': 'mfg-qa-ooxml-profile.v1'}, mapping)
        self.assertIn('RECORD_KEY', {v['code'] for v in r.issues})

    def test_unknown_profile_is_blocked_not_assumed(self):
        package = self.root / 'package'; source, mapping, _ = make_package(package)
        r = q.verify_package(package, source, {'schema_version': 'future-adapter'}, mapping)
        self.assertEqual(r.status, '阻塞'); self.assertIn('SOURCE_ADAPTER_NOT_SELECTED', {v['code'] for v in r.issues})

    def test_missing_mapping_is_blocked(self):
        package = self.root / 'package'; source, _, _ = make_package(package)
        r = q.verify_package(package, source, {'schema_version': 'mfg-qa-ooxml-profile.v1'})
        self.assertEqual(r.status, '阻塞'); self.assertIn('MAPPING_NOT_PROVIDED', {v['code'] for v in r.issues})

    def test_mapping_changed_detected(self):
        package = self.root / 'package'; source, mapping, _ = make_package(package)
        mapping.write_text('{"schema_version":"changed"}', encoding='utf-8')
        r = q.verify_package(package, source, {'schema_version': 'mfg-qa-ooxml-profile.v1'}, mapping)
        self.assertEqual(r.status, '失败'); self.assertIn('MAPPING_HASH', {v['code'] for v in r.issues})

    def test_explicit_unit_uncertainty_must_stay_null(self):
        package = self.root / 'package'; source, mapping, _ = make_package(package)
        doc = json.loads(mapping.read_bytes()); doc['fields']['现金流水!D3']['blocked'] = True; mapping.write_bytes(enc(doc))
        inv = json.loads((package / 'inventory.json').read_bytes()); inv['mapping_sha256'] = sha(mapping.read_bytes()); (package / 'inventory.json').write_bytes(enc(inv))
        manifest = json.loads((package / 'manifest.json').read_bytes()); manifest['source_revision'] = sha(enc(inv)); rewrite_manifest(package, manifest)
        r = q.verify_package(package, source, {'schema_version': 'mfg-qa-ooxml-profile.v1'}, mapping)
        self.assertIn('UNIT_UNRESOLVED', {v['code'] for v in r.issues})

    def test_ooxml_empty_formula_is_still_formula(self):
        package = self.root / 'package'; source, _, _ = make_package(package)
        file = replace_sheet(source / 'source.xlsx', b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="3"><c r="D3"><f t="shared" si="0"/><v>1.23</v></c></row></sheetData></worksheet>')
        cells = q.ooxml_cells(file, '现金流水')
        self.assertTrue(cells['D3']['formula_present']); self.assertIsNone(cells['D3']['formula'])

    def test_ooxml_entities_rejected(self):
        package = self.root / 'package'; source, _, _ = make_package(package)
        file = replace_sheet(source / 'source.xlsx', b'<!DOCTYPE worksheet [<!ENTITY x "boom">]><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>')
        with self.assertRaises(q.InputError):
            q.ooxml_cells(file, '现金流水')

    def test_ooxml_utf16_entities_rejected(self):
        package = self.root / 'package'; source, _, _ = make_package(package)
        text = '<?xml version="1.0" encoding="utf-16"?><!DOCTYPE worksheet [<!ENTITY x "boom">]><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>'
        file = replace_sheet(source / 'source.xlsx', text.encode('utf-16'))
        with self.assertRaises(q.InputError):
            q.ooxml_cells(file, '现金流水')

    def test_cli_invalid_json_has_nonzero_and_no_traceback(self):
        obj = self.root / 'bad.json'; obj.write_text('{bad')
        context = self.root / 'context.json'; context.write_bytes(enc(self.context)); captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = q.main(['verify-result', '--result', str(obj), '--context', str(context)])
        self.assertEqual(code, 1); self.assertNotIn('Traceback', captured.getvalue())

    def test_replay_cannot_turn_wrong_outcome_into_match(self):
        bad = copy.deepcopy(self.obj); bad['amounts']['net'] = '40000.01'
        cases = self.root / 'cases'; pinned = replay_plan(cases, [('incorrect-expectation', bad, self.context, None, '通过', [])])
        self.assertEqual(q.replay(cases, pinned).status, '失败')


TEST_ROOT = None

if __name__ == '__main__':
    unittest.main(verbosity=2)
