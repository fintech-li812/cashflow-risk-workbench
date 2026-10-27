"""mfg-agent-result.v1 结果校验守卫。

继承来源：01_源文件/参考候选/agent_guard.py（sha256 eb99d420e2ac7ef1352b448d0c29e1430d0a65cd80a76111eee3dc27c96055c1）。
本文件是**防御式改写**：原实现直接下标取值（data["period"] / data["issues"] / data["amounts"]），
缺键时会抛 KeyError / TypeError 而不是受控的 ResultError，与本任务“程序异常不可伪装成功”的边界冲突。
校验规则、状态闭集、金额正则与原文件保持一致，不新增状态词、不改金额口径；差异登记在 04_继承与改动.csv。

本模块不做模型推理、不连服务器、不读写表格、不计算现金流。
"""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

VERSION = "mfg-agent-result.v1"
STATES = ("success", "missing_inputs", "formula_error", "unavailable")
CONTEXT_KEYS = ("tenant_id", "company_id", "period", "source_revision", "run_id")
AMOUNTS = ("opening", "inflow", "outflow", "net", "closing", "actual_closing", "difference")
SOURCE_KEYS = ("workbook_ref", "sheet", "range", "snapshot_ref")
PERIOD_RE = re.compile(r"[0-9]{4}-(?:0[1-9]|1[0-2])")
MONEY_RE = re.compile(r"-?(?:0|[1-9][0-9]{0,17})\.[0-9]{2}")
DIGITS_RE = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")

REQUIRED_RESULT_KEYS = (
    "schema_version", "industry", "status", "issues",
    "tenant_id", "company_id", "period", "source_revision", "run_id",
)


class ResultError(ValueError):
    """受控校验失败。消息可直接返回给调用者，不含凭据与路径。"""

    def __init__(self, reason: str, *, field: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.field = field


def canonical_bytes(obj: Any) -> bytes:
    """统一规范 JSON：sort_keys / ensure_ascii=False / 紧凑分隔 / 禁 NaN。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def _require(ok: bool, reason: str, *, field: str = "") -> None:
    if not ok:
        raise ResultError(reason, field=field)


def money(value: Any) -> Decimal:
    """金额必须是元、2 位小数的十进制字符串，整数位不超过 18 位。"""
    _require(isinstance(value, str), "amount must be a decimal string in yuan", field="amounts")
    _require(MONEY_RE.fullmatch(value) is not None,
             "amount must be a finite decimal string in yuan, at most 18 integer digits and 2 decimals",
             field="amounts")
    try:
        return Decimal(value)
    except InvalidOperation:  # pragma: no cover - 正则已拦截，保留兜底
        raise ResultError("amount is not a valid decimal", field="amounts")


def load_result_json(text: str) -> Any:
    """解析结果 JSON。显式拒绝 NaN / Infinity / -Infinity 等非有限值。"""

    def _reject_constant(name: str) -> Any:
        raise ResultError("non-finite number is not allowed in result json: " + name,
                          field="json")

    def _unique_pairs(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ResultError("duplicate JSON key: " + key, field="json")
            obj[key] = value
        return obj

    return json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_unique_pairs)


def _check_context(context: Dict[str, Any]) -> None:
    _require(isinstance(context, dict), "trusted context must be an object", field="context")
    for key in CONTEXT_KEYS:
        value = context.get(key)
        _require(isinstance(value, str) and bool(value.strip()),
                 "trusted context missing or empty: " + key, field=key)
    _require(PERIOD_RE.fullmatch(context["period"]) is not None,
             "trusted context period must be YYYY-MM with valid month", field="period")


def validate_result(data: Any, context: Any, *, allow_fixture: bool = False) -> Dict[str, Any]:
    """校验结果对象与可信上下文。成功返回原对象；失败抛 ResultError。"""
    _require(isinstance(data, dict), "result must be a JSON object", field="root")
    _check_context(context)

    for key in REQUIRED_RESULT_KEYS:
        _require(key in data, "result missing required field: " + key, field=key)
    _require(data.get("schema_version") == VERSION,
             "unsupported schema version", field="schema_version")

    for key in CONTEXT_KEYS:
        _require(isinstance(data.get(key), str) and bool(data[key].strip()),
                 "result identity field empty: " + key, field=key)
        _require(data[key] == context[key],
                 "context mismatch: " + key, field=key)

    _require(PERIOD_RE.fullmatch(data["period"]) is not None,
             "period must be YYYY-MM with valid month", field="period")
    _require(data.get("industry") == "manufacturing",
             "out of scope industry", field="industry")

    status = data.get("status")
    _require(isinstance(status, str) and status in STATES,
             "unknown status (closed set: success/missing_inputs/formula_error/unavailable)",
             field="status")

    issues = data.get("issues")
    _require(isinstance(issues, list) and all(isinstance(x, str) and bool(x.strip()) for x in issues),
             "issues must be a list of nonempty strings", field="issues")

    if status != "success":
        _require(bool(issues), "non-success requires at least one reason", field="issues")
        _require(data.get("amounts") is None,
                 "non-success cannot expose a completed result", field="amounts")
        return data

    _require(data.get("origin") == "qwen_sheet"
             or (allow_fixture and data.get("origin") == "offline_fixture"),
             "production result must come from a bound source; offline_fixture needs explicit flag",
             field="origin")
    _require(data.get("unit") == "CNY", "result must be yuan", field="unit")
    _require(data.get("coverage") == "full_cashflow",
             "cannot claim full balance from partial cashflow", field="coverage")
    calculation_version = data.get("calculation_version")
    _require(isinstance(calculation_version, str) and bool(calculation_version.strip()),
             "missing calculation version", field="calculation_version")
    _require(issues == [], "success cannot hide unresolved input issues", field="issues")

    source = data.get("source")
    _require(isinstance(source, dict), "missing source locator", field="source")
    for key in SOURCE_KEYS:
        value = source.get(key)
        _require(isinstance(value, str) and bool(value.strip()),
                 "missing source locator field: " + key, field="source")

    amounts = data.get("amounts")
    _require(isinstance(amounts, dict), "missing amounts", field="amounts")
    extra = set(amounts) - set(AMOUNTS)
    missing = set(AMOUNTS) - set(amounts)
    _require(not extra and not missing,
             "amounts must contain exactly the seven keys; missing=%s unexpected=%s"
             % (sorted(missing), sorted(extra)), field="amounts")

    vals = {k: money(amounts[k]) for k in AMOUNTS if k not in ("actual_closing", "difference")}
    _require(vals["inflow"] >= 0 and vals["outflow"] >= 0,
             "gross inflow/outflow must not be negative", field="amounts")
    _require(vals["net"] == vals["inflow"] - vals["outflow"],
             "net does not reconcile", field="amounts.net")
    _require(vals["closing"] == vals["opening"] + vals["net"],
             "balance does not reconcile", field="amounts.closing")

    if amounts["actual_closing"] is None:
        _require(amounts["difference"] is None,
                 "missing actual balance must not produce a difference", field="amounts.difference")
    else:
        actual = money(amounts["actual_closing"])
        difference = money(amounts["difference"])
        _require(difference == actual - vals["closing"],
                 "difference is incorrect", field="amounts.difference")
    return data


def reconciliation_state(data: Dict[str, Any]) -> str:
    """勾稽状态：只描述本次结果是否完成独立余额核对，不改变业务字段。"""
    amounts = data.get("amounts") or {}
    if amounts.get("actual_closing") is None or amounts.get("difference") is None:
        return "not_performed"
    return "completed" if Decimal(amounts["difference"]) == 0 else "difference_pending_review"


def difference_is_zero(data: Dict[str, Any]) -> bool:
    amounts = data.get("amounts") or {}
    if amounts.get("difference") is None:
        return False
    return Decimal(amounts["difference"]) == 0
