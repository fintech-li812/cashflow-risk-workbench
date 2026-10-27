"""离线 HTML 报告：无外部脚本/请求，所有 Excel 内容 HTML 转义。"""
from html import escape


def _e(v):
    return escape("" if v is None else str(v))


def render_report(path, inventory, records, issues, identity):
    parts = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>",
        "<title>mfg-import.v1 导入报告</title>",
        "<style>body{font-family:system-ui,sans-serif;margin:24px;color:#222}",
        "table{border-collapse:collapse;margin:12px 0;font-size:13px}",
        "th,td{border:1px solid #ccc;padding:4px 8px;text-align:left;vertical-align:top}",
        "th{background:#f2f2f2}h1{font-size:20px}h2{font-size:16px;margin-top:24px}",
        ".mono{font-family:Consolas,monospace;font-size:12px}</style>",
        "</head><body>",
        "<h1>制造业 Excel 导入报告（离线）</h1>",
        "<p class='mono'>schema=%s | tool=%s | tenant=%s | company=%s | period=%s | run=%s</p>"
        % (
            _e(inventory["schema"]), _e(inventory["tool_version"]),
            _e(identity["tenant_id"]), _e(identity["company_id"]),
            _e(identity["period"]), _e(identity["run_id"]),
        ),
        "<p class='mono'>source_revision=%s</p>" % _e(inventory["source_revision"]),
        "<h2>输入文件</h2><table><tr><th>逻辑名</th><th>SHA256</th><th>日期系统</th><th>Sheet（识别/原始计数）</th></tr>",
    ]
    for inp in inventory["inputs"]:
        sheets = "; ".join(
            "%s(%s, %d)" % (_e(s["name"]), "是" if s.get("recognized") else "登记",
                            s.get("raw_record_count", 0))
            for s in inp["sheets"]
        )
        parts.append(
            "<tr><td>%s</td><td class='mono'>%s</td><td>%s</td><td>%s</td></tr>"
            % (_e(inp["logical_name"]), _e(inp["sha256"]), _e(inp["date_system"]), sheets)
        )
    parts.append("</table>")
    parts.append(
        "<h2>问题清单（%d 条）</h2><table><tr><th>ID</th><th>代码</th><th>文件</th>"
        "<th>Sheet</th><th>地址</th><th>行</th><th>原值</th><th>原因</th><th>建议动作</th></tr>"
        % len(issues)
    )
    for i in issues:
        parts.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
            "<td class='mono'>%s</td><td>%s</td><td>%s</td></tr>"
            % tuple(_e(i[k]) for k in ("issue_id", "code", "file", "sheet",
                                       "address", "row", "raw", "reason", "action"))
        )
    parts.append("</table>")
    parts.append(
        "<h2>记录概览（%d 条）</h2><table><tr><th>source_record_key</th><th>Sheet</th>"
        "<th>行</th><th>规范字段（字段=值 @地址）</th></tr>" % len(records)
    )
    for r in records:
        norm = "; ".join(
            "%s=%s @%s" % (_e(k), _e(v["value"]), _e(v["address"]))
            for k, v in r["normalized"].items()
        )
        parts.append(
            "<tr><td class='mono'>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (_e(r["source_record_key"]), _e(r["sheet"]), _e(r["row"]), norm)
        )
    parts.append("</table></body></html>")
    with open(path, "wb") as f:
        f.write("".join(parts).encode("utf-8"))
