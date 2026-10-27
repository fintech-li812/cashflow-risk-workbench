"""WB-AGENT-003 独立自测入口：在包根目录执行 python run_tests.py。

把 candidate/ 与包根加入模块搜索路径后运行 tests/ 下全部用例。
任一用例失败即以退出码 1 结束；不覆盖、不重写独立预期基准。
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
for p in (str(HERE / "candidate"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(HERE / "tests"), top_level_dir=str(HERE))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print(f"\nran={result.testsRun} failures={len(result.failures)} "
          f"errors={len(result.errors)} skipped={len(result.skipped)}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
