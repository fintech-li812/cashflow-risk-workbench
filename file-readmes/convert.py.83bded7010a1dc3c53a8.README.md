# 文件说明：convert.py

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/ZIP复现/MEM-IMPORT-002/src/mfg_import/convert.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/ZIP%E5%A4%8D%E7%8E%B0/MEM-IMPORT-002/src/mfg_import/convert.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：4992字节
- 导出SHA256：4a92b7128acf51cb18e9c697596d921021fbdba67d2ed18d88e72ceb0a7cc990

## 内容与作用

模块说明：金额与日期转换：全部用 Decimal / 显式规则，不猜、不静默修正。

规则要点（来自统一接口 v1 / 一期范围）：
- 金额用 Decimal，源万元按原精度乘 10000 后在元位 ROUND_HALF_UP 落到分；
  禁止先截到两位再换算（FIN-01 反例：1.234567 万 = 12345.67 元，不是 12300.00）。
- 非法/非有限金额（NaN、Infinity、bad 字符串）统一拒绝（FIN-02 反例）。
- 日期序列按工作簿 1900/1904 系统解释；serial 60 是 Excel1900 虚构闰日，
  不可静默变成合法业务日期；非法日期（2026-13-05、2026-02-30）不进位；
  两位年份不猜世纪。

主要函数：\`is_numeric_text\`, \`parse_decimal\`, \`wan_to_yuan_fen\`, \`yuan_to_fen_str\`, \`serial_to_date\`, \`parse_date_text\`, \`parse_month_text\`

主要类：\`ConvertError\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
