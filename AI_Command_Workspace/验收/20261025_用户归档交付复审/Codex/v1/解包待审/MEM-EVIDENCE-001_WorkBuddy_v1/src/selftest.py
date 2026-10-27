"""MEM-EVIDENCE-001 自测编排：在全新工作目录跑完整测试矩阵。

用法：python -m src.cli selftest --workdir <全新目录>
      python tests/run_tests.py --workdir <全新目录>

约束：
- 工作目录必须全新（不存在或为空目录），已存在且非空直接拒绝（退出码 2）。
- 独立预期来自 expected/ 冻结文件，运行只读不写；运行前后核验 expected/ 与 fixtures/ 的哈希。
- 故障注入只终止本包自己启动的子进程，不碰任何外部进程/服务器。
- 自测结论只针对本地 SQLite 测试库，不代表千问/生产 MySQL 行为。
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
FIXTURES = os.path.join(ROOT, "fixtures")
EXPECTED = os.path.join(ROOT, "expected")
OUTPUT = os.path.join(ROOT, "test-output")


def _cli(args, timeout: int = 90, env: dict = None):
    return subprocess.run([PY, "-m", "src.cli", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout,
                          env=env)


def _script(path, args, timeout: int = 90):
    return subprocess.run([PY, path, *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _json(proc):
    lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    if not lines:
        return {}
    try:
        return json.loads(lines[-1])
    except ValueError:
        return {"_stdout": proc.stdout[-500:]}


def sha256_file(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def snapshot_tree(base: str) -> dict:
    out = {}
    for root, _dirs, files in os.walk(base):
        for name in files:
            full = os.path.join(root, name)
            out[os.path.relpath(full, base).replace("\\", "/")] = sha256_file(full)
    return out


def count_rows(path: str, table: str) -> int:
    if not os.path.exists(path):
        return 0
    conn = sqlite3.connect(path, timeout=5.0)
    try:
        return conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
    except sqlite3.Error:
        return -1
    finally:
        conn.close()


def first_record_id(path: str) -> str:
    if not os.path.exists(path):
        return ""
    conn = sqlite3.connect(path, timeout=5.0)
    try:
        row = conn.execute("SELECT record_id FROM evidence_record ORDER BY id ASC LIMIT 1").fetchone()
        return row[0] if row else ""
    except sqlite3.Error:
        return ""
    finally:
        conn.close()


def stored_digest(path: str, record_id: str) -> str:
    conn = sqlite3.connect(path, timeout=5.0)
    try:
        row = conn.execute("SELECT payload_sha256 FROM evidence_record WHERE record_id=?",
                           (record_id,)).fetchone()
        return row[0] if row else ""
    finally:
        conn.close()


class Runner:
    def __init__(self, workdir: str, inject_failure: bool = False, dry: bool = False):
        self.workdir = workdir
        self.inject_failure = inject_failure
        self.dry = dry
        self.results = []
        self.case_dir = os.path.join(OUTPUT, "cases")
        if not dry:
            os.makedirs(self.case_dir, exist_ok=True)

    def db(self, name: str) -> str:
        return os.path.join(self.workdir, name + ".sqlite3")

    def fx(self, name: str) -> str:
        return os.path.join("fixtures", name)

    def add(self, tc, name, nature, inputs, expected_ref, expected_exit, actual_exit,
            facts, checks, cmd, note="", test_status=None):
        """checks: list of (描述, 期望值, 实际值)"""
        ok = all(exp == act for _d, exp, act in checks)
        if test_status is None:
            test_status = "通过" if (ok and expected_exit == actual_exit) else "失败"
        if self.inject_failure and tc == "TC-26":
            test_status = "失败" if ok else test_status
        record = {
            "case_id": tc, "name": name, "nature": nature, "inputs": inputs,
            "expected_ref": expected_ref, "expected_exit": expected_exit,
            "actual_exit": actual_exit, "status": test_status,
            "checks": [{"desc": d, "expected": e, "actual": a} for d, e, a in checks],
            "facts": facts, "command": cmd, "note": note,
        }
        self.results.append(record)
        return record

    def dump_case_raw(self, tc, text):
        if self.dry:
            return
        with open(os.path.join(self.case_dir, tc + ".out"), "w", encoding="utf-8") as handle:
            handle.write(text or "")


def run_selftest(workdir: str, pretty: bool = False, inject_failure: bool = False) -> int:
    """dry 模式（嵌套运行）只返回结果、不写 test-output，避免覆盖主运行的证据。"""
    dry = os.environ.get("MEM_EVIDENCE_SELFTEST_DRY") == "1"
    started = time.time()
    workdir_real = os.path.realpath(workdir)
    if os.path.exists(workdir_real):
        if not os.path.isdir(workdir_real) or os.listdir(workdir_real):
            print(json.dumps({"ok": False, "code": "USAGE", "status": "rejected",
                               "message": "workdir already exists and is not empty: %s" % workdir,
                               "details": {}}, ensure_ascii=False))
            return 2
    else:
        try:
            os.makedirs(workdir_real)
        except OSError as exc:
            print(json.dumps({"ok": False, "code": "USAGE", "status": "rejected",
                              "message": "cannot create workdir: %s" % exc}, ensure_ascii=False))
            return 2

    os.makedirs(OUTPUT, exist_ok=True)
    before_expected = snapshot_tree(EXPECTED)
    before_fixtures = snapshot_tree(FIXTURES)
    with open(os.path.join(EXPECTED, "expected_values.json"), "r", encoding="utf-8") as handle:
        exp = json.load(handle)

    runner = Runner(workdir_real, inject_failure=inject_failure, dry=dry)
    R = runner.add
    db = runner.db
    fx = runner.fx
    ctx = fx("trusted_context.json")
    ctx_other = fx("trusted_context_other.json")
    ctx_rev2 = fx("trusted_context_rev2.json")
    ctx_sql = fx("trusted_context_sql_special.json")

    def cmd_str(*args):
        return "python -m src.cli " + " ".join(args)

    # ---------------- TC-01 正常提交 + 重启读回 ----------------
    store1 = db("tc01")
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                 "--context", ctx, "--request-id", "req-main-001",
                 "--store", "tc01.sqlite3", "--allow-fixture"])
    out = _json(proc)
    runner.dump_case_raw("TC-01", proc.stdout + proc.stderr)
    rid1 = (out.get("receipt") or {}).get("record_id", "")
    proc_get = _cli(["get", "--workdir", workdir_real, "--context", ctx, "--record-id", rid1,
                     "--store", "tc01.sqlite3", "--include-payload"])
    out_get = _json(proc_get)
    runner.dump_case_raw("TC-01b", proc_get.stdout + proc_get.stderr)
    R("TC-01", "正常提交后新进程重启读回", "正例", "fixtures/synthetic_success.json + 可信上下文",
      "expected/expected_values.json#TC-01", 0, proc.returncode,
      {"outcome": out.get("outcome"), "record_id": rid1,
       "readback_closing": ((out_get.get("payload") or {}).get("amounts") or {}).get("closing")},
      [("退出码", 0, proc.returncode),
       ("outcome", "created", out.get("outcome")),
       ("回执状态", "committed", (out.get("receipt") or {}).get("status")),
       ("摘要一致", exp["digests"]["synthetic_success.json"],
        (out.get("receipt") or {}).get("payload_sha256")),
       ("record_id", exp["record_ids"]["req-main-001"], rid1),
       ("新进程读回退出码", 0, proc_get.returncode),
       ("重启读回 record_id 相同", rid1, out_get.get("record_id")),
       ("精度保留 140000.00", "140000.00",
        ((out_get.get("payload") or {}).get("amounts") or {}).get("closing"))],
      cmd_str("save ... --allow-fixture") + " && " + cmd_str("get ..."),
      "提交与读回分别在不同进程，证明跨进程持久化")

    # ---------------- TC-02 幂等回放 ----------------
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                 "--context", ctx, "--request-id", "req-main-001",
                 "--store", "tc01.sqlite3", "--allow-fixture"])
    out = _json(proc)
    runner.dump_case_raw("TC-02", proc.stdout + proc.stderr)
    R("TC-02", "同键同摘要回放返回原 record_id", "正例", "同一 request-id + 同一 payload",
      "expected/expected_values.json#TC-02", 0, proc.returncode,
      {"outcome": out.get("outcome"), "record_id": (out.get("receipt") or {}).get("record_id"),
       "rows": count_rows(db("tc01"), "evidence_record")},
      [("退出码", 0, proc.returncode),
       ("outcome", "replay", out.get("outcome")),
       ("record_id 不变", rid1, (out.get("receipt") or {}).get("record_id")),
       ("业务记录数", 1, count_rows(db("tc01"), "evidence_record"))],
      cmd_str("save --request-id req-main-001"),
      "幂等不新增记录；断言内容与身份而非仅计数")

    # ---------------- TC-03 同键异摘要冲突 ----------------
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success_variant.json"),
                 "--context", ctx, "--request-id", "req-main-001",
                 "--store", "tc01.sqlite3", "--allow-fixture"])
    out = _json(proc)
    runner.dump_case_raw("TC-03", proc.stdout + proc.stderr)
    R("TC-03", "同键不同 payload 冲突且不覆盖", "负例", "fixtures/synthetic_success_variant.json",
      "expected/expected_values.json#TC-03", 4, proc.returncode,
      {"code": out.get("code"), "rows": count_rows(db("tc01"), "evidence_record"),
       "stored_digest": stored_digest(db("tc01"), rid1)},
      [("退出码", 4, proc.returncode),
       ("错误码", "CONFLICT", out.get("code")),
       ("业务记录数仍为 1", 1, count_rows(db("tc01"), "evidence_record")),
       ("原记录摘要未被覆盖", exp["digests"]["synthetic_success.json"],
        stored_digest(db("tc01"), rid1))],
      cmd_str("save --request-id req-main-001（payload 已变）"))

    # ---------------- TC-04 全 0 金额 ----------------
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success_zero.json"),
                 "--context", ctx, "--request-id", "req-zero-001",
                 "--store", "tc04.sqlite3", "--allow-fixture"])
    out = _json(proc)
    runner.dump_case_raw("TC-04", proc.stdout + proc.stderr)
    rid0 = (out.get("receipt") or {}).get("record_id", "")
    proc_get = _cli(["get", "--workdir", workdir_real, "--context", ctx, "--record-id", rid0,
                     "--store", "tc04.sqlite3", "--include-payload"])
    out_get = _json(proc_get)
    R("TC-04", "全 0 金额（真实 0 不等于缺项）", "正例", "fixtures/synthetic_success_zero.json",
      "expected/expected_values.json#TC-04", 0, proc.returncode,
      {"outcome": out.get("outcome"),
       "opening": ((out_get.get("payload") or {}).get("amounts") or {}).get("opening")},
      [("退出码", 0, proc.returncode),
       ("outcome", "created", out.get("outcome")),
       ("opening 保留 0.00", "0.00",
        ((out_get.get("payload") or {}).get("amounts") or {}).get("opening")),
       ("勾稽状态", "completed", (out.get("receipt") or {}).get("reconciliation_state"))],
      cmd_str("save --input synthetic_success_zero.json"))

    # ---------------- TC-05 缺独立实际余额 ----------------
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success_no_actual.json"),
                 "--context", ctx, "--request-id", "req-noactual-001",
                 "--store", "tc05.sqlite3", "--allow-fixture"])
    out = _json(proc)
    runner.dump_case_raw("TC-05", proc.stdout + proc.stderr)
    rid_na = (out.get("receipt") or {}).get("record_id", "")
    proc_get = _cli(["get", "--workdir", workdir_real, "--context", ctx, "--record-id", rid_na,
                     "--store", "tc05.sqlite3", "--include-payload"])
    out_get = _json(proc_get)
    amounts_na = (out_get.get("payload") or {}).get("amounts") or {}
    R("TC-05", "缺实际余额可保存但勾稽未完成", "正例（业务未核对）", "fixtures/synthetic_success_no_actual.json",
      "expected/expected_values.json#TC-05", 0, proc.returncode,
      {"reconciliation_state": (out.get("receipt") or {}).get("reconciliation_state"),
       "difference": amounts_na.get("difference")},
      [("退出码", 0, proc.returncode),
       ("勾稽状态", "not_performed", (out.get("receipt") or {}).get("reconciliation_state")),
       ("difference 为 null", None, amounts_na.get("difference")),
       ("actual_closing 为 null", None, amounts_na.get("actual_closing")),
       ("提示未完成勾稽", True, bool(out.get("reconciliation_note")))],
      cmd_str("save --input synthetic_success_no_actual.json"),
      "缺项不得伪造差异 0")

    # ---------------- TC-06 差异一分 ----------------
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success_diff_cent.json"),
                 "--context", ctx, "--request-id", "req-diffcent-001",
                 "--store", "tc06.sqlite3", "--allow-fixture"])
    out = _json(proc)
    rid_dc = (out.get("receipt") or {}).get("record_id", "")
    proc_get = _cli(["get", "--workdir", workdir_real, "--context", ctx, "--record-id", rid_dc,
                     "--store", "tc06.sqlite3", "--include-payload"])
    out_get = _json(proc_get)
    amounts_dc = (out_get.get("payload") or {}).get("amounts") or {}
    R("TC-06", "差异一分保存并标记待核", "正例（差异待核）", "fixtures/synthetic_success_diff_cent.json",
      "expected/expected_values.json#TC-06", 0, proc.returncode,
      {"reconciliation_state": (out.get("receipt") or {}).get("reconciliation_state"),
       "difference": amounts_dc.get("difference")},
      [("退出码", 0, proc.returncode),
       ("勾稽状态", "difference_pending_review",
        (out.get("receipt") or {}).get("reconciliation_state")),
       ("difference 精确到分", "0.01", amounts_dc.get("difference"))],
      cmd_str("save --input synthetic_success_diff_cent.json"))

    # ---------------- TC-07 非法金额 / 非有限值 / 勾稽错误 ----------------
    proc_a = _cli(["save", "--workdir", workdir_real, "--input", fx("result_bad_amount.json"),
                   "--context", ctx, "--request-id", "req-bad-001",
                   "--store", "tc07.sqlite3", "--allow-fixture"])
    out_a = _json(proc_a)
    proc_b = _cli(["save", "--workdir", workdir_real, "--input", fx("result_nonfinite.json"),
                   "--context", ctx, "--request-id", "req-nan-001",
                   "--store", "tc07.sqlite3", "--allow-fixture"])
    out_b = _json(proc_b)
    proc_c = _cli(["save", "--workdir", workdir_real, "--input", fx("result_recon_mismatch.json"),
                   "--context", ctx, "--request-id", "req-recon-001",
                   "--store", "tc07.sqlite3", "--allow-fixture"])
    out_c = _json(proc_c)
    runner.dump_case_raw("TC-07", "\n".join([proc_a.stdout, proc_a.stderr, proc_b.stdout,
                                             proc_b.stderr, proc_c.stdout, proc_c.stderr]))
    R("TC-07", "非法金额/非有限值/勾稽错误全部拒绝", "负例",
      "result_bad_amount.json、result_nonfinite.json、result_recon_mismatch.json",
      "expected/expected_values.json#TC-07", 3, proc_a.returncode,
      {"bad_code": out_a.get("code"), "nan_code": out_b.get("code"), "recon_code": out_c.get("code")},
      [("非法金额退出码", 3, proc_a.returncode),
       ("非法金额错误码", "VALIDATION_FAILED", out_a.get("code")),
       ("非有限值退出码", 3, proc_b.returncode),
       ("勾稽错误退出码", 3, proc_c.returncode),
       ("未写入任何记录", 0, count_rows(db("tc07"), "evidence_record"))],
      cmd_str("save --input result_bad_amount.json / result_nonfinite.json / result_recon_mismatch.json"))

    # ---------------- TC-08 缺必填字段 ----------------
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("result_missing_field.json"),
                 "--context", ctx, "--request-id", "req-miss-001",
                 "--store", "tc08.sqlite3", "--allow-fixture"])
    out = _json(proc)
    runner.dump_case_raw("TC-08", proc.stdout + proc.stderr)
    expect_exit = 0 if runner.inject_failure else 3
    R("TC-08", "缺必填字段拒绝保存", "负例", "fixtures/result_missing_field.json",
      "expected/expected_values.json#TC-08", expect_exit, proc.returncode,
      {"code": out.get("code")},
      [("退出码", 3, proc.returncode),
       ("错误码", "VALIDATION_FAILED", out.get("code")),
       ("未写入记录", 0, count_rows(db("tc08"), "evidence_record"))],
      cmd_str("save --input result_missing_field.json"),
      "（故意断言失败开关命中时，本用例的预期被临时改为 0 以验证非 0 退出真实触发）"
      if runner.inject_failure else "")

    # ---------------- TC-09 身份不匹配 ----------------
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("result_identity_mismatch.json"),
                 "--context", ctx, "--request-id", "req-ident-001",
                 "--store", "tc09.sqlite3", "--allow-fixture"])
    out = _json(proc)
    R("TC-09", "payload 身份与可信上下文不一致拒绝", "负例", "fixtures/result_identity_mismatch.json",
      "expected/expected_values.json#TC-09", 3, proc.returncode,
      {"code": out.get("code")},
      [("退出码", 3, proc.returncode), ("错误码", "VALIDATION_FAILED", out.get("code")),
       ("未写入记录", 0, count_rows(db("tc09"), "evidence_record"))],
      cmd_str("save --input result_identity_mismatch.json"))

    # ---------------- TC-10 源版本错 ----------------
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("result_rev_mismatch.json"),
                 "--context", ctx, "--request-id", "req-rev-001",
                 "--store", "tc10.sqlite3", "--allow-fixture"])
    out = _json(proc)
    R("TC-10", "源版本与上下文不一致拒绝（不误复用旧快照）", "负例", "fixtures/result_rev_mismatch.json",
      "expected/expected_values.json#TC-10", 3, proc.returncode,
      {"code": out.get("code")},
      [("退出码", 3, proc.returncode), ("错误码", "VALIDATION_FAILED", out.get("code"))],
      cmd_str("save --input result_rev_mismatch.json"))

    # ---------------- TC-11 非 success 拒绝正式保存 / 诊断通道 ----------------
    proc_a = _cli(["save", "--workdir", workdir_real, "--input", fx("result_non_success.json"),
                   "--context", ctx, "--request-id", "req-diag-001",
                   "--store", "tc11.sqlite3", "--allow-fixture"])
    out_a = _json(proc_a)
    proc_b = _cli(["save", "--workdir", workdir_real, "--input", fx("result_non_success.json"),
                   "--context", ctx, "--request-id", "req-diag-001",
                   "--store", "tc11.sqlite3", "--allow-fixture", "--save-diagnostic"])
    out_b = _json(proc_b)
    runner.dump_case_raw("TC-11", "\n".join([proc_a.stdout, proc_b.stdout]))
    R("TC-11", "非 success 不产生正式回执，仅可存诊断", "负例+诊断",
      "fixtures/result_non_success.json", "expected/expected_values.json#TC-11",
      3, proc_a.returncode,
      {"formal_rows": count_rows(db("tc11"), "evidence_record"),
       "diag_rows": count_rows(db("tc11"), "diagnostic_record"),
       "diag_receipt": out_b.get("receipt")},
      [("正式保存退出码", 3, proc_a.returncode),
       ("正式保存错误码", "VALIDATION_FAILED", out_a.get("code")),
       ("诊断通道退出码", 0, proc_b.returncode),
       ("正式记录数", 0, count_rows(db("tc11"), "evidence_record")),
       ("诊断记录数", 1, count_rows(db("tc11"), "diagnostic_record")),
       ("诊断不返回回执", None, out_b.get("receipt"))],
      cmd_str("save --save-diagnostic"),
      "业务状态 BLOCKED 与测试状态分开：本用例测试状态为通过")

    # ---------------- TC-12 默认拒 fixture / 显式允许 ----------------
    proc_a = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                   "--context", ctx, "--request-id", "req-fix-001", "--store", "tc12.sqlite3"])
    out_a = _json(proc_a)
    proc_b = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                   "--context", ctx, "--request-id", "req-fix-001",
                   "--store", "tc12.sqlite3", "--allow-fixture"])
    out_b = _json(proc_b)
    runner.dump_case_raw("TC-12", "\n".join([proc_a.stdout, proc_b.stdout]))
    R("TC-12", "默认拒绝 offline_fixture，显式允许产生醒目标识", "负例+正例",
      "fixtures/synthetic_success.json（origin=offline_fixture）",
      "expected/expected_values.json#TC-12", 3, proc_a.returncode,
      {"default_code": out_a.get("code"), "fixture_warning": out_b.get("fixture_warning", "")[:20],
       "is_fixture": (out_b.get("receipt") or {}).get("is_fixture")},
      [("默认退出码", 3, proc_a.returncode),
       ("默认错误码", "VALIDATION_FAILED", out_a.get("code")),
       ("显式允许退出码", 0, proc_b.returncode),
       ("回执标记 is_fixture", True, (out_b.get("receipt") or {}).get("is_fixture")),
       ("输出含醒目标识", True, "【合成数据" in out_b.get("fixture_warning", ""))],
      cmd_str("save（无 --allow-fixture） vs save --allow-fixture"))

    # ---------------- TC-13 提交前故障不留半条 ----------------
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                 "--context", ctx, "--request-id", "req-fault-001",
                 "--store", "tc13.sqlite3", "--allow-fixture", "--fault-before-commit"])
    runner.dump_case_raw("TC-13", proc.stdout + proc.stderr)
    rows_after_crash = count_rows(db("tc13"), "evidence_record")
    proc_ok = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                    "--context", ctx, "--request-id", "req-fault-001",
                    "--store", "tc13.sqlite3", "--allow-fixture"])
    out_ok = _json(proc_ok)
    R("TC-13", "COMMIT 前进程终止：不留半条记录", "故障注入",
      "子进程 --fault-before-commit", "expected/expected_values.json#TC-13", 9, proc.returncode,
      {"child_exit": proc.returncode, "rows_after_crash": rows_after_crash,
       "rows_after_retry": count_rows(db("tc13"), "evidence_record")},
      [("故障子进程退出码", 9, proc.returncode),
       ("崩溃后无部分记录", 0, rows_after_crash),
       ("重试后记录数", 1, count_rows(db("tc13"), "evidence_record")),
       ("重试返回 committed", "committed", (out_ok.get("receipt") or {}).get("status"))],
      cmd_str("save --fault-before-commit"),
      "仅终止本包自己启动的子进程，不停止任何外部进程")

    # ---------------- TC-14 提交后回执丢失，先回查再重试 ----------------
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                 "--context", ctx, "--request-id", "req-after-001",
                 "--store", "tc14.sqlite3", "--allow-fixture", "--fault-after-commit"])
    runner.dump_case_raw("TC-14", proc.stdout + proc.stderr)
    rows_after = count_rows(db("tc14"), "evidence_record")
    rid_after = first_record_id(db("tc14"))
    proc_retry = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                       "--context", ctx, "--request-id", "req-after-001",
                       "--store", "tc14.sqlite3", "--allow-fixture"])
    out_retry = _json(proc_retry)
    R("TC-14", "COMMIT 后回执丢失：回查命中原记录，重试返回同一 record_id", "故障注入+恢复",
      "子进程 --fault-after-commit 后同 ID 重试",
      "expected/expected_values.json#TC-14", 9, proc.returncode,
      {"child_exit": proc.returncode, "committed_rows_before_retry": rows_after,
       "retry_record_id": (out_retry.get("receipt") or {}).get("record_id"),
       "rows_after_retry": count_rows(db("tc14"), "evidence_record")},
      [("故障子进程退出码", 9, proc.returncode),
       ("崩溃前已落库记录数", 1, rows_after),
       ("重试退出码", 0, proc_retry.returncode),
       ("重试返回原 record_id", rid_after, (out_retry.get("receipt") or {}).get("record_id")),
       ("重试未新增记录", 1, count_rows(db("tc14"), "evidence_record"))],
      cmd_str("save --fault-after-commit 后同 request-id 再 save"),
      "核心故障恢复证据：原 record_id + 摘要 + 主体边界一致")

    # ---------------- TC-15 受控并发竞争 ----------------
    procs = []
    for _ in range(6):
        procs.append(subprocess.Popen(
            [PY, "-m", "src.cli", "save", "--workdir", workdir_real,
             "--input", fx("synthetic_success.json"), "--context", ctx,
             "--request-id", "req-race-001", "--store", "tc15.sqlite3", "--allow-fixture"],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace"))
    outs = []
    for p in procs:
        stdout, _ = p.communicate(timeout=120)
        try:
            outs.append(json.loads([ln for ln in stdout.splitlines() if ln.strip()][-1]))
        except (ValueError, IndexError):
            outs.append({})
    exit_codes = [p.returncode for p in procs]
    rids = sorted({(o.get("receipt") or {}).get("record_id", "") for o in outs})
    runner.dump_case_raw("TC-15", json.dumps({"exit_codes": exit_codes, "record_ids": rids},
                                             ensure_ascii=False, indent=2))
    R("TC-15", "6 个受控子进程竞争同一幂等键", "并发负例",
      "6×子进程同 request-id 同 payload", "expected/expected_values.json#TC-15", 0,
      exit_codes[0],
      {"exit_codes": exit_codes, "distinct_record_ids": rids,
       "rows": count_rows(db("tc15"), "evidence_record")},
      [("全部子进程退出码为 0", [0] * 6, exit_codes),
       ("唯一业务记录", 1, count_rows(db("tc15"), "evidence_record")),
       ("record_id 唯一", 1, len(rids)),
       ("record_id 与预期一致", exp["record_ids"]["req-race-001"], rids[0] if rids else "")],
      cmd_str("save --request-id req-race-001 ×6 并发"),
      "仅本机受控测试库，不代表允许多方并行施工")

    # ---------------- TC-16 SQLite 锁超时明确返回 ----------------
    lock_db = db("tc16")
    _cli(["lock-hold", "--workdir", workdir_real, "--store", "tc16.sqlite3", "--seconds", "0"])
    holder = subprocess.Popen([PY, "-m", "src.cli", "lock-hold", "--workdir", workdir_real,
                               "--store", "tc16.sqlite3", "--seconds", "8"],
                              cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8")
    time.sleep(1.0)
    t0 = time.time()
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                 "--context", ctx, "--request-id", "req-lock-001",
                 "--store", "tc16.sqlite3", "--allow-fixture"], timeout=60)
    elapsed = time.time() - t0
    out = _json(proc)
    holder.communicate(timeout=60)
    runner.dump_case_raw("TC-16", proc.stdout + proc.stderr)
    R("TC-16", "写锁被占用时明确返回锁超时，不无限重试", "故障注入",
      "子进程 lock-hold 8s + 主进程 save", "expected/expected_values.json#TC-16", 7,
      proc.returncode,
      {"code": out.get("code"), "elapsed_sec": round(elapsed, 2),
       "rows": count_rows(lock_db, "evidence_record")},
      [("退出码", 7, proc.returncode),
       ("错误码", "STORAGE_BUSY", out.get("code")),
       ("等待时间小于 15 秒", True, elapsed < 15),
       ("锁期间未写入", 0, count_rows(lock_db, "evidence_record"))],
      cmd_str("lock-hold --seconds 8 与 save 并行"),
      "锁等待上限由 busy_timeout=3000ms 控制，不做重试循环")

    # ---------------- TC-17 历史只追加与当前版本选择 ----------------
    _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
          "--context", ctx, "--request-id", "req-rev1-001",
          "--store", "tc17.sqlite3", "--allow-fixture"])
    proc2 = _cli(["save", "--workdir", workdir_real, "--input", fx("result_source_rev2.json"),
                  "--context", ctx_rev2, "--request-id", "req-rev2-001",
                  "--store", "tc17.sqlite3", "--allow-fixture"])
    out2 = _json(proc2)
    proc_hist = _cli(["history", "--workdir", workdir_real, "--context", ctx, "--period", "2026-08",
                      "--store", "tc17.sqlite3"])
    hist = _json(proc_hist)
    proc_hist_rev1 = _cli(["history", "--workdir", workdir_real, "--context", ctx, "--period", "2026-08",
                           "--source-revision", "fixture-rev-1", "--store", "tc17.sqlite3"])
    hist_rev1 = _json(proc_hist_rev1)
    runner.dump_case_raw("TC-17", proc_hist.stdout)
    rid_rev2 = (out2.get("receipt") or {}).get("record_id", "")
    R("TC-17", "历史只追加、旧版不覆盖、当前版本选择可解释", "正例",
      "rev1 与 rev2 两条同期间不同源版本", "expected/expected_values.json#TC-17", 0,
      proc_hist.returncode,
      {"count": hist.get("count"), "current": hist.get("current_record_id"),
       "revisions": hist.get("distinct_source_revisions"),
       "rev1_only_count": hist_rev1.get("count")},
      [("退出码", 0, proc_hist.returncode),
       ("历史条数", 2, hist.get("count")),
       ("当前有效为 rev2 记录", rid_rev2, hist.get("current_record_id")),
       ("存在两个源版本", ["fixture-rev-1", "fixture-rev-2"], hist.get("distinct_source_revisions")),
       ("按 rev1 过滤只剩 1 条", 1, hist_rev1.get("count")),
       ("给出选择规则说明", True, bool(hist.get("current_selection_rule")))],
      cmd_str("history --period 2026-08 / --source-revision fixture-rev-1"),
      "旧版本记录保留且未被静默改写")

    # ---------------- TC-18 跨身份隔离 ----------------
    proc_a = _cli(["get", "--workdir", workdir_real, "--context", ctx_other, "--record-id", rid1,
                   "--store", "tc01.sqlite3"])
    out_a = _json(proc_a)
    proc_b = _cli(["history", "--workdir", workdir_real, "--context", ctx_other,
                   "--period", "2026-08", "--store", "tc01.sqlite3"])
    out_b = _json(proc_b)
    proc_c = _cli(["get", "--workdir", workdir_real, "--context", ctx, "--record-id", rid1,
                   "--store", "tc01.sqlite3", "--tenant-id", "other-tenant"])
    out_c = _json(proc_c)
    runner.dump_case_raw("TC-18", "\n".join([proc_a.stdout, proc_b.stdout, proc_c.stdout]))
    R("TC-18", "跨租户/跨企业读取被拒且不泄露内容", "负例",
      "固定独立可信上下文 trusted_context_other.json", "expected/expected_values.json#TC-18",
      6, proc_a.returncode,
      {"get_code": out_a.get("code"), "other_history_count": out_b.get("count"),
       "selffill_code": out_c.get("code")},
      [("他身份 get 退出码", 6, proc_a.returncode),
       ("他身份 get 错误码", "SCOPE_DENIED", out_a.get("code")),
       ("他身份 history 条数", 0, out_b.get("count")),
       ("自填身份与上下文不符退出码", 6, proc_c.returncode),
       ("响应不含 payload", False, "payload" in out_a)],
      cmd_str("get --context trusted_context_other.json"))

    # ---------------- TC-19 verify-store 正常 + 库重开复核 ----------------
    proc_v1 = _cli(["verify-store", "--workdir", workdir_real, "--store", "tc01.sqlite3"])
    out_v1 = _json(proc_v1)
    proc_v2 = _cli(["verify-store", "--workdir", workdir_real, "--store", "tc01.sqlite3"])
    out_v2 = _json(proc_v2)
    runner.dump_case_raw("TC-19", proc_v1.stdout + proc_v2.stdout)
    R("TC-19", "verify-store 通过，且关闭库后重开结果一致", "正例", "tc01.sqlite3（含 1 条记录）",
      "expected/expected_values.json#TC-19", 0, proc_v1.returncode,
      {"problems": len(out_v1.get("report", {}).get("problems", [])),
       "formal_records": out_v1.get("report", {}).get("formal_records")},
      [("首次退出码", 0, proc_v1.returncode),
       ("问题数", 0, len(out_v1.get("report", {}).get("problems", []))),
       ("重开后退出码", 0, proc_v2.returncode),
       ("记录数一致", out_v1.get("report", {}).get("formal_records"),
        out_v2.get("report", {}).get("formal_records"))],
      cmd_str("verify-store --store tc01.sqlite3（两次独立进程）"))

    # ---------------- TC-20/21/22 三类篡改检测 ----------------
    tamper_cases = [
        ("TC-20", "payload", "tc20.sqlite3", "PAYLOAD_HASH_MISMATCH", "篡改 payload 业务值"),
        ("TC-21", "digest", "tc21.sqlite3", "PAYLOAD_HASH_MISMATCH", "篡改 payload_sha256"),
        ("TC-22", "identity", "tc22.sqlite3", "IDENTITY_LINK_BROKEN", "篡改关联身份字段"),
    ]
    for tc, mode, dbname, want_code, desc in tamper_cases:
        store_path = os.path.join(workdir_real, dbname)
        proc_save = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                          "--context", ctx, "--request-id", "req-tamper-001", "--store", dbname,
                          "--allow-fixture"])
        proc_t = _script(os.path.join("tests", "tamper_db.py"),
                         ["--store", store_path, "--mode", mode])
        proc_v = _cli(["verify-store", "--workdir", workdir_real, "--store", dbname])
        out_v = _json(proc_v)
        codes = [p.get("code") for p in (out_v.get("report", {}).get("problems") or [])]
        runner.dump_case_raw(tc, "\n".join([proc_save.stdout, proc_t.stdout, proc_t.stderr,
                                            proc_v.stdout]))
        R(tc, "篡改检测：" + desc, "负例", "tests/tamper_db.py --mode %s" % mode,
          "expected/expected_values.json#" + tc, 8, proc_v.returncode,
          {"tamper_exit": proc_t.returncode, "codes": codes},
          [("保存退出码", 0, proc_save.returncode),
           ("篡改脚本执行成功", 0, proc_t.returncode),
           ("退出码", 8, proc_v.returncode),
           ("错误码", "VERIFY_FAILED", out_v.get("code")),
           ("检出问题码含 %s" % want_code, True, want_code in codes)],
          cmd_str("verify-store --store %s（已篡改）" % dbname),
          "篡改需先移除 append-only 触发器，模拟具备库文件写权限者")

    # ---------------- TC-23 路径越界与重名拒绝 ----------------
    outside = os.path.join(os.path.dirname(workdir_real), "outside-evidence.sqlite3")
    proc_a = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                   "--context", ctx, "--request-id", "req-path-001",
                   "--store", "../outside-evidence.sqlite3", "--allow-fixture"])
    out_a = _json(proc_a)
    proc_b = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                   "--context", ctx, "--request-id", "req-path-002",
                   "--store", outside, "--allow-fixture"])
    out_b = _json(proc_b)
    proc_c = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                   "--context", ctx, "--request-id", "req-path-003",
                   "--store", "tc23.txt", "--allow-fixture"])
    out_c = _json(proc_c)
    proc_d = _cli(["selftest", "--workdir", workdir_real])
    runner.dump_case_raw("TC-23", "\n".join([proc_a.stdout, proc_b.stdout, proc_c.stdout,
                                             proc_d.stdout]))
    R("TC-23", "路径穿越/绝对路径越界/非法后缀/非空工作目录全部拒绝", "负例",
      "../outside-evidence.sqlite3、绝对路径、tc23.txt、非空 workdir",
      "expected/expected_values.json#TC-23", 2, proc_a.returncode,
      {"rel_code": out_a.get("code"), "abs_code": out_b.get("code"),
       "suffix_code": out_c.get("code"), "nonempty_workdir_exit": proc_d.returncode},
      [("相对穿越退出码", 2, proc_a.returncode),
       ("相对穿越错误码", "USAGE", out_a.get("code")),
       ("绝对路径越界退出码", 2, proc_b.returncode),
       ("非法后缀退出码", 2, proc_c.returncode),
       ("非空 workdir 退出码", 2, proc_d.returncode)],
      cmd_str("save --store ../outside-evidence.sqlite3"))

    # ---------------- TC-24 SQL 特殊字符身份 ----------------
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("result_sql_special.json"),
                 "--context", ctx_sql, "--request-id", "req-sql-001",
                 "--store", "tc24.sqlite3", "--allow-fixture"])
    out = _json(proc)
    rid_sql = (out.get("receipt") or {}).get("record_id", "")
    proc_get = _cli(["get", "--workdir", workdir_real, "--context", ctx_sql, "--record-id", rid_sql,
                     "--store", "tc24.sqlite3", "--include-payload"])
    proc_v = _cli(["verify-store", "--workdir", workdir_real, "--store", "tc24.sqlite3"])
    runner.dump_case_raw("TC-24", "\n".join([proc.stdout, proc_get.stdout, proc_v.stdout]))
    R("TC-24", "身份含 SQL 特殊字符仍安全存取（全参数化）", "正例",
      "trusted_context_sql_special.json", "expected/expected_values.json#TC-24", 0,
      proc.returncode,
      {"record_id": rid_sql, "get_exit": proc_get.returncode,
       "verify_exit": proc_v.returncode},
      [("保存退出码", 0, proc.returncode),
       ("读回退出码", 0, proc_get.returncode),
       ("表结构完好可复核", 0, proc_v.returncode),
       ("record_id 与预期一致", exp["record_ids"]["req-sql-001"], rid_sql)],
      cmd_str("save --context trusted_context_sql_special.json"))

    # ---------------- TC-25 提交后状态未确定 ----------------
    proc = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                 "--context", ctx, "--request-id", "req-unknown-001",
                 "--store", "tc25.sqlite3", "--allow-fixture", "--simulate-unknown"])
    out = _json(proc)
    rows_unknown = count_rows(db("tc25"), "evidence_record")
    proc_retry = _cli(["save", "--workdir", workdir_real, "--input", fx("synthetic_success.json"),
                       "--context", ctx, "--request-id", "req-unknown-001",
                       "--store", "tc25.sqlite3", "--allow-fixture"])
    out_retry = _json(proc_retry)
    runner.dump_case_raw("TC-25", proc.stdout + proc_retry.stdout)
    R("TC-25", "提交后回执未确定：返回未确定态且不报成功", "故障注入",
      "--simulate-unknown", "expected/expected_values.json#TC-25", 11, proc.returncode,
      {"code": out.get("code"), "rows": rows_unknown,
       "retry_record_id": (out_retry.get("receipt") or {}).get("record_id")},
      [("退出码", 11, proc.returncode),
       ("错误码", "UNKNOWN_STATE", out.get("code")),
       ("未报成功", False, bool(out.get("ok"))),
       ("库中已有该提交", 1, rows_unknown),
       ("同 ID 重试返回同一 record_id", exp["record_ids"]["req-unknown-001"],
        (out_retry.get("receipt") or {}).get("record_id")),
       ("重试后仍仅 1 条", 1, count_rows(db("tc25"), "evidence_record"))],
      cmd_str("save --simulate-unknown"))

    # ---------------- TC-26 故意断言失败必须非 0 ----------------
    if runner.inject_failure:
        # 嵌套注入运行内部不再递归：直接断言本运行已因注入产生失败用例。
        failures_now = [r["case_id"] for r in runner.results if r["status"] == "失败"]
        R("TC-26", "注入模式：本运行存在失败用例，退出码非 0", "元测试",
          "--inject-failure 开关", "expected/expected_values.json#TC-26", 10, 10,
          {"failed_cases": failures_now},
          [("存在失败用例", True, bool(failures_now)),
           ("注入命中 TC-08", True, "TC-08" in failures_now)],
          cmd_str("selftest --inject-failure（嵌套运行）"),
          "嵌套运行以 dry 模式执行，不覆盖主运行的 test-output")
    else:
        subdir = os.path.join(workdir_real, "inject-check")
        os.makedirs(subdir, exist_ok=True)
        env = dict(os.environ)
        env["MEM_EVIDENCE_SELFTEST_DRY"] = "1"
        proc = _cli(["selftest", "--workdir", subdir, "--inject-failure"], timeout=300,
                    env=env)
        out = _json(proc)
        R("TC-26", "故意断言失败的自测必须非 0 退出", "元测试",
          "嵌套 selftest --inject-failure", "expected/expected_values.json#TC-26",
          10, proc.returncode,
          {"exit": proc.returncode, "inner_failed": (out.get("summary") or {}).get("failed"),
           "inner_code": out.get("code")},
          [("退出码", 10, proc.returncode),
           ("返回码", "SELFTEST_FAILED", out.get("code")),
           ("内部失败数大于 0", True, ((out.get("summary") or {}).get("failed") or 0) > 0)],
          cmd_str("selftest --workdir <空目录> --inject-failure"),
          "验证失败退出码能真实触发，不是 catch 后仍报 PASS")

    # ---------------- TC-27 静态边界检查 ----------------
    proc = _script(os.path.join("tests", "static_boundary_check.py"), [])
    out = _json(proc)
    runner.dump_case_raw("TC-27", proc.stdout)
    R("TC-27", "源码静态边界检查：无外连/无删除逻辑/无凭据读取", "静态检查",
      "src/*.py, tests/*.py", "expected/expected_values.json#TC-27", 0, proc.returncode,
      {"scanned": out.get("scanned_files"), "findings": len(out.get("findings", []))},
      [("退出码", 0, proc.returncode),
       ("无违规发现", 0, len(out.get("findings", []))),
       ("扫描文件数大于 0", True, (out.get("scanned_files") or 0) > 0)],
      "python tests/static_boundary_check.py")

    # ---------------- TC-28 独立预期与夹具运行前后哈希一致 ----------------
    after_expected = snapshot_tree(EXPECTED)
    after_fixtures = snapshot_tree(FIXTURES)
    R("TC-28", "运行前后独立预期与夹具哈希未被改写", "元测试",
      "expected/ 与 fixtures/ 全量文件", "expected/expected_values.json#TC-28", 0, 0,
      {"expected_files": len(after_expected), "fixture_files": len(after_fixtures)},
      [("expected 哈希一致", True, before_expected == after_expected),
       ("fixtures 哈希一致", True, before_fixtures == after_fixtures),
       ("expected 文件数大于 0", True, len(after_expected) > 0)],
      "（selftest 内部自动核验）",
      "独立预期来自冻结文件，运行不重写")

    # ---------------- 汇总 ----------------
    passed = sum(1 for r in runner.results if r["status"] == "通过")
    failed = sum(1 for r in runner.results if r["status"] == "失败")
    blocked = sum(1 for r in runner.results if r["status"] == "阻塞")
    notrun = sum(1 for r in runner.results if r["status"] == "未执行")
    total = len(runner.results)
    duration = round(time.time() - started, 2)

    summary = {
        "task_id": "MEM-EVIDENCE-001",
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "python": sys.version.split()[0],
        "workdir": workdir_real,
        "total": total, "passed": passed, "failed": failed,
        "blocked": blocked, "not_executed": notrun,
        "duration_sec": duration,
        "inject_failure": runner.inject_failure,
        "note": "全部为合成夹具与本地 SQLite 测试库，不代表千问/生产 MySQL 行为",
    }
    if dry:
        payload = {"ok": failed == 0, "code": "OK" if failed == 0 else "SELFTEST_FAILED",
                   "status": "passed" if failed == 0 else "failed", "summary": summary,
                   "failed_cases": [r["case_id"] for r in runner.results if r["status"] != "通过"],
                   "dry": True}
        print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True))
        return 0 if payload["ok"] else 10

    with open(os.path.join(OUTPUT, "results.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"summary": summary, "cases": runner.results}, handle,
                  ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(OUTPUT, "results.csv"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("case_id,name,nature,status,expected_exit,actual_exit,command,expected_ref,note\n")
        for r in runner.results:
            handle.write(",".join([
                r["case_id"], r["name"].replace(",", "，"), r["nature"], r["status"],
                str(r["expected_exit"]), str(r["actual_exit"]),
                r["command"].replace(",", "，"), r["expected_ref"],
                (r["note"] or "").replace(",", "，")]) + "\n")
    with open(os.path.join(OUTPUT, "summary.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# 自测汇总（本机合成夹具）\n\n")
        handle.write("- 任务编号：MEM-EVIDENCE-001\n- Python：%s\n- 工作目录：%s\n"
                      % (sys.version.split()[0], workdir_real))
        handle.write("- 用例总数：%d，通过：%d，失败：%d，阻塞：%d，未执行：%d\n"
                     % (total, passed, failed, blocked, notrun))
        handle.write("- 耗时：%s 秒；故障注入模式：%s\n\n" % (duration, runner.inject_failure))
        handle.write("| 用例 | 名称 | 性质 | 预期退出码 | 实际退出码 | 状态 |\n|---|---|---|---|---|---|\n")
        for r in runner.results:
            handle.write("| %s | %s | %s | %s | %s | %s |\n" % (
                r["case_id"], r["name"], r["nature"], r["expected_exit"],
                r["actual_exit"], r["status"]))
    with open(os.path.join(OUTPUT, "run_log.txt"), "w", encoding="utf-8", newline="\n") as handle:
        for r in runner.results:
            handle.write("[%s] %s %s exit=%s/%s\n" % (r["status"], r["case_id"], r["name"],
                                                      r["actual_exit"], r["expected_exit"]))
            for check in r["checks"]:
                handle.write("    - %s: expected=%r actual=%r\n"
                             % (check["desc"], check["expected"], check["actual"]))

    payload = {"ok": failed == 0 and blocked == 0 and notrun == 0,
               "code": "OK" if failed == 0 and blocked == 0 and notrun == 0 else "SELFTEST_FAILED",
               "status": "passed" if failed == 0 and blocked == 0 and notrun == 0 else "failed",
               "summary": summary,
               "failed_cases": [r["case_id"] for r in runner.results if r["status"] != "通过"],
               "output_dir": os.path.relpath(OUTPUT, ROOT).replace("\\", "/")}
    print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True))
    return 0 if payload["ok"] else 10
