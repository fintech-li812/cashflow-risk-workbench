"""WB-AGENT-003 保存与回查：逐字段映射、幂等键、回执、精确回查、超时不确定态。

范围依据：333.md C 项；工件格式依据：规则/制造业Agent周边工程统一接口_v1.md 第 3 节
（mfg-evidence.v1：schema_version / kind=receipt / operation / 五字段 / request_id /
 record_id / payload_sha256 / stored_at / status=committed）。

本模块的 MemoryEvidenceStore 是**本地进程内参考实现，仅用于离线自测**，
不是 MySQL、不是生产存储、不产生任何数据库主键；record_id 明确标注为本地存储 ID。
"""
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from runtime_adapter import (Binding, CAP_QUERY_SAVED, CAP_SAVE_RESULT, COMMITTED,
                             CONFLICT, NOT_FOUND, Outcome, OPERATION_SAVE, PENDING,
                             UNAVAILABLE, READ_OK, canonical_sha256, receipt_problem)
import agent_guard

RECEIPT_SCHEMA = "mfg-evidence.v1"
READ_ONLY_CHECK_STEPS = [
    "按 tenant_id + company_id + period + request_id 在存储侧列出当前全部记录，不跨企业比较。",
    "比对目标记录的 payload_sha256 与本次待确认结果对象的规范 JSON 哈希是否一致。",
    "一致则说明提交已落地，取该 record_id 作为回执；不一致或不存在则仍为未确认。",
    "不得以最大 record_id 或最大时间猜测跨企业最新记录。",
]

FIELD_MAPPING: Dict[str, str] = {
    "tenant_id": "binding.tenant_id",
    "company_id": "binding.company_id",
    "period": "binding.period",
    "source_revision": "binding.source_revision",
    "run_id": "binding.run_id",
    "request_id": "request.request_id",
    "schema_version": "result.schema_version",
    "industry": "result.industry",
    "status": "result.status",
    "origin": "result.origin",
    "unit": "result.unit",
    "coverage": "result.coverage",
    "calculation_version": "result.calculation_version",
    "source": "result.source",
    "amounts": "result.amounts",
}


def build_save_payload(binding: Binding, result: Dict[str, Any], request_id: str,
                       input_schema: Optional[Dict[str, Any]] = None) -> Outcome:
    """按实际工具 inputSchema 逐字段映射构造保存载荷。

    未提供真实 inputSchema 时返回 unavailable 与缺项，不凭提示词虚构接口。
    """
    if not isinstance(input_schema, dict) or not input_schema:
        return Outcome(capability=CAP_SAVE_RESULT, status=UNAVAILABLE, payload=None,
                       missing=["tool_inputSchema:字段名清单", "tool_inputSchema:required"],
                       reason="未取得实际存储工具 inputSchema，不能构造保存载荷",
                       evidence_steps=["从实际已绑定工具的 tools/list 取得 inputSchema 后逐字段映射，"
                                       "不使用本文件预设字段名直接提交。"])
    required = input_schema.get("required", [])
    properties = input_schema.get("properties", {})
    payload: Dict[str, Any] = {}
    gaps: List[str] = []
    for name in required:
        source = FIELD_MAPPING.get(name)
        if source is None:
            gaps.append(f"inputSchema.required 中的 {name} 无映射来源")
            continue
        if source.startswith("binding."):
            payload[name] = getattr(binding, source.split(".", 1)[1])
        elif source.startswith("request."):
            payload[name] = request_id
        elif source.startswith("result."):
            key = source.split(".", 1)[1]
            if key not in result:
                gaps.append(f"结果缺少字段 {key}（映射目标 {name}）")
                continue
            payload[name] = result[key]
    for name in properties:
        if name in payload:
            continue
        source = FIELD_MAPPING.get(name)
        if source and source.startswith("result."):
            key = source.split(".", 1)[1]
            if key in result:
                payload[name] = result[key]
    if gaps:
        return Outcome(capability=CAP_SAVE_RESULT, status=UNAVAILABLE, payload=None,
                       missing=gaps, reason="逐字段映射存在缺项",
                       evidence_steps=["补齐缺项后再提交，不省略必填字段。"])
    return Outcome(capability=CAP_SAVE_RESULT, status=READ_OK, payload=payload,
                   missing=[], reason="参数准备完成，尚未执行提交，不是已保存回执", evidence_steps=[])


@dataclass
class Receipt:
    schema_version: str = RECEIPT_SCHEMA
    kind: str = "receipt"
    operation: str = OPERATION_SAVE
    tenant_id: str = ""
    company_id: str = ""
    period: str = ""
    source_revision: str = ""
    run_id: str = ""
    request_id: str = ""
    record_id: str = ""
    payload_sha256: str = ""
    stored_at: str = ""
    status: str = COMMITTED
    note: str = "本地存储ID，不是MySQL主键"

    def as_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


class MemoryEvidenceStore:
    """进程内参考实现：仅用于离线自测幂等/超时/冲突/隔离语义。

    不是数据库，不持久化，不跨进程，不声称已入库，不产生 MySQL 主键。
    """

    def __init__(self, timeout_request_ids: Optional[List[str]] = None,
                 clock: Optional[List[str]] = None):
        self._records: Dict[Tuple[str, str, str], List[Receipt]] = {}
        self._payloads: Dict[Tuple[str, str, str], str] = {}
        self._timeout_ids = set(timeout_request_ids or [])
        self._clock = clock if clock is not None else ["2026-10-23T00:00:00Z"]

    def _key(self, binding: Binding, request_id: str) -> Tuple[str, str, str]:
        return (binding.tenant_id, binding.company_id, request_id)

    def commit(self, binding: Binding, result: Dict[str, Any], request_id: str) -> Outcome:
        if not isinstance(binding, Binding) or not isinstance(result, dict) or not isinstance(request_id, str) or not request_id.strip():
            return validate_store_input(binding, result, request_id)
        key = self._key(binding, request_id)
        try:
            payload_hash = canonical_sha256(result)
        except (ValueError, TypeError):
            return Outcome(capability=CAP_SAVE_RESULT, status=UNAVAILABLE, payload=None,
                           missing=["规范JSON载荷"], reason="载荷不可安全序列化，未保存",
                           evidence_steps=READ_ONLY_CHECK_STEPS)
        if key in self._payloads and self._payloads[key] != payload_hash:
            return Outcome(capability=CAP_SAVE_RESULT, status=CONFLICT, payload=None,
                           missing=["request_id 已有其他载荷，包括未确认提交"],
                           reason="同一逻辑请求载荷冲突，禁止覆盖未确认状态",
                           evidence_steps=READ_ONLY_CHECK_STEPS)
        problem = validate_store_input(binding, result, request_id)
        if problem is not None:
            return problem
        existing = self._records.get(key)
        if existing:
            if self._payloads.get(key) != payload_hash:
                return Outcome(capability=CAP_SAVE_RESULT, status=CONFLICT, payload=None,
                               missing=["request_id 已存在但载荷不同"],
                               reason="同一 request_id 载荷不一致，拒绝覆盖旧记录",
                               evidence_steps=["新逻辑请求必须使用新 request_id；旧记录保留不覆盖。"])
            return Outcome(capability=CAP_SAVE_RESULT, status=COMMITTED,
                           payload=existing[-1].as_dict(), missing=[],
                           reason="幂等重放：返回已有回执", evidence_steps=[])
        if request_id in self._timeout_ids:
            self._payloads[key] = payload_hash
            pending = Receipt(tenant_id=binding.tenant_id, company_id=binding.company_id,
                              period=binding.period, source_revision=binding.source_revision,
                              run_id=binding.run_id, request_id=request_id, record_id="",
                              payload_sha256=payload_hash, stored_at="",
                              status=PENDING)
            return Outcome(capability=CAP_SAVE_RESULT, status=PENDING,
                           payload=pending.as_dict(), missing=["确认回执"],
                           reason="提交后未取得确定结果：结果尚未确认",
                           evidence_steps=["沿用同一 request_id 先回查，禁止随机换 ID 重复提交。"])
        digest = hashlib.sha256(f"{binding.tenant_id}|{binding.company_id}|{request_id}".encode()).hexdigest()
        receipt = Receipt(tenant_id=binding.tenant_id, company_id=binding.company_id,
                          period=binding.period, source_revision=binding.source_revision,
                          run_id=binding.run_id, request_id=request_id,
                          record_id="local-" + digest[:16], payload_sha256=payload_hash,
                          stored_at=self._clock[-1], status=COMMITTED)
        self._records[key] = [receipt]
        self._payloads[key] = payload_hash
        return Outcome(capability=CAP_SAVE_RESULT, status=COMMITTED,
                       payload=receipt.as_dict(), missing=[], reason="", evidence_steps=[])

    def query(self, binding: Binding, request_id: str) -> Outcome:
        key = self._key(binding, request_id)
        records = self._records.get(key)
        if records:
            return Outcome(capability=CAP_QUERY_SAVED, status=COMMITTED,
                           payload=records[-1].as_dict(), missing=[], reason="", evidence_steps=[])
        if key in self._payloads:
            return Outcome(capability=CAP_QUERY_SAVED, status=PENDING, payload=None,
                           missing=["确认回执"], reason="提交已发出但尚未确认，仍为未确认状态",
                           evidence_steps=["沿用同一 request_id 再次回查；不得换 ID 重提。"])
        return Outcome(capability=CAP_QUERY_SAVED, status=NOT_FOUND, payload=None,
                       missing=[request_id], reason="未找到该 request_id 的提交记录",
                       evidence_steps=["确认 request_id 与租户/企业是否匹配后重新提交。"])

    def list_scope(self, binding: Binding) -> List[Dict[str, Any]]:
        """只读核对用：列出同租户+同企业的全部记录，绝不跨企业比较。"""
        out: List[Dict[str, Any]] = []
        for (tenant, company, _), records in self._records.items():
            if tenant == binding.tenant_id and company == binding.company_id:
                out.extend(r.as_dict() for r in records)
        return out


class NoQueryCapabilityStore(MemoryEvidenceStore):
    """能提交但没有精确回查能力的存储：回查必须明确阻塞并给只读核对步骤。"""

    def query(self, binding: Binding, request_id: str) -> Outcome:
        return Outcome(capability=CAP_QUERY_SAVED, status=UNAVAILABLE, payload=None,
                       missing=["精确回查能力"],
                       reason="该存储不具备按 request_id 的精确回查能力，无法确认保存结果",
                       evidence_steps=READ_ONLY_CHECK_STEPS)


def retry_after_timeout(store: MemoryEvidenceStore, binding: Binding,
                        result: Dict[str, Any], original_request_id: str,
                        submitted_request_id: str) -> Outcome:
    """超时后的正确处理：必须先回查，且沿用同一 request_id。

    传入不同 ID 视为换 ID 重复提交，直接拒绝，不写入。
    """
    if submitted_request_id != original_request_id:
        return Outcome(capability=CAP_SAVE_RESULT, status=CONFLICT, payload=None,
                       missing=["request_id 不一致"],
                       reason="超时后禁止随机换 ID 重复提交：必须沿用同一逻辑请求 ID",
                       evidence_steps=["用原 request_id 回查；确认为未提交时才可沿用同 ID 重提。"])
    problem = validate_store_input(binding, result, original_request_id)
    if problem is not None:
        return problem
    try:
        query = store.query(binding, original_request_id)
    except (TimeoutError, ConnectionError):
        return Outcome(capability=CAP_SAVE_RESULT, status=PENDING, payload=None,
                       missing=["确认回执"], reason="回查连接未确认，禁止推断未提交并重写",
                       evidence_steps=READ_ONLY_CHECK_STEPS)
    if not isinstance(query, Outcome) or query.capability != CAP_QUERY_SAVED:
        return Outcome(capability=CAP_SAVE_RESULT, status=UNAVAILABLE, payload=None,
                       missing=["有效回查响应"], reason="回查响应不符，不允许自动重提",
                       evidence_steps=READ_ONLY_CHECK_STEPS)
    if query.status == COMMITTED:
        problem = receipt_problem(query.payload, binding, original_request_id, canonical_sha256(result))
        if problem:
            return Outcome(capability=CAP_SAVE_RESULT, status=CONFLICT, payload=None,
                           missing=["与当前请求一致的回执"], reason=problem,
                           evidence_steps=READ_ONLY_CHECK_STEPS)
        return Outcome(capability=CAP_SAVE_RESULT, status=COMMITTED, payload=query.payload,
                       missing=[], reason="回查确认：提交已落地", evidence_steps=[])
    if query.status == PENDING:
        return Outcome(capability=CAP_SAVE_RESULT, status=PENDING, payload=None,
                       missing=["确认回执"], reason="回查后仍为未确认，不得改称已保存",
                       evidence_steps=["继续沿用同一 request_id 回查；仍不确定则报阻塞。"])
    if query.status == UNAVAILABLE:
        return Outcome(capability=CAP_SAVE_RESULT, status=UNAVAILABLE, payload=None,
                       missing=query.missing, reason="无精确回查能力，无法确认",
                       evidence_steps=READ_ONLY_CHECK_STEPS)
    if query.status != NOT_FOUND:
        return Outcome(capability=CAP_SAVE_RESULT, status=UNAVAILABLE, payload=None,
                       missing=["明确未提交的回查结果"], reason="未知回查状态，不允许自动重提",
                       evidence_steps=READ_ONLY_CHECK_STEPS)
    return store.commit(binding, result, original_request_id)


def validate_store_input(binding, result, request_id):
    """Reference-store input guard; local fixture support is not production authentication."""
    try:
        if not isinstance(binding, Binding) or not isinstance(request_id, str) or not request_id.strip():
            raise agent_guard.ResultError("trusted binding/request_id required")
        if not isinstance(result, dict) or result.get("status") != "success":
            raise agent_guard.ResultError("only successful results may be saved")
        agent_guard.validate_result(result, binding.as_dict(), allow_fixture=True)
    except agent_guard.ResultError as exc:
        return Outcome(capability=CAP_SAVE_RESULT, status=UNAVAILABLE, payload=None,
                       missing=["validated_result"], reason="保存前拒绝：" + str(exc),
                       evidence_steps=READ_ONLY_CHECK_STEPS)
    return None
