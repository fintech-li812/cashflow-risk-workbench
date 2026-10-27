# 文件说明：make_fixtures.py

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/修订交付/MEM-IMPORT-002/Codex/v2/fixtures/make_fixtures.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/%E4%BF%AE%E8%AE%A2%E4%BA%A4%E4%BB%98/MEM-IMPORT-002/Codex/v2/fixtures/make_fixtures.py)
- 归属：样例或测试夹具；可能故意无效，仅按所属测试使用
- 大小：4104字节
- 导出SHA256：847b8d3627b949a11570ed6f8f8327b6efdd8b7e286c64c6e659a1276ebccb94

## 内容与作用

模块说明：自造微型 xlsx 夹具生成器（源码交付，不只交手工截图）。

所有夹具都是明确的小号合成数据，与真实企业无关。
部分形态（公式缓存、空串、serial 60）openpyxl 写不出来，
用 patch_cell 直接改写包内 sheet XML 实现 —— 改写只发生在自己生成的夹具上。

主要函数：\`_fill_company\`, \`_fill_sheet\`, \`build_workbook\`, \`patch_cell\`, \`set_formula\`, \`set_serial\`, \`set_empty_string\`, \`set_blank_cell\`, \`make_input_dir\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
