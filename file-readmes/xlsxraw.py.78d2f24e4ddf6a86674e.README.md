# 文件说明：xlsxraw.py

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/解包待审/MEM-IMPORT-002_WorkBuddy_v1/src/mfg_import/xlsxraw.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/%E8%A7%A3%E5%8C%85%E5%BE%85%E5%AE%A1/MEM-IMPORT-002_WorkBuddy_v1/src/mfg_import/xlsxraw.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：5852字节
- 导出SHA256：c8dbd3b273c636e7eef0a057f18e24fe91fd93bbeffbe6cdf3a4b4ac72d4a5ca

## 内容与作用

模块说明：xlsx 原始 XML 只读读取。

直接解析 xl/ 下的 XML，保留每个单元格的：
- 原始数值文本（不经过 float，避免 80.59999999999999 被显示成 80.6 后当成原值）
- 单元格类型（数值/文本/数字文本/布尔/错误）
- 公式原文与缓存值（缓存缺失绝不 eval 代算）
- 空白（元素不存在）/ 显式空白单元格（无 &lt;v&gt;）/ 空字符串 / 空格 的区别
- 工作簿日期系统（1900/1904）

不执行宏、不解析外部链接、不运行任何单元格内容。

主要函数：\`col_to_num\`, \`num_to_col\`, \`split_address\`, \`_text_of_si\`, \`read_workbook\`, \`_read_sheet\`

主要类：\`RawCell\`, \`RawSheet\`, \`RawWorkbook\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
