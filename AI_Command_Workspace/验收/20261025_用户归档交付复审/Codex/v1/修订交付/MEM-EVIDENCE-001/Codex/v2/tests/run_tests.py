"""自测入口（与 `python -m src.cli selftest` 等价）。

用法：python tests/run_tests.py --workdir <全新目录>
退出码：0 全部通过；10 存在失败/阻塞/未执行；2 工作目录已存在且非空。
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from selftest import run_selftest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--inject-failure", action="store_true",
                        help="故意让一例断言失败，用于验证非 0 退出真实触发")
    args = parser.parse_args()
    return run_selftest(args.workdir, pretty=args.pretty, inject_failure=args.inject_failure)


if __name__ == "__main__":
    sys.exit(main())
