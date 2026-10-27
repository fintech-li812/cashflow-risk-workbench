# 文件说明：__init__.py

- 仓库路径：AI_Command_Workspace/交付/WB-AGENT-003/WorkBuddy/v1/candidate/__init__.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E4%BA%A4%E4%BB%98/WB-AGENT-003/WorkBuddy/v1/candidate/__init__.py)
- 归属：交付或存档材料；包/文档不等于发布或验收通过
- 大小：696字节
- 导出SHA256：6820218f14ce7acdafda68fa158bebd0eadebe0be7e1a754ecd91167c19219a5

## 内容与作用

模块说明：WB-AGENT-003 候选代码包：制造业 Agent 接入工程（非算法外围）。

模块分工：
  agent_guard.py     继承 CX-AGENT-002（未修改冻结内容）：结果校验与渲染
  runtime_adapter.py A 项：四类内部能力接口 + 结构化 unavailable
  request_flow.py    B 项：可信绑定、源版本失效重取、守卫
  persistence.py     C 项：逐字段映射、幂等、回执、精确回查、超时不确定态
  adapters.py        后端组合（含仅测试可用的离线夹具后端）

本包不含算法、不连接服务器、不读写生产库、不部署。

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
