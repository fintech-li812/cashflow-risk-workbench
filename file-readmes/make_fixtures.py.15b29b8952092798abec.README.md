# 文件说明：make_fixtures.py

- 仓库路径：AI_Command_Workspace/发包/四个大型独立任务_20261025_v1/01_导入与追溯工程升级/参考候选/导入修订v2/fixtures/make_fixtures.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E5%8F%91%E5%8C%85/%E5%9B%9B%E4%B8%AA%E5%A4%A7%E5%9E%8B%E7%8B%AC%E7%AB%8B%E4%BB%BB%E5%8A%A1_20261025_v1/01_%E5%AF%BC%E5%85%A5%E4%B8%8E%E8%BF%BD%E6%BA%AF%E5%B7%A5%E7%A8%8B%E5%8D%87%E7%BA%A7/%E5%8F%82%E8%80%83%E5%80%99%E9%80%89/%E5%AF%BC%E5%85%A5%E4%BF%AE%E8%AE%A2v2/fixtures/make_fixtures.py)
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
