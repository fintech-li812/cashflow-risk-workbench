# 文件说明：__main__.py

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/ZIP复现/MEM-IMPORT-002/src/mfg_import/__main__.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/ZIP%E5%A4%8D%E7%8E%B0/MEM-IMPORT-002/src/mfg_import/__main__.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：2445字节
- 导出SHA256：85dffc6a8723adae2f1371c8343bf7ec01e05db152d771afc730249a34c96b4d

## 内容与作用

模块说明：CLI 入口：scan / verify / selftest。

退出码：
- scan:    0=技术执行成功（业务疑点见报告，不等于数据合格）；2=参数错误；1=运行错误
- verify:  0=全部核对通过；1=存在不符项或运行错误；2=参数错误
- selftest: 0=全部用例 PASS；1=存在 FAIL/BLOCKED/意外异常；2=参数错误

主要函数：\`main\`

命令行选项：--input, --output, --mapping, --tenant-id, --company-id, --period, --run-id, --unit-exceptions, --package, --source, --workdir；运行前先读所属README。

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
