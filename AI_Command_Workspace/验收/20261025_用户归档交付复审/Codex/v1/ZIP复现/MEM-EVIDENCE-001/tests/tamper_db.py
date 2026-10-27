"""故障注入子进程：直接改写本地测试库，用于验证 verify-store 的检测边界。

用法：python tests/tamper_db.py --store <库路径> --mode payload|digest|identity

说明（重要）：evidence_record 带 BEFORE UPDATE 触发器禁止改写（append-only）。
本脚本先 DROP 该触发器，模拟"已具备库文件写权限的攻击者"；这是检测边界演示，
不代表正常调用路径可以改写历史。普通哈希也无法抵御能重写整个库及全部可信摘要的攻击者。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", required=True)
    parser.add_argument("--mode", required=True, choices=("payload", "digest", "identity"))
    parser.add_argument("--record-id", default=None)
    args = parser.parse_args()

    conn = sqlite3.connect(args.store)
    conn.execute("DROP TRIGGER IF EXISTS trg_evidence_no_update")
    row = conn.execute("SELECT * FROM evidence_record ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        print(json.dumps({"ok": False, "reason": "no record to tamper"}))
        return 1
    cols = [d[0] for d in conn.execute("SELECT * FROM evidence_record LIMIT 1").description]
    record = dict(zip(cols, row))
    rid = args.record_id or record["record_id"]

    if args.mode == "payload":
        payload = json.loads(record["payload_json"])
        payload["amounts"]["closing"] = "999999.99"  # 篡改业务值，摘要随之不匹配
        conn.execute("UPDATE evidence_record SET payload_json=? WHERE record_id=?",
                     (json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")), rid))
    elif args.mode == "digest":
        conn.execute("UPDATE evidence_record SET payload_sha256=? WHERE record_id=?",
                     ("0" * 64, rid))
    elif args.mode == "identity":
        conn.execute("UPDATE evidence_record SET company_id=? WHERE record_id=?",
                     ("tampered-company", rid))
    conn.commit()
    print(json.dumps({"ok": True, "mode": args.mode, "record_id": rid,
                      "note": "append-only 触发器已临时移除以模拟库文件级篡改"},
                     ensure_ascii=False))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
