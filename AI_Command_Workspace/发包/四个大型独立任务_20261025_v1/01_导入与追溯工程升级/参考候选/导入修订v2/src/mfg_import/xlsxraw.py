"""xlsx 原始 XML 只读读取。

直接解析 xl/ 下的 XML，保留每个单元格的：
- 原始数值文本（不经过 float，避免 80.59999999999999 被显示成 80.6 后当成原值）
- 单元格类型（数值/文本/数字文本/布尔/错误）
- 公式原文与缓存值（缓存缺失绝不 eval 代算）
- 空白（元素不存在）/ 显式空白单元格（无 <v>）/ 空字符串 / 空格 的区别
- 工作簿日期系统（1900/1904）

不执行宏、不解析外部链接、不运行任何单元格内容。
"""
import re
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

_CELL_RE = re.compile(r"^([A-Z]+)([0-9]+)$")


@dataclass
class RawCell:
    address: str
    col: str
    row: int
    kind: str  # number | text | bool | error | blank
    raw: "str | None"  # XML 原文（数字保留原始文本）
    formula: "str | None" = None
    cached: "str | None" = None  # 公式缓存原文；None 表示无缓存
    style: "str | None" = None

    @property
    def has_formula(self) -> bool:
        return self.formula is not None

    @property
    def formula_cache_missing(self) -> bool:
        return self.formula is not None and self.cached is None


@dataclass
class RawSheet:
    name: str
    cells: dict = field(default_factory=dict)  # address -> RawCell
    max_row: int = 0

    def cell(self, address: str) -> "RawCell | None":
        return self.cells.get(address)


@dataclass
class RawWorkbook:
    date1904: bool
    sheets: list  # list[RawSheet]，按工作簿顺序

    def sheet(self, name: str) -> "RawSheet | None":
        for s in self.sheets:
            if s.name == name:
                return s
        return None


def col_to_num(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def num_to_col(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def split_address(addr: str):
    m = _CELL_RE.match(addr)
    if not m:
        raise ValueError(f"bad cell address: {addr!r}")
    return m.group(1), int(m.group(2))


def _text_of_si(si) -> str:
    return "".join(t.text or "" for t in si.iter(NS + "t"))


def read_workbook(path) -> RawWorkbook:
    """只读解析 xlsx，返回 RawWorkbook。绝不写回源文件。"""
    with zipfile.ZipFile(path) as z:
        wb_xml = ET.fromstring(z.read("xl/workbook.xml"))
        wb_pr = wb_xml.find(NS + "workbookPr")
        date1904 = bool(
            wb_pr is not None and wb_pr.get("date1904") in ("1", "true", "True")
        )

        rels = {}
        rels_xml = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        for rel in rels_xml.iter(NS_REL + "Relationship"):
            rels[rel.get("Id")] = rel.get("Target")

        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in sst.iter(NS + "si"):
                shared.append(_text_of_si(si))

        sheets = []
        for sh in wb_xml.iter(NS + "sheet"):
            name = sh.get("name")
            rid = sh.get(NS_R + "id")
            target = rels.get(rid, "").lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            sheets.append((name, target))

        result = []
        for name, target in sheets:
            result.append(_read_sheet(z, target, name, shared))
        return RawWorkbook(date1904=date1904, sheets=result)


def _read_sheet(z, target: str, name: str, shared) -> RawSheet:
    root = ET.fromstring(z.read(target))
    cells = {}
    max_row = 0
    for c in root.iter(NS + "c"):
        addr = c.get("r")
        if not addr:
            continue
        col, row = split_address(addr)
        max_row = max(max_row, row)
        t = c.get("t") or "n"
        f_el = c.find(NS + "f")
        v_el = c.find(NS + "v")
        is_el = c.find(NS + "is")
        formula = f_el.text if f_el is not None else None
        raw = None
        kind = "blank"
        if t == "s" and v_el is not None:
            idx = int(v_el.text)
            raw = shared[idx] if 0 <= idx < len(shared) else None
            kind = "text"
        elif t == "inlineStr":
            raw = (
                "".join(x.text or "" for x in is_el.iter(NS + "t"))
                if is_el is not None
                else None
            )
            kind = "text" if raw is not None else "blank"
        elif t == "str" and v_el is not None:
            raw = v_el.text
            kind = "text"
        elif t == "b" and v_el is not None:
            raw = v_el.text
            kind = "bool"
        elif t == "e" and v_el is not None:
            raw = v_el.text
            kind = "error"
        elif v_el is not None:
            raw = v_el.text
            kind = "number"
        if formula is not None:
            # 公式单元格：raw 视为缓存；无 <v> 则缓存缺失
            cells[addr] = RawCell(
                address=addr,
                col=col,
                row=row,
                kind=kind if v_el is not None else "blank",
                raw=None,
                formula=formula,
                cached=v_el.text if v_el is not None else None,
                style=c.get("s"),
            )
        else:
            cells[addr] = RawCell(
                address=addr,
                col=col,
                row=row,
                kind=kind,
                raw=raw,
                style=c.get("s"),
            )
    return RawSheet(name=name, cells=cells, max_row=max_row)
