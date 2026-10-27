"""CLI 入口：scan / verify / selftest。

退出码：
- scan:    0=技术执行成功（业务疑点见报告，不等于数据合格）；2=参数错误；1=运行错误
- verify:  0=全部核对通过；1=存在不符项或运行错误；2=参数错误
- selftest: 0=全部用例 PASS；1=存在 FAIL/BLOCKED/意外异常；2=参数错误
"""
import argparse
import sys

from .scanner import ScanError, scan
from .verifier import verify


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mfg_import",
                                     description="制造业 Excel 导入与来源追溯工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="扫描输入目录，生成 mfg-import.v1 导入包")
    p_scan.add_argument("--input", required=True)
    p_scan.add_argument("--output", required=True, help="全新输出目录（已存在则拒绝）")
    p_scan.add_argument("--mapping", required=True)
    p_scan.add_argument("--tenant-id", required=True)
    p_scan.add_argument("--company-id", required=True)
    p_scan.add_argument("--period", required=True)
    p_scan.add_argument("--run-id", required=True)
    p_scan.add_argument("--unit-exceptions", default=None)

    p_ver = sub.add_parser("verify", help="独立核对导入包与真实源")
    p_ver.add_argument("--package", required=True)
    p_ver.add_argument("--source", required=True)

    p_self = sub.add_parser("selftest", help="合成夹具正反例自测")
    p_self.add_argument("--workdir", required=True, help="全新测试目录（已存在则拒绝）")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "scan":
            return scan(args.input, args.output, args.mapping,
                        args.tenant_id, args.company_id, args.period,
                        args.run_id, exceptions_path=args.unit_exceptions)
        if args.cmd == "verify":
            return verify(args.package, args.source)
        if args.cmd == "selftest":
            from .selftest import run_selftest
            return run_selftest(args.workdir)
    except ScanError as e:
        print(f"[参数/运行错误] {e}", file=sys.stderr)
        return 2
    except Exception as e:  # 意外异常必须非0，不伪装 PASS/BLOCKED
        print(f"[意外错误] {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
