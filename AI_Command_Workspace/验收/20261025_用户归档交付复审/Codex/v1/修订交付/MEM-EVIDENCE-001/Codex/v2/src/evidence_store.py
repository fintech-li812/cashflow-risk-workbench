"""MEM-EVIDENCE-001：本地 SQLite 事务化证据存储。

边界（与任务书一致）：
- 只做制造业现金流结果的**本地**可靠存储与回查；不连 MySQL、不连千问、不部署服务。
- 正式结果只在事务 COMMIT 成功之后生成 mfg-evidence.v1 回执；committed 仅表示本地库已落库，
  不表示服务端 MySQL 已入库。
- 幂等唯一键 = (tenant_id, company_id, operation, request_id)；同键同规范摘要回放原 record_id，
  同键异摘要冲突且不覆盖。
- 历史只追加（触发器禁止 UPDATE/DELETE）；当前有效记录的选择规则显式可解释，绝不跨企业取 MAX(id)。
- 所有 SQL 全部参数化；不接收任何外部 SQL；数据库文件路径必须由调用者限定在测试工作目录内。

本文件不实现任何金额计算，计算口径校验委托 src/result_guard.py。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from result_guard import (CONTEXT_KEYS, canonical_sha256, load_result_json,
                          reconciliation_state, validate_result)

STORE_SCHEMA_VERSION = "evidence-schema-1"
RECEIPT_SCHEMA = "mfg-evidence.v1"
OPERATION_SAVE = "save_cashflow_result"

STATUS_COMMITTED = "committed"
STATUS_CONFLICT = "conflict"
STATUS_NOT_FOUND = "not_found"
STATUS_SCOPE_DENIED = "denied"
STATUS_BUSY = "busy"
STATUS_UNKNOWN = "unknown"
STATUS_BLOCKED = "blocked"

FIXTURE_MARK = "【合成数据·非生产·offline_fixture】"

RECORD_ID_RE = re.compile(r"loc-[0-9a-f]{24}")


class StoreError(Exception):
    """受控失败。code 决定 CLI 退出码（见 错误码说明.md）。"""

    def __init__(self, code: str, message: str, *, status: str = "", details: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status or code.lower()
        self.details = details if details is not None else {}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_record_id(tenant_id: str, company_id: str, operation: str,
                   request_id: str, payload_sha256: str) -> str:
    """确定性 record_id：同键同摘要必然同 ID，便于回查与重放比对。"""
    seed = "|".join((tenant_id, company_id, operation, request_id, payload_sha256))
    return "loc-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


DDL_V1 = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_record (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id           TEXT NOT NULL UNIQUE,
    tenant_id           TEXT NOT NULL,
    company_id          TEXT NOT NULL,
    period              TEXT NOT NULL,
    source_revision     TEXT NOT NULL,
    run_id              TEXT NOT NULL,
    operation           TEXT NOT NULL,
    request_id          TEXT NOT NULL,
    status              TEXT NOT NULL,
    origin              TEXT NOT NULL,
    is_fixture          INTEGER NOT NULL,
    reconciliation_state TEXT NOT NULL,
    payload_sha256      TEXT NOT NULL,
    payload_json        TEXT NOT NULL,
    stored_at           TEXT NOT NULL,
    UNIQUE (tenant_id, company_id, operation, request_id)
);
CREATE INDEX IF NOT EXISTS idx_evidence_scope
    ON evidence_record (tenant_id, company_id, period, source_revision, run_id);
CREATE TABLE IF NOT EXISTS diagnostic_record (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id        TEXT NOT NULL,
    company_id       TEXT NOT NULL,
    period           TEXT NOT NULL,
    source_revision  TEXT NOT NULL,
    run_id           TEXT NOT NULL,
    request_id       TEXT NOT NULL,
    result_status    TEXT NOT NULL,
    reason           TEXT NOT NULL,
    payload_sha256   TEXT NOT NULL,
    payload_json     TEXT NOT NULL,
    stored_at        TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_evidence_no_update
BEFORE UPDATE ON evidence_record
BEGIN
    SELECT RAISE(ABORT, 'append-only: evidence_record cannot be updated');
END;
CREATE TRIGGER IF NOT EXISTS trg_evidence_no_delete
BEFORE DELETE ON evidence_record
BEGIN
    SELECT RAISE(ABORT, 'append-only: evidence_record cannot be deleted');
END;
CREATE TRIGGER IF NOT EXISTS trg_diag_no_update
BEFORE UPDATE ON diagnostic_record
BEGIN
    SELECT RAISE(ABORT, 'append-only: diagnostic_record cannot be updated');
END;
"""


def load_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return load_result_json(handle.read())


class Store:
    """本地 SQLite 事务存储。"""

    def __init__(self, conn: sqlite3.Connection, path: str):
        self.conn = conn
        self.path = path

    @classmethod
    def open(cls, path: str, *, busy_timeout_ms: int = 3000) -> "Store":
        try:
            conn = sqlite3.connect(path, timeout=busy_timeout_ms / 1000.0,
                                   isolation_level=None)
        except sqlite3.Error as exc:  # pragma: no cover - 打开失败与环境相关
            raise StoreError("STORAGE_BUSY", "cannot open sqlite store: %s" % type(exc).__name__,
                             status=STATUS_BUSY)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout = %d" % int(busy_timeout_ms))
            conn.execute("PRAGMA journal_mode = DELETE")
            conn.execute("PRAGMA synchronous = FULL")
        except sqlite3.OperationalError as exc:
            conn.close()
            raise StoreError("STORAGE_BUSY",
                             "store is locked by another process: %s" % exc, status=STATUS_BUSY)
        store = cls(conn, path)
        store._migrate()
        return store

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        """迁移：空库建立 v1；已标记 v1 无动作；未知版本报错不静默升级。"""
        try:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_meta ("
                "key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            row = self.conn.execute(
                "SELECT value FROM schema_meta WHERE key='store_schema_version'").fetchone()
            current = row["value"] if row is not None else None
            if current is None:
                self.conn.executescript(DDL_V1)
                self.conn.execute(
                    "INSERT OR REPLACE INTO schema_meta(key,value) "
                    "VALUES('store_schema_version',?)", (STORE_SCHEMA_VERSION,))
            elif current != STORE_SCHEMA_VERSION:
                raise StoreError("INTERNAL_ERROR",
                                 "unknown store schema version: %s" % current)
        except sqlite3.OperationalError as exc:
            # 库被其他进程独占时明确报锁等待，不做重试循环。
            raise StoreError("STORAGE_BUSY",
                             "store is busy during schema check: %s" % exc, status=STATUS_BUSY)

    # ---------------- save ----------------

    def save(self, result: Dict[str, Any], context: Dict[str, Any], request_id: str, *,
             allow_fixture: bool = False, operation: str = OPERATION_SAVE,
             fault_before_commit: bool = False, fault_after_commit: bool = False,
             simulate_unknown: bool = False) -> Dict[str, Any]:
        """保存正式结果。成功/回放/冲突/锁等待全部显式返回，不静默重试。"""
        if operation != OPERATION_SAVE:
            raise StoreError("VALIDATION_FAILED", "operation must be save_cashflow_result", status="rejected")
        if not isinstance(request_id, str) or not request_id.strip():
            raise StoreError("VALIDATION_FAILED", "request_id must be a nonempty string",
                             status="rejected")
        try:
            validate_result(result, context, allow_fixture=allow_fixture)
        except ValueError as exc:
            raise StoreError("VALIDATION_FAILED", str(exc), status="rejected")

        if result.get("status") != "success":
            raise StoreError("VALIDATION_FAILED",
                             "only success results can be stored as formal evidence; "
                             "use --save-diagnostic for non-success", status="rejected")

        digest = canonical_sha256(result)
        tenant_id = context["tenant_id"]
        company_id = context["company_id"]
        is_fixture = 1 if result.get("origin") == "offline_fixture" else 0
        payload_json = json.dumps(result, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":"), allow_nan=False)
        stored_at = utc_now()
        record_id = make_record_id(tenant_id, company_id, operation, request_id, digest)

        try:
            self.conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            raise StoreError("STORAGE_BUSY",
                             "cannot begin transaction: %s" % exc, status=STATUS_BUSY)

        try:
            existing = self.conn.execute(
                "SELECT * FROM evidence_record WHERE tenant_id=? AND company_id=? "
                "AND operation=? AND request_id=?",
                (tenant_id, company_id, operation, request_id)).fetchone()
            if existing is not None:
                if existing["payload_sha256"] != digest:
                    self.conn.execute("ROLLBACK")
                    raise StoreError(
                        "CONFLICT",
                        "same idempotency key with different payload digest: refusing to overwrite",
                        status=STATUS_CONFLICT,
                        details={"record_id": existing["record_id"],
                                 "stored_digest": existing["payload_sha256"][:12],
                                 "incoming_digest": digest[:12]})
                self._validate_row(existing)
                self.conn.execute("COMMIT")
                return {"outcome": "replay", "status": STATUS_COMMITTED,
                        "receipt": self._receipt(existing)}

            self.conn.execute(
                "INSERT INTO evidence_record (record_id, tenant_id, company_id, period, "
                "source_revision, run_id, operation, request_id, status, origin, is_fixture, "
                "reconciliation_state, payload_sha256, payload_json, stored_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (record_id, tenant_id, company_id, context["period"],
                 context["source_revision"], context["run_id"], operation, request_id,
                 STATUS_COMMITTED, result.get("origin", ""), is_fixture,
                 reconciliation_state(result), digest, payload_json, stored_at))

            if fault_before_commit:
                # 提交前故障：不作 COMMIT，直接终止进程，模拟崩溃。
                os._exit(9)

            self.conn.execute("COMMIT")
        except StoreError:
            if self.conn.in_transaction:
                self.conn.execute("ROLLBACK")
            raise
        except sqlite3.IntegrityError as exc:
            self.conn.execute("ROLLBACK")
            row = self.conn.execute(
                "SELECT * FROM evidence_record WHERE tenant_id=? AND company_id=? "
                "AND operation=? AND request_id=?",
                (tenant_id, company_id, operation, request_id)).fetchone()
            if row is not None and row["payload_sha256"] == digest:
                return {"outcome": "replay", "status": STATUS_COMMITTED,
                        "receipt": self._receipt(row)}
            raise StoreError("CONFLICT",
                             "idempotency key collision: %s" % exc, status=STATUS_CONFLICT)
        except sqlite3.OperationalError as exc:
            self.conn.execute("ROLLBACK")
            raise StoreError("STORAGE_BUSY",
                             "sqlite operational error, nothing written: %s" % exc,
                             status=STATUS_BUSY)

        if fault_after_commit:
            # 提交后、回执返回前终止：库里已有记录，但调用方没拿到回执。
            os._exit(9)

        if simulate_unknown:
            # 提交已完成但回执未能确定交付：明确返回未确定态，绝不报成功。
            raise StoreError("UNKNOWN_STATE",
                             "commit finished but receipt delivery unconfirmed; "
                             "re-query with the same request_id before retrying",
                             status=STATUS_UNKNOWN,
                             details={"request_id": request_id, "record_id": record_id})

        row = self.conn.execute(
            "SELECT * FROM evidence_record WHERE record_id=?", (record_id,)).fetchone()
        return {"outcome": "created", "status": STATUS_COMMITTED,
                "receipt": self._receipt(row)}

    def save_diagnostic(self, result: Dict[str, Any], context: Dict[str, Any],
                        request_id: str) -> Dict[str, Any]:
        """非 success 结果只存诊断记录，不生成正式回执。"""
        try:
            validate_result(result, context, allow_fixture=True)
        except ValueError as exc:
            raise StoreError("VALIDATION_FAILED", str(exc), status="rejected")
        if result.get("status") == "success":
            raise StoreError("VALIDATION_FAILED",
                             "diagnostic channel is only for non-success results",
                             status="rejected")
        digest = canonical_sha256(result)
        stored_at = utc_now()
        self.conn.execute(
            "INSERT INTO diagnostic_record (tenant_id, company_id, period, source_revision, "
            "run_id, request_id, result_status, reason, payload_sha256, payload_json, stored_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (context["tenant_id"], context["company_id"], context["period"],
             context["source_revision"], context["run_id"], request_id,
             result.get("status", ""), ";".join(result.get("issues", [])), digest,
             json.dumps(result, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":"), allow_nan=False), stored_at))
        return {"outcome": "diagnostic", "status": STATUS_BLOCKED,
                "request_id": request_id, "result_status": result.get("status"),
                "payload_sha256": digest, "stored_at": stored_at,
                "receipt": None,
                "note": "诊断记录，不是 mfg-evidence.v1 正式回执，不表示结果已保存"}

    # ---------------- read ----------------

    def _validate_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        try:
            payload = load_result_json(row["payload_json"])
            ctx = {key: row[key] for key in CONTEXT_KEYS}
            validate_result(payload, ctx, allow_fixture=True)
            valid = (payload.get("status") == "success"
                     and row["status"] == STATUS_COMMITTED
                     and row["operation"] == OPERATION_SAVE
                     and row["origin"] == payload.get("origin")
                     and bool(row["is_fixture"]) == (payload.get("origin") == "offline_fixture")
                     and row["reconciliation_state"] == reconciliation_state(payload)
                     and row["payload_sha256"] == canonical_sha256(payload)
                     and row["record_id"] == make_record_id(row["tenant_id"], row["company_id"], row["operation"], row["request_id"], row["payload_sha256"]))
            if not valid:
                raise ValueError("record links are inconsistent")
        except (ValueError, TypeError, KeyError):
            raise StoreError("VERIFY_FAILED", "stored payload/receipt/identity link is inconsistent", status="tampered")
        return payload

    def _receipt(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "schema_version": RECEIPT_SCHEMA,
            "kind": "receipt",
            "operation": row["operation"],
            "tenant_id": row["tenant_id"],
            "company_id": row["company_id"],
            "period": row["period"],
            "source_revision": row["source_revision"],
            "run_id": row["run_id"],
            "request_id": row["request_id"],
            "record_id": row["record_id"],
            "payload_sha256": row["payload_sha256"],
            "stored_at": row["stored_at"],
            "status": row["status"],
            "is_fixture": bool(row["is_fixture"]),
            "reconciliation_state": row["reconciliation_state"],
            "note": "本地存储ID，不是MySQL主键；committed 仅表示本地事务已提交",
        }

    def get(self, context: Dict[str, Any], record_id: str) -> Dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM evidence_record WHERE record_id=?", (record_id,)).fetchone()
        if row is None:
            raise StoreError("NOT_FOUND", "no record in this identity scope",
                             status=STATUS_NOT_FOUND)
        if row["tenant_id"] != context["tenant_id"] or row["company_id"] != context["company_id"]:
            # 不泄露他家记录内容：只说明范围内无此记录，退出码区分越权。
            raise StoreError("SCOPE_DENIED",
                             "record is outside the trusted identity scope",
                             status=STATUS_SCOPE_DENIED)
        payload = self._validate_row(row)
        for key in CONTEXT_KEYS:
            if row[key] != context.get(key):
                raise StoreError("SCOPE_DENIED", "record version is outside the trusted context", status=STATUS_SCOPE_DENIED)
        if canonical_sha256(payload) != row["payload_sha256"]:
            raise StoreError("VERIFY_FAILED",
                             "payload digest mismatch on read (record_id=%s)" % row["record_id"],
                             status="tampered",
                             details={"record_id": row["record_id"]})
        return {"record_id": row["record_id"], "receipt": self._receipt(row),
                "payload": payload, "is_fixture": bool(row["is_fixture"]),
                "reconciliation_state": row["reconciliation_state"]}

    def history(self, context: Dict[str, Any], period: str,
                source_revision: Optional[str] = None) -> Dict[str, Any]:
        params: List[Any] = [context["tenant_id"], context["company_id"], period]
        sql = ("SELECT * FROM evidence_record WHERE tenant_id=? AND company_id=? AND period=?")
        if source_revision:
            sql += " AND source_revision=?"
            params.append(source_revision)
        sql += " ORDER BY stored_at ASC, id ASC"
        rows = self.conn.execute(sql, params).fetchall()
        for row in rows:
            self._validate_row(row)
        items = [self._receipt(r) for r in rows]
        revisions = sorted({r["source_revision"] for r in rows})
        runs = sorted({r["run_id"] for r in rows})
        current_id = rows[-1]["record_id"] if rows else None
        for item in items:
            item["is_current"] = item["record_id"] == current_id
        return {
            "scope": {"tenant_id": context["tenant_id"], "company_id": context["company_id"],
                      "period": period},
            "count": len(items),
            "records": items,
            "current_record_id": current_id,
            "current_selection_rule": (
                "仅在同一 tenant_id + company_id + period 内按 (stored_at, id) 排序取最后一条为当前有效；"
                "绝不跨企业/跨租户取 MAX(id)。存在多条 source_revision 时新旧版本共存、旧版不删除也不改写，"
                "调用方须用 --source-revision 显式锁定目标版本。"),
            "distinct_source_revisions": revisions,
            "distinct_run_ids": runs,
            "ambiguous_versions": len(revisions) > 1,
        }

    # ---------------- verify ----------------

    def verify(self) -> Dict[str, Any]:
        problems: List[Dict[str, str]] = []
        rows = self.conn.execute(
            "SELECT * FROM evidence_record ORDER BY id ASC").fetchall()
        for row in rows:
            record_id = row["record_id"]
            try:
                self._validate_row(row)
            except StoreError as exc:
                problems.append({"record_id": record_id, "code": "IDENTITY_LINK_BROKEN", "field": "record", "detail": exc.message})
            try:
                payload = json.loads(row["payload_json"])
            except ValueError:
                problems.append({"record_id": record_id, "code": "PAYLOAD_NOT_JSON",
                                 "field": "payload_json", "detail": "stored payload is not valid json"})
                continue
            if canonical_sha256(payload) != row["payload_sha256"]:
                problems.append({"record_id": record_id, "code": "PAYLOAD_HASH_MISMATCH",
                                 "field": "payload_sha256",
                                 "detail": "digest %s does not match stored payload"
                                           % row["payload_sha256"][:12]})
            ctx = {k: row[k] for k in CONTEXT_KEYS}
            for key in CONTEXT_KEYS:
                if payload.get(key) != ctx[key]:
                    problems.append({"record_id": record_id, "code": "IDENTITY_LINK_BROKEN",
                                     "field": key, "detail": "payload identity differs from record link"})
            for key in ("record_id", "payload_sha256", "stored_at", "status"):
                if not row[key]:
                    problems.append({"record_id": record_id, "code": "RECEIPT_INCOMPLETE",
                                     "field": key, "detail": "receipt field is empty"})
            if row["status"] != STATUS_COMMITTED:
                problems.append({"record_id": record_id, "code": "RECEIPT_INCOMPLETE",
                                 "field": "status",
                                 "detail": "formal record must be committed"})
            try:
                validate_result(payload, ctx, allow_fixture=True)
            except ValueError as exc:
                problems.append({"record_id": record_id, "code": "AMOUNT_RECONCILE_FAILED",
                                 "field": "amounts", "detail": str(exc)})
        diag_rows = self.conn.execute(
            "SELECT * FROM diagnostic_record ORDER BY id ASC").fetchall()
        for row in diag_rows:
            if row["result_status"] == STATUS_COMMITTED:
                problems.append({"record_id": "diagnostic#%d" % row["id"],
                                 "code": "DIAGNOSTIC_MISLABELED", "field": "result_status",
                                 "detail": "diagnostic record cannot claim committed"})
        return {"store_schema_version": STORE_SCHEMA_VERSION,
                "formal_records": len(rows), "diagnostic_records": len(diag_rows),
                "problems": problems,
                "verified_at": utc_now()}


def resolve_store_path(workdir: str, store_arg: str) -> str:
    """路径边界：库文件必须落在调用者指定的工作目录内，拒绝 .. 穿越与绝对路径越界。"""
    workdir_real = os.path.realpath(workdir)
    if os.path.isabs(store_arg):
        candidate = os.path.realpath(store_arg)
    else:
        candidate = os.path.realpath(os.path.join(workdir_real, store_arg))
    try:
        common = os.path.commonpath([workdir_real, candidate])
    except ValueError:
        raise StoreError("USAGE", "store path is outside the workdir", status="rejected")
    if common != workdir_real:
        raise StoreError("USAGE",
                         "store path escapes the workdir: %s" % os.path.basename(store_arg),
                         status="rejected")
    if not candidate.endswith(".sqlite3"):
        raise StoreError("USAGE", "store file must use .sqlite3 suffix", status="rejected")
    return candidate


def hold_exclusive_lock(path: str, seconds: int) -> None:
    """故障注入：由测试子进程持有写锁，用于验证锁超时明确返回而不是无限重试。"""
    conn = sqlite3.connect(path, timeout=1.0, isolation_level=None)
    conn.execute("PRAGMA busy_timeout = 1000")
    conn.execute("BEGIN EXCLUSIVE")
    conn.execute("INSERT OR IGNORE INTO schema_meta(key,value) VALUES('lock_probe','1')")
    time.sleep(seconds)
    conn.execute("COMMIT")
    conn.close()
