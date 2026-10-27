# -*- coding: utf-8 -*-
"""
WB-ENG-001 契约自动校验脚本
================================
校验对象（相对本脚本所在 v1/ 目录）：
  candidate/docs/千问办公_MySQL_MCP工具定义_v1.1.json
  candidate/sql/init_v1.1.sql

校验分四节：
  A. 工具 JSON 结构静态断言（14 工具集合 / 24 event_type / 4 risk_level /
     5 scenario / additionalProperties:false / 条件必填 / 验收报告 5 处违规修复）
  B. JSON Schema 正反例实测（jsonschema 4.26.0，真实 validate 调用）
  C. DDL 静态解析核对（表/视图/列/类型/约束与契约映射）
  D. 真实 MySQL 执行 → 恒 BLOCKED（WB-ENG-001 纪律：不在服务器执行 DDL；
     静态解析通过不等于 MySQL 执行通过）

输出：终端打印 + test-output/validate_output.txt（由运行命令重定向）。
退出码：0=全部 PASS/BLOCKED 无 FAIL；1=存在 FAIL。

结果口径：PASS / FAIL / SKIP / BLOCKED 分开统计，禁止虚报全绿。
"""
import json
import re
import sys
from pathlib import Path

V1 = Path(__file__).resolve().parent.parent
JSON_PATH = V1 / "candidate" / "docs" / "千问办公_MySQL_MCP工具定义_v1.1.json"
SQL_PATH = V1 / "candidate" / "sql" / "init_v1.1.sql"

RESULTS = []  # (section, item, status, detail)

def report(section, item, status, detail=""):
    RESULTS.append((section, item, status, detail))
    print(f"[{status:7}] {section} | {item}" + (f" | {detail}" if detail else ""))

# 契约常量（依据：规格裁决 A1/A2.1/A2.2/A5、D10、D11；验收报告第三节）
EXPECTED_TOOLS = {
    "log_to_mysql", "query_rule_stats", "query_audit_by_event",
    "log_feedback", "query_feedback_stats",
    "save_param_template", "load_param_template",
    "log_exception", "query_exception_stats",
    "log_stress_test", "verify_payment",
    "rf_predict", "load_da_coefficients", "save_da_coefficients",
}
EXPECTED_EVENT_TYPES = {
    "daily_check", "quality_check", "deada_score", "rf_predict", "risk_assessment",
    "approval", "exception", "config_change", "assumption_analysis", "industry_compare",
    "param_adjust", "feedback", "onboarding", "root_cause", "dynamic_threshold",
    "stress_test", "exception_review", "audit_triggered", "payment_verified",
    "da_coefficients_updated", "risk_warning", "tracking_changed",
    "parameter_changed", "task_result",
}
EXPECTED_RISK_LEVELS = {"green", "yellow", "red", "unknown"}
EXPECTED_SCENARIOS = {"receivable_shock", "financing_shock", "cost_shock",
                      "dual_shock", "combined_shock"}
EXPECTED_TABLES = {
    "mcp_request_ledger", "audit_log", "feedback_log", "param_template",
    "exception_log", "stress_test_log", "payment_verify_log",
    "quality_log", "deada_score_log", "rf_predict_log", "da_coefficient",
}
EXPECTED_VIEWS = {
    "v_record_active", "v_rule_stats", "v_feedback_label_counts", "v_exception_stats",
    "v_stress_run_progress", "v_verified_payment_sum", "v_template_published_latest",
    "v_quality_active", "v_deada_active", "v_rf_active",
}

# ============================== SECTION A =====================================
def section_a(doc):
    tools = doc.get("tools", [])
    names = [t.get("name") for t in tools]

    # A1 工具名称集合精确匹配
    if set(names) == EXPECTED_TOOLS and len(names) == 14 and len(set(names)) == 14:
        report("A-JSON静态", "14工具名称集合精确匹配", "PASS", f"实际{len(names)}个")
    else:
        report("A-JSON静态", "14工具名称集合精确匹配", "FAIL",
               f"多:{set(names)-EXPECTED_TOOLS or '无'} 缺:{EXPECTED_TOOLS-set(names) or '无'} 重复:{len(names)-len(set(names))}")

    by_name = {t["name"]: t for t in tools}

    # A2 每工具 additionalProperties:false
    bad = [n for n, t in by_name.items()
           if t.get("inputSchema", {}).get("additionalProperties") is not False]
    if not bad:
        report("A-JSON静态", "全部工具 additionalProperties:false", "PASS", "14/14")
    else:
        report("A-JSON静态", "全部工具 additionalProperties:false", "FAIL", f"违规:{bad}")

    # A3 log_to_mysql event_type 24 枚举精确集合
    et = by_name["log_to_mysql"]["inputSchema"]["properties"]["event_type"]["enum"]
    if set(et) == EXPECTED_EVENT_TYPES and len(et) == 24:
        report("A-JSON静态", "log_to_mysql event_type 24值精确集合", "PASS")
    else:
        report("A-JSON静态", "log_to_mysql event_type 24值精确集合", "FAIL",
               f"多:{set(et)-EXPECTED_EVENT_TYPES} 缺:{EXPECTED_EVENT_TYPES-set(et)}")

    # A4 query_audit_by_event event_type 同样 24 值
    et2 = by_name["query_audit_by_event"]["inputSchema"]["properties"]["event_type"]["enum"]
    ok = set(et2) == EXPECTED_EVENT_TYPES and len(et2) == 24
    report("A-JSON静态", "query_audit_by_event event_type 24值", "PASS" if ok else "FAIL")

    # A5 risk_level 四值（log_to_mysql / query_rule_stats / query_audit_by_event / log_stress_test）
    rl_bad = []
    for tn in ["log_to_mysql", "query_rule_stats", "query_audit_by_event", "log_stress_test"]:
        props = by_name[tn]["inputSchema"]["properties"]
        if "risk_level" in props:
            if set(props["risk_level"].get("enum", [])) != EXPECTED_RISK_LEVELS:
                rl_bad.append(tn)
    report("A-JSON静态", "risk_level=green/yellow/red/unknown（4处）",
           "PASS" if not rl_bad else "FAIL", f"违规:{rl_bad}" if rl_bad else "4/4 一致")

    # A6 条件必填：risk_warning 与 risk_assessment 两条 allOf
    allof = by_name["log_to_mysql"]["inputSchema"].get("allOf", [])
    cond_consts = [c.get("if", {}).get("properties", {}).get("event_type", {}).get("const")
                   for c in allof]
    cond_req = all(set(c.get("then", {}).get("required", [])) ==
                   {"rule_id", "rule_version", "risk_level"} for c in allof)
    if set(cond_consts) == {"risk_warning", "risk_assessment"} and len(allof) == 2 and cond_req:
        report("A-JSON静态", "条件必填 risk_warning+risk_assessment 两条", "PASS")
    else:
        report("A-JSON静态", "条件必填 risk_warning+risk_assessment 两条", "FAIL",
               f"allOf条件:{cond_consts}")

    # A7 scenario 五值
    sc = by_name["log_stress_test"]["inputSchema"]["properties"]["scenario"]["enum"]
    ok = set(sc) == EXPECTED_SCENARIOS and len(sc) == 5
    report("A-JSON静态", "log_stress_test scenario 5值（A5扩枚举）",
           "PASS" if ok else "FAIL", f"实际:{sc}" if not ok else "")

    # A8 验收报告违规1：verify_payment 输入不得含 status
    vp = by_name["verify_payment"]["inputSchema"]
    ok = "status" not in vp.get("properties", {}) and "status" not in vp.get("required", [])
    report("A-JSON静态", "verify_payment 无 status 输入（违规1修复）", "PASS" if ok else "FAIL")

    # A9 验收报告违规2：log_exception 无 approver、有 approval_ref 必填
    le = by_name["log_exception"]["inputSchema"]
    ok = ("approver" not in le.get("properties", {})
          and "approval_ref" in le.get("required", []))
    report("A-JSON静态", "log_exception 无approver/有approval_ref（违规2修复）",
           "PASS" if ok else "FAIL")

    # A10 验收报告违规3：save_param_template 必填 template_version、无 source
    spt = by_name["save_param_template"]["inputSchema"]
    ok = ("template_version" in spt.get("required", [])
          and "source" not in spt.get("properties", {}))
    report("A-JSON静态", "save_param_template 有template_version/无source（违规3修复）",
           "PASS" if ok else "FAIL")

    # A11 验收报告违规4：log_to_mysql 幂等三件套必填
    lm_req = set(by_name["log_to_mysql"]["inputSchema"]["required"])
    ok = {"request_id", "source_ref", "occurred_at"} <= lm_req
    report("A-JSON静态", "log_to_mysql 幂等三件套必填（违规4修复）", "PASS" if ok else "FAIL")

    # A12 验收报告违规5：log_feedback 字段集
    #  R-01 修订：predicted_value/actual_value 由无条件必填改为按 accuracy_label 条件必填，
    #  故无条件必填从 12 项降为 10 项；两金额改为可空（["string","null"]）。
    lf_req = set(by_name["log_feedback"]["inputSchema"]["required"])
    expect_base = {"request_id", "source_ref", "occurred_at", "metric_code",
                   "actual_source_ref", "evaluation_version", "currency",
                   "accuracy_label", "forecast_start_at", "forecast_end_at"}
    props = by_name["log_feedback"]["inputSchema"]["properties"]
    ok = (expect_base == lf_req and "accuracy" not in props and "deviation" not in props)
    report("A-JSON静态", "log_feedback 10项无条件必填+无accuracy/deviation（违规5修复+R-01）",
           "PASS" if ok else "FAIL",
           "" if ok else f"多:{lf_req-expect_base} 缺:{expect_base-lf_req}")

    # A13 金额字段 pattern（元、最多两位小数）+ R-01 可空
    money_ok = True
    for tn, fld in [("log_feedback", "predicted_value"), ("log_feedback", "actual_value"),
                    ("log_exception", "amount")]:
        p = by_name[tn]["inputSchema"]["properties"][fld]
        if "pattern" not in p:
            money_ok = False
    report("A-JSON静态", "金额字段=十进制字符串+pattern（元，D12）",
           "PASS" if money_ok else "FAIL")
    for fld in ("predicted_value", "actual_value"):
        t = by_name["log_feedback"]["inputSchema"]["properties"][fld].get("type")
        nullable = t == ["string", "null"] or t == ["null", "string"]
        report("A-JSON静态", f"R-01 log_feedback.{fld} 可空（pending 无实际值）",
               "PASS" if nullable else "FAIL", f"type={t}")

    # A13b R-02：audit_id 必须是十进制数字字符串（对应 audit_log.id BIGINT UNSIGNED）
    aid = by_name["log_feedback"]["inputSchema"]["properties"]["audit_id"]
    ok = aid.get("pattern") == "^[0-9]{1,20}$" and aid.get("maxLength") == 20
    report("A-JSON静态", "R-02 audit_id 为十进制数字字符串（非业务串）",
           "PASS" if ok else "FAIL", f"pattern={aid.get('pattern')}")

    # A14 新工具必备字段
    rf_req = set(by_name["rf_predict"]["inputSchema"]["required"])
    ok = {"features", "feature_names", "feature_schema_version", "model_version"} <= rf_req
    report("A-JSON静态", "rf_predict 必填特征对+双版本", "PASS" if ok else "FAIL")
    ldc_req = set(by_name["load_da_coefficients"]["inputSchema"]["required"])
    ok = {"industry_key", "coefficient_version"} <= ldc_req
    report("A-JSON静态", "load_da_coefficients 必填精确版本", "PASS" if ok else "FAIL")

# ============================== SECTION B =====================================
def section_b(doc):
    from jsonschema import Draft202012Validator
    by_name = {t["name"]: t for t in doc["tools"]}

    def check(tool, args, expect_valid, label):
        schema = by_name[tool]["inputSchema"]
        v = Draft202012Validator(schema)
        errors = list(v.iter_errors(args))
        actual_valid = len(errors) == 0
        ok = actual_valid == expect_valid
        status = "PASS" if ok else "FAIL"
        detail = f"期望{'合法' if expect_valid else '拒绝'}，实际{'合法' if actual_valid else '拒绝'}"
        if errors and not expect_valid:
            detail += f"（首错: {errors[0].json_path or '/'}: {errors[0].message[:60]}）"
        report("B-Schema正反例", label, status, detail)

    base_audit = {"request_id": "r1", "source_ref": "s1",
                  "occurred_at": "2026-10-22T10:00:00+08:00",
                  "event_type": "daily_check", "payload": {}}

    # 正例
    check("log_to_mysql", {**base_audit, "event_type": "risk_warning",
                           "rule_id": "r", "rule_version": "1", "risk_level": "yellow"},
          True, "正例: risk_warning 三件套齐全")
    check("log_to_mysql", {**base_audit, "event_type": "risk_assessment",
                           "rule_id": "r", "rule_version": "1", "risk_level": "unknown"},
          True, "正例: risk_assessment + unknown 灯")
    check("log_to_mysql", base_audit, True, "正例: daily_check 无需三件套")
    # 反例
    check("log_to_mysql", {**base_audit, "event_type": "risk_warning"},
          False, "反例: risk_warning 缺 rule_id/rule_version/risk_level")
    check("log_to_mysql", {**base_audit, "event_type": "risk_assessment",
                           "rule_id": "r", "rule_version": "1"},
          False, "反例: risk_assessment 缺 risk_level")
    check("log_to_mysql", {**base_audit, "event_type": "not_a_real_event"},
          False, "反例: 非法 event_type 枚举")
    check("log_to_mysql", {**base_audit, "risk_level": "greenx",
                           "event_type": "risk_warning", "rule_id": "r", "rule_version": "1"},
          False, "反例: 非法 risk_level")
    check("log_to_mysql", {**base_audit, "extra_field": 1},
          False, "反例: 多余字段（additionalProperties:false）")
    check("log_to_mysql", {"source_ref": "s1", "occurred_at": "2026-10-22T10:00:00+08:00",
                           "event_type": "daily_check", "payload": {}},
          False, "反例: 缺必填 request_id")

    vp = {"request_id": "r1", "source_ref": "s1",
          "occurred_at": "2026-10-22T10:00:00+08:00",
          "payment_id": "p1", "method": "bank_api", "evidence_ref": "oss://x"}
    check("verify_payment", vp, True, "正例: verify_payment 合法输入")
    check("verify_payment", {**vp, "status": "verified"},
          False, "反例: verify_payment 携带 status（模型自证）")
    check("verify_payment", {**vp, "method": "cash"},
          False, "反例: 非法 method 枚举")

    st = {"request_id": "r1", "source_ref": "s1",
          "occurred_at": "2026-10-22T10:00:00+08:00",
          "run_id": "run1", "scenario": "financing_shock", "scenario_version": "v1",
          "input_snapshot": {}, "result_snapshot": {}, "risk_level": "red"}
    check("log_stress_test", st, True, "正例: financing_shock（A5新增枚举）")
    check("log_stress_test", {**st, "scenario": "fx_shock"},
          False, "反例: 非法 scenario 枚举")
    check("log_stress_test", {**st, "risk_level": "unknown"},
          True, "正例: stress risk_level=unknown（D10）")

    le = {"request_id": "r1", "source_ref": "s1",
          "occurred_at": "2026-10-22T10:00:00+08:00",
          "dept": "d1", "amount": "125000.00", "currency": "CNY",
          "reason": "x", "approval_ref": "appr-1"}
    check("log_exception", le, True, "正例: log_exception 合法")
    check("log_exception", {**le, "approver": "张三"},
          False, "反例: log_exception 携带 approver 姓名")
    check("log_exception", {**le, "amount": "1.234"},
          False, "反例: 金额超过两位小数")
    check("log_exception", {**le, "amount": "1234567890123456789.00"},
          False, "反例: 金额整数位超18位（DECIMAL(20,2)容量外）")
    check("log_exception", {k: v for k, v in le.items() if k != "approval_ref"},
          False, "反例: 缺 approval_ref")

    rf = {"request_id": "r1", "source_ref": "s1",
          "occurred_at": "2026-10-22T10:00:00+08:00",
          "eval_date": "2026-10-22", "features": [0.1] * 15,
          "feature_names": [f"f{i}" for i in range(15)],
          "feature_schema_version": "fs-v1", "model_version": "rf-v1"}
    check("rf_predict", rf, True, "正例: rf_predict 15维（非30维也可，D13）")
    check("rf_predict", {**rf, "features": []},
          False, "反例: features 空数组（minItems:1）")
    check("rf_predict", {k: v for k, v in rf.items() if k != "feature_schema_version"},
          False, "反例: 缺 feature_schema_version")
    check("rf_predict", {**rf, "feature_names": "not_array"},
          False, "反例: feature_names 非数组")

    fb = {"request_id": "r1", "source_ref": "s1",
          "occurred_at": "2026-10-22T10:00:00+08:00",
          "metric_code": "m1", "actual_source_ref": "s2",
          "evaluation_version": "ev1", "predicted_value": "100.00",
          "actual_value": "99.50", "currency": "CNY",
          "accuracy_label": "accurate",
          "forecast_start_at": "2026-10-01T00:00:00+08:00",
          "forecast_end_at": "2026-10-31T00:00:00+08:00",
          "audit_id": "1024"}
    check("log_feedback", fb, True, "正例: log_feedback 合法（audit_id 分支，R-02 数字形态）")
    check("log_feedback", {k: v for k, v in fb.items() if k != "audit_id"},
          False, "反例: audit_id/forecast_id 均缺（anyOf）")
    check("log_feedback", {**fb, "accuracy_label": "mostly_right"},
          False, "反例: 非法 accuracy_label 枚举")

    # --- R-01 正反例：pending 无实际值必须合法，accurate/inaccurate 缺实际值必须被拒 ---
    fb_pending = {**fb, "accuracy_label": "pending"}
    fb_pending_omit = {k: v for k, v in fb_pending.items()
                       if k not in ("predicted_value", "actual_value")}
    check("log_feedback", fb_pending_omit, True,
          "R-01 正例: pending 省略两金额（不得被迫填 0）")
    check("log_feedback", {**fb_pending, "predicted_value": None, "actual_value": None},
          True, "R-01 正例: pending 显式 null 两金额")
    check("log_feedback", {**fb_pending, "actual_value": "0.00"},
          True, "R-01 说明: pending 携带 actual_value 也允许（按 Codex 处置不增设禁止）")
    fb_acc_no_actual = {k: v for k, v in fb.items() if k != "actual_value"}
    check("log_feedback", fb_acc_no_actual, False,
          "R-01 反例: accurate 缺 actual_value")
    fb_inacc_no_actual = {**fb, "accuracy_label": "inaccurate"}
    fb_inacc_no_actual = {k: v for k, v in fb_inacc_no_actual.items() if k != "actual_value"}
    check("log_feedback", fb_inacc_no_actual, False,
          "R-01 反例: inaccurate 缺 actual_value")
    check("log_feedback", {**fb, "actual_value": "abc"}, False,
          "R-01 反例: actual_value 非金额格式")

    # --- R-02 正反例：audit_id 形态 ---
    check("log_feedback", {**fb, "audit_id": "A-demo-001"}, False,
          "R-02 反例: audit_id 为业务串（协议旧示例已作废）")
    check("log_feedback", {**fb, "audit_id": "12a4"}, False,
          "R-02 反例: audit_id 含非数字字符")
    check("log_feedback", {**fb, "audit_id": "1" * 21}, False,
          "R-02 反例: audit_id 超 20 位（BIGINT UNSIGNED 形态上限）")
    check("log_feedback", {**fb, "audit_id": "1" * 20}, True,
          "R-02 正例: audit_id 20 位数字（形态通过；范围仍由服务端校验）")

    sdc = {"request_id": "r1", "source_ref": "s1",
           "occurred_at": "2026-10-22T10:00:00+08:00",
           "industry_key": "retail", "coefficient_version": "cv-1",
           "coefficients": [{"indicator_code": "X4", "indicator_name": "流动比率",
                             "io_role": "input", "direction": "positive",
                             "weight": "0.1234567890"}],
           "solved_at": "2026-10-22T09:00:00+08:00", "solver_ref": "solver/v1@2026Q3"}
    check("save_da_coefficients", sdc, True, "正例: save_da_coefficients 合法")
    check("save_da_coefficients",
          {**sdc, "coefficients": [{**sdc["coefficients"][0], "io_role": "middle"}]},
          False, "反例: 非法 io_role 枚举")
    check("save_da_coefficients",
          {**sdc, "coefficients": [{**sdc["coefficients"][0], "weight": "0.12345678901"}]},
          False, "反例: weight 超10位小数")

    # 说明：features 与 feature_names 等长约束无法在 JSON Schema draft2020-12
    # 表达跨字段长度比较，由 DB CHECK(ck_rf_feature_pair) 与服务端校验兜底——
    # 此处如实标注，不虚报 Schema 层已覆盖。
    report("B-Schema正反例", "features/feature_names 等长", "SKIP",
           "JSON Schema 无法表达跨字段等长；由 ck_rf_feature_pair + 服务端按 feature_schema_version 校验")

# ============================== SECTION C =====================================
def strip_sql_comments(sql: str) -> str:
    """剥离 -- 行注释（本文件未使用 块注释与字符串内 CREATE TABLE 字面量）。"""
    lines = []
    for line in sql.splitlines():
        # 注意：字符串字面量中的 -- 不在本文件出现（已人工核对），直接按 -- 截断
        idx = line.find("--")
        lines.append(line[:idx] if idx >= 0 else line)
    return "\n".join(lines)

def section_c(sql_text):
    sql = strip_sql_comments(sql_text)

    # C1 表集合精确匹配（裸 CREATE TABLE，行首锚定）
    tables = re.findall(r"(?mi)^\s*CREATE TABLE\s+(\w+)\s*\(", sql)
    if set(tables) == EXPECTED_TABLES and len(tables) == 11:
        report("C-DDL静态", "11张表名称集合精确匹配", "PASS", f"实际{len(tables)}张")
    else:
        report("C-DDL静态", "11张表名称集合精确匹配", "FAIL",
               f"多:{set(tables)-EXPECTED_TABLES or '无'} 缺:{EXPECTED_TABLES-set(tables) or '无'}")

    # C2 视图集合精确匹配
    views = re.findall(r"(?mi)^\s*CREATE OR REPLACE VIEW\s+(\w+)\s+AS", sql)
    if set(views) == EXPECTED_VIEWS and len(views) == 10:
        report("C-DDL静态", "10个视图名称集合精确匹配", "PASS", f"实际{len(views)}个")
    else:
        report("C-DDL静态", "10个视图名称集合精确匹配", "FAIL",
               f"多:{set(views)-EXPECTED_VIEWS or '无'} 缺:{EXPECTED_VIEWS-set(views) or '无'}")

    # C3 表级无 IF NOT EXISTS（库级允许）
    if re.search(r"(?i)CREATE TABLE\s+IF NOT EXISTS", sql):
        report("C-DDL静态", "表级无 IF NOT EXISTS（不静默跳过）", "FAIL", "发现 CREATE TABLE IF NOT EXISTS")
    else:
        report("C-DDL静态", "表级无 IF NOT EXISTS（不静默跳过）", "PASS", "裸 CREATE TABLE；同名报错停止")

    # C4 无 GRANT/CREATE USER/FLUSH（账号与建表分离）
    if re.search(r"(?i)\b(GRANT|CREATE USER|FLUSH PRIVILEGES)\b", sql):
        report("C-DDL静态", "无 GRANT/CREATE USER（账号分离）", "FAIL", "init 内含授权语句")
    else:
        report("C-DDL静态", "无 GRANT/CREATE USER（账号分离）", "PASS")

    # C5 库名与排序规则
    #  R-10：脚本不再自带 CREATE DATABASE（低权账号下会 1044 中止），改为校验
    #  ① USE cf_workbench 存在（库不存在时 ERROR 1049 硬失败）② 全部表显式 utf8mb4_0900_ai_ci
    use_ok = bool(re.search(r"(?im)^\s*USE\s+cf_workbench\s*;", sql))
    tbl_collate = len(re.findall(r"(?i)COLLATE\s*=?\s*utf8mb4_0900_ai_ci", sql))
    ok = use_ok and tbl_collate >= len(EXPECTED_TABLES)
    report("C-DDL静态", "库=cf_workbench（USE 硬失败前置）+ 全表 utf8mb4_0900_ai_ci（D8/R-10）",
           "PASS" if ok else "FAIL",
           f"USE={use_ok} 表级collate命中={tbl_collate}/期望>={len(EXPECTED_TABLES)}")

    # C6 无 audit_db / utf8mb4_bin 残留（表/库级；payload_sha256 列级 ascii_bin 为批准保留项）
    bad_db = re.findall(r"(?i)\baudit_db\b", sql)
    bin_collate = re.findall(r"(?i)COLLATE\s*=\s*utf8mb4_bin|COLLATE utf8mb4_bin", sql)
    ok = not bad_db and not bin_collate
    report("C-DDL静态", "无 audit_db / 库表级 utf8mb4_bin 残留", "PASS" if ok else "FAIL",
           f"audit_db×{len(bad_db)} bin×{len(bin_collate)}" if not ok else "")

    # C7 逐表公共列核对（10 业务表全列；账本为登记例外）
    def table_block(name):
        m = re.search(rf"(?mi)^\s*CREATE TABLE\s+{name}\s*\((.*?)\n\)\s*ENGINE", sql, re.S)
        return m.group(1) if m else ""

    biz_tables = EXPECTED_TABLES - {"mcp_request_ledger"}
    common_missing = {}
    for t in sorted(biz_tables):
        blk = table_block(t)
        missing = [c for c in ["tenant_id", "request_id", "source_ref", "occurred_at",
                               "created_at", "actor_id", "supersedes_id"]
                   if not re.search(rf"(?mi)^\s*{c}\s+", blk)]
        if missing:
            common_missing[t] = missing
    if not common_missing:
        report("C-DDL静态", "业务表公共列齐全（A2.3；账本按 U-03 待裁不补列，R-09）", "PASS", "10/10")
    else:
        report("C-DDL静态", "10业务表公共列齐全（A2.3）", "FAIL", f"{common_missing}")

    # C7b 账本例外结构（已登记：无 occurred_at/source_ref/actor_id/supersedes_id）
    blk = table_block("mcp_request_ledger")
    ok = (re.search(r"(?mi)^\s*tenant_id\s+VARCHAR\(64\)", blk)
          and re.search(r"(?mi)^\s*tool_name\s+VARCHAR\(64\)", blk)
          and re.search(r"(?mi)^\s*request_id\s+VARCHAR\(128\)", blk)
          and re.search(r"(?mi)^\s*payload_hash\s+CHAR\(64\)", blk))
    report("C-DDL静态", "mcp_request_ledger 账本结构（登记例外）", "PASS" if ok else "FAIL")

    # C7c R-04：v_template_published_latest 必须排除被替代版本，且并列时结果唯一
    def view_block(name):
        m = re.search(rf"(?mi)^\s*CREATE OR REPLACE VIEW\s+{name}\s+AS(.*?);\s*$",
                      sql, re.S | re.M)
        return m.group(1) if m else ""
    vt = view_block("v_template_published_latest")
    has_not_exists = bool(re.search(r"(?is)NOT\s+EXISTS\s*\(", vt))
    tenant_scoped = bool(re.search(r"(?is)s(3)?\.tenant_id\s*=\s*p(3)?\.tenant_id", vt))
    deterministic = bool(re.search(r"(?is)ORDER\s+BY.*DESC", vt)) and bool(
        re.search(r"(?is)LIMIT\s+1", vt))
    ok = bool(vt) and has_not_exists and tenant_scoped and deterministic
    report("C-DDL静态",
           "R-04 v_template_published_latest 排除被替代版本且并列确定性",
           "PASS" if ok else "FAIL",
           f"NOT EXISTS={has_not_exists} 同租户={tenant_scoped} 并列确定性={deterministic}")

    # C7d R-08：已发布必须有发布时间（防止无时间戳的行进入发布视图）
    ok = bool(re.search(r"(?i)ck_tpl_published_has_time", sql))
    report("C-DDL静态", "R-08 ck_tpl_published_has_time（published→published_at 非空）",
           "PASS" if ok else "FAIL")

    # C7e R-10：脚本不再自带 CREATE DATABASE（低权账号下会 1044 中止）
    has_create_db = bool(re.search(r"(?im)^\s*CREATE\s+DATABASE\b", sql))
    report("C-DDL静态", "R-10 无 CREATE DATABASE（避免 cf_admin 权限不足 1044 中止）",
           "PASS" if not has_create_db else "FAIL",
           "" if not has_create_db else "仍存在 CREATE DATABASE")

    # C8 request_id VARCHAR(128) 全部 11 表
    bad128 = [t for t in sorted(EXPECTED_TABLES)
              if not re.search(r"(?mi)^\s*request_id\s+VARCHAR\(128\)", table_block(t))]
    report("C-DDL静态", "request_id=VARCHAR(128) 全11表（验收报告缺件4）",
           "PASS" if not bad128 else "FAIL", f"违规:{bad128}" if bad128 else "11/11")

    # C9 created_at UTC 默认表达式（D21）全 11 表
    bad_utc = [t for t in sorted(EXPECTED_TABLES)
               if not re.search(r"(?mi)^\s*created_at\s+DATETIME\(6\)\s+NOT NULL\s+DEFAULT\s+\(UTC_TIMESTAMP\(6\)\)", table_block(t))]
    report("C-DDL静态", "created_at DEFAULT (UTC_TIMESTAMP(6)) 全11表（D21）",
           "PASS" if not bad_utc else "FAIL", f"违规:{bad_utc}" if bad_utc else "11/11")

    # C10 金额列 DECIMAL(20,2)
    money_cols = [("feedback_log", "predicted_value"), ("feedback_log", "actual_value"),
                  ("exception_log", "amount"), ("payment_verify_log", "verified_amount")]
    bad_money = [f"{t}.{c}" for t, c in money_cols
                 if not re.search(rf"(?mi)^\s*{c}\s+DECIMAL\(20,2\)", table_block(t))]
    report("C-DDL静态", "金额列 DECIMAL(20,2)（元，D12）",
           "PASS" if not bad_money else "FAIL", f"违规:{bad_money}" if bad_money else "4列一致")

    # C11 时间列 DATETIME(6) 抽查（occurred_at 全业务表）
    bad_dt = [t for t in sorted(biz_tables)
              if not re.search(r"(?mi)^\s*occurred_at\s+DATETIME\(6\)", table_block(t))]
    report("C-DDL静态", "occurred_at DATETIME(6) 全10业务表",
           "PASS" if not bad_dt else "FAIL", f"违规:{bad_dt}" if bad_dt else "10/10")

    # C12 灯色英文四值：无中文灯色 CHECK 残留；关键表含 unknown
    zh = re.findall(r"'(绿|黄|红)'", sql)
    lvl_ok = True
    for t, ck in [("audit_log", "ck_audit_risk_level"), ("stress_test_log", "ck_stress_level"),
                  ("rf_predict_log", "ck_rf_level")]:
        blk = table_block(t)
        m = re.search(rf"{ck}\s+CHECK\s*\((.*?)\)", blk, re.S)
        if not m or "'unknown'" not in m.group(1):
            lvl_ok = False
    ok = not zh and lvl_ok
    report("C-DDL静态", "灯色 green/yellow/red/unknown，无中文枚举残留（D10）",
           "PASS" if ok else "FAIL", f"中文字面量:{zh}" if zh else "")

    # C13 D13：rf 表无 JSON_LENGTH(features)=30 硬卡；保留等长约束
    rf_blk = table_block("rf_predict_log")
    has30 = bool(re.search(r"JSON_LENGTH\(features\)\s*=\s*30", rf_blk))
    has_pair = bool(re.search(r"ck_rf_feature_pair\s+CHECK.*?JSON_LENGTH\(features\)\s*=\s*JSON_LENGTH\(feature_names\)", rf_blk, re.S))
    if not has30 and has_pair:
        report("C-DDL静态", "rf 无30维硬卡+保留等长约束（D13）", "PASS")
    else:
        report("C-DDL静态", "rf 无30维硬卡+保留等长约束（D13）", "FAIL",
               f"has30={has30} has_pair={has_pair}")

    # C14 event_type CHECK 24 值
    audit_blk = table_block("audit_log")
    m = re.search(r"ck_audit_event_type\s+CHECK\s*\((.*?)\)\)", audit_blk, re.S)
    if m:
        vals = set(re.findall(r"'(\w+)'", m.group(1)))
        ok = vals == EXPECTED_EVENT_TYPES
        report("C-DDL静态", "audit_log event_type CHECK 24值", "PASS" if ok else "FAIL",
               f"实际{len(vals)}值" if not ok else "")
    else:
        report("C-DDL静态", "audit_log event_type CHECK 24值", "FAIL", "未找到 ck_audit_event_type")

    # C15 scenario CHECK 5 值
    st_blk = table_block("stress_test_log")
    m = re.search(r"ck_stress_scenario\s+CHECK\s*\((.*?)\)", st_blk, re.S)
    vals = set(re.findall(r"'(\w+)'", m.group(1))) if m else set()
    ok = vals == EXPECTED_SCENARIOS
    report("C-DDL静态", "stress_test_log scenario CHECK 5值（A5）", "PASS" if ok else "FAIL",
           f"实际:{vals}" if not ok else "")

    # C16 三张模型日志表采纳队友结构标志（execution_status/payload_sha256/company_id/run_id/record_key）
    trio_ok = True
    for t in ["quality_log", "deada_score_log", "rf_predict_log"]:
        blk = table_block(t)
        for c in ["company_id", "run_id", "record_key", "payload_sha256", "execution_status"]:
            if not re.search(rf"(?mi)^\s*{c}\s+", blk):
                trio_ok = False
    report("C-DDL静态", "三层日志表含 company_id/run_id/record_key/payload_sha256/execution_status（D9采纳）",
           "PASS" if trio_ok else "FAIL")

    # C17 视图纠错链同 tenant 限制（v_record_active 等 NOT EXISTS 子查询）
    view_blocks = re.findall(r"(?is)CREATE OR REPLACE VIEW\s+(\w+)\s+AS\s+(.*?);", sql)
    no_tenant = []
    for vn, body in view_blocks:
        if "NOT EXISTS" in body and "supersedes_id" in body:
            if not re.search(r"s\.tenant_id\s*=\s*\w+\.tenant_id", body):
                no_tenant.append(vn)
    report("C-DDL静态", "纠错链子查询同 tenant 限制（防跨租户误判）",
           "PASS" if not no_tenant else "FAIL", f"缺限制:{no_tenant}" if no_tenant else "")

    # C18 结构预检段存在（information_schema 查询）
    ok = ("information_schema.tables" in sql and "existing_table" in sql
          and "information_schema.SCHEMATA" in sql)
    report("C-DDL静态", "结构预检段存在（库collation/同名表/同名视图）", "PASS" if ok else "FAIL")

    # C19 三表 uk 行级幂等键（tenant,company,run,record_key）
    uk_ok = True
    for t in ["quality_log", "deada_score_log", "rf_predict_log"]:
        if not re.search(r"UNIQUE KEY\s+\w+\s*\(tenant_id,company_id,run_id,record_key\)", table_block(t)):
            uk_ok = False
    report("C-DDL静态", "三层日志表行级唯一键 (tenant,company,run,record_key)（D9）",
           "PASS" if uk_ok else "FAIL")

    # C20 账本唯一键
    ok = bool(re.search(r"UNIQUE KEY\s+uk_ledger_key\s*\(tenant_id,\s*tool_name,\s*request_id\)",
                        table_block("mcp_request_ledger")))
    report("C-DDL静态", "账本唯一键 (tenant_id,tool_name,request_id)", "PASS" if ok else "FAIL")

# ============================== SECTION D =====================================
def section_d():
    report("D-真实MySQL", "init_v1.1.sql 在 MySQL 8.x 实际执行", "BLOCKED",
           "R-06 修正措辞：本机【有】MySQL 实例（审核实测 MySQL84 服务运行、3306 监听、"
           "mysql.exe 存在），真正的原因是【无可用凭据且未获授权建库】——root 以空口令被拒，"
           "且 WB-ENG-001 纪律禁止在服务器执行 DDL。"
           "静态解析通过 ≠ MySQL 执行通过，留待 WB-ENG-006 隔离环境验证")
    report("D-真实MySQL", "视图在真实库创建与查询", "BLOCKED",
           "同上；且 cf_admin 缺 CREATE VIEW/SHOW VIEW，权限候选待批准")

# ============================== main =====================================
def main():
    print(f"校验对象: {JSON_PATH.name} / {SQL_PATH.name}")
    print("=" * 78)
    doc = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    sql_text = SQL_PATH.read_text(encoding="utf-8")
    section_a(doc)
    section_b(doc)
    section_c(sql_text)
    section_d()
    print("=" * 78)
    from collections import Counter
    cnt = Counter(r[2] for r in RESULTS)
    print(f"汇总: PASS={cnt.get('PASS',0)} FAIL={cnt.get('FAIL',0)} "
          f"SKIP={cnt.get('SKIP',0)} BLOCKED={cnt.get('BLOCKED',0)} 合计={len(RESULTS)}")
    if cnt.get("FAIL", 0):
        print("结论: 存在 FAIL，须修复后重跑")
        sys.exit(1)
    print("结论: 无 FAIL（BLOCKED/SKIP 项见明细，不构成通过证据）")
    sys.exit(0)

if __name__ == "__main__":
    main()
