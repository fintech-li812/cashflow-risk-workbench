"""金额与日期转换：全部用 Decimal / 显式规则，不猜、不静默修正。

规则要点（来自统一接口 v1 / 一期范围）：
- 金额用 Decimal，源万元按原精度乘 10000 后在元位 ROUND_HALF_UP 落到分；
  禁止先截到两位再换算（FIN-01 反例：1.234567 万 = 12345.67 元，不是 12300.00）。
- 非法/非有限金额（NaN、Infinity、bad 字符串）统一拒绝（FIN-02 反例）。
- 日期序列按工作簿 1900/1904 系统解释；serial 60 是 Excel1900 虚构闰日，
  不可静默变成合法业务日期；非法日期（2026-13-05、2026-02-30）不进位；
  两位年份不猜世纪。
"""
import datetime as _dt
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

FEN = Decimal("0.01")


class ConvertError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


_NUMERIC_TEXT_RE = re.compile(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$")
_DATE_TEXT_RE = re.compile(r"^(\d{2,4})-(\d{1,2})-(\d{1,2})$")
_MONTH_TEXT_RE = re.compile(r"^(\d{4})-(\d{1,2})$")


def is_numeric_text(text: str) -> bool:
    return bool(_NUMERIC_TEXT_RE.match(text.strip()))


def parse_decimal(raw: str) -> Decimal:
    """把 XML 原始数值文本解析为 Decimal；拒绝非有限数与非法字符串。"""
    text = raw.strip()
    if not text:
        raise ConvertError("EMPTY_AMOUNT", "空金额文本")
    lowered = text.lower()
    if lowered in ("nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"):
        raise ConvertError("NON_FINITE_AMOUNT", f"非有限金额: {raw!r}")
    try:
        d = Decimal(text)
    except InvalidOperation:
        raise ConvertError("INVALID_AMOUNT", f"非法金额文本: {raw!r}")
    if not d.is_finite():
        raise ConvertError("NON_FINITE_AMOUNT", f"非有限金额: {raw!r}")
    return d


def wan_to_yuan_fen(d: Decimal) -> str:
    """万元 → 元十进制字符串：原精度乘 10000，再在元位 ROUND_HALF_UP 落到分。"""
    yuan = d * Decimal(10000)
    return str(yuan.quantize(FEN, rounding=ROUND_HALF_UP))


def yuan_to_fen_str(d: Decimal) -> str:
    """元 → 2 位小数十进制字符串。"""
    return str(d.quantize(FEN, rounding=ROUND_HALF_UP))


# ---------------- 日期 ----------------

EPOCH_1900 = _dt.date(1899, 12, 30)  # 已含 Excel1900 闰日 bug 偏移（serial>60）
EPOCH_1904 = _dt.date(1904, 1, 1)


def serial_to_date(serial_text: str, date1904: bool) -> _dt.date:
    """序列号转日期。Excel1900 serial=60 是虚构闰日，明确报错不静默修正。"""
    try:
        n = Decimal(serial_text.strip())
    except InvalidOperation:
        raise ConvertError("INVALID_DATE", f"非法日期序列号: {serial_text!r}")
    if n != n.to_integral_value():
        # 含时间部分的序列：只接受整数日，避免静默截断
        raise ConvertError("INVALID_DATE", f"日期序列含小数部分: {serial_text!r}")
    n = int(n)
    if not date1904:
        if n == 60:
            raise ConvertError(
                "EXCEL1900_FICTITIOUS_LEAP_DAY",
                "Excel 1900 日期系统 serial=60 对应不存在的 1900-02-29（虚构闰日）",
            )
        if n < 0 or n > 2958465:
            raise ConvertError("INVALID_DATE", f"日期序列越界: {n}")
        return EPOCH_1900 + _dt.timedelta(days=n)
    else:
        if n < 0 or n > 2957003:
            raise ConvertError("INVALID_DATE", f"日期序列越界: {n}")
        return EPOCH_1904 + _dt.timedelta(days=n)


def parse_date_text(text: str, formats) -> _dt.date:
    """文本日期只接受映射明示的格式；非法日期不进位；两位年份不猜世纪。"""
    s = text.strip()
    m = _DATE_TEXT_RE.match(s)
    if not m:
        raise ConvertError("INVALID_DATE_FORMAT", f"日期文本不符任何已声明格式: {text!r}")
    year_s = m.group(1)
    if len(year_s) == 2:
        raise ConvertError("TWO_DIGIT_YEAR", f"两位年份不猜世纪: {text!r}")
    year, month, day = int(year_s), int(m.group(2)), int(m.group(3))
    allowed = False
    for fmt in formats or []:
        if fmt in ("%Y-%m-%d", "YYYY-MM-DD"):
            allowed = True
    if not allowed:
        raise ConvertError("INVALID_DATE_FORMAT", f"格式未被映射声明: {text!r}")
    try:
        return _dt.date(year, month, day)
    except ValueError:
        raise ConvertError("INVALID_DATE", f"非法日历日期（不自动进位）: {text!r}")


def parse_month_text(text: str) -> str:
    s = text.strip()
    m = _MONTH_TEXT_RE.match(s)
    if not m:
        raise ConvertError("INVALID_MONTH", f"非法月份: {text!r}")
    month = int(m.group(2))
    if not (1 <= month <= 12):
        raise ConvertError("INVALID_MONTH", f"非法月份: {text!r}")
    return f"{m.group(1)}-{month:02d}"
