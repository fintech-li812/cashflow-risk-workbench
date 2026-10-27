# 文件说明：selftest.py

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/解包待审/MEM-IMPORT-002_WorkBuddy_v1/src/mfg_import/selftest.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/%E8%A7%A3%E5%8C%85%E5%BE%85%E5%AE%A1/MEM-IMPORT-002_WorkBuddy_v1/src/mfg_import/selftest.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：36949字节
- 导出SHA256：861724b6ba6ffbf0cfc0b01cf9a4a676242303a89cb1cb3df72291753eddd1e1

## 内容与作用

模块说明：selftest：只用自造合成夹具跑正反例，不依赖真实企业文件/网络/他人模块。

每个用例有：输入（夹具）、独立预期（tests/expected/expected_values.json 冻结文件）、
实际值、退出码。任一 FAIL/BLOCKED/意外异常 → 整体退出非 0（不 catch 后报 PASS）。

主要函数：\`cashflow_rec\`, \`ncodes\`, \`norm\`, \`tc_001_normal\`, \`tc_002_column_reorder\`, \`tc_003_missing_sheet\`, \`tc_004_missing_column\`, \`tc_005_duplicate_column\`, \`tc_006_alias_ambiguity\`, \`tc_007_vertical_reorder\`, \`tc_008_zero_and_empties\`, \`tc_009_numeric_text\`, \`tc_010_formula_cached\`, \`tc_011_formula_no_cache\`, \`tc_012_long_decimal\`

主要类：\`CaseFail\`, \`Ctx\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
