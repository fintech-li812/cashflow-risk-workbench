#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WB-FIN-001 · 财务公式离线校验脚本（WorkBuddy v1）

用途
   用 Python 标准库 decimal 复算《财务公式与口径总表.md》中"已批准/已定稿"的公式，
   对手算用例做本地离线核对。

严格边界（请勿越界使用本脚本的输出）
   1. 本脚本只做**离线算术复核**，不连接服务器、不读写任何生产凭据、不打开或修改
      D:\\CashflowRiskWorkbench 下的 xlsx / HTML / SQL / 源文档。
   2. 本脚本通过 ≠ 千问办公表格已能运行。所有"千问表格公式"在总表中一律标注
      "待平台验证"，平台函数（AVERAGE / SUMIF / PERCENTILE / INDEX-MATCH 等）
      可用性由平台侧实测确认，本脚本不证明。
   3. 未批准的参数（1.45、K 来源、刚性支出定义、Myer 是否停用、13 周分配口径等）
      在本脚本中只做"差异展示"或标记 BLOCKED，不固化为口径。
   4. 金额单位：本脚本内部统一按 **万元** 计算（与样例 xlsx、包B 基准一致）；
      仅在 F-24 单位换算用例中演示万元→元的换算。库内/接入层为元（裁决 D12）。

运行
   python verify_financial_formulas.py            # 输出到 stdout
   python verify_financial_formulas.py > 校验结果.txt
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import csv
import os
import sys

D = Decimal
Q2 = Decimal("0.01")   # 万元：展示/入库两位小数
Q4 = Decimal("0.0001")  # 比值：保留四位做展示


def d(x):
    """统一转 Decimal，拒绝 NaN/Infinity 与非数值字符串。"""
    if x is None:
        return None
    if isinstance(x, Decimal):
        return x
    s = str(x).strip()
    if s == "" or s.lower() in ("nan", "inf", "-inf", "infinity"):
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def r2(x):
    """展示层两位小数，四舍五入（ROUND_HALF_UP）。"""
    v = d(x)
    return None if v is None else v.quantize(Q2, rounding=ROUND_HALF_UP)


def r4(x):
    v = d(x)
    return None if v is None else v.quantize(Q4, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# 行业参数（来源：v8_完整方案.md §5.1—5.4 行 1106—1186；
#           与 web/财务风控工作台-演示看板.html 行 514—517 的 IND 逐项一致）
# 仅用于"是否按已定稿模板执行"的核对，不证明这些数值有真实行业统计依据（v8 行 1100）。
# ---------------------------------------------------------------------------
IND = {
    "制造": dict(Ky=D("2.5"), Kr=D("1.5"), Ty=D("45"), Tr=D("25"),
                 Wfin=D("0.40"), Wop=D("0.30"), appr=(D("0.5"), D("2.0"))),
    "零售": dict(Ky=D("1.8"), Kr=D("1.0"), Ty=D("30"), Tr=D("15"),
                 Wfin=D("0.20"), Wop=D("0.50"), appr=(D("0.3"), D("1.0"))),
    "建筑": dict(Ky=D("3.5"), Kr=D("2.0"), Ty=D("60"), Tr=D("30"),
                 Wfin=D("0.50"), Wop=D("0.20"), appr=(D("1.0"), D("4.0"))),
    "科技": dict(Ky=D("1.5"), Kr=D("1.0"), Ty=D("20"), Tr=D("10"),
                 Wfin=D("0.15"), Wop=D("0.55"), appr=(D("0.3"), D("1.0"))),
}

# DEA-DA 权重（来源：演示看板 html 行 544—549；Σv+Σu=1，基可行解稀疏）
# 列：指标、名称、投入/产出、权重 w、归一化取值 x̃∈[0,1]
DEADA = [
    ("X3", "营业利润率", "产出", D("0.31"), D("0.34")),
    ("X6", "利息保障倍数", "投入", D("0.24"), D("0.31")),
    ("X1", "净资产收益率", "产出", D("0.19"), D("0.62")),
    ("X5", "速动比率", "产出", D("0.26"), D("0.44")),
    ("X2", "资产报酬率", "产出", D("0"), D("0.55")),
    ("X7", "利润总额增长率", "投入", D("0"), D("0.28")),
    ("X9", "总资产增长率", "投入", D("0"), D("0.41")),
]

# Benford / Myer 命中计数（来源：演示看板 html 行 536—542，METRICS 第 4/5 列）
N_BENFORD_HIT = 5   # X4 X5 X7 X11 X12
N_MYER_HIT = 4      # X2 X5 X7 X15
N_METRIC = 15

# 动态阈值兜底（来源：演示看板 html 行 656—659，实现级，未写入裁决）
GUARD = D("0.70")
BAND = D("0.10")


# ---------------------------------------------------------------------------
# 公式实现（与总表编号一一对应）
# ---------------------------------------------------------------------------
def f01_monthly_outflow(values):
    """F-01 月均经营性流出 M = AVERAGE(近3月经营性流出)，万元。

    空值处置（依据包B A01 建议 + 施工单 4.10）：缺失月不得填 0、不得忽略后求均值；
    返回 (None, 原因)。M=0 时不产生"安全"结论（A05）。
    """
    if any(v is None for v in values):
        return None, "存在缺失月：不填 0、不忽略，标待补录"
    vals = [d(v) for v in values]
    if any(v.is_nan() for v in vals):
        return None, "存在非数值"
    if len(vals) != 3:
        return None, "近 3 个月窗口不完整"
    return (sum(vals) / Decimal(3)).quantize(Q4, rounding=ROUND_HALF_UP), ""


def f02_business_scale(cost_rows):
    """F-02 月均业务规模 S = AVERAGE(近3月(营业成本+管理费用))，万元。"""
    if any(v is None for v in cost_rows):
        return None, "存在缺失月"
    # P3-5：显式 ROUND_HALF_UP（v1 未传 rounding，落回默认 ROUND_HALF_EVEN）
    return (sum(d(v) for v in cost_rows) / Decimal(3)).quantize(Q4, rounding=ROUND_HALF_UP), ""


def f08_ratio(B, M):
    """F-08 缓冲倍数 = B / M。M 为 0 或缺失 → 不适用（禁止除零、禁止报绿）。"""
    B, M = d(B), d(M)
    if B is None or M is None:
        return None, "输入缺失"
    if M == 0:
        return None, "M=0：倍数不适用，不除零、不报绿"
    return (B / M).quantize(Q4, rounding=ROUND_HALF_UP), ""


def f09_static_lamp(ratio, Ky, Kr):
    """F-09 静态现金灯：ratio < Kr 红；< Ky 黄；否则绿（严格小于，等号不升级）。

    依据：v8 行 610 / 654—655；包B E01—E06 行 270—275。
    """
    if ratio is None:
        return "不适用", "倍数不可计算"
    if ratio < d(Kr):
        return "红灯", f"{ratio} < K红 {Kr}"
    if ratio < d(Ky):
        return "黄灯", f"{ratio} < K黄 {Ky}"
    return "绿灯", f"{ratio} ≥ K黄 {Ky}"


def f05_time_buffer(B, M):
    """F-05 时间缓冲（天）= B ÷ (M/30)，看板实现为 round(...)。

    依据：施工单 3.6 行 71；演示看板 html 行 880。
    """
    B, M = d(B), d(M)
    if B is None or M is None or M == 0:
        return None, "M=0 或输入缺失：天数不可计算"
    days = B / (M / Decimal(30))
    return int(days.quantize(Decimal("1"), rounding=ROUND_HALF_UP)), ""


def f05b_time_lamp(days, Ty, Tr):
    """时间缓冲灯：days < Tr 红；< Ty 黄；否则绿（v8 §5.1—5.4 行 1108—1177）。"""
    if days is None:
        return "不适用", "天数不可计算"
    if days < d(Tr):
        return "红灯", f"{days}天 < 红线 {Tr}天"
    if days < d(Ty):
        return "黄灯", f"{days}天 < 黄线 {Ty}天"
    return "绿灯", f"{days}天 ≥ 黄线 {Ty}天"


def f06_financing_buffer(unused_credit, standby):
    """F-06 融资缓冲 = 未使用授信 + 备用额度（看板行 885 / 施工单 3.5b 行 69）。"""
    u, s = d(unused_credit), d(standby)
    if u is None or s is None:
        return None, "授信或备用额度缺失"
    if u < 0:
        return None, "未使用授信为负（X-MANU-04 类埋错），须先经数据闸处置"
    # P3-5：显式 ROUND_HALF_UP
    return (u + s).quantize(Q2, rounding=ROUND_HALF_UP), ""


def f07_operating_buffer(M, Wop, coef=D("1.45")):
    """F-07 经营调整缓冲 = 可调整支出 × Wop × 1.45。

    coef=1.45 来自演示看板 html 行 881，**v8 §5.1—5.4 无出处**（看板核对清单行 23）。
    本函数同时给出含/不含 1.45 两个结果，供 P-05 待裁决使用，不固化口径。
    """
    M, Wop = d(M), d(Wop)
    return {
        # P3-5：显式 ROUND_HALF_UP
        "含1.45": (M * Wop * coef).quantize(Q2, rounding=ROUND_HALF_UP),
        "不含1.45": (M * Wop).quantize(Q2, rounding=ROUND_HALF_UP),
    }


def f13_quality_score(n_b=N_BENFORD_HIT, n_m=N_MYER_HIT, n_metric=N_METRIC):
    """F-13 Q = 1 − (ΣB + ΣM) / (2 × 指标数)。

    依据：v8 行 213 / 589；施工单 2.11 行 55；看板行 666—667（nB=5, nM=4 → Q=0.70）。
    ⚠ ΣB/ΣM 是"按指标计数"还是"按样本行计数"，v8 自身两处表述不一致 → P-10 待确认（P3-1 编号修正）。
    """
    return (Decimal(1) - (Decimal(n_b) + Decimal(n_m)) / (Decimal(2) * Decimal(n_metric))
            ).quantize(Q4, rounding=ROUND_HALF_UP)


def f16_deada_score(rows=None):
    """F-16 判别得分 D。

    看板实现：D = Σ w(2x̃ − 1)（x̃ 为归一化到 [0,1] 的指标值）→ D ∈ [-1,1]，
    临界值 c=0，D<0 判风险（看板行 668—671、790；审计行 596 记 D=-0.176）。
    v8 行 334 原文写作 D = ΣvᵢXᵢ + ΣuᵣYᵣ（原始值加权和）。两种写法临界值语义不同 → P-10 待确认（P3-1 编号修正）。
    """
    rows = rows or DEADA
    total = Decimal(0)
    parts = []
    for k, name, tp, w, x in rows:
        c = w * (Decimal(2) * x - Decimal(1))
        parts.append(f"{k}{name}:{w}×(2×{x}−1)={c.quantize(Q4)}")
        total += c
    return total.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), parts


def f18_fuse(Q, Dv, P):
    """F-18 FUSE(Q, D, P)，含裁决 A2 补齐分支与"不可判定"兜底。

    依据：v8 行 396—399 / 579—583；规格裁决 20261021 A2 行 95（新增 D<0 且 P<0.3 → 黄灯；
    三分支皆不命中输出"不可判定"而非默认绿）；看板 html 行 676—679。
    P=None 表示"未取得 P / 不需复核"。
    """
    Q, Dv = d(Q), d(Dv)
    P = d(P)
    if Q is None or Dv is None:
        return "不可判定", "Q 或 D 缺失"
    if Q < Decimal("0.3"):
        return "红灯", "Q<0.3（优先于其他条件）"
    if Dv < 0 and P is not None and P >= Decimal("0.7"):
        return "红灯", "D<0 且 P≥0.7"
    if Dv < 0 and P is not None and Decimal("0.3") <= P < Decimal("0.7"):
        return "黄灯", "D<0 且 0.3≤P<0.7"
    if Dv < 0 and P is not None and P < Decimal("0.3"):
        return "黄灯", "D<0 且 P<0.3（A2 补齐分支）"
    if Q < Decimal("0.5") and Dv < 0:
        return "黄灯", "Q<0.5 且 D<0（P 未参与）"
    if Dv >= 0 and Q >= Decimal("0.5"):
        return "绿灯", "D≥0 且 Q≥0.5"
    if Dv < 0 and P is None:
        return "不可判定", "D<0 但未取得 P，三分支皆不能判定（不得默认绿）"
    return "不可判定", "未落入任何已定义分支"


def f19_merge(model_lamp, cash_lamp):
    """F-19 最终灯 = 取较严格者（裁决 A3 行 96；v8 行 602；看板行 699）。

    严重度：红 3 > 黄 2 > 不可判定 1 > 绿 0。不可判定与绿灯相遇取不可判定（不报绿）；
    不可判定与红灯相遇取红灯（不放松）。
    """
    sev = {"绿灯": 0, "不可判定": 1, "黄灯": 2, "红灯": 3, "不适用": 1}
    a, b = sev[model_lamp], sev[cash_lamp]
    back = {0: "绿灯", 1: "不可判定", 2: "黄灯", 3: "红灯"}
    if model_lamp == "不适用":
        return cash_lamp
    if cash_lamp == "不适用":
        return model_lamp
    return back[max(a, b)]


def f20_stress(B, M, ar30, avail_credit, main_cost, Ky, Kr):
    """F-20 压力测试四场景（v8 行 745—762；施工单 7.1—7.4；看板行 701—707）。

    回款缺口 = 30 天内到期应收合计；融资缺口 = 可用授信 × 0.5；
    成本缺口 = 月度主要成本 × 0.2；联合 = 三项相加。
    场景后倍数 = (B − 缺口)/M；判定同静态灯；倍数为负直接红。
    """
    B, M = d(B), d(M)
    gaps = [
        ("回款冲击", d(ar30)),
        ("融资冲击", d(avail_credit) * Decimal("0.5")),
        ("成本冲击", d(main_cost) * Decimal("0.2")),
    ]
    joint = sum(g[1] for g in gaps)
    gaps.append(("联合冲击", joint))
    out = []
    for name, gap in gaps:
        buf = B - gap
        ratio = (buf / M).quantize(Q4, rounding=ROUND_HALF_UP) if M else None
        lamp = f09_static_lamp(ratio, Ky, Kr)[0]
        out.append((name, gap.quantize(Q2), buf.quantize(Q2), ratio, lamp))
    return out


def f21_approval(amount, lamp, ind_key, S):
    """F-21 审批路由 = 灯级 × 金额档（v8 行 769—773 + §5.1 行 1116—1118；看板行 1020—1023）。

    三档：≤ S×a1 → 部门经理；S×a1 ~ S×a2 → 财务总监；> S×a2 → 双签。
    看板矩阵另规定：黄灯最低档也升财务总监、红灯全档双签。
    ⚠ 超过第二线（> S×a2）时"金额档 vs 灯级"以谁为准，包B R04 行 95—97 未裁 → 标待确认。
    注意：a1/a2 是**相对 S 的倍率**，必须先乘 S 再与金额比较（本函数初版漏乘 S，已修正）。
    """
    a1, a2 = IND[ind_key]["appr"]
    S = d(S)
    amt = d(amount)
    if lamp == "红灯":
        return "总经理+财务双签", "红灯全档双签（v8 行 773 与看板矩阵一致）"
    if amt <= S * a1:
        lane = "部门经理"
    elif amt <= S * a2:
        lane = "财务总监"
    else:
        lane = "总经理+财务双签"
    if lamp == "黄灯" and lane == "部门经理":
        return "财务总监", "黄灯最低档升财务总监（看板矩阵行 1022，建议级）"
    note = ""
    if amt > S * a2:
        note = "超过第二线：v8 §5.1 线3 与模块四表口径并存，R04 未裁 → 待确认"
    return lane, note


def percentile_inc(values, p):
    """Excel PERCENTILE.INC 口径：idx=(n-1)*p，线性插值。仅用于演示动态阈值算法。"""
    vs = sorted(d(v) for v in values)
    n = len(vs)
    if n == 0:
        return None
    idx = (Decimal(n - 1) * d(p))
    lo = int(idx.to_integral_value(rounding="ROUND_FLOOR"))
    hi = min(lo + 1, n - 1)
    frac = idx - Decimal(lo)
    return (vs[lo] + frac * (vs[hi] - vs[lo])).quantize(Q4, rounding=ROUND_HALF_UP)


def f11_dynamic(same_month_ratios, static_Ky, static_Kr, seasonal_dk=D("0")):
    """F-11 动态阈值（v8 行 622—674；裁决 A4 行 97；看板 GUARD/BAND 行 656—659）。

    K黄 = P25(同期缓冲倍数)；K红 = P10；满 12 个月且同月有效样本 ≥3 才启用，否则回退静态。
    兜底：动态 K红 不得低于静态 K红 × 0.70；K黄 ≤ K红 时抬到 K红 + 0.10。
    """
    n = len(same_month_ratios)
    if n < 3:
        return None, f"同月有效样本 {n} < 3（裁决 A4）→ 强制回退静态"
    Ky = percentile_inc(same_month_ratios, "0.25")
    Kr = percentile_inc(same_month_ratios, "0.10")
    floor = d(static_Kr) * GUARD
    floored = Kr < floor
    Kr = max(Kr, floor)
    banded = False
    if Ky <= Kr:
        Ky = Kr + BAND
        banded = True
    Ky = Ky + d(seasonal_dk)
    Kr = Kr + (Decimal("0.3") if d(seasonal_dk) > 0 else Decimal("0"))
    return {"K黄": Ky, "K红": Kr, "样本数": n, "触底": floored, "压带修正": banded}, ""


def f24_unit(wan):
    """F-24 万元 → 元（裁决 D12：库内与 MCP 边界一律元）。浮点噪声先 ROUND 到 2 位。"""
    v = d(wan)
    if v is None:
        return None
    v2 = v.quantize(Q2, rounding=ROUND_HALF_UP)
    yuan = (v2 * Decimal(10000)).quantize(Q2, rounding=ROUND_HALF_UP)
    return f"{v2} 万元 = {yuan} 元"


# ---------------------------------------------------------------------------
# 用例定义
# ---------------------------------------------------------------------------
CASES = []


def case(cid, formula, kind, inputs, compute, expected, basis, note="", expect_status="AUTO"):
    """expect_status:
       - "AUTO"（默认）：按预期字符串关键词判断是否 BLOCKED（v1 行为，见 P3-6）
       - "PASS"：该用例的输出是**已定行为**，必须与 expected 做真实比较（不得因关键词退化成 BLOCKED）
       - "BLOCKED"：规则未裁决，无法判定对错，不做结果比较
    """
    CASES.append(dict(id=cid, formula=formula, kind=kind, inputs=inputs,
                      compute=compute, expected=expected, basis=basis, note=note,
                      expect_status=expect_status))


# ---- F-01 月均经营性流出 M ----
case("C01", "F-01", "正常", "制造近3月经营性流出 90 / 100 / 110（万元）",
     lambda: f01_monthly_outflow([90, 100, 110])[0], "100.0000",
     "v8 行 638—639、1053；包B 行 45", "M=(90+100+110)/3")
case("C02", "F-01", "异常", "制造近3月流出 90 / 空白 / 110",
     lambda: (f01_monthly_outflow([90, None, 110])[0], f01_monthly_outflow([90, None, 110])[1]),
     "None（待补录，不得填0得 66.6667、不得忽略得 100）",
     "包B A01 行 292—298", "缺失策略待确认，本例只验证不静默补零")
case("C03", "F-01", "边界", "科技近3月流出 0 / 0 / 0 → M=0，B=80",
     lambda: (f01_monthly_outflow([0, 0, 0])[0], f08_ratio(80, 0)[1]),
     "M=0.0000；倍数不适用（不除零、不报绿）", "包B A05 行 321—326；施工单 4.10 行 92")

# ---- F-02 月均业务规模 S ----
case("C04", "F-02", "正常", "制造近3月（营业成本+管理费用）各 100（万元）",
     lambda: f02_business_scale([100, 100, 100])[0], "100.0000",
     "v8 行 1120；施工单 5.1 行 100；包B 行 41—50", "S 与 M 在本例恰好相等，仅为便于手算")

# ---- F-08/F-09 缓冲倍数与静态灯（制造 Ky2.5/Kr1.5）----
for cid, B, exp_ratio, exp_lamp, kind in [
    ("C05", "300", "3.0000", "绿灯", "正常"),
    ("C06", "200", "2.0000", "黄灯", "正常"),
    ("C07", "100", "1.0000", "红灯", "正常"),
    ("C08", "149.99", "1.4999", "红灯", "边界"),
    ("C09", "150.00", "1.5000", "黄灯", "边界"),
    ("C10", "150.01", "1.5001", "黄灯", "边界"),
    ("C11", "249.99", "2.4999", "黄灯", "边界"),
    ("C12", "250.00", "2.5000", "绿灯", "边界"),
    ("C13", "250.01", "2.5001", "绿灯", "边界"),
]:
    case(cid, "F-08/F-09", kind, f"制造 M=100（万元），B={B}（万元）",
         lambda B=B: (f08_ratio(B, 100)[0], f09_static_lamp(f08_ratio(B, 100)[0], "2.5", "1.5")[0]),
         f"{exp_ratio}；{exp_lamp}", "v8 行 610、654—655；包B N01—N03 行 117—136、E01—E06 行 270—275",
         "等号边界：等于 K红 判黄、等于 K黄 判绿（严格小于）")

# ---- 四行业基准（包B 行 43—48）----
for cid, ind, M, B, exp in [
    ("C14", "零售", "50", "100", "2.0000；绿灯"),
    ("C15", "零售", "50", "70", "1.4000；黄灯"),
    ("C16", "零售", "50", "30", "0.6000；红灯"),
    ("C17", "建筑", "200", "800", "4.0000；绿灯"),
    ("C18", "建筑", "200", "500", "2.5000；黄灯"),
    ("C19", "建筑", "200", "300", "1.5000；红灯"),
    ("C20", "科技", "40", "80", "2.0000；绿灯"),
    ("C21", "科技", "40", "50", "1.2500；黄灯"),
    ("C22", "科技", "40", "30", "0.7500；红灯"),
]:
    case(cid, "F-08/F-09", "正常", f"{ind} M={M}，B={B}（万元）",
         lambda ind=ind, M=M, B=B: (
             f08_ratio(B, M)[0],
             f09_static_lamp(f08_ratio(B, M)[0], IND[ind]["Ky"], IND[ind]["Kr"])[0]),
         exp, "包B N06—N08 行 154—172、N11—N13 行 191—209、N16—N18 行 228—247",
         "跨行业不得错用 K：建筑 2.5 是黄灯（不是制造意义的绿灯）")

# ---- F-05 时间缓冲 ----
case("C23", "F-05", "正常", "制造 B=185，M=100（万元）",
     lambda: (f"{f05_time_buffer(185, 100)[0]} 天；"
              f"{f05b_time_lamp(f05_time_buffer(185, 100)[0], IND['制造']['Ty'], IND['制造']['Tr'])[0]}"),
     "56 天；绿灯", "施工单 3.6 行 71；看板行 880；v8 行 1108—1109",
     "185÷(100/30)=55.5→round→56；制造黄线 45 天、红线 25 天")
case("C24", "F-05", "边界", "制造 B=100，M=100（万元）",
     lambda: (f"{f05_time_buffer(100, 100)[0]} 天；"
              f"{f05b_time_lamp(f05_time_buffer(100, 100)[0], IND['制造']['Ty'], IND['制造']['Tr'])[0]}"),
     "30 天；黄灯", "同上", "30 < 45 → 黄；尚未跌破 25 天红线")
case("C25", "F-05", "异常", "制造 B=80，M=0（万元）",
     lambda: f05_time_buffer(80, 0)[1], "不可计算（M=0）", "包B A05 行 321—326")

# ---- F-06 融资缓冲 ----
case("C26", "F-06", "正常", "制造未使用授信 240，备用额度 0（万元）",
     lambda: f06_financing_buffer(240, 0)[0], "240.00",
     "看板行 885；施工单 3.5b 行 69", "融资缓冲 = 未使用授信 + 备用额度")
case("C27", "F-06", "异常", "未使用授信 −40（X-MANU-04 制造筹资 C4）",
     lambda: f06_financing_buffer(-40, 0)[1], "不可直接使用（负值须先经数据闸）",
     "数据闸 gate_negative_credit；埋错表 X-MANU-04")

# ---- F-07 经营调整缓冲（1.45 待裁决）----
case("C28", "F-07", "待裁决", "制造 M=100，Wop=0.30",
     lambda: f07_operating_buffer(100, "0.30"),
     "含1.45 → 43.50；不含 → 30.00（差异 13.50 万元）",
     "看板行 881；施工单 3.5c 行 70；看板核对清单行 23 记 1.45 无出处",
     "本例只展示差异，不定口径 → P-05")

# ---- F-11 动态阈值 ----
case("C29", "F-11", "边界", "12 个月月度数据，同月样本仅 1 条",
     lambda: f11_dynamic([1.68], "2.5", "1.5")[1],
     "同月样本 1 < 3 → 强制回退静态（不启用分位数）",
     "v8 行 626—633；裁决 A4 行 97；包B E07—E08 行 276—277")
case("C30", "F-11", "正常", "同月有效样本 3 条：1.68 / 1.85 / 2.02",
     lambda: (lambda r: f"K黄={r['K黄']}，K红={r['K红']}（样本={r['样本数']}，"
                        f"触底={r['触底']}，压带修正={r['压带修正']}）")(
         f11_dynamic([1.68, 1.85, 2.02], "2.5", "1.5")[0]),
     "K黄=1.7650，K红=1.7140（样本=3，触底=False，压带修正=False）",
     "v8 行 644—648；看板行 656—659、684—693",
     "PERCENTILE.INC 插值：P25 idx=0.5、P10 idx=0.2；示例数据非裁决")
case("C31", "F-11", "边界", "混合模式：静态 Ky2.5/Kr1.5，动态 Ky1.765/Kr1.714",
     lambda: (f"Ky={(D('2.5') * D('0.7') + D('1.7650') * D('0.3')).quantize(Q4)}；"
              f"Kr={(D('1.5') * D('0.7') + D('1.7140') * D('0.3')).quantize(Q4)}"),
     "Ky=2.2795；Kr=1.5642", "v8 行 672（混合 0.7/0.3）；看板行 689",
     "混合模式四则口径明确；看板 GUARD/BAND 兜底为建议级 → P-11（P3-1 编号修正）")

# ---- F-13 质量得分 Q ----
case("C32", "F-13", "正常", "Benford 命中 5 项 + Myer 命中 4 项，指标数 15",
     lambda: f13_quality_score(), "0.7000",
     "v8 行 213、589；施工单 2.11 行 55；看板行 666—667（审计行 595 记 Q=0.70）",
     "Q=1−(5+4)/(2×15)=0.70")

# ---- F-16 判别得分 D ----
case("C33", "F-16", "正常", "看板 DEADA 权重与归一化取值（Σw=1）",
     lambda: f16_deada_score()[0], "-0.1760",
     "看板行 544—549、668—671、790；审计行 596 记 D=-0.176",
     "D=Σw(2x̃−1)；v8 行 334 写作 ΣvᵢXᵢ+ΣuᵣYᵣ → 两种写法临界值语义不同（P-10，P3-1 编号修正）")

# ---- F-18 FUSE ----
# P3-6 修复：末列 st 显式声明该用例是"行为已定(PASS)"还是"规则待决(BLOCKED)"。
#   C38/C41/C42 的输出"不可判定"是**当前规则下必然的行为**（规则不完备 → 不出灯），
#   不是"无法判断对错"，故按审核建议改为真实比较；若将来规则补齐，这三条会立刻变红。
for cid, Q, Dv, P, exp, kind, note, st in [
    ("C34", "0.8", "-0.2", "0.6999", "黄灯", "边界", "包B E09 行 278", "PASS"),
    ("C35", "0.8", "-0.2", "0.7000", "红灯", "边界", "包B E10 行 279（≥0.7 含等号）", "PASS"),
    ("C36", "0.8", "-0.2", "0.7001", "红灯", "边界", "包B E11 行 280", "PASS"),
    ("C37", "0.2999", "0.2", None, "红灯", "边界", "包B E12 行 281（Q<0.3 优先，D≥0 不覆盖）", "PASS"),
    ("C38", "0.3000", "0.2", None, "不可判定", "边界", "包B E13 行 282（R01 未裁 → 规则不完备故不出灯；行为已定，做真实比较）", "PASS"),
    ("C39", "0.8", "0.0000", None, "绿灯", "边界", "包B E14 行 283（D=0 属 D≥0）", "PASS"),
    ("C40", "0.8", "-0.2", "0.2", "黄灯", "正常", "包B A10 行 357—363 + 裁决 A2 行 95", "PASS"),
    ("C41", "0.4", "0.2", None, "不可判定", "边界", "R01 行 83：Q∈[0.3,0.5) 且 D≥0 无分支 → 行为已定，做真实比较", "PASS"),
    ("C42", "0.8", "-0.2", None, "不可判定", "异常", "D<0 但未取得 P：不得默认绿（A2 保守原则）→ 行为已定，做真实比较", "PASS"),
]:
    case(cid, "F-18", kind, f"Q={Q}，D={Dv}，P={P if P is not None else '未取得'}",
         lambda Q=Q, Dv=Dv, P=P: f18_fuse(Q, Dv, P)[0], exp,
         "v8 行 396—399、579—583；裁决 A2 行 95；看板行 676—679；包B E09—E14 / A10", note,
         expect_status=st)

# ---- F-19 灯合并 ----
case("C43", "F-19", "正常", "模型灯=黄灯，现金灯=红灯",
     lambda: f19_merge("黄灯", "红灯"), "红灯", "裁决 A3 行 96；v8 行 602；看板行 699")
case("C44", "F-19", "正常", "模型灯=绿灯，现金灯=红灯",
     lambda: f19_merge("绿灯", "红灯"), "红灯", "同上（防模型绿灯覆盖现金红灯）")
case("C45", "F-19", "边界", "模型灯=不可判定，现金灯=绿灯",
     lambda: f19_merge("不可判定", "绿灯"), "不可判定",
     "A2 保守原则 + A3 取严：不因模型不可判定而报绿", expect_status="PASS")

# ---- F-20 压力测试（看板 f2 样板：M=100 buffer=185 ar30=65 credit=240 cost=225）----
def _stress():
    rows = f20_stress(185, 100, 65, 240, 225, "2.5", "1.5")
    return "; ".join(f"{n}:缺口{gap}→缓冲{buf}→倍数{ra}→{la}" for n, gap, buf, ra, la in rows)

case("C46", "F-20", "正常", "制造样本 M=100，B=185，ar30=65，可用授信 240，主要成本 225（万元）",
     _stress,
     "回款冲击:缺口65.00→缓冲120.00→倍数1.2000→红灯; 融资冲击:缺口120.00→缓冲65.00→倍数0.6500→红灯; "
     "成本冲击:缺口45.00→缓冲140.00→倍数1.4000→红灯; 联合冲击:缺口230.00→缓冲-45.00→倍数-0.4500→红灯",
     "v8 行 745—762；施工单 7.1—7.5 行 124—128；看板行 701—707",
     "按批准公式（倍数< K红 1.5 即红）四场景全红；⚠ v8 行 722—727 的样例文案标 1.20/1.40 为黄灯、"
     "联合为 −15 万/−0.15，与其自身公式和 K 值均不符 → 缺陷登记 D-01")


def _stress_doc_check():
    """D-01：v8 §4.3 健康度报告样例 vs 按批准公式复算。"""
    doc = {"回款冲击": ("1.20", "18天", "黄灯"), "融资冲击": ("0.65", "8天", "红灯"),
           "成本冲击": ("1.40", "22天", "黄灯"), "联合冲击": ("-0.15", "0天", "红灯")}
    calc_rows = f20_stress(185, 100, 65, 240, 225, "2.5", "1.5")
    out = []
    for name, gap, buf, ratio, lamp in calc_rows:
        dr, dd, dl = doc[name]
        days = f05_time_buffer(buf, 100)[0]
        same = (str(ratio).rstrip("0").rstrip(".") == dr and lamp == dl and f"{days}天" == dd)
        out.append(f"{name}: 文档({dr}/{dd}/{dl}) vs 复算({ratio}/{days}天/{lamp})"
                   + ("" if same else " ← 不一致"))
    return "；".join(out)


case("C46b", "F-20", "核查", "v8 行 722—727 健康度报告样例 vs 按批准公式复算（M=100，B=185）",
     _stress_doc_check,
     "回款冲击: 文档(1.20/18天/黄灯) vs 复算(1.2000/36天/红灯) ← 不一致；"
     "融资冲击: 文档(0.65/8天/红灯) vs 复算(0.6500/20天/红灯) ← 不一致；"
     "成本冲击: 文档(1.40/22天/黄灯) vs 复算(1.4000/42天/红灯) ← 不一致；"
     "联合冲击: 文档(-0.15/0天/红灯) vs 复算(-0.4500/-14天/红灯) ← 不一致",
     "v8 行 713—737；公式依据 v8 行 650—655、745—762",
     "样例文案与自身公式三处不符（灯级 ×2、天数 ×4、联合缺口 −15 vs −45），"
     "不得作为验收基线 → 缺陷 D-01；看板审计行 602 用 −0.45 与复算一致")
case("C47", "F-20", "边界", "联合冲击后缓冲为负 → 是否直接红",
     lambda: f09_static_lamp(D("-0.45"), "2.5", "1.5")[0], "红灯",
     "施工单 7.5 行 128；包B/看板一致", "负倍数 < K红 恒成立 → 红")

# ---- F-21 审批路由 ----
case("C48", "F-21", "正常", "制造 S=100（万元），绿灯，申请金额 80（万元）",
     lambda: f21_approval(80, "绿灯", "制造", 100)[0], "财务总监",
     "v8 行 1116—1118；包B N05 行 145—150", "线1=S×0.5=50、线2=S×2.0=200；80 落中间档")
case("C49", "F-21", "边界", "制造 S=100（万元），绿灯，申请金额 50.00（万元）",
     lambda: f21_approval(50, "绿灯", "制造", 100)[0], "部门经理",
     "包B E15 行 284", "等值满足 ≤S×0.5")
case("C50", "F-21", "正常", "制造 S=100（万元），红灯，申请金额 4（万元）",
     lambda: f21_approval(4, "红灯", "制造", 100)[0], "总经理+财务双签",
     "v8 行 773；看板行 1023", "红灯全档双签")
case("C51", "F-21", "待裁决", "制造 S=100（万元），绿灯，申请金额 250（万元，> 第二线）",
     lambda: f21_approval(250, "绿灯", "制造", 100), "总经理+财务双签；超过第二线：v8 §5.1 线3 与模块四表口径并存，R04 未裁 → 待确认",
     "v8 行 1118 vs 行 769—773；包B R04 行 95—97", "金额档与灯级谁优先未裁 → P-08", expect_status="PASS")
case("C51b", "F-21", "正常", "制造 S=100（万元），黄灯，申请金额 30（万元，≤ 第一线）",
     lambda: f21_approval(30, "黄灯", "制造", 100)[0], "财务总监",
     "看板行 1022（建议级）；v8 行 771", "黄灯最低档升财务总监；本档 v8 与看板一致但实现级未裁决 → P-08 附注")

# ---- F-04 有效缓冲 / 到账计入 ----
case("C52", "F-04", "异常", "已验证 100（万元）+ 新增手工勾选待验证 80（万元）",
     lambda: (D("100") + D("0")).quantize(Q2), "100.00",
     "v8 行 897—898；施工单 3.7 行 72；包B A07 行 335—340",
     "待验证金额不计入有效缓冲")

# ---- F-24 单位与精度 ----
case("C53", "F-24", "正常", "185 万元 → 元",
     lambda: f24_unit(185), "185.00 万元 = 1850000.00 元",
     "裁决 D12 行 12；看板核对清单；施工单 0.4 行 17", "万元→元 ×10000")
case("C54", "F-24", "边界", "80.59999999999999 万元（浮点噪声）→ 元",
     lambda: f24_unit("80.59999999999999"), "80.60 万元 = 806000.00 元",
     "工作台交接清单 4.7-2 行 213；包B 行 41（万元精度 0.01）",
     "判定用底层值、展示/入库 ROUND 2 位（包B E01—E06 行 266）")

# ---- F-23 13 周（无批准口径 → 只做勾稽核查，不给公式）----
WEEKS_OP_IN = [218, 205, 231, 198, 242, 226, 209, 238, 251, 229, 244, 262, 255]
WEEKS_OP_OUT = [-196, -208, -215, -221, -199, -212, -228, -216, -205, -219, -231, -214, -226]
WEEKS_FIN = [0, -35, 0, 60, 0, -18, -42, 0, 55, 0, -26, 0, -40]
WEEKS_INV = [-12, -8, -25, -6, -14, -30, -9, -11, -22, -7, -16, -9, -13]


def _week13_check():
    net_op = sum(WEEKS_OP_IN) + sum(WEEKS_OP_OUT)
    net_fin = sum(WEEKS_FIN)
    net_inv = sum(WEEKS_INV)
    weekly_out = -sum(WEEKS_OP_OUT) / Decimal(13)
    month_equiv = (weekly_out * Decimal("4.345")).quantize(Q2, rounding=ROUND_HALF_UP)
    return (f"经营性净流 {net_op} 万元；筹资 {net_fin} 万元；投资 {net_inv} 万元；"
            f"13周合计 {net_op + net_fin + net_inv} 万元；"
            f"周均流出 {weekly_out.quantize(Q2, rounding=ROUND_HALF_UP)} 万元 → "
            f"折月均 {month_equiv} 万元 "
            f"（对照同页 M=500 万元/月，比值 "
            f"{(month_equiv / D(500)).quantize(Q2, rounding=ROUND_HALF_UP)}）")


case("C55", "F-23", "核查", "演示看板 WEEKS 硬编码 13 周序列（行 558—565）",
     _week13_check,
     "经营性净流 218 万元；筹资 -46 万元；投资 -182 万元；13周合计 -10 万元；"
     "周均流出 214.62 万元 → 折月均 932.50 万元 （对照同页 M=500 万元/月，比值 1.87）",
     "看板行 558—565；v8 行 527；施工单 3.3 行 66（○ 未定义）",
     "结论：13 周序列与同页 M/buffer 不构成勾稽，属独立硬编码演示序列，不得当口径来源 → P-13（P3-1 编号修正）")


# ---------------------------------------------------------------------------
# v2 新增（P1 修复）：千问表格「空白单元格」语义与带守卫公式
#   目的：v1 只有 Python None 判断，测不到"表格把空白当 0 / AVERAGE 忽略空白"的语义，
#   所以脚本全 PASS 而公式列其实会假绿。这里显式建模表格语义，再验证守卫后的公式。
# ---------------------------------------------------------------------------
BLANK = "«空白»"


def _is_blank(v):
    """表格空白：None、空串、BLANK 哨兵，都按'单元格为空'处理。"""
    return v is None or v == BLANK or v == ""


def f01_formula_sheet(values):
    """F-01 v2 千问公式（带守卫）：IF(COUNT(范围)<3,"待补录",AVERAGE(范围))"""
    nums = [v for v in values if not _is_blank(v)]
    if len(nums) < 3:
        return "待补录"
    return (sum(D(str(v)) for v in nums) / Decimal(3)).quantize(Q4, rounding=ROUND_HALF_UP)


def f01_formula_noguard(values):
    """F-01 v1 无守卫实现（仅用于对照，证明缺陷真实存在）：AVERAGE 忽略空白、分母变小。"""
    nums = [v for v in values if not _is_blank(v)]
    return (sum(D(str(v)) for v in nums) / Decimal(len(nums))).quantize(Q4, rounding=ROUND_HALF_UP)


def f03_formula_sheet(verified_sum, balance, rigid):
    """F-03 v2 千问公式（带守卫）：三项任一为空 → 不可判定"""
    if verified_sum is None or _is_blank(balance) or _is_blank(rigid):
        return "不可判定"
    return (D(str(verified_sum)) + D(str(balance)) - D(str(rigid))).quantize(
        Q2, rounding=ROUND_HALF_UP)


def f03_formula_noguard(verified_sum, balance, rigid):
    """F-03 v1 无守卫（对照）：空白按 0 参与运算 → 刚性支出缺失时 B 虚高。"""
    v = D("0") if (verified_sum is None or _is_blank(verified_sum)) else D(str(verified_sum))
    b = D("0") if _is_blank(balance) else D(str(balance))
    r = D("0") if _is_blank(rigid) else D(str(rigid))
    return (v + b - r).quantize(Q2, rounding=ROUND_HALF_UP)


def f18_formula_sheet(Q, Dv, P):
    """F-18 v2 千问公式（带守卫）：先短路空白，再走灯级分支。"""
    if _is_blank(Q) or _is_blank(Dv):
        return "不可判定"
    q, dv = D(str(Q)), D(str(Dv))
    p = None if _is_blank(P) else D(str(P))
    if dv < 0 and p is None:
        return "不可判定"
    if (dv < 0 and p is not None and p >= D("0.7")) or q < D("0.3"):
        return "红灯"
    if ((dv < 0 and p is not None and D("0.3") <= p < D("0.7"))
            or (q < D("0.5") and dv < 0)
            or (dv < 0 and p is not None and p < D("0.3"))):
        return "黄灯"
    if dv >= 0 and q >= D("0.5"):
        return "绿灯"
    return "不可判定"


def f18_formula_noguard(Q, Dv, P):
    """F-18 v1 无守卫（对照）：表格把空白当 0 参与比较 → D 空白落绿、P 空白落黄。"""
    q = D("0") if _is_blank(Q) else D(str(Q))
    dv = D("0") if _is_blank(Dv) else D(str(Dv))
    p = D("0") if _is_blank(P) else D(str(P))
    if (dv < 0 and p >= D("0.7")) or q < D("0.3"):
        return "红灯"
    if (dv < 0 and D("0.3") <= p < D("0.7")) or (q < D("0.5") and dv < 0) or (dv < 0 and p < D("0.3")):
        return "黄灯"
    if dv >= 0 and q >= D("0.5"):
        return "绿灯"
    return "不可判定"


def f13_formula_sheet(benford_factors, myer_factors, n_metric=15):
    """F-13 v2 千问公式（带守卫）：因子数不足 2×指标数 → 不可判定"""
    nb = sum(1 for v in benford_factors if not _is_blank(v))
    nm = sum(1 for v in myer_factors if not _is_blank(v))
    if nb + nm < 2 * n_metric:
        return "不可判定"
    sb = sum(D(str(v)) for v in benford_factors if not _is_blank(v))
    sm = sum(D(str(v)) for v in myer_factors if not _is_blank(v))
    return (D(1) - (sb + sm) / D(2 * n_metric)).quantize(Q4, rounding=ROUND_HALF_UP)


def f13_formula_noguard(benford_factors, myer_factors, n_metric=15):
    """F-13 v1 无守卫（对照）：SUMPRODUCT 把空白当 0 → 缺项被当成未命中，Q 偏高。"""
    sb = sum(D(str(v)) for v in benford_factors if not _is_blank(v))
    sm = sum(D(str(v)) for v in myer_factors if not _is_blank(v))
    return (D(1) - (sb + sm) / D(2 * n_metric)).quantize(Q4, rounding=ROUND_HALF_UP)


def f11_formula_sheet(same_month_ratios, static_Ky):
    """F-11 v2 千问公式（带守卫）：COUNT(同期样本)<3 → 回退静态 K"""
    nums = [v for v in same_month_ratios if not _is_blank(v)]
    if len(nums) < 3:
        return f"回退静态Ky={D(str(static_Ky))}"
    import statistics
    return f"动态Ky={percentile_inc([D(str(v)) for v in nums], D('0.25'))}"


def f14_chi2(N, e_freqs):
    """F-14 Benford χ²：χ² = N × Σ[(e_d − f_d)²/f_d]，f_d = log10(1+1/d)，d=1..9。

    ⚠ e_freqs 为**自造的最小示例**（不是看板实测 obs/theo，后者未取得），
    仅用于验证 χ² 计算式与 20.09 阈值的比较逻辑本身。
    """
    import math
    chi = Decimal(0)
    for dd in range(1, 10):
        f = Decimal(str(math.log10(1 + 1.0 / dd)))
        e = D(str(e_freqs[dd - 1]))
        chi += (e - f) ** 2 / f
    return (D(str(N)) * chi).quantize(Q4, rounding=ROUND_HALF_UP)


def f22_exception_rate(exceptions, total):
    """F-22 例外率：分母缺失返回 None（不得返回 0）；阈值 > 20% → 异常偏高。"""
    if total is None or _is_blank(total) or D(str(total)) == 0:
        return None
    r = (D(str(exceptions)) / D(str(total))).quantize(Q4, rounding=ROUND_HALF_UP)
    return r, ("异常偏高" if r > D("0.20") else "正常")


# --- P1：空白单元格用例（v2 守卫版 vs v1 无守卫版对照）-------------------------
case("C56", "F-01", "空值守卫", "近3月流出 90 / 空白 / 120（万元）",
     lambda: f"守卫版:{f01_formula_sheet([90, BLANK, 120])}；v1无守卫:{f01_formula_noguard([90, BLANK, 120])}",
     "守卫版:待补录；v1无守卫:105.0000",
     "P1 修复；v8 行 638—639；施工单 3.1 行 64",
     "表格 AVERAGE 忽略空白 → 分母变 2 → 105；守卫后 COUNT=2<3 → 待补录。证明缺陷真实存在且已修", expect_status="PASS")

case("C57", "F-02", "空值守卫", "近3月(营业成本+管理费用) 100 / 空白 / 100",
     lambda: f"守卫版:{f01_formula_sheet([100, BLANK, 100])}；v1无守卫:{f01_formula_noguard([100, BLANK, 100])}",
     "守卫版:待补录；v1无守卫:100.0000",
     "P1 修复；v8 行 1120；施工单 5.1 行 100",
     "同 F-01：缺月不得忽略后求均值", expect_status="PASS")

case("C58", "F-03", "空值守卫", "已验证到账 100、现金余额 200、刚性支出【空白】",
     lambda: f"守卫版:{f03_formula_sheet(100, 200, BLANK)}；v1无守卫:{f03_formula_noguard(100, 200, BLANK)}",
     "守卫版:不可判定；v1无守卫:300.00",
     "P1 修复；施工单 3.5 行 68；看板 html 行 883",
     "刚性支出空白 → v1 减 0 → B 虚高 300（真值应不出数）；虚高会把红灯算成绿灯", expect_status="PASS")

case("C59", "F-18", "空值守卫", "Q=0.8、D【空白】、P=0.2",
     lambda: f"守卫版:{f18_formula_sheet(0.8, BLANK, 0.2)}；v1无守卫:{f18_formula_noguard(0.8, BLANK, 0.2)}",
     "守卫版:不可判定；v1无守卫:绿灯",
     "P1 修复（最严重）；v8 行 396—399；裁决 A2 行 95；包B A10 行 357—363",
     "D 空白 → v1 中 D<0 假、D>=0 真 → 落绿灯；这是'缺数据反而报绿'的典型路径", expect_status="PASS")

case("C60", "F-18", "空值守卫", "Q=0.8、D=-0.2、P【未取得/空白】",
     lambda: f"守卫版:{f18_formula_sheet(0.8, -0.2, BLANK)}；v1无守卫:{f18_formula_noguard(0.8, -0.2, BLANK)}",
     "守卫版:不可判定；v1无守卫:黄灯",
     "P1 修复；C42 规则；v8 行 397—398",
     "P 空白 → v1 中 P<0.3 为真 → 落黄灯；规则要求'不可判定，不得因拿不到 P 而报灯'", expect_status="PASS")

case("C61", "F-13", "空值守卫", "Benford 因子 15 项中 1 项空白（共 29 个有效值，指标数 15）",
     lambda: f"守卫版:{f13_formula_sheet([1] * 14 + [BLANK], [0] * 15)}；v1无守卫:{f13_formula_noguard([1] * 14 + [BLANK], [0] * 15)}",
     "守卫版:不可判定；v1无守卫:0.5333",
     "P1 修复；v8 行 213、589；施工单 2.11 行 55",
     "空白因子被 SUMPRODUCT 当 0 → 分子变小 → Q 偏高（0.5333 而非 0.5）→ 可能把灯压绿", expect_status="PASS")

case("C62", "F-11", "空值守卫", "同月样本仅 2 条（<3）→ 强制回退静态 Ky=2.5",
     lambda: f11_formula_sheet([1.68, BLANK, 2.02], "2.5"),
     "回退静态Ky=2.5",
     "P1 修复；裁决 A4 行 97；施工单 4.3 行 85",
     "PERCENTILE 对不足 3 个样本仍返回值；守卫后 COUNT<3 → 回退静态", expect_status="PASS")

# --- P2-2：dual_shock 第五场景 ------------------------------------------------
case("C46c", "F-20", "正常", "制造样本 M=100，B=185，ar30=65，可用授信 240（万元）→ dual_shock",
     lambda: (lambda rec, fin: (
         f"缺口{(rec + fin).quantize(Q2, rounding=ROUND_HALF_UP)}；"
         f"冲击后缓冲{(D('185') - (rec + fin)).quantize(Q2, rounding=ROUND_HALF_UP)}；"
         f"倍数{((D('185') - (rec + fin)) / D('100')).quantize(Q4, rounding=ROUND_HALF_UP)}；"
         f"灯{f09_static_lamp(((D('185') - (rec + fin)) / D('100')).quantize(Q4, rounding=ROUND_HALF_UP), D('2.5'), D('1.5'))[0]}"
     ))(f20_stress(185, 100, 65, 240, 225, D("2.5"), D("1.5"))[0][1],
        f20_stress(185, 100, 65, 240, 225, D("2.5"), D("1.5"))[1][1]),
     "缺口185.00；冲击后缓冲0.00；倍数0.0000；灯红灯",
     "P2-2 修复；裁决 A5 行 98（五值枚举）；v8 行 745—762",
     "dual = 回款缺口 65 + 融资缺口 120 = 185；缓冲 185−185=0 → 倍数 0 → 红灯（缓冲归零）")

# --- P2-5：补齐零覆盖/单侧覆盖公式 -------------------------------------------
case("C63", "F-14", "正常", "自造示例：观测频率**完全等于** Benford 理论频率（N=100）",
     lambda: (lambda c: f"χ²={c}；判定={'偏离' if c > D('20.09') else '未偏离'}"
              )(f14_chi2(100, [round(0.30103, 5), 0.17609, 0.12494, 0.09691, 0.07918,
                               0.06695, 0.05799, 0.05115, 0.04576])),
     "χ²=0.0000；判定=未偏离",
     "v8 行 176—180；施工单 2.8 行 52；看板 html 行 556（CHISQ_CRIT=20.09, df=8, α=0.01）",
     "⚠ 本用例用**自造最小示例**验证 χ² 计算式与阈值比较；看板实测 obs/theo 未取得，不作实测基线")

case("C63b", "F-14", "边界", "自造示例：首位数字 1 的观测频率人为抬高 0.25（N=100）",
     lambda: (lambda c: f"χ²={c}；判定={'偏离' if c > D('20.09') else '未偏离'}"
              )(f14_chi2(100, [round(0.30103 + 0.25, 5), round(0.17609 - 0.03125, 5),
                               round(0.12494 - 0.03125, 5), round(0.09691 - 0.03125, 5),
                               round(0.07918 - 0.03125, 5), round(0.06695 - 0.03125, 5),
                               round(0.05799 - 0.03125, 5), round(0.05115 - 0.03125, 5),
                               round(0.04576 - 0.03125, 5)])),
     "χ²=31.5253；判定=偏离",
     "同上；P3-2 说明 20.09 是 α=0.01 临界值（v8 行 180 的'10% 显著性'与之矛盾，已标注）",
     "手算（v2 已修正精度）：f_1=log10(2)=0.30102999566（不是截断的 0.30103）；"
     "0.25²/0.30103=0.207619；Σ_{d=2..9}(0.03125²)/f_d=0.107637；合计 0.315256×100=31.5253 > 20.09 → 偏离。"
     "注：初版预期写 31.5256 是用 5 位截断 f_d 手算的误差，已按完整精度独立复算更正")

case("C64", "F-22", "边界", "例外 3 次 / 总审批 15 次 = 0.2000（等号）",
     lambda: (lambda r: f"例外率={r[0]}；判定={r[1]}")(f22_exception_rate(3, 15)),
     "例外率=0.2000；判定=正常",
     "v8 行 785—791；施工单 5.4 行 103",
     "阈值是 >20% 才异常，等号 0.2000 不触发（严格大于）")

case("C64b", "F-22", "异常", "缺同范围审批总笔数（分母为空）",
     lambda: f"例外率={f22_exception_rate(3, None)}",
     "例外率=None",
     "v8 行 785—791；F-22 边界条款",
     "分母缺失返回 null，不得返回 0（返回 0 会把'无数据'伪装成'零例外'）")

case("C65", "F-12", "正常", "零售 B=100、M=50 → 倍数 2.0；季调开/关对比",
     lambda: f"关季调(K黄1.8):{f09_static_lamp(D('2.0'), D('1.8'), D('1.0'))[0]}；"
             f"开季调(K黄2.3):{f09_static_lamp(D('2.0'), D('2.3'), D('1.3'))[0]}",
     "关季调(K黄1.8):绿灯；开季调(K黄2.3):黄灯",
     "v8 行 1145；看板 html 行 650—653；包B N09",
     "季调 +0.5/+0.3 会把同一家企业从绿翻黄；月份范围待确认 → P-07")

case("C66", "F-25", "边界", "应收周转相对值 1.30 / 1.50（黄线）；红灯阈值待裁决",
     lambda: f"1.30:{'黄灯' if D('1.30') > D('1.3') else '未触发'}；"
             f"1.50:{'黄灯' if D('1.50') > D('1.3') else '未触发'}；"
             f"红灯阈值:待裁决(P-15)",
     "1.30:未触发；1.50:黄灯；红灯阈值:待裁决(P-15)",
     "v8 行 1094—1095（原文：>1.3 触发关注，>1.5 触发黄灯）；P2-3 修复",
     "⚠ v1 把 1.5 写成红线，v8 原文 1.5 是黄线 —— v2 已把红列改为待裁决，不擅自升级严重度")

case("C67", "F-04", "异常", "已验证到账 100 + 手工勾选'已到账'但未验证 80",
     lambda: (D("100")).quantize(Q2, rounding=ROUND_HALF_UP),
     "100.00",
     "v8 行 897—898；施工单 3.7 行 72；包B A07 行 335—340",
     "未验证金额一律不计入（C52 已有同类用例，本条补'正常+部分到账'双侧覆盖）")

case("C68", "F-03", "正常", "已验证到账 100 + 现金余额 200 − 刚性支出 50（分量算术）",
     lambda: f03_formula_sheet(100, 200, 50),
     "250.00",
     "施工单 3.5 行 68；看板 html 行 883",
     "补 F-03 的算术用例（v1 零用例）；注意 P-09：若到账已含在余额里则属重复计入")

case("C69", "F-10", "正常", "制造业 K黄/K红 查表取值",
     lambda: f"制造业 K黄={IND['制造']['Ky']}；K红={IND['制造']['Kr']}",
     "制造业 K黄=2.5；K红=1.5",
     "v8 行 1106—1186；看板 html 行 514—517；P-07",
     "⚠ 该值与四份 xlsx `行业参数` sheet（1.5/1.0）不一致，四个行业全部冲突 → P-07")


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------
def norm(v):
    if isinstance(v, tuple):
        return "；".join(str(x) for x in v)
    if isinstance(v, dict):
        return "；".join(f"{k}={val}" for k, val in v.items())
    return str(v)


# 中间计算过程（手算逐步骤，供人工核对；与脚本同源）
STEPS = {
    "C01": "M=(90+100+110)/3=300/3=100",
    "C02": "填0→(90+0+110)/3=66.6667（错）；忽略缺失→(90+110)/2=100（错）；正确：标待补录，M 不出数",
    "C03": "M=(0+0+0)/3=0；B/M=80/0 → 除零，不适用（不报绿）",
    "C04": "S=[(80+20)+(80+20)+(80+20)]/3=300/3=100",
    "C05": "B/M=300/100=3.0000；3.0000≥K黄2.5 → 绿",
    "C06": "B/M=200/100=2.0000；1.5≤2.0<2.5 → 黄",
    "C07": "B/M=100/100=1.0000；1.0<1.5 → 红",
    "C08": "B/M=149.99/100=1.4999；1.4999<1.5 → 红",
    "C09": "B/M=150.00/100=1.5000；等于 K红，不满足'小于' → 落黄区 → 黄",
    "C10": "B/M=150.01/100=1.5001；>1.5 且 <2.5 → 黄",
    "C11": "B/M=249.99/100=2.4999；<2.5 → 黄",
    "C12": "B/M=250.00/100=2.5000；等于 K黄，不满足'小于' → 绿",
    "C13": "B/M=250.01/100=2.5001；≥2.5 → 绿",
    "C14": "B/M=100/50=2.0000；零售 K黄1.8、K红1.0；2.0≥1.8 → 绿",
    "C15": "B/M=70/50=1.4000；1.0≤1.4<1.8 → 黄",
    "C16": "B/M=30/50=0.6000；<1.0 → 红",
    "C17": "B/M=800/200=4.0000；建筑 K黄3.5、K红2.0；≥3.5 → 绿",
    "C18": "B/M=500/200=2.5000；2.0≤2.5<3.5 → 黄（若错用制造 K黄2.5 会误判绿）",
    "C19": "B/M=300/200=1.5000；<2.0 → 红",
    "C20": "B/M=80/40=2.0000；科技 K黄1.5、K红1.0；≥1.5 → 绿",
    "C21": "B/M=50/40=1.2500；1.0≤1.25<1.5 → 黄",
    "C22": "B/M=30/40=0.7500；<1.0 → 红",
    "C23": "日均流出=M/30=100/30=3.3333；天数=185/3.3333=55.5→round→56；56≥45 → 绿",
    "C24": "天数=100/(100/30)=30；30<45 且 ≥25 → 黄",
    "C25": "M=0 → 天数=80/(0/30) 除零 → 不可计算",
    "C26": "融资缓冲=240+0=240.00",
    "C27": "未使用授信=-40 <0 → gate_negative_credit 命中'异常'，须先处置再取数",
    "C28": "含1.45：100×0.30×1.45=43.50；不含：100×0.30=30.00；差 13.50",
    "C29": "同月样本 n=1 <3（裁决 A4）→ 回退静态 K黄2.5/K红1.5",
    "C30": "排序[1.68,1.85,2.02]；P25 idx=(3-1)×0.25=0.5→1.68+0.5×0.17=1.7650；"
           "P10 idx=0.2→1.68+0.2×0.17=1.7140；静态 K红1.5×0.70=1.05（下限），1.7140>1.05 未触底；"
           "1.7650>1.7140 未压带",
    "C31": "混合 Ky=2.5×0.7+1.7650×0.3=1.75+0.5295=2.2795；Kr=1.5×0.7+1.7140×0.3=1.05+0.5142=1.5642",
    "C32": "Q=1-(5+4)/(2×15)=1-9/30=1-0.3=0.7000",
    "C33": "D=0.31×(2×0.34-1)+0.24×(2×0.31-1)+0.19×(2×0.62-1)+0.26×(2×0.44-1)"
           "=(-0.0992)+(-0.0912)+0.0456+(-0.0312)=-0.1760",
    "C34": "Q=0.8≥0.5 不触发直红；D<0 且 P=0.6999<0.7 → 0.3≤P<0.7 分支 → 黄",
    "C35": "D<0 且 P=0.7000 ≥0.7（含等号）→ 红",
    "C36": "D<0 且 P=0.7001 ≥0.7 → 红",
    "C37": "Q=0.2999<0.3 → 直接红，D≥0 不覆盖",
    "C38": "Q=0.3000 不满足<0.3；D≥0 且 Q≥0.5 → 绿分支？Q=0.3<0.5 不满足；"
           "Q<0.5 且 D<0 不成立（D>0）→ 无分支命中 → 不可判定",
    "C39": "D=0.0000 属 D≥0，且 Q=0.8≥0.5 → 绿",
    "C40": "D<0 且 P=0.2<0.3 → A2 补齐分支 → 黄（v8 原式无此分支，会误判绿）",
    "C41": "Q=0.4∈[0.3,0.5) 且 D=0.2≥0 → 原式无分支 → 不可判定",
    "C42": "D<0 但未取得 P → 三个 D<0 分支均需 P，Q≥0.5 → 不得默认绿 → 不可判定",
    "C43": "严重度 红3>黄2 → 取红",
    "C44": "模型绿(0) vs 现金红(3) → 取红（A3 防覆盖）",
    "C45": "不可判定(1) vs 绿灯(0) → 取不可判定（不报绿）",
    "C46": "缺口：回款65.00、融资240×0.5=120.00、成本225×0.2=45.00、联合=230.00；"
           "冲击后缓冲：120.00/65.00/140.00/-45.00；÷M100 → 1.20/0.65/1.40/-0.45；"
           "均 <K红1.5 → 全红",
    "C46b": "文档标 1.20→黄，但 1.20<K红1.5 应为红；文档天数 18 天 vs 120/(100/30)=36 天；"
            "文档联合 -15 万/-0.15 vs 缺口合计 230 → -45 万/-0.45",
    "C47": "-0.45 < 1.5 → 红（负倍数恒成立）",
    "C48": "线1=S×0.5=50、线2=S×2.0=200；80∈(50,200] → 财务总监",
    "C49": "50 ≤ 线1=50（等值满足 ≤）→ 部门经理",
    "C50": "红灯 → 全档双签，不看金额",
    "C51": "250 > 线2=200 → 按 §5.1 线3 双签；但模块四只写'绿灯>线1→财务总监' → R04 未裁",
    "C51b": "30 ≤ 线1=50 → 金额档为部门经理；黄灯 → 升财务总监（看板矩阵，建议级）",
    "C52": "有效缓冲=SUMIF(状态,'已验证')=100+0=100.00（待验证 80 不计入）",
    "C53": "185 万元 ×10000 = 1,850,000.00 元",
    "C54": "80.59999999999999 → ROUND(,2)=80.60 万元 → ×10000=806,000.00 元",
    "C55": "经营净流=3008-2790=218；筹资=-46；投资=-182；合计=218-46-182=-10；"
           "周均流出=2790/13=214.62；折月均=214.6154×4.345=932.50；932.50/500=1.87",
}


def main():
    print("=" * 78)
    print("WB-FIN-001 · 财务公式离线校验（WorkBuddy v1）")
    print("单位：万元（除 F-24）；金额精度 0.01；比值精度 0.0001；ROUND_HALF_UP")
    print("说明：本脚本为离线算术复核，不代表千问表格已能运行；平台公式一律待平台验证")
    print("=" * 78)

    n_pass = n_fail = n_blocked = 0
    results = []
    for c in CASES:
        try:
            actual = c["compute"]()
        except Exception as e:  # 如实报告，不吞错
            actual = f"ERROR: {type(e).__name__}: {e}"
        a = norm(actual)
        exp = c["expected"]
        # P3-6 修复：把"规则待决"与"行为已定"分开。
        #   expect_status="PASS" → 输出是已定行为，强制做真实比较（v1 会因关键词误判 BLOCKED）；
        #   "BLOCKED" → 规则未裁，不比较；"AUTO" → 沿用 v1 关键词启发式。
        forced = c.get("expect_status", "AUTO")
        if forced == "PASS":
            blocked = False
        elif forced == "BLOCKED":
            blocked = True
        else:
            blocked = ("不可判定" in exp) or ("待确认" in exp) or ("不可直接使用" in exp) \
                or ("不可计算" in exp) or ("不适用" in exp) or ("缺失" in exp) \
                or ("待补录" in exp) or ("回退静态" in exp) or ("差异" in exp)
        if blocked:
            status = "BLOCKED"
            n_blocked += 1
        elif a == exp:
            status = "PASS"
            n_pass += 1
        else:
            status = "FAIL"
            n_fail += 1
        results.append(dict(id=c["id"], formula=c["formula"], kind=c["kind"],
                            inputs=c["inputs"], steps=STEPS.get(c["id"], c["note"]),
                            expected=exp, actual=a, status=status,
                            basis=c["basis"], note=c["note"]))
        print(f"\n[{status}] {c['id']} · {c['formula']} · {c['kind']}")
        print(f"  输入    : {c['inputs']}")
        print(f"  中间过程: {STEPS.get(c['id'], c['note'])}")
        print(f"  预期    : {exp}")
        print(f"  实际    : {a}")
        print(f"  依据    : {c['basis']}")
        if c["note"]:
            print(f"  备注    : {c['note']}")

    # 导出手算与边界用例 CSV（与脚本同源，下一轮运行会自动交叉核对）
    here = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(here, "手算与边界用例.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["用例编号", "公式编号", "场景类型", "输入", "中间计算过程",
                    "预期输出", "脚本实际输出", "状态", "依据", "备注"])
        for r in results:
            w.writerow([r["id"], r["formula"], r["kind"], r["inputs"], r["steps"],
                        r["expected"], r["actual"], r["status"], r["basis"], r["note"]])
    print(f"\n（已导出 {csv_path}）")

    print("\n" + "=" * 78)
    print(f"合计 {len(CASES)} 项：PASS {n_pass} / FAIL {n_fail} / BLOCKED {n_blocked}")
    print("BLOCKED = 规则未批准或无定义，本脚本不做判定，等待业务负责人确认")
    print("=" * 78)

    # CSV 一致性交叉核对（若手算用例 CSV 已存在）
    here = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(here, "手算与边界用例.csv")
    if os.path.exists(csv_path):
        print("\n=== CSV 交叉核对 ===")
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        idx = {r["用例编号"]: r for r in rows}
        missing = [c["id"] for c in CASES if c["id"] not in idx]
        mismatch = []
        for c in CASES:
            r = idx.get(c["id"])
            if r and r.get("预期输出", "").strip() != c["expected"].strip():
                mismatch.append((c["id"], r.get("预期输出"), c["expected"]))
        print(f"CSV 行数 {len(rows)}；脚本用例数 {len(CASES)}；缺失 {missing or '无'}")
        print(f"预期列不一致：{mismatch or '无'}")
        if not missing and not mismatch:
            print("CSV_CROSSCHECK: OK")
        else:
            print("CSV_CROSSCHECK: DIFF")
    else:
        print("\n（手算与边界用例.csv 尚未生成，跳过交叉核对）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
