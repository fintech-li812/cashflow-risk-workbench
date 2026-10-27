"""MEM-EVIDENCE-001 CLI：save / get / history / verify-store / selftest。

用法（在交付根目录）：
  python src/evidence_cli.py save --input <结果JSON> --context <可信上下文JSON> \
      --request-id <逻辑ID> --store <库路径> [--workdir <目录>] [--allow-fixture]
  python src/evidence_cli.py get --tenant-id T --company-id C --record-id R \
      --store <库路径> [--workdir <目录>]
  python src/evidence_cli.py history --tenant-id T --company-id C --period YYYY-MM \
      --store <库路径> [--workdir <目录>]
  python src/evidence_cli.py verify-store --store <库路径> [--workdir <目录>]
  python src/evidence_cli.py selftest --workdir <全新目录>

约定：
- stdout 只输出机器可读 JSON；人类说明与告警走 stderr。
- --store 与 --workdir 同时给出时，库路径必须解析在 workdir 之内；
  未给 --workdir 时以 store 所在目录为界（拒绝其外的相对穿越）。
- --fault-inject 仅供受控测试子进程使用：before_commit / after_commit。
- 退出码见 错误码说明.md。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evidence_store import (EXIT_CONFLICT, EXIT_INTERNAL, EXIT_INVALID, EXIT_NON_SUCCESS,
                            EXIT_NOT_FOUND, EXIT_OK, EXIT_STORE_ERROR, EXIT_TAMPER,
                            EvidenceStore, FaultInjected, ValidationError)


def _emit(obj, exit_code):
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return exit_code


def _load_json(path_arg: str, what: str):
    try:
        with open(path_arg, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise ValidationError(f"{what} 无法读取或不是合法JSON（文件名级错误，不透露内容）") from exc


def _resolve_store(args) -> Path:
    workdir = args.workdir
    if workdir is None:
        p = Path(args.store).resolve()
        workdir = str(p.parent)
    return EvidenceStore.resolve_store_path(args.store, workdir)


def cmd_save(args) -> int:
    result = _load_json(args.input, "结果文件")
    context = _load_json(args.context, "context文件")
    store = EvidenceStore(_resolve_store(args))
    try:
        outcome, code = store.save(result, context, args.request_id,
                                   allow_fixture=args.allow_fixture,
                                   fault=args.fault_inject)
    finally:
        store.close()
    return _emit(outcome, code)


def cmd_get(args) -> int:
    store = EvidenceStore(_resolve_store(args))
    try:
        outcome, code = store.get(args.tenant_id, args.company_id, args.record_id)
    finally:
        store.close()
    return _emit(outcome, code)


def cmd_history(args) -> int:
    store = EvidenceStore(_resolve_store(args))
    try:
        outcome, code = store.history(args.tenant_id, args.company_id, args.period)
    finally:
        store.close()
    return _emit(outcome, code)


def cmd_verify(args) -> int:
    store = EvidenceStore(_resolve_store(args))
    try:
        outcome, code = store.verify_store()
    finally:
        store.close()
    return _emit(outcome, code)


# ---------------------------------------------------------------- selftest

def _selftest(workdir: Path, fail_inject: bool) -> int:
    """在全新 workdir 内自证：成功/缺项/失败结果、事务、幂等、冲突、回查。"""
    if workdir.exists() and any(workdir.iterdir()):
        print("selftest 拒绝非空目录：" + workdir.name, file=sys.stderr)
        return EXIT_INVALID
    workdir.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent.parent
    fx = here / "fixtures"
    context = _load_json(str(fx / "context_trusted.json"), "context夹具")
    db = workdir / "selftest.db"

    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        return ok

    # fail_inject：演示断言失败时退出码非0（测试入口，文档注明）
    if fail_inject:
        check("selftest-fail-inject（人为注入的失败断言）", False,
              "该用例被 --selftest-fail-inject 强制置为失败，用于证明退出码非0可真实触发")
        return _emit({"selftest": "FAILED", "checks": checks}, EXIT_INTERNAL)

    store = EvidenceStore(db)
    # 1. fixture 默认拒绝
    fx_result = _load_json(str(fx / "result_success_fixture.json"), "夹具")
    _, code = store.save(dict(fx_result), dict(context), "st-01", allow_fixture=False)
    check("fixture 默认拒绝", code == EXIT_INVALID, f"exit={code}")
    # 2. 显式允许后成功提交
    out1, code1 = store.save(dict(fx_result), dict(context), "st-01", allow_fixture=True)
    check("fixture 显式允许后提交", code1 == EXIT_OK and out1["status"] == "committed",
          f"exit={code1}")
    rid = out1.get("receipt", {}).get("record_id", "")
    # 3. 同键同参幂等回放
    out2, code2 = store.save(dict(fx_result), dict(context), "st-01", allow_fixture=True)
    check("同键同参幂等回放",
          code2 == EXIT_OK and out2.get("idempotent_replay") is True
          and out2["receipt"]["record_id"] == rid, f"exit={code2}")
    # 4. 同键异参冲突
    changed = dict(fx_result)
    changed["amounts"] = dict(changed["amounts"], inflow="130000.01", net="40000.01",
                              closing="140000.01", actual_closing="140000.01",
                              difference="0.00")
    _, code4 = store.save(changed, dict(context), "st-01", allow_fixture=True)
    check("同键异参冲突且不覆盖", code4 == EXIT_CONFLICT, f"exit={code4}")
    # 5. 精确回查
    gout, gcode = store.get(context["tenant_id"], context["company_id"], rid)
    check("按 record_id 精确回查",
          gcode == EXIT_OK and gout["receipt"]["payload_sha256"]
          == out1["receipt"]["payload_sha256"], f"exit={gcode}")
    # 6. 缺独立余额：允许保存且双 null
    nb = _load_json(str(fx / "result_no_balance_fixture.json"), "夹具")
    nbo, nbcode = store.save(nb, dict(context), "st-02", allow_fixture=True)
    check("缺实际余额保存成功且双null",
          nbcode == EXIT_OK and nb["amounts"]["actual_closing"] is None
          and nb["amounts"]["difference"] is None, f"exit={nbcode}")
    # 7. 差一分拒绝
    bad = _load_json(str(fx / "result_net_off_by_cent_fixture.json"), "夹具")
    _, badcode = store.save(bad, dict(context), "st-03", allow_fixture=True)
    check("净额差一分拒绝", badcode == EXIT_INVALID, f"exit={badcode}")
    # 8. 非 success 只入诊断
    ns = _load_json(str(fx / "result_non_success.json"), "夹具")
    nso, nscode = store.save(ns, dict(context), "st-04", allow_fixture=True)
    check("非success无正式回执", nscode == EXIT_NON_SUCCESS
          and nso["status"] == "diagnosed", f"exit={nscode}")
    # 9. 历史追加不覆盖
    hout, hcode = store.history(context["tenant_id"], context["company_id"],
                                context["period"])
    check("history 两条记录且当前有效可解释",
          hcode == EXIT_OK and len(hout["entries"]) == 2
          and hout["current_effective_record_id"] == hout["entries"][-1]["record_id"],
          f"exit={hcode}")
    # 10. verify-store
    vout, vcode = store.verify_store()
    check("verify-store 通过", vcode == EXIT_OK and vout["checked_records"] == 2,
          f"exit={vcode}")
    store.close()
    # 11. 重启读回
    store2 = EvidenceStore(db)
    gout2, gcode2 = store2.get(context["tenant_id"], context["company_id"], rid)
    check("关库重开后读回同一记录", gcode2 == EXIT_OK, f"exit={gcode2}")
    store2.close()

    passed = sum(1 for c in checks if c["pass"])
    failed = len(checks) - passed
    print(f"selftest: {passed} 通过 / {failed} 失败（库与证据在 {workdir.name}）",
          file=sys.stderr)
    return _emit({"selftest": "PASSED" if failed == 0 else "FAILED",
                  "workdir": str(workdir), "checks": checks},
                 EXIT_OK if failed == 0 else EXIT_INTERNAL)


def cmd_selftest(args) -> int:
    try:
        return _selftest(Path(args.workdir).resolve(), args.selftest_fail_inject)
    except FaultInjected as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_STORE_ERROR


# ---------------------------------------------------------------- argparse

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evidence_cli",
                                description="MEM-EVIDENCE-001 本地证据存储CLI（SQLite，非生产）")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("save", help="校验并幂等保存结果")
    s.add_argument("--input", required=True)
    s.add_argument("--context", required=True)
    s.add_argument("--request-id", required=True)
    s.add_argument("--store", required=True)
    s.add_argument("--workdir", default=None)
    s.add_argument("--allow-fixture", action="store_true")
    s.add_argument("--fault-inject", choices=["none", "before_commit", "after_commit"],
                   default="none", help="仅受控测试子进程使用")
    s.set_defaults(func=cmd_save)

    g = sub.add_parser("get", help="按 record_id 精确回查（限同身份）")
    g.add_argument("--tenant-id", required=True)
    g.add_argument("--company-id", required=True)
    g.add_argument("--record-id", required=True)
    g.add_argument("--store", required=True)
    g.add_argument("--workdir", default=None)
    g.set_defaults(func=cmd_get)

    h = sub.add_parser("history", help="同主体同期间历史与当前有效")
    h.add_argument("--tenant-id", required=True)
    h.add_argument("--company-id", required=True)
    h.add_argument("--period", required=True)
    h.add_argument("--store", required=True)
    h.add_argument("--workdir", default=None)
    h.set_defaults(func=cmd_history)

    v = sub.add_parser("verify-store", help="复核哈希/关联/勾稽，检出篡改返回非0")
    v.add_argument("--store", required=True)
    v.add_argument("--workdir", default=None)
    v.set_defaults(func=cmd_verify)

    t = sub.add_parser("selftest", help="全新目录内自证，失败退出码非0")
    t.add_argument("--workdir", required=True)
    t.add_argument("--selftest-fail-inject", action="store_true",
                   help="人为注入一条失败断言，演示退出码非0（仅测试）")
    t.set_defaults(func=cmd_selftest)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValidationError as exc:
        return _emit({"status": "invalid", "reason": str(exc)}, EXIT_INVALID)
    except FaultInjected as exc:
        print(str(exc), file=sys.stderr)
        return _emit({"status": "store_error",
                      "reason": "故障注入：commit前失败，事务已回滚"}, EXIT_STORE_ERROR)
    except Exception as exc:  # 非预期异常：非0退出，不伪装 BLOCKED
        print("内部错误: " + type(exc).__name__, file=sys.stderr)
        return _emit({"status": "internal_error",
                      "reason": "非预期异常（类型级脱敏）"}, EXIT_INTERNAL)


if __name__ == "__main__":
    sys.exit(main())
