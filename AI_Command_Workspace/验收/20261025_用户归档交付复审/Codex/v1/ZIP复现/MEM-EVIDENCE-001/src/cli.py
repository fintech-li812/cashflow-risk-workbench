"""MEM-EVIDENCE-001 CLI：save / get / history / verify-store / selftest（含故障注入入口）。

返回格式统一为单行 JSON（--pretty 可缩进），退出码见 错误码说明.md：
0 OK | 1 未预期内部异常 | 2 用法/路径越界 | 3 校验拒绝 | 4 幂等冲突
5 范围内不存在 | 6 越权/身份范围不符 | 7 存储锁等待超时 | 8 一致性校验失败
9 故障注入子进程终止 | 10 自测断言失败 | 11 保存状态未确定

信任边界：--context 是**被调用者信任的本地测试上下文**（见 trust_boundary.md），
CLI 上自填的 tenant/company 不是认证，必须与可信上下文一致，否则按越权拒绝。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evidence_store import (FIXTURE_MARK, OPERATION_SAVE, Store, StoreError,  # noqa: E402
                            hold_exclusive_lock, load_json_file, resolve_store_path)
from result_guard import load_result_json  # noqa: E402

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_USAGE = 2
EXIT_VALIDATION = 3
EXIT_CONFLICT = 4
EXIT_NOT_FOUND = 5
EXIT_SCOPE = 6
EXIT_BUSY = 7
EXIT_VERIFY = 8
EXIT_FAULT = 9
EXIT_SELFTEST = 10
EXIT_UNKNOWN = 11

CODE_TO_EXIT = {
    "OK": EXIT_OK,
    "USAGE": EXIT_USAGE,
    "VALIDATION_FAILED": EXIT_VALIDATION,
    "CONFLICT": EXIT_CONFLICT,
    "NOT_FOUND": EXIT_NOT_FOUND,
    "SCOPE_DENIED": EXIT_SCOPE,
    "STORAGE_BUSY": EXIT_BUSY,
    "VERIFY_FAILED": EXIT_VERIFY,
    "FAULT_INJECTED": EXIT_FAULT,
    "SELFTEST_FAILED": EXIT_SELFTEST,
    "UNKNOWN_STATE": EXIT_UNKNOWN,
    "INTERNAL_ERROR": EXIT_INTERNAL,
}


def _emit(payload: dict, pretty: bool = False) -> None:
    if pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")))


def _fail(error: StoreError, pretty: bool) -> int:
    payload = {"ok": False, "code": error.code, "status": error.status,
               "message": error.message, "details": error.details}
    _emit(payload, pretty)
    return CODE_TO_EXIT.get(error.code, EXIT_INTERNAL)


def _require_workdir(workdir: str) -> str:
    real = os.path.realpath(workdir)
    if not os.path.isdir(real):
        raise StoreError("USAGE", "workdir does not exist: %s" % os.path.basename(real),
                         status="rejected")
    return real


def _open(workdir: str, store_arg: str) -> Store:
    return Store.open(resolve_store_path(workdir, store_arg))


def _identity_guard(context: dict, tenant_id, company_id) -> None:
    """CLI 自填身份必须与可信上下文一致，不一致即越权，不静默放行。"""
    for arg_name, arg_value, key in (("--tenant-id", tenant_id, "tenant_id"),
                                     ("--company-id", company_id, "company_id")):
        if arg_value is not None and arg_value != context.get(key):
            raise StoreError("SCOPE_DENIED",
                             "%s does not match the trusted context; self-filled identity "
                             "is not authentication" % arg_name, status="denied")


def _load_json_safe(path: str, label: str):
    """解析输入 JSON；非法 JSON / 非有限值统一转为受控校验失败，不抛未捕获异常。"""
    try:
        return load_json_file(path)
    except ValueError as exc:
        raise StoreError("VALIDATION_FAILED", "%s is not a valid finite result json: %s"
                         % (label, exc), status="rejected")


def cmd_save(args) -> int:
    try:
        workdir = _require_workdir(args.workdir)
        context = _load_json_safe(args.context, "context")
        result = _load_json_safe(args.input, "input")
        store = _open(workdir, args.store)
    except StoreError as exc:
        return _fail(exc, args.pretty)
    try:
        if args.save_diagnostic:
            out = store.save_diagnostic(result, context, args.request_id)
            out["ok"] = True
            out["code"] = "OK"
            out["exit_note"] = "诊断已记录，未生成 mfg-evidence.v1 committed 回执"
            _emit(out, args.pretty)
            return EXIT_OK
        out = store.save(result, context, args.request_id,
                         allow_fixture=args.allow_fixture, operation=args.operation,
                         fault_before_commit=args.fault_before_commit,
                         fault_after_commit=args.fault_after_commit,
                         simulate_unknown=args.simulate_unknown)
        out["ok"] = True
        out["code"] = "OK"
        if out["receipt"] and out["receipt"].get("is_fixture"):
            out["fixture_warning"] = (FIXTURE_MARK + " 本次为合成夹具结果，"
                                      "不代表真实来源，不得当作生产证据")
        if out["receipt"] and out["receipt"].get("reconciliation_state") == "not_performed":
            out["reconciliation_note"] = "缺少独立实际期末余额，未完成余额勾稽"
        _emit(out, args.pretty)
        return EXIT_OK
    except StoreError as exc:
        return _fail(exc, args.pretty)
    finally:
        store.close()


def cmd_get(args) -> int:
    try:
        workdir = _require_workdir(args.workdir)
        context = _load_json_safe(args.context, "context")
        _identity_guard(context, args.tenant_id, args.company_id)
        store = _open(workdir, args.store)
    except StoreError as exc:
        return _fail(exc, args.pretty)
    try:
        found = store.get(context, args.record_id)
        payload = {"ok": True, "code": "OK", "record_id": found["record_id"],
                   "receipt": found["receipt"], "reconciliation_state": found["reconciliation_state"]}
        if args.include_payload:
            payload["payload"] = found["payload"]
        if found["is_fixture"]:
            payload["fixture_warning"] = FIXTURE_MARK
        _emit(payload, args.pretty)
        return EXIT_OK
    except StoreError as exc:
        return _fail(exc, args.pretty)
    finally:
        store.close()


def cmd_history(args) -> int:
    try:
        workdir = _require_workdir(args.workdir)
        context = _load_json_safe(args.context, "context")
        _identity_guard(context, args.tenant_id, args.company_id)
        store = _open(workdir, args.store)
    except StoreError as exc:
        return _fail(exc, args.pretty)
    try:
        out = store.history(context, args.period, args.source_revision)
        out["ok"] = True
        out["code"] = "OK"
        _emit(out, args.pretty)
        return EXIT_OK
    except StoreError as exc:
        return _fail(exc, args.pretty)
    finally:
        store.close()


def cmd_verify(args) -> int:
    try:
        workdir = _require_workdir(args.workdir)
        store = _open(workdir, args.store)
    except StoreError as exc:
        return _fail(exc, args.pretty)
    try:
        report = store.verify()
        if report["problems"]:
            payload = {"ok": False, "code": "VERIFY_FAILED", "status": "tampered",
                       "message": "store consistency check found %d problem(s)"
                                 % len(report["problems"]),
                       "report": report}
            _emit(payload, args.pretty)
            return EXIT_VERIFY
        payload = {"ok": True, "code": "OK", "status": "verified",
                   "message": "store consistency check passed", "report": report}
        _emit(payload, args.pretty)
        return EXIT_OK
    except StoreError as exc:
        return _fail(exc, args.pretty)
    finally:
        store.close()


def cmd_lock_hold(args) -> int:
    """故障注入入口：由测试子进程独占写锁，用于验证锁超时行为。"""
    try:
        workdir = _require_workdir(args.workdir)
        path = resolve_store_path(workdir, args.store)
        Store.open(path).close()  # 确保库结构已建立，随后持锁
    except StoreError as exc:
        return _fail(exc, args.pretty)
    hold_exclusive_lock(path, args.seconds)
    _emit({"ok": True, "code": "OK", "action": "lock_released",
           "seconds": args.seconds}, args.pretty)
    return EXIT_OK


def cmd_selftest(args) -> int:
    from selftest import run_selftest
    return run_selftest(args.workdir, pretty=args.pretty,
                        inject_failure=getattr(args, "inject_failure", False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="MEM-EVIDENCE-001 本地可靠结果存储（SQLite 事务）")
    parser.add_argument("--pretty", action="store_true", help="缩进输出 JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(sp):
        sp.add_argument("--workdir", required=True, help="本次任务工作目录（库文件只能建在此目录内）")

    p_save = sub.add_parser("save", help="保存正式结果（或在 --save-diagnostic 下存诊断）")
    add_common(p_save)
    p_save.add_argument("--input", required=True, help="结果 JSON 路径")
    p_save.add_argument("--context", required=True, help="可信测试上下文 JSON 路径")
    p_save.add_argument("--request-id", required=True, help="逻辑请求 ID（重试沿用同一 ID）")
    p_save.add_argument("--store", default="evidence.sqlite3", help="库文件名，位于 workdir 内")
    p_save.add_argument("--operation", default=OPERATION_SAVE)
    p_save.add_argument("--allow-fixture", action="store_true",
                        help="显式允许 origin=offline_fixture 的合成夹具")
    p_save.add_argument("--save-diagnostic", action="store_true",
                        help="非 success 结果只存诊断，不产生正式回执")
    p_save.add_argument("--fault-before-commit", action="store_true",
                        help="故障注入：INSERT 后、COMMIT 前终止进程")
    p_save.add_argument("--fault-after-commit", action="store_true",
                        help="故障注入：COMMIT 成功后、回执返回前终止进程")
    p_save.add_argument("--simulate-unknown", action="store_true",
                        help="故障注入：提交后回执未确定交付，返回未确定态（非 0）")
    p_save.set_defaults(func=cmd_save)

    p_get = sub.add_parser("get", help="按 record_id 精确读取快照与回执")
    add_common(p_get)
    p_get.add_argument("--context", required=True)
    p_get.add_argument("--record-id", required=True)
    p_get.add_argument("--store", default="evidence.sqlite3")
    p_get.add_argument("--tenant-id", default=None, help="须与可信上下文一致")
    p_get.add_argument("--company-id", default=None, help="须与可信上下文一致")
    p_get.add_argument("--include-payload", action="store_true")
    p_get.set_defaults(func=cmd_get)

    p_hist = sub.add_parser("history", help="按期间列出历史（只追加）并给出当前有效选择")
    add_common(p_hist)
    p_hist.add_argument("--context", required=True)
    p_hist.add_argument("--period", required=True)
    p_hist.add_argument("--source-revision", default=None)
    p_hist.add_argument("--store", default="evidence.sqlite3")
    p_hist.add_argument("--tenant-id", default=None)
    p_hist.add_argument("--company-id", default=None)
    p_hist.add_argument("--verbose", action="store_true", help="额外输出金额（默认只出元数据）")
    p_hist.set_defaults(func=cmd_history)

    p_verify = sub.add_parser("verify-store", help="一致性复核：哈希/关联/回执/勾稽")
    add_common(p_verify)
    p_verify.add_argument("--store", default="evidence.sqlite3")
    p_verify.set_defaults(func=cmd_verify)

    p_lock = sub.add_parser("lock-hold", help="故障注入入口：子进程独占写锁若干秒")
    add_common(p_lock)
    p_lock.add_argument("--store", default="evidence.sqlite3")
    p_lock.add_argument("--seconds", type=int, default=5)
    p_lock.set_defaults(func=cmd_lock_hold)

    p_self = sub.add_parser("selftest", help="在全新工作目录运行完整测试矩阵")
    add_common(p_self)
    p_self.add_argument("--inject-failure", action="store_true",
                        help="故意让一例断言失败，用于验证自测非 0 退出真实触发")
    p_self.set_defaults(func=cmd_selftest)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:  # 未预期异常：打印原文并以 1 退出，绝不伪装成功
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
