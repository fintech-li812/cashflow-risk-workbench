"""静态边界检查：证明本包源码不含对外连接、不含删除/清理逻辑、不含凭据读取。

只做只读文本扫描，输出 JSON：{"ok":true,"findings":[...]}，退出码 0/10。
这是静态证据，不能证明运行时行为，也不能证明平台能力。
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_DIRS = ("src", "tests")
SCAN_SUFFIX = (".py",)

FORBIDDEN = {
    "network_client": r"\b(pymysql|mysql\.connector|psycopg2|requests|httpx|urllib\.request|socket\.create_connection)\b",
    "outbound_send": r"\b(smtplib|webbrowser|subprocess\.Popen\(\s*\[[^\]]*(curl|wget))",
    "delete_logic": r"\b(shutil\.rmtree|os\.remove|os\.unlink|os\.rmdir|DROP\s+TABLE)\b",
    "credential_read": r"\b(getenv|environ)\s*\(\s*[\"'](PASSWORD|PASSWD|TOKEN|SECRET|PRIVATE_KEY)[\"']",
    "git_push": r"\bgit\s+push\b",
    "wildcard_delete_sql": r"DELETE\s+FROM\s+\w+\s*;",
}

# 本文件自身只保存规则字符串，不参与违规判定（否则规则表会把自身判为违规）
SELF_FILE = "static_boundary_check.py"


def main() -> int:
    findings = []
    scanned = 0
    for directory in SCAN_DIRS:
        base = os.path.join(ROOT, directory)
        for name in sorted(os.listdir(base)):
            if not name.endswith(SCAN_SUFFIX):
                continue
            scanned += 1
            path = os.path.join(base, name)
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            if name == SELF_FILE:
                continue
            for rule, pattern in FORBIDDEN.items():
                for match in re.finditer(pattern, text):
                    line_no = text.count("\n", 0, match.start()) + 1
                    findings.append({"file": os.path.join(directory, name), "rule": rule,
                                     "line": line_no, "matched": match.group(0)[:60]})
    result = {"ok": not findings, "scanned_files": scanned, "findings": findings,
              "note": "静态扫描：只证明源码文本不含上述模式，不能证明运行时网络行为或平台能力"}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if not findings else 10


if __name__ == "__main__":
    sys.exit(main())
