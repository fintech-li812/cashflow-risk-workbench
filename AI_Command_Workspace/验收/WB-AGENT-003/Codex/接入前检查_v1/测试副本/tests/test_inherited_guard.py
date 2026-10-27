import copy
import unittest
from agent_guard import validate_result, render_result, unavailable, ResultError

CTX = dict(tenant_id="fixture-tenant", company_id="fixture-company", period="2026-08",
           source_revision="fixture-rev-1", run_id="fixture-run-1")
def sample():
    return dict(CTX, schema_version="mfg-agent-result.v1", industry="manufacturing", status="success",
        origin="offline_fixture", unit="CNY", coverage="full_cashflow", calculation_version="fixture.v1",
        issues=[], source=dict(workbook_ref="synthetic-book", sheet="synthetic-result", range="A1:H2", snapshot_ref="fixture-snapshot"),
        amounts=dict(opening="100000.00", inflow="130000.00", outflow="90000.00", net="40000.00",
                     closing="140000.00", actual_closing="140000.00", difference="0.00"))
class GuardTests(unittest.TestCase):
    def reject(self, data, context=CTX):
        with self.assertRaises(ResultError):validate_result(data, context, allow_fixture=True)
    def test_fixture_requires_explicit_mode(self):
        with self.assertRaises(ResultError):validate_result(sample(), CTX)
    def test_success_fixture(self):
        self.assertIn("合成数据离线演示", render_result(sample(), CTX, allow_fixture=True))
    def test_context_identity_and_revision(self):
        for key in CTX:
            with self.subTest(key=key):
                d=sample();d[key]="other";self.reject(d)
    def test_missing_trusted_context(self):
        self.reject(sample(), {})
    def test_invalid_month(self):
        d=sample();d['period']='2026-13';c=dict(CTX, period='2026-13');self.reject(d,c)
    def test_non_manufacturing(self):
        d=sample();d['industry']='services';self.reject(d)
    def test_unknown_status(self):
        d=sample();d['status']='probably_ok';self.reject(d)
    def test_negative_gross(self):
        d=sample();d['amounts']['inflow']='-1.00';self.reject(d)
    def test_money_formats(self):
        for value in [0, False, None, 'NaN', 'Infinity', '1e3', '1.234', '01.00', '1000000000000000000.00']:
            with self.subTest(value=value):
                d=sample();d['amounts']['opening']=value;self.reject(d)
    def test_wrong_net(self):
        d=sample();d['amounts']['net']='41000.00';self.reject(d)
    def test_wrong_balance(self):
        d=sample();d['amounts']['closing']='150000.00';self.reject(d)
    def test_wrong_difference(self):
        d=sample();d['amounts']['difference']='10.00';self.reject(d)
    def test_unreconciled_actual_visible(self):
        d=sample();d['amounts'].update(actual_closing='139000.00',difference='-1000.00')
        text=render_result(d,CTX,allow_fixture=True)
        self.assertIn('-1000.00',text);self.assertIn('尚待核实',text)
    def test_missing_actual_not_zero(self):
        d=sample();d['amounts'].update(actual_closing=None,difference=None)
        self.assertIn('尚未完成余额核对',render_result(d,CTX,allow_fixture=True))
    def test_missing_actual_cannot_fake_zero_difference(self):
        d=sample();d['amounts']['actual_closing']=None;self.reject(d)
    def test_pending_algorithm_no_fake_success(self):
        d=unavailable(CTX);self.assertEqual(validate_result(d,CTX)['status'],'unavailable')
        self.assertIn('尚未绑定',render_result(d,CTX))
    def test_pending_cannot_contain_amounts(self):
        d=unavailable(CTX);d['amounts']=sample()['amounts'];self.reject(d)
    def test_success_cannot_hide_issues(self):
        d=sample();d['issues']=['missing opening'];self.reject(d)
    def test_coverage(self):
        d=sample();d['coverage']='operating_only';self.reject(d)
    def test_source_required(self):
        d=sample();d['source']['snapshot_ref']='';self.reject(d)
    def test_calculation_version_required(self):
        d=sample();d['calculation_version']='';self.reject(d)
    def test_no_nan_crash(self):
        for status in [[], {}, 3]:
            d=sample();d['status']=status;self.reject(d)
    def test_negative_balance_preserved(self):
        d=sample();d['amounts'].update(opening='10000.00',inflow='0.00',outflow='15000.00',net='-15000.00',closing='-5000.00',actual_closing=None,difference=None)
        self.assertIn('-5000.00',render_result(d,CTX,allow_fixture=True))
if __name__ == '__main__':unittest.main()
