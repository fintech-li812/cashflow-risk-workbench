"""WB-AGENT-003 运行适配层：四类内部能力接口（不是对外 MCP 工具名）。

范围依据：333.md A 项；接口口径依据：规则/制造业Agent周边工程统一接口_v1.md。

本模块只做三件事：
  1. 定义 read_snapshot / read_calculated_result / save_result / query_saved_result
     四类内部能力的调用形状与返回状态；
  2. 在未绑定真实千问读表 / 表格公式 / 存储工具时，返回结构化 unavailable
     与缺项清单，并给出人工导入证据流程；
  3. 提供显式测试夹具通道，且生产模式下禁用。

本模块不做：不实现算法、不计算金额、不连接服务器、不读写生产库、
不伪造任何平台 API 或网页端点、不把合成夹具当作真实结果。
"""
import json
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "mfg-agent-adapter.v1"
CONTEXT_FIELDS = ("tenant_id", "company_id", "period", "source_revision", "run_id")
OPERATION_SAVE = "save_cashflow_result"

CAP_READ_SNAPSHOT = "read_snapshot"
CAP_READ_RESULT = "read_calculated_result"
CAP_SAVE_RESULT = "save_result"
CAP_QUERY_SAVED = "query_saved_result"

CAPABILITIES = (CAP_READ_SNAPSHOT, CAP_READ_RESULT, CAP_SAVE_RESULT, CAP_QUERY_SAVED)

UNAVAILABLE = "unavailable"
COMMITTED = "committed"
PENDING = "pending"
CONFLICT = "conflict"
NOT_FOUND = "not_found"
READ_OK = "ok"  # Existing internal read/preparation state, never a commit receipt.

MISSING_BINDING = "真实平台绑定未就绪"
MISSING_STORAGE = "存储与回查工具未绑定"
MISSING_ALGORITHM = "主算法 / 千问表格公式适配器未绑定"


def canonical_json(obj: Any) -> bytes:
    """规范 JSON：统一接口文件规定的固定序列化，allow_nan=False 拒绝非有限数。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_sha256(obj: Any) -> str:
    import hashlib
    return hashlib.sha256(canonical_json(obj)).hexdigest()


@dataclass(frozen=True)
class Binding:
    """可信身份与版本绑定。只能由平台认证绑定层生成，不由表格文本或文件名推断。"""
    tenant_id: str
    company_id: str
    period: str
    source_revision: str
    run_id: str

    def as_dict(self) -> Dict[str, str]:
        return {k: getattr(self, k) for k in CONTEXT_FIELDS}

    def same_scope(self, other: "Binding") -> bool:
        return (self.tenant_id == other.tenant_id
                and self.company_id == other.company_id)


@dataclass
class Outcome:
    """统一返回包装：status 为闭集，非成功时不携带金额。"""
    capability: str
    status: str
    payload: Optional[Dict[str, Any]] = None
    missing: List[str] = field(default_factory=list)
    reason: str = ""
    evidence_steps: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "capability": self.capability,
            "status": self.status,
            "payload": self.payload,
            "missing": list(self.missing),
            "reason": self.reason,
            "evidence_steps": list(self.evidence_steps),
        }


def unavailable(capability: str, reason: str, missing: List[str],
                evidence_steps: Optional[List[str]] = None) -> Outcome:
    """结构化未就绪：带缺项清单与人工取证步骤，绝不返回合成结果。"""
    return Outcome(capability=capability, status=UNAVAILABLE, payload=None,
                   missing=list(missing), reason=reason,
                   evidence_steps=list(evidence_steps or []))


MANUAL_SNAPSHOT_STEPS = [
    "在千问办公打开已绑定的制造业工作簿，确认 tenant/company/period 与当前请求一致。",
    "导出或截图当期现金流水 Sheet 的取数区域，记录 workbook_ref / sheet / range。",
    "记录该次取数的 snapshot_ref 与 source_revision（源数据改变必须产生新版本号）。",
    "将以上四项作为手动证据写入本次运行记录，再继续执行后续能力。",
]

MANUAL_RESULT_STEPS = [
    "在表格中执行已批准的现金流公式，确认返回流入/流出/净额/期末。",
    "记录 calculation_version 与公式所在 sheet / range。",
    "取得独立实际期末余额（若有），否则明确标注未完成余额核对。",
    "把结果交给结果守卫校验，不手工改写金额。",
]

MANUAL_STORAGE_STEPS = [
    "确认实际绑定的存储工具真实 inputSchema 与权限，逐字段映射，不凭提示词虚构接口。",
    "保存时使用同一 request_id 作为幂等键，超时视为结果尚未确认。",
    "回查时按 request_id + payload_sha256 精确查询；无精确回查能力则按只读步骤人工核对。",
]


class Backend:
    """真实能力后端接口。所有方法默认返回 unavailable，子类按实际绑定实现。"""

    def read_snapshot(self, binding: Binding) -> Outcome:
        return unavailable(CAP_READ_SNAPSHOT, MISSING_BINDING,
                           ["platform_binding:千问读表适配器", "snapshot_ref", "source_revision"],
                           MANUAL_SNAPSHOT_STEPS)

    def read_calculated_result(self, binding: Binding, snapshot: Dict[str, Any]) -> Outcome:
        return unavailable(CAP_READ_RESULT, MISSING_ALGORITHM,
                           ["algorithm:主算法或表格公式适配器", "calculation_version"],
                           MANUAL_RESULT_STEPS)

    def save_result(self, binding: Binding, result: Dict[str, Any], request_id: str) -> Outcome:
        return unavailable(CAP_SAVE_RESULT, MISSING_STORAGE,
                           ["tool:MCP存储工具真实inputSchema", "request_id", "receipt"],
                           MANUAL_STORAGE_STEPS)

    def query_saved_result(self, binding: Binding, request_id: str) -> Outcome:
        return unavailable(CAP_QUERY_SAVED, MISSING_STORAGE,
                           ["tool:MCP存储工具真实inputSchema", "request_id"],
                           MANUAL_STORAGE_STEPS)


class UnboundBackend(Backend):
    """显式未绑定后端：与 Backend 默认一致，用于让"未绑定"这件事可被显式声明。"""
    pass


def read_snapshot(backend: Backend, binding: Binding) -> Outcome:
    """A-1 读取当期源数据快照。未绑定返回 unavailable 及缺项。"""
    if not isinstance(binding, Binding):
        raise TypeError("binding must be a trusted Binding")
    try:
        out = backend.read_snapshot(binding)
    except (TimeoutError, ConnectionError):
        return unavailable(CAP_READ_SNAPSHOT, "读取快照的连接未确认", ["snapshot_response"], MANUAL_SNAPSHOT_STEPS)
    if not isinstance(out, Outcome) or out.capability != CAP_READ_SNAPSHOT:
        return unavailable(CAP_READ_SNAPSHOT, "快照响应类型或能力不符", ["snapshot_response"], MANUAL_SNAPSHOT_STEPS)
    if out.status == UNAVAILABLE:
        return out
    if out.status != READ_OK or not isinstance(out.payload, dict):
        return unavailable(CAP_READ_SNAPSHOT, "快照读取未取得显式成功", ["snapshot_response.status"], MANUAL_SNAPSHOT_STEPS)
    snap = out.payload
    required = ("workbook_ref", "sheet", "range", "snapshot_ref")
    gaps = [k for k in required if not isinstance(snap.get(k), str) or not snap[k].strip()]
    if gaps:
        return unavailable(CAP_READ_SNAPSHOT, "快照缺少定位字段", gaps, MANUAL_SNAPSHOT_STEPS)
    if any(k in snap and snap[k] != binding.as_dict()[k] for k in CONTEXT_FIELDS):
        return unavailable(CAP_READ_SNAPSHOT, "快照声明的身份或来源版本不符", ["snapshot_context"], MANUAL_SNAPSHOT_STEPS)
    return out


def read_calculated_result(backend: Backend, binding: Binding,
                           snapshot: Dict[str, Any]) -> Outcome:
    """A-2 读取计算结果。算法未就绪返回 unavailable，不产生假成功。"""
    if not isinstance(snapshot, dict) or not snapshot.get("snapshot_ref"):
        return unavailable(CAP_READ_RESULT, "缺少有效快照，无法取数", ["snapshot_ref"],
                           MANUAL_SNAPSHOT_STEPS)
    try:
        out = backend.read_calculated_result(binding, snapshot)
    except (TimeoutError, ConnectionError):
        return unavailable(CAP_READ_RESULT, "读取公式结果的连接未确认", ["result_response"], MANUAL_RESULT_STEPS)
    if not isinstance(out, Outcome) or out.capability != CAP_READ_RESULT:
        return unavailable(CAP_READ_RESULT, "公式响应类型或能力不符", ["result_response"], MANUAL_RESULT_STEPS)
    if out.status == UNAVAILABLE:
        return out
    if out.status != READ_OK or not isinstance(out.payload, dict):
        return unavailable(CAP_READ_RESULT, "公式结果读取未取得显式成功", ["result_response.status"], MANUAL_RESULT_STEPS)
    res = out.payload
    if res.get("status") != "success":
        return unavailable(CAP_READ_RESULT, "公式未返回成功现金流结果", ["result.status"], MANUAL_RESULT_STEPS)
    for key in ("calculation_version", "origin"):
        if not isinstance(res.get(key), str) or not res[key].strip():
            return unavailable(CAP_READ_RESULT, f"结果缺少 {key}", [key], MANUAL_RESULT_STEPS)
    return out


def save_result(backend: Backend, binding: Binding, result: Dict[str, Any],
                request_id: str, *, allow_fixture: Optional[bool] = None) -> Outcome:
    """A-3 保存结果。幂等键 request_id；超时为 pending，不得换 ID 重提。"""
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id must be a nonempty string")
    if not isinstance(result, dict):
        raise TypeError("result must be an object")
    if not isinstance(binding, Binding):
        raise TypeError("binding must be a trusted Binding")
    if result.get("status") != "success":
        return Outcome(capability=CAP_SAVE_RESULT, status=UNAVAILABLE, payload=None,
                       missing=["result.status"], reason="非成功结果不允许保存",
                       evidence_steps=MANUAL_STORAGE_STEPS)
    import agent_guard
    fixture_mode = getattr(backend, "allow_fixture", False) is True if allow_fixture is None else allow_fixture is True
    try:
        agent_guard.validate_result(result, binding.as_dict(), allow_fixture=fixture_mode)
    except agent_guard.ResultError as exc:
        return unavailable(CAP_SAVE_RESULT, "保存前结果守卫拒绝：" + str(exc), ["validated_result"], MANUAL_STORAGE_STEPS)
    try:
        out = backend.save_result(binding, result, request_id)
    except (TimeoutError, ConnectionError):
        return Outcome(capability=CAP_SAVE_RESULT, status=PENDING, payload=None,
                       missing=["确认回执"], reason="保存连接中断，提交结果尚未确认",
                       evidence_steps=MANUAL_STORAGE_STEPS)
    if not isinstance(out, Outcome) or out.capability != CAP_SAVE_RESULT or out.status not in (COMMITTED, PENDING, CONFLICT, UNAVAILABLE):
        return unavailable(CAP_SAVE_RESULT, "保存响应类型或状态不符", ["save_response"], MANUAL_STORAGE_STEPS)
    if out.status == COMMITTED:
        problem = receipt_problem(out.payload, binding, request_id, canonical_sha256(result))
        if problem:
            return unavailable(CAP_SAVE_RESULT, problem, ["matching_receipt"], MANUAL_STORAGE_STEPS)
    return out


def receipt_problem(receipt, binding: Binding, request_id: str, expected_hash=None) -> str:
    """Structural/scope/content check only; not proof of an actual database transaction."""
    if not isinstance(receipt, dict):
        return "缺少可核对的提交回执"
    if any(receipt.get(k) != v for k, v in binding.as_dict().items()):
        return "回执身份、期间、来源版本或run与当前请求不符"
    expected = {"schema_version": "mfg-evidence.v1", "kind": "receipt",
                "operation": OPERATION_SAVE, "status": COMMITTED, "request_id": request_id}
    if any(receipt.get(k) != v for k, v in expected.items()):
        return "回执协议、状态或request_id不符"
    if not isinstance(receipt.get("record_id"), str) or not receipt["record_id"].strip():
        return "回执缺少record_id"
    value = receipt.get("payload_sha256")
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        return "回执内容摘要非法"
    if expected_hash is not None and value != expected_hash:
        return "同一逻辑请求回执与本次载荷不一致"
    try:
        stamp = datetime.fromisoformat(receipt["stored_at"].replace("Z", "+00:00"))
        if stamp.utcoffset() is None:
            return "回执时间缺少时区"
    except (KeyError, ValueError, TypeError, AttributeError):
        return "回执时间非法"
    return ""


def query_saved_result(backend: Backend, binding: Binding, request_id: str) -> Outcome:
    """A-4 精确回查。无精确回查能力时返回 unavailable 与只读核对步骤。"""
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id must be a nonempty string")
    if not isinstance(binding, Binding):
        raise TypeError("binding must be a trusted Binding")
    try:
        out = backend.query_saved_result(binding, request_id)
    except (TimeoutError, ConnectionError):
        return unavailable(CAP_QUERY_SAVED, "回查连接未确认，不能认定未提交", ["query_response"], MANUAL_STORAGE_STEPS)
    if not isinstance(out, Outcome) or out.capability != CAP_QUERY_SAVED or out.status not in (COMMITTED, PENDING, NOT_FOUND, UNAVAILABLE):
        return unavailable(CAP_QUERY_SAVED, "回查响应类型或状态不符", ["query_response"], MANUAL_STORAGE_STEPS)
    if out.status == COMMITTED:
        problem = receipt_problem(out.payload, binding, request_id)
        if problem:
            return unavailable(CAP_QUERY_SAVED, problem, ["matching_receipt"], MANUAL_STORAGE_STEPS)
    return out
