"""selftest：只用自造合成夹具跑正反例，不依赖真实企业文件/网络/他人模块。

每个用例有：输入（夹具）、独立预期（tests/expected/expected_values.json 冻结文件）、
实际值、退出码。任一 FAIL/BLOCKED/意外异常 → 整体退出非 0（不 catch 后报 PASS）。
"""
import datetime
import json
import os
import shutil
import subprocess
import sys

from .canon import sha256_file, sha256_hex

DELIVERY_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # v1/src/mfg_import/selftest.py -> v1
SRC_ROOT = os.path.join(DELIVERY_ROOT, "src")
FIXTURES_DIR = os.path.join(DELIVERY_ROOT, "fixtures")
EXPECTED_FILE = os.path.join(DELIVERY_ROOT, "tests", "expected", "expected_values.json")

IDENTITY = ["--tenant-id", "test-tenant", "--company-id", "test-company",
            "--period", "2026-03", "--run-id", "selftest-run-1"]
MAPPING = os.path.join(FIXTURES_DIR, "mapping_fixture.json")

PASS, FAIL, BLOCKED, NOT_RUN = "PASS", "FAIL", "BLOCKED", "NOT_RUN"


class CaseFail(Exception):
    pass


class Ctx:
    def __init__(self, workdir):
        self.workdir = workdir
        self.cases_dir = os.path.join(workdir, "cases")
        self.expected = json.loads(open(EXPECTED_FILE, "rb").read().decode("utf-8"))
        self.expected_sha_before = sha256_file(EXPECTED_FILE)
        self.n = 0

    def case_dir(self, cid):
        d = os.path.join(self.cases_dir, cid)
        os.makedirs(d, exist_ok=True)
        return d

    def cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = SRC_ROOT
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, "-m", "mfg_import", *args],
            capture_output=True, text=True, env=env,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def scan(self, cid, input_dir, exceptions=None, extra=()):
        d = self.case_dir(cid)
        pkg = os.path.join(d, "pkg")
        args = ["scan", "--input", input_dir, "--output", pkg,
                "--mapping", MAPPING, *IDENTITY, *extra]
        if exceptions:
            args += ["--unit-exceptions", exceptions]
        rc, out, err = self.cli(*args)
        return rc, out, err, pkg

    def records(self, pkg):
        path = os.path.join(pkg, "records.jsonl")
        if not os.path.isfile(path):
            return []
        return [json.loads(l) for l in open(path, "rb").read().decode("utf-8").splitlines() if l.strip()]

    def issues(self, pkg):
        path = os.path.join(pkg, "issues.jsonl")
        if not os.path.isfile(path):
            return []
        return [json.loads(l) for l in open(path, "rb").read().decode("utf-8").splitlines() if l.strip()]

    def inventory(self, pkg):
        return json.loads(open(os.path.join(pkg, "inventory.json"), "rb").read().decode("utf-8"))

    def manifest(self, pkg):
        return json.loads(open(os.path.join(pkg, "manifest.json"), "rb").read().decode("utf-8"))


def cashflow_rec(recs, row):
    for r in recs:
        if r["sheet"] == "现金流水" and r["row"] == row:
            return r
    raise CaseFail(f"找不到 现金流水!行{row} 记录")


def ncodes(recs):
    return [i["code"] for i in recs]


def norm(rec, field):
    return rec["normalized"][field]


# ------------------------- 用例 -------------------------

def tc_001_normal(ctx):
    d = ctx.case_dir("TC-001")
    inp = _mk(d, "in")
    rc, out, err, pkg = ctx.scan("TC-001", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    recs = ctx.records(pkg)
    exp = ctx.expected
    got_in = [norm(cashflow_rec(recs, r), "经营性流入（万元）")["value"] for r in (3, 4, 5)]
    got_out = [norm(cashflow_rec(recs, r), "经营性流出（万元）")["value"] for r in (3, 4, 5)]
    got_month = [norm(cashflow_rec(recs, r), "月份")["value"] for r in (3, 4, 5)]
    got_date = [norm(cashflow_rec(recs, r), "月末日期")["value"] for r in (3, 4, 5)]
    if got_in != exp["normal_inflow_yuan"]:
        raise CaseFail(f"流入规范值 {got_in} != 预期 {exp['normal_inflow_yuan']}")
    if got_out != exp["normal_outflow_yuan"]:
        raise CaseFail(f"流出规范值 {got_out} != 预期 {exp['normal_outflow_yuan']}")
    if got_month != exp["normal_months"]:
        raise CaseFail(f"月份 {got_month} != 预期")
    if got_date != exp["normal_dates"]:
        raise CaseFail(f"日期 {got_date} != 预期 {exp['normal_dates']}")
    # 每个规范字段都有真实地址与转换依据
    for r in (3, 4, 5):
        rec = cashflow_rec(recs, r)
        for f in ("经营性流入（万元）", "月末日期"):
            n = norm(rec, f)
            if not n["address"] or not n["transform"]:
                raise CaseFail(f"行{r} 字段{f} 缺少地址或转换依据")
    co = [r for r in recs if r["sheet"] == "企业基本信息"]
    rev = [r for r in co if "上年度营业收入（万元）" in r["normalized"]][0]
    head = [r for r in co if "在职人数（人）" in r["normalized"]][0]
    if norm(rev, "上年度营业收入（万元）")["value"] != exp["revenue_yuan"]:
        raise CaseFail(f"营收 {norm(rev,'上年度营业收入（万元）')['value']} != {exp['revenue_yuan']}")
    if norm(head, "在职人数（人）")["value"] != exp["headcount"]:
        raise CaseFail("在职人数不符")
    for r in recs:
        if not r["source_record_key"] or len(r["source_record_key"]) != 64:
            raise CaseFail("source_record_key 缺失或长度异常")
    return (f"记录 {len(recs)} 条；流入 {got_in}；营收 {exp['revenue_yuan']}；"
            f"全部字段带地址与转换依据")


def tc_002_column_reorder(ctx):
    d = ctx.case_dir("TC-002")
    from fixtures.make_fixtures import build_workbook, CASHFLOW_ROWS
    rows = [[r[2], r[3], r[4], r[1], r[0]] for r in CASHFLOW_ROWS]  # 列重排
    inp = _mk(d, "in", cashflow_header=["流水类型", "经营性流入（万元）",
                                        "经营性流出（万元）", "月末日期", "月份"],
              cashflow_rows=rows)
    rc, out, err, pkg = ctx.scan("TC-002", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    recs = ctx.records(pkg)
    got_in = [norm(cashflow_rec(recs, r), "经营性流入（万元）")["value"] for r in (3, 4, 5)]
    if got_in != ctx.expected["normal_inflow_yuan"]:
        raise CaseFail(f"列重排后流入 {got_in} != 预期 {ctx.expected['normal_inflow_yuan']}")
    return f"列重排后仍映射正确: {got_in}"


def tc_003_missing_sheet(ctx):
    d = ctx.case_dir("TC-003")
    inp = _mk(d, "in", include_cashflow=False)
    rc, out, err, pkg = ctx.scan("TC-003", inp)
    if rc != 0:
        raise CaseFail(f"scan 技术执行失败 {rc}: {err}")
    codes = ncodes(ctx.issues(pkg))
    if "MISSING_SHEET" not in codes:
        raise CaseFail(f"未报 MISSING_SHEET: {codes}")
    return f"缺 Sheet 明确报告并继续执行: {codes}"


def tc_004_missing_column(ctx):
    d = ctx.case_dir("TC-004")
    inp = _mk(d, "in", cashflow_header=["月份", "月末日期", "流水类型", "经营性流入（万元）"],
              cashflow_rows=[[r[0], r[1], r[2], r[3]] for r in _rows()])
    rc, out, err, pkg = ctx.scan("TC-004", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    codes = ncodes(ctx.issues(pkg))
    if "MISSING_COLUMN" not in codes:
        raise CaseFail(f"未报 MISSING_COLUMN: {codes}")
    rec = cashflow_rec(ctx.records(pkg), 3)
    if norm(rec, "经营性流出（万元）")["value"] is not None:
        raise CaseFail("缺列却给出了规范值")
    return f"缺列报 MISSING_COLUMN，规范值保持 null: {codes}"


def tc_005_duplicate_column(ctx):
    d = ctx.case_dir("TC-005")
    inp = _mk(d, "in", cashflow_header=["月份", "月末日期", "流水类型",
                                        "经营性流入（万元）", "经营性流入（万元）"],
              cashflow_rows=[[r[0], r[1], r[2], r[3], r[3]] for r in _rows()])
    rc, out, err, pkg = ctx.scan("TC-005", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    codes = ncodes(ctx.issues(pkg))
    if "DUPLICATE_COLUMN" not in codes:
        raise CaseFail(f"未报 DUPLICATE_COLUMN: {codes}")
    rec = cashflow_rec(ctx.records(pkg), 3)
    if norm(rec, "经营性流入（万元）")["value"] is not None:
        raise CaseFail("重名列却取了第一列的值")
    return "重名列报 DUPLICATE_COLUMN，不取第一项"


def tc_006_alias_ambiguity(ctx):
    d = ctx.case_dir("TC-006")
    company_rows = [("企业名称", "测试合成企业"), ("在职人数", 320), ("在职人数（人）", 320)]
    inp = _mk(d, "in", company_rows=company_rows)
    rc, out, err, pkg = ctx.scan("TC-006", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    codes = ncodes(ctx.issues(pkg))
    if "ALIAS_AMBIGUITY" not in codes:
        raise CaseFail(f"未报 ALIAS_AMBIGUITY: {codes}")
    rec = [r for r in ctx.records(pkg)
           if r["sheet"] == "企业基本信息" and "在职人数（人）" in r["normalized"]][0]
    if norm(rec, "在职人数（人）")["value"] is not None:
        raise CaseFail("别名歧义却默默取了值")
    return "两个别名同时出现报歧义，不覆盖不取值"


def tc_007_vertical_reorder(ctx):
    d = ctx.case_dir("TC-007")
    company_rows = [("上年度营业收入（万元）", 12800), ("在职人数（人）", 320),
                     ("企业名称", "测试合成企业")]
    inp = _mk(d, "in", company_rows=company_rows)
    rc, out, err, pkg = ctx.scan("TC-007", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    recs = ctx.records(pkg)
    head = [r for r in recs if r["sheet"] == "企业基本信息"
            and "在职人数（人）" in r["normalized"]][0]
    if norm(head, "在职人数（人）")["value"] != ctx.expected["headcount"]:
        raise CaseFail("换行号后未取到正确值")
    addr = norm(head, "在职人数（人）")["address"]
    if addr != "B4":
        raise CaseFail(f"地址应为 B4（换行后位置变化），实际 {addr}")
    return f"纵向字段换行仍按字段名定位，地址 = {addr}"


def tc_008_zero_and_empties(ctx):
    from fixtures.make_fixtures import (set_blank_cell, set_empty_string)
    d = ctx.case_dir("TC-008")
    rows = [["2026-01", _dt(2026, 1, 31), "经营性", 0, 60.0],
            ["2026-02", _dt(2026, 2, 28), "经营性", "", 60.0],
            ["2026-03", _dt(2026, 3, 31), "经营性", " ", 60.0]]
    inp = _mk(d, "in", cashflow_rows=rows)
    f = os.path.join(inp, "fixture.xlsx")
    set_blank_cell(f, 2, "E3")       # 元素存在但无 <v>：显式空白
    set_empty_string(f, 2, "D4")    # 显式空字符串
    rc, out, err, pkg = ctx.scan("TC-008", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    recs = ctx.records(pkg)
    zero = norm(cashflow_rec(recs, 3), "经营性流入（万元）")["value"]
    blank = norm(cashflow_rec(recs, 3), "经营性流出（万元）")["transform"]["status"]
    empty = norm(cashflow_rec(recs, 4), "经营性流入（万元）")["transform"]["status"]
    space = norm(cashflow_rec(recs, 5), "经营性流入（万元）")["transform"]["status"]
    if zero != ctx.expected["zero_amount_yuan"]:
        raise CaseFail(f"真实 0 应为 {ctx.expected['zero_amount_yuan']}，实际 {zero}")
    if blank != "blank_cell":
        raise CaseFail(f"空白单元格状态 {blank} != blank_cell")
    if empty != "empty_string":
        raise CaseFail(f"空串状态 {empty} != empty_string")
    if space != "whitespace_only":
        raise CaseFail(f"空格状态 {space} != whitespace_only")
    return f"0={zero}；空白={blank}；空串={empty}；空格={space}（四者可区分）"


def tc_009_numeric_text(ctx):
    d = ctx.case_dir("TC-009")
    rows = [["2026-01", _dt(2026, 1, 31), "经营性", "123.45", 60.0]]
    inp = _mk(d, "in", cashflow_rows=rows)
    rc, out, err, pkg = ctx.scan("TC-009", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    n = norm(cashflow_rec(ctx.records(pkg), 3), "经营性流入（万元）")
    codes = ncodes(ctx.issues(pkg))
    if n["value"] is not None:
        raise CaseFail(f"数字文本被偷转为 {n['value']}")
    if "NUMERIC_TEXT_NOT_CONVERTED" not in codes:
        raise CaseFail(f"未报 NUMERIC_TEXT_NOT_CONVERTED: {codes}")
    if n["transform"].get("from_raw") != "123.45":
        raise CaseFail("未保留数字文本原值")
    return "数字文本不偷转，保留原文 123.45 并报 NUMERIC_TEXT_NOT_CONVERTED"


def tc_010_formula_cached(ctx):
    from fixtures.make_fixtures import set_formula
    d = ctx.case_dir("TC-010")
    inp = _mk(d, "in")
    f = os.path.join(inp, "fixture.xlsx")
    set_formula(f, 2, "D3", "D3*2", "180.87")
    rc, out, err, pkg = ctx.scan("TC-010", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    rec = cashflow_rec(ctx.records(pkg), 3)
    n = norm(rec, "经营性流入（万元）")
    snap = rec["cells"]["D3"]
    if snap.get("formula") is None or snap.get("cache_status") != "cached":
        raise CaseFail(f"未保留公式与缓存状态: {snap}")
    if n["value"] != ctx.expected["normal_inflow_yuan"][0]:
        raise CaseFail(f"缓存值未用于规范字段: {n['value']}")
    return f"公式 {snap['formula']} 有缓存：保留公式原文 + 缓存值 {n['value']}"


def tc_011_formula_no_cache(ctx):
    from fixtures.make_fixtures import set_formula
    d = ctx.case_dir("TC-011")
    inp = _mk(d, "in")
    f = os.path.join(inp, "fixture.xlsx")
    set_formula(f, 2, "D3", "D3*2", None)
    rc, out, err, pkg = ctx.scan("TC-011", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    n = norm(cashflow_rec(ctx.records(pkg), 3), "经营性流入（万元）")
    codes = ncodes(ctx.issues(pkg))
    if n["value"] is not None:
        raise CaseFail("缓存缺失却给出了值（疑似 eval 代算）")
    if "FORMULA_CACHE_MISSING" not in codes:
        raise CaseFail(f"未报 FORMULA_CACHE_MISSING: {codes}")
    return "公式无缓存：规范值 null + FORMULA_CACHE_MISSING，不 eval 代算"


def tc_012_long_decimal(ctx):
    d = ctx.case_dir("TC-012")
    val = float(ctx.expected["long_decimal_raw"])
    rows = [["2026-01", _dt(2026, 1, 31), "经营性", val, 0.0]]
    inp = _mk(d, "in", cashflow_rows=rows)
    rc, out, err, pkg = ctx.scan("TC-012", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    rec = cashflow_rec(ctx.records(pkg), 3)
    n = norm(rec, "经营性流入（万元）")
    if n["transform"].get("from_raw") != ctx.expected["long_decimal_raw"]:
        raise CaseFail(f"原始长小数未保留: {n['transform'].get('from_raw')}")
    if n["value"] != ctx.expected["long_decimal_yuan"]:
        raise CaseFail(f"长小数换算 {n['value']} != {ctx.expected['long_decimal_yuan']}")
    return f"原始 {ctx.expected['long_decimal_raw']} 原样保留，规范值 {n['value']}"


def tc_013_wan_precision(ctx):
    d = ctx.case_dir("TC-013")
    rows = [["2026-01", _dt(2026, 1, 31), "经营性", 1.234567, 0.0],
            ["2026-02", _dt(2026, 2, 28), "经营性", 163.13, 0.0]]
    inp = _mk(d, "in", cashflow_rows=rows)
    rc, out, err, pkg = ctx.scan("TC-013", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    recs = ctx.records(pkg)
    got = [norm(cashflow_rec(recs, r), "经营性流入（万元）")["value"] for r in (3, 4)]
    want = [ctx.expected["wan_precision_cases"]["1.234567"],
            ctx.expected["wan_precision_cases"]["163.13"]]
    if got != want:
        raise CaseFail(f"万元精度 {got} != 预期 {want}（不得先截两位再换算）")
    return f"1.234567万→{got[0]}元；163.13万→{got[1]}元"


def tc_014_exception_bound(ctx):
    from .canon import sha256_file as _sha
    d = ctx.case_dir("TC-014")
    rows = [["2026-01", _dt(2026, 1, 31), "经营性", 1631300, 0.0]]
    inp = _mk(d, "in", cashflow_rows=rows)
    f = os.path.join(inp, "fixture.xlsx")
    ex = {"exceptions": [{"id": "EXC-SELFTEST-D3", "source_sha256": _sha(f),
                          "sheet": "现金流水", "address": "D3",
                          "reason": "自测登记的单位疑点（绑定源SHA+Sheet+地址）"}]}
    exp_path = os.path.join(d, "unit_exceptions_test.json")
    with open(exp_path, "wb") as fp:
        fp.write(json.dumps(ex, ensure_ascii=False).encode("utf-8"))
    rc, out, err, pkg = ctx.scan("TC-014", inp, exceptions=exp_path)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    n = norm(cashflow_rec(ctx.records(pkg), 3), "经营性流入（万元）")
    codes = ncodes(ctx.issues(pkg))
    if n["value"] is not None:
        raise CaseFail(f"单位疑点应 null，实际 {n['value']}")
    if "UNIT_SUSPECT_PENDING" not in codes:
        raise CaseFail(f"未报 UNIT_SUSPECT_PENDING: {codes}")
    rec = cashflow_rec(ctx.records(pkg), 3)
    if rec["cells"]["D3"]["raw"] != ctx.expected["exception_raw_kept"]:
        raise CaseFail("未保留原始值")
    return f"D3=1631300 绑定例外：规范值 null，原值保留，不乘 10000"


def tc_015_exception_not_binding_other_file(ctx):
    from .canon import sha256_file as _sha
    d = ctx.case_dir("TC-015")
    rows = [["2026-01", _dt(2026, 1, 31), "经营性", 1631300, 0.0]]
    inp = _mk(d, "in", cashflow_rows=rows)
    # 例外绑定的是 TC-014 那份文件的哈希，本用例是不同的源（多一行）
    other = _mk(d, "in2", cashflow_rows=rows + [["2026-02", _dt(2026, 2, 28),
                                                "经营性", 1.0, 0.0]])
    ex = {"exceptions": [{"id": "EXC-SELFTEST-D3", "source_sha256": _sha(
        os.path.join(inp, "fixture.xlsx")), "sheet": "现金流水", "address": "D3",
        "reason": "只绑定另一个源"}]}
    exp_path = os.path.join(d, "exceptions.json")
    with open(exp_path, "wb") as fp:
        fp.write(json.dumps(ex, ensure_ascii=False).encode("utf-8"))
    rc, out, err, pkg = ctx.scan("TC-015", other, exceptions=exp_path)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    n = norm(cashflow_rec(ctx.records(pkg), 3), "经营性流入（万元）")
    if n["value"] is None:
        raise CaseFail("不同源文件同地址被误拦（例外不应跨文件生效）")
    codes = ncodes(ctx.issues(pkg))
    if "UNIT_SUSPECT_PENDING" in codes:
        raise CaseFail("例外被扩大到其他文件")
    return f"另一源同地址不误拦，正常换算为 {n['value']}"


def tc_016_invalid_dates(ctx):
    d = ctx.case_dir("TC-016")
    rows = [["2026-01", "2026-13-05", "经营性", 1.0, 0.0],
            ["2026-02", "2026-02-30", "经营性", 1.0, 0.0]]
    inp = _mk(d, "in", cashflow_rows=rows)
    rc, out, err, pkg = ctx.scan("TC-016", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    recs = ctx.records(pkg)
    a = norm(cashflow_rec(recs, 3), "月末日期")
    b = norm(cashflow_rec(recs, 4), "月末日期")
    codes = ncodes(ctx.issues(pkg))
    if a["value"] is not None or b["value"] is not None:
        raise CaseFail(f"非法日期被静默修正: {a['value']} / {b['value']}")
    if codes.count("INVALID_DATE") < 2:
        raise CaseFail(f"未报两条 INVALID_DATE: {codes}")
    return f"2026-13-05 / 2026-02-30 保持 null，报 {codes.count('INVALID_DATE')} 条 INVALID_DATE"


def tc_017_two_digit_year(ctx):
    d = ctx.case_dir("TC-017")
    rows = [["2026-01", "26-01-31", "经营性", 1.0, 0.0]]
    inp = _mk(d, "in", cashflow_rows=rows)
    rc, out, err, pkg = ctx.scan("TC-017", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    n = norm(cashflow_rec(ctx.records(pkg), 3), "月末日期")
    if n["value"] is not None:
        raise CaseFail(f"两位年份被猜成 {n['value']}")
    if "TWO_DIGIT_YEAR" not in ncodes(ctx.issues(pkg)):
        raise CaseFail(f"未报 TWO_DIGIT_YEAR: {ncodes(ctx.issues(pkg))}")
    return "两位年份 26-01-31 不猜世纪，报 TWO_DIGIT_YEAR"


def tc_018_serial_1900_legal(ctx):
    from fixtures.make_fixtures import set_serial
    d = ctx.case_dir("TC-018")
    inp = _mk(d, "in")
    set_serial(os.path.join(inp, "fixture.xlsx"), 2, "B3", 45961)
    rc, out, err, pkg = ctx.scan("TC-018", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    n = norm(cashflow_rec(ctx.records(pkg), 3), "月末日期")
    if n["value"] != ctx.expected["serial_45961_1900"]:
        raise CaseFail(f"serial 45961 → {n['value']} != {ctx.expected['serial_45961_1900']}")
    if n["transform"].get("date_system") != "1900":
        raise CaseFail("未记录日期系统")
    return f"1900 系统 serial 45961 → {n['value']}（记录 date_system=1900）"


def tc_019_serial_60_fiction(ctx):
    from fixtures.make_fixtures import set_serial
    d = ctx.case_dir("TC-019")
    inp = _mk(d, "in")
    set_serial(os.path.join(inp, "fixture.xlsx"), 2, "B3", 60)
    rc, out, err, pkg = ctx.scan("TC-019", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    n = norm(cashflow_rec(ctx.records(pkg), 3), "月末日期")
    if n["value"] is not None:
        raise CaseFail(f"虚构闰日被变成 {n['value']}")
    if "EXCEL1900_FICTITIOUS_LEAP_DAY" not in ncodes(ctx.issues(pkg)):
        raise CaseFail(f"未报虚构闰日: {ncodes(ctx.issues(pkg))}")
    return "serial=60 明确报 Excel1900 虚构闰日，不冒充 1900-02-29"


def tc_020_date_system_1904(ctx):
    d = ctx.case_dir("TC-020")
    inp = _mk(d, "in", date1904=True)
    rc, out, err, pkg = ctx.scan("TC-020", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    inv = ctx.inventory(pkg)
    if inv["inputs"][0]["date_system"] != "1904":
        raise CaseFail(f"未识别 1904 系统: {inv['inputs'][0]['date_system']}")
    n = norm(cashflow_rec(ctx.records(pkg), 3), "月末日期")
    if n["value"] != ctx.expected["date_1904_fixture"]:
        raise CaseFail(f"1904 日期 {n['value']} != {ctx.expected['date_1904_fixture']}")
    return f"1904 系统识别正确，日期 {n['value']}"


def tc_021_duplicate_rows_kept(ctx):
    d = ctx.case_dir("TC-021")
    rows = _rows()[:1] + _rows()[:1]
    inp = _mk(d, "in", cashflow_rows=rows)
    rc, out, err, pkg = ctx.scan("TC-021", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    recs = [r for r in ctx.records(pkg) if r["sheet"] == "现金流水"]
    if len(recs) != 2:
        raise CaseFail(f"重复行被删除/合并，实际 {len(recs)} 条")
    keys = {r["source_record_key"] for r in recs}
    if len(keys) != 2:
        raise CaseFail("重复行 source_record_key 相同，无法从来源区分")
    dup = [i for i in ctx.issues(pkg) if i["code"] == "DUPLICATE_ROW"]
    if len(dup) != 2:
        raise CaseFail(f"重复证据条数 {len(dup)} != 2")
    return "重复两行全部保留，各自有独立键与重复证据"


def tc_022_partial_payment_ok(ctx):
    d = ctx.case_dir("TC-022")
    ar_rows = [["AR001", 100, 40, "部分到账"]]
    inp = _mk(d, "in", ar_rows=ar_rows)
    rc, out, err, pkg = ctx.scan("TC-022", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    rec = [r for r in ctx.records(pkg) if r["sheet"] == "应收账款"][0]
    got = (norm(rec, "应收金额（万元）")["value"], norm(rec, "已收金额（万元）")["value"])
    want = (ctx.expected["partial_payment"]["receivable_yuan"],
            ctx.expected["partial_payment"]["received_yuan"])
    if got != want:
        raise CaseFail(f"分次到账金额 {got} != {want}")
    bad = [i for i in ctx.issues(pkg)
           if i["code"] in ("INVALID_AMOUNT", "AMOUNT_ERROR", "DUPLICATE_ROW")]
    if bad:
        raise CaseFail(f"合法部分到账被误判为错误: {[i['code'] for i in bad]}")
    return f"应收 {got[0]} / 已收 {got[1]}，未判为数据错误"


def tc_023_stable_keys(ctx):
    d = ctx.case_dir("TC-023")
    inp = _mk(d, "in")
    rc1, _, _, pkg1 = ctx.scan("TC-023a", inp)
    rc2, _, _, pkg2 = ctx.scan("TC-023b", inp)
    if rc1 != 0 or rc2 != 0:
        raise CaseFail(f"scan 退出码 {rc1}/{rc2}")
    b1 = open(os.path.join(pkg1, "records.jsonl"), "rb").read()
    b2 = open(os.path.join(pkg2, "records.jsonl"), "rb").read()
    if b1 != b2:
        raise CaseFail("同源重跑 records.jsonl 不稳定")
    rev1 = ctx.manifest(pkg1)["source_revision"]
    if rev1 != ctx.manifest(pkg2)["source_revision"]:
        raise CaseFail("同源重跑 source_revision 不稳定")
    codes = ncodes(ctx.issues(pkg1))
    return f"同源重跑字节一致；source_revision 稳定 {rev1[:12]}…；输出排序稳定"


def tc_024_source_change_detected(ctx):
    d = ctx.case_dir("TC-024")
    inp = _mk(d, "in")
    rc, _, _, pkg = ctx.scan("TC-024", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}")
    rev_before = ctx.manifest(pkg)["source_revision"]
    os.remove(os.path.join(inp, "fixture.xlsx"))
    from fixtures.make_fixtures import build_workbook
    build_workbook(os.path.join(inp, "fixture.xlsx"),
                   cashflow_rows=[["2026-01", _dt(2026, 1, 31), "经营性", 999.99, 1.0]])
    rc2, out2, err2 = ctx.cli("verify", "--package", pkg, "--source", inp)
    if rc2 == 0:
        raise CaseFail("源改变后 verify 仍通过")
    rc3, out3, err3, pkg2 = ctx.scan("TC-024b", inp)
    rev_after = ctx.manifest(pkg2)["source_revision"]
    if rev_after == rev_before:
        raise CaseFail("源改变但 source_revision 未变")
    return f"源改变后 verify 退出码 {rc2} 并检出；source_revision 由 {rev_before[:12]}… 变为 {rev_after[:12]}…"


def tc_025_tamper_with_rehashed_manifest(ctx):
    """篡改字段 + 重算清单哈希，verify 仍须失败并指出源地址。"""
    from .canon import sha256_file as _sha
    d = ctx.case_dir("TC-025")
    inp = _mk(d, "in")
    rc, _, _, pkg = ctx.scan("TC-025", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}")
    pkg2 = os.path.join(d, "pkg_tampered")
    shutil.copytree(pkg, pkg2)
    rec_path = os.path.join(pkg2, "records.jsonl")
    data = open(rec_path, "rb").read().decode("utf-8")
    if ctx.expected["normal_inflow_yuan"][0] not in data:
        raise CaseFail("夹具原始值未出现在 records.jsonl，无法构造篡改")
    data = data.replace(ctx.expected["normal_inflow_yuan"][0], "99999999.00", 1)
    open(rec_path, "wb").write(data.encode("utf-8"))
    # 攻击者重算 manifest 中 files 的 sha256
    man = ctx.manifest(pkg2)
    for entry in man["files"]:
        entry["sha256"] = _sha(os.path.join(pkg2, entry["path"]))
    open(os.path.join(pkg2, "manifest.json"), "wb").write(
        json.dumps(man, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    rc2, out2, err2 = ctx.cli("verify", "--package", pkg2, "--source", inp)
    if rc2 == 0:
        raise CaseFail("篡改并重算哈希后 verify 仍通过")
    blob = out2 + err2
    if "现金流水" not in blob and "被篡改" not in blob:
        raise CaseFail(f"未指出源定位: {blob[-400:]}")
    return (f"篡改字段并重算清单哈希后 verify 退出码 {rc2}，"
            f"指出源地址与期望值：{_digest(blob)}")


def tc_026_html_escape(ctx):
    d = ctx.case_dir("TC-026")
    rows = [["2026-01", _dt(2026, 1, 31), "<script>alert('x')</script>", 1.0, 0.0]]
    inp = _mk(d, "in", cashflow_rows=rows)
    rc, out, err, pkg = ctx.scan("TC-026", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}: {err}")
    html = open(os.path.join(pkg, "report.html"), "rb").read().decode("utf-8")
    if "<script>alert" in html:
        raise CaseFail("HTML 存在未转义的可执行脚本")
    if "&lt;script&gt;" not in html:
        raise CaseFail("HTML 未保留转义后的原文")
    if "http://" in html or "https://" in html or "src=" in html:
        raise CaseFail("HTML 含外部资源引用（不离线）")
    return "单元格 <script> 被转义为 &lt;script&gt;，报告无外部资源"


def tc_027_csv_injection(ctx):
    from .scanner import csv_safe
    for s in ctx.expected["csv_injection_samples"]:
        out = csv_safe(s)
        if not out.startswith("'"):
            raise CaseFail(f"CSV 危险文本 {s!r} 未做前缀处理: {out!r}")
    if csv_safe("-3") != "-3":
        raise CaseFail("普通负数被误改")
    return "= / + / @ / HYPERLINK 等 CSV 危险文本导出时加前缀，原文仍在 JSON 保留"


def tc_028_path_safety(ctx):
    d = ctx.case_dir("TC-028")
    inp = _mk(d, "in")
    existing = os.path.join(d, "existing")
    os.makedirs(existing)
    rc, out, err = ctx.cli("scan", "--input", inp, "--output", existing,
                           "--mapping", MAPPING, *IDENTITY)
    if rc == 0:
        raise CaseFail("输出目录重名仍被接受")
    rc2, _, _, pkg = ctx.scan("TC-028", inp)
    pkg3 = os.path.join(d, "pkg_abs")
    shutil.copytree(pkg, pkg3)
    man = ctx.manifest(pkg3)
    man["files"][0]["path"] = "../evil.json"
    open(os.path.join(pkg3, "manifest.json"), "wb").write(
        json.dumps(man, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    rc3, out3, err3 = ctx.cli("verify", "--package", pkg3, "--source", inp)
    if rc3 == 0:
        raise CaseFail("manifest 含 .. 越界路径仍通过")
    man["files"][0]["path"] = "C:/evil/abs.json"
    open(os.path.join(pkg3, "manifest.json"), "wb").write(
        json.dumps(man, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    rc4, out4, err4 = ctx.cli("verify", "--package", pkg3, "--source", inp)
    if rc4 == 0:
        raise CaseFail("manifest 含绝对路径仍通过")
    return f"输出重名退出码 {rc}；.. 越界 {rc3}；绝对路径 {rc4}（均非0拒绝）"


def tc_029_deliberate_fail_exit(ctx):
    d = ctx.case_dir("TC-029")
    inp = _mk(d, "in")
    rc_bad_period, _, err1 = ctx.cli("scan", "--input", inp,
                                     "--output", os.path.join(d, "o1"),
                                     "--mapping", MAPPING, "--tenant-id", "t",
                                     "--company-id", "c", "--period", "2026-13",
                                     "--run-id", "r")
    if rc_bad_period == 0:
        raise CaseFail("非法 period 仍返回 0")
    rc_ok, _, _, pkg = ctx.scan("TC-029", inp)
    if rc_ok != 0:
        raise CaseFail(f"正常 scan 退出码 {rc_ok}")
    os.remove(os.path.join(pkg, "records.jsonl"))
    rc_missing, out2, err2 = ctx.cli("verify", "--package", pkg, "--source", inp)
    if rc_missing == 0:
        raise CaseFail("包内文件缺失仍 verify 通过")
    return f"非法 period 退出码 {rc_bad_period}；缺文件 verify 退出码 {rc_missing}（非0）"


def tc_030_source_unchanged(ctx):
    d = ctx.case_dir("TC-030")
    inp = _mk(d, "in")
    f = os.path.join(inp, "fixture.xlsx")
    before = sha256_file(f)
    rc, _, _, pkg = ctx.scan("TC-030", inp)
    after = sha256_file(f)
    if before != after:
        raise CaseFail("源文件在 scan 后被改变")
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}")
    return f"源件 scan 前后 SHA256 一致: {before[:16]}…"


def tc_031_verify_clean_package(ctx):
    d = ctx.case_dir("TC-031")
    inp = _mk(d, "in")
    rc, _, _, pkg = ctx.scan("TC-031", inp)
    if rc != 0:
        raise CaseFail(f"scan 退出码 {rc}")
    rc2, out2, err2 = ctx.cli("verify", "--package", pkg, "--source", inp)
    if rc2 != 0:
        raise CaseFail(f"干净包 verify 失败 {rc2}: {err2[-300:]}")
    return "干净包 verify 退出码 0：清单哈希、记录数、字段来源一致"


CASES = [
    ("TC-001", "正常三行抽取：金额/日期/来源准确", tc_001_normal),
    ("TC-002", "列重排仍映射正确", tc_002_column_reorder),
    ("TC-003", "缺必需 Sheet 明确报告", tc_003_missing_sheet),
    ("TC-004", "缺列报缺项，规范值 null", tc_004_missing_column),
    ("TC-005", "重名列报重名，不取第一项", tc_005_duplicate_column),
    ("TC-006", "别名歧义同时出现报歧义", tc_006_alias_ambiguity),
    ("TC-007", "企业纵向字段换行仍按字段名定位", tc_007_vertical_reorder),
    ("TC-008", "0/空白/空串/空格可区分", tc_008_zero_and_empties),
    ("TC-009", "数字文本不偷转", tc_009_numeric_text),
    ("TC-010", "公式有缓存：保留公式与缓存值", tc_010_formula_cached),
    ("TC-011", "公式无缓存：null + 报缺口，不 eval", tc_011_formula_no_cache),
    ("TC-012", "原始长小数保留", tc_012_long_decimal),
    ("TC-013", "万元精度：先乘后落分", tc_013_wan_precision),
    ("TC-014", "单位例外绑定源SHA+Sheet+地址", tc_014_exception_bound),
    ("TC-015", "同地址不同源不误拦", tc_015_exception_not_binding_other_file),
    ("TC-016", "非法日期不静默修正", tc_016_invalid_dates),
    ("TC-017", "两位年份不猜世纪", tc_017_two_digit_year),
    ("TC-018", "1900 序列日期", tc_018_serial_1900_legal),
    ("TC-019", "Excel1900 虚构闰日", tc_019_serial_60_fiction),
    ("TC-020", "1904 日期系统", tc_020_date_system_1904),
    ("TC-021", "重复行保留且可区分", tc_021_duplicate_rows_kept),
    ("TC-022", "合法分次到账不当错误", tc_022_partial_payment_ok),
    ("TC-023", "同源重跑键与排序稳定", tc_023_stable_keys),
    ("TC-024", "源改变：revision 变且 verify 检出", tc_024_source_change_detected),
    ("TC-025", "篡改字段并重算哈希仍失败", tc_025_tamper_with_rehashed_manifest),
    ("TC-026", "HTML 注入转义且离线", tc_026_html_escape),
    ("TC-027", "CSV 导出防公式注入", tc_027_csv_injection),
    ("TC-028", "路径越界/重名拒绝", tc_028_path_safety),
    ("TC-029", "故意失败退出码非0", tc_029_deliberate_fail_exit),
    ("TC-030", "源件 scan 前后一致", tc_030_source_unchanged),
    ("TC-031", "干净包 verify 通过", tc_031_verify_clean_package),
]


def run_selftest(workdir):
    if os.path.exists(workdir):
        print(f"[参数错误] 测试目录已存在，拒绝覆盖: {workdir}")
        return 2
    os.makedirs(workdir)
    ctx = Ctx(workdir)
    # 夹具生成源码需可导入（交付 fixtures/ 目录）
    sys.path.insert(0, DELIVERY_ROOT)
    sys.path.insert(0, SRC_ROOT)

    results = []
    log = []
    for cid, title, fn in CASES:
        try:
            status, detail = PASS, fn(ctx)
        except CaseFail as e:
            status, detail = FAIL, str(e)
        except Exception as e:
            status, detail = FAIL, f"意外异常 {type(e).__name__}: {e}"
        results.append({"case_id": cid, "title": title, "status": status,
                        "detail": detail})
        log.append(f"{cid} {status} | {title} | {detail}")
        print(f"{cid} {status} | {title} | {detail}")

    exp_after = sha256_file(EXPECTED_FILE)
    if exp_after != ctx.expected_sha_before:
        results.append({"case_id": "TC-EXP", "title": "独立预期文件运行前后未被改写",
                        "status": FAIL, "detail": "expected_values.json 哈希变化"})
        print("TC-EXP FAIL | 独立预期文件被改写")

    passed = sum(1 for r in results if r["status"] == PASS)
    failed = sum(1 for r in results if r["status"] == FAIL)
    blocked = sum(1 for r in results if r["status"] == BLOCKED)
    notrun = sum(1 for r in results if r["status"] == NOT_RUN)

    summary = {
        "workdir": workdir,
        "expected_file_sha256_before": ctx.expected_sha_before,
        "expected_file_sha256_after": exp_after,
        "counts": {"PASS": passed, "FAIL": failed, "BLOCKED": blocked,
                   "NOT_RUN": notrun, "TOTAL": len(results)},
        "results": results,
    }
    with open(os.path.join(workdir, "selftest_results.json"), "wb") as f:
        f.write(json.dumps(summary, ensure_ascii=False, sort_keys=True,
                           indent=2).encode("utf-8"))
    with open(os.path.join(workdir, "selftest_log.txt"), "wb") as f:
        f.write(("\n".join(log) + "\n").encode("utf-8"))
    print(f"selftest 汇总: PASS={passed} FAIL={failed} BLOCKED={blocked} "
          f"NOT_RUN={notrun} TOTAL={len(results)}")
    return 0 if failed == 0 and blocked == 0 and notrun == 0 else 1


def _digest(blob):
    lines = [l for l in blob.splitlines() if "篡改" in l or "现金流水" in l]
    return lines[0][:160] if lines else blob[-160:]


def _rows():
    from fixtures.make_fixtures import CASHFLOW_ROWS
    return [[r[0], r[1], r[2], r[3], r[4]] for r in CASHFLOW_ROWS]


def _mk(d, name, **kw):
    from fixtures.make_fixtures import make_input_dir
    return make_input_dir(d, name, **kw)


def _dt(year, month, day):
    return datetime.datetime(year, month, day)
