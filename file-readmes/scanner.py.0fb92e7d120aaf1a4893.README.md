# 文件说明：scanner.py

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/修订交付/MEM-IMPORT-002/Codex/v2/src/mfg_import/scanner.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/%E4%BF%AE%E8%AE%A2%E4%BA%A4%E4%BB%98/MEM-IMPORT-002/Codex/v2/src/mfg_import/scanner.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：23912字节
- 导出SHA256：668a244e200de85804a059a14b8498d818a280ba4bdb5e996846aea9f75f5efa

## 内容与作用

模块说明：scan：把制造业 xlsx 变成有原始单元格证据的 mfg-import.v1 规范数据包。

主要函数：\`_norm_header\`, \`validate_identity\`, \`ensure_fresh_output_dir\`, \`check_safe_relpath\`, \`load_mapping\`, \`load_unit_exceptions\`, \`_cell_snapshot\`, \`_convert_cell\`, \`_match_columns\`, \`_scan_horizontal\`, \`_scan_vertical\`, \`_report_duplicates\`, \`scan\`, \`_write_json\`, \`csv_safe\`

主要类：\`ScanError\`, \`IssueSink\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
