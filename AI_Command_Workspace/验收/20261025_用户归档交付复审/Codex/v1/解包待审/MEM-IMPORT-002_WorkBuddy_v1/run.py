"""统一入口：python run.py scan|verify|selftest ...
等价于 PYTHONPATH=src python -m mfg_import，方便照抄运行。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from mfg_import.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
