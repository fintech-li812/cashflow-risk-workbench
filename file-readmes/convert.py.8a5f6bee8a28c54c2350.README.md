# 文件说明：convert.py

- 仓库路径：AI_Command_Workspace/发包/四个大型独立任务_20261025_v1/01_导入与追溯工程升级/参考候选/导入修订v2/src/mfg_import/convert.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E5%8F%91%E5%8C%85/%E5%9B%9B%E4%B8%AA%E5%A4%A7%E5%9E%8B%E7%8B%AC%E7%AB%8B%E4%BB%BB%E5%8A%A1_20261025_v1/01_%E5%AF%BC%E5%85%A5%E4%B8%8E%E8%BF%BD%E6%BA%AF%E5%B7%A5%E7%A8%8B%E5%8D%87%E7%BA%A7/%E5%8F%82%E8%80%83%E5%80%99%E9%80%89/%E5%AF%BC%E5%85%A5%E4%BF%AE%E8%AE%A2v2/src/mfg_import/convert.py)
- 归属：任务说明/接续指令；文件存在不代表已执行
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
