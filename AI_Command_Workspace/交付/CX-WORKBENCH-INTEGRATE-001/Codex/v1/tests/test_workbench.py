import hashlib,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
import workbench
from qa_entry import environment

class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before=hashlib.sha256(workbench.SOURCE_PATH.read_bytes()).hexdigest()
        cls.inspected=workbench.inspect_source()
    @classmethod
    def tearDownClass(cls):
        assert cls.before==hashlib.sha256(workbench.SOURCE_PATH.read_bytes()).hexdigest()
    def test_only_registered_manufacturing_source(self):
        data=workbench.list_sources();self.assertEqual(len(data['sources']),1)
        self.assertFalse(data['other_industries_enabled']);self.assertFalse(data['sources'][0]['native_qwen_workbook'])
    def test_invalid_source_cannot_be_arbitrary_path(self):
        for name in ('../secret','D:/','retail',''):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'not_registered'):workbench.inspect_source(name)
    def test_changed_source_stops_before_parse(self):
        with patch.object(workbench,'SOURCE_SHA256','0'*64),self.assertRaisesRegex(ValueError,'requires_rebinding'):workbench.inspect_source()
    def test_missing_file_reports_unavailable_not_empty_success(self):
        with patch.object(workbench,'SOURCE_PATH',ROOT/'not-a-source.bin'):
            self.assertEqual(workbench.list_sources()['sources'][0]['status'],'unavailable')
            with self.assertRaisesRegex(ValueError,'unavailable'):workbench.inspect_source()
    def test_fake_workbook_does_not_get_unit_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'file.bin';file.write_bytes(b'not the approved source')
            with patch.object(workbench,'SOURCE_PATH',file),self.assertRaisesRegex(ValueError,'requires_rebinding'):workbench.readiness()
    def test_actual_eight_sheets(self):
        self.assertEqual(len(self.inspected['sheet_names']),8)
        self.assertIn('现金流水',self.inspected['sheet_names']);self.assertIn('筹资信息',self.inspected['sheet_names'])
    def test_read_scope_explicit(self):
        self.assertEqual(self.inspected['blocks']['企业基本信息']['range'],'A1:C10')
        self.assertEqual(self.inspected['blocks']['现金流水']['range'],'A1:I15')
        self.assertFalse(self.inspected['formula_execution_performed']);self.assertFalse(self.inspected['money_conversion_performed'])
    def test_original_unit_suspect_is_preserved(self):
        cell=self.inspected['blocks']['现金流水']['cells']['D8']
        self.assertEqual(cell['value'],'1631300');self.assertEqual(cell['raw_xml_value'],'1631300')
        self.assertFalse(cell['has_formula'])
    def test_date_system_is_not_guessed_from_strings(self):self.assertEqual(self.inspected['date_system'],'1900')
    def test_duplicate_original_rows_are_both_read(self):
        cells=self.inspected['blocks']['现金流水']['cells']
        self.assertEqual([cells[f'{c}12']['value'] for c in 'ABCDEFGHI'],[cells[f'{c}15']['value'] for c in 'ABCDEFGHI'])
    def test_known_flags_are_not_gate_results(self):
        data=workbench.readiness();codes={x['code'] for x in data['issues']}
        self.assertIn('unit_confirmation_required',codes);self.assertIn('duplicate_rows_preserved',codes)
        self.assertFalse(data['gate_rules_executed']);self.assertFalse(data['normal_partial_receipts_treated_as_errors'])
    def test_missing_source_inputs_never_return_financial_success(self):
        data=workbench.readiness();self.assertEqual(data['status'],'blocked');self.assertNotIn('amounts',data)
        self.assertFalse(data['can_claim_full_cashflow']);self.assertFalse(data['can_save_source_result'])
    def test_native_recalc_and_independent_balance_are_explicit(self):
        codes={x['code'] for x in workbench.readiness()['issues']}
        self.assertTrue({'native_recalculation_not_bound','independent_closing_not_bound','full_cashflow_mapping_incomplete'}.issubset(codes))
    def test_failed_database_probe_is_not_reported_connected(self):
        with patch.dict(os.environ,environment(),clear=False),patch.object(workbench.Service,'connect',side_effect=OSError('private info')):
            status=workbench.project_status()
        self.assertEqual(status['components']['database'],'unavailable');self.assertNotIn('private info',str(status))
    def test_fixture_and_inspected_workbook_not_merged(self):
        with patch.dict(os.environ,environment(),clear=False),patch.object(workbench.Service,'connect',side_effect=OSError()):
            status=workbench.project_status()
        self.assertEqual(status['result_profile']['origin'],'offline_fixture')
        self.assertTrue(status['financial_result_source_is_separate_from_inspected_workbook'])
        self.assertFalse(status['production_deployed'])

if __name__=='__main__':unittest.main(verbosity=2,failfast=True)
