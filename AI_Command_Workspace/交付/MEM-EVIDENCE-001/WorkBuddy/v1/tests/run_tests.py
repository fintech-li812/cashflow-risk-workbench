"""MEM-EVIDENCE-001 独立测试矩阵 runner。

运行（在交付根目录 v1/ 下）：
    python tests/run_tests.py

约定：
- 每个用例通过 subprocess 真实调用 src/evidence_cli.py（独立进程），
  退出码/stdout/stderr 原样落盘 test-output/<用例>/。
- 独立预期只读 expected/cli_cases_expected.json（冻结），运行前后核其 SHA256，
  本程序永不改写 expected/ 与 fixtures/。
- 判定：实际退出码与预期一致且关键关系断言通过 → PASS，否则 FAIL；
  非预期异常如实 FAIL 并附类型名，不伪装 BLOCKED。
- 任一用例 FAIL → 汇总退出码 1；全部 PASS → 0。
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "src" / "evidence_cli.py"
FX = ROOT / "fixtures"
EXPECTED = ROOT / "expected" / "cli_cases_expected.json"
OUT = ROOT / "test-output"
RUN = OUT / ("run_" + time.strftime("%Y%m%d_%H%M%S"))

RESULTS = []


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_cli(case: str, step: str, args: list) -> tuple:
    """跑一次 CLI，落盘证据，返回 (exit_code, stdout_obj_or_text)."""
    cdir = RUN / case
    cdir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(CLI)] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    (cdir / f"{step}.cmd.txt").write_text(" ".join(cmd), encoding="utf-8")
    (cdir / f"{step}.stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (cdir / f"{step}.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    (cdir / f"{step}.exit.txt").write_text(str(proc.returncode), encoding="utf-8")
    try:
        return proc.returncode, json.loads(proc.stdout)
    except ValueError:
        return proc.returncode, proc.stdout


def db_count(db: Path, request_id: str) -> int:
    con = sqlite3.connect(str(db))
    try:
        row = con.execute(
            "SELECT COUNT(*) FROM evidence_records WHERE request_id=?",
            (request_id,)).fetchone()
        return int(row[0])
    finally:
        con.close()


def db_all_count(db: Path) -> int:
    con = sqlite3.connect(str(db))
    try:
        return int(con.execute("SELECT COUNT(*) FROM evidence_records").fetchone()[0])
    finally:
        con.close()


def db_diag_count(db: Path) -> int:
    con = sqlite3.connect(str(db))
    try:
        return int(con.execute("SELECT COUNT(*) FROM diagnostics").fetchone()[0])
    finally:
        con.close()


def record(tc: str, name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append({"case": tc, "name": name, "status": "PASS" if passed else "FAIL",
                    "detail": detail})
    print(f"[{'PASS' if passed else 'FAIL'}] {tc} {name} {detail}")


def expect_exit(tc: str, expect: dict, actual: int) -> bool:
    return actual == expect["expect_exit"]


def main() -> int:
    expected_sha_before = sha256_file(EXPECTED)
    fixtures_sha_before = {p.name: sha256_file(p) for p in sorted(FX.glob("*.json"))}
    exp = json.loads(EXPECTED.read_text(encoding="utf-8"))["cases"]
    fx_sha = json.loads(EXPECTED.read_text(encoding="utf-8"))["fixture_payload_sha256"]

    RUN.mkdir(parents=True, exist_ok=True)
    wd = RUN / "wd"
    wd.mkdir()
    db = wd / "test.db"
    ctx = str(FX / "context_trusted.json")
    ctx_b = str(FX / "context_other_tenant.json")
    ctx_r2 = str(FX / "context_rev2.json")
    ok_fixture = str(FX / "result_success_fixture.json")

    def save_args(inp, rid, context=ctx, allow=True, extra=None, store=None):
        a = ["save", "--input", inp, "--context", context,
             "--request-id", rid, "--store", str(store or db)]
        if allow:
            a.append("--allow-fixture")
        if extra:
            a += extra
        return a

    # TC-01 正常提交
    code, out = run_cli("TC-01", "save", save_args(ok_fixture, "st-01"))
    rid = out.get("receipt", {}).get("record_id", "") if isinstance(out, dict) else ""
    record("TC-01", "正常提交",
           expect_exit("TC-01", exp["TC-01"], code)
           and isinstance(out, dict) and out.get("status") == "committed"
           and out["receipt"]["payload_sha256"] == fx_sha["result_success_fixture.json"],
           f"exit={code} record_id={rid}")

    # TC-02 跨进程重启读回（每个CLI调用本就是新进程；再显式get验证）
    code, out = run_cli("TC-02", "get", ["get", "--tenant-id", "fixture-tenant",
                        "--company-id", "fixture-company", "--record-id", rid,
                        "--store", str(db)])
    record("TC-02", "重启读回与哈希一致",
           expect_exit("TC-02", exp["TC-02"], code)
           and isinstance(out, dict) and out.get("receipt", {}).get("payload_sha256")
           == fx_sha["result_success_fixture.json"], f"exit={code}")

    # TC-03 全0金额
    code, out = run_cli("TC-03", "save",
                        save_args(str(FX / "result_zero_amounts_fixture.json"), "st-03"))
    record("TC-03", "全0金额允许", expect_exit("TC-03", exp["TC-03"], code)
           and out.get("status") == "committed", f"exit={code}")

    # TC-04 缺独立余额
    code, out = run_cli("TC-04", "save",
                        save_args(str(FX / "result_no_balance_fixture.json"), "st-04"))
    record("TC-04", "缺独立余额双null允许", expect_exit("TC-04", exp["TC-04"], code)
           and out.get("status") == "committed", f"exit={code}")

    # TC-05 net差一分
    code, _ = run_cli("TC-05", "save",
                      save_args(str(FX / "result_net_off_by_cent_fixture.json"), "st-05"))
    record("TC-05", "net差一分拒绝", expect_exit("TC-05", exp["TC-05"], code), f"exit={code}")

    # TC-06 非法金额
    code, _ = run_cli("TC-06", "save",
                      save_args(str(FX / "result_bad_amount_fixture.json"), "st-06"))
    record("TC-06", "非法金额字符串拒绝", expect_exit("TC-06", exp["TC-06"], code),
           f"exit={code}")

    # TC-07 缺必填
    code, _ = run_cli("TC-07", "save",
                      save_args(str(FX / "result_missing_field.json"), "st-07"))
    record("TC-07", "缺company_id拒绝", expect_exit("TC-07", exp["TC-07"], code),
           f"exit={code}")

    # TC-08 身份不一致
    code, _ = run_cli("TC-08", "save", save_args(ok_fixture, "st-08", context=ctx_b))
    record("TC-08", "payload与context身份不一致拒绝",
           expect_exit("TC-08", exp["TC-08"], code), f"exit={code}")

    # TC-09 源版本不一致
    code, _ = run_cli("TC-09", "save", save_args(ok_fixture, "st-09", context=ctx_r2))
    record("TC-09", "source_revision不一致拒绝",
           expect_exit("TC-09", exp["TC-09"], code), f"exit={code}")

    # TC-10 非success只入诊断
    code, out = run_cli("TC-10", "save",
                        save_args(str(FX / "result_non_success.json"), "st-10"))
    record("TC-10", "非success无回执且入诊断",
           expect_exit("TC-10", exp["TC-10"], code)
           and db_diag_count(db) == 1 and db_count(db, "st-10") == 0, f"exit={code}")

    # TC-11a 默认拒绝fixture
    code, _ = run_cli("TC-11a", "save", save_args(ok_fixture, "st-11", allow=False))
    record("TC-11a", "默认拒绝fixture", expect_exit("TC-11a", exp["TC-11a"], code),
           f"exit={code}")
    # TC-11b 显式允许且带合成标识
    code, out = run_cli("TC-11b", "save", save_args(ok_fixture, "st-11", allow=True))
    marker = "fixture_marker" in json.dumps(out, ensure_ascii=False) or \
        "合成" in json.dumps(out, ensure_ascii=False)
    record("TC-11b", "显式允许fixture且带合成标识",
           expect_exit("TC-11b", exp["TC-11b"], code) and marker, f"exit={code}")

    # TC-12 同键同参回放
    code, out = run_cli("TC-12", "save", save_args(ok_fixture, "st-01"))
    record("TC-12", "同键同参回放原record_id且行数不增",
           expect_exit("TC-12", exp["TC-12"], code)
           and out.get("idempotent_replay") is True
           and out["receipt"]["record_id"] == exp["TC-12"]["expect_record_id"]
           and db_count(db, "st-01") == 1, f"exit={code}")

    # TC-13 同键异参冲突不覆盖
    tampered_input = RUN / "TC-13" / "changed.json"
    tampered_input.parent.mkdir(parents=True, exist_ok=True)
    obj = json.loads(Path(ok_fixture).read_text(encoding="utf-8"))
    obj["amounts"]["inflow"] = "130000.01"
    obj["amounts"]["net"] = "40000.01"
    obj["amounts"]["closing"] = "140000.01"
    obj["amounts"]["actual_closing"] = "140000.01"
    tampered_input.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    code, out = run_cli("TC-13", "save", save_args(str(tampered_input), "st-01"))
    vcode, _ = run_cli("TC-13", "verify", ["verify-store", "--store", str(db)])
    record("TC-13", "同键异参冲突且旧记录未被覆盖",
           expect_exit("TC-13", exp["TC-13"], code) and vcode == 0
           and db_count(db, "st-01") == 1, f"exit={code} verify={vcode}")

    # TC-14 跨身份 not_found
    code, _ = run_cli("TC-14", "get", ["get", "--tenant-id", "fixture-tenant-B",
                      "--company-id", "fixture-company-B", "--record-id", rid,
                      "--store", str(db)])
    record("TC-14", "跨身份get不泄露", expect_exit("TC-14", exp["TC-14"], code),
           f"exit={code}")

    # TC-15 commit前故障无半条
    code, _ = run_cli("TC-15", "save",
                      save_args(ok_fixture, "st-15",
                                extra=["--fault-inject", "before_commit"]))
    rows_after_fail = db_count(db, "st-15")
    code2, _ = run_cli("TC-15", "retry", save_args(ok_fixture, "st-15"))
    record("TC-15", "commit前故障无半条且可重试",
           expect_exit("TC-15", exp["TC-15"], code)
           and rows_after_fail == 0 and code2 == 0, f"exit={code} retry={code2}")

    # TC-16 commit后回执丢失，同ID重试返回原记录
    code, _ = run_cli("TC-16", "save",
                      save_args(ok_fixture, "st-16",
                                extra=["--fault-inject", "after_commit"]))
    code2, out2 = run_cli("TC-16", "retry", save_args(ok_fixture, "st-16"))
    record("TC-16", "commit后回执丢失（子进程exit42）重试返回原record_id",
           code == 42 and expect_exit("TC-16", exp["TC-16"], code2)
           and isinstance(out2, dict) and out2.get("idempotent_replay") is True
           and db_count(db, "st-16") == 1, f"fault_exit={code} retry={code2}")

    # TC-17 受控竞争：同键同参并发 -> 行数1；同键异参并发 -> 一个0一个2
    # 竞争点是“提交”，不是“同时建库”：父进程先预建库消除建库竞争源。
    (RUN / "TC-17").mkdir(parents=True, exist_ok=True)
    run_cli("TC-17", "warmup", ["verify-store", "--store", str(db)])

    def race(rid: str, inputs: list, tag: str) -> list:
        procs = []
        for i, inp in enumerate(inputs):
            (RUN / "TC-17" / f"{tag}_{i}.cmd.txt").write_text(
                "save " + rid, encoding="utf-8")
            procs.append(subprocess.Popen(
                [sys.executable, str(CLI)] + save_args(inp, rid),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8"))
        codes = []
        for i, p in enumerate(procs):
            so, se = p.communicate()
            codes.append(p.returncode)
            (RUN / "TC-17" / f"{tag}_{i}.stdout.txt").write_text(so, encoding="utf-8")
            (RUN / "TC-17" / f"{tag}_{i}.stderr.txt").write_text(se, encoding="utf-8")
            (RUN / "TC-17" / f"{tag}_{i}.exit.txt").write_text(
                str(p.returncode), encoding="utf-8")
        return sorted(codes)

    codes = race("st-17", [ok_fixture, ok_fixture], "same")
    rows = db_count(db, "st-17")
    (RUN / "TC-17" / "exits.txt").write_text(json.dumps(codes), encoding="utf-8")
    record("TC-17a", "并发同键同参唯一（行数1，退出码均在{0,2}）",
           rows == 1 and all(c in exp["TC-17"]["expect_exit_set"] for c in codes),
           f"exits={codes} rows={rows}")
    obj_b = json.loads(Path(ok_fixture).read_text(encoding="utf-8"))
    obj_b["amounts"]["outflow"] = "90000.01"
    obj_b["amounts"]["net"] = "39999.99"
    obj_b["amounts"]["closing"] = "139999.99"
    obj_b["amounts"]["actual_closing"] = "139999.99"
    alt = RUN / "TC-17" / "alt.json"
    alt.write_text(json.dumps(obj_b, ensure_ascii=False), encoding="utf-8")
    codes_b = race("st-17b", [ok_fixture, str(alt)], "diff")
    rows_b = db_count(db, "st-17b")
    (RUN / "TC-17" / "exits_b.txt").write_text(json.dumps(codes_b), encoding="utf-8")
    record("TC-17b", "并发同键异参恰一提交一冲突（行数1）",
           rows_b == 1 and codes_b == [0, 2], f"exits={codes_b} rows={rows_b}")

    # TC-18 历史追加不覆盖（同period不同request_id）
    time.sleep(0.05)
    code, _ = run_cli("TC-18", "save", save_args(ok_fixture, "st-18"))
    code, out = run_cli("TC-18", "history", ["history", "--tenant-id", "fixture-tenant",
                        "--company-id", "fixture-company", "--period", "2026-08",
                        "--store", str(db)])
    record("TC-18", "历史追加不覆盖",
           expect_exit("TC-18", exp["TC-18"], code)
           and len(out.get("entries", [])) >= exp["TC-18"]["expect_entries"],
           f"exit={code} entries={len(out.get('entries', []))}")

    # TC-19 当前有效=stored_at最新
    record("TC-19", "当前有效选择规则",
           expect_exit("TC-19", exp["TC-19"], code)
           and out["current_effective_record_id"] == out["entries"][-1]["record_id"]
           and "不跨主体" in out["selection_rule"],
           f"current={out.get('current_effective_record_id')}")

    # TC-20 篡改payload_json被检出
    tdb = RUN / "wd_tamper"
    tdb.mkdir()
    tdb_path = tdb / "t.db"
    run_cli("TC-20", "seed", save_args(ok_fixture, "t-20", store=tdb_path))
    con = sqlite3.connect(str(tdb_path))
    con.execute("UPDATE evidence_records SET payload_json = payload_json || ' '")
    con.commit()
    con.close()
    code, out = run_cli("TC-20", "verify", ["verify-store", "--store", str(tdb_path)])
    record("TC-20", "篡改payload被verify检出",
           expect_exit("TC-20", exp["TC-20"], code), f"exit={code}")

    # TC-21 篡改索引列被检出
    con = sqlite3.connect(str(tdb_path))
    con.execute("UPDATE evidence_records SET tenant_id = 'evil-tenant'")
    con.commit()
    con.close()
    code, out = run_cli("TC-21", "verify", ["verify-store", "--store", str(tdb_path)])
    record("TC-21", "篡改索引列被verify检出",
           expect_exit("TC-21", exp["TC-21"], code), f"exit={code}")

    # TC-22 正常库重开verify通过
    code, out = run_cli("TC-22", "verify", ["verify-store", "--store", str(db)])
    record("TC-22", "关库重开verify通过",
           expect_exit("TC-22", exp["TC-22"], code)
           and out.get("status") == "ok", f"exit={code}")

    # TC-23 路径越界拒绝
    outside = RUN / "wd"
    code, _ = run_cli("TC-23", "save",
                      ["save", "--input", ok_fixture, "--context", ctx,
                       "--request-id", "st-23", "--store", "../escape.db",
                       "--workdir", str(wd), "--allow-fixture"])
    record("TC-23", "store路径越界拒绝", expect_exit("TC-23", exp["TC-23"], code),
           f"exit={code}")
    escape_exists = (RUN / "escape.db").exists()
    record("TC-23b", "越界目标文件未被创建", not escape_exists,
           f"exists={escape_exists}")

    # TC-24 SQL特殊字符
    evil_rid = "x'); DROP TABLE evidence_records;--"
    code, out = run_cli("TC-24", "save", save_args(ok_fixture, evil_rid))
    vcode, _ = run_cli("TC-24", "verify", ["verify-store", "--store", str(db)])
    record("TC-24", "SQL特殊字符参数化处理且库完好",
           expect_exit("TC-24", exp["TC-24"], code) and vcode == 0,
           f"exit={code} verify={vcode}")

    # TC-25 selftest 注入失败必须非0
    st_dir = RUN / "selftest_bad"
    code, _ = run_cli("TC-25", "selftest",
                      ["selftest", "--workdir", str(st_dir), "--selftest-fail-inject"])
    record("TC-25", "selftest注入失败非0退出",
           expect_exit("TC-25", exp["TC-25"], code), f"exit={code}")

    # selftest 正例（全新目录）
    st_ok = RUN / "selftest_ok"
    code, out = run_cli("SELFTEST", "selftest", ["selftest", "--workdir", str(st_ok)])
    record("SELFTEST", "selftest正例全过且exit0",
           code == 0 and isinstance(out, dict) and out.get("selftest") == "PASSED",
           f"exit={code}")

    # ---- 收尾：expected/fixtures 哈希复核 ----
    expected_sha_after = sha256_file(EXPECTED)
    fixtures_sha_after = {p.name: sha256_file(p) for p in sorted(FX.glob("*.json"))}
    frozen_ok = (expected_sha_before == expected_sha_after
                 and fixtures_sha_before == fixtures_sha_after)
    record("FROZEN", "expected与fixtures运行前后哈希不变", frozen_ok)

    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = len(RESULTS) - passed
    summary = {"total": len(RESULTS), "pass": passed, "fail": failed,
               "blocked": 0, "not_executed": 0,
               "expected_sha256": expected_sha_after,
               "results": RESULTS}
    (RUN / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n合计 {len(RESULTS)} 项：PASS {passed} / FAIL {failed} / BLOCKED 0 / 未执行 0")
    print(f"证据目录: {RUN}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
