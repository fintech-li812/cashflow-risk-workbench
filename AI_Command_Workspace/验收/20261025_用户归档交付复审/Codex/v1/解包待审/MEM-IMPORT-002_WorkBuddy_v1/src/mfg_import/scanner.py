"""scan：把制造业 xlsx 变成有原始单元格证据的 mfg-import.v1 规范数据包。"""
import csv
import io
import json
import os
import re
import sys
from decimal import Decimal

from . import SCHEMA, TOOL_VERSION
from .canon import (
    canonical_bytes,
    compute_record_key,
    compute_source_revision,
    sha256_file,
    sha256_hex,
)
from .convert import (
    ConvertError,
    is_numeric_text,
    parse_date_text,
    parse_decimal,
    parse_month_text,
    serial_to_date,
    wan_to_yuan_fen,
    yuan_to_fen_str,
)
from .xlsxraw import col_to_num, read_workbook

PACKAGE_FILES = [
    "inventory.json",
    "records.jsonl",
    "issues.jsonl",
    "issues.csv",
    "mapping.snapshot.json",
    "unit_exceptions.snapshot.json",
    "report.html",
]

_ID_RE = re.compile(r"^\S+$")
_PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})$")


class ScanError(Exception):
    """参数/运行错误（退出码 2/1），与业务疑点无关。"""


def _norm_header(s: str) -> str:
    return re.sub(r"[\s　]+", " ", s).strip()


def validate_identity(tenant_id, company_id, period, run_id):
    for name, v in (
        ("tenant_id", tenant_id),
        ("company_id", company_id),
        ("run_id", run_id),
    ):
        if not v or not isinstance(v, str) or not _ID_RE.match(v):
            raise ScanError(f"{name} 必须为非空字符串且无空白字符（调用者显式提供，不推测）")
    m = _PERIOD_RE.match(period or "")
    if not m or not (1 <= int(m.group(2)) <= 12):
        raise ScanError("period 必须为合法 YYYY-MM")


def ensure_fresh_output_dir(output):
    """输出目录必须全新：拒绝已存在（重名）、符号链接。"""
    if os.path.islink(output):
        raise ScanError(f"输出路径是符号链接，拒绝: {output}")
    if os.path.exists(output):
        raise ScanError(f"输出目录已存在，拒绝覆盖: {output}")
    os.makedirs(output)


def check_safe_relpath(p: str):
    """包内相对路径：拒绝绝对路径、..、空段。"""
    if os.path.isabs(p) or re.match(r"^[A-Za-z]:", p):
        raise ScanError(f"拒绝绝对路径: {p!r}")
    parts = p.replace("\\", "/").split("/")
    if any(part in ("", "..", ".") for part in parts):
        raise ScanError(f"拒绝越界路径: {p!r}")


def load_mapping(path):
    with open(path, "rb") as f:
        raw = f.read()
    mapping = json.loads(raw.decode("utf-8"))
    return mapping, sha256_hex(raw), raw


def load_unit_exceptions(path):
    """unit_exceptions.json：例外必须绑定 源SHA256+Sheet+地址，不全局硬编码。"""
    if not path:
        return []
    with open(path, "rb") as f:
        data = json.loads(f.read().decode("utf-8"))
    out = []
    for e in data.get("exceptions", []):
        for k in ("source_sha256", "sheet", "address", "reason"):
            if not e.get(k):
                raise ScanError(f"unit exception 缺字段 {k}: {e!r}")
        out.append(e)
    return out


class IssueSink:
    def __init__(self):
        self.issues = []
        self._n = 0

    def add(self, code, file, sheet, address, row, raw, reason, action):
        self._n += 1
        issue = {
            "issue_id": f"ISS-{self._n:04d}",
            "code": code,
            "file": file,
            "sheet": sheet,
            "address": address,
            "row": row,
            "raw": raw,
            "reason": reason,
            "action": action,
        }
        self.issues.append(issue)
        return issue["issue_id"]


def _cell_snapshot(cell):
    if cell is None:
        return None
    snap = {"type": cell.kind, "raw": cell.raw}
    if cell.has_formula:
        snap["formula"] = cell.formula
        snap["cached"] = cell.cached
        snap["cache_status"] = "cached" if cell.cached is not None else "missing"
    return snap


def _convert_cell(field, cell, ctx):
    """返回 (value, transform_or_note, issue_ids)。

    区分：缺失单元格 / 空白 / 空串 / 空格 / 数值0 / 数字文本 / 公式有无缓存。
    单位例外绑定 source_sha256+sheet+address，命中则规范值 null 且不再换算。
    """
    ftype = field["type"]
    name = field["name"]
    issues = ctx["issues"]
    addr = cell.address if cell else None

    def note(kind, extra_issue=None):
        iid = None
        if extra_issue:
            iid = issues.add(
                extra_issue[0], ctx["logical_name"], ctx["sheet_name"], addr,
                cell.row if cell else None,
                cell.raw if cell else None, extra_issue[1], extra_issue[2],
            )
        return None, {"status": kind}, ([iid] if iid else [])

    # 单位例外优先于一切换算（绑定实际源哈希，不扩大到任意文件同地址）
    for ex in ctx["exceptions"]:
        if (
            cell is not None
            and ex["source_sha256"] == ctx["file_sha256"]
            and ex["sheet"] == ctx["sheet_name"]
            and ex["address"] == addr
        ):
            iid = issues.add(
                "UNIT_SUSPECT_PENDING", ctx["logical_name"], ctx["sheet_name"],
                addr, cell.row, cell.raw,
                f"已登记单位疑点（绑定源SHA+Sheet+地址）：{ex['reason']}；规范值保持 null，不再放大",
                "人工核实真实单位后按批准口径重导",
            )
            return None, {"status": "unit_suspect_pending", "exception": ex.get("id")}, [iid]

    if cell is None:
        return note("missing_cell")
    if cell.has_formula and cell.formula_cache_missing:
        iid = issues.add(
            "FORMULA_CACHE_MISSING", ctx["logical_name"], ctx["sheet_name"],
            addr, cell.row, cell.formula,
            "公式存在但缓存缺失，无法取得已算值；不调用外部程序代算",
            "在源系统打开重算后重新导出，或改提供固定值",
        )
        return None, {"status": "formula_cache_missing", "formula": cell.formula}, [iid]

    raw = cell.cached if cell.has_formula else cell.raw
    if raw is None:
        return note("blank_cell")

    if cell.kind == "number" or cell.has_formula:
        if ftype in ("amount", "number"):
            try:
                d = parse_decimal(raw)
            except ConvertError as e:
                iid = issues.add(
                    e.code, ctx["logical_name"], ctx["sheet_name"], addr,
                    cell.row, raw, str(e), "人工核对源单元格",
                )
                return None, {"status": "invalid", "error": e.code}, [iid]
            if ftype == "number":
                return (
                    str(d),
                    {"status": "ok", "from_raw": raw},
                    [],
                )
            unit = field.get("unit", "元")
            if unit == "万元":
                value = wan_to_yuan_fen(d)
                transform = {
                    "status": "ok",
                    "from_unit": "万元",
                    "to_unit": "元",
                    "factor": "10000",
                    "rounding": "ROUND_HALF_UP到分（原精度乘10000后落分）",
                    "from_raw": raw,
                }
            elif unit == "元":
                value = yuan_to_fen_str(d)
                transform = {"status": "ok", "from_unit": "元", "to_unit": "元",
                             "rounding": "ROUND_HALF_UP到分", "from_raw": raw}
            else:
                iid = issues.add(
                    "UNIT_UNKNOWN", ctx["logical_name"], ctx["sheet_name"], addr,
                    cell.row, raw, f"未批准的单位 {unit!r}，不套转换",
                    "确认单位并更新映射后重导",
                )
                return None, {"status": "unit_unknown", "from_raw": raw}, [iid]
            return value, transform, []
        if ftype == "date":
            try:
                d = serial_to_date(raw, ctx["date1904"])
            except ConvertError as e:
                iid = issues.add(
                    e.code, ctx["logical_name"], ctx["sheet_name"], addr,
                    cell.row, raw, str(e), "人工核对源日期",
                )
                return None, {"status": "invalid", "error": e.code}, [iid]
            return d.isoformat(), {
                "status": "ok",
                "from_serial": raw,
                "date_system": "1904" if ctx["date1904"] else "1900",
            }, []
        # 文本/月份字段拿到数值：保留原文，不偷转
        return raw, {"status": "ok_numeric_as_text", "from_raw": raw}, []

    # 文本类单元格
    if raw == "":
        return note("empty_string")
    if raw.strip() == "":
        return note("whitespace_only")
    if ftype == "amount":
        if is_numeric_text(raw):
            iid = issues.add(
                "NUMERIC_TEXT_NOT_CONVERTED", ctx["logical_name"], ctx["sheet_name"],
                addr, cell.row, raw,
                "数字以文本存储，未经批准规则不偷转数值",
                "确认是否按数值处理并更新映射",
            )
            return None, {"status": "numeric_text_not_converted", "from_raw": raw}, [iid]
        iid = issues.add(
            "INVALID_AMOUNT", ctx["logical_name"], ctx["sheet_name"], addr,
            cell.row, raw, "金额单元格为非数字文本", "人工核对源单元格",
        )
        return None, {"status": "invalid", "error": "INVALID_AMOUNT"}, [iid]
    if ftype == "date":
        try:
            d = parse_date_text(raw, field.get("formats"))
        except ConvertError as e:
            iid = issues.add(
                e.code, ctx["logical_name"], ctx["sheet_name"], addr,
                cell.row, raw, str(e), "人工核对源日期",
            )
            return None, {"status": "invalid", "error": e.code}, [iid]
        return d.isoformat(), {"status": "ok", "from_text": raw}, []
    if ftype == "month":
        try:
            return parse_month_text(raw), {"status": "ok", "from_text": raw}, []
        except ConvertError as e:
            iid = issues.add(
                e.code, ctx["logical_name"], ctx["sheet_name"], addr,
                cell.row, raw, str(e), "人工核对源月份",
            )
            return None, {"status": "invalid", "error": e.code}, [iid]
    return raw, {"status": "ok"}, []


def _match_columns(header_cells, fields, ctx):
    """按表头与别名匹配列。缺列/重名列/别名歧义都报，不取第一列糊弄。

    返回 {field_name: col_letter}（无法唯一确定的字段缺失）。
    """
    # header_cells: list[(col_letter, normalized_text)]
    result = {}
    for field in fields:
        aliases = [_norm_header(a) for a in [field["name"], *field.get("aliases", [])]]
        hits = [col for col, text in header_cells if text in aliases]
        distinct = set(text for _, text in header_cells if text in aliases)
        if len(hits) == 0:
            if field.get("required", True):
                ctx["issues"].add(
                    "MISSING_COLUMN", ctx["logical_name"], ctx["sheet_name"], None,
                    None, None,
                    f"缺少必需列: {field['name']}（别名 {aliases}）",
                    "补齐源表列或更新映射后重导",
                )
            continue
        if len(hits) > 1:
            code = "ALIAS_AMBIGUITY" if len(distinct) > 1 else "DUPLICATE_COLUMN"
            ctx["issues"].add(
                code, ctx["logical_name"], ctx["sheet_name"],
                ",".join(f"{c}{ctx['header_row']}" for c in hits), ctx["header_row"],
                ",".join(sorted(distinct)),
                f"字段 {field['name']} 匹配到多列 {hits}，不取第一项",
                "人工消除歧义后重导",
            )
            continue
        result[field["name"]] = hits[0]
    return result


def _scan_horizontal(sheet, spec, ctx):
    records = []
    header_row = spec["header_row"]
    data_start = spec["data_start_row"]
    header_cells = []
    for cell in sheet.cells.values():
        if cell.row == header_row and cell.raw is not None:
            header_cells.append((cell.col, _norm_header(str(cell.raw))))
    col_map = _match_columns(header_cells, spec["fields"], {**ctx, "header_row": header_row})
    for row in range(data_start, sheet.max_row + 1):
        row_cells = [c for c in sheet.cells.values() if c.row == row]
        if not row_cells:
            continue
        key = compute_record_key(ctx["file_sha256"], sheet.name, row)
        cells_snap = {}
        for c in sorted(row_cells, key=lambda c: col_to_num(c.col)):
            cells_snap[c.address] = _cell_snapshot(c)
        normalized = {}
        rec_issue_ids = []
        raws = []
        for field in spec["fields"]:
            col = col_map.get(field["name"])
            cell = sheet.cell(f"{col}{row}") if col else None
            value, transform, iids = _convert_cell(field, cell, ctx)
            rec_issue_ids.extend(iids)
            normalized[field["name"]] = {
                "value": value,
                "address": cell.address if cell else None,
                "transform": transform,
            }
            raws.append(cell.raw if cell else None)
        records.append(
            {
                "source_record_key": key,
                "record_type": sheet.name,
                "source_file_sha256": ctx["file_sha256"],
                "sheet": sheet.name,
                "row": row,
                "cells": cells_snap,
                "normalized": normalized,
                "issues": rec_issue_ids,
                "_rawsig": canonical_bytes(raws),
            }
        )
    _report_duplicates(records, ctx)
    return records


def _scan_vertical(sheet, spec, ctx):
    """企业基本信息纵向表：按字段名定位，行号不统一。"""
    key_col = spec.get("key_column", "A")
    val_col = spec.get("value_column", "B")
    header_row = spec.get("header_row", 2)
    # 字段名 -> [(row, raw_name)]
    found = {}
    for cell in sheet.cells.values():
        if cell.col == key_col and cell.row > header_row and cell.raw is not None:
            found.setdefault(cell.row, _norm_header(str(cell.raw)))
    records = []
    used_rows = set()
    for field in spec["fields"]:
        aliases = [_norm_header(a) for a in [field["name"], *field.get("aliases", [])]]
        hits = [r for r, name in found.items() if name in aliases]
        distinct = {found[r] for r in hits}
        row = None
        if len(hits) == 0:
            if field.get("required", True):
                ctx["issues"].add(
                    "MISSING_FIELD", ctx["logical_name"], ctx["sheet_name"], None,
                    None, None, f"缺少必需字段: {field['name']}（别名 {aliases}）",
                    "补齐源表字段或更新映射后重导",
                )
        elif len(hits) > 1:
            code = "ALIAS_AMBIGUITY" if len(distinct) > 1 else "DUPLICATE_FIELD"
            ctx["issues"].add(
                code, ctx["logical_name"], ctx["sheet_name"],
                ",".join(f"{key_col}{r}" for r in hits), None,
                ",".join(sorted(distinct)),
                f"字段 {field['name']} 匹配到多行 {hits}，不取第一行",
                "人工消除歧义后重导",
            )
        else:
            row = hits[0]
            used_rows.add(row)
        cell = sheet.cell(f"{val_col}{row}") if row else None
        value, transform, iids = _convert_cell(field, cell, ctx)
        key = compute_record_key(ctx["file_sha256"], sheet.name, row or 0)
        records.append(
            {
                "source_record_key": key,
                "record_type": f"{sheet.name}:{field['name']}",
                "source_file_sha256": ctx["file_sha256"],
                "sheet": sheet.name,
                "row": row,
                "cells": {cell.address: _cell_snapshot(cell)} if cell else {},
                "normalized": {field["name"]: {"value": value,
                                              "address": cell.address if cell else None,
                                              "transform": transform}},
                "issues": iids,
                "_rawsig": b"",
            }
        )
    return records


def _report_duplicates(records, ctx):
    """重复行保留并给证据；不按相同金额删行。"""
    groups = {}
    for rec in records:
        groups.setdefault(rec["_rawsig"], []).append(rec)
    for sig, group in groups.items():
        if len(group) > 1:
            rows = [g["row"] for g in group]
            for g in group:
                iid = ctx["issues"].add(
                    "DUPLICATE_ROW", ctx["logical_name"], ctx["sheet_name"],
                    None, g["row"], None,
                    f"行 {rows} 原始取值完全相同；重复保留，不删除",
                    "人工确认是否重复录入",
                )
                g["issues"].append(iid)


def scan(input_dir, output_dir, mapping_path, tenant_id, company_id, period, run_id,
         exceptions_path=None):
    validate_identity(tenant_id, company_id, period, run_id)
    if not os.path.isdir(input_dir):
        raise ScanError(f"输入目录不存在: {input_dir}")
    mapping, mapping_sha, mapping_raw = load_mapping(mapping_path)
    exceptions = load_unit_exceptions(exceptions_path)
    ensure_fresh_output_dir(output_dir)

    files = sorted(
        f for f in os.listdir(input_dir) if f.lower().endswith(".xlsx") and not f.startswith("~$")
    )
    if not files:
        raise ScanError(f"输入目录无 xlsx 文件: {input_dir}")

    issues = IssueSink()
    sources = []
    inventory_inputs = []
    all_records = []

    for fname in files:
        path = os.path.join(input_dir, fname)
        file_sha = sha256_file(path)
        sources.append({"logical_name": fname, "sha256": file_sha})
        wb = read_workbook(path)
        sheet_specs = mapping["sheets"]
        sheet_infos = []
        present = {s.name for s in wb.sheets}
        for sname, spec in sheet_specs.items():
            if spec.get("required", True) and sname not in present:
                issues.add("MISSING_SHEET", fname, sname, None, None, None,
                           f"缺少必需 Sheet: {sname}", "补齐源文件或更新映射后重导")
        for rawsheet in wb.sheets:
            spec = sheet_specs.get(rawsheet.name)
            if spec is None:
                # 额外 Sheet 登记，不删除；数据字典等不当真值
                sheet_infos.append({"name": rawsheet.name, "recognized": False,
                                    "raw_record_count": max(0, rawsheet.max_row - 1)})
                continue
            ctx = {
                "issues": issues,
                "logical_name": fname,
                "file_sha256": file_sha,
                "sheet_name": rawsheet.name,
                "date1904": wb.date1904,
                "exceptions": exceptions,
            }
            if spec.get("layout") == "vertical":
                recs = _scan_vertical(rawsheet, spec, ctx)
            else:
                recs = _scan_horizontal(rawsheet, spec, ctx)
            all_records.extend(recs)
            sheet_infos.append({
                "name": rawsheet.name,
                "recognized": True,
                "header_row": spec.get("header_row"),
                "data_start_row": spec.get("data_start_row"),
                "raw_record_count": len(recs),
            })
        inventory_inputs.append({
            "logical_name": fname,
            "sha256": file_sha,
            "date_system": "1904" if wb.date1904 else "1900",
            "sheets": sheet_infos,
        })

    source_revision = compute_source_revision(sources, mapping_sha)

    # 稳定排序：按 (文件序, sheet, row) 规范输出，重跑字节稳定
    file_order = {s["sha256"]: i for i, s in enumerate(sources)}
    all_records.sort(key=lambda r: (file_order.get(r["source_file_sha256"], 0),
                                    r["sheet"], r["row"] or 0,
                                    r["source_record_key"]))
    for rec in all_records:
        rec.pop("_rawsig", None)
        rec.pop("_rawlist", None)

    inventory = {
        "schema": SCHEMA,
        "tool_version": TOOL_VERSION,
        "mapping_version": mapping.get("mapping_version"),
        "mapping_sha256": mapping_sha,
        "source_revision": source_revision,
        "inputs": inventory_inputs,
        "counts": {"records": len(all_records), "issues": len(issues.issues)},
    }

    _write_json(os.path.join(output_dir, "inventory.json"), inventory)
    with open(os.path.join(output_dir, "records.jsonl"), "wb") as f:
        for rec in all_records:
            f.write(canonical_bytes(rec) + b"\n")
    with open(os.path.join(output_dir, "issues.jsonl"), "wb") as f:
        for issue in issues.issues:
            f.write(canonical_bytes(issue) + b"\n")
    _write_issues_csv(os.path.join(output_dir, "issues.csv"), issues.issues)
    # 映射快照按原始字节拷贝，保证包内快照 SHA256 == 源映射 SHA256（source_revision 可复算）
    with open(os.path.join(output_dir, "mapping.snapshot.json"), "wb") as f:
        f.write(mapping_raw)
    _write_json(os.path.join(output_dir, "unit_exceptions.snapshot.json"),
                {"exceptions": exceptions})

    from .report import render_report

    render_report(
        os.path.join(output_dir, "report.html"),
        inventory, all_records, issues.issues,
        {"tenant_id": tenant_id, "company_id": company_id,
         "period": period, "run_id": run_id},
    )

    manifest_files = []
    for name in PACKAGE_FILES:
        p = os.path.join(output_dir, name)
        rc = None
        if name == "records.jsonl":
            rc = len(all_records)
        elif name == "issues.jsonl":
            rc = len(issues.issues)
        manifest_files.append({"path": name, "sha256": sha256_file(p),
                               "record_count": rc})
    import datetime as _dt

    manifest = {
        "schema": SCHEMA,
        "kind": "import_package",
        "tenant_id": tenant_id,
        "company_id": company_id,
        "period": period,
        "source_revision": source_revision,
        "run_id": run_id,
        "unit": "CNY",
        "tool_version": TOOL_VERSION,
        "mapping_version": mapping.get("mapping_version"),
        "files": manifest_files,
        "non_deterministic_fields": ["created_at"],
        "created_at": _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(),
    }
    _write_json(os.path.join(output_dir, "manifest.json"), manifest)

    print(f"scan 完成: 文件 {len(sources)} 个, 记录 {len(all_records)} 条, "
          f"问题 {len(issues.issues)} 条, source_revision={source_revision[:16]}…")
    print("注意: scan 技术执行成功=0 不代表数据合格，业务疑点见 issues.jsonl / report.html")
    return 0


def _write_json(path, obj):
    with open(path, "wb") as f:
        f.write(canonical_bytes(obj) + b"\n")


_CSV_DANGER = ("=", "+", "@", "\t", "\r")


def csv_safe(value):
    """CSV 导出防公式注入：危险开头加 '；机器原文仍在 JSON 保留。"""
    if value is None:
        return ""
    s = str(value)
    if s.startswith(_CSV_DANGER) or (s.startswith("-") and len(s) > 1 and not s[1].isdigit()):
        return "'" + s
    return s


def _write_issues_csv(path, issues):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["issue_id", "code", "file", "sheet", "address", "row",
                "raw", "reason", "action"])
    for i in issues:
        w.writerow([csv_safe(i[k]) for k in
                    ("issue_id", "code", "file", "sheet", "address", "row",
                     "raw", "reason", "action")])
    with open(path, "wb") as f:
        f.write(buf.getvalue().encode("utf-8-sig"))
