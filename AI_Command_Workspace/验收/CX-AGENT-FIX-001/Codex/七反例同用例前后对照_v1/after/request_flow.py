"""WB-AGENT-003 请求流程：绑定可信身份、源版本失效重取、统一接口守卫。

范围依据：333.md B 项。本模块不实现算法、不心算金额、不替代千问表格公式。
结果校验直接复用继承来的 agent_guard，不在本文件重复造一套判定规则。
"""
import re
import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from runtime_adapter import (Binding, CAP_READ_RESULT, CAP_READ_SNAPSHOT, Outcome,
                             UNAVAILABLE, canonical_sha256, read_calculated_result,
                             read_snapshot)
import agent_guard

PERIOD_RE = re.compile(r"[0-9]{4}-(?:0[1-9]|1[0-2])")
NON_FINITE = re.compile(r"(?i)^(?:[-+]?\.(?:inf|infinity)|nan)$")


class FlowBlocked(Exception):
    """流程在某一阶段被阻塞，携带结构化原因。"""
    def __init__(self, stage: str, outcome: Outcome):
        super().__init__(f"{stage}: {outcome.reason}")
        self.stage = stage
        self.outcome = outcome


@dataclass
class FlowResult:
    stage: str
    ok: bool
    binding: Dict[str, str]
    result: Optional[Dict[str, Any]] = None
    text: str = ""
    issues: List[str] = field(default_factory=list)
    blocked: Optional[Dict[str, Any]] = None
    invalidated: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {"stage": self.stage, "ok": self.ok, "binding": self.binding,
                "result": self.result, "text": self.text, "issues": list(self.issues),
                "blocked": self.blocked, "invalidated": self.invalidated}


def validate_binding(binding: Binding) -> List[str]:
    """绑定五字段校验：非空字符串、period 合法月份。缺项逐条报出，不静默补默认。"""
    problems: List[str] = []
    for key in Binding.__dataclass_fields__:
        value = getattr(binding, key, None)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"binding.{key} 缺失或非字符串")
    if isinstance(binding.period, str) and PERIOD_RE.fullmatch(binding.period) is None:
        problems.append(f"binding.period 非法: {binding.period!r}（应为 YYYY-MM 且月份合法）")
    return problems


def pre_guard_amounts(result: Dict[str, Any]) -> List[str]:
    """金额/范围/非有限数/缺值的前置检查。与 agent_guard 互补，不重复其勾稽判定。"""
    problems: List[str] = []
    if result.get("status") != "success":
        return problems
    amounts = result.get("amounts")
    if amounts is None:
        return ["success 结果缺少 amounts"]
    if not isinstance(amounts, dict):
        return ["amounts 必须是对象"]
    for key in agent_guard.AMOUNTS:
        if key not in amounts:
            problems.append(f"amounts 缺字段: {key}")
            continue
        value = amounts[key]
        if value is None:
            continue
        if not isinstance(value, str):
            problems.append(f"amounts.{key} 必须是元十进制字符串，实际 {type(value).__name__}")
            continue
        if NON_FINITE.match(value.strip()):
            problems.append(f"amounts.{key} 是非有限数: {value!r}")
    return problems


def _block(capability: str, stage: str, reason: str, missing: List[str],
           steps: List[str]) -> FlowBlocked:
    return FlowBlocked(stage, Outcome(capability=capability, status=UNAVAILABLE,
                                      payload=None, missing=missing, reason=reason,
                                      evidence_steps=steps))


class RequestFlow:
    """一次制造业现金流请求：绑定 → 快照 → 结果 → 守卫 → 渲染。

    cache 用于演示"源版本变更使旧结果失效并重新取数"，是进程内缓存，
    不是数据库，不持久、不跨进程，不声称已入库。
    """

    def __init__(self, backend, cache: Optional[Dict[Tuple[str, str, str], Tuple[str, Dict[str, Any]]]] = None):
        self.backend = backend
        self.cache: Dict[Tuple[str, str, str], Tuple[str, Dict[str, Any]]] = cache if cache is not None else {}

    def _cache_key(self, binding: Binding) -> Tuple[str, str, str]:
        return (binding.tenant_id, binding.company_id, binding.period)

    def invalidate_if_stale(self, binding: Binding) -> bool:
        """源版本变更使旧结果失效。返回是否发生了失效。"""
        key = self._cache_key(binding)
        cached = self.cache.get(key)
        if cached is None:
            return False
        cached_revision, _ = cached
        if cached_revision != binding.source_revision:
            del self.cache[key]
            return True
        return False

    def run(self, binding: Binding, *, allow_fixture: bool = False) -> FlowResult:
        problems = validate_binding(binding)
        if problems:
            raise FlowBlocked("bind", Outcome(capability="bind", status=UNAVAILABLE,
                                              payload=None, missing=problems,
                                              reason="可信绑定不完整",
                                              evidence_steps=["由平台认证绑定层提供五字段，不由表格文本或文件名推断。"]))

        invalidated = self.invalidate_if_stale(binding)

        snap_out = read_snapshot(self.backend, binding)
        if snap_out.status == UNAVAILABLE:
            raise _block(CAP_READ_SNAPSHOT, "read_snapshot", snap_out.reason,
                         snap_out.missing, snap_out.evidence_steps)
        snapshot = snap_out.payload or {}

        cached = self.cache.get(self._cache_key(binding))
        source_keys = ("workbook_ref", "sheet", "range", "snapshot_ref")
        cache_matches = (cached is not None and cached[0] == binding.source_revision
                         and isinstance(cached[1], dict)
                         and cached[1].get("run_id") == binding.run_id
                         and isinstance(cached[1].get("source"), dict)
                         and all(cached[1]["source"].get(k) == snapshot.get(k) for k in source_keys)
                         and ("calculation_version" not in snapshot or snapshot["calculation_version"] == cached[1].get("calculation_version")))
        if cache_matches:
            result = copy.deepcopy(cached[1])
        else:
            if cached is not None:
                self.cache.pop(self._cache_key(binding), None)
                invalidated = True
            res_out = read_calculated_result(self.backend, binding, snapshot)
            if res_out.status == UNAVAILABLE:
                raise _block(CAP_READ_RESULT, "read_calculated_result", res_out.reason,
                             res_out.missing, res_out.evidence_steps)
            result = copy.deepcopy(res_out.payload or {})

        pre = pre_guard_amounts(result)
        if pre:
            self.cache.pop(self._cache_key(binding), None)
            raise _block(CAP_READ_RESULT, "guard", "守卫前置检查未通过", pre,
                        ["修正金额字段类型/缺值后重新取数，不手工改写金额。"])

        try:
            agent_guard.validate_result(result, binding.as_dict(), allow_fixture=allow_fixture)
        except agent_guard.ResultError as exc:
            self.cache.pop(self._cache_key(binding), None)
            reason = str(exc)
            steps = ["修正源数据或口径后重新取数，不手工改写金额。"]
            if "full balance" in reason:
                steps = ["仅有部分口径时只报告该部分，另出经营部分视图/说明，不得冒充全口径余额。"]
            raise _block(CAP_READ_RESULT, "guard", reason, [reason], steps)

        if any(result["source"].get(k) != snapshot.get(k) for k in source_keys):
            self.cache.pop(self._cache_key(binding), None)
            raise _block(CAP_READ_RESULT, "guard", "公式结果来源与本次实际快照不符", ["source.snapshot"],
                         ["重新读取同一工作簿/Sheet/区域/快照，不把别次结果绑定为本次来源。"])
        if "calculation_version" in snapshot and result.get("calculation_version") != snapshot["calculation_version"]:
            raise _block(CAP_READ_RESULT, "guard", "公式结果版本与快照指定版本不符", ["calculation_version"],
                         ["取得本次批准的公式版本结果。"])

        # Only fully validated results enter cache; no mutable aliases leak to the caller.
        self.cache[self._cache_key(binding)] = (binding.source_revision, copy.deepcopy(result))

        text = agent_guard.render_result(result, binding.as_dict(), allow_fixture=allow_fixture)
        return FlowResult(stage="done", ok=True, binding=binding.as_dict(), result=result,
                          text=text, issues=[], blocked=None, invalidated=invalidated)


def blocked_report(exc: FlowBlocked, binding: Optional[Binding] = None) -> Dict[str, Any]:
    """把阻塞转成可回传给 Agent 的结构化报告：不生成结果、不心算、不保存。"""
    return {"stage": exc.stage,
            "binding": binding.as_dict() if binding else None,
            "status": UNAVAILABLE,
            "blocked": exc.outcome.as_dict(),
            "answer": f"本阶段未完成：{exc.outcome.reason}。缺项："
                      + "、".join(exc.outcome.missing) + "。未执行保存或通知。"}


def source_revision_of(snapshot: Dict[str, Any]) -> str:
    """快照指纹：用于判断源数据是否变更（本地计算，不是平台版本号）。"""
    return canonical_sha256({k: snapshot.get(k) for k in
                             ("workbook_ref", "sheet", "range", "snapshot_ref")})
