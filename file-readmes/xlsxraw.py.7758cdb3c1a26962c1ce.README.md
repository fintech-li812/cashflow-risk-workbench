# 文件说明：xlsxraw.py

- 仓库路径：AI_Command_Workspace/发包/四个大型独立任务_20261025_v1/01_导入与追溯工程升级/参考候选/导入修订v2/src/mfg_import/xlsxraw.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E5%8F%91%E5%8C%85/%E5%9B%9B%E4%B8%AA%E5%A4%A7%E5%9E%8B%E7%8B%AC%E7%AB%8B%E4%BB%BB%E5%8A%A1_20261025_v1/01_%E5%AF%BC%E5%85%A5%E4%B8%8E%E8%BF%BD%E6%BA%AF%E5%B7%A5%E7%A8%8B%E5%8D%87%E7%BA%A7/%E5%8F%82%E8%80%83%E5%80%99%E9%80%89/%E5%AF%BC%E5%85%A5%E4%BF%AE%E8%AE%A2v2/src/mfg_import/xlsxraw.py)
- 归属：任务说明/接续指令；文件存在不代表已执行
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
