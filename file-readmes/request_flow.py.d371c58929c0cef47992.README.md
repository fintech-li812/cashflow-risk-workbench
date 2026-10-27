# 文件说明：request_flow.py

- 仓库路径：AI_Command_Workspace/验收/WB-AGENT-003/Codex/边界反例_20261023_v1/冻结代码/request_flow.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/WB-AGENT-003/Codex/%E8%BE%B9%E7%95%8C%E5%8F%8D%E4%BE%8B_20261023_v1/%E5%86%BB%E7%BB%93%E4%BB%A3%E7%A0%81/request_flow.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：8052字节
- 导出SHA256：4acf699159af53cdbf5fb1ad0341a7ccc286f7c9d5dbc7c584b914a4ae4b832b

## 内容与作用

模块说明：WB-AGENT-003 请求流程：绑定可信身份、源版本失效重取、统一接口守卫。

范围依据：333.md B 项。本模块不实现算法、不心算金额、不替代千问表格公式。
结果校验直接复用继承来的 agent_guard，不在本文件重复造一套判定规则。

主要函数：\`validate_binding\`, \`pre_guard_amounts\`, \`_block\`, \`blocked_report\`, \`source_revision_of\`

主要类：\`FlowBlocked\`, \`FlowResult\`, \`RequestFlow\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
