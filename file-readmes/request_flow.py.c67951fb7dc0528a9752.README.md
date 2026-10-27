# 文件说明：request_flow.py

- 仓库路径：AI_Command_Workspace/交付/CX-AGENT-FIX-001/Codex/v1/candidate/request_flow.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E4%BA%A4%E4%BB%98/CX-AGENT-FIX-001/Codex/v1/candidate/request_flow.py)
- 归属：交付或存档材料；包/文档不等于发布或验收通过
- 大小：9707字节
- 导出SHA256：17039cea3c37a7db3d8c0741b884d5a45b0fdbc2e6c5bdcebdfaa5e4d0fc20ee

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
