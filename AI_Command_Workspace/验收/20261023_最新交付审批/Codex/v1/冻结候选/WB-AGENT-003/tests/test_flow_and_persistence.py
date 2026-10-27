"""WB-AGENT-003 独立测试：流程 + 保存回执 + 六项打回红线。

覆盖 333.md E 项列出的 11 类场景。所有用例使用明确标识的合成夹具；
生产路径不允许夹具泄漏（由 test_fixture_never_leaks_to_production 等用例断言）。
失败即以非 0 退出，不重写独立预期。
"""
import copy
import unittest

from runtime_adapter import (Binding, CAP_SAVE_RESULT, COMMITTED, CONFLICT, NOT_FOUND,
                             PENDING, UNAVAILABLE, UnboundBackend, canonical_sha256,
                             save_result)
from request_flow import (RequestFlow, FlowBlocked, blocked_report, pre_guard_amounts,
                          validate_binding)
from persistence import (MemoryEvidenceStore, NoQueryCapabilityStore, READ_ONLY_CHECK_STEPS,
                         build_save_payload, retry_after_timeout)
from adapters import OfflineFixtureBackend, FIXTURE_RESULT

CTX = dict(tenant_id="t-1", company_id="c-1", period="2026-08",
           source_revision="rev-1", run_id="run-1")


def binding(**over):
    return Binding(**dict(CTX, **over))


class CountingBackend(OfflineFixtureBackend):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.calls = 0

    def read_calculated_result(self, b, snapshot):
        self.calls += 1
        return super().read_calculated_result(b, snapshot)


class SnapshotOnlyBackend(OfflineFixtureBackend):
    """快照可读、算法未就绪：用于精确表达"算法未绑定"而不是"读表未绑定"。"""

    def read_calculated_result(self, b, snapshot):
        from runtime_adapter import (Outcome, UNAVAILABLE, MISSING_ALGORITHM,
                                     MANUAL_RESULT_STEPS)
        return Outcome(capability="read_calculated_result", status=UNAVAILABLE, payload=None,
                       missing=["algorithm:主算法或表格公式适配器", "calculation_version"],
                       reason=MISSING_ALGORITHM, evidence_steps=MANUAL_RESULT_STEPS)


class FixedResultBackend(OfflineFixtureBackend):
    """返回指定 result（不按 binding 覆盖身份字段），用于身份不一致等负例。"""

    def __init__(self, result, **kw):
        super().__init__(result=result, **kw)
        self._result = result

    def read_calculated_result(self, b, snapshot):
        blocked = self._guard("read_calculated_result")
        if blocked:
            return blocked
        from runtime_adapter import Outcome
        return Outcome(capability="read_calculated_result", status="ok",
                       payload=copy.deepcopy(self._result), missing=[], reason="",
                       evidence_steps=[])

    def save_result(self, b, result, request_id):
        blocked = self._guard("save_result")
        if blocked:
            return blocked
        return self.store.commit(b, result, request_id)

    def query_saved_result(self, b, request_id):
        blocked = self._guard("query_saved_result")
        if blocked:
            return blocked
        return self.store.query(b, request_id)


class FlowTests(unittest.TestCase):
    def test_01_normal_success(self):
        backend = OfflineFixtureBackend(allow_fixture=True)
        flow = RequestFlow(backend)
        out = flow.run(binding(), allow_fixture=True)
        self.assertTrue(out.ok)
        self.assertIn("合成数据离线演示", out.text)
        self.assertEqual(out.stage, "done")

    def test_02_missing_input_binding(self):
        flow = RequestFlow(OfflineFixtureBackend(allow_fixture=True))
        for key in CTX:
            with self.subTest(field=key):
                over = {key: "   "}
                with self.assertRaises(FlowBlocked) as cm:
                    flow.run(binding(**over))
                self.assertEqual(cm.exception.stage, "bind")
                self.assertIn(key, " ".join(cm.exception.outcome.missing))

    def test_03_amount_and_unit_errors(self):
        bad_values = ["1e3", "NaN", "Infinity", "12.345", "01.00", "1631300.00万元",
                      "1000000000000000000.00", 12345, None]
        for value in bad_values:
            with self.subTest(value=value):
                result = copy.deepcopy(FIXTURE_RESULT)
                result.update(binding().as_dict())
                result["amounts"]["opening"] = value
                problems = pre_guard_amounts(result)
                if not problems:
                    backend = FixedResultBackend(result, allow_fixture=True)
                    with self.assertRaises(FlowBlocked) as cm:
                        RequestFlow(backend).run(binding(), allow_fixture=True)
                    self.assertEqual(cm.exception.stage, "guard")
                else:
                    self.assertTrue(any("opening" in p for p in problems))

    def test_04_source_revision_stale_invalidates(self):
        backend = CountingBackend(allow_fixture=True)
        flow = RequestFlow(backend)
        out1 = flow.run(binding(source_revision="rev-1"), allow_fixture=True)
        self.assertTrue(out1.ok)
        self.assertEqual(backend.calls, 1)
        flow.run(binding(source_revision="rev-1"), allow_fixture=True)
        self.assertEqual(backend.calls, 1)
        out3 = flow.run(binding(source_revision="rev-2"), allow_fixture=True)
        self.assertTrue(out3.invalidated)
        self.assertEqual(backend.calls, 2)

    def test_05_company_mismatch_rejected(self):
        result = copy.deepcopy(FIXTURE_RESULT)
        result.update(binding().as_dict())
        result["company_id"] = "other-company"
        backend = FixedResultBackend(result, allow_fixture=True)
        with self.assertRaises(FlowBlocked) as cm:
            RequestFlow(backend).run(binding(), allow_fixture=True)
        self.assertEqual(cm.exception.stage, "guard")
        self.assertIn("company_id", cm.exception.outcome.reason)

    def test_06_partial_cashflow_not_full(self):
        result = copy.deepcopy(FIXTURE_RESULT)
        result.update(binding().as_dict())
        result["coverage"] = "operating_only"
        backend = FixedResultBackend(result, allow_fixture=True)
        with self.assertRaises(FlowBlocked) as cm:
            RequestFlow(backend).run(binding(), allow_fixture=True)
        self.assertIn("full balance", cm.exception.outcome.reason)
        self.assertIn("经营部分", " ".join(cm.exception.outcome.evidence_steps))

    def test_07_missing_actual_closing(self):
        result = copy.deepcopy(FIXTURE_RESULT)
        result.update(binding().as_dict())
        result["amounts"].update(actual_closing=None, difference=None)
        backend = FixedResultBackend(result, allow_fixture=True)
        out = RequestFlow(backend).run(binding(), allow_fixture=True)
        self.assertTrue(out.ok)
        self.assertIn("尚未完成余额核对", out.text)
        self.assertIsNone(out.result["amounts"]["actual_closing"])

    def test_08_algorithm_unavailable(self):
        with self.assertRaises(FlowBlocked) as cm:
            RequestFlow(SnapshotOnlyBackend(allow_fixture=True)).run(binding(), allow_fixture=True)
        self.assertEqual(cm.exception.stage, "read_calculated_result")
        self.assertIn("未绑定", cm.exception.outcome.reason)
        self.assertEqual(cm.exception.outcome.status, UNAVAILABLE)
        self.assertIsNone(cm.exception.outcome.payload)
        report = blocked_report(cm.exception, binding())
        self.assertIn("未执行保存或通知", report["answer"])

    def test_08b_read_table_unavailable_blocks_earlier(self):
        with self.assertRaises(FlowBlocked) as cm:
            RequestFlow(UnboundBackend()).run(binding())
        self.assertEqual(cm.exception.stage, "read_snapshot")
        self.assertEqual(cm.exception.outcome.status, UNAVAILABLE)

    def test_09_save_before_success_blocked(self):
        store = MemoryEvidenceStore()
        failed = copy.deepcopy(FIXTURE_RESULT)
        failed.update(binding().as_dict())
        failed["status"] = "missing_inputs"
        failed["amounts"] = None
        failed["issues"] = ["缺少期初余额"]
        out = save_result(OfflineFixtureBackend(store=store, allow_fixture=True),
                          binding(), failed, "req-1")
        self.assertEqual(out.status, UNAVAILABLE)
        self.assertIn("非成功结果不允许保存", out.reason)
        self.assertEqual(store.list_scope(binding()), [])

    def test_10_timeout_then_retry_same_id(self):
        store = MemoryEvidenceStore(timeout_request_ids=["req-timeout"])
        backend = OfflineFixtureBackend(store=store, allow_fixture=True)
        result = copy.deepcopy(FIXTURE_RESULT)
        result.update(binding().as_dict())
        first = save_result(backend, binding(), result, "req-timeout")
        self.assertEqual(first.status, PENDING)
        self.assertEqual(first.payload["status"], PENDING)
        self.assertEqual(first.payload["record_id"], "")
        again = retry_after_timeout(store, binding(), result, "req-timeout", "req-timeout")
        self.assertEqual(again.status, PENDING)
        self.assertIn("不得改称已保存", again.reason)
        wrong = retry_after_timeout(store, binding(), result, "req-timeout", "req-new-random")
        self.assertEqual(wrong.status, CONFLICT)
        self.assertIn("禁止随机换", wrong.reason)
        self.assertEqual(store.list_scope(binding()), [])

    def test_11_query_errors(self):
        store = NoQueryCapabilityStore()
        out = store.query(binding(), "req-1")
        self.assertEqual(out.status, UNAVAILABLE)
        self.assertIn("精确回查", " ".join(out.missing))
        self.assertEqual(out.evidence_steps, READ_ONLY_CHECK_STEPS)
        mem = MemoryEvidenceStore()
        self.assertEqual(mem.query(binding(), "nope").status, NOT_FOUND)


class RedLineTests(unittest.TestCase):
    """333.md 列出的六项直接打回项。"""

    def test_illegal_amounts_rejected(self):
        result = copy.deepcopy(FIXTURE_RESULT)
        result.update(binding().as_dict())
        result["amounts"]["net"] = "41000.00"
        backend = FixedResultBackend(result, allow_fixture=True)
        with self.assertRaises(FlowBlocked):
            RequestFlow(backend).run(binding(), allow_fixture=True)

    def test_version_mismatch_rejected(self):
        result = copy.deepcopy(FIXTURE_RESULT)
        result.update(binding().as_dict())
        result["source_revision"] = "rev-old"
        backend = FixedResultBackend(result, allow_fixture=True)
        with self.assertRaises(FlowBlocked) as cm:
            RequestFlow(backend).run(binding(), allow_fixture=True)
        self.assertIn("source_revision", cm.exception.outcome.reason)

    def test_fixture_never_leaks_to_production(self):
        backend = OfflineFixtureBackend(allow_fixture=False)
        snap_out = backend.read_snapshot(binding())
        self.assertEqual(snap_out.status, UNAVAILABLE)
        self.assertIsNone(snap_out.payload)
        res_out = backend.read_calculated_result(binding(), {})
        self.assertEqual(res_out.status, UNAVAILABLE)
        self.assertIsNone(res_out.payload)
        with self.assertRaises(FlowBlocked):
            RequestFlow(OfflineFixtureBackend(allow_fixture=False)).run(binding())

    def test_timeout_never_reported_as_saved(self):
        store = MemoryEvidenceStore(timeout_request_ids=["req-x"])
        result = copy.deepcopy(FIXTURE_RESULT)
        result.update(binding().as_dict())
        out = store.commit(binding(), result, "req-x")
        self.assertNotEqual(out.status, COMMITTED)
        self.assertEqual(out.status, PENDING)
        self.assertEqual(store.list_scope(binding()), [])

    def test_duplicate_write_is_idempotent_not_appended(self):
        store = MemoryEvidenceStore()
        result = copy.deepcopy(FIXTURE_RESULT)
        result.update(binding().as_dict())
        first = store.commit(binding(), result, "req-same")
        second = store.commit(binding(), result, "req-same")
        self.assertEqual(first.status, COMMITTED)
        self.assertEqual(second.status, COMMITTED)
        self.assertEqual(first.payload["record_id"], second.payload["record_id"])
        self.assertEqual(len(store.list_scope(binding())), 1)
        changed = copy.deepcopy(result)
        changed["amounts"]["net"] = "41000.00"
        conflict = store.commit(binding(), changed, "req-same")
        self.assertEqual(conflict.status, CONFLICT)
        self.assertEqual(len(store.list_scope(binding())), 1)

    def test_cross_company_query_isolated(self):
        store = MemoryEvidenceStore()
        result = copy.deepcopy(FIXTURE_RESULT)
        result.update(binding().as_dict())
        saved = store.commit(binding(), result, "req-iso")
        self.assertEqual(saved.status, COMMITTED)
        other = binding(company_id="c-2")
        self.assertEqual(store.query(other, "req-iso").status, NOT_FOUND)
        self.assertEqual(store.list_scope(other), [])


class MappingTests(unittest.TestCase):
    def test_build_save_payload_needs_real_schema(self):
        result = copy.deepcopy(FIXTURE_RESULT)
        result.update(binding().as_dict())
        out = build_save_payload(binding(), result, "req-1")
        self.assertEqual(out.status, UNAVAILABLE)
        self.assertIn("inputSchema", " ".join(out.missing))

    def test_build_save_payload_maps_required(self):
        result = copy.deepcopy(FIXTURE_RESULT)
        result.update(binding().as_dict())
        schema = {"required": ["tenant_id", "company_id", "period", "request_id", "amounts"],
                  "properties": {"unit": {}, "status": {}}}
        out = build_save_payload(binding(), result, "req-9", schema)
        self.assertEqual(out.status, COMMITTED)
        self.assertEqual(out.payload["request_id"], "req-9")
        self.assertEqual(out.payload["tenant_id"], "t-1")
        self.assertEqual(out.payload["unit"], "CNY")

    def test_canonical_json_stable_and_refuses_nan(self):
        self.assertEqual(canonical_sha256({"b": 1, "a": "中"}),
                         canonical_sha256({"a": "中", "b": 1}))
        with self.assertRaises(ValueError):
            canonical_sha256({"x": float("nan")})


if __name__ == "__main__":
    unittest.main()
