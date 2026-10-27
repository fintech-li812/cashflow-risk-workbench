"""MEM-EVIDENCE-001 本地证据存储核心库（SQLite 事务版）。

任务来源：发包/进阶两个任务_20261023/MEM-EVIDENCE-001/v1/任务书_要求与验收.md
接口依据：规则/制造业Agent周边工程统一接口_v1.md（五字段、request_id、规范JSON、
金额元十进制字符串、mfg-evidence.v1 回执）与 规则/结果边界接口.md（status 闭集、
金额勾稽、origin/fixture 约束）。

性质声明：
- 本模块是本地 SQLite 事务存储，不是 MySQL、不是生产服务、不联网。
- record_id 是本地存储 ID（确定性派生），不是任何数据库主键，不声称已入生产库。
- 校验逻辑继承 WB-AGENT-003 参考候选 agent_guard.py 的口径（金额格式/勾稽/状态闭集），
  本包按 MEM-EVIDENCE-001 任务书补齐持久化、幂等、事务、故障恢复与防混查。
- 所有错误消息脱敏：不打印完整 payload、金额流水、凭据或绝对路径细节。
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------- 常量

SCHEMA_RESULT = "mfg-agent-result.v1"
SCHEMA_RECEIPT = "mfg-evidence.v1"
KIND_RECEIPT = "receipt"
OPERATION_SAVE = "save_cashflow_result"
STATUS_COMMITTED = "committed"

RESULT_STATES = {"success", "missing_inputs", "formula_error", "unavailable"}
CONTEXT_FIELDS = ("tenant_id", "company_id", "period", "source_revision", "run_id")
AMOUNT_FIELDS = ("opening", "inflow", "outflow", "net", "closing",
                 "actual_closing", "difference")

MONEY_RE = re.compile(r"-?(?:0|[1-9][0-9]{0,17})\.[0-9]{2}")
PERIOD_RE = re.compile(r"[0-9]{4}-(?:0[1-9]|1[0-2])")

# CLI 退出码（错误码说明.md 同步维护）
EXIT_OK = 0            # committed / 幂等回放 / 查询成功 / verify 通过
EXIT_INTERNAL = 1      # 非预期内部错误（含测试断言失败）
EXIT_CONFLICT = 2      # 同键异参冲突，旧记录未覆盖
EXIT_NOT_FOUND = 3     # 记录不存在或不属于该身份（不区分，防泄露）
EXIT_INVALID = 4       # 输入校验失败（含 fixture 未显式允许、路径越界）
EXIT_STORE_ERROR = 5   # 存储层错误（锁超时、IO 等），明确返回不无限重试
EXIT_TAMPER = 6        # verify-store 检出哈希/关联/勾稽不一致
EXIT_NON_SUCCESS = 7   # 结果非 success：仅入诊断表，不产生正式回执

FIXTURE_TAG = "【合成离线夹具，非平台真实结果】"

SCHEMA_VERSION = 1
DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_records (
    record_id       TEXT PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    company_id      TEXT NOT NULL,
    operation       TEXT NOT NULL,
    request_id      TEXT NOT NULL,
    period          TEXT NOT NULL,
    source_revision TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    status          TEXT NOT NULL,
    payload_sha256  TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    stored_at       TEXT NOT NULL,
    fixture         INTEGER NOT NULL DEFAULT 0,
    UNIQUE (tenant_id, company_id, operation, request_id)
);
CREATE TABLE IF NOT EXISTS diagnostics (
    diag_id         TEXT PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    company_id      TEXT NOT NULL,
    operation       TEXT NOT NULL,
    request_id      TEXT NOT NULL,
    period          TEXT NOT NULL,
    source_revision TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    result_status   TEXT NOT NULL,
    issues_json     TEXT NOT NULL,
    payload_sha256  TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    stored_at       TEXT NOT NULL,
    fixture         INTEGER NOT NULL DEFAULT 0,
    UNIQUE (tenant_id, company_id, operation, request_id)
);
"""


class ValidationError(Exception):
    """输入校验失败。消息只允许含字段名/规则名，不含 payload 值。"""


class FaultInjected(Exception):
    """受控故障注入（仅测试入口触发）。"""


# ---------------------------------------------------------------- 规范JSON

def canonical_bytes(obj: Any) -> bytes:
    """统一接口固定规范JSON：UTF8、键排序、紧凑分隔、拒绝 NaN/Infinity。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _new_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}-" + digest[:24]


def make_record_id(tenant_id: str, company_id: str, operation: str,
                   request_id: str, payload_sha256: str) -> str:
    """确定性本地存储 ID：同键同摘要必得同 ID，便于幂等回放与关联篡改检测。"""
    return _new_id("ev", tenant_id, company_id, operation, request_id, payload_sha256)


# ---------------------------------------------------------------- 结果校验
# 口径继承 agent_guard.py（WB-AGENT-003 参考候选），并按本包任务书强化。

def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValidationError(reason)


def _money(value: Any, field: str) -> Decimal:
    _require(isinstance(value, str) and MONEY_RE.fullmatch(value) is not None,
             f"amounts.{field} 必须是元为单位、2位小数的十进制字符串（最多18位整数）")
    dec = Decimal(value)
    _require(dec.is_finite(), f"amounts.{field} 必须为有限值")
    return dec


def validate_result(data: Any, context: Any, *, allow_fixture: bool = False) -> Dict[str, Any]:
    """校验 mfg-agent-result.v1 结果对象与可信 context 的一致性。通过则返回 data。"""
    _require(isinstance(data, dict) and isinstance(context, dict), "结果与context必须是JSON对象")
    _require(data.get("schema_version") == SCHEMA_RESULT, "schema_version 不支持")
    for key in CONTEXT_FIELDS:
        _require(isinstance(context.get(key), str) and bool(context[key].strip()),
                 f"可信context缺少字段 {key}")
        _require(data.get(key) == context[key], f"结果与context身份不一致: {key}")
    _require(PERIOD_RE.fullmatch(data["period"]) is not None,
             "period 必须为 YYYY-MM 且月份合法")
    _require(data.get("industry") == "manufacturing", "超出本期范围的行业")
    status = data.get("status")
    _require(isinstance(status, str) and status in RESULT_STATES, "未知 status")
    _require(isinstance(data.get("issues"), list)
             and all(isinstance(x, str) and x.strip() for x in data["issues"]),
             "issues 必须为非空字符串列表")
    if status != "success":
        _require(bool(data["issues"]), "非 success 必须给出原因")
        _require(data.get("amounts") is None, "非 success 不得携带金额")
        return data
    # ---- success 分支 ----
    origin = data.get("origin")
    if origin == "offline_fixture":
        _require(allow_fixture, "默认拒绝 offline_fixture；测试须显式 --allow-fixture")
    else:
        _require(origin == "qwen_sheet", "origin 仅接受 qwen_sheet（或测试显式允许 fixture）")
    _require(data.get("unit") == "CNY", "unit 必须为 CNY")
    _require(isinstance(data.get("calculation_version"), str)
             and bool(data["calculation_version"].strip()), "缺少 calculation_version")
    _require(data.get("coverage") == "full_cashflow", "coverage 必须为 full_cashflow，不得以部分冒充")
    _require(data["issues"] == [], "success 不得隐藏未解决缺项")
    source = data.get("source")
    _require(isinstance(source, dict) and all(
        isinstance(source.get(k), str) and source[k].strip()
        for k in ("workbook_ref", "sheet", "range", "snapshot_ref")), "缺少 source 定位字段")
    amounts = data.get("amounts")
    _require(isinstance(amounts, dict) and set(amounts) == set(AMOUNT_FIELDS),
             "amounts 字段缺失或出现未声明字段")
    vals = {k: _money(amounts[k], k) for k in AMOUNT_FIELDS
            if k not in ("actual_closing", "difference")}
    _require(vals["inflow"] >= 0 and vals["outflow"] >= 0, "流入/流出不得为负")
    _require(vals["net"] == vals["inflow"] - vals["outflow"], "净额勾稽不符（差一分也不接受）")
    _require(vals["closing"] == vals["opening"] + vals["net"], "期末勾稽不符（差一分也不接受）")
    if amounts["actual_closing"] is None:
        _require(amounts["difference"] is None, "缺独立实际余额时 difference 必须同为 null")
    else:
        actual = _money(amounts["actual_closing"], "actual_closing")
        diff = _money(amounts["difference"], "difference")
        _require(diff == actual - vals["closing"], "勾稽差异计算不符（差一分也不接受）")
    return data


# ---------------------------------------------------------------- 存储

class EvidenceStore:
    """本地 SQLite 证据存储：幂等保存、精确回查、历史追加、篡改复核。

    事务边界：正式记录写入与回执生成之间以 BEGIN IMMEDIATE ... COMMIT 包裹；
    回执只在 COMMIT 成功之后产生；任何 COMMIT 前异常都回滚，不留半条记录。
    锁等待由 PRAGMA busy_timeout 一次性承担，超时明确报错，不做应用层无限重试。
    """

    def __init__(self, db_path: Path, *, busy_timeout_ms: int = 5000):
        self._path = db_path
        self._con = sqlite3.connect(str(db_path), timeout=busy_timeout_ms / 1000.0)
        self._con.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
        self._con.execute("PRAGMA journal_mode = WAL")
        self._con.execute("PRAGMA foreign_keys = ON")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._con:
            self._con.executescript(DDL)
            row = self._con.execute(
                "SELECT MAX(version) FROM schema_migrations").fetchone()
            if row[0] is None:
                self._con.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, utc_now()))

    # ---------------- 路径安全 ----------------

    @staticmethod
    def resolve_store_path(store_arg: str, workdir: str) -> Path:
        """--store 必须解析在 --workdir 之内；拒绝 .. 越界与绝对路径穿越。"""
        wd = Path(workdir).resolve()
        candidate = Path(store_arg)
        if not candidate.is_absolute():
            candidate = wd / candidate
        resolved = candidate.resolve()
        if resolved != wd and wd not in resolved.parents:
            raise ValidationError("store 路径越界：必须位于指定 workdir 之内")
        if resolved.exists() and resolved.is_file() and resolved.stat().st_size > 0:
            with open(resolved, "rb") as fh:
                head = fh.read(16)
            if head != b"SQLite format 3\x00":
                raise ValidationError("拒绝覆盖非本模块创建的既有文件（非 SQLite 头）")
        return resolved

    # ---------------- save ----------------

    def save(self, result: Dict[str, Any], context: Dict[str, Any],
             request_id: str, *, allow_fixture: bool = False,
             fault: str = "none") -> Tuple[Dict[str, Any], int]:
        """保存结果。返回 (outcome, exit_code)。回执只在 COMMIT 之后产生。"""
        try:
            validate_result(result, context, allow_fixture=allow_fixture)
        except ValidationError as exc:
            return ({"status": "invalid", "reason": str(exc)}, EXIT_INVALID)
        if not isinstance(request_id, str) or not request_id.strip():
            return ({"status": "invalid", "reason": "request_id 必须为非空字符串"},
                    EXIT_INVALID)

        fixture = 1 if result.get("origin") == "offline_fixture" else 0
        digest = canonical_sha256(result)
        key = (result["tenant_id"], result["company_id"], OPERATION_SAVE, request_id)

        if result["status"] != "success":
            return self._save_diagnostic(result, request_id, digest, fixture, fault)

        try:
            self._con.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            return ({"status": "store_error",
                     "reason": "数据库锁超时（busy_timeout 已用尽），明确失败，未重试"},
                    EXIT_STORE_ERROR)
        try:
            row = self._con.execute(
                "SELECT record_id, payload_sha256, stored_at FROM evidence_records "
                "WHERE tenant_id=? AND company_id=? AND operation=? AND request_id=?",
                key).fetchone()
            if row is not None:
                self._con.execute("ROLLBACK")
                if row[1] == digest:
                    receipt = self._receipt(result, request_id, row[0], row[1], row[2],
                                            fixture, replayed=True)
                    return ({"status": STATUS_COMMITTED, "receipt": receipt,
                             "idempotent_replay": True}, EXIT_OK)
                return ({"status": "conflict",
                         "reason": "同一 (tenant_id,company_id,operation,request_id) "
                                   "已存在不同 payload 摘要，拒绝覆盖旧记录",
                         "existing_record_id": row[0]}, EXIT_CONFLICT)
            record_id = make_record_id(key[0], key[1], key[2], key[3], digest)
            stored_at = utc_now()
            self._con.execute(
                "INSERT INTO evidence_records(record_id, tenant_id, company_id, operation,"
                " request_id, period, source_revision, run_id, status, payload_sha256,"
                " payload_json, stored_at, fixture) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (record_id, result["tenant_id"], result["company_id"], OPERATION_SAVE,
                 request_id, result["period"], result["source_revision"], result["run_id"],
                 STATUS_COMMITTED, digest, canonical_bytes(result).decode("utf-8"),
                 stored_at, fixture))
            if fault == "before_commit":
                self._con.execute("ROLLBACK")
                raise FaultInjected("fault-inject: before_commit（事务已回滚，无半条记录）")
            self._con.execute("COMMIT")
        except FaultInjected:
            raise
        except sqlite3.IntegrityError:
            # 并发下同键竞态：唯一约束兜底，重新按回放/冲突判定
            self._con.execute("ROLLBACK")
            return self._retry_after_unique_race(result, request_id, digest, fixture)
        except sqlite3.OperationalError:
            self._con.execute("ROLLBACK")
            return ({"status": "store_error", "reason": "SQLite 操作失败（脱敏），事务已回滚"},
                    EXIT_STORE_ERROR)
        if fault == "after_commit":
            # 模拟"已提交但回执未返回进程即崩溃"。只能在受控子进程使用。
            import os
            os._exit(42)
        receipt = self._receipt(result, request_id, record_id, digest, stored_at,
                                fixture, replayed=False)
        return ({"status": STATUS_COMMITTED, "receipt": receipt,
                 "idempotent_replay": False}, EXIT_OK)

    def _retry_after_unique_race(self, result, request_id, digest, fixture):
        key = (result["tenant_id"], result["company_id"], OPERATION_SAVE, request_id)
        row = self._con.execute(
            "SELECT record_id, payload_sha256, stored_at FROM evidence_records "
            "WHERE tenant_id=? AND company_id=? AND operation=? AND request_id=?",
            key).fetchone()
        if row is None:
            return ({"status": "store_error",
                     "reason": "唯一约束冲突后未找到既有记录，状态不确定，如实报错"},
                    EXIT_STORE_ERROR)
        if row[1] == digest:
            return ({"status": STATUS_COMMITTED,
                     "receipt": self._receipt(result, request_id, row[0], row[1], row[2],
                                              fixture, replayed=True),
                     "idempotent_replay": True}, EXIT_OK)
        return ({"status": "conflict",
                 "reason": "并发下同键异参，拒绝覆盖", "existing_record_id": row[0]},
                EXIT_CONFLICT)

    def _save_diagnostic(self, result, request_id, digest, fixture, fault):
        """非 success：只入诊断表，绝不产生 committed 回执。"""
        key = (result["tenant_id"], result["company_id"], OPERATION_SAVE, request_id)
        try:
            self._con.execute("BEGIN IMMEDIATE")
            row = self._con.execute(
                "SELECT diag_id, payload_sha256 FROM diagnostics "
                "WHERE tenant_id=? AND company_id=? AND operation=? AND request_id=?",
                key).fetchone()
            if row is not None:
                self._con.execute("ROLLBACK")
                if row[1] == digest:
                    return ({"status": "diagnosed", "diag_id": row[0],
                             "idempotent_replay": True,
                             "note": "非 success 结果不产生正式回执"}, EXIT_NON_SUCCESS)
                return ({"status": "conflict",
                         "reason": "同键诊断已存在且摘要不同，拒绝覆盖"}, EXIT_CONFLICT)
            diag_id = _new_id("diag", key[0], key[1], key[2], key[3], digest)
            self._con.execute(
                "INSERT INTO diagnostics(diag_id, tenant_id, company_id, operation,"
                " request_id, period, source_revision, run_id, result_status, issues_json,"
                " payload_sha256, payload_json, stored_at, fixture)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (diag_id, key[0], key[1], key[2], key[3], result["period"],
                 result["source_revision"], result["run_id"], result["status"],
                 canonical_bytes(result["issues"]).decode("utf-8"), digest,
                 canonical_bytes(result).decode("utf-8"), utc_now(), fixture))
            if fault == "before_commit":
                self._con.execute("ROLLBACK")
                raise FaultInjected("fault-inject: before_commit（诊断事务已回滚）")
            self._con.execute("COMMIT")
        except FaultInjected:
            raise
        except sqlite3.OperationalError:
            self._con.execute("ROLLBACK")
            return ({"status": "store_error", "reason": "SQLite 操作失败（脱敏），事务已回滚"},
                    EXIT_STORE_ERROR)
        return ({"status": "diagnosed", "diag_id": diag_id,
                 "idempotent_replay": False,
                 "note": "非 success 结果仅入诊断表，未产生正式保存回执"},
                EXIT_NON_SUCCESS)

    def _receipt(self, result, request_id, record_id, digest, stored_at,
                 fixture, *, replayed) -> Dict[str, Any]:
        receipt = {
            "schema_version": SCHEMA_RECEIPT,
            "kind": KIND_RECEIPT,
            "operation": OPERATION_SAVE,
            "tenant_id": result["tenant_id"],
            "company_id": result["company_id"],
            "period": result["period"],
            "source_revision": result["source_revision"],
            "run_id": result["run_id"],
            "request_id": request_id,
            "record_id": record_id,
            "payload_sha256": digest,
            "stored_at": stored_at,
            "status": STATUS_COMMITTED,
            "idempotent_replay": replayed,
            "note": "本地SQLite存储ID，不是MySQL主键；committed仅指本地库原子提交完成",
        }
        if fixture:
            receipt["fixture_marker"] = FIXTURE_TAG
        return receipt

    # ---------------- get / history ----------------

    def get(self, tenant_id: str, company_id: str, record_id: str
            ) -> Tuple[Dict[str, Any], int]:
        """精确读取。记录不存在与属于其他身份统一返回 not_found，不泄露别家存在性。"""
        row = self._con.execute(
            "SELECT tenant_id, company_id, period, source_revision, run_id, request_id,"
            " status, payload_sha256, payload_json, stored_at, fixture"
            " FROM evidence_records WHERE record_id=?", (record_id,)).fetchone()
        if row is None or row[0] != tenant_id or row[1] != company_id:
            return ({"status": "not_found",
                     "reason": "记录不存在或不属于指定身份（两者不区分，防混查泄露）"},
                    EXIT_NOT_FOUND)
        payload = json.loads(row[8])
        actual = hashlib.sha256(row[8].encode("utf-8")).hexdigest()
        if actual != row[7]:
            return ({"status": "tampered",
                     "reason": "读时复核发现摘要与存储内容不一致", "record_id": record_id},
                    EXIT_TAMPER)
        receipt = {"schema_version": SCHEMA_RECEIPT, "kind": KIND_RECEIPT,
                   "operation": OPERATION_SAVE, "tenant_id": row[0], "company_id": row[1],
                   "period": row[2], "source_revision": row[3], "run_id": row[4],
                   "request_id": row[5], "record_id": record_id,
                   "payload_sha256": row[7], "stored_at": row[9], "status": row[6]}
        out = {"status": "ok", "record": payload, "receipt": receipt}
        if row[10]:
            out["fixture_marker"] = FIXTURE_TAG
        return (out, EXIT_OK)

    def history(self, tenant_id: str, company_id: str, period: str
                ) -> Tuple[Dict[str, Any], int]:
        """同主体同期间历史（只追加、不覆盖）。

        当前有效选择规则：限定 (tenant_id, company_id, period) 后取 stored_at 最新
        （并列时 record_id 字典序最小）的那一条；绝不以 MAX(record_id) 跨主体取“最新”。
        """
        rows = self._con.execute(
            "SELECT record_id, source_revision, run_id, request_id, payload_sha256,"
            " stored_at, fixture FROM evidence_records"
            " WHERE tenant_id=? AND company_id=? AND period=?"
            " ORDER BY stored_at ASC, record_id ASC",
            (tenant_id, company_id, period)).fetchall()
        if not rows:
            return ({"status": "not_found",
                     "reason": "该主体/期间无任何已提交记录"}, EXIT_NOT_FOUND)
        current = rows[-1]
        entries = []
        for r in rows:
            entries.append({
                "record_id": r[0], "source_revision": r[1], "run_id": r[2],
                "request_id": r[3], "payload_sha256": r[4], "stored_at": r[5],
                "is_current_effective": r[0] == current[0],
                "fixture": bool(r[6]),
            })
        return ({"status": "ok", "tenant_id": tenant_id, "company_id": company_id,
                 "period": period, "entries": entries,
                 "current_effective_record_id": current[0],
                 "selection_rule": "同tenant_id+company_id+period内stored_at最新"
                                   "（并列取record_id字典序最小）；不跨主体取MAX"},
                EXIT_OK)

    # ---------------- verify-store ----------------

    def verify_store(self) -> Tuple[Dict[str, Any], int]:
        """读时复核：摘要、record_id 关联、身份一致性、success 勾稽。

        检测边界见 trust_boundary.md：普通哈希不能抵御可重写整库及所有可信摘要的攻击者。
        """
        problems: List[Dict[str, str]] = []
        rows = self._con.execute(
            "SELECT record_id, tenant_id, company_id, operation, request_id, period,"
            " source_revision, run_id, status, payload_sha256, payload_json, stored_at"
            " FROM evidence_records").fetchall()
        for r in rows:
            (record_id, tenant, company, operation, request_id, period,
             source_revision, run_id, status, digest, payload_json, stored_at) = r
            try:
                payload = json.loads(payload_json)
            except ValueError:
                problems.append({"record_id": record_id, "check": "payload_json 无法解析"})
                continue
            actual = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            if actual != digest:
                problems.append({"record_id": record_id, "check": "payload_sha256 与内容不符"})
            expect_id = make_record_id(tenant, company, operation, request_id, digest)
            if expect_id != record_id:
                problems.append({"record_id": record_id, "check": "record_id 与身份/摘要关联不符"})
            for f, v in (("tenant_id", tenant), ("company_id", company),
                         ("period", period), ("source_revision", source_revision),
                         ("run_id", run_id)):
                if payload.get(f) != v:
                    problems.append({"record_id": record_id,
                                     "check": f"索引列与 payload 字段不一致: {f}"})
            if not stored_at:
                problems.append({"record_id": record_id, "check": "stored_at 缺失"})
            if payload.get("status") == "success":
                ctx = {k: payload.get(k) for k in CONTEXT_FIELDS}
                try:
                    validate_result(payload, ctx,
                                    allow_fixture=(payload.get("origin") == "offline_fixture"))
                except ValidationError as exc:
                    problems.append({"record_id": record_id,
                                     "check": "success 结果勾稽/格式复核失败: " + str(exc)})
        if problems:
            return ({"status": "tampered", "problem_count": len(problems),
                     "problems": problems}, EXIT_TAMPER)
        return ({"status": "ok", "checked_records": len(rows)}, EXIT_OK)

    def count_records(self, tenant_id: str, company_id: str, request_id: str) -> int:
        row = self._con.execute(
            "SELECT COUNT(*) FROM evidence_records"
            " WHERE tenant_id=? AND company_id=? AND request_id=?",
            (tenant_id, company_id, request_id)).fetchone()
        return int(row[0])

    def close(self) -> None:
        self._con.close()
