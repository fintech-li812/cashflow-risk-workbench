"""Independent regression cases for the seven frozen v1 boundary counterexamples."""
import copy
import unittest
from adapters import OfflineFixtureBackend, FIXTURE_RESULT, FIXTURE_SNAPSHOT, with_binding
from runtime_adapter import (Binding, Backend, Outcome, CAP_READ_SNAPSHOT, CAP_READ_RESULT,
                             CAP_SAVE_RESULT, CAP_QUERY_SAVED, COMMITTED, CONFLICT, UNAVAILABLE,
                             PENDING, NOT_FOUND, save_result, query_saved_result, canonical_sha256)
from request_flow import RequestFlow, FlowBlocked
from persistence import MemoryEvidenceStore, build_save_payload, retry_after_timeout


def binding(**overrides):
    return Binding(**dict(dict(tenant_id='reg-tenant', company_id='reg-company', period='2026-08', source_revision='reg-rev', run_id='reg-run-1'), **overrides))


def result(**binding_overrides):
    return with_binding(copy.deepcopy(FIXTURE_RESULT), binding(**binding_overrides))


class CountBackend(OfflineFixtureBackend):
    def __init__(self, **kw):
        super().__init__(allow_fixture=True, **kw); self.reads = 0; self.saves = 0

    def read_calculated_result(self, binding, snapshot):
        self.reads += 1
        return super().read_calculated_result(binding, snapshot)

    def save_result(self, binding, data, request_id):
        self.saves += 1
        return super().save_result(binding, data, request_id)


class BoundaryRegressions(unittest.TestCase):
    def test_p01_new_run_reads_new_result(self):
        backend = CountBackend(); flow = RequestFlow(backend)
        first = flow.run(binding(), allow_fixture=True)
        second = flow.run(binding(run_id='reg-run-2'), allow_fixture=True)
        self.assertTrue(first.ok and second.ok); self.assertEqual(backend.reads, 2)
        self.assertEqual(second.result['run_id'], 'reg-run-2')

    def test_same_run_same_snapshot_reuses_valid_cache(self):
        backend = CountBackend(); flow = RequestFlow(backend)
        flow.run(binding(), allow_fixture=True); flow.run(binding(), allow_fixture=True)
        self.assertEqual(backend.reads, 1)

    def test_p02_invalid_response_never_cached(self):
        bad = copy.deepcopy(FIXTURE_RESULT); bad['amounts']['net'] = '40000.01'
        backend = CountBackend(result=bad); flow = RequestFlow(backend)
        with self.assertRaises(FlowBlocked):
            flow.run(binding(), allow_fixture=True)
        self.assertEqual(flow.cache, {})
        backend.result = copy.deepcopy(FIXTURE_RESULT)
        self.assertTrue(flow.run(binding(), allow_fixture=True).ok)
        self.assertEqual(backend.reads, 2)

    def test_caller_cannot_mutate_cached_nested_amounts(self):
        backend = CountBackend(); flow = RequestFlow(backend)
        first = flow.run(binding(), allow_fixture=True)
        first.result['amounts']['net'] = '1.00'
        second = flow.run(binding(), allow_fixture=True)
        self.assertEqual(second.result['amounts']['net'], '40000.00')

    def test_fixture_instances_and_defaults_do_not_share_nested_values(self):
        first = CountBackend(); second = CountBackend()
        first.result['amounts']['net'] = '1.00'
        self.assertEqual(second.result['amounts']['net'], '40000.00')
        self.assertEqual(FIXTURE_RESULT['amounts']['net'], '40000.00')

    def test_explicit_empty_fixture_is_not_replaced_by_success(self):
        with self.assertRaises(FlowBlocked):
            RequestFlow(CountBackend(result={})).run(binding(), allow_fixture=True)

    def test_p03_each_source_locator_must_match_snapshot(self):
        for key in ('workbook_ref', 'sheet', 'range', 'snapshot_ref'):
            with self.subTest(key=key):
                snapshot = copy.deepcopy(FIXTURE_SNAPSHOT); snapshot[key] = 'different'
                flow = RequestFlow(CountBackend(snapshot=snapshot))
                with self.assertRaises(FlowBlocked) as cm:
                    flow.run(binding(), allow_fixture=True)
                self.assertEqual(cm.exception.stage, 'guard'); self.assertEqual(flow.cache, {})

    def test_snapshot_changed_same_source_version_invalidates_old_cache(self):
        backend = CountBackend(); flow = RequestFlow(backend)
        flow.run(binding(), allow_fixture=True)
        backend.snapshot = copy.deepcopy(FIXTURE_SNAPSHOT); backend.snapshot['snapshot_ref'] = 'snapshot-2'
        backend.result = copy.deepcopy(FIXTURE_RESULT); backend.result['source']['snapshot_ref'] = 'snapshot-2'
        current = flow.run(binding(), allow_fixture=True)
        self.assertTrue(current.ok and current.invalidated); self.assertEqual(backend.reads, 2)

    def test_formula_version_hint_invalidates_old_cache(self):
        backend = CountBackend(); flow = RequestFlow(backend)
        flow.run(binding(), allow_fixture=True)
        backend.snapshot = copy.deepcopy(FIXTURE_SNAPSHOT); backend.snapshot['calculation_version'] = 'formula-2'
        backend.result = copy.deepcopy(FIXTURE_RESULT); backend.result['calculation_version'] = 'formula-2'
        self.assertTrue(flow.run(binding(), allow_fixture=True).ok); self.assertEqual(backend.reads, 2)

    def test_formula_version_hint_mismatch_rejected(self):
        snapshot = copy.deepcopy(FIXTURE_SNAPSHOT); snapshot['calculation_version'] = 'unreturned-version'
        with self.assertRaises(FlowBlocked):
            RequestFlow(CountBackend(snapshot=snapshot)).run(binding(), allow_fixture=True)

    def test_p04_existing_receipt_wrong_payload_is_conflict(self):
        store = MemoryEvidenceStore(); first = store.commit(binding(), result(), 'same-request')
        changed = result(); changed['amounts']['actual_closing'] = '139000.00'; changed['amounts']['difference'] = '-1000.00'
        out = retry_after_timeout(store, binding(), changed, 'same-request', 'same-request')
        self.assertEqual(out.status, CONFLICT)
        self.assertEqual(store.query(binding(), 'same-request').payload['payload_sha256'], first.payload['payload_sha256'])

    def test_p04_valid_saved_receipt_replay_is_same_record(self):
        store = MemoryEvidenceStore(); first = store.commit(binding(), result(), 'same-request')
        out = retry_after_timeout(store, binding(), result(), 'same-request', 'same-request')
        self.assertEqual(out.status, COMMITTED); self.assertEqual(out.payload['record_id'], first.payload['record_id'])

    def test_pending_different_payload_cannot_overwrite_hash(self):
        store = MemoryEvidenceStore(timeout_request_ids=['pending'])
        self.assertEqual(store.commit(binding(), result(), 'pending').status, PENDING)
        changed = result(); changed['amounts']['actual_closing'] = None; changed['amounts']['difference'] = None
        self.assertEqual(store.commit(binding(), changed, 'pending').status, CONFLICT)
        self.assertEqual(store._payloads[(binding().tenant_id, binding().company_id, 'pending')], canonical_sha256(result()))

    def test_p05_save_foreign_result_never_calls_backend(self):
        backend = CountBackend(); data = result(company_id='foreign-company')
        self.assertEqual(save_result(backend, binding(), data, 'r').status, UNAVAILABLE)
        self.assertEqual(backend.saves, 0); self.assertEqual(backend.store.list_scope(binding()), [])

    def test_p05_bad_money_rejected_at_public_and_store_boundaries(self):
        data = result(); data['amounts']['net'] = '40000.01'
        backend = CountBackend()
        self.assertEqual(save_result(backend, binding(), data, 'r').status, UNAVAILABLE)
        self.assertEqual(backend.saves, 0)
        self.assertEqual(backend.store.commit(binding(), data, 'r').status, UNAVAILABLE)

    def test_explicit_false_fixture_mode_overrides_fixture_backend(self):
        backend = CountBackend()
        self.assertEqual(save_result(backend, binding(), result(), 'r', allow_fixture=False).status, UNAVAILABLE)
        self.assertEqual(backend.saves, 0)

    def test_p06_mapping_ready_is_not_committed(self):
        backend = CountBackend(); schema = {'type': 'object', 'required': ['request_id'], 'properties': {'request_id': {'type': 'string'}}}
        out = build_save_payload(binding(), result(), 'r', schema)
        self.assertEqual(out.status, 'ok'); self.assertNotEqual(out.status, COMMITTED)
        self.assertEqual(backend.saves, 0); self.assertIn('尚未执行提交', out.reason)

    def test_p07_pending_snapshot_is_blocked(self):
        class Pending(CountBackend):
            def read_snapshot(self, b):
                out = super().read_snapshot(b); out.status = PENDING; return out
        with self.assertRaises(FlowBlocked) as cm:
            RequestFlow(Pending()).run(binding(), allow_fixture=True)
        self.assertEqual(cm.exception.stage, 'read_snapshot')

    def test_p07_pending_result_is_blocked(self):
        class Pending(CountBackend):
            def read_calculated_result(self, b, snapshot):
                out = super().read_calculated_result(b, snapshot); out.status = PENDING; return out
        with self.assertRaises(FlowBlocked) as cm:
            RequestFlow(Pending()).run(binding(), allow_fixture=True)
        self.assertEqual(cm.exception.stage, 'read_calculated_result')

    def test_read_wrong_capability_cannot_be_accepted(self):
        class Wrong(CountBackend):
            def read_snapshot(self, b):
                out = super().read_snapshot(b); out.capability = CAP_SAVE_RESULT; return out
        with self.assertRaises(FlowBlocked):
            RequestFlow(Wrong()).run(binding(), allow_fixture=True)

    def test_declared_foreign_snapshot_identity_rejected(self):
        snapshot = copy.deepcopy(FIXTURE_SNAPSHOT); snapshot['company_id'] = 'foreign'
        with self.assertRaises(FlowBlocked):
            RequestFlow(CountBackend(snapshot=snapshot)).run(binding(), allow_fixture=True)

    def test_non_success_payload_cannot_be_flow_ok(self):
        data = copy.deepcopy(FIXTURE_RESULT); data.update(status='unavailable', amounts=None, issues=['not-ready'])
        with self.assertRaises(FlowBlocked):
            RequestFlow(CountBackend(result=data)).run(binding(), allow_fixture=True)

    def test_commit_then_lost_reply_is_pending_then_precise_replay(self):
        class LostReply(CountBackend):
            def save_result(self, b, data, request_id):
                super().save_result(b, data, request_id)
                raise TimeoutError('synthetic lost reply')
        backend = LostReply(); initial = save_result(backend, binding(), result(), 'lost-reply')
        self.assertEqual(initial.status, PENDING)
        stored = backend.store.query(binding(), 'lost-reply')
        self.assertEqual(stored.status, COMMITTED)
        recovered = retry_after_timeout(backend.store, binding(), result(), 'lost-reply', 'lost-reply')
        self.assertEqual(recovered.status, COMMITTED); self.assertEqual(recovered.payload['record_id'], stored.payload['record_id'])
        self.assertEqual(len(backend.store.list_scope(binding())), 1)

    def test_query_connection_failure_does_not_trigger_resubmit(self):
        class FailedQuery(MemoryEvidenceStore):
            def __init__(self):
                super().__init__(); self.commits = 0
            def query(self, b, request_id):
                raise ConnectionError('synthetic')
            def commit(self, b, data, request_id):
                self.commits += 1
                return super().commit(b, data, request_id)
        store = FailedQuery(); out = retry_after_timeout(store, binding(), result(), 'r', 'r')
        self.assertEqual(out.status, PENDING); self.assertEqual(store.commits, 0)

    def test_unknown_query_status_never_resubmits(self):
        class UnknownQuery(MemoryEvidenceStore):
            def query(self, b, request_id):
                return Outcome(capability=CAP_QUERY_SAVED, status='unknown')
        store = UnknownQuery(); out = retry_after_timeout(store, binding(), result(), 'r', 'r')
        self.assertEqual(out.status, UNAVAILABLE); self.assertEqual(store.list_scope(binding()), [])

    def test_public_save_rejects_bad_receipt_even_after_backend_claim(self):
        class WrongReceipt(CountBackend):
            def save_result(self, b, data, request_id):
                out = super().save_result(b, data, request_id); out.payload['payload_sha256'] = '0' * 64; return out
        self.assertEqual(save_result(WrongReceipt(), binding(), result(), 'r').status, UNAVAILABLE)

    def test_public_query_must_match_current_full_context(self):
        backend = CountBackend(); save_result(backend, binding(), result(), 'r')
        out = query_saved_result(backend, binding(run_id='other-run'), 'r')
        self.assertEqual(out.status, UNAVAILABLE)


if __name__ == '__main__':
    unittest.main()
