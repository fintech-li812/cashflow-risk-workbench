"""WB-AGENT-003 后端组合：把四类能力接到具体实现。

OfflineFixtureBackend 只服务于显式测试；allow_fixture 默认 False，
生产路径不会自动回退到合成夹具。合成标记在返回的 payload 中原样保留，不擦除。
"""
from typing import Any, Dict, List, Optional
import copy

from runtime_adapter import (Backend, Binding, CAP_QUERY_SAVED, CAP_READ_RESULT,
                             CAP_READ_SNAPSHOT, CAP_SAVE_RESULT, Outcome, UNAVAILABLE)
from persistence import MemoryEvidenceStore, NoQueryCapabilityStore

FIXTURE_SNAPSHOT: Dict[str, Any] = {
    "workbook_ref": "synthetic-book",
    "sheet": "synthetic-result",
    "range": "A1:H2",
    "snapshot_ref": "fixture-snapshot",
    "origin": "offline_fixture",
}

FIXTURE_RESULT: Dict[str, Any] = {
    "schema_version": "mfg-agent-result.v1",
    "industry": "manufacturing",
    "status": "success",
    "origin": "offline_fixture",
    "unit": "CNY",
    "coverage": "full_cashflow",
    "calculation_version": "fixture.v1",
    "issues": [],
    "source": {"workbook_ref": "synthetic-book", "sheet": "synthetic-result",
               "range": "A1:H2", "snapshot_ref": "fixture-snapshot"},
    "amounts": {"opening": "100000.00", "inflow": "130000.00", "outflow": "90000.00",
                "net": "40000.00", "closing": "140000.00",
                "actual_closing": "140000.00", "difference": "0.00"},
}


def with_binding(result: Dict[str, Any], binding: Binding) -> Dict[str, Any]:
    out = copy.deepcopy(result)
    out.update(binding.as_dict())
    return out


class OfflineFixtureBackend(Backend):
    """离线夹具后端。allow_fixture=False（默认）时全部能力返回 unavailable。"""

    def __init__(self, snapshot: Optional[Dict[str, Any]] = None,
                 result: Optional[Dict[str, Any]] = None,
                 store: Optional[MemoryEvidenceStore] = None,
                 timeout_request_ids: Optional[List[str]] = None,
                 allow_fixture: bool = False,
                 no_query: bool = False):
        self.snapshot = copy.deepcopy(FIXTURE_SNAPSHOT if snapshot is None else snapshot)
        self.result = copy.deepcopy(FIXTURE_RESULT if result is None else result)
        self.store = store if store is not None else (NoQueryCapabilityStore() if no_query
                               else MemoryEvidenceStore(timeout_request_ids=timeout_request_ids))
        self.timeout_request_ids = timeout_request_ids
        self.allow_fixture = allow_fixture

    def _guard(self, capability: str) -> Optional[Outcome]:
        if not self.allow_fixture:
            return Outcome(capability=capability, status=UNAVAILABLE, payload=None,
                           missing=["allow_fixture"],
                           reason="离线夹具后端仅在显式测试模式可用，生产禁止回退 fixture",
                           evidence_steps=["绑定真实千问读表与表格公式适配器后再调用。"])
        return None

    def read_snapshot(self, binding: Binding) -> Outcome:
        blocked = self._guard(CAP_READ_SNAPSHOT)
        if blocked:
            return blocked
        return Outcome(capability=CAP_READ_SNAPSHOT, status="ok",
                       payload=copy.deepcopy(self.snapshot), missing=[], reason="", evidence_steps=[])

    def read_calculated_result(self, binding: Binding, snapshot: Dict[str, Any]) -> Outcome:
        blocked = self._guard(CAP_READ_RESULT)
        if blocked:
            return blocked
        return Outcome(capability=CAP_READ_RESULT, status="ok",
                       payload=with_binding(self.result, binding), missing=[], reason="",
                       evidence_steps=[])

    def save_result(self, binding: Binding, result: Dict[str, Any], request_id: str) -> Outcome:
        blocked = self._guard(CAP_SAVE_RESULT)
        if blocked:
            return blocked
        return self.store.commit(binding, result, request_id)

    def query_saved_result(self, binding: Binding, request_id: str) -> Outcome:
        blocked = self._guard(CAP_QUERY_SAVED)
        if blocked:
            return blocked
        return self.store.query(binding, request_id)
