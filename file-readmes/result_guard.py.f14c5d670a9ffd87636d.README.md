# 文件说明：result_guard.py

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/ZIP复现/MEM-EVIDENCE-001/src/result_guard.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/ZIP%E5%A4%8D%E7%8E%B0/MEM-EVIDENCE-001/src/result_guard.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：8982字节
- 导出SHA256：c2e0d46c1b480187466708ea4627b0f0f38e30c57688114bea317507743b118d

## 内容与作用

模块说明：mfg-agent-result.v1 结果校验守卫。

继承来源：01_源文件/参考候选/agent_guard.py（sha256 eb99d420e2ac7ef1352b448d0c29e1430d0a65cd80a76111eee3dc27c96055c1）。
本文件是**防御式改写**：原实现直接下标取值（data[&quot;period&quot;] / data[&quot;issues&quot;] / data[&quot;amounts&quot;]），
缺键时会抛 KeyError / TypeError 而不是受控的 ResultError，与本任务“程序异常不可伪装成功”的边界冲突。
校验规则、状态闭集、金额正则与原文件保持一致，不新增状态词、不改金额口径；差异登记在 04_继承与改动.csv。

本模块不做模型推理、不连服务器、不读写表格、不计算现金流。

主要函数：\`canonical_bytes\`, \`canonical_sha256\`, \`_require\`, \`money\`, \`load_result_json\`, \`_check_context\`, \`validate_result\`, \`reconciliation_state\`, \`difference_is_zero\`

主要类：\`ResultError\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
