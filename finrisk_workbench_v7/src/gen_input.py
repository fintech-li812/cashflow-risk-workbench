"""生成确定性合成输入台账（config.company.note 已声明为合成演示数据）。

random.seed 固定 -> 重复运行产生完全相同的文件，可与 require_input_hash 对拍。
故意注入四类缺陷，供数据质量评分与"判断受限"分支真实触发：
缺关键字段 / 过期(record_date 超出 freshness_days) / 重复 collection_id / 未通过核验。
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta

from common import (INPUT, CHANGES, DATA, ROOT, load_config, parse_date,
                    week_start, write_json)

rnd = random.Random(20261019)

COUNTERPARTIES = [
    ("北方智造", "AR"), ("华鑫电子", "AR"), ("宏图汽配", "AR"), ("长江物流", "AR"),
    ("蓝海重工", "AR"), ("锦绣软件", "AR"), ("天工模具", "AR"), ("瑞泰新材料", "AR"),
    ("中恒机电", "AR"), ("远大百货", "AR"),
]

VERIFY_MIX = (
    ["verified_bank"] * 10 + ["verified_voucher"] * 8
    + ["manual"] * 3 + ["sampling_failed"] * 2 + ["pending"] * 2
)


def gen_collections(base: date, weeks: int) -> list[dict]:
    rows = []
    rid = 0
    for k in range(1, weeks + 1):
        ws = week_start(base, k)
        n = rnd.choice([3, 3, 4])
        for j in range(n):
            rid += 1
            cp = rnd.choice(COUNTERPARTIES)[0]
            promised = ws + timedelta(days=rnd.randint(0, 6))
            rows.append({
                "collection_id": f"COL-{k:02d}-{j+1:02d}",
                "counterparty": cp,
                "category": rnd.choice(["货款", "货款", "服务费", "质保金"]),
                "amount": round(rnd.uniform(18.0, 42.0), 2),
                "promised_week": str(k),
                "promised_date": promised.isoformat(),
                "actual_received_date": "",
                "verify_status": rnd.choice(VERIFY_MIX),
                "record_date": (base - timedelta(days=rnd.randint(0, 30))).isoformat(),
                "source_doc": f"INV-{2026_0000 + rid}",
            })

    # --- 缺陷注入（确定性）---
    # 1) 缺关键字段：amount / promised_week / promised_date
    for idx in (2, 17, 33):
        rows[idx]["amount"] = ""
    rows[9]["promised_week"] = ""
    rows[26]["promised_date"] = ""
    # 2) 过期：record_date 早于 base - freshness_days
    stale = (base - timedelta(days=58)).isoformat()
    for idx in (5, 12, 22, 38):
        rows[idx]["record_date"] = stale
    # 3) 重复 collection_id
    rows.append(dict(rows[3]))
    rows.append(dict(rows[21]))
    # 4) 大额关键回款缺 promised_week -> 触发 missing_critical_collection_rows
    rows[14]["promised_week"] = ""
    rows[14]["amount"] = 39.5
    rows[14]["promised_date"] = week_start(base, 2).isoformat()
    return rows


def gen_payments(base: date, weeks: int) -> list[dict]:
    rows = []
    # 供应商货款：每周 4 笔，合计 ~93 万
    for k in range(1, weeks + 1):
        ws = week_start(base, k)
        for j in range(4):
            rows.append({
                "payment_id": f"PAY-{k:02d}-S{j+1}",
                "payee": rnd.choice(["东方钢构", "鑫源原料", "联合包装", "恒通化工", "精工零件"]),
                "category": "supplier",
                "amount": round(rnd.uniform(16.0, 30.0), 2),
                "due_date": (ws + timedelta(days=rnd.randint(0, 6))).isoformat(),
                "due_week": str(k),
                "recurrence": "none",
                "verify_status": "voucher_pass",
                "memo": "应付账款到期",
            })
    # 周期性刚性支出
    recurring = [
        ("salary", "人力成本（含税前工资）", 68.0, "monthly", (4, 9, 13)),
        ("rent", "厂房与办公租金", 12.0, "monthly", (2, 6, 10)),
        ("tax", "增值税及附加", 60.0, "quarterly", (6,)),
        ("interest", "银行贷款利息", 9.0, "quarterly", (3, 12)),
    ]
    for cat, payee, amt, rec, wks in recurring:
        for k in wks:
            rows.append({
                "payment_id": f"PAY-{k:02d}-{cat.upper()[:3]}",
                "payee": payee, "category": cat, "amount": amt,
                "due_date": week_start(base, k).isoformat(), "due_week": str(k),
                "recurrence": rec, "verify_status": "voucher_pass", "memo": "刚性支出",
            })
    # 资本性支出：两笔大额（其中一笔超过 major_payment_threshold_wan=40）
    for k, amt, note in ((3, 45.0, "设备采购尾款（重大付款，需日级拆分）"),
                         (10, 28.0, "模具开发款")):
        rows.append({
            "payment_id": f"PAY-{k:02d}-CAPEX", "payee": "精密设备供应商",
            "category": "capex", "amount": amt,
            "due_date": week_start(base, k).isoformat(), "due_week": str(k),
            "recurrence": "none", "verify_status": "pending", "memo": note,
        })
    for k, amt in ((7, 12.0), (11, 5.0)):
        rows.append({
            "payment_id": f"PAY-{k:02d}-LOG", "payee": "中远物流", "category": "logistics",
            "amount": amt, "due_date": week_start(base, k).isoformat(), "due_week": str(k),
            "recurrence": "none", "verify_status": "voucher_pass", "memo": "运费月结",
        })
    return rows


def gen_history() -> list[dict]:
    """仅 8 个月历史 -> 少于 dynamic_threshold.min_history_months=12 -> 强制静态阈值。"""
    rows = []
    cash = 240.0
    for i, ym in enumerate(["2026-02", "2026-03", "2026-04", "2026-05",
                            "2026-06", "2026-07", "2026-08", "2026-09"]):
        inflow = round(rnd.uniform(470.0, 540.0), 2)
        outflow = round(rnd.uniform(455.0, 545.0), 2)
        closing = round(cash + inflow - outflow, 2)
        rows.append({
            "month": ym, "opening_cash": cash, "total_inflow": inflow,
            "total_outflow": outflow, "closing_cash": closing,
            "collection_delay_days_actual": str(rnd.randint(-4, 18)),
            "ar_turnover_days_actual": str(rnd.randint(55, 72)),
        })
        cash = closing
    return rows


def gen_accuracy() -> list[dict]:
    """周度预测 vs 实际：故意让命中率落在 accuracy_threshold 以下，驱动参数自修正分支。"""
    rows = []
    # (预测, 实际, 预测等级, 实际等级)
    pairs = [
        (258.0, 255.4, "green", "green"), (251.2, 249.8, "green", "green"),
        (244.0, 231.5, "green", "green"), (239.6, 238.9, "green", "yellow"),
        (228.0, 214.7, "yellow", "yellow"), (241.5, 219.0, "yellow", "yellow"),
        (233.8, 208.2, "yellow", "yellow"), (219.0, 226.4, "red", "yellow"),
        (212.4, 205.1, "yellow", "yellow"), (207.9, 178.3, "yellow", "red"),
    ]
    for i, (f, a, lp, la) in enumerate(pairs, 1):
        rows.append({
            "period": f"W{i:02d}", "forecast_closing_cash": f,
            "actual_closing_cash": a, "level_predicted": lp, "level_actual": la,
        })
    return rows


def gen_credit() -> list[dict]:
    rows = []
    for cp, _ in COUNTERPARTIES[:6]:
        line = round(rnd.uniform(80.0, 260.0), 2)
        drawn = round(line * rnd.uniform(0.25, 0.65), 2)
        rows.append({
            "counterparty": cp, "credit_line_wan": line, "drawn_wan": drawn,
            "available_wan": round(line - drawn, 2),
            "committed": rnd.choice(["yes", "yes", "no"]),
        })
    # 银行授信（S2 授信压降的作用对象）
    rows.append({"counterparty": "工商银行-综合授信", "credit_line_wan": 400.0,
                 "drawn_wan": 150.0, "available_wan": 250.0, "committed": "yes"})
    rows.append({"counterparty": "招商银行-流贷额度", "credit_line_wan": 180.0,
                 "drawn_wan": 60.0, "available_wan": 120.0, "committed": "yes"})
    return rows


def gen_change_requests() -> list[dict]:
    """变更申请台账：一条合规双签（角色不同），一条单签不合规。"""
    return [
        {
            "change_request_id": "CR-2026-001",
            "target_key": "industry_deviation_watch_ratio",
            "current_value": 0.3, "proposed_value": 0.26,
            "status": "approved", "approved_at": "2026-10-15",
            "signer_a": {"name": "赵敏", "role": "财务总监"},
            "signer_b": {"name": "孙立", "role": "风控负责人"},
            "basis": "季度行业偏离复盘，P25 口径校准",
        },
        {
            "change_request_id": "CR-2026-002",
            "target_key": "stress_params.collection_delay_days",
            "current_value": 30, "proposed_value": 10,
            "status": "pending", "approved_at": None,
            "signer_a": {"name": "李文博", "role": "资金部经理"},
            "signer_b": None,
            "basis": "希望调低压力情景强度",
        },
    ]


def gen_overrides() -> list[dict]:
    """外部覆盖尝试：混合合规与越权，交由 rule_gate 逐条裁决。"""
    return [
        {"target_key": "industry_deviation_watch_ratio", "proposed_value": 0.26,
         "change_request": "CR-2026-001", "actor": "孙立",
         "reason": "已批准变更申请，双签角色不同"},
        {"target_key": "stress_params.collection_delay_days", "proposed_value": 10,
         "change_request": "CR-2026-002", "actor": "李文博",
         "reason": "变更申请仅单签且状态 pending，未获批准"},
        {"target_key": "data_quality.limited_judgment_score_below", "proposed_value": 70.0,
         "change_request": None, "actor": "未知会话",
         "reason": "无变更申请直接压低受限阈值"},
        {"target_key": "cash_buffer_red_wan", "proposed_value": 60.0,
         "change_request": None, "actor": "演示脚本",
         "reason": "命中 industry_protected_suffixes，试图下调红色缓冲线"},
    ]


def main() -> None:
    cfg = load_config()
    base = parse_date(cfg["base_date"])
    weeks = cfg["forecast"]["cashflow_weeks"]

    datasets = {
        "collections.csv": gen_collections(base, weeks),
        "payments.csv": gen_payments(base, weeks),
        "history_months.csv": gen_history(),
        "forecast_accuracy.csv": gen_accuracy(),
        "counterparty_credit.csv": gen_credit(),
        "opening_balance.csv": [
            {"scope": "available", "amount_wan": cfg["opening_cash"]["available"],
             "as_of": cfg["base_date"], "note": "可自由动用，计入现金缓冲"},
            {"scope": "restricted", "amount_wan": cfg["opening_cash"]["restricted"],
             "as_of": cfg["base_date"], "note": "受限资金（保证金等），不计入现金缓冲"},
            {"scope": "purpose_restricted", "amount_wan": cfg["opening_cash"]["purpose_restricted"],
             "as_of": cfg["base_date"], "note": "专款专用，不计入现金缓冲"},
        ],
    }
    INPUT.mkdir(parents=True, exist_ok=True)
    for name, rows in datasets.items():
        path = INPUT / name
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"  写入 {path.relative_to(ROOT)}  ({len(rows)} 行)")

    CHANGES.mkdir(parents=True, exist_ok=True)
    write_json(CHANGES / "change_requests.json", gen_change_requests())
    write_json(DATA / "overrides.json", gen_overrides())
    print(f"  写入 {Path('changes/change_requests.json')}")
    print(f"  写入 {Path('data/overrides.json')}")


if __name__ == "__main__":
    main()
